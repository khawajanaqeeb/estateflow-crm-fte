"""
EstateFlow Customer Success AI Agent — Core Prototype Loop.

Flow:
  IncomingMessage
    → identify customer (cross-channel)
    → get or create conversation session (memory)
    → retrieve full session context (prior turns, channel switches)
    → search knowledge base
    → check escalation rules (uses sentiment trend from session)
    → generate response via Claude (with session context)
    → format for channel
    → record turn in session memory
    → create/update ticket in store
    → return AgentResponse
"""

import os
import json
import re
from pathlib import Path

import anthropic

from .models import (
    AgentResponse, Channel, IncomingMessage, Message,
    Priority, Sentiment, TicketStatus,
)
from .customer_store import CustomerStore
from .memory import MemoryStore
from . import knowledge_base
from . import escalation as esc_engine
from . import formatter

# ── Context documents ─────────────────────────────────────────────────────────

_CONTEXT_DIR = Path(__file__).parents[2] / "context"

def _load(filename: str) -> str:
    return (_CONTEXT_DIR / filename).read_text(encoding="utf-8")

_BRAND_VOICE    = _load("brand-voice.md")
_COMPANY        = _load("company-profile.md")
_ESC_RULES      = _load("escalation-rules.md")


# ── System prompt ─────────────────────────────────────────────────────────────

SYSTEM_PROMPT = f"""You are the Customer Success AI for EstateFlow CRM — a real estate CRM platform.
You handle support inquiries from real estate agents, team leads, and brokerage admins.

== YOUR ROLE ==
Answer customer questions accurately using the product documentation provided in each message.
Follow the brand voice and communication standards exactly.
Never invent features, never promise timelines, never discuss competitors negatively.
If a question has multiple parts, answer ALL of them.

== BRAND VOICE SUMMARY ==
{_BRAND_VOICE[:2000]}

== COMPANY CONTEXT ==
{_COMPANY[:1500]}

== RESPONSE FORMAT INSTRUCTIONS ==
You will be told the channel in each request. Follow these rules strictly:

EMAIL:
- 150–500 words
- Formal, structured, use numbered steps for instructions
- Do NOT include greeting or sign-off — those are added automatically

WHATSAPP:
- Under 80 words, plain text only
- No markdown, no bold, no headers
- Direct and conversational
- Do NOT include greeting or sign-off

WEB_FORM:
- 100–300 words, semi-formal
- Use numbered steps for multi-step answers
- Do NOT include greeting or sign-off

== OUTPUT FORMAT ==
Respond with a JSON object with these fields:
{{
  "response": "your customer-facing response text",
  "sentiment_detected": "positive|neutral|negative|frustrated|angry",
  "topics": ["list", "of", "topics", "covered"],
  "priority": "low|medium|high|urgent",
  "confidence": 0.0-1.0
}}
"""


# ── Sentiment classifier ──────────────────────────────────────────────────────

_NEGATIVE_WORDS = re.compile(
    r'\b(frustrated|angry|terrible|awful|broken|useless|disaster|'
    r'unacceptable|worst|hate|ridiculous|waste)\b',
    re.IGNORECASE,
)
_POSITIVE_WORDS = re.compile(
    r'\b(great|thanks|thank you|love|excited|perfect|awesome|helpful|appreciate)\b',
    re.IGNORECASE,
)

def _quick_sentiment(message: str) -> Sentiment:
    """Lightweight pre-check sentiment before Claude call."""
    neg = len(_NEGATIVE_WORDS.findall(message))
    pos = len(_POSITIVE_WORDS.findall(message))
    if neg >= 2:
        return Sentiment.ANGRY
    if neg == 1:
        return Sentiment.FRUSTRATED
    if pos >= 1:
        return Sentiment.POSITIVE
    return Sentiment.NEUTRAL


def _map_sentiment(raw: str) -> Sentiment:
    mapping = {
        "positive": Sentiment.POSITIVE,
        "neutral": Sentiment.NEUTRAL,
        "negative": Sentiment.NEGATIVE,
        "frustrated": Sentiment.FRUSTRATED,
        "angry": Sentiment.ANGRY,
    }
    return mapping.get(raw.lower(), Sentiment.NEUTRAL)


def _map_priority(raw: str) -> Priority:
    mapping = {
        "low": Priority.LOW,
        "medium": Priority.MEDIUM,
        "high": Priority.HIGH,
        "urgent": Priority.URGENT,
    }
    return mapping.get(raw.lower(), Priority.MEDIUM)


# ── Agent class ───────────────────────────────────────────────────────────────

class CustomerSuccessAgent:
    def __init__(self, api_key: str | None = None):
        self.client = anthropic.Anthropic(
            api_key=api_key or os.environ.get("ANTHROPIC_API_KEY")
        )
        self.store = CustomerStore()
        self.memory = MemoryStore()
        self.model = "claude-haiku-4-5-20251001"   # fast + cheap for prototype

    def handle(self, incoming: IncomingMessage) -> AgentResponse:
        """Main entry point — process one incoming message end to end."""

        # 1. Identify customer (cross-channel unification)
        customer = self.store.identify_customer(
            email=incoming.customer_email,
            phone=incoming.customer_phone,
            name=incoming.customer_name,
            plan=incoming.plan,
            channel=incoming.channel,
        )

        # 2. Get or create conversation session (memory)
        session, is_new_session = self.memory.get_or_create_session(
            customer_id=customer.customer_id,
            channel=incoming.channel,
        )

        # 3. Build session context for Claude
        #    - conversation history (prior turns)
        #    - cross-channel history summary (all past sessions)
        session_context = session.to_context_string(max_turns=5)
        all_sessions_context = self.memory.get_customer_context(customer.customer_id)

        # 4. Quick sentiment pre-check (regex, before API call)
        quick_sentiment = _quick_sentiment(incoming.raw_message)

        # 5. Escalation check — uses full sentiment TREND from session memory
        prior_trend = session.sentiment_trend   # full trend for this session

        open_tickets = self.store.get_open_tickets(customer.customer_id)
        troubleshooting_attempts = len(session.turns)   # turns = troubleshooting rounds

        esc_decision = esc_engine.check(
            message=incoming.raw_message,
            sentiment=quick_sentiment,
            channel=incoming.channel,
            plan=incoming.plan,
            troubleshooting_attempts=troubleshooting_attempts,
            prior_sentiment_trend=prior_trend,
        )

        # Sentiment worsening override — escalate even if no single rule fires
        if not esc_decision.should_escalate and session.sentiment_worsening():
            from .escalation import EscalationDecision
            esc_decision = EscalationDecision(
                should_escalate=True,
                reason="Sentiment deteriorating across conversation turns",
                level="L2",
                rule="Rule 2 — Persistent Negative Sentiment",
            )

        # 6. Detect upsell signal
        is_upsell, upsell_plan = esc_engine.detect_upsell_signal(
            incoming.raw_message, incoming.plan
        )

        # 7. Search knowledge base
        kb_results = knowledge_base.search(incoming.raw_message, max_results=3)
        kb_context = knowledge_base.format_results(kb_results)

        # 8. Detect channel switch
        channel_switch_note = ""
        if not is_new_session and session.channel_switched(incoming.channel):
            channel_switch_note = (
                f"NOTE: This customer previously contacted via "
                f"{session.original_channel.value} and has now switched to "
                f"{incoming.channel.value}. Do not ask them to repeat information "
                f"already covered in session history."
            )

        # 9. Generate response via Claude (now includes session context)
        raw_response, ai_sentiment, topics, priority = self._generate_response(
            incoming=incoming,
            customer_name=incoming.customer_name or "",
            kb_context=kb_context,
            session_context=session_context,
            all_sessions_context=all_sessions_context,
            is_escalating=esc_decision.should_escalate,
            esc_decision=esc_decision,
            upsell_plan=upsell_plan,
            channel_switch_note=channel_switch_note,
        )

        sentiment = _map_sentiment(ai_sentiment)
        priority_enum = _map_priority(priority)

        # 10. Format for channel
        formatted = formatter.format_for_channel(
            response=raw_response,
            channel=incoming.channel,
            customer_name=incoming.customer_name or "",
        )

        # 11. Record turn in session memory
        session.add_turn(
            customer_message=incoming.raw_message,
            agent_response=formatted,
            channel=incoming.channel,
            sentiment=sentiment,
            topics=topics,
        )

        # 12. Update session status
        if esc_decision.should_escalate:
            self.memory.escalate(session.session_id, reason=esc_decision.reason)
        else:
            self.memory.resolve(session.session_id, summary=f"Resolved: {topics}")

        # 13. Create ticket in the store and log messages
        ticket = self.store.create_ticket(
            customer_id=customer.customer_id,
            channel=incoming.channel,
            issue_summary=incoming.raw_message[:120],
            priority=priority_enum,
        )

        self.store.add_message(ticket.ticket_id, Message(
            role="customer",
            content=incoming.raw_message,
            channel=incoming.channel,
            sentiment=sentiment,
        ))
        self.store.add_message(ticket.ticket_id, Message(
            role="agent",
            content=formatted,
            channel=incoming.channel,
        ))
        self.store.update_sentiment(ticket.ticket_id, sentiment)

        if esc_decision.should_escalate:
            self.store.escalate_ticket(
                ticket.ticket_id,
                reason=esc_decision.reason,
                level=esc_decision.level,
            )
        else:
            self.store.update_status(ticket.ticket_id, TicketStatus.RESOLVED)

        return AgentResponse(
            ticket_id=ticket.ticket_id,
            message=formatted,
            channel=incoming.channel,
            escalate=esc_decision.should_escalate,
            escalation_reason=esc_decision.reason,
            escalation_level=esc_decision.level,
            sentiment_detected=sentiment,
            topics_detected=topics,
            priority=priority_enum,
            upsell_signal=is_upsell,
            upsell_plan=upsell_plan,
        )

    def _generate_response(
        self,
        incoming: IncomingMessage,
        customer_name: str,
        kb_context: str,
        session_context: str,
        all_sessions_context: str,
        is_escalating: bool,
        esc_decision,
        upsell_plan: str | None,
        channel_switch_note: str = "",
    ) -> tuple[str, str, list, str]:
        """Call Claude and return (response_text, sentiment, topics, priority)."""

        escalation_note = ""
        if is_escalating:
            escalation_note = f"""
ESCALATION TRIGGERED: {esc_decision.rule}
Write a response that:
- Acknowledges the issue with genuine empathy (one sentence only)
- Informs the customer a human team member will follow up
- Gives the escalation timeframe based on level {esc_decision.level}:
  L1: next business day | L2: within 4 hours | L3: within 1 hour | L4: immediately
- Provides a ticket reference note
Do NOT attempt to solve the technical issue yourself.
"""

        upsell_note = ""
        if upsell_plan:
            upsell_note = f"""
UPSELL SIGNAL: The customer is asking about a feature available on the {upsell_plan.title()} plan.
Answer their question fully first, then briefly mention that this feature is available on the {upsell_plan.title()} plan.
Do not hard-sell. One sentence maximum about the upgrade.
"""

        user_content = f"""
CHANNEL: {incoming.channel.value}
CUSTOMER NAME: {customer_name or "Unknown"}
CUSTOMER PLAN: {incoming.plan or "Unknown"}

CUSTOMER SESSION HISTORY (this conversation so far):
{session_context if session_context else "This is the first message in this session."}

ALL-TIME CUSTOMER HISTORY (past sessions):
{all_sessions_context}

{channel_switch_note}

PRODUCT DOCUMENTATION (relevant sections):
{kb_context}

CUSTOMER MESSAGE:
{incoming.raw_message}
{escalation_note}
{upsell_note}

Respond with valid JSON only. No text outside the JSON object.
"""

        message = self.client.messages.create(
            model=self.model,
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_content}],
        )

        raw = message.content[0].text.strip()

        # parse JSON response
        try:
            # strip markdown code fences if present
            raw_clean = re.sub(r'^```(?:json)?\n?', '', raw)
            raw_clean = re.sub(r'\n?```$', '', raw_clean)
            data = json.loads(raw_clean)
            return (
                data.get("response", raw),
                data.get("sentiment_detected", "neutral"),
                data.get("topics", []),
                data.get("priority", "medium"),
            )
        except (json.JSONDecodeError, KeyError):
            # fallback: return raw text with defaults
            return raw, "neutral", [], "medium"

    def memory_summary(self) -> dict:
        """Return combined store + memory stats — useful for reporting."""
        return {
            "store": self.store.summary(),
            "memory": self.memory.summary(),
        }
