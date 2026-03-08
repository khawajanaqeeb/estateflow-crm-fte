"""
EstateFlow Customer Success FTE — Gmail Channel Handler
Handles inbound Gmail messages via Google Pub/Sub push notifications
and sends replies via the Gmail API.

Setup required:
  1. Enable Gmail API and Pub/Sub in Google Cloud Console.
  2. Create a service account and download credentials JSON.
  3. Set GMAIL_CREDENTIALS env var to the path of credentials JSON.
  4. Run setup_push_notifications() once to register the Pub/Sub topic.

Env vars:
  GMAIL_CREDENTIALS   — path to OAuth2 credentials JSON file
  GMAIL_USER          — Gmail address to watch (default: "me")
"""

import base64
import json
import logging
import os
import re
from datetime import datetime, timezone
from email.mime.text import MIMEText
from typing import Optional

logger = logging.getLogger(__name__)


class GmailHandler:
    """
    Wraps the Gmail API for inbound message parsing and outbound reply sending.
    Lazy-initializes the API client to avoid import errors when credentials
    are not configured (e.g., during unit tests).
    """

    def __init__(self) -> None:
        self._service = None
        self._credentials_path = os.getenv("GMAIL_CREDENTIALS", "")
        self._user = os.getenv("GMAIL_USER", "me")

    def _get_service(self):
        """Build and cache the Gmail API service client."""
        if self._service is not None:
            return self._service

        if not self._credentials_path or not os.path.exists(self._credentials_path):
            raise RuntimeError(
                "GMAIL_CREDENTIALS env var must point to a valid credentials JSON file. "
                f"Got: '{self._credentials_path}'"
            )

        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build

        creds = Credentials.from_authorized_user_file(
            self._credentials_path,
            scopes=["https://www.googleapis.com/auth/gmail.modify"],
        )
        self._service = build("gmail", "v1", credentials=creds)
        return self._service

    # ── Inbound ───────────────────────────────────────────────────────────────

    async def setup_push_notifications(self, pubsub_topic: str) -> dict:
        """
        Register Gmail push notifications to a Google Pub/Sub topic.
        Call once during initial deployment or when the watch expires (every 7 days).

        Args:
            pubsub_topic: Full Pub/Sub topic name,
                          e.g. "projects/my-project/topics/gmail-push"
        Returns:
            Gmail watch response dict with historyId and expiration.
        """
        svc = self._get_service()
        response = svc.users().watch(
            userId=self._user,
            body={
                "labelIds": ["INBOX"],
                "topicName": pubsub_topic,
                "labelFilterAction": "include",
            },
        ).execute()
        logger.info("Gmail watch registered: historyId=%s", response.get("historyId"))
        return response

    async def process_notification(self, pubsub_message: dict) -> list[dict]:
        """
        Process an incoming Pub/Sub push notification from Gmail.
        Returns a list of normalized message dicts ready for Kafka.

        Args:
            pubsub_message: The decoded Pub/Sub message body (JSON dict).
        """
        history_id = pubsub_message.get("historyId")
        if not history_id:
            logger.warning("Pub/Sub notification missing historyId")
            return []

        svc = self._get_service()
        try:
            history = svc.users().history().list(
                userId=self._user,
                startHistoryId=history_id,
                historyTypes=["messageAdded"],
            ).execute()
        except Exception as e:
            logger.error("Gmail history fetch failed: %s", e)
            return []

        messages = []
        for record in history.get("history", []):
            for msg_added in record.get("messagesAdded", []):
                msg_id = msg_added["message"]["id"]
                try:
                    normalized = await self.get_message(msg_id)
                    if normalized:
                        messages.append(normalized)
                except Exception as e:
                    logger.error("Failed to fetch Gmail message %s: %s", msg_id, e)

        return messages

    async def get_message(self, message_id: str) -> Optional[dict]:
        """
        Fetch a single Gmail message and return a normalized dict for Kafka.

        Returns None if the message is from EstateFlow itself (avoid loops).
        """
        svc = self._get_service()
        msg = svc.users().messages().get(
            userId=self._user,
            id=message_id,
            format="full",
        ).execute()

        headers = {h["name"].lower(): h["value"] for h in msg["payload"]["headers"]}
        from_header = headers.get("from", "")
        customer_email = self._extract_email(from_header)

        # Avoid processing our own outbound messages
        if customer_email and "estateflow.io" in customer_email:
            return None

        body = self._extract_body(msg["payload"])

        return {
            "channel":            "email",
            "channel_message_id": message_id,
            "customer_email":     customer_email,
            "customer_name":      self._extract_name(from_header),
            "subject":            headers.get("subject", ""),
            "content":            body,
            "received_at":        datetime.now(timezone.utc).isoformat(),
            "thread_id":          msg.get("threadId"),
            "metadata": {
                "headers": dict(headers),
                "labels":  msg.get("labelIds", []),
            },
        }

    # ── Outbound ──────────────────────────────────────────────────────────────

    async def send_reply(
        self,
        to_email: str,
        subject: str,
        body: str,
        thread_id: Optional[str] = None,
    ) -> dict:
        """
        Send an email reply via Gmail API.

        Args:
            to_email:  Recipient email address.
            subject:   Email subject (Re: prefix added automatically if missing).
            body:      Plain-text body (already formatted by formatter.py).
            thread_id: Gmail thread ID to keep replies in the same thread.

        Returns:
            {"channel_message_id": str, "delivery_status": "sent"}
        """
        svc = self._get_service()

        reply_subject = subject if subject.lower().startswith("re:") else f"Re: {subject}"
        mime_msg = MIMEText(body, "plain", "utf-8")
        mime_msg["to"] = to_email
        mime_msg["subject"] = reply_subject

        raw = base64.urlsafe_b64encode(mime_msg.as_bytes()).decode("utf-8")
        send_body: dict = {"raw": raw}
        if thread_id:
            send_body["threadId"] = thread_id

        try:
            result = svc.users().messages().send(
                userId=self._user, body=send_body
            ).execute()
            logger.info("Gmail reply sent: id=%s to=%s", result["id"], to_email)
            return {"channel_message_id": result["id"], "delivery_status": "sent"}
        except Exception as e:
            logger.error("Gmail send failed to %s: %s", to_email, e)
            return {"channel_message_id": None, "delivery_status": "failed"}

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _extract_body(self, payload: dict) -> str:
        """Recursively extract plain-text body from a Gmail message payload."""
        # Direct body data
        if "body" in payload and payload["body"].get("data"):
            return base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8", errors="replace")

        # Multipart — prefer text/plain
        for part in payload.get("parts", []):
            if part.get("mimeType") == "text/plain" and part["body"].get("data"):
                return base64.urlsafe_b64decode(part["body"]["data"]).decode("utf-8", errors="replace")

        # Fall back to first available part
        for part in payload.get("parts", []):
            result = self._extract_body(part)
            if result:
                return result

        return ""

    def _extract_email(self, from_header: str) -> str:
        """Extract bare email address from a 'From' header."""
        match = re.search(r"<(.+?)>", from_header)
        if match:
            return match.group(1).strip().lower()
        return from_header.strip().lower()

    def _extract_name(self, from_header: str) -> str:
        """Extract display name from a 'From' header."""
        match = re.match(r'^"?([^"<]+)"?\s*<', from_header)
        if match:
            return match.group(1).strip()
        return ""
