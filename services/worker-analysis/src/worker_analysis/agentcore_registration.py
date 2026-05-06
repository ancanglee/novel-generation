"""Worker-level AgentCore Runtime self-registration (I2=C).

Race-safe via DynamoDB conditional put (`AGENT_REG#{agent_id}`). If another Worker
has already registered, we skip without contention.
"""

from __future__ import annotations

from datetime import UTC, datetime

from novelgen_obs import get_logger
from novelgen_storage import DynamoDBAdapter

log = get_logger("worker-analysis.registration")


class AgentCoreRegistrar:
    def __init__(self, jobs_table: DynamoDBAdapter, agent_id: str, env: str) -> None:
        self._ddb = jobs_table
        self._agent_id = agent_id
        self._env = env

    async def register_if_needed(self) -> bool:
        """Returns True if we registered, False if already registered by another Worker."""
        acquired = await self._try_claim_registration()
        if not acquired:
            log.info("AgentCore already registered by another Worker; skipping")
            return False

        try:
            await self._call_agentcore_register()
            log.info("AgentCore registration completed", extra={"agent_id": self._agent_id})
            return True
        except NotImplementedError:
            log.warning("AgentCore Runtime SDK not wired; skipping registration call")
            return False

    async def _try_claim_registration(self) -> bool:
        """Conditional write: only the first caller succeeds."""

        # Registration counter is platform-scope (not team-scope); use a pseudo-team PK.
        try:
            inserted = await self._ddb.put_if_absent(
                team_id=None,  # type: ignore[arg-type]
                item={
                    "pk": f"AGENT_REG#{self._env}",
                    "sk": f"AGENT#{self._agent_id}",
                    "agent_id": self._agent_id,
                    "registered_at": datetime.now(tz=UTC).isoformat(),
                },
            )
            return bool(inserted)
        except Exception as e:
            log.warning("registration claim failed; assuming already registered", extra={"error": str(e)})
            return False

    async def _call_agentcore_register(self) -> None:
        """Actual AgentCore Control API call. SDK binding pending."""
        raise NotImplementedError(
            "AgentCore Runtime register_agent SDK call pending; fill when SDK stabilizes"
        )
