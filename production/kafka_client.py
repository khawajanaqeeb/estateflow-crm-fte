"""
EstateFlow Customer Success FTE — Kafka Client
Async producer and consumer using aiokafka.

Topics:
  fte.tickets.incoming      — unified intake from all channels (consumed by worker)
  fte.channels.email.inbound
  fte.channels.whatsapp.inbound
  fte.channels.webform.inbound
  fte.channels.email.outbound
  fte.channels.whatsapp.outbound
  fte.escalations           — escalated tickets for human dashboard
  fte.metrics               — performance events
  fte.dlq                   — dead letter queue for failed processing
"""

import json
import logging
import os
from datetime import datetime, timezone
from typing import Awaitable, Callable

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from aiokafka.errors import KafkaConnectionError

logger = logging.getLogger(__name__)

KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")

# ── Topic registry ─────────────────────────────────────────────────────────────

TOPICS = {
    # Unified intake — all channels publish here; worker consumes
    "tickets_incoming":      "fte.tickets.incoming",

    # Channel-specific inbound (optional fine-grained routing)
    "email_inbound":         "fte.channels.email.inbound",
    "whatsapp_inbound":      "fte.channels.whatsapp.inbound",
    "webform_inbound":       "fte.channels.webform.inbound",

    # Channel-specific outbound (for delivery tracking)
    "email_outbound":        "fte.channels.email.outbound",
    "whatsapp_outbound":     "fte.channels.whatsapp.outbound",

    # Downstream consumers
    "escalations":           "fte.escalations",
    "metrics":               "fte.metrics",
    "dlq":                   "fte.dlq",
}


# ── Producer ──────────────────────────────────────────────────────────────────

class FTEKafkaProducer:
    """Async Kafka producer. Call start() before use, stop() on shutdown."""

    def __init__(self) -> None:
        self._producer: AIOKafkaProducer | None = None

    async def start(self) -> None:
        self._producer = AIOKafkaProducer(
            bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
            value_serializer=lambda v: json.dumps(v, default=str).encode("utf-8"),
            # Reliable delivery: wait for all in-sync replicas
            acks="all",
            # Retry transient errors up to 5 times
            retries=5,
        )
        await self._producer.start()
        logger.info("Kafka producer started — brokers: %s", KAFKA_BOOTSTRAP_SERVERS)

    async def stop(self) -> None:
        if self._producer:
            await self._producer.stop()
            logger.info("Kafka producer stopped")

    async def publish(self, topic: str, event: dict) -> None:
        """
        Publish an event to a topic. Automatically stamps event with UTC timestamp.
        Raises RuntimeError if producer has not been started.
        """
        if not self._producer:
            raise RuntimeError("Producer not started — call await producer.start() first")

        event["timestamp"] = datetime.now(timezone.utc).isoformat()
        await self._producer.send_and_wait(topic, event)
        logger.debug("Published to %s: %s", topic, event.get("event_type", "-"))

    async def publish_to_dlq(self, original_topic: str, original_message: dict,
                              error: Exception, retry_count: int = 0) -> None:
        """Send a failed message to the dead letter queue."""
        await self.publish(TOPICS["dlq"], {
            "original_topic":   original_topic,
            "original_message": original_message,
            "error_type":       type(error).__name__,
            "error_message":    str(error),
            "retry_count":      retry_count,
            "failed_at":        datetime.now(timezone.utc).isoformat(),
        })
        logger.warning("Message sent to DLQ: %s — %s", type(error).__name__, error)


# ── Consumer ──────────────────────────────────────────────────────────────────

class FTEKafkaConsumer:
    """
    Async Kafka consumer.
    Usage:
        consumer = FTEKafkaConsumer(topics=[TOPICS["tickets_incoming"]], group_id="fte-worker")
        await consumer.start()
        await consumer.consume(handler)   # handler: async (topic, message) -> None
    """

    def __init__(self, topics: list[str], group_id: str) -> None:
        self._topics = topics
        self._group_id = group_id
        self._consumer: AIOKafkaConsumer | None = None

    async def start(self) -> None:
        self._consumer = AIOKafkaConsumer(
            *self._topics,
            bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
            group_id=self._group_id,
            value_deserializer=lambda v: json.loads(v.decode("utf-8")),
            # Start from earliest unread message on first run
            auto_offset_reset="earliest",
            # Disable auto-commit so we only commit after successful processing
            enable_auto_commit=False,
        )
        await self._consumer.start()
        logger.info(
            "Kafka consumer started — group: %s, topics: %s",
            self._group_id, self._topics,
        )

    async def stop(self) -> None:
        if self._consumer:
            await self._consumer.stop()
            logger.info("Kafka consumer stopped")

    async def consume(
        self,
        handler: Callable[[str, dict], Awaitable[None]],
    ) -> None:
        """
        Poll for messages and call handler(topic, message) for each one.
        Commits offset only after the handler completes successfully.
        On handler failure the offset is NOT committed — message will be redelivered.
        """
        if not self._consumer:
            raise RuntimeError("Consumer not started — call await consumer.start() first")

        async for msg in self._consumer:
            try:
                await handler(msg.topic, msg.value)
                await self._consumer.commit()
            except Exception as e:
                logger.error(
                    "Handler failed for topic=%s partition=%s offset=%s: %s",
                    msg.topic, msg.partition, msg.offset, e,
                )
                # Do NOT commit — message will be redelivered on next poll
