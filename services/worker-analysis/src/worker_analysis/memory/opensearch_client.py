"""OpenSearch Serverless Vector Search client with kNN + bulk write."""

from __future__ import annotations

from typing import Any
from uuid import UUID

import boto3
from opensearchpy import AsyncOpenSearch, AWSV4SignerAsyncAuth, RequestsHttpConnection


INDEX_TEMPLATE_NAME = "facts-template"
INDEX_TEMPLATE = {
    "index_patterns": ["facts-*"],
    "template": {
        "settings": {
            "index.knn": True,
            "index.knn.algo_param.ef_search": 100,
        },
        "mappings": {
            "properties": {
                "team_id": {"type": "keyword"},
                "novel_id": {"type": "keyword"},
                "fact_key": {"type": "keyword"},
                "fact_type": {"type": "keyword"},
                "chapter": {"type": "integer"},
                "content_text": {"type": "text"},
                "embedding": {
                    "type": "knn_vector",
                    "dimension": 1024,
                    "method": {
                        "name": "hnsw",
                        "space_type": "cosinesimil",
                        "engine": "nmslib",
                        "parameters": {"ef_construction": 512, "m": 16},
                    },
                },
            }
        },
    },
}


class OpenSearchVectorClient:
    """kNN + bulk write wrapper for OpenSearch Serverless."""

    def __init__(self, endpoint: str, region: str = "us-east-1") -> None:
        host = endpoint.replace("https://", "").replace("http://", "").rstrip("/")
        credentials = boto3.Session().get_credentials()
        auth = AWSV4SignerAsyncAuth(credentials, region, "aoss")
        self._client = AsyncOpenSearch(
            hosts=[{"host": host, "port": 443}],
            http_auth=auth,
            use_ssl=True,
            verify_certs=True,
            connection_class=RequestsHttpConnection,
        )
        self._known_indices: set[str] = set()

    async def close(self) -> None:
        await self._client.close()

    @staticmethod
    def index_name(team_id: UUID) -> str:
        return f"facts-{team_id}"

    async def ensure_template(self) -> None:
        await self._client.indices.put_index_template(
            name=INDEX_TEMPLATE_NAME, body=INDEX_TEMPLATE
        )

    async def ensure_index(self, team_id: UUID) -> None:
        idx = self.index_name(team_id)
        if idx in self._known_indices:
            return
        exists = await self._client.indices.exists(index=idx)
        if not exists:
            await self._client.indices.create(index=idx)
        self._known_indices.add(idx)

    async def bulk_index(
        self, team_id: UUID, novel_id: UUID, documents: list[dict[str, Any]]
    ) -> None:
        if not documents:
            return
        await self.ensure_index(team_id)
        idx = self.index_name(team_id)
        actions: list[dict[str, Any]] = []
        for doc in documents:
            actions.append({"index": {"_index": idx, "_id": doc["fact_key"]}})
            actions.append(
                {
                    **doc,
                    "team_id": str(team_id),
                    "novel_id": str(novel_id),
                }
            )
        await self._client.bulk(body=actions)

    async def knn_search(
        self,
        team_id: UUID,
        novel_id: UUID,
        embedding: list[float],
        top_k: int = 20,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        idx = self.index_name(team_id)
        must_filters = [
            {"term": {"team_id": str(team_id)}},
            {"term": {"novel_id": str(novel_id)}},
        ]
        if filters:
            for k, v in filters.items():
                must_filters.append({"term": {k: v}})

        body = {
            "size": top_k,
            "query": {
                "bool": {
                    "filter": must_filters,
                    "must": [{"knn": {"embedding": {"vector": embedding, "k": top_k}}}],
                }
            },
        }
        resp = await self._client.search(index=idx, body=body)
        return [hit for hit in resp.get("hits", {}).get("hits", [])]

    async def hybrid_search(
        self,
        team_id: UUID,
        novel_id: UUID,
        query_text: str,
        embedding: list[float],
        top_k: int = 20,
    ) -> list[dict[str, Any]]:
        """BM25 + kNN hybrid via two searches + client-side RRF."""
        idx = self.index_name(team_id)
        filters = [
            {"term": {"team_id": str(team_id)}},
            {"term": {"novel_id": str(novel_id)}},
        ]
        bm25_body = {
            "size": top_k,
            "query": {
                "bool": {
                    "filter": filters,
                    "must": [{"match": {"content_text": query_text}}],
                }
            },
        }
        knn_body = {
            "size": top_k,
            "query": {
                "bool": {
                    "filter": filters,
                    "must": [{"knn": {"embedding": {"vector": embedding, "k": top_k}}}],
                }
            },
        }
        bm25 = await self._client.search(index=idx, body=bm25_body)
        knn = await self._client.search(index=idx, body=knn_body)
        return _rrf_merge(
            bm25.get("hits", {}).get("hits", []),
            knn.get("hits", {}).get("hits", []),
            top_k,
        )


def _rrf_merge(
    a: list[dict[str, Any]], b: list[dict[str, Any]], top_k: int, k: int = 60
) -> list[dict[str, Any]]:
    scores: dict[str, float] = {}
    by_id: dict[str, dict[str, Any]] = {}
    for rank, hit in enumerate(a):
        doc_id = hit["_id"]
        scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank + 1)
        by_id[doc_id] = hit
    for rank, hit in enumerate(b):
        doc_id = hit["_id"]
        scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank + 1)
        by_id.setdefault(doc_id, hit)
    ordered = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)[:top_k]
    return [by_id[doc_id] for doc_id, _ in ordered]
