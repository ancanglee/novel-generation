"""Worker-level AgentCore Runtime health check + heartbeat.

Design change vs V1:
- **Runtime itself is created by CDK at deploy time** (one `CreateAgentRuntime` per role).
  The worker no longer creates runtimes at startup — it only verifies the runtime it's
  supposed to belong to is READY, and stamps a DDB heartbeat row for operators.
- DDB conditional put (`AGENT_REG#{env}#AGENT#{agent_id}`) is kept as a process-level
  "i-am-alive" signal and for race-free first-time registration logs. Failure to claim
  the DDB row is not fatal — multiple workers are expected to run the same AgentRuntime.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime

from novelgen_agentcore_runtime import (
    AgentRuntimeDescribe,
    AgentRuntimeNotReady,
    RuntimeClient,
)
from novelgen_obs import get_logger
from novelgen_storage import DynamoDBAdapter

log = get_logger("worker-analysis.registration")


class AgentCoreRegistrar:
    def __init__(
        self,
        jobs_table: DynamoDBAdapter,
        *,
        agent_id: str,
        env: str,
        runtime_id: str | None = None,
        region: str | None = None,
    ) -> None:
        self._ddb = jobs_table
        self._agent_id = agent_id
        self._env = env
        self._runtime_id = runtime_id or os.environ.get("AGENTCORE_RUNTIME_ID", "")
        self._runtime_client = RuntimeClient(
            region=region or os.environ.get("AWS_REGION", "us-west-2")
        )

    async def register_if_needed(self) -> AgentRuntimeDescribe | None:
        """Verify the runtime is READY and record a DDB heartbeat.

        Returns the runtime describe if verification succeeds, None if skipped
        (e.g. no runtime_id configured, which is allowed in dev/local tests).
        """
        if not self._runtime_id:
            log.info(
                "no AGENTCORE_RUNTIME_ID configured; skipping runtime verification",
                extra={"agent_id": self._agent_id},
            )
            return None

        describe = await self._runtime_client.wait_until_ready(
            self._runtime_id, timeout_seconds=120, poll_seconds=5
        )

        await self._stamp_heartbeat(describe.arn)
        log.info(
            "agentcore runtime verified READY",
            extra={
                "agent_id": self._agent_id,
                "runtime_id": self._runtime_id,
                "runtime_arn": describe.arn,
            },
        )
        return describe

    async def _stamp_heartbeat(self, runtime_arn: str) -> None:
        try:
            await self._ddb.put_if_absent(
                team_id=None,  # type: ignore[arg-type]
                item={
                    "pk": f"AGENT_REG#{self._env}",
                    "sk": f"AGENT#{self._agent_id}",
                    "agent_id": self._agent_id,
                    "runtime_arn": runtime_arn,
                    "registered_at": datetime.now(tz=UTC).isoformat(),
                },
            )
        except Exception as e:
            # Another worker already claimed the row — perfectly fine.
            log.debug("heartbeat claim skipped (row exists)", extra={"error": str(e)})


__all__ = ["AgentCoreRegistrar", "AgentRuntimeNotReady"]
