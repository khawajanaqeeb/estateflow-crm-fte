"""
EstateFlow Customer Success FTE — Production Tools
OpenAI Agents SDK @function_tool definitions wired to PostgreSQL via queries.py.

Phase 2 upgrade from prototype stubs:
  search_knowledge_base  → asyncpg + pgvector cosine similarity
  create_ticket          → INSERT INTO tickets + conversations
  get_customer_history   → SELECT from customers + messages (cross-channel)
  get_session_context    → SELECT last 10 turns for active conversation
  escalate_to_human      → UPDATE ticket + publish to fte.escalations Kafka topic
  send_response          → formatter + Gmail API / Twilio / DB store
  update_ticket_status   → UPDATE tickets SET status
  detect_upsell_signal   → in-memory rule engine (no DB needed)
  analyze_sentiment      → in-memory classifier (no DB needed)
"""

import json
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from agents import function_tool
from pydantic import BaseModel

logger = logging.getLogger(__name__)


# ── Input schemas ─────────────────────────────────────────────────────────────

class KnowledgeSearchInput(BaseModel):
    query: str
    max_results: int = 5
    category: Optional[str] = None


class CreateTicketInput(BaseModel):
    customer_id: str
    issue: str
    priority: str = "medium"   # low | medium | high | urgent
    channel: str               # email | whatsapp | web_form
    category: Optional[str] = None


class CustomerHistoryInput(BaseModel):
    email: Optional[str] = None
    phone: Optional[str] = None


class SessionContextInput(BaseModel):
    customer_id: str
    conversation_id: Optional[str] = None


class EscalateInput(BaseModel):
    ticket_id: str
    reason: str
    level: str              # L1 | L2 | L3 | L4
    context_summary: str
    rule_triggered: Optional[str] = None


class SendResponseInput(BaseModel):
    ticket_id: str
    message: str
    channel: str            # email | whatsapp | web_form
    customer_name: Optional[str] = None
    customer_email: Optional[str] = None
    customer_phone: Optional[str] = None
    thread_id: Optional[str] = None


class UpdateTicketInput(BaseModel):
    ticket_id: str
    status: str             # resolved | pending | open | closed
    resolution_notes: Optional[str] = None


class UpsellSignalInput(BaseModel):
    message: str
    current_plan: str       # starter | professional | team | brokerage


class SentimentInput(BaseModel):
    message: str


# ── Internal helpers ──────────────────────────────────────────────────────────

async def _generate_embedding(text: str) -> Optional[list[float]]:
    """Generate an embedding vector using OpenAI text-embedding-3-small."""
    try:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        resp = await client.embeddings.create(
            model="text-embedding-3-small",
            input=text,
        )
        return resp.data[0].embedding
    except Exception as e:
        logger.warning("Embedding generation failed — falling back to keyword search: %s", e)
        return None


def _format_search_results(results: list[dict]) -> str:
    if not results:
        return (
            "No relevant documentation found for this query. "
            "Consider escalating to human support if the customer needs an answer."
        )
    parts = []
    for r in results:
        score = float(r.get("similarity", 0))
        parts.append(f"**{r['title']}** (relevance: {score:.2f})\n{r['content'][:600]}")
    return "\n\n---\n\n".join(parts)


def _format_customer_history(rows: list[dict]) -> str:
    if not rows:
        return json.dumps({
            "status": "new_customer",
            "message": "No prior interactions found.",
            "prior_messages": [],
        })
    formatted = [
        {
            "channel":    r["channel"],
            "role":       r["role"],
            "content":    r["content"][:300],
            "created_at": str(r["created_at"]),
        }
        for r in rows
    ]
    return json.dumps({
        "status":         "returning_customer",
        "prior_messages": formatted,
        "message_count":  len(rows),
    })


_SLA_MAP = {
    "L1": "Next business day",
    "L2": "Within 4 business hours",
    "L3": "Within 1 hour",
    "L4": "Immediate (24/7 on-call)",
}

_SLA_OFFSETS = {
    "L1": timedelta(days=1),
    "L2": timedelta(hours=4),
    "L3": timedelta(hours=1),
    "L4": timedelta(minutes=15),
}

_ESCALATION_ROUTES = [
    (("billing", "refund", "charge", "invoice"),          "billing@estateflow.io"),
    (("security", "unauthorized", "hacked", "breach"),    "security@estateflow.io"),
    (("legal", "compliance", "gdpr", "ccpa", "privacy"),  "privacy@estateflow.io"),
    (("pricing", "discount", "negotiate", "contract"),    "sales@estateflow.io"),
]


def _route_escalation(reason: str) -> str:
    r = reason.lower()
    for keywords, dest in _ESCALATION_ROUTES:
        if any(k in r for k in keywords):
            return dest
    return "team@estateflow.io"


def _proto_path() -> str:
    return os.path.dirname(os.path.dirname(os.path.dirname(__file__)))


# ── Tool implementations (_impl suffix — called directly by tests) ─────────────

async def _search_knowledge_base_impl(input: KnowledgeSearchInput) -> str:
    try:
        from production.database.queries import search_knowledge_base_db

        embedding = await _generate_embedding(input.query)
        results   = await search_knowledge_base_db(
            embedding=embedding,
            max_results=input.max_results,
            category=input.category,
        )

        return _format_search_results(results)

    except Exception as e:
        logger.error("search_knowledge_base failed: %s", e)
        return "Knowledge base temporarily unavailable. Please escalate if the customer needs an immediate answer."


async def _create_ticket_impl(input: CreateTicketInput) -> str:
    try:
        from production.database.queries import (
            get_active_conversation,
            create_conversation,
            create_ticket_record,
        )

        conv = await get_active_conversation(input.customer_id)
        conversation_id = str(conv["id"]) if conv else await create_conversation(
            input.customer_id, input.channel
        )

        ticket_id = await create_ticket_record(
            conversation_id=conversation_id,
            customer_id=input.customer_id,
            source_channel=input.channel,
            category=input.category,
            priority=input.priority,
        )

        logger.info("Ticket created: %s (customer=%s channel=%s)", ticket_id, input.customer_id, input.channel)
        return json.dumps({
            "ticket_id":       ticket_id,
            "conversation_id": conversation_id,
            "customer_id":     input.customer_id,
            "channel":         input.channel,
            "priority":        input.priority,
            "status":          "open",
            "created_at":      datetime.now(timezone.utc).isoformat(),
        })

    except Exception as e:
        logger.error("create_ticket failed: %s", e)
        return json.dumps({"error": "Ticket creation failed. Proceeding without ticket ID — log manually."})


async def _get_customer_history_impl(input: CustomerHistoryInput) -> str:
    try:
        from production.database.queries import (
            find_customer_by_email,
            find_customer_by_phone,
            get_customer_full_history,
        )

        if not input.email and not input.phone:
            return json.dumps({"error": "Provide at least one of email or phone."})

        customer = None
        if input.email:
            customer = await find_customer_by_email(input.email)
        if not customer and input.phone:
            customer = await find_customer_by_phone(input.phone)

        if not customer:
            return json.dumps({
                "status":         "new_customer",
                "message":        "No prior interactions found. This is a new customer.",
                "prior_messages": [],
            })

        history = await get_customer_full_history(str(customer["id"]))
        return _format_customer_history(history)

    except Exception as e:
        logger.error("get_customer_history failed: %s", e)
        return json.dumps({"error": "Could not retrieve history. Proceed as new customer."})


async def _get_session_context_impl(input: SessionContextInput) -> str:
    try:
        from production.database.queries import (
            get_active_conversation,
            load_conversation_history,
        )

        conv = await get_active_conversation(input.customer_id)
        if not conv:
            return json.dumps({
                "customer_id":    input.customer_id,
                "active_session": None,
                "message":        "No active session. This is the start of a new conversation.",
                "history":        [],
            })

        history = await load_conversation_history(str(conv["id"]))
        return json.dumps({
            "customer_id":     input.customer_id,
            "conversation_id": str(conv["id"]),
            "channel":         conv["initial_channel"],
            "started_at":      str(conv["started_at"]),
            "message_count":   len(history),
            "history": [
                {"role": m["role"], "content": m["content"][:300], "channel": m["channel"]}
                for m in history[-10:]
            ],
        })

    except Exception as e:
        logger.error("get_session_context failed: %s", e)
        return json.dumps({"error": "Could not retrieve session. Proceed as new conversation."})


async def _escalate_to_human_impl(input: EscalateInput) -> str:
    try:
        from production.database.queries import update_ticket_record
        from production.kafka_client import FTEKafkaProducer, TOPICS

        routed_to    = _route_escalation(input.reason)
        sla          = _SLA_MAP.get(input.level, "Next business day")
        sla_deadline = (
            datetime.now(timezone.utc) + _SLA_OFFSETS.get(input.level, timedelta(days=1))
        ).isoformat()

        await update_ticket_record(
            ticket_id=input.ticket_id,
            status="escalated",
            escalation_level=input.level,
            escalation_reason=input.reason,
        )

        event = {
            "event_type":      "escalation",
            "ticket_id":       input.ticket_id,
            "escalation_id":   f"ESC-{input.ticket_id[:8]}",
            "level":           input.level,
            "reason":          input.reason,
            "rule_triggered":  input.rule_triggered or "Manual escalation",
            "routed_to":       routed_to,
            "sla":             sla,
            "sla_deadline":    sla_deadline,
            "context_summary": input.context_summary,
        }

        producer = FTEKafkaProducer()
        await producer.start()
        await producer.publish(TOPICS["escalations"], event)
        await producer.stop()

        logger.warning("Escalation: ticket=%s level=%s → %s", input.ticket_id, input.level, routed_to)
        return json.dumps({**event, "status": "escalated"})

    except Exception as e:
        logger.error("escalate_to_human failed: %s", e)
        return json.dumps({"error": "Escalation system unavailable. Contact team@estateflow.io directly."})


def _format_for_channel(message: str, channel: str, customer_name: str = "") -> str:
    """Inline channel formatter — avoids importing prototype src package."""
    import re
    first_name = customer_name.split()[0] if customer_name else ""

    if channel == "whatsapp":
        text = re.sub(r'\*\*(.*?)\*\*', r'\1', message)
        text = re.sub(r'\*(.*?)\*', r'\1', text)
        text = re.sub(r'#{1,6}\s*', '', text)
        text = re.sub(r'`(.*?)`', r'\1', text)
        words = text.split()
        if len(words) > 80:
            text = " ".join(words[:80])
            last = max(text.rfind('.'), text.rfind('!'), text.rfind('?'))
            if last > len(text) // 2:
                text = text[:last + 1]
        if len(text) > 300:
            text = text[:300].rsplit(' ', 1)[0] + "..."
        return text.strip()

    lines = message.strip().splitlines()
    has_greeting = lines and re.match(r'^(hi|hello|dear)\b', lines[0], re.IGNORECASE)
    parts = []
    if not has_greeting:
        parts.append(f"Hi {first_name}," if first_name else "Hi there,")
        parts.append("")
    parts.append(message.strip())

    if channel == "email":
        has_signoff = len(lines) > 1 and re.match(
            r'^(best|regards|thanks|sincerely|warm)', lines[-1], re.IGNORECASE
        )
        if not has_signoff:
            parts += ["", "Let me know if you have any other questions.", "",
                      "Best,", "EstateFlow Customer Success", "support@estateflow.io"]
    else:  # web_form
        if not any(re.match(r'^(let me know|feel free|reach out|hope that)', l, re.IGNORECASE)
                   for l in lines[-3:]):
            parts += ["", "Let me know if you need anything else."]

    return "\n".join(parts)


async def _send_response_impl(input: SendResponseInput) -> str:
    try:
        formatted = _format_for_channel(
            message=input.message,
            channel=input.channel,
            customer_name=input.customer_name or "",
        )

        delivery_status = "pending"

        if input.channel == "email" and input.customer_email:
            from production.channels.gmail_handler import GmailHandler
            result          = await GmailHandler().send_reply(
                to_email=input.customer_email,
                subject="Re: Your EstateFlow Support Request",
                body=formatted,
                thread_id=input.thread_id,
            )
            delivery_status = result.get("delivery_status", "sent")

        elif input.channel == "whatsapp" and input.customer_phone:
            from production.channels.whatsapp_handler import WhatsAppHandler
            result          = await WhatsAppHandler().send_message(
                to_phone=input.customer_phone,
                body=formatted,
            )
            delivery_status = result.get("delivery_status", "queued")

        else:
            delivery_status = "stored"   # web_form — customer polls /support/ticket/{id}

        logger.info("Response sent: ticket=%s channel=%s status=%s", input.ticket_id, input.channel, delivery_status)
        return json.dumps({
            "ticket_id":         input.ticket_id,
            "channel":           input.channel,
            "delivery_status":   delivery_status,
            "formatted_message": formatted,
        })

    except Exception as e:
        logger.error("send_response failed: %s", e)
        return json.dumps({"error": "Response delivery failed. Log the message manually and retry."})


async def _update_ticket_status_impl(input: UpdateTicketInput) -> str:
    try:
        from production.database.queries import update_ticket_record

        await update_ticket_record(
            ticket_id=input.ticket_id,
            status=input.status,
            resolution_notes=input.resolution_notes,
        )
        return json.dumps({
            "ticket_id":        input.ticket_id,
            "status":           input.status,
            "resolution_notes": input.resolution_notes or "",
            "updated_at":       datetime.now(timezone.utc).isoformat(),
        })

    except Exception as e:
        logger.error("update_ticket_status failed: %s", e)
        return json.dumps({"error": "Could not update ticket status."})


async def _detect_upsell_signal_impl(input: UpsellSignalInput) -> str:
    try:
        import sys
        sys.path.insert(0, _proto_path())
        from src.agent.escalation import detect_upsell_signal

        is_upsell, target_plan = detect_upsell_signal(input.message, input.current_plan)
        plan_prices = {
            "starter":      "$39/mo",
            "professional": "$79/mo",
            "team":         "$149/mo",
            "brokerage":    "Custom pricing",
        }
        return json.dumps({
            "upsell_signal_detected": is_upsell,
            "current_plan":      input.current_plan,
            "target_plan":       target_plan,
            "target_plan_price": plan_prices.get(target_plan) if target_plan else None,
            "guidance": (
                f"Answer the question fully first. Then add: "
                f"'This feature is available on our {target_plan.title()} plan "
                f"({plan_prices.get(target_plan)}). Upgrade anytime from Settings → Billing.'"
            ) if is_upsell else "No upsell action needed.",
        })

    except Exception as e:
        logger.error("detect_upsell_signal failed: %s", e)
        return json.dumps({"upsell_signal_detected": False, "error": "Detection unavailable."})


async def _analyze_sentiment_impl(input: SentimentInput) -> str:
    try:
        import sys
        sys.path.insert(0, _proto_path())
        from src.agent.agent import _quick_sentiment
        from src.agent.models import Sentiment

        sentiment = _quick_sentiment(input.message)
        negative  = {Sentiment.FRUSTRATED, Sentiment.NEGATIVE, Sentiment.ANGRY}

        tone_map = {
            Sentiment.POSITIVE.value:   "Customer is positive. Answer directly and warmly.",
            Sentiment.NEUTRAL.value:    "Customer is neutral. Be clear and professional.",
            Sentiment.NEGATIVE.value:   "Customer is dissatisfied. Acknowledge once, then solve.",
            Sentiment.FRUSTRATED.value: "Customer is frustrated. One empathy sentence, then solve fast.",
            Sentiment.ANGRY.value:      "Customer is angry. Acknowledge, do not defend, escalate if needed.",
        }

        return json.dumps({
            "sentiment":          sentiment.value,
            "is_negative":        sentiment in negative,
            "escalation_advised": sentiment == Sentiment.ANGRY,
            "tone_guidance":      tone_map.get(sentiment.value, "Respond professionally."),
        })

    except Exception as e:
        logger.error("analyze_sentiment failed: %s", e)
        return json.dumps({"sentiment": "neutral", "error": "Sentiment analysis unavailable."})


# ── @function_tool wrappers ───────────────────────────────────────────────────

@function_tool
async def search_knowledge_base(input: KnowledgeSearchInput) -> str:
    """Search EstateFlow product documentation for relevant information.

    Use this when the customer asks questions about product features,
    how to use something, reports an issue, or needs technical guidance.
    """
    return await _search_knowledge_base_impl(input)


@function_tool
async def create_ticket(input: CreateTicketInput) -> str:
    """Create a support ticket. ALWAYS call this first before any response.

    Every customer interaction must be logged. The returned ticket_id must
    be used in all subsequent tool calls for this conversation.
    """
    return await _create_ticket_impl(input)


@function_tool
async def get_customer_history(input: CustomerHistoryInput) -> str:
    """Retrieve a customer's full interaction history across ALL channels.

    Use this at the start of every conversation to check for prior context.
    Pass email (preferred) or phone to identify the customer.
    """
    return await _get_customer_history_impl(input)


@function_tool
async def get_session_context(input: SessionContextInput) -> str:
    """Retrieve the active conversation session for a customer.

    Use this for follow-up messages so the customer doesn't repeat themselves.
    Returns the last 10 message turns.
    """
    return await _get_session_context_impl(input)


@function_tool
async def escalate_to_human(input: EscalateInput) -> str:
    """Escalate a ticket to a human agent with full context.

    Use when: customer requests human, billing dispute, data loss, security
    incident, persistent negative sentiment, unresolved bug after 2 attempts,
    brokerage customer with complex issue, or legal question.
    Always include the full context_summary.
    """
    return await _escalate_to_human_impl(input)


@function_tool
async def send_response(input: SendResponseInput) -> str:
    """Send a formatted response to the customer via their channel.

    ALWAYS call this as the final step. Never reply without this tool.
    Auto-formats for channel: email gets greeting + signature,
    WhatsApp gets plain text under 300 chars.
    """
    return await _send_response_impl(input)


@function_tool
async def update_ticket_status(input: UpdateTicketInput) -> str:
    """Update the status of a support ticket.

    Mark as 'resolved' when the issue is fully addressed.
    Mark as 'pending' when waiting for customer follow-up.
    Always resolve tickets before ending the conversation.
    """
    return await _update_ticket_status_impl(input)


@function_tool
async def detect_upsell_signal(input: UpsellSignalInput) -> str:
    """Detect if a customer is asking about a feature only on a higher plan.

    Answer the question fully first, then mention the upgrade in one sentence.
    Do not hard-sell.
    """
    return await _detect_upsell_signal_impl(input)


@function_tool
async def analyze_sentiment(input: SentimentInput) -> str:
    """Analyze the sentiment of a customer message.

    Run on every incoming message to classify emotional state and
    inform escalation decisions.
    """
    return await _analyze_sentiment_impl(input)


ALL_TOOLS = [
    search_knowledge_base,
    create_ticket,
    get_customer_history,
    get_session_context,
    escalate_to_human,
    send_response,
    update_ticket_status,
    detect_upsell_signal,
    analyze_sentiment,
]
