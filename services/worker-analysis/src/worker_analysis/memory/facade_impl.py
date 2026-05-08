"""MemoryFacade concrete implementation.

Architecture (post-AgentCore):
- **AgentCore Memory is the system of record** for facts. Writes there MUST succeed
  or we raise `MemoryBackendError` → caller routes to DLQ.
- Neptune (graph) + OpenSearch (vector) are **enhancement stores**. Writes are
  best-effort and degrade silently (with metrics). Reads fall through to them only
  when Memory returns zero results.
- No more `except NotImplementedError: log.warning(...)` silent placeholders. AgentCore
  calls are real SDK invocations; failures propagate.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
from typing import Any
from uuid import UUID

import aioboto3
from cachetools import LRUCache
from novelgen_memory.facade import MemoryFacade
from novelgen_memory.models import CharacterSnapshot, GraphEdge, GraphNode, VectorHit
from novelgen_obs import emit_metric, get_logger
from novelgen_types.fact import Fact

from worker_analysis.memory.agentcore_memory import (
    AgentCoreMemoryClient,
    MemoryItem,
    MemoryReadError,
    MemoryWriteError,
)
from worker_analysis.memory.neptune_client import NeptuneSignedClient
from worker_analysis.memory.opensearch_client import OpenSearchVectorClient

log = get_logger("worker-analysis.memory")

_EMBED_CACHE: LRUCache[str, list[float]] = LRUCache(maxsize=1000)


class MemoryBackendError(Exception):
    """AgentCore Memory write failed — fatal for the Fact batch."""


class MemoryFacadeImpl(MemoryFacade):
    """Concrete MemoryFacade with AgentCore Memory as authoritative store."""

    def __init__(
        self,
        agentcore: AgentCoreMemoryClient,
        neptune: NeptuneSignedClient | None,
        opensearch: OpenSearchVectorClient | None,
        *,
        embed_model: str = "amazon.titan-embed-text-v2:0",
        region: str = "us-west-2",
    ) -> None:
        self._agentcore = agentcore
        self._neptune = neptune
        self._opensearch = opensearch
        self._embed_model = embed_model
        self._region = region
        self._session = aioboto3.Session()

    # ------------------------------------------------------------------
    # AgentCore Memory (authoritative)
    # ------------------------------------------------------------------

    async def remember(
        self,
        team_id: UUID,
        novel_id: UUID,
        facts: list[Fact],
        *,
        session_id: str | None = None,
    ) -> None:
        """Write facts to AgentCore Memory (must succeed) + graph/vector (best effort).

        `session_id` defaults to "facts" if unspecified; callers with a job_id should
        pass `session_id=str(job_id)` to group events per job.
        """
        if not facts:
            return

        items = [
            MemoryItem(
                fact_key=f.fact_key,
                content=f.content or {},
                fact_type=f.fact_type.value if hasattr(f.fact_type, "value") else str(f.fact_type),
                source_chapter=f.source_chapter,
            )
            for f in facts
        ]

        # Step 1: AgentCore Memory — must succeed.
        try:
            await self._agentcore.put_batch(
                team_id,
                novel_id,
                items,
                session_id=session_id or "facts",
            )
            emit_metric("MemoryWriteSuccess", 1.0, dimensions={"Layer": "agentcore"})
        except MemoryWriteError as e:
            emit_metric("MemoryWriteFailure", 1.0, dimensions={"Layer": "agentcore"})
            raise MemoryBackendError(f"AgentCore Memory write failed: {e}") from e

        # Step 2 + 3: Neptune (graph) + OpenSearch (vector) in parallel — best-effort.
        await asyncio.gather(
            self._try_write_graph(team_id, novel_id, facts),
            self._try_write_vectors(team_id, novel_id, facts),
            return_exceptions=True,
        )

    async def _try_write_graph(
        self, team_id: UUID, novel_id: UUID, facts: list[Fact]
    ) -> None:
        if self._neptune is None:
            return
        try:
            tid = str(team_id)
            nid = str(novel_id)
            for fact in facts:
                label, node_id, props = _fact_to_graph_node(fact)
                if not label:
                    continue
                await self._neptune.upsert_node(label, tid, nid, node_id, props)
        except Exception as e:
            log.warning("Neptune write failed; degrading", extra={"error": str(e)})
            emit_metric("MemoryWriteFailure", 1.0, dimensions={"Layer": "neptune"})

    async def _try_write_vectors(
        self, team_id: UUID, novel_id: UUID, facts: list[Fact]
    ) -> None:
        if self._opensearch is None:
            return
        try:
            docs = []
            for fact in facts:
                text = _fact_text(fact)
                if not text:
                    continue
                embedding = await self.embed(text)
                docs.append(
                    {
                        "fact_key": fact.fact_key,
                        "fact_type": fact.fact_type.value,
                        "chapter": fact.source_chapter or 0,
                        "content_text": text,
                        "embedding": embedding,
                    }
                )
            if docs:
                await self._opensearch.bulk_index(team_id, novel_id, docs)
        except Exception as e:
            log.warning("OpenSearch write failed; degrading", extra={"error": str(e)})
            emit_metric("MemoryWriteFailure", 1.0, dimensions={"Layer": "opensearch"})

    async def recall(
        self, team_id: UUID, novel_id: UUID, query: str, top_k: int = 20
    ) -> list[Fact]:
        """Retrieve facts. Primary: AgentCore Memory. Fallback: OpenSearch."""
        # Primary path — AgentCore Memory.
        try:
            records = await self._agentcore.retrieve(
                team_id, novel_id, query=query, top_k=top_k
            )
            emit_metric("MemoryReadSuccess", 1.0, dimensions={"Layer": "agentcore"})
        except MemoryReadError as e:
            log.warning("AgentCore recall failed; falling back to vector", extra={"error": str(e)})
            emit_metric("MemoryReadFailure", 1.0, dimensions={"Layer": "agentcore"})
            records = []

        if records:
            return [_memory_record_to_fact(team_id, novel_id, r) for r in records]

        # Fallback — OpenSearch (degraded mode).
        if self._opensearch is None:
            return []
        try:
            embedding = await self.embed(query)
            hits = await self._opensearch.knn_search(team_id, novel_id, embedding, top_k)
        except Exception as e:
            log.warning("OpenSearch fallback failed; empty", extra={"error": str(e)})
            emit_metric("MemoryReadFailure", 1.0, dimensions={"Layer": "opensearch"})
            return []

        results: list[Fact] = []
        for hit in hits:
            src = hit.get("_source", {})
            try:
                results.append(
                    Fact(
                        fact_key=src["fact_key"],
                        team_id=team_id,
                        novel_id=novel_id,
                        fact_type=src.get("fact_type"),
                        content={"text": src.get("content_text", "")},
                        source_chapter=src.get("chapter") or None,
                    )
                )
            except Exception:
                continue
        return results

    async def get_character(
        self,
        team_id: UUID,
        novel_id: UUID,
        character_id: str,
        at_chapter: int | None = None,
    ) -> CharacterSnapshot | None:
        """Pull the most recent CHARACTER_SNAPSHOT for character_id from Memory."""
        query = f"character snapshot for {character_id}"
        if at_chapter is not None:
            query += f" at or before chapter {at_chapter}"
        try:
            records = await self._agentcore.retrieve(
                team_id, novel_id, query=query, top_k=10
            )
        except MemoryReadError as e:
            log.warning("get_character recall failed", extra={"error": str(e)})
            return None

        for rec in records:
            try:
                payload = json.loads(rec.content_text)
            except (ValueError, TypeError):
                continue
            content = payload.get("content") or {}
            if content.get("character_id") == character_id:
                if at_chapter is not None and content.get("chapter", 0) > at_chapter:
                    continue
                return CharacterSnapshot(
                    character_id=character_id,
                    display_name=content.get("display_name", character_id),
                    chapter=int(content.get("chapter", 0)),
                    attributes=content,
                )
        return None

    # ------------------------------------------------------------------
    # Graph (enhancement store)
    # ------------------------------------------------------------------

    async def upsert_graph(
        self,
        team_id: UUID,
        novel_id: UUID,
        nodes: list[GraphNode],
        edges: list[GraphEdge],
    ) -> None:
        if self._neptune is None:
            log.debug("upsert_graph skipped: no neptune configured")
            return
        tid = str(team_id)
        nid = str(novel_id)
        try:
            for node in nodes:
                label = node.labels[0] if node.labels else "Node"
                await self._neptune.upsert_node(label, tid, nid, node.node_id, node.properties)
            for edge in edges:
                await self._neptune.upsert_edge(
                    from_label="Node",
                    to_label="Node",
                    edge_type=edge.edge_type,
                    team_id=tid,
                    novel_id=nid,
                    from_id=edge.from_id,
                    to_id=edge.to_id,
                    properties=edge.properties,
                )
        except Exception as e:
            log.warning("Neptune upsert_graph failed; degrading", extra={"error": str(e)})
            emit_metric("MemoryWriteFailure", 1.0, dimensions={"Layer": "neptune"})

    async def neighbors(
        self,
        team_id: UUID,
        novel_id: UUID,
        node_id: str,
        edge_type: str | None = None,
        depth: int = 1,
    ) -> list[GraphNode]:
        if self._neptune is None:
            return []
        try:
            rows = await self._neptune.neighbors(
                str(team_id), str(novel_id), node_id, edge_type=edge_type, limit=50
            )
        except Exception as e:
            log.warning("Neptune neighbors failed; empty", extra={"error": str(e)})
            return []
        results: list[GraphNode] = []
        for row in rows:
            nb = row.get("neighbor") or {}
            props = nb.get("properties", {}) if isinstance(nb, dict) else {}
            results.append(
                GraphNode(
                    node_id=props.get("node_id", ""),
                    labels=nb.get("labels", []) if isinstance(nb, dict) else [],
                    properties=props,
                )
            )
        return results

    # ------------------------------------------------------------------
    # Vectors (enhancement store)
    # ------------------------------------------------------------------

    async def index_vector(
        self,
        team_id: UUID,
        novel_id: UUID,
        chunk_id: str,
        embedding: list[float],
        payload: dict[str, Any],
    ) -> None:
        if self._opensearch is None:
            return
        doc = {"fact_key": chunk_id, "embedding": embedding, **payload}
        await self._opensearch.bulk_index(team_id, novel_id, [doc])

    async def search_similar(
        self,
        team_id: UUID,
        novel_id: UUID,
        embedding: list[float],
        top_k: int = 10,
        filters: dict[str, Any] | None = None,
    ) -> list[VectorHit]:
        if self._opensearch is None:
            return []
        hits = await self._opensearch.knn_search(team_id, novel_id, embedding, top_k, filters)
        return [
            VectorHit(
                fact_key=h["_id"],
                score=h.get("_score", 0.0),
                payload=h.get("_source", {}),
            )
            for h in hits
        ]

    async def hybrid_search(
        self,
        team_id: UUID,
        novel_id: UUID,
        query_text: str,
        query_embed: list[float],
        top_k: int = 10,
    ) -> list[VectorHit]:
        if self._opensearch is None:
            return []
        hits = await self._opensearch.hybrid_search(
            team_id, novel_id, query_text, query_embed, top_k
        )
        return [
            VectorHit(
                fact_key=h["_id"],
                score=h.get("_score", 0.0),
                payload=h.get("_source", {}),
            )
            for h in hits
        ]

    # ------------------------------------------------------------------
    # Embeddings
    # ------------------------------------------------------------------

    async def embed(self, text: str) -> list[float]:
        key = hashlib.sha256(text.encode("utf-8")).hexdigest()
        cached = _EMBED_CACHE.get(key)
        if cached is not None:
            emit_metric("EmbeddingCacheHit", 1.0)
            return cached

        async with self._session.client("bedrock-runtime", region_name=self._region) as client:
            resp = await client.invoke_model(
                modelId=self._embed_model,
                body=json.dumps({"inputText": text[:8000], "normalize": True}),
            )
            payload = json.loads(await resp["body"].read())
        vector = payload.get("embedding") or []
        _EMBED_CACHE[key] = vector
        return vector


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------

def _fact_text(fact: Fact) -> str:
    content = fact.content or {}
    if isinstance(content, dict):
        return str(content.get("text") or content.get("summary") or json.dumps(content)[:1000])
    return str(content)[:1000]


def _fact_to_graph_node(fact: Fact) -> tuple[str, str, dict[str, Any]]:
    ft = fact.fact_type.value if hasattr(fact.fact_type, "value") else str(fact.fact_type)
    if ft == "CHARACTER_SNAPSHOT":
        name = (fact.content or {}).get("character_id", "")
        return "Character", name, fact.content or {}
    if ft == "MAP_PLACE":
        pid = (fact.content or {}).get("place_id", "")
        return "Place", pid, fact.content or {}
    if ft == "EVENT":
        eid = (fact.content or {}).get("event_id", "")
        return "Event", eid, fact.content or {}
    return "", "", {}


def _memory_record_to_fact(team_id: UUID, novel_id: UUID, rec) -> Fact:
    """Parse a MemoryRecord.content_text (which is JSON of the original MemoryItem)."""
    try:
        payload = json.loads(rec.content_text)
    except (ValueError, TypeError):
        payload = {}
    return Fact(
        fact_key=payload.get("fact_key", rec.record_id),
        team_id=team_id,
        novel_id=novel_id,
        fact_type=payload.get("fact_type"),
        content=payload.get("content") or {},
        source_chapter=payload.get("source_chapter"),
    )
