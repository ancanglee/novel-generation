"""MemoryFacade skeleton. Concrete implementation lives in U3 construction phase."""

from novelgen_memory.facade import MemoryFacade
from novelgen_memory.models import CharacterSnapshot, GraphEdge, GraphNode, VectorHit

__all__ = [
    "CharacterSnapshot",
    "GraphEdge",
    "GraphNode",
    "MemoryFacade",
    "VectorHit",
]
