"""write_memory — thin wrapper that calls MemoryFacade.remember + upsert_graph.

Exposed as a Supervisor tool so it can flush batched facts/nodes/edges collected
across multiple sub-agents in one step.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from novelgen_memory.models import GraphEdge, GraphNode
from novelgen_obs import emit_metric, get_logger
from novelgen_types.fact import Fact

log = get_logger("worker-analysis.memory_writer")


async def write_memory(
    facade: Any,
    team_id: UUID,
    novel_id: UUID,
    facts: list[Fact],
    nodes: list[GraphNode] | None = None,
    edges: list[GraphEdge] | None = None,
) -> dict[str, int]:
    """Flush a batch to MemoryFacade. Returns counts per layer."""
    if facts:
        await facade.remember(team_id, novel_id, facts)
    if nodes or edges:
        await facade.upsert_graph(team_id, novel_id, nodes or [], edges or [])

    result = {
        "facts": len(facts),
        "nodes": len(nodes or []),
        "edges": len(edges or []),
    }
    emit_metric("MemoryFlushCount", float(sum(result.values())))
    log.info("memory flush complete", extra=result)
    return result
