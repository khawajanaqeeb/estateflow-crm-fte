"""
Transition Tests: Verify agent behavior matches incubation discoveries.
Run these BEFORE deploying to production.

Tests are based on edge cases found during the incubation phase.
Each test maps to a documented edge case in specs/transition-checklist.md.
"""

import pytest
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))


# ── Tool-level tests ──────────────────────────────────────────────────────────

class TestToolMigration:
    """Verify production tools work the same as their MCP prototype versions."""

    @pytest.mark.asyncio
    async def test_knowledge_search_returns_results(self):
        """Knowledge search should return formatted results for a valid query."""
        from production.agent.tools import _search_knowledge_base_impl, KnowledgeSearchInput

        result = await _search_knowledge_base_impl(KnowledgeSearchInput(
            query="password reset", max_results=3
        ))
        assert result is not None
        assert len(result) > 0
        assert "password" in result.lower() or "log" in result.lower()

    @pytest.mark.asyncio
    async def test_knowledge_search_handles_no_results(self):
        """Knowledge search should return a helpful message when nothing is found."""
        from production.agent.tools import _search_knowledge_base_impl, KnowledgeSearchInput

        result = await _search_knowledge_base_impl(KnowledgeSearchInput(
            query="xyznonexistentquery999abc", max_results=3
        ))
        assert "no" in result.lower() or "not found" in result.lower() or "unavailable" in result.lower()

    @pytest.mark.asyncio
    async def test_create_ticket_returns_ticket_id(self):
        """create_ticket must return a valid ticket_id."""
        import json
        from production.agent.tools import _create_ticket_impl, CreateTicketInput

        result = await _create_ticket_impl(CreateTicketInput(
            customer_id="test-cust-001",
            issue="Cannot import contacts from Zillow",
            priority="medium",
            channel="email",
        ))
        data = json.loads(result)
        assert "ticket_id" in data
        assert data["ticket_id"].startswith("TKT-")
        assert data["status"] == "open"

    @pytest.mark.asyncio
    async def test_escalate_routes_billing_correctly(self):
        """Billing escalations must route to billing@estateflow.io."""
        import json
        from production.agent.tools import _escalate_to_human_impl, EscalateInput

        result = await _escalate_to_human_impl(EscalateInput(
            ticket_id="TKT-TEST01",
            reason="Customer reported duplicate billing charge — refund requested",
            level="L2",
            context_summary="Customer was charged twice in March. Requesting refund.",
            rule_triggered="Rule 4 — Billing Dispute",
        ))
        data = json.loads(result)
        assert data["routed_to"] == "billing@estateflow.io"
        assert data["level"] == "L2"
        assert data["sla"] == "Within 4 business hours"

    @pytest.mark.asyncio
    async def test_escalate_routes_security_correctly(self):
        """Security escalations must route to security@estateflow.io and be L4."""
        import json
        from production.agent.tools import _escalate_to_human_impl, EscalateInput

        result = await _escalate_to_human_impl(EscalateInput(
            ticket_id="TKT-TEST02",
            reason="Customer reported unauthorized access to account — security incident",
            level="L4",
            context_summary="Login from unrecognized location. Customer alarmed.",
            rule_triggered="Rule 6 — Security Incident",
        ))
        data = json.loads(result)
        assert data["routed_to"] == "security@estateflow.io"
        assert data["sla"] == "Immediate (24/7 on-call)"

    @pytest.mark.asyncio
    async def test_send_response_whatsapp_strips_markdown(self):
        """WhatsApp responses must not contain markdown formatting."""
        import json
        from production.agent.tools import _send_response_impl, SendResponseInput

        result = await _send_response_impl(SendResponseInput(
            ticket_id="TKT-TEST03",
            message="Go to **Settings → Integrations → Zillow** and click **Reconnect**.",
            channel="whatsapp",
            customer_name="Jordan",
        ))
        data = json.loads(result)
        assert "**" not in data["formatted_message"]
        assert "Settings" in data["formatted_message"]

    @pytest.mark.asyncio
    async def test_send_response_email_adds_greeting(self):
        """Email responses must include a greeting."""
        import json
        from production.agent.tools import _send_response_impl, SendResponseInput

        result = await _send_response_impl(SendResponseInput(
            ticket_id="TKT-TEST04",
            message="Go to Settings → Integrations → Gmail and click Reconnect.",
            channel="email",
            customer_name="Sarah Morrison",
        ))
        data = json.loads(result)
        msg = data["formatted_message"].lower()
        assert "hi sarah" in msg or "hello sarah" in msg

    @pytest.mark.asyncio
    async def test_detect_upsell_sms_for_starter(self):
        """SMS question from Starter plan customer should detect upsell to Professional."""
        import json
        from production.agent.tools import _detect_upsell_signal_impl, UpsellSignalInput

        result = await _detect_upsell_signal_impl(UpsellSignalInput(
            message="can i send texts to my clients from estateflow",
            current_plan="starter",
        ))
        data = json.loads(result)
        assert data["upsell_signal_detected"] is True
        assert data["target_plan"] == "professional"

    @pytest.mark.asyncio
    async def test_detect_upsell_no_signal_for_basic_question(self):
        """A basic how-to question should not trigger an upsell signal."""
        import json
        from production.agent.tools import _detect_upsell_signal_impl, UpsellSignalInput

        result = await _detect_upsell_signal_impl(UpsellSignalInput(
            message="how do i reset my password",
            current_plan="professional",
        ))
        data = json.loads(result)
        assert data["upsell_signal_detected"] is False

    @pytest.mark.asyncio
    async def test_analyze_sentiment_angry(self):
        """Strong negative language should classify as angry."""
        import json
        from production.agent.tools import _analyze_sentiment_impl, SentimentInput

        result = await _analyze_sentiment_impl(SentimentInput(
            message="This is absolutely terrible and completely unacceptable. Nothing works."
        ))
        data = json.loads(result)
        assert data["sentiment"] in ("angry", "frustrated")
        assert data["is_negative"] is True

    @pytest.mark.asyncio
    async def test_analyze_sentiment_positive(self):
        """Positive language should classify as positive."""
        import json
        from production.agent.tools import _analyze_sentiment_impl, SentimentInput

        result = await _analyze_sentiment_impl(SentimentInput(
            message="Thank you so much! This is exactly what I needed."
        ))
        data = json.loads(result)
        assert data["sentiment"] == "positive"
        assert data["is_negative"] is False


# ── Escalation rule tests ─────────────────────────────────────────────────────

class TestEscalationRules:
    """Verify escalation rule engine matches incubation discoveries."""

    def test_billing_dispute_escalates(self):
        """Billing dispute language must trigger escalation."""
        import sys; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        from src.agent.escalation import check
        from src.agent.models import Channel, Sentiment

        decision = check(
            message="I was charged twice this month and want a refund",
            sentiment=Sentiment.FRUSTRATED,
            channel=Channel.EMAIL,
            plan="professional",
        )
        assert decision.should_escalate is True
        assert "Rule 4" in decision.rule

    def test_security_incident_escalates_l4(self):
        """Security incident must escalate at L4."""
        from src.agent.escalation import check
        from src.agent.models import Channel, Sentiment

        decision = check(
            message="I think my account was hacked — I got a login from somewhere I don't recognize",
            sentiment=Sentiment.NEUTRAL,
            channel=Channel.WEB_FORM,
            plan="team",
        )
        assert decision.should_escalate is True
        assert decision.level == "L4"

    def test_cancellation_escalates(self):
        """Cancellation intent must trigger escalation."""
        from src.agent.escalation import check
        from src.agent.models import Channel, Sentiment

        decision = check(
            message="I want to cancel my subscription",
            sentiment=Sentiment.NEUTRAL,
            channel=Channel.EMAIL,
            plan="starter",
        )
        assert decision.should_escalate is True
        assert "Rule 3" in decision.rule

    def test_normal_question_does_not_escalate(self):
        """A standard product question must not escalate."""
        from src.agent.escalation import check
        from src.agent.models import Channel, Sentiment

        decision = check(
            message="how do i import contacts from zillow",
            sentiment=Sentiment.NEUTRAL,
            channel=Channel.WHATSAPP,
            plan="starter",
        )
        assert decision.should_escalate is False

    def test_persistent_negative_sentiment_escalates(self):
        """Two consecutive negative sentiments must trigger escalation."""
        from src.agent.escalation import check
        from src.agent.models import Channel, Sentiment

        decision = check(
            message="still not working",
            sentiment=Sentiment.FRUSTRATED,
            channel=Channel.EMAIL,
            plan="professional",
            prior_sentiment_trend=[Sentiment.FRUSTRATED, Sentiment.FRUSTRATED],
        )
        assert decision.should_escalate is True

    def test_unresolved_bug_after_two_attempts_escalates(self):
        """Bug unresolved after 2 troubleshooting attempts must escalate."""
        from src.agent.escalation import check
        from src.agent.models import Channel, Sentiment

        decision = check(
            message="still crashing after reinstall",
            sentiment=Sentiment.FRUSTRATED,
            channel=Channel.WEB_FORM,
            plan="professional",
            troubleshooting_attempts=2,
        )
        assert decision.should_escalate is True
        assert "Rule 7" in decision.rule


# ── Channel formatting tests ──────────────────────────────────────────────────

class TestChannelAdaptation:
    """Verify channel-specific formatting from incubation patterns."""

    def test_whatsapp_no_markdown(self):
        """WhatsApp output must contain no markdown."""
        from src.agent.formatter import format_for_channel
        from src.agent.models import Channel

        result = format_for_channel(
            response="Go to **Settings** and click **Connect Gmail**.",
            channel=Channel.WHATSAPP,
            customer_name="Sarah",
        )
        assert "**" not in result

    def test_whatsapp_under_word_limit(self):
        """WhatsApp responses must stay within word limit."""
        from src.agent.formatter import format_for_channel
        from src.agent.models import Channel

        long_text = " ".join(["word"] * 200)
        result = format_for_channel(long_text, Channel.WHATSAPP)
        assert len(result.split()) <= 85   # some tolerance for formatting

    def test_email_has_greeting(self):
        """Email responses must include a greeting."""
        from src.agent.formatter import format_for_channel
        from src.agent.models import Channel

        result = format_for_channel(
            response="Here are the steps to connect Gmail.",
            channel=Channel.EMAIL,
            customer_name="Marcus Reed",
        )
        assert "Hi Marcus" in result or "Hello Marcus" in result

    def test_email_has_signoff(self):
        """Email responses must include a sign-off."""
        from src.agent.formatter import format_for_channel
        from src.agent.models import Channel

        result = format_for_channel(
            response="Here are the steps.",
            channel=Channel.EMAIL,
            customer_name="Sarah",
        )
        assert "EstateFlow Customer Success" in result

    def test_web_form_has_greeting_no_full_signature(self):
        """Web form must have a greeting but not a full email signature."""
        from src.agent.formatter import format_for_channel
        from src.agent.models import Channel

        result = format_for_channel(
            response="Here are the steps.",
            channel=Channel.WEB_FORM,
            customer_name="Jordan",
        )
        assert "Hi Jordan" in result
        assert "support@estateflow.io" not in result


# ── Memory and cross-channel tests ────────────────────────────────────────────

class TestMemoryAndCrossChannel:
    """Verify session memory and cross-channel identity from incubation."""

    def test_same_session_returned_for_followup(self):
        """A follow-up message from the same customer returns the same session."""
        from src.agent.memory import MemoryStore
        from src.agent.models import Channel

        store = MemoryStore()
        s1, is_new1 = store.get_or_create_session("cust-001", Channel.EMAIL)
        s2, is_new2 = store.get_or_create_session("cust-001", Channel.EMAIL)

        assert s1.session_id == s2.session_id
        assert is_new1 is True
        assert is_new2 is False

    def test_channel_switch_detected(self):
        """Session detects when customer switches from email to WhatsApp."""
        from src.agent.memory import MemoryStore
        from src.agent.models import Channel

        store = MemoryStore()
        s1, _ = store.get_or_create_session("cust-002", Channel.EMAIL)
        s2, _ = store.get_or_create_session("cust-002", Channel.WHATSAPP)

        assert s2.channel_switched(Channel.WHATSAPP) is True
        assert Channel.WHATSAPP in s2.channels_used

    def test_cross_channel_identity_email_phone(self):
        """Customer identified by email on first contact and phone on second."""
        from src.agent.customer_store import CustomerStore
        from src.agent.models import Channel

        store = CustomerStore()
        c1 = store.identify_customer(email="test@example.com", channel=Channel.EMAIL)
        c2 = store.identify_customer(phone="+14085551234", email="test@example.com", channel=Channel.WHATSAPP)

        assert c1.customer_id == c2.customer_id
        assert Channel.WHATSAPP in c2.channels_used

    def test_sentiment_worsening_detection(self):
        """Two consecutive frustrated sentiments trigger worsening flag."""
        from src.agent.memory import MemoryStore
        from src.agent.models import Channel, Sentiment

        store = MemoryStore()
        session, _ = store.get_or_create_session("cust-003", Channel.EMAIL)
        session.add_turn("first issue", "response 1", Channel.EMAIL, Sentiment.FRUSTRATED, [])
        session.add_turn("still broken", "response 2", Channel.EMAIL, Sentiment.FRUSTRATED, [])

        assert session.sentiment_worsening() is True
