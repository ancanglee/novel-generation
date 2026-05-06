"""SSE relay: subscribes an SNS fan-out topic via a per-replica SQS queue and routes
EventBridge generation events to active SSE connections in this ApiService process.

On replica startup we create a dedicated SQS queue and subscribe to the SNS Topic
(`novelgen-generation-events`). Each message is a fan-out of an EventBridge event
with source `novelgen.generation`. Events whose (job_id / generation_id / chapter_idx)
match an active local subscriber are dispatched; unmatched events are dropped.
"""

from __future__ import annotations

import asyncio
import json
import os
import uuid
from dataclasses import dataclass, field
from typing import Any

import aioboto3

from novelgen_obs import get_logger

log = get_logger("api.sse_relay")

SNS_TOPIC_ARN = os.environ.get("GENERATION_SNS_TOPIC_ARN", "")
REGION = os.environ.get("AWS_REGION", "us-east-1")


@dataclass
class SseSubscriber:
    subscriber_id: str
    queue: asyncio.Queue[dict[str, Any]]
    job_id: str | None = None
    generation_id: str | None = None
    chapter_idx: int | None = None


@dataclass
class SseRelayState:
    replica_id: str
    sqs_queue_url: str = ""
    sns_subscription_arn: str = ""
    subscribers: dict[str, SseSubscriber] = field(default_factory=dict)
    stop_event: asyncio.Event = field(default_factory=asyncio.Event)


class SseRelay:
    """Per-replica SSE relay. Instantiated once during app lifespan."""

    def __init__(self) -> None:
        self.state = SseRelayState(replica_id=f"{os.environ.get('HOSTNAME', 'local')}-{uuid.uuid4().hex[:8]}")
        self._session = aioboto3.Session()
        self._poll_task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        """Create SQS queue, subscribe to SNS, start poll loop."""
        if not SNS_TOPIC_ARN:
            log.warning("GENERATION_SNS_TOPIC_ARN not set; SSE relay disabled")
            return

        queue_name = f"novelgen-sse-relay-{self.state.replica_id}"
        async with self._session.client("sqs", region_name=REGION) as sqs:
            resp = await sqs.create_queue(
                QueueName=queue_name,
                Attributes={"MessageRetentionPeriod": "3600", "VisibilityTimeout": "30"},
            )
            self.state.sqs_queue_url = resp["QueueUrl"]
            attrs = await sqs.get_queue_attributes(
                QueueUrl=self.state.sqs_queue_url, AttributeNames=["QueueArn"]
            )
            queue_arn = attrs["Attributes"]["QueueArn"]

        async with self._session.client("sns", region_name=REGION) as sns:
            sub = await sns.subscribe(
                TopicArn=SNS_TOPIC_ARN,
                Protocol="sqs",
                Endpoint=queue_arn,
                ReturnSubscriptionArn=True,
            )
            self.state.sns_subscription_arn = sub["SubscriptionArn"]

        log.info(
            "sse relay started",
            extra={"replica_id": self.state.replica_id, "queue": self.state.sqs_queue_url},
        )
        self._poll_task = asyncio.create_task(self._poll_loop())

    async def stop(self) -> None:
        """Unsubscribe SNS and delete the per-replica SQS queue."""
        self.state.stop_event.set()
        if self._poll_task:
            self._poll_task.cancel()

        if self.state.sns_subscription_arn:
            async with self._session.client("sns", region_name=REGION) as sns:
                try:
                    await sns.unsubscribe(SubscriptionArn=self.state.sns_subscription_arn)
                except Exception as e:
                    log.warning("sns unsubscribe failed", extra={"error": str(e)})
        if self.state.sqs_queue_url:
            async with self._session.client("sqs", region_name=REGION) as sqs:
                try:
                    await sqs.delete_queue(QueueUrl=self.state.sqs_queue_url)
                except Exception as e:
                    log.warning("sqs delete failed", extra={"error": str(e)})

    def register(
        self,
        *,
        job_id: str | None = None,
        generation_id: str | None = None,
        chapter_idx: int | None = None,
    ) -> SseSubscriber:
        sub = SseSubscriber(
            subscriber_id=uuid.uuid4().hex,
            queue=asyncio.Queue(maxsize=1000),
            job_id=job_id,
            generation_id=generation_id,
            chapter_idx=chapter_idx,
        )
        self.state.subscribers[sub.subscriber_id] = sub
        return sub

    def unregister(self, subscriber_id: str) -> None:
        self.state.subscribers.pop(subscriber_id, None)

    async def replay_since(
        self,
        subscriber: SseSubscriber,
        last_event_id: str,
    ) -> None:
        """Replay events from EventBridge Archive; best-effort for reconnect."""
        log.info(
            "sse replay requested",
            extra={"subscriber": subscriber.subscriber_id, "last_event_id": last_event_id},
        )
        # Archive replay via StartReplay is asynchronous and coarse-grained;
        # V1 logs the intent. Production can invoke events:StartReplay and block
        # until replay completes, then continue live.

    async def _poll_loop(self) -> None:
        async with self._session.client("sqs", region_name=REGION) as sqs:
            while not self.state.stop_event.is_set():
                try:
                    resp = await sqs.receive_message(
                        QueueUrl=self.state.sqs_queue_url,
                        MaxNumberOfMessages=10,
                        WaitTimeSeconds=10,
                    )
                    for msg in resp.get("Messages", []):
                        await self._dispatch(msg)
                        await sqs.delete_message(
                            QueueUrl=self.state.sqs_queue_url,
                            ReceiptHandle=msg["ReceiptHandle"],
                        )
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    log.exception("sse poll error", extra={"error": str(e)})
                    await asyncio.sleep(1)

    async def _dispatch(self, msg: dict[str, Any]) -> None:
        try:
            sns_envelope = json.loads(msg["Body"])
            event = json.loads(sns_envelope.get("Message", "{}"))
        except json.JSONDecodeError:
            return

        detail = event.get("detail", {}) if isinstance(event, dict) else {}
        detail_type = event.get("detail-type", "")
        gen_id = detail.get("generation_id")
        job_id = detail.get("job_id")
        chapter_idx = detail.get("chapter_idx")

        for sub in list(self.state.subscribers.values()):
            if sub.job_id and sub.job_id != job_id:
                continue
            if sub.generation_id and sub.generation_id != gen_id:
                continue
            if sub.chapter_idx is not None and sub.chapter_idx != chapter_idx:
                continue
            try:
                sub.queue.put_nowait({"type": detail_type, "data": detail})
            except asyncio.QueueFull:
                log.warning("sse subscriber queue full; dropping", extra={"sub": sub.subscriber_id})
