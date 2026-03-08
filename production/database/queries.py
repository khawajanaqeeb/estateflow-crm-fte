"""
EstateFlow Customer Success FTE — Database Query Functions
All asyncpg queries used by production tools and the message worker.
"""

import asyncpg
import os
import json
import logging
from typing import Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# ── Connection pool (singleton) ───────────────────────────────────────────────

_pool: Optional[asyncpg.Pool] = None


async def get_db_pool() -> asyncpg.Pool:
    """Return the shared connection pool, creating it if needed."""
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(
            host=os.getenv("POSTGRES_HOST", "localhost"),
            port=int(os.getenv("POSTGRES_PORT", 5432)),
            database=os.getenv("POSTGRES_DB", "fte_db"),
            user=os.getenv("POSTGRES_USER", "fte_user"),
            password=os.getenv("POSTGRES_PASSWORD", ""),
            min_size=2,
            max_size=10,
        )
    return _pool


async def close_db_pool() -> None:
    """Close the connection pool on shutdown."""
    global _pool
    if _pool:
        await _pool.close()
        _pool = None


# ── Customer queries ──────────────────────────────────────────────────────────

async def find_customer_by_email(email: str) -> Optional[dict]:
    """Return customer row by email, or None."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id, email, phone, name, plan FROM customers WHERE email = $1",
            email,
        )
        return dict(row) if row else None


async def find_customer_by_phone(phone: str) -> Optional[dict]:
    """Return customer by WhatsApp phone number via customer_identifiers."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT c.id, c.email, c.phone, c.name, c.plan
            FROM customers c
            JOIN customer_identifiers ci ON ci.customer_id = c.id
            WHERE ci.identifier_type = 'whatsapp' AND ci.identifier_value = $1
            """,
            phone,
        )
        return dict(row) if row else None


async def create_customer(
    email: Optional[str] = None,
    phone: Optional[str] = None,
    name: Optional[str] = None,
    plan: str = "starter",
) -> str:
    """Insert a new customer. Returns the new customer_id (UUID string)."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        customer_id = await conn.fetchval(
            """
            INSERT INTO customers (email, phone, name, plan)
            VALUES ($1, $2, $3, $4)
            RETURNING id
            """,
            email, phone, name or "", plan,
        )
        return str(customer_id)


async def add_customer_identifier(
    customer_id: str,
    identifier_type: str,
    identifier_value: str,
) -> None:
    """Link an identifier (email/phone/whatsapp) to a customer. Ignores duplicates."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO customer_identifiers (customer_id, identifier_type, identifier_value)
            VALUES ($1, $2, $3)
            ON CONFLICT (identifier_type, identifier_value) DO NOTHING
            """,
            customer_id, identifier_type, identifier_value,
        )


async def get_customer_full_history(customer_id: str) -> list[dict]:
    """
    Return the last 20 messages across all conversations for a customer,
    ordered newest first. Used by get_customer_history tool.
    """
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
                c.initial_channel,
                c.status          AS conversation_status,
                c.started_at      AS conversation_started,
                m.role,
                m.content,
                m.channel,
                m.created_at
            FROM conversations c
            JOIN messages m ON m.conversation_id = c.id
            WHERE c.customer_id = $1
            ORDER BY m.created_at DESC
            LIMIT 20
            """,
            customer_id,
        )
        return [dict(r) for r in rows]


# ── Conversation queries ──────────────────────────────────────────────────────

async def get_active_conversation(customer_id: str) -> Optional[dict]:
    """Return an active conversation started within the last 24 hours, or None."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT id, initial_channel, status, started_at
            FROM conversations
            WHERE customer_id = $1
              AND status = 'active'
              AND started_at > NOW() - INTERVAL '24 hours'
            ORDER BY started_at DESC
            LIMIT 1
            """,
            customer_id,
        )
        return dict(row) if row else None


async def create_conversation(customer_id: str, channel: str) -> str:
    """Insert a new conversation. Returns conversation_id."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        conv_id = await conn.fetchval(
            """
            INSERT INTO conversations (customer_id, initial_channel, status)
            VALUES ($1, $2, 'active')
            RETURNING id
            """,
            customer_id, channel,
        )
        return str(conv_id)


async def update_conversation_status(
    conversation_id: str,
    status: str,
    resolution_type: Optional[str] = None,
    escalated_to: Optional[str] = None,
    sentiment_score: Optional[float] = None,
) -> None:
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE conversations
            SET status           = $2,
                resolution_type  = COALESCE($3, resolution_type),
                escalated_to     = COALESCE($4, escalated_to),
                sentiment_score  = COALESCE($5, sentiment_score),
                ended_at         = CASE WHEN $2 IN ('resolved', 'closed') THEN NOW() ELSE ended_at END
            WHERE id = $1
            """,
            conversation_id, status, resolution_type, escalated_to, sentiment_score,
        )


async def load_conversation_history(conversation_id: str) -> list[dict]:
    """Return all messages in a conversation ordered oldest first."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT role, content, channel, created_at, tool_calls
            FROM messages
            WHERE conversation_id = $1
            ORDER BY created_at ASC
            """,
            conversation_id,
        )
        return [dict(r) for r in rows]


# ── Message queries ───────────────────────────────────────────────────────────

async def store_message(
    conversation_id: str,
    channel: str,
    direction: str,
    role: str,
    content: str,
    formatted_content: Optional[str] = None,
    tokens_used: Optional[int] = None,
    latency_ms: Optional[int] = None,
    tool_calls: Optional[list] = None,
    channel_message_id: Optional[str] = None,
    delivery_status: str = "pending",
) -> str:
    """Insert a message. Returns message_id."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        msg_id = await conn.fetchval(
            """
            INSERT INTO messages (
                conversation_id, channel, direction, role, content,
                formatted_content, tokens_used, latency_ms, tool_calls,
                channel_message_id, delivery_status
            ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)
            RETURNING id
            """,
            conversation_id, channel, direction, role, content,
            formatted_content, tokens_used, latency_ms,
            json.dumps(tool_calls or []),
            channel_message_id, delivery_status,
        )
        return str(msg_id)


async def update_delivery_status(channel_message_id: str, status: str) -> None:
    """Update delivery status when Twilio/Gmail callback arrives."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE messages
            SET delivery_status = $2
            WHERE channel_message_id = $1
            """,
            channel_message_id, status,
        )


# ── Ticket queries ────────────────────────────────────────────────────────────

async def create_ticket_record(
    conversation_id: str,
    customer_id: str,
    source_channel: str,
    category: Optional[str] = None,
    priority: str = "medium",
) -> str:
    """Insert a ticket. Returns ticket_id."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        ticket_id = await conn.fetchval(
            """
            INSERT INTO tickets (conversation_id, customer_id, source_channel, category, priority)
            VALUES ($1, $2, $3, $4, $5)
            RETURNING id
            """,
            conversation_id, customer_id, source_channel, category, priority,
        )
        return str(ticket_id)


async def update_ticket_record(
    ticket_id: str,
    status: str,
    escalation_level: Optional[str] = None,
    escalation_reason: Optional[str] = None,
    resolution_notes: Optional[str] = None,
) -> None:
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        sla_deadline = None
        if escalation_level:
            sla_deadline = await conn.fetchval(
                "SELECT compute_sla_deadline($1)", escalation_level
            )
        await conn.execute(
            """
            UPDATE tickets
            SET status            = $2,
                escalation_level  = COALESCE($3, escalation_level),
                escalation_reason = COALESCE($4, escalation_reason),
                resolution_notes  = COALESCE($5, resolution_notes),
                sla_deadline      = COALESCE($6, sla_deadline),
                resolved_at       = CASE WHEN $2 IN ('resolved', 'closed') THEN NOW() ELSE resolved_at END
            WHERE id = $1
            """,
            ticket_id, status, escalation_level, escalation_reason,
            resolution_notes, sla_deadline,
        )


async def get_ticket_by_id(ticket_id: str) -> Optional[dict]:
    """Return ticket with its messages for status endpoint."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        ticket = await conn.fetchrow(
            "SELECT * FROM tickets WHERE id = $1", ticket_id
        )
        if not ticket:
            return None

        messages = await conn.fetch(
            """
            SELECT role, content, channel, created_at
            FROM messages
            WHERE conversation_id = $1
            ORDER BY created_at ASC
            """,
            ticket["conversation_id"],
        )
        result = dict(ticket)
        result["messages"] = [dict(m) for m in messages]
        result["last_updated"] = (
            result["messages"][-1]["created_at"] if result["messages"] else result["created_at"]
        )
        return result


# ── Knowledge base queries ────────────────────────────────────────────────────

async def search_knowledge_base_db(
    embedding: list[float],
    max_results: int = 5,
    category: Optional[str] = None,
) -> list[dict]:
    """
    Vector similarity search using pgvector cosine distance.
    Falls back to keyword search if embedding is None.
    """
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        if embedding:
            rows = await conn.fetch(
                """
                SELECT title, content, category,
                       1 - (embedding <=> $1::vector) AS similarity
                FROM knowledge_base
                WHERE ($2::text IS NULL OR category = $2)
                ORDER BY embedding <=> $1::vector
                LIMIT $3
                """,
                embedding, category, max_results,
            )
        else:
            # Fallback: return all rows up to limit (no semantic ranking)
            rows = await conn.fetch(
                """
                SELECT title, content, category, 0.5 AS similarity
                FROM knowledge_base
                WHERE ($1::text IS NULL OR category = $1)
                LIMIT $2
                """,
                category, max_results,
            )
        return [dict(r) for r in rows]


# ── Metrics queries ───────────────────────────────────────────────────────────

async def record_metric(
    metric_name: str,
    metric_value: float,
    channel: Optional[str] = None,
    ticket_id: Optional[str] = None,
    dimensions: Optional[dict] = None,
) -> None:
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO agent_metrics (metric_name, metric_value, channel, ticket_id, dimensions)
            VALUES ($1, $2, $3, $4, $5)
            """,
            metric_name, metric_value, channel,
            ticket_id, json.dumps(dimensions or {}),
        )


async def get_channel_metrics(hours: int = 24) -> list[dict]:
    """Return per-channel summary metrics for the last N hours."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
                initial_channel                                        AS channel,
                COUNT(*)                                               AS total_conversations,
                AVG(sentiment_score)                                   AS avg_sentiment,
                COUNT(*) FILTER (WHERE status = 'escalated')          AS escalations,
                COUNT(*) FILTER (WHERE status = 'resolved')           AS resolved
            FROM conversations
            WHERE started_at > NOW() - ($1 || ' hours')::INTERVAL
            GROUP BY initial_channel
            """,
            str(hours),
        )
        return [dict(r) for r in rows]
