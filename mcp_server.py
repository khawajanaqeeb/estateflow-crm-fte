"""
EstateFlow Customer Success FTE — MCP Server

Exposes the prototype's capabilities as MCP tools that any MCP-compatible
client (Claude Desktop, OpenAI Agents SDK, etc.) can call.

Tools exposed:
  1. search_knowledge_base      — search product docs
  2. create_ticket              — log a new support interaction
  3. get_customer_history       — full cross-channel history for a customer
  4. get_session_context        — active conversation memory for a customer
  5. escalate_to_human          — trigger escalation with full context
  6. send_response              — deliver a reply via the correct channel
  7. update_ticket_status       — mark a ticket resolved / pending
  8. detect_upsell_signal       — check if a message implies a plan upgrade need
  9. analyze_sentiment          — classify customer sentiment

Run with:
  venv/bin/python mcp_server.py
Or via Claude Desktop config (see README).
"""

import asyncio
import json
import sys
import os
from enum import Enum
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# ── Bootstrap project path ────────────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(__file__))

from src.agent.customer_store import CustomerStore
from src.agent.memory import MemoryStore
from src.agent import knowledge_base
from src.agent import escalation as esc_engine
from src.agent.models import Channel, Priority, Sentiment, TicketStatus

# ── Shared state (singleton for the server lifetime) ─────────────────────────
store = CustomerStore()
memory = MemoryStore()

# ── Channel enum ──────────────────────────────────────────────────────────────
class ChannelEnum(str, Enum):
    EMAIL = "email"
    WHATSAPP = "whatsapp"
    WEB_FORM = "web_form"

# ── Server init ───────────────────────────────────────────────────────────────
server = Server("estateflow-customer-success-fte")


# ─────────────────────────────────────────────────────────────────────────────
# Tool 1 — search_knowledge_base
# ─────────────────────────────────────────────────────────────────────────────
@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="search_knowledge_base",
            description=(
                "Search EstateFlow's product documentation for information relevant to a customer query. "
                "Use this whenever a customer asks how to use a feature, reports a problem, "
                "or needs guidance on any aspect of EstateFlow CRM. "
                "Returns the top matching documentation sections with relevance scores."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The customer's question or topic to search for"
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of documentation sections to return (default: 3)",
                        "default": 3
                    }
                },
                "required": ["query"]
            }
        ),

        # ── Tool 2 ────────────────────────────────────────────────────────────
        Tool(
            name="create_ticket",
            description=(
                "Create a support ticket to log a customer interaction. "
                "ALWAYS call this before sending any response to a customer. "
                "The ticket tracks the issue, channel, priority, and customer identity."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "customer_id": {
                        "type": "string",
                        "description": "The customer's unique ID (from identify_customer or get_customer_history)"
                    },
                    "issue": {
                        "type": "string",
                        "description": "A brief description of the customer's issue (max 120 characters)"
                    },
                    "priority": {
                        "type": "string",
                        "enum": ["low", "medium", "high", "urgent"],
                        "description": "Ticket priority based on issue severity"
                    },
                    "channel": {
                        "type": "string",
                        "enum": ["email", "whatsapp", "web_form"],
                        "description": "The channel through which the customer contacted support"
                    }
                },
                "required": ["customer_id", "issue", "priority", "channel"]
            }
        ),

        # ── Tool 3 ────────────────────────────────────────────────────────────
        Tool(
            name="get_customer_history",
            description=(
                "Retrieve a customer's full interaction history across ALL channels (email, WhatsApp, web form). "
                "Use this at the start of any conversation to check if this is a returning customer "
                "and to understand prior issues, unresolved tickets, and escalation history. "
                "Pass either email or phone to identify the customer."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "email": {
                        "type": "string",
                        "description": "Customer's email address (primary identifier)"
                    },
                    "phone": {
                        "type": "string",
                        "description": "Customer's phone number — use for WhatsApp contacts (e.g. +14085559021)"
                    }
                },
                "required": []
            }
        ),

        # ── Tool 4 ────────────────────────────────────────────────────────────
        Tool(
            name="get_session_context",
            description=(
                "Retrieve the active conversation session context for a customer. "
                "Returns the prior turns in the current conversation, including messages exchanged "
                "across channels, sentiment trend, and topics already covered. "
                "Use this when a customer sends a follow-up message to avoid making them repeat themselves."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "customer_id": {
                        "type": "string",
                        "description": "The customer's unique ID"
                    }
                },
                "required": ["customer_id"]
            }
        ),

        # ── Tool 5 ────────────────────────────────────────────────────────────
        Tool(
            name="escalate_to_human",
            description=(
                "Escalate a ticket to a human agent. Call this when: "
                "the customer requests a human, sentiment is very negative, "
                "a billing dispute or refund is requested, data loss is reported, "
                "a security incident is suspected, or a technical bug persists after 2 troubleshooting attempts. "
                "Always include the full context summary so the human agent doesn't ask the customer to repeat themselves."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "ticket_id": {
                        "type": "string",
                        "description": "The ticket ID to escalate"
                    },
                    "reason": {
                        "type": "string",
                        "description": "Clear explanation of why this is being escalated"
                    },
                    "level": {
                        "type": "string",
                        "enum": ["L1", "L2", "L3", "L4"],
                        "description": "Escalation level: L1=next day, L2=4hrs, L3=1hr, L4=immediate"
                    },
                    "context_summary": {
                        "type": "string",
                        "description": "Summary of the conversation so far — what the customer said, what was tried"
                    },
                    "rule_triggered": {
                        "type": "string",
                        "description": "Which escalation rule triggered this (e.g. Rule 4 — Billing Dispute)"
                    }
                },
                "required": ["ticket_id", "reason", "level", "context_summary"]
            }
        ),

        # ── Tool 6 ────────────────────────────────────────────────────────────
        Tool(
            name="send_response",
            description=(
                "Record and deliver a response to a customer via the appropriate channel. "
                "The response text will be formatted automatically for the target channel "
                "(email gets a greeting and signature, WhatsApp is trimmed to plain text). "
                "Call this after generating your response and checking escalation."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "ticket_id": {
                        "type": "string",
                        "description": "The ticket ID this response belongs to"
                    },
                    "message": {
                        "type": "string",
                        "description": "The response text to send to the customer"
                    },
                    "channel": {
                        "type": "string",
                        "enum": ["email", "whatsapp", "web_form"],
                        "description": "The channel to send the response through"
                    },
                    "customer_name": {
                        "type": "string",
                        "description": "Customer's name for personalizing the greeting"
                    }
                },
                "required": ["ticket_id", "message", "channel"]
            }
        ),

        # ── Tool 7 ────────────────────────────────────────────────────────────
        Tool(
            name="update_ticket_status",
            description=(
                "Update the status of an existing ticket. "
                "Mark as 'resolved' once the customer's issue is fully addressed. "
                "Mark as 'pending' if waiting for customer follow-up. "
                "Always resolve tickets before closing the conversation."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "ticket_id": {
                        "type": "string",
                        "description": "The ticket ID to update"
                    },
                    "status": {
                        "type": "string",
                        "enum": ["resolved", "pending", "open"],
                        "description": "New status for the ticket"
                    },
                    "resolution_notes": {
                        "type": "string",
                        "description": "Brief notes on how the issue was resolved"
                    }
                },
                "required": ["ticket_id", "status"]
            }
        ),

        # ── Tool 8 ────────────────────────────────────────────────────────────
        Tool(
            name="detect_upsell_signal",
            description=(
                "Check if a customer's message contains a signal that they need a feature "
                "only available on a higher plan. Use this after classifying the customer's intent. "
                "If an upsell signal is detected, answer the question fully first, then "
                "mention the upgrade path in one sentence — do not hard-sell."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "message": {
                        "type": "string",
                        "description": "The customer's message to analyze"
                    },
                    "current_plan": {
                        "type": "string",
                        "enum": ["starter", "professional", "team", "brokerage"],
                        "description": "The customer's current plan"
                    }
                },
                "required": ["message", "current_plan"]
            }
        ),

        # ── Tool 9 ────────────────────────────────────────────────────────────
        Tool(
            name="analyze_sentiment",
            description=(
                "Analyze the sentiment of a customer message. "
                "Use this on every incoming message to track emotional state and "
                "inform escalation decisions. Sentiment is also stored in session memory "
                "to detect worsening trends across a conversation."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "message": {
                        "type": "string",
                        "description": "The customer message to analyze"
                    }
                },
                "required": ["message"]
            }
        ),
    ]


# ─────────────────────────────────────────────────────────────────────────────
# Tool call handler
# ─────────────────────────────────────────────────────────────────────────────
@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:

    # ── Tool 1: search_knowledge_base ─────────────────────────────────────────
    if name == "search_knowledge_base":
        query = arguments["query"]
        max_results = arguments.get("max_results", 3)
        results = knowledge_base.search(query, max_results=max_results)
        if not results:
            text = "No relevant documentation found for this query."
        else:
            parts = []
            for r in results:
                parts.append(
                    f"**{r.section}** (relevance: {r.score})\n{r.content}"
                )
            text = "\n\n---\n\n".join(parts)
        return [TextContent(type="text", text=text)]

    # ── Tool 2: create_ticket ─────────────────────────────────────────────────
    elif name == "create_ticket":
        channel_map = {
            "email": Channel.EMAIL,
            "whatsapp": Channel.WHATSAPP,
            "web_form": Channel.WEB_FORM,
        }
        priority_map = {
            "low": Priority.LOW,
            "medium": Priority.MEDIUM,
            "high": Priority.HIGH,
            "urgent": Priority.URGENT,
        }
        ticket = store.create_ticket(
            customer_id=arguments["customer_id"],
            channel=channel_map[arguments["channel"]],
            issue_summary=arguments["issue"][:120],
            priority=priority_map[arguments["priority"]],
        )
        result = {
            "ticket_id": ticket.ticket_id,
            "customer_id": ticket.customer_id,
            "channel": ticket.channel.value,
            "priority": ticket.priority.value,
            "status": ticket.status.value,
            "created_at": ticket.created_at.isoformat(),
        }
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    # ── Tool 3: get_customer_history ──────────────────────────────────────────
    elif name == "get_customer_history":
        email = arguments.get("email")
        phone = arguments.get("phone")

        if not email and not phone:
            return [TextContent(type="text", text="Error: provide at least one of email or phone.")]

        # identify customer
        customer = store.identify_customer(email=email, phone=phone)
        tickets = store.get_customer_history(customer.customer_id)
        sessions = memory.get_all_sessions(customer.customer_id)

        if not tickets and not sessions:
            return [TextContent(
                type="text",
                text=json.dumps({
                    "customer_id": customer.customer_id,
                    "status": "new_customer",
                    "message": "No prior interactions found.",
                }, indent=2)
            )]

        ticket_data = []
        for t in tickets[:10]:
            ticket_data.append({
                "ticket_id": t.ticket_id,
                "channel": t.channel.value,
                "issue": t.issue_summary,
                "priority": t.priority.value,
                "status": t.status.value,
                "escalated": t.status.value == "escalated",
                "escalation_reason": t.escalation_reason,
                "sentiment_trend": [s.value for s in t.sentiment_trend],
                "topics": t.topics,
                "created_at": t.created_at.isoformat(),
            })

        session_data = []
        for s in sessions[-5:]:
            session_data.append({
                "session_id": s.session_id,
                "status": s.status,
                "channels": [c.value for c in s.channels_used],
                "topics": s.topics_covered,
                "turns": len(s.turns),
                "sentiment_trend": [sv.value for sv in s.sentiment_trend],
                "created_at": s.created_at.isoformat(),
            })

        result = {
            "customer_id": customer.customer_id,
            "email": customer.email,
            "phone": customer.phone,
            "name": customer.name,
            "plan": customer.plan,
            "channels_used": [c.value for c in customer.channels_used],
            "total_tickets": len(tickets),
            "recent_tickets": ticket_data,
            "sessions": session_data,
            "memory_summary": memory.get_customer_context(customer.customer_id),
        }
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    # ── Tool 4: get_session_context ───────────────────────────────────────────
    elif name == "get_session_context":
        customer_id = arguments["customer_id"]
        sessions = memory.get_all_sessions(customer_id)
        active = [s for s in sessions if s.status == "open" and not s.is_expired()]

        if not active:
            return [TextContent(
                type="text",
                text=json.dumps({
                    "customer_id": customer_id,
                    "active_session": None,
                    "message": "No active session. This is the start of a new conversation.",
                }, indent=2)
            )]

        s = active[-1]
        result = {
            "session_id": s.session_id,
            "customer_id": customer_id,
            "status": s.status,
            "original_channel": s.original_channel.value,
            "channels_used": [c.value for c in s.channels_used],
            "turns": len(s.turns),
            "topics_covered": s.topics_covered,
            "sentiment_trend": [sv.value for sv in s.sentiment_trend],
            "sentiment_worsening": s.sentiment_worsening(),
            "channel_switched": len(s.channels_used) > 1,
            "context": s.to_context_string(max_turns=5),
        }
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    # ── Tool 5: escalate_to_human ─────────────────────────────────────────────
    elif name == "escalate_to_human":
        ticket_id = arguments["ticket_id"]
        reason = arguments["reason"]
        level = arguments["level"]
        context_summary = arguments["context_summary"]
        rule_triggered = arguments.get("rule_triggered", "Manual escalation")

        ticket = store.get_ticket(ticket_id)
        if not ticket:
            return [TextContent(type="text", text=f"Error: ticket {ticket_id} not found.")]

        store.escalate_ticket(ticket_id, reason=reason, level=level)

        # also update memory session
        sessions = memory.get_all_sessions(ticket.customer_id)
        for s in sessions:
            if s.status == "open":
                memory.escalate(s.session_id, reason=reason)

        escalation_record = {
            "escalation_id": f"ESC-{ticket_id}",
            "ticket_id": ticket_id,
            "customer_id": ticket.customer_id,
            "level": level,
            "reason": reason,
            "rule_triggered": rule_triggered,
            "context_summary": context_summary,
            "routed_to": _escalation_team(level, reason),
            "sla": _sla_for_level(level),
            "status": "escalated",
        }
        return [TextContent(type="text", text=json.dumps(escalation_record, indent=2))]

    # ── Tool 6: send_response ─────────────────────────────────────────────────
    elif name == "send_response":
        from src.agent import formatter
        from src.agent.models import Message

        ticket_id = arguments["ticket_id"]
        message_text = arguments["message"]
        channel_str = arguments["channel"]
        customer_name = arguments.get("customer_name", "")

        channel_map = {
            "email": Channel.EMAIL,
            "whatsapp": Channel.WHATSAPP,
            "web_form": Channel.WEB_FORM,
        }
        channel = channel_map[channel_str]

        formatted = formatter.format_for_channel(
            response=message_text,
            channel=channel,
            customer_name=customer_name,
        )

        ticket = store.get_ticket(ticket_id)
        if ticket:
            store.add_message(ticket_id, Message(
                role="agent",
                content=formatted,
                channel=channel,
            ))

        # In prototype: simulated delivery
        # In Stage 2: calls Gmail API / Twilio / web socket
        delivery_result = {
            "ticket_id": ticket_id,
            "channel": channel_str,
            "status": "delivered",
            "formatted_message": formatted,
            "delivery_note": f"[PROTOTYPE] Message logged. In production, sent via {channel_str} API.",
        }
        return [TextContent(type="text", text=json.dumps(delivery_result, indent=2))]

    # ── Tool 7: update_ticket_status ──────────────────────────────────────────
    elif name == "update_ticket_status":
        ticket_id = arguments["ticket_id"]
        status_str = arguments["status"]
        notes = arguments.get("resolution_notes", "")

        status_map = {
            "resolved": TicketStatus.RESOLVED,
            "pending": TicketStatus.PENDING,
            "open": TicketStatus.OPEN,
        }
        status = status_map.get(status_str, TicketStatus.OPEN)
        store.update_status(ticket_id, status, resolution_notes=notes)

        ticket = store.get_ticket(ticket_id)
        if not ticket:
            return [TextContent(type="text", text=f"Error: ticket {ticket_id} not found.")]

        result = {
            "ticket_id": ticket_id,
            "status": status.value,
            "resolution_notes": notes,
            "updated_at": ticket.updated_at.isoformat(),
        }
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    # ── Tool 8: detect_upsell_signal ──────────────────────────────────────────
    elif name == "detect_upsell_signal":
        message = arguments["message"]
        plan = arguments["current_plan"]

        is_upsell, target_plan = esc_engine.detect_upsell_signal(message, plan)

        plan_prices = {
            "starter": "$39/mo",
            "professional": "$79/mo",
            "team": "$149/mo",
            "brokerage": "Custom pricing",
        }

        result = {
            "upsell_signal_detected": is_upsell,
            "current_plan": plan,
            "target_plan": target_plan,
            "target_plan_price": plan_prices.get(target_plan) if target_plan else None,
            "guidance": (
                f"Answer the question fully first. Then mention: "
                f"'This feature is available on our {target_plan.title()} plan ({plan_prices.get(target_plan)}). "
                f"You can upgrade anytime from Settings → Billing.'"
            ) if is_upsell else "No upsell action needed.",
        }
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    # ── Tool 9: analyze_sentiment ─────────────────────────────────────────────
    elif name == "analyze_sentiment":
        from src.agent.agent import _quick_sentiment

        message = arguments["message"]
        sentiment = _quick_sentiment(message)

        negative_states = {Sentiment.FRUSTRATED, Sentiment.NEGATIVE, Sentiment.ANGRY}
        result = {
            "sentiment": sentiment.value,
            "is_negative": sentiment in negative_states,
            "escalation_advised": sentiment == Sentiment.ANGRY,
            "guidance": {
                Sentiment.POSITIVE.value: "Customer is in a positive state. Answer directly and helpfully.",
                Sentiment.NEUTRAL.value: "Customer is neutral. Answer clearly and professionally.",
                Sentiment.NEGATIVE.value: "Customer is dissatisfied. Acknowledge briefly, then solve.",
                Sentiment.FRUSTRATED.value: "Customer is frustrated. One empathy sentence, then solve fast.",
                Sentiment.ANGRY.value: "Customer is angry. Acknowledge, do not argue, escalate if needed.",
            }.get(sentiment.value, "Respond professionally."),
        }
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    else:
        return [TextContent(type="text", text=f"Unknown tool: {name}")]


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _escalation_team(level: str, reason: str) -> str:
    if "billing" in reason.lower() or "charge" in reason.lower() or "refund" in reason.lower():
        return "billing@estateflow.io"
    if "security" in reason.lower() or "unauthorized" in reason.lower():
        return "security@estateflow.io"
    if "legal" in reason.lower() or "compliance" in reason.lower():
        return "privacy@estateflow.io"
    if "pricing" in reason.lower() or "discount" in reason.lower():
        return "sales@estateflow.io"
    return "team@estateflow.io"


def _sla_for_level(level: str) -> str:
    return {
        "L1": "Next business day",
        "L2": "Within 4 business hours",
        "L3": "Within 1 hour",
        "L4": "Immediate (24/7 on-call)",
    }.get(level, "Next business day")


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────
async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )

if __name__ == "__main__":
    asyncio.run(main())
