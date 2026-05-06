"""Abstract MemoryFacade interface. U3 provides concrete implementation."""

from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from novelgen_types.fact import Fact

from novelgen_memory.models import CharacterSnapshot, GraphEdge, GraphNode, VectorHit


class MemoryFacade(ABC):
    """Unified interface over AgentCore Memory + Neptune + OpenSearch Serverless."""

    # AgentCore Memory --------------------------------------------------------

    @abstractmethod
    async def remember(self, team_id: UUID, novel_id: UUID, facts: list[Fact]) -> None:
        """Idempotently upsert facts keyed by fact_key."""

    @abstractmethod
    async def recall(
        self, team_id: UUID, novel_id: UUID, query: str, top_k: int = 20
    ) -> list[Fact]:
        """Retrieve facts relevant to a natural-language query."""

    @abstractmethod
    async def get_character(
        self,
        team_id: UUID,
        novel_id: UUID,
        character_id: str,
        at_chapter: int | None = None,
    ) -> CharacterSnapshot | None:
        """Fetch the character snapshot closest to (but not after) at_chapter."""

    # Neptune knowledge graph -------------------------------------------------

    @abstractmethod
    async def upsert_graph(
        self,
        team_id: UUID,
        novel_id: UUID,
        nodes: list[GraphNode],
        edges: list[GraphEdge],
    ) -> None:
        """Idempotently upsert graph nodes and edges."""

    @abstractmethod
    async def neighbors(
        self,
        team_id: UUID,
        novel_id: UUID,
        node_id: str,
        edge_type: str | None = None,
        depth: int = 1,
    ) -> list[GraphNode]:
        """Graph neighborhood traversal."""

    # OpenSearch vector -------------------------------------------------------

    @abstractmethod
    async def index_vector(
        self,
        team_id: UUID,
        novel_id: UUID,
        chunk_id: str,
        embedding: list[float],
        payload: dict[str, object],
    ) -> None:
        """Index a chunk embedding."""

    @abstractmethod
    async def search_similar(
        self,
        team_id: UUID,
        novel_id: UUID,
        embedding: list[float],
        top_k: int = 10,
        filters: dict[str, object] | None = None,
    ) -> list[VectorHit]:
        """Vector kNN search with optional filters."""

    @abstractmethod
    async def hybrid_search(
        self,
        team_id: UUID,
        novel_id: UUID,
        query_text: str,
        query_embed: list[float],
        top_k: int = 10,
    ) -> list[VectorHit]:
        """BM25 + vector hybrid search."""

    # Embeddings --------------------------------------------------------------

    @abstractmethod
    async def embed(self, text: str) -> list[float]:
        """Encode text to an embedding vector (Titan Embeddings V2 in U1 default)."""
