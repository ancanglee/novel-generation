"""worker-moderation entrypoint — V2-reserved stub.

Behavior:
  - If env var `MODERATION_QUEUE_URL` is set AND `MODERATION_ENABLED=1`,
    long-poll SQS and log receive-only (no actual moderation yet).
  - Otherwise, idle-sleep in a signal-respecting loop so that Fargate
    can run a container (desired_count=0 in U1 keeps cost at zero;
    if scaled up manually, the container stays healthy-idle).

This file exists so `worker-moderation` has a real Python entrypoint
matching the Dockerfile CMD, even before V2 activates ModerationAgent.
"""

from __future__ import annotations

import asyncio
import logging
import os
import signal

log = logging.getLogger("worker_moderation")
_LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=getattr(logging, _LOG_LEVEL, logging.INFO))

_REGION = os.environ.get("AWS_REGION", "us-west-2")
_ENV = os.environ.get("NOVELGEN_ENV", "dev")
_QUEUE_URL = os.environ.get("MODERATION_QUEUE_URL")
_ENABLED = os.environ.get("MODERATION_ENABLED", "0") == "1"


class WorkerModeration:
    def __init__(self) -> None:
        self._stop = asyncio.Event()

    def request_stop(self) -> None:
        self._stop.set()

    async def _idle(self) -> None:
        log.info(
            "worker_moderation_idle env=%s region=%s reason=%s",
            _ENV,
            _REGION,
            "v2_reserved" if not _ENABLED else "missing_queue_url",
        )
        # Heartbeat every 60s; exit cleanly on SIGTERM/SIGINT.
        while not self._stop.is_set():
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=60.0)
            except asyncio.TimeoutError:
                log.debug("worker_moderation_heartbeat")

    async def _poll(self) -> None:
        # Lazy import so the idle path has zero boto overhead.
        import aioboto3

        session = aioboto3.Session()
        assert _QUEUE_URL is not None
        log.info(
            "worker_moderation_polling queue=%s region=%s env=%s",
            _QUEUE_URL,
            _REGION,
            _ENV,
        )
        async with session.client("sqs", region_name=_REGION) as sqs:
            while not self._stop.is_set():
                resp = await sqs.receive_message(
                    QueueUrl=_QUEUE_URL,
                    MaxNumberOfMessages=5,
                    WaitTimeSeconds=10,
                    VisibilityTimeout=30,
                )
                messages = resp.get("Messages", [])
                if not messages:
                    continue
                # V2 stub: log and delete without processing so the queue
                # never silently piles up if somebody wires the rule early.
                for msg in messages:
                    log.warning(
                        "moderation_stub_drop msg_id=%s body_len=%d",
                        msg.get("MessageId"),
                        len(msg.get("Body", "")),
                    )
                    await sqs.delete_message(
                        QueueUrl=_QUEUE_URL,
                        ReceiptHandle=msg["ReceiptHandle"],
                    )

    async def run(self) -> None:
        if _ENABLED and _QUEUE_URL:
            await self._poll()
        else:
            await self._idle()


async def _amain() -> None:
    try:
        from novelgen_obs import init_observability

        init_observability("worker-moderation", _ENV)
    except ImportError:
        pass
    worker = WorkerModeration()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, worker.request_stop)
    await worker.run()


def main() -> None:
    asyncio.run(_amain())


if __name__ == "__main__":
    main()
