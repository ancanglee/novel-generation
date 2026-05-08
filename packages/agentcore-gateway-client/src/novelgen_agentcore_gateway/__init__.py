"""AgentCore Gateway client.

Two surfaces:
- `GatewayControlClient` — CRUD for Gateway / GatewayTarget (used by CDK bootstrap Lambda).
- `GatewayMcpClient` — HTTPS MCP-over-SSE invocation client for agents.
"""

from novelgen_agentcore_gateway.control import (
    GatewayControlClient,
    GatewayDescribe,
    GatewayTargetDescribe,
)
from novelgen_agentcore_gateway.mcp import (
    GatewayAuthError,
    GatewayMcpClient,
    GatewayToolError,
    ToolResult,
)

__all__ = [
    "GatewayControlClient",
    "GatewayDescribe",
    "GatewayTargetDescribe",
    "GatewayMcpClient",
    "GatewayAuthError",
    "GatewayToolError",
    "ToolResult",
]
