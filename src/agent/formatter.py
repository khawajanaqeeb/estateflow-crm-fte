"""
Channel-aware response formatter.
Takes a raw AI-generated response and formats it correctly for the target channel.
"""

import re
import textwrap
from .models import Channel

# Maximum response lengths per channel
MAX_WORDS = {
    Channel.EMAIL: 500,
    Channel.WEB_FORM: 300,
    Channel.WHATSAPP: 80,   # ~160 chars preferred, generous word count
}

WHATSAPP_MAX_CHARS = 300    # hard cap for WhatsApp messages


def format_for_channel(
    response: str,
    channel: Channel,
    customer_name: str = "",
    agent_sign_off: bool = True,
) -> str:
    """
    Format a raw response for the given channel.
    """
    if channel == Channel.EMAIL:
        return _format_email(response, customer_name)
    elif channel == Channel.WHATSAPP:
        return _format_whatsapp(response)
    elif channel == Channel.WEB_FORM:
        return _format_web_form(response, customer_name)
    return response


def _format_email(response: str, customer_name: str = "") -> str:
    """
    Email: formal, detailed. Add greeting and signature if not already present.
    """
    first_name = customer_name.split()[0] if customer_name else ""
    lines = response.strip().splitlines()

    # Check if response already has a greeting
    has_greeting = lines and re.match(r'^(hi|hello|dear)\b', lines[0], re.IGNORECASE)

    # Check if response already has a sign-off
    has_signoff = len(lines) > 1 and re.match(
        r'^(best|regards|thanks|sincerely|warm)', lines[-1], re.IGNORECASE
    )

    parts = []

    if not has_greeting:
        greeting = f"Hi {first_name}," if first_name else "Hi there,"
        parts.append(greeting)
        parts.append("")

    parts.append(response.strip())

    if not has_signoff:
        parts.append("")
        parts.append("Let me know if you have any other questions.")
        parts.append("")
        parts.append("Best,")
        parts.append("EstateFlow Customer Success")
        parts.append("support@estateflow.io")

    return "\n".join(parts)


def _format_whatsapp(response: str) -> str:
    """
    WhatsApp: concise, plain text, no markdown, no signature.
    Strip formatting, trim length, break into short paragraphs.
    """
    # Strip markdown formatting
    text = re.sub(r'\*\*(.*?)\*\*', r'\1', response)   # bold
    text = re.sub(r'\*(.*?)\*', r'\1', text)            # italic
    text = re.sub(r'#{1,6}\s*', '', text)               # headers
    text = re.sub(r'`(.*?)`', r'\1', text)              # inline code

    # Trim to word limit
    words = text.split()
    if len(words) > MAX_WORDS[Channel.WHATSAPP]:
        text = " ".join(words[:MAX_WORDS[Channel.WHATSAPP]])
        # cut at last sentence boundary
        last_period = max(text.rfind('.'), text.rfind('!'), text.rfind('?'))
        if last_period > len(text) // 2:
            text = text[:last_period + 1]

    # Hard character cap
    if len(text) > WHATSAPP_MAX_CHARS:
        text = text[:WHATSAPP_MAX_CHARS].rsplit(' ', 1)[0] + "..."

    return text.strip()


def _format_web_form(response: str, customer_name: str = "") -> str:
    """
    Web form: semi-formal, structured. Brief greeting, no full signature.
    """
    first_name = customer_name.split()[0] if customer_name else ""
    lines = response.strip().splitlines()

    has_greeting = lines and re.match(r'^(hi|hello|dear)\b', lines[0], re.IGNORECASE)

    parts = []

    if not has_greeting:
        greeting = f"Hi {first_name}," if first_name else "Hi there,"
        parts.append(greeting)
        parts.append("")

    parts.append(response.strip())

    if not any(re.match(r'^(let me know|feel free|reach out|hope that)', l, re.IGNORECASE)
               for l in lines[-3:]):
        parts.append("")
        parts.append("Let me know if you need anything else.")

    return "\n".join(parts)


def strip_markdown(text: str) -> str:
    """Remove all markdown formatting — used for WhatsApp."""
    text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
    text = re.sub(r'\*(.*?)\*', r'\1', text)
    text = re.sub(r'#{1,6}\s*', '', text)
    text = re.sub(r'`{1,3}.*?`{1,3}', '', text, flags=re.DOTALL)
    text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
    return text.strip()
