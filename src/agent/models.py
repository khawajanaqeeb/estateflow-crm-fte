"""
Core data models for the EstateFlow Customer Success FTE prototype.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class Channel(str, Enum):
    EMAIL = "email"
    WHATSAPP = "whatsapp"
    WEB_FORM = "web_form"


class Priority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class TicketStatus(str, Enum):
    OPEN = "open"
    RESOLVED = "resolved"
    ESCALATED = "escalated"
    PENDING = "pending"


class Sentiment(str, Enum):
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"
    FRUSTRATED = "frustrated"
    ANGRY = "angry"


@dataclass
class IncomingMessage:
    """A normalized message from any channel."""
    channel: Channel
    raw_message: str
    customer_email: Optional[str] = None    # primary key for identity
    customer_phone: Optional[str] = None    # secondary key (WhatsApp)
    customer_name: Optional[str] = None
    subject: Optional[str] = None           # email only
    plan: Optional[str] = None
    received_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class Message:
    """A single message in a conversation."""
    role: str           # "customer" or "agent"
    content: str
    channel: Channel
    timestamp: datetime = field(default_factory=datetime.utcnow)
    sentiment: Optional[Sentiment] = None


@dataclass
class Customer:
    """A unified customer record across all channels."""
    customer_id: str
    email: Optional[str] = None
    phone: Optional[str] = None
    name: Optional[str] = None
    plan: Optional[str] = None
    channels_used: list = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class Ticket:
    """A support ticket tracking a customer interaction."""
    ticket_id: str
    customer_id: str
    channel: Channel
    issue_summary: str
    priority: Priority
    status: TicketStatus
    sentiment_trend: list = field(default_factory=list)  # list of Sentiment values
    topics: list = field(default_factory=list)
    messages: list = field(default_factory=list)         # list of Message
    escalation_reason: Optional[str] = None
    escalation_level: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    resolved_at: Optional[datetime] = None


@dataclass
class AgentResponse:
    """The agent's output for a given incoming message."""
    ticket_id: str
    message: str                    # formatted response ready to send
    channel: Channel
    escalate: bool
    escalation_reason: Optional[str]
    escalation_level: Optional[str]
    sentiment_detected: Sentiment
    topics_detected: list
    priority: Priority
    upsell_signal: bool = False
    upsell_plan: Optional[str] = None
