"""
In-memory customer and ticket store.
Will be replaced with PostgreSQL in Stage 2.
"""

import uuid
from datetime import datetime
from typing import Optional

from .models import Customer, Ticket, Message, Channel, Priority, TicketStatus, Sentiment


class CustomerStore:
    def __init__(self):
        self._customers: dict[str, Customer] = {}   # customer_id -> Customer
        self._email_index: dict[str, str] = {}       # email -> customer_id
        self._phone_index: dict[str, str] = {}       # phone -> customer_id
        self._tickets: dict[str, Ticket] = {}        # ticket_id -> Ticket

    # ── Customer identity ────────────────────────────────────────────────────

    def identify_customer(
        self,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        name: Optional[str] = None,
        plan: Optional[str] = None,
        channel: Optional[Channel] = None,
    ) -> Customer:
        """
        Find or create a customer. Email is the primary key; phone is secondary.
        Merges identifiers if both email and phone are provided.
        """
        customer_id = None

        if email and email in self._email_index:
            customer_id = self._email_index[email]
        elif phone and phone in self._phone_index:
            customer_id = self._phone_index[phone]

        if customer_id:
            customer = self._customers[customer_id]
            # enrich with any new data
            if email and not customer.email:
                customer.email = email
                self._email_index[email] = customer_id
            if phone and not customer.phone:
                customer.phone = phone
                self._phone_index[phone] = customer_id
            if name and not customer.name:
                customer.name = name
            if plan:
                customer.plan = plan
            if channel and channel not in customer.channels_used:
                customer.channels_used.append(channel)
            return customer

        # new customer
        customer_id = str(uuid.uuid4())[:8]
        customer = Customer(
            customer_id=customer_id,
            email=email,
            phone=phone,
            name=name,
            plan=plan,
            channels_used=[channel] if channel else [],
        )
        self._customers[customer_id] = customer
        if email:
            self._email_index[email] = customer_id
        if phone:
            self._phone_index[phone] = customer_id
        return customer

    def get_customer(self, customer_id: str) -> Optional[Customer]:
        return self._customers.get(customer_id)

    # ── Ticket management ────────────────────────────────────────────────────

    def create_ticket(
        self,
        customer_id: str,
        channel: Channel,
        issue_summary: str,
        priority: Priority,
    ) -> Ticket:
        ticket_id = "TKT-" + str(uuid.uuid4())[:6].upper()
        ticket = Ticket(
            ticket_id=ticket_id,
            customer_id=customer_id,
            channel=channel,
            issue_summary=issue_summary,
            priority=priority,
            status=TicketStatus.OPEN,
        )
        self._tickets[ticket_id] = ticket
        return ticket

    def get_ticket(self, ticket_id: str) -> Optional[Ticket]:
        return self._tickets.get(ticket_id)

    def add_message(self, ticket_id: str, message: Message):
        ticket = self._tickets.get(ticket_id)
        if ticket:
            ticket.messages.append(message)
            ticket.updated_at = datetime.utcnow()

    def update_status(self, ticket_id: str, status: TicketStatus, resolution_notes: str = ""):
        ticket = self._tickets.get(ticket_id)
        if ticket:
            ticket.status = status
            ticket.updated_at = datetime.utcnow()
            if status == TicketStatus.RESOLVED:
                ticket.resolved_at = datetime.utcnow()

    def escalate_ticket(self, ticket_id: str, reason: str, level: str):
        ticket = self._tickets.get(ticket_id)
        if ticket:
            ticket.status = TicketStatus.ESCALATED
            ticket.escalation_reason = reason
            ticket.escalation_level = level
            ticket.updated_at = datetime.utcnow()

    def update_sentiment(self, ticket_id: str, sentiment: Sentiment):
        ticket = self._tickets.get(ticket_id)
        if ticket:
            ticket.sentiment_trend.append(sentiment)
            ticket.updated_at = datetime.utcnow()

    def get_customer_history(self, customer_id: str) -> list[Ticket]:
        """Return all tickets for a customer, sorted newest first."""
        return sorted(
            [t for t in self._tickets.values() if t.customer_id == customer_id],
            key=lambda t: t.created_at,
            reverse=True,
        )

    def get_open_tickets(self, customer_id: str) -> list[Ticket]:
        return [
            t for t in self._tickets.values()
            if t.customer_id == customer_id and t.status == TicketStatus.OPEN
        ]

    def summary(self) -> dict:
        return {
            "total_customers": len(self._customers),
            "total_tickets": len(self._tickets),
            "open": sum(1 for t in self._tickets.values() if t.status == TicketStatus.OPEN),
            "resolved": sum(1 for t in self._tickets.values() if t.status == TicketStatus.RESOLVED),
            "escalated": sum(1 for t in self._tickets.values() if t.status == TicketStatus.ESCALATED),
        }
