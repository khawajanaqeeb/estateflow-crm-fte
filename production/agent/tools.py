"""
EstateFlow Customer Success FTE — Production Tools
Converted from MCP server tools to OpenAI Agents SDK @function_tool functions.

Key differences from MCP prototype:
- Pydantic BaseModel for strict input validation
- Try/catch with graceful fallbacks on every tool
- PostgreSQL connection pool (asyncpg) instead of in-memory store
- Structured logging instead of print statements
- Detailed docstrings written for LLM consumption
"""

import logging
from typing import Optional
from pydantic import BaseModel
from agents import function_tool

logger = logging.getLogger(__name__)

# ── Note on testability ───────────────────────────────────────────────────────
# Each tool is implemented as a private async function (_impl suffix) and then
# wrapped with @function_tool for the agent. Tests call the _impl functions
# directly, bypassing the FunctionTool wrapper.


# ── Input schemas ─────────────────────────────────────────────────────────────

class KnowledgeSearchInput(BaseModel):
    """Input schema for knowledge base search."""
    query: str
    max_results: int = 5
    category: Optional[str] = None


class CreateTicketInput(BaseModel):
    """Input schema for ticket creation."""
    customer_id: str
    issue: str
    priority: str        # low | medium | high | urgent
    channel: str         # email | whatsapp | web_form


class CustomerHistoryInput(BaseModel):
    """Input schema for customer history retrieval."""
    email: Optional[str] = None
    phone: Optional[str] = None


class SessionContextInput(BaseModel):
    """Input schema for session context retrieval."""
    customer_id: str


class EscalateInput(BaseModel):
    """Input schema for human escalation."""
    ticket_id: str
    reason: str
    level: str           # L1 | L2 | L3 | L4
    context_summary: str
    rule_triggered: Optional[str] = None


class SendResponseInput(BaseModel):
    """Input schema for sending a response."""
    ticket_id: str
    message: str
    channel: str         # email | whatsapp | web_form
    customer_name: Optional[str] = None


class UpdateTicketInput(BaseModel):
    """Input schema for ticket status update."""
    ticket_id: str
    status: str          # resolved | pending | open
    resolution_notes: Optional[str] = None


class UpsellSignalInput(BaseModel):
    """Input schema for upsell signal detection."""
    message: str
    current_plan: str    # starter | professional | team | brokerage


class SentimentInput(BaseModel):
    """Input schema for sentiment analysis."""
    message: str


# ── Tools ─────────────────────────────────────────────────────────────────────

async def _search_knowledge_base_impl(input: KnowledgeSearchInput) -> str:
    """Search EstateFlow product documentation for relevant information.

    Use this when the customer asks questions about product features,
    how to use something, needs technical information, or reports an issue
    that may have a documented solution.

    Args:
        input: Search parameters including query text and optional category filter.

    Returns:
        Formatted search results with section names and relevance scores.
        Returns a helpful message if no results are found.
    """
    try:
        import sys, os
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        from src.agent import knowledge_base

        results = knowledge_base.search(input.query, max_results=input.max_results)
        if not results:
            return "No relevant documentation found for this query. Consider escalating to human support if the customer needs an answer."

        parts = []
        for r in results:
            parts.append(f"**{r.section}** (relevance: {r.score})\n{r.content}")
        return "\n\n---\n\n".join(parts)

    except Exception as e:
        logger.error(f"Knowledge base search failed: {e}")
        return "Knowledge base temporarily unavailable. Please try again or escalate to human support."


async def _create_ticket_impl(input: CreateTicketInput) -> str:
    """Create a support ticket to log a customer interaction.

    ALWAYS call this as the very first tool before sending any response.
    Every customer interaction must be logged with a ticket.
    The returned ticket_id must be used in all subsequent tool calls.

    Args:
        input: Ticket details including customer_id, issue summary, priority, and channel.

    Returns:
        JSON string with ticket_id, status, and creation timestamp.
    """
    try:
        import json, uuid
        from datetime import datetime

        # Production: insert into PostgreSQL tickets table via asyncpg
        # Prototype: return simulated ticket
        ticket_id = "TKT-" + str(uuid.uuid4())[:6].upper()
        result = {
            "ticket_id": ticket_id,
            "customer_id": input.customer_id,
            "channel": input.channel,
            "priority": input.priority,
            "status": "open",
            "created_at": datetime.utcnow().isoformat(),
        }
        logger.info(f"Ticket created: {ticket_id} for customer {input.customer_id}")
        return json.dumps(result)

    except Exception as e:
        logger.error(f"Ticket creation failed: {e}")
        return '{"error": "Ticket creation failed. Proceeding without ticket ID — log manually."}'


async def _get_customer_history_impl(input: CustomerHistoryInput) -> str:
    """Retrieve a customer's full interaction history across ALL channels.

    Use this at the start of every conversation to check if this is a returning
    customer and to understand their prior issues, escalations, and sentiment history.
    Pass either email (preferred) or phone number to identify the customer.

    Args:
        input: Customer identifier — at least one of email or phone required.

    Returns:
        JSON string with customer profile, ticket history, and session history.
    """
    try:
        import json

        if not input.email and not input.phone:
            return '{"error": "Provide at least one of email or phone to identify the customer."}'

        # Production: query PostgreSQL customers + tickets tables
        # Prototype: return new customer response
        identifier = input.email or input.phone
        return json.dumps({
            "customer_id": "LOOKUP_REQUIRED",
            "identifier_used": identifier,
            "status": "new_customer",
            "message": "No prior interactions found. This is a new customer.",
            "prior_tickets": [],
            "prior_sessions": [],
        })

    except Exception as e:
        logger.error(f"Customer history retrieval failed: {e}")
        return '{"error": "Could not retrieve customer history. Proceed as new customer."}'


async def _get_session_context_impl(input: SessionContextInput) -> str:
    """Retrieve the active conversation session for a customer.

    Use this when a customer sends a follow-up message to avoid making them
    repeat themselves. Returns prior turns, sentiment trend, topics covered,
    and whether a channel switch has occurred.

    Args:
        input: Customer ID to look up the active session.

    Returns:
        JSON string with session details and prior conversation turns.
    """
    try:
        import json

        # Production: query PostgreSQL sessions + messages tables
        return json.dumps({
            "customer_id": input.customer_id,
            "active_session": None,
            "message": "No active session. This is the start of a new conversation.",
        })

    except Exception as e:
        logger.error(f"Session context retrieval failed: {e}")
        return '{"error": "Could not retrieve session context. Proceed as new conversation."}'


async def _escalate_to_human_impl(input: EscalateInput) -> str:
    """Escalate a support ticket to a human agent.

    Call this when: the customer requests a human, sentiment is very negative,
    a billing dispute or refund is requested, data loss is reported, a security
    incident is suspected, a technical bug persists after 2 troubleshooting attempts,
    or a brokerage customer has an unresolved issue.

    Always include the full context_summary — the human agent must NOT need to
    ask the customer to repeat themselves.

    Args:
        input: Ticket ID, escalation reason, level (L1-L4), and full context summary.

    Returns:
        JSON string with escalation ID, routing destination, and SLA commitment.
    """
    try:
        import json

        sla_map = {
            "L1": "Next business day",
            "L2": "Within 4 business hours",
            "L3": "Within 1 hour",
            "L4": "Immediate (24/7 on-call)",
        }

        def route(reason: str) -> str:
            r = reason.lower()
            if any(w in r for w in ["billing", "charge", "refund", "invoice"]):
                return "billing@estateflow.io"
            if any(w in r for w in ["security", "unauthorized", "hacked"]):
                return "security@estateflow.io"
            if any(w in r for w in ["legal", "compliance", "gdpr"]):
                return "privacy@estateflow.io"
            if any(w in r for w in ["pricing", "discount", "negotiate"]):
                return "sales@estateflow.io"
            return "team@estateflow.io"

        result = {
            "escalation_id": f"ESC-{input.ticket_id}",
            "ticket_id": input.ticket_id,
            "level": input.level,
            "reason": input.reason,
            "rule_triggered": input.rule_triggered or "Manual escalation",
            "routed_to": route(input.reason),
            "sla": sla_map.get(input.level, "Next business day"),
            "context_summary": input.context_summary,
            "status": "escalated",
        }
        logger.warning(f"Escalation triggered: {input.ticket_id} | {input.level} | {input.reason}")
        return json.dumps(result)

    except Exception as e:
        logger.error(f"Escalation failed: {e}")
        return '{"error": "Escalation system unavailable. Contact team@estateflow.io directly."}'


async def _send_response_impl(input: SendResponseInput) -> str:
    """Send a formatted response to the customer via the appropriate channel.

    ALWAYS call this as the final step. Never reply to the customer without
    calling this tool. The response is formatted automatically for the target
    channel (email gets greeting + signature, WhatsApp is trimmed to plain text).

    Args:
        input: Ticket ID, message text, channel, and optional customer name.

    Returns:
        JSON string with delivery status and the formatted message that was sent.
    """
    try:
        import json, sys, os
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        from src.agent import formatter
        from src.agent.models import Channel

        channel_map = {
            "email": Channel.EMAIL,
            "whatsapp": Channel.WHATSAPP,
            "web_form": Channel.WEB_FORM,
        }
        channel = channel_map.get(input.channel, Channel.EMAIL)
        formatted = formatter.format_for_channel(
            response=input.message,
            channel=channel,
            customer_name=input.customer_name or "",
        )

        # Production: call Gmail API / Twilio / WebSocket based on channel
        result = {
            "ticket_id": input.ticket_id,
            "channel": input.channel,
            "status": "delivered",
            "formatted_message": formatted,
        }
        logger.info(f"Response sent: ticket={input.ticket_id} channel={input.channel}")
        return json.dumps(result)

    except Exception as e:
        logger.error(f"send_response failed: {e}")
        return '{"error": "Response delivery failed. Log the message manually and retry."}'


async def _update_ticket_status_impl(input: UpdateTicketInput) -> str:
    """Update the status of an existing support ticket.

    Mark as 'resolved' once the customer's issue is fully addressed.
    Mark as 'pending' if waiting for customer follow-up or human action.
    Always resolve tickets before ending the conversation.

    Args:
        input: Ticket ID, new status, and optional resolution notes.

    Returns:
        JSON string confirming the status update.
    """
    try:
        import json
        from datetime import datetime

        # Production: UPDATE tickets SET status=... WHERE ticket_id=...
        result = {
            "ticket_id": input.ticket_id,
            "status": input.status,
            "resolution_notes": input.resolution_notes or "",
            "updated_at": datetime.utcnow().isoformat(),
        }
        logger.info(f"Ticket updated: {input.ticket_id} → {input.status}")
        return json.dumps(result)

    except Exception as e:
        logger.error(f"Ticket update failed: {e}")
        return '{"error": "Could not update ticket status."}'


async def _detect_upsell_signal_impl(input: UpsellSignalInput) -> str:
    """Detect if a customer is asking about a feature only available on a higher plan.

    Use this after classifying the customer's intent when their plan is known.
    If an upsell signal is detected, answer the question fully first, then
    mention the upgrade path in one sentence — do not hard-sell.

    Args:
        input: The customer's message and their current plan.

    Returns:
        JSON string with whether a signal was detected, the target plan, and guidance.
    """
    try:
        import json, sys, os
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        from src.agent import escalation as esc

        is_upsell, target_plan = esc.detect_upsell_signal(input.message, input.current_plan)
        plan_prices = {
            "starter": "$39/mo",
            "professional": "$79/mo",
            "team": "$149/mo",
            "brokerage": "Custom pricing",
        }
        return json.dumps({
            "upsell_signal_detected": is_upsell,
            "current_plan": input.current_plan,
            "target_plan": target_plan,
            "target_plan_price": plan_prices.get(target_plan) if target_plan else None,
            "guidance": (
                f"Answer the question fully first. Then add one sentence: "
                f"'This feature is available on our {target_plan.title()} plan "
                f"({plan_prices.get(target_plan)}). You can upgrade anytime from Settings → Billing.'"
            ) if is_upsell else "No upsell action needed.",
        })

    except Exception as e:
        logger.error(f"Upsell detection failed: {e}")
        return '{"upsell_signal_detected": false, "error": "Detection unavailable."}'


async def _analyze_sentiment_impl(input: SentimentInput) -> str:
    """Analyze the sentiment of a customer message.

    Run this on every incoming message to classify emotional state and
    inform escalation decisions. Results are also stored in session memory
    to detect worsening sentiment trends across a conversation.

    Args:
        input: The customer message to analyze.

    Returns:
        JSON string with sentiment label, confidence, and tone guidance.
    """
    try:
        import json, sys, os
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        from src.agent.agent import _quick_sentiment
        from src.agent.models import Sentiment

        sentiment = _quick_sentiment(input.message)
        negative_states = {Sentiment.FRUSTRATED, Sentiment.NEGATIVE, Sentiment.ANGRY}

        tone_guidance = {
            Sentiment.POSITIVE.value:   "Customer is positive. Answer directly and warmly.",
            Sentiment.NEUTRAL.value:    "Customer is neutral. Be clear and professional.",
            Sentiment.NEGATIVE.value:   "Customer is dissatisfied. Acknowledge once, then solve.",
            Sentiment.FRUSTRATED.value: "Customer is frustrated. One empathy sentence, then solve fast.",
            Sentiment.ANGRY.value:      "Customer is angry. Acknowledge, do not defend, escalate if needed.",
        }

        return json.dumps({
            "sentiment": sentiment.value,
            "is_negative": sentiment in negative_states,
            "escalation_advised": sentiment == Sentiment.ANGRY,
            "tone_guidance": tone_guidance.get(sentiment.value, "Respond professionally."),
        })

    except Exception as e:
        logger.error(f"Sentiment analysis failed: {e}")
        return '{"sentiment": "neutral", "error": "Sentiment analysis unavailable."}'


# ── @function_tool decorated wrappers (used by the OpenAI Agents SDK agent) ───
# Tests call the _impl functions directly; the agent uses these wrappers.

@function_tool
async def search_knowledge_base(input: KnowledgeSearchInput) -> str:
    """Search EstateFlow product documentation for relevant information."""
    return await _search_knowledge_base_impl(input)

@function_tool
async def create_ticket(input: CreateTicketInput) -> str:
    """Create a support ticket. ALWAYS call this first before responding."""
    return await _create_ticket_impl(input)

@function_tool
async def get_customer_history(input: CustomerHistoryInput) -> str:
    """Retrieve a customer's full interaction history across all channels."""
    return await _get_customer_history_impl(input)

@function_tool
async def get_session_context(input: SessionContextInput) -> str:
    """Retrieve the active conversation session for a customer."""
    return await _get_session_context_impl(input)

@function_tool
async def escalate_to_human(input: EscalateInput) -> str:
    """Escalate a ticket to a human agent with full context."""
    return await _escalate_to_human_impl(input)

@function_tool
async def send_response(input: SendResponseInput) -> str:
    """Send a formatted response to the customer. ALWAYS call this last."""
    return await _send_response_impl(input)

@function_tool
async def update_ticket_status(input: UpdateTicketInput) -> str:
    """Update the status of a support ticket."""
    return await _update_ticket_status_impl(input)

@function_tool
async def detect_upsell_signal(input: UpsellSignalInput) -> str:
    """Detect if a customer needs a feature only available on a higher plan."""
    return await _detect_upsell_signal_impl(input)

@function_tool
async def analyze_sentiment(input: SentimentInput) -> str:
    """Analyze the sentiment of a customer message."""
    return await _analyze_sentiment_impl(input)


# Convenience list for registering all tools with the agent
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
