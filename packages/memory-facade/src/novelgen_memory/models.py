"""Graph & vector retrieval result types used by MemoryFacade."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class GraphNode(BaseModel):
    node_id: str
    labels: list[str]
    properties: dict[str, Any]


class GraphEdge(BaseModel):
    edge_id: str
    edge_type: str
    from_id: str
    to_id: str
    properties: dict[str, Any] = {}


class VectorHit(BaseModel):
    fact_key: str
    score: float
    payload: dict[str, Any]


class CharacterSnapshot(BaseModel):
    character_id: str
    chapter: int
    attributes: dict[str, Any]
