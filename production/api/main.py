"""
EstateFlow Customer Success FTE — FastAPI Application
Receives webhooks from Gmail and Twilio, accepts web form submissions,
and exposes operational endpoints for monitoring and customer lookup.

Endpoints:
  GET  /health                         — liveness + channel status
  POST /support/submit                 — web form submission (via web_form_handler)
  GET  /support/ticket/{id}            — ticket status (via web_form_handler)
  POST /webhooks/gmail                 — Gmail Pub/Sub push notification
  POST /webhooks/whatsapp              — Twilio inbound WhatsApp message
  POST /webhooks/whatsapp/status       — Twilio delivery status callback
  GET  /customers/lookup               — look up customer by email or phone
  GET  /conversations/{id}             — full conversation history
  GET  /metrics/channels               — per-channel 24h performance metrics
"""

import logging
from datetime import datetime, timezone

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from production.channels.gmail_handler import GmailHandler
from production.channels.whatsapp_handler import WhatsAppHandler
from production.channels.web_form_handler import router as web_form_router
from production.kafka_client import FTEKafkaProducer, TOPICS

logger = logging.getLogger(__name__)

# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="EstateFlow Customer Success FTE API",
    description="24/7 AI-powered customer support across Email, WhatsApp, and Web Form.",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS — allow the web form to POST from any origin (tighten in production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Shared instances ──────────────────────────────────────────────────────────

gmail_handler     = GmailHandler()
whatsapp_handler  = WhatsAppHandler()
kafka_producer    = FTEKafkaProducer()

# ── Routers ───────────────────────────────────────────────────────────────────

app.include_router(web_form_router)

# ── Lifecycle ─────────────────────────────────────────────────────────────────

@app.on_event("startup")
async def startup() -> None:
    await kafka_producer.start()
    logger.info("FastAPI startup complete — Kafka producer ready")


@app.on_event("shutdown")
async def shutdown() -> None:
    await kafka_producer.stop()
    from production.database.queries import close_db_pool
    await close_db_pool()
    logger.info("FastAPI shutdown complete")


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/health", tags=["ops"])
async def health_check():
    """
    Liveness probe. Returns 200 when the API is up.
    Channel status is best-effort — failures are logged but don't fail the probe.
    """
    import os

    gmail_status     = "active" if os.getenv("GMAIL_CREDENTIALS") else "not_configured"
    whatsapp_status  = "active" if os.getenv("TWILIO_ACCOUNT_SID") else "not_configured"

    return {
        "status":    "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "channels": {
            "email":     gmail_status,
            "whatsapp":  whatsapp_status,
            "web_form":  "active",
        },
    }


# ── Gmail webhook ─────────────────────────────────────────────────────────────

@app.post("/webhooks/gmail", tags=["webhooks"])
async def gmail_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    Receive Gmail Pub/Sub push notifications.

    Google sends a JSON body with a base64-encoded 'data' field containing
    the Gmail historyId. We decode it and fetch the new messages via the
    Gmail API, then publish each to fte.tickets.incoming.
    """
    import base64

    try:
        body = await request.json()

        # Pub/Sub wraps the notification in a 'message' envelope
        pubsub_envelope = body.get("message", {})
        raw_data = pubsub_envelope.get("data", "")

        # Decode the base64 payload to get the historyId JSON
        if raw_data:
            decoded = base64.urlsafe_b64decode(raw_data + "==").decode("utf-8")
            import json
            notification = json.loads(decoded)
        else:
            notification = body  # fallback: treat body directly as notification

        messages = await gmail_handler.process_notification(notification)

        for msg in messages:
            background_tasks.add_task(
                kafka_producer.publish,
                TOPICS["tickets_incoming"],
                msg,
            )

        logger.info("Gmail webhook: %d message(s) queued", len(messages))
        return {"status": "processed", "count": len(messages)}

    except Exception as e:
        logger.error("Gmail webhook error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


# ── WhatsApp webhook ──────────────────────────────────────────────────────────

@app.post("/webhooks/whatsapp", tags=["webhooks"])
async def whatsapp_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    Receive inbound WhatsApp messages via Twilio webhook.
    Validates the Twilio signature, normalizes the message, and publishes
    to fte.tickets.incoming.

    Returns an empty TwiML response — the agent sends its reply asynchronously
    via the Twilio REST API, not via this synchronous response.
    """
    if not await whatsapp_handler.validate_webhook(request):
        logger.warning("WhatsApp webhook: invalid Twilio signature")
        raise HTTPException(status_code=403, detail="Invalid Twilio signature")

    form_data = await request.form()
    message   = await whatsapp_handler.process_webhook(dict(form_data))

    # Only queue messages that have content (ignore delivery receipts on this endpoint)
    if message.get("content"):
        background_tasks.add_task(
            kafka_producer.publish,
            TOPICS["tickets_incoming"],
            message,
        )
        logger.info(
            "WhatsApp webhook: message queued from %s", message.get("customer_phone")
        )

    # Empty TwiML — Twilio requires a valid XML response
    return Response(
        content='<?xml version="1.0" encoding="UTF-8"?><Response></Response>',
        media_type="application/xml",
    )


@app.post("/webhooks/whatsapp/status", tags=["webhooks"])
async def whatsapp_status_webhook(request: Request):
    """
    Receive Twilio delivery status callbacks (sent → delivered → read → failed).
    Updates the delivery_status on the corresponding message row.
    """
    from production.database.queries import update_delivery_status

    form_data = await request.form()
    msg_sid   = form_data.get("MessageSid")
    status    = form_data.get("MessageStatus")

    if msg_sid and status:
        try:
            await update_delivery_status(msg_sid, status)
            logger.debug("Delivery status updated: sid=%s status=%s", msg_sid, status)
        except Exception as e:
            logger.error("Failed to update delivery status: %s", e)

    return {"status": "received"}


# ── Customer lookup ───────────────────────────────────────────────────────────

@app.get("/customers/lookup", tags=["customers"])
async def lookup_customer(email: str = None, phone: str = None):
    """
    Look up a customer by email or phone number across all channels.
    At least one of email or phone must be provided.
    """
    from production.database.queries import (
        find_customer_by_email,
        find_customer_by_phone,
        get_customer_full_history,
    )

    if not email and not phone:
        raise HTTPException(
            status_code=400,
            detail="Provide at least one of: email, phone",
        )

    customer = None
    if email:
        customer = await find_customer_by_email(email)
    if not customer and phone:
        customer = await find_customer_by_phone(phone)

    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    history = await get_customer_full_history(str(customer["id"]))

    # Count unique conversations
    conv_ids = {m["conversation_started"] for m in history if "conversation_started" in m}

    return {
        "customer_id":        str(customer["id"]),
        "email":              customer.get("email"),
        "phone":              customer.get("phone"),
        "name":               customer.get("name"),
        "plan":               customer.get("plan", "starter"),
        "total_conversations": len(conv_ids),
        "recent_messages":    history[:5],   # last 5 messages for preview
    }


# ── Conversation history ──────────────────────────────────────────────────────

@app.get("/conversations/{conversation_id}", tags=["conversations"])
async def get_conversation(conversation_id: str):
    """
    Return the full message history for a conversation, ordered oldest first.
    Includes channel metadata per message for cross-channel context.
    """
    from production.database.queries import load_conversation_history

    history = await load_conversation_history(conversation_id)
    if not history:
        raise HTTPException(status_code=404, detail="Conversation not found")

    return {
        "conversation_id": conversation_id,
        "messages":        history,
        "total_messages":  len(history),
    }


# ── Channel metrics ───────────────────────────────────────────────────────────

@app.get("/metrics/channels", tags=["ops"])
async def get_channel_metrics(hours: int = 24):
    """
    Return per-channel performance metrics for the last N hours (default 24).
    Used by monitoring dashboards and the scoring rubric validation.
    """
    from production.database.queries import get_channel_metrics

    rows = await get_channel_metrics(hours=hours)
    return {
        row["channel"]: {
            "total_conversations": row["total_conversations"],
            "avg_sentiment":       float(row["avg_sentiment"]) if row["avg_sentiment"] else None,
            "escalations":         row["escalations"],
            "resolved":            row["resolved"],
        }
        for row in rows
    }
