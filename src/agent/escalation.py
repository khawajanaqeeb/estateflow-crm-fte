"""
Escalation rule engine based on escalation-rules.md.
Deterministic — no AI needed for this layer.
"""

import re
from dataclasses import dataclass
from typing import Optional

from .models import Sentiment, Channel


@dataclass
class EscalationDecision:
    should_escalate: bool
    reason: Optional[str]
    level: Optional[str]    # L1 / L2 / L3 / L4
    rule: Optional[str]     # which rule triggered


# ── Trigger patterns ─────────────────────────────────────────────────────────

_HUMAN_REQUEST = re.compile(
    r'\b(real person|human|manager|speak to someone|talk to someone|'
    r'stop (sending|with) (automated|bot)|not a bot|actual (person|agent|human))\b',
    re.IGNORECASE,
)

_CANCELLATION = re.compile(
    r'\b(cancel|cancellation|cancel my (account|plan|subscription)|'
    r'switching to|moving (away|to a competitor)|done with|not (working|useful) for me|'
    r'want (a )?refund)\b',
    re.IGNORECASE,
)

_BILLING_DISPUTE = re.compile(
    r'\b(charged (twice|wrong|too much|again)|incorrect (charge|invoice|bill)|'
    r'overbill|duplicate charge|refund|credit|overcharged|billing error)\b',
    re.IGNORECASE,
)

_DATA_LOSS = re.compile(
    r'\b(deleted|lost|missing|disappeared|gone|can\'t find|accidentally (deleted|removed))\b',
    re.IGNORECASE,
)

_SECURITY = re.compile(
    r'\b(hacked|unauthori(z|s)ed|someone (else|accessed)|suspicious|'
    r'login (from|notification).*don\'t recognize|account (compromised|taken))\b',
    re.IGNORECASE,
)

_LEGAL = re.compile(
    r'\b(legal|compliance|gdpr|ccpa|hipaa|lawsuit|attorney|regulatory|'
    r'data rights|legal hold|baa|business associate)\b',
    re.IGNORECASE,
)

_PRICING_NEGOTIATION = re.compile(
    r'\b(discount|negotiate|better price|match.*price|custom (pricing|contract)|'
    r'enterprise (deal|pricing)|nonprofit discount)\b',
    re.IGNORECASE,
)

_VERY_NEGATIVE = re.compile(
    r'\b(unacceptable|terrible|awful|disaster|useless|worst|complete (failure|disaster)|'
    r'absolute (garbage|joke|joke)|i\'m done|getting a lawyer|'
    r'posting (a review|negative|on twitter)|sue)\b',
    re.IGNORECASE,
)


def check(
    message: str,
    sentiment: Sentiment,
    channel: Channel,
    plan: Optional[str],
    troubleshooting_attempts: int = 0,
    prior_sentiment_trend: Optional[list] = None,
) -> EscalationDecision:
    """
    Evaluate escalation rules in priority order.
    Returns the first triggered rule.
    """

    # Rule 6 — Security incident (highest priority after explicit human request)
    if _SECURITY.search(message):
        return EscalationDecision(
            should_escalate=True,
            reason="Potential security incident — unauthorized account access reported",
            level="L4",
            rule="Rule 6 — Security Incident",
        )

    # Rule 1 — Customer requests a human
    if _HUMAN_REQUEST.search(message):
        return EscalationDecision(
            should_escalate=True,
            reason="Customer explicitly requested a human agent",
            level="L2",
            rule="Rule 1 — Human Request",
        )

    # Rule 5 — Data loss
    if _DATA_LOSS.search(message):
        return EscalationDecision(
            should_escalate=True,
            reason="Potential data loss reported — requires backend investigation",
            level="L3",
            rule="Rule 5 — Data Loss",
        )

    # Rule 4 — Billing dispute
    if _BILLING_DISPUTE.search(message):
        return EscalationDecision(
            should_escalate=True,
            reason="Billing dispute or refund request — requires billing team review",
            level="L2",
            rule="Rule 4 — Billing Dispute",
        )

    # Rule 2 — Very negative sentiment language
    if _VERY_NEGATIVE.search(message) or sentiment == Sentiment.ANGRY:
        return EscalationDecision(
            should_escalate=True,
            reason="Customer expressing extreme frustration or anger",
            level="L3",
            rule="Rule 2 — Negative Sentiment",
        )

    # Rule 2b — Persistent negative sentiment across messages
    if prior_sentiment_trend:
        negative_states = {Sentiment.FRUSTRATED, Sentiment.NEGATIVE, Sentiment.ANGRY}
        negative_count = sum(1 for s in prior_sentiment_trend[-3:] if s in negative_states)
        if negative_count >= 2:
            return EscalationDecision(
                should_escalate=True,
                reason="Persistent negative sentiment across multiple messages",
                level="L2",
                rule="Rule 2 — Persistent Negative Sentiment",
            )

    # Rule 3 — Cancellation intent
    if _CANCELLATION.search(message):
        return EscalationDecision(
            should_escalate=True,
            reason="Cancellation intent detected — retention opportunity",
            level="L2",
            rule="Rule 3 — Cancellation Intent",
        )

    # Rule 9 — Legal/compliance questions
    if _LEGAL.search(message):
        return EscalationDecision(
            should_escalate=True,
            reason="Legal or compliance question — requires human review",
            level="L2",
            rule="Rule 9 — Legal/Compliance",
        )

    # Rule 10 — Pricing negotiation
    if _PRICING_NEGOTIATION.search(message):
        return EscalationDecision(
            should_escalate=True,
            reason="Pricing negotiation or custom contract request — route to sales",
            level="L1",
            rule="Rule 10 — Pricing Negotiation",
        )

    # Rule 7 — Bug unresolved after 2 troubleshooting attempts
    if troubleshooting_attempts >= 2:
        return EscalationDecision(
            should_escalate=True,
            reason=f"Technical issue unresolved after {troubleshooting_attempts} troubleshooting attempts",
            level="L2",
            rule="Rule 7 — Unresolved Bug",
        )

    # Rule 8 — Brokerage plan customer with non-trivial issue
    if plan == "brokerage" and sentiment in (Sentiment.FRUSTRATED, Sentiment.NEGATIVE, Sentiment.ANGRY):
        return EscalationDecision(
            should_escalate=True,
            reason="Brokerage enterprise customer with negative sentiment — white-glove escalation",
            level="L2",
            rule="Rule 8 — Enterprise Customer",
        )

    return EscalationDecision(
        should_escalate=False,
        reason=None,
        level=None,
        rule=None,
    )


def detect_upsell_signal(message: str, plan: Optional[str]) -> tuple[bool, Optional[str]]:
    """
    Detect when a customer on a lower plan is asking about a higher-plan feature.
    Returns (is_upsell_signal, target_plan).
    """
    if not plan:
        return False, None

    # Features that require Professional or above
    professional_features = re.compile(
        r'\b(sms|texts?|send texts?|text (clients|customers)|drip (campaign|email)|automation|'
        r'automated (follow.?up|email|sequence)|unlimited (contacts|pipeline))\b',
        re.IGNORECASE,
    )
    # Features that require Team or above
    team_features = re.compile(
        r'\b(client portal|portal|shared pipeline|lead routing|team dashboard|'
        r'co.?list|assign.*agent|multiple agents.*deal)\b',
        re.IGNORECASE,
    )
    # Features that require Brokerage
    brokerage_features = re.compile(
        r'\b(sso|single sign.?on|compliance checklist|white.?label|custom brand|'
        r'audit log|saml)\b',
        re.IGNORECASE,
    )

    if plan == "starter":
        if professional_features.search(message):
            return True, "professional"
        if team_features.search(message):
            return True, "team"
        if brokerage_features.search(message):
            return True, "brokerage"
    elif plan == "professional":
        if team_features.search(message):
            return True, "team"
        if brokerage_features.search(message):
            return True, "brokerage"
    elif plan == "team":
        if brokerage_features.search(message):
            return True, "brokerage"

    return False, None
