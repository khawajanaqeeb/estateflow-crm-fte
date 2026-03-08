"""
Conversation memory and session management.

A "session" is an ongoing conversation with a customer — potentially
spanning multiple messages and multiple channels. The agent uses session
history to maintain context across follow-up messages.

Key responsibilities:
- Link follow-up messages to the correct open session
- Detect channel switches within a session
- Build context window payload for Claude from prior messages
- Track sentiment trend and surface worsening patterns
- Summarize long sessions to stay within token limits
- Mark sessions as resolved, pending, or escalated
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

from .models import Channel, Sentiment


# Sessions idle for more than this are treated as new conversations
SESSION_TIMEOUT_MINUTES = 60 * 4   # 4 hours


@dataclass
class Turn:
    """A single exchange in a session (one customer message + one agent reply)."""
    turn_id: str
    customer_message: str
    agent_response: str
    channel: Channel
    sentiment: Sentiment
    topics: list[str]
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class Session:
    """
    An ongoing conversation with a customer.
    May span multiple channels.
    """
    session_id: str
    customer_id: str
    status: str                         # open | resolved | escalated | pending
    original_channel: Channel
    channels_used: list[Channel]
    turns: list[Turn]
    sentiment_trend: list[Sentiment]
    topics_covered: list[str]
    resolution_summary: Optional[str]
    escalation_reason: Optional[str]
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_active_at: datetime = field(default_factory=datetime.utcnow)

    def is_expired(self) -> bool:
        cutoff = datetime.utcnow() - timedelta(minutes=SESSION_TIMEOUT_MINUTES)
        return self.last_active_at < cutoff

    def channel_switched(self, incoming_channel: Channel) -> bool:
        return incoming_channel != self.original_channel

    def sentiment_worsening(self) -> bool:
        """True if the last 2 sentiments are both negative/frustrated/angry."""
        negative = {Sentiment.NEGATIVE, Sentiment.FRUSTRATED, Sentiment.ANGRY}
        if len(self.sentiment_trend) >= 2:
            return all(s in negative for s in self.sentiment_trend[-2:])
        return False

    def add_turn(
        self,
        customer_message: str,
        agent_response: str,
        channel: Channel,
        sentiment: Sentiment,
        topics: list[str],
    ) -> Turn:
        turn = Turn(
            turn_id=str(uuid.uuid4())[:6],
            customer_message=customer_message,
            agent_response=agent_response,
            channel=channel,
            sentiment=sentiment,
            topics=topics,
        )
        self.turns.append(turn)
        self.sentiment_trend.append(sentiment)
        if channel not in self.channels_used:
            self.channels_used.append(channel)
        for t in topics:
            if t not in self.topics_covered:
                self.topics_covered.append(t)
        self.last_active_at = datetime.utcnow()
        return turn

    def to_context_string(self, max_turns: int = 5) -> str:
        """
        Format session history for Claude's context window.
        Only includes the last max_turns turns to stay within limits.
        """
        if not self.turns:
            return ""

        recent = self.turns[-max_turns:]
        parts = [f"[Conversation history — {len(self.turns)} turn(s) total, showing last {len(recent)}]"]

        if self.channel_switched(self.turns[-1].channel if self.turns else self.original_channel):
            parts.append(
                f"NOTE: Customer originally contacted via {self.original_channel.value}. "
                f"Channels used: {', '.join(c.value for c in self.channels_used)}."
            )

        for turn in recent:
            parts.append(
                f"\n[Turn {self.turns.index(turn) + 1} | {turn.channel.value} | "
                f"sentiment={turn.sentiment.value}]"
            )
            parts.append(f"Customer: {turn.customer_message}")
            parts.append(f"Agent: {turn.agent_response[:300]}{'...' if len(turn.agent_response) > 300 else ''}")

        if self.topics_covered:
            parts.append(f"\nTopics already addressed: {', '.join(self.topics_covered)}")

        return "\n".join(parts)


class MemoryStore:
    """
    In-memory session store.
    Replaced with PostgreSQL (sessions + messages tables) in Stage 2.
    """

    def __init__(self):
        # customer_id -> list of Session (most recent last)
        self._sessions: dict[str, list[Session]] = {}
        # session_id -> Session (fast lookup)
        self._by_id: dict[str, Session] = {}

    # ── Session lifecycle ─────────────────────────────────────────────────────

    def get_or_create_session(
        self, customer_id: str, channel: Channel
    ) -> tuple[Session, bool]:
        """
        Find an active (non-expired) session for this customer,
        or create a new one.

        Returns (session, is_new).
        """
        existing = self._find_active(customer_id)
        if existing:
            if existing.channel_switched(channel):
                _note = (
                    f"Channel switch detected: {existing.original_channel.value} → {channel.value}"
                )
                # record the channel but keep the session alive
                if channel not in existing.channels_used:
                    existing.channels_used.append(channel)
            return existing, False

        session = self._create(customer_id, channel)
        return session, True

    def _find_active(self, customer_id: str) -> Optional[Session]:
        sessions = self._sessions.get(customer_id, [])
        for session in reversed(sessions):
            if session.status == "open" and not session.is_expired():
                return session
        return None

    def _create(self, customer_id: str, channel: Channel) -> Session:
        session = Session(
            session_id=str(uuid.uuid4())[:8],
            customer_id=customer_id,
            status="open",
            original_channel=channel,
            channels_used=[channel],
            turns=[],
            sentiment_trend=[],
            topics_covered=[],
            resolution_summary=None,
            escalation_reason=None,
        )
        self._sessions.setdefault(customer_id, []).append(session)
        self._by_id[session.session_id] = session
        return session

    # ── State updates ─────────────────────────────────────────────────────────

    def resolve(self, session_id: str, summary: str = ""):
        session = self._by_id.get(session_id)
        if session:
            session.status = "resolved"
            session.resolution_summary = summary

    def escalate(self, session_id: str, reason: str):
        session = self._by_id.get(session_id)
        if session:
            session.status = "escalated"
            session.escalation_reason = reason

    def mark_pending(self, session_id: str):
        session = self._by_id.get(session_id)
        if session:
            session.status = "pending"

    # ── Queries ───────────────────────────────────────────────────────────────

    def get_session(self, session_id: str) -> Optional[Session]:
        return self._by_id.get(session_id)

    def get_all_sessions(self, customer_id: str) -> list[Session]:
        return self._sessions.get(customer_id, [])

    def get_customer_context(self, customer_id: str) -> str:
        """
        Build a compact history summary across ALL past sessions for a customer.
        Used to give the agent awareness of the customer's full journey.
        """
        sessions = self._sessions.get(customer_id, [])
        if not sessions:
            return "New customer — no prior sessions."

        lines = [f"Customer has {len(sessions)} session(s) on record:"]
        for s in sessions[-4:]:     # last 4 sessions
            status_icon = {"open": "🔓", "resolved": "✓", "escalated": "⚠", "pending": "⏳"}.get(s.status, "?")
            channels = " + ".join(c.value for c in s.channels_used)
            topics = ", ".join(s.topics_covered[:4]) if s.topics_covered else "unknown"
            lines.append(
                f"  {status_icon} [{s.created_at.strftime('%Y-%m-%d')}] "
                f"via {channels} | topics: {topics} | {s.status}"
            )
            if s.escalation_reason:
                lines.append(f"    Escalated: {s.escalation_reason}")

        return "\n".join(lines)

    def summary(self) -> dict:
        all_sessions = [s for sessions in self._sessions.values() for s in sessions]
        return {
            "total_sessions": len(all_sessions),
            "open": sum(1 for s in all_sessions if s.status == "open"),
            "resolved": sum(1 for s in all_sessions if s.status == "resolved"),
            "escalated": sum(1 for s in all_sessions if s.status == "escalated"),
            "pending": sum(1 for s in all_sessions if s.status == "pending"),
            "multi_channel": sum(1 for s in all_sessions if len(s.channels_used) > 1),
        }
