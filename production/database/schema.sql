-- =============================================================================
-- EstateFlow Customer Success FTE — CRM/Ticket Management System
-- =============================================================================
-- PostgreSQL 16 + pgvector extension
-- This schema IS the CRM: customers, conversations, tickets, messages.
-- No external CRM required.
-- =============================================================================

-- Enable pgvector for semantic search on knowledge_base
CREATE EXTENSION IF NOT EXISTS vector;

-- =============================================================================
-- CUSTOMERS
-- Unified identity across all channels.
-- Primary key: email (preferred) or phone (WhatsApp fallback).
-- =============================================================================

CREATE TABLE customers (
    id           UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    email        VARCHAR(255) UNIQUE,
    phone        VARCHAR(50),                          -- E.164 format e.g. +14085551234
    name         VARCHAR(255),
    plan         VARCHAR(50)  NOT NULL DEFAULT 'starter', -- starter|professional|team|brokerage
    created_at   TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    metadata     JSONB        NOT NULL DEFAULT '{}'    -- timezone, agent_count, etc.
);

-- =============================================================================
-- CUSTOMER IDENTIFIERS
-- Maps one customer to multiple channel-specific IDs.
-- Enables cross-channel identity matching (email ↔ phone ↔ WhatsApp).
-- =============================================================================

CREATE TABLE customer_identifiers (
    id               UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id      UUID         NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    identifier_type  VARCHAR(50)  NOT NULL,  -- email|phone|whatsapp|gmail_thread
    identifier_value VARCHAR(255) NOT NULL,
    verified         BOOLEAN      NOT NULL DEFAULT FALSE,
    created_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    UNIQUE (identifier_type, identifier_value)
);

-- =============================================================================
-- CONVERSATIONS
-- One conversation per continuous interaction thread.
-- A single customer can have many conversations over time.
-- Active conversations are reused within a 24-hour window.
-- =============================================================================

CREATE TABLE conversations (
    id               UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id      UUID         NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    initial_channel  VARCHAR(50)  NOT NULL,  -- email|whatsapp|web_form
    status           VARCHAR(50)  NOT NULL DEFAULT 'active', -- active|resolved|escalated|closed
    sentiment_score  DECIMAL(3,2),                           -- 0.00 (negative) to 1.00 (positive)
    resolution_type  VARCHAR(50),                            -- resolved|escalated|abandoned
    escalated_to     VARCHAR(255),                           -- escalation destination email
    started_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    ended_at         TIMESTAMPTZ,
    metadata         JSONB        NOT NULL DEFAULT '{}'      -- includes channels_used array
);

-- =============================================================================
-- MESSAGES
-- Individual turns in a conversation.
-- Tracks both inbound (customer) and outbound (agent) messages with
-- channel source, delivery status, latency, and tool calls.
-- =============================================================================

CREATE TABLE messages (
    id                  UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id     UUID         NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    channel             VARCHAR(50)  NOT NULL,  -- email|whatsapp|web_form
    direction           VARCHAR(20)  NOT NULL,  -- inbound|outbound
    role                VARCHAR(20)  NOT NULL,  -- customer|agent|system
    content             TEXT         NOT NULL,
    formatted_content   TEXT,                   -- channel-formatted version (outbound only)
    created_at          TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    tokens_used         INTEGER,
    latency_ms          INTEGER,
    tool_calls          JSONB        NOT NULL DEFAULT '[]',
    channel_message_id  VARCHAR(255),           -- Gmail msg ID or Twilio SID
    delivery_status     VARCHAR(50)  NOT NULL DEFAULT 'pending' -- pending|sent|delivered|failed
);

-- =============================================================================
-- TICKETS
-- Formal support ticket per conversation.
-- Tracks category, priority, SLA deadline, and escalation details.
-- =============================================================================

CREATE TABLE tickets (
    id                UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id   UUID         NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    customer_id       UUID         NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    source_channel    VARCHAR(50)  NOT NULL,  -- channel of first contact
    category          VARCHAR(100),           -- technical|billing|general|feedback|bug_report
    priority          VARCHAR(20)  NOT NULL DEFAULT 'medium', -- low|medium|high|urgent
    status            VARCHAR(50)  NOT NULL DEFAULT 'open',   -- open|in_progress|escalated|resolved|closed
    escalation_level  VARCHAR(10),            -- L1|L2|L3|L4
    escalation_reason TEXT,
    sla_deadline      TIMESTAMPTZ,            -- computed from escalation_level at escalation time
    created_at        TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    resolved_at       TIMESTAMPTZ,
    resolution_notes  TEXT
);

-- =============================================================================
-- KNOWLEDGE BASE
-- Product documentation chunks for semantic search via pgvector.
-- Seeded from context/product-docs.md during setup.
-- =============================================================================

CREATE TABLE knowledge_base (
    id          UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    title       VARCHAR(500)  NOT NULL,
    content     TEXT          NOT NULL,
    category    VARCHAR(100),              -- integrations|billing|features|mobile|general
    embedding   VECTOR(1536),             -- OpenAI text-embedding-3-small
    synonyms    TEXT[]        NOT NULL DEFAULT '{}', -- keyword aliases for fallback search
    created_at  TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

-- =============================================================================
-- AGENT METRICS
-- Per-event performance records for monitoring and reporting.
-- =============================================================================

CREATE TABLE agent_metrics (
    id            UUID           PRIMARY KEY DEFAULT gen_random_uuid(),
    metric_name   VARCHAR(100)   NOT NULL,    -- message_processed|escalation|error|sla_breach
    metric_value  DECIMAL(10,4)  NOT NULL,
    channel       VARCHAR(50),               -- optional channel filter
    ticket_id     UUID           REFERENCES tickets(id) ON DELETE SET NULL,
    dimensions    JSONB          NOT NULL DEFAULT '{}',
    recorded_at   TIMESTAMPTZ    NOT NULL DEFAULT NOW()
);

-- =============================================================================
-- INDEXES
-- =============================================================================

-- Customer lookup
CREATE INDEX idx_customers_email              ON customers(email);
CREATE INDEX idx_customers_phone              ON customers(phone);
CREATE INDEX idx_customer_identifiers_value   ON customer_identifiers(identifier_value);
CREATE INDEX idx_customer_identifiers_type    ON customer_identifiers(identifier_type, identifier_value);

-- Conversation lookup
CREATE INDEX idx_conversations_customer       ON conversations(customer_id);
CREATE INDEX idx_conversations_status         ON conversations(status);
CREATE INDEX idx_conversations_channel        ON conversations(initial_channel);
-- Partial index: fast lookup of active conversations (used by worker to reuse session)
CREATE INDEX idx_conversations_active         ON conversations(customer_id, started_at)
    WHERE status = 'active';

-- Message lookup
CREATE INDEX idx_messages_conversation        ON messages(conversation_id);
CREATE INDEX idx_messages_channel             ON messages(channel);
CREATE INDEX idx_messages_created_at          ON messages(conversation_id, created_at);

-- Ticket lookup
CREATE INDEX idx_tickets_status               ON tickets(status);
CREATE INDEX idx_tickets_channel              ON tickets(source_channel);
CREATE INDEX idx_tickets_customer             ON tickets(customer_id);
-- Partial index: fast SLA breach detection for escalated tickets
CREATE INDEX idx_tickets_sla_breach           ON tickets(sla_deadline)
    WHERE status = 'escalated';

-- Knowledge base semantic search (ivfflat for approximate nearest neighbor)
CREATE INDEX idx_knowledge_embedding          ON knowledge_base
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

-- Metrics time-series
CREATE INDEX idx_metrics_name_time            ON agent_metrics(metric_name, recorded_at);
CREATE INDEX idx_metrics_channel_time         ON agent_metrics(channel, recorded_at)
    WHERE channel IS NOT NULL;

-- =============================================================================
-- SEED: SLA DEADLINE FUNCTION
-- Computes SLA deadline from escalation level at the time of escalation.
-- =============================================================================

CREATE OR REPLACE FUNCTION compute_sla_deadline(level VARCHAR(10))
RETURNS TIMESTAMPTZ
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN CASE level
        WHEN 'L1' THEN NOW() + INTERVAL '1 business day'
        WHEN 'L2' THEN NOW() + INTERVAL '4 hours'
        WHEN 'L3' THEN NOW() + INTERVAL '1 hour'
        WHEN 'L4' THEN NOW() + INTERVAL '15 minutes'
        ELSE NOW() + INTERVAL '1 business day'
    END;
END;
$$;
