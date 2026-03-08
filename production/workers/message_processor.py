"""
EstateFlow Customer Success FTE — Unified Message Processor
Kafka consumer that reads from fte.tickets.incoming and runs the agent
for every inbound message regardless of channel.

Run with:
  python -m production.workers.message_processor

Or via Docker:
  command: ["python", "production/workers/message_processor.py"]
"""

import asyncio
import logging
import os
from datetime import datetime, timezone

from production.kafka_client import FTEKafkaConsumer, FTEKafkaProducer, TOPICS
from production.agent.customer_success_agent import run_agent
from production.channels.gmail_handler import GmailHandler
from production.channels.whatsapp_handler import WhatsAppHandler

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)


class UnifiedMessageProcessor:
    """
    Kafka consumer that processes incoming support messages from all channels.

    Workflow per message:
      1. Resolve or create customer record
      2. Get or create conversation (reuse if active within 24h)
      3. Store inbound message in DB
      4. Build conversation history for agent
      5. Run agent with context dict
      6. Store outbound message + tool calls
      7. Publish metrics event to Kafka
      8. On error: send apology via channel + publish to DLQ
    """

    def __init__(self) -> None:
        self.gmail     = GmailHandler()
        self.whatsapp  = WhatsAppHandler()
        self.producer  = FTEKafkaProducer()

    async def start(self) -> None:
        """Start the producer and consumer. Blocks indefinitely."""
        await self.producer.start()

        consumer = FTEKafkaConsumer(
            topics=[TOPICS["tickets_incoming"]],
            group_id="fte-message-processor",
        )
        await consumer.start()

        logger.info("Message processor ready — listening on %s", TOPICS["tickets_incoming"])

        try:
            await consumer.consume(self.process_message)
        finally:
            await consumer.stop()
            await self.producer.stop()
            from production.database.queries import close_db_pool
            await close_db_pool()

    # ── Core processing ───────────────────────────────────────────────────────

    async def process_message(self, topic: str, message: dict) -> None:
        """Process one inbound message end-to-end."""
        start_time = datetime.now(timezone.utc)
        channel    = message.get("channel", "web_form")

        try:
            # 1. Resolve customer
            customer_id = await self._resolve_customer(message)

            # 2. Get or create conversation
            conversation_id = await self._get_or_create_conversation(
                customer_id=customer_id,
                channel=channel,
            )

            # 3. Store inbound message
            from production.database.queries import store_message
            await store_message(
                conversation_id=conversation_id,
                channel=channel,
                direction="inbound",
                role="customer",
                content=message.get("content", ""),
                channel_message_id=message.get("channel_message_id"),
            )

            # 4. Build conversation history for the agent
            history = await self._build_agent_history(conversation_id)

            # 5. Build context dict
            customer_plan = await self._get_customer_plan(customer_id)
            context = {
                "customer_id":     customer_id,
                "conversation_id": conversation_id,
                "channel":         channel,
                "plan":            customer_plan,
                "ticket_subject":  message.get("subject", "Support Request"),
            }

            # 6. Run the agent
            result = await run_agent(messages=history, context=context)

            # 7. Store agent response
            latency_ms = int(
                (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
            )
            tool_calls = [
                {"tool": tc.tool_name, "input": str(tc.input)[:200]}
                for tc in (result.tool_calls or [])
            ] if hasattr(result, "tool_calls") else []

            await store_message(
                conversation_id=conversation_id,
                channel=channel,
                direction="outbound",
                role="agent",
                content=result.final_output or "",
                latency_ms=latency_ms,
                tool_calls=tool_calls,
                delivery_status="sent",
            )

            # 8. Publish metrics
            await self.producer.publish(TOPICS["metrics"], {
                "event_type":       "message_processed",
                "channel":          channel,
                "conversation_id":  conversation_id,
                "latency_ms":       latency_ms,
                "tool_calls_count": len(tool_calls),
                "escalated":        any(
                    "escalate" in tc.get("tool", "") for tc in tool_calls
                ),
            })

            logger.info(
                "Processed %s message in %dms (conv=%s)",
                channel, latency_ms, conversation_id,
            )

        except Exception as e:
            logger.error("Error processing message from %s: %s", channel, e, exc_info=True)
            await self._handle_error(message, e)

    # ── Customer resolution ───────────────────────────────────────────────────

    async def _resolve_customer(self, message: dict) -> str:
        """
        Look up existing customer by email or phone.
        Creates a new customer record if not found.
        Returns customer_id (UUID string).
        """
        from production.database.queries import (
            find_customer_by_email,
            find_customer_by_phone,
            create_customer,
            add_customer_identifier,
        )

        email = message.get("customer_email")
        phone = message.get("customer_phone")
        name  = message.get("customer_name", "")

        # Try email first
        if email:
            customer = await find_customer_by_email(email)
            if customer:
                return str(customer["id"])

            # New customer — create and link identifier
            customer_id = await create_customer(email=email, name=name)
            await add_customer_identifier(customer_id, "email", email)

            # Also link phone if provided
            if phone:
                await add_customer_identifier(customer_id, "whatsapp", phone)

            return customer_id

        # Try phone (WhatsApp customers without email)
        if phone:
            customer = await find_customer_by_phone(phone)
            if customer:
                return str(customer["id"])

            customer_id = await create_customer(phone=phone, name=name)
            await add_customer_identifier(customer_id, "whatsapp", phone)
            return customer_id

        raise ValueError(f"Message has no customer_email or customer_phone: {message}")

    # ── Conversation management ───────────────────────────────────────────────

    async def _get_or_create_conversation(
        self, customer_id: str, channel: str
    ) -> str:
        """
        Reuse an active conversation started within the last 24 hours,
        or create a new one. Returns conversation_id.
        """
        from production.database.queries import get_active_conversation, create_conversation

        conv = await get_active_conversation(customer_id)
        if conv:
            return str(conv["id"])
        return await create_conversation(customer_id, channel)

    # ── History builder ───────────────────────────────────────────────────────

    async def _build_agent_history(self, conversation_id: str) -> list[dict]:
        """
        Load conversation history from DB and convert to OpenAI message format.
        Maps customer → user, agent/system → assistant.
        Keeps last 20 turns to stay within context limits.
        """
        from production.database.queries import load_conversation_history

        rows = await load_conversation_history(conversation_id)
        rows = rows[-20:]  # last 20 turns

        history = []
        for row in rows:
            role = "user" if row["role"] == "customer" else "assistant"
            history.append({"role": role, "content": row["content"]})

        return history

    # ── Customer plan lookup ──────────────────────────────────────────────────

    async def _get_customer_plan(self, customer_id: str) -> str:
        """Return the customer's plan (defaults to 'starter' on error)."""
        try:
            from production.database.queries import get_db_pool
            pool = await get_db_pool()
            async with pool.acquire() as conn:
                plan = await conn.fetchval(
                    "SELECT plan FROM customers WHERE id = $1", customer_id
                )
                return plan or "starter"
        except Exception:
            return "starter"

    # ── Error handling ────────────────────────────────────────────────────────

    async def _handle_error(self, message: dict, error: Exception) -> None:
        """
        Send an apology to the customer via their original channel.
        Publish the failed message to the DLQ for manual review.
        """
        channel = message.get("channel", "web_form")
        apology = (
            "I'm sorry, I'm having trouble processing your request right now. "
            "A member of our team will follow up with you shortly."
        )

        try:
            if channel == "email" and message.get("customer_email"):
                await self.gmail.send_reply(
                    to_email=message["customer_email"],
                    subject=message.get("subject", "Support Request"),
                    body=apology,
                    thread_id=message.get("thread_id"),
                )
            elif channel == "whatsapp" and message.get("customer_phone"):
                await self.whatsapp.send_message(
                    to_phone=message["customer_phone"],
                    body=apology,
                )
            # web_form: no immediate reply possible — DLQ handles follow-up

        except Exception as send_err:
            logger.error("Failed to send error apology: %s", send_err)

        # Publish to DLQ
        await self.producer.publish_to_dlq(
            original_topic=TOPICS["tickets_incoming"],
            original_message=message,
            error=error,
        )


# ── Entry point ───────────────────────────────────────────────────────────────

async def main() -> None:
    processor = UnifiedMessageProcessor()
    await processor.start()


if __name__ == "__main__":
    asyncio.run(main())
