"""
EstateFlow Customer Success FTE — WhatsApp Channel Handler (via Twilio)
Handles inbound WhatsApp messages via Twilio webhook and sends replies.

Env vars:
  TWILIO_ACCOUNT_SID        — Twilio account SID
  TWILIO_AUTH_TOKEN         — Twilio auth token
  TWILIO_WHATSAPP_NUMBER    — Sender number e.g. "whatsapp:+14155238886"
"""

import logging
import os
from datetime import datetime, timezone
from typing import Optional

from fastapi import Request

logger = logging.getLogger(__name__)

# WhatsApp hard limit per message (Twilio)
WHATSAPP_MAX_CHARS = 1600


class WhatsAppHandler:
    """
    Wraps the Twilio REST client for inbound webhook processing and
    outbound WhatsApp message delivery.
    Lazy-initializes the Twilio client to avoid import errors during tests.
    """

    def __init__(self) -> None:
        self._account_sid = os.getenv("TWILIO_ACCOUNT_SID", "")
        self._auth_token  = os.getenv("TWILIO_AUTH_TOKEN", "")
        self._from_number = os.getenv("TWILIO_WHATSAPP_NUMBER", "")
        self._client    = None
        self._validator = None

    def _get_client(self):
        if self._client is None:
            from twilio.rest import Client
            self._client = Client(self._account_sid, self._auth_token)
        return self._client

    def _get_validator(self):
        if self._validator is None:
            from twilio.request_validator import RequestValidator
            self._validator = RequestValidator(self._auth_token)
        return self._validator

    # ── Inbound ───────────────────────────────────────────────────────────────

    async def validate_webhook(self, request: Request) -> bool:
        """
        Validate the X-Twilio-Signature header to ensure the request is
        genuinely from Twilio and not a spoofed call.

        Returns True if valid, False otherwise.
        """
        if not self._auth_token:
            logger.warning("TWILIO_AUTH_TOKEN not set — skipping webhook validation")
            return True  # Allow in development; enforce in production

        signature = request.headers.get("X-Twilio-Signature", "")
        url        = str(request.url)
        form_data  = await request.form()
        params     = dict(form_data)

        return self._get_validator().validate(url, params, signature)

    async def process_webhook(self, form_data: dict) -> dict:
        """
        Parse an incoming Twilio WhatsApp webhook form payload into a
        normalized message dict for publishing to Kafka.

        Args:
            form_data: Dict of form fields from the Twilio POST request.

        Returns:
            Normalized message dict.
        """
        raw_from = form_data.get("From", "")
        # Strip "whatsapp:" prefix that Twilio adds
        phone = raw_from.replace("whatsapp:", "").strip()

        return {
            "channel":            "whatsapp",
            "channel_message_id": form_data.get("MessageSid"),
            "customer_phone":     phone,
            "customer_name":      form_data.get("ProfileName", ""),
            "content":            form_data.get("Body", "").strip(),
            "received_at":        datetime.now(timezone.utc).isoformat(),
            "metadata": {
                "wa_id":      form_data.get("WaId", ""),
                "num_media":  form_data.get("NumMedia", "0"),
                "status":     form_data.get("SmsStatus", ""),
            },
        }

    # ── Outbound ──────────────────────────────────────────────────────────────

    async def send_message(self, to_phone: str, body: str) -> dict:
        """
        Send a WhatsApp message via Twilio.

        Automatically adds the "whatsapp:" prefix if missing.
        If the body exceeds WHATSAPP_MAX_CHARS it is split into multiple
        messages via split_message().

        Args:
            to_phone: Recipient phone in E.164 or "whatsapp:+E164" format.
            body:     Plain-text message body (markdown already stripped).

        Returns:
            {"channel_message_id": str, "delivery_status": str}
        """
        client = self._get_client()

        if not to_phone.startswith("whatsapp:"):
            to_phone = f"whatsapp:{to_phone}"

        if not self._from_number:
            logger.error("TWILIO_WHATSAPP_NUMBER is not configured")
            return {"channel_message_id": None, "delivery_status": "failed"}

        parts = self.split_message(body)
        last_result: dict = {"channel_message_id": None, "delivery_status": "failed"}

        for part in parts:
            try:
                msg = client.messages.create(
                    body=part,
                    from_=self._from_number,
                    to=to_phone,
                )
                last_result = {
                    "channel_message_id": msg.sid,
                    "delivery_status":    msg.status,  # queued|sent|delivered|failed
                }
                logger.info("WhatsApp sent: sid=%s to=%s", msg.sid, to_phone)
            except Exception as e:
                logger.error("Twilio send failed to %s: %s", to_phone, e)
                last_result = {"channel_message_id": None, "delivery_status": "failed"}

        return last_result

    # ── Helpers ───────────────────────────────────────────────────────────────

    def split_message(self, body: str, max_length: int = WHATSAPP_MAX_CHARS) -> list[str]:
        """
        Split a long message into multiple parts that each fit within
        max_length characters. Splits on sentence boundaries when possible.

        Args:
            body:       Full message text.
            max_length: Character limit per part (default: 1600).

        Returns:
            List of message strings (usually just one).
        """
        if len(body) <= max_length:
            return [body]

        parts: list[str] = []
        remaining = body

        while remaining:
            if len(remaining) <= max_length:
                parts.append(remaining)
                break

            chunk = remaining[:max_length]

            # Prefer sentence boundary
            cut = max(chunk.rfind(". "), chunk.rfind("! "), chunk.rfind("? "))
            if cut == -1 or cut < max_length // 2:
                # Fall back to word boundary
                cut = chunk.rfind(" ")
            if cut == -1:
                cut = max_length

            parts.append(remaining[:cut + 1].strip())
            remaining = remaining[cut + 1:].strip()

        return parts
