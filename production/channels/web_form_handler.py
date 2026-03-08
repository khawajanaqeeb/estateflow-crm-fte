"""
EstateFlow Customer Success FTE — Web Support Form Handler
FastAPI router that accepts support form submissions and publishes them to Kafka.

Endpoints:
  POST /support/submit          — submit a new support request
  GET  /support/ticket/{id}     — check ticket status and conversation history
"""

import uuid
import logging
from datetime import datetime, timezone
from typing import Literal, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr, field_validator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/support", tags=["support-form"])

# ── Request / Response models ─────────────────────────────────────────────────

class SupportFormSubmission(BaseModel):
    name: str
    email: EmailStr
    subject: str
    category: Literal["general", "technical", "billing", "bug_report", "feedback"]
    message: str
    priority: Literal["low", "medium", "high"] = "medium"
    attachments: list[str] = []

    @field_validator("name")
    @classmethod
    def name_min_length(cls, v: str) -> str:
        if len(v.strip()) < 2:
            raise ValueError("Name must be at least 2 characters")
        return v.strip()

    @field_validator("subject")
    @classmethod
    def subject_min_length(cls, v: str) -> str:
        if len(v.strip()) < 5:
            raise ValueError("Subject must be at least 5 characters")
        return v.strip()

    @field_validator("message")
    @classmethod
    def message_min_length(cls, v: str) -> str:
        if len(v.strip()) < 10:
            raise ValueError("Message must be at least 10 characters")
        return v.strip()


class SupportFormResponse(BaseModel):
    ticket_id: str
    message: str
    estimated_response_time: str


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/submit", response_model=SupportFormResponse)
async def submit_support_form(submission: SupportFormSubmission):
    """
    Accept a web support form submission.

    1. Validates the submission (Pydantic handles this).
    2. Builds a normalized message dict.
    3. Publishes to Kafka fte.tickets.incoming.
    4. Returns ticket_id to the customer for status tracking.
    """
    from production.kafka_client import FTEKafkaProducer, TOPICS

    ticket_id = str(uuid.uuid4())

    message_data = {
        "channel":          "web_form",
        "channel_message_id": ticket_id,
        "customer_email":   submission.email,
        "customer_name":    submission.name,
        "subject":          submission.subject,
        "content":          submission.message,
        "category":         submission.category,
        "priority":         submission.priority,
        "received_at":      datetime.now(timezone.utc).isoformat(),
        "metadata": {
            "form_version": "1.0",
            "attachments":  submission.attachments,
        },
    }

    try:
        producer = FTEKafkaProducer()
        await producer.start()
        await producer.publish(TOPICS["tickets_incoming"], message_data)
        await producer.stop()
    except Exception as e:
        logger.error("Failed to publish web form submission to Kafka: %s", e)
        raise HTTPException(
            status_code=503,
            detail="Could not queue your request. Please try again in a moment.",
        )

    logger.info("Web form submission queued: ticket=%s email=%s", ticket_id, submission.email)

    return SupportFormResponse(
        ticket_id=ticket_id,
        message="Thank you for contacting us! Our AI assistant will respond to your email shortly.",
        estimated_response_time="Usually within 5 minutes",
    )


@router.get("/ticket/{ticket_id}")
async def get_ticket_status(ticket_id: str):
    """
    Return the current status and full message history for a ticket.
    Used by the web form UI to let customers track their request.
    """
    from production.database.queries import get_ticket_by_id

    ticket = await get_ticket_by_id(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    return {
        "ticket_id":    ticket_id,
        "status":       ticket["status"],
        "created_at":   ticket["created_at"],
        "last_updated": ticket["last_updated"],
        "messages": [
            {
                "role":       m["role"],
                "content":    m["content"],
                "channel":    m["channel"],
                "created_at": m["created_at"],
            }
            for m in ticket["messages"]
        ],
    }
