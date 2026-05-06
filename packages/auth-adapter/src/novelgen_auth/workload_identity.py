"""Thin client for AgentCore Identity: fetch workload tokens for Agent->downstream-tool calls.

V1 is a placeholder wrapper; actual AgentCore Identity SDK binding is filled in U3/U4 when
Agents consume external tools via Gateway.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class WorkloadToken:
    access_token: str
    expires_at: int


class WorkloadIdentityClient:
    """Placeholder for AgentCore Identity integration."""

    def __init__(self, agent_id: str) -> None:
        self.agent_id = agent_id

    def get_token(self, resource: str) -> WorkloadToken:
        """Request a workload token from AgentCore Identity for the given downstream resource."""
        raise NotImplementedError(
            "AgentCore Identity binding not yet implemented; "
            "to be wired in U3/U4 when Agents call external tools via Gateway"
        )
