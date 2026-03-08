# Discovery Log — EstateFlow Customer Success FTE
**Phase:** Incubation — Exercise 1.1
**Date:** 2026-03-08
**Method:** Analysis of 55 sample tickets across 3 channels + review of all context documents

---

## 1. Channel Analysis

### Distribution
| Channel | Count | % of Total |
|---|---|---|
| Email | 19 | 34.5% |
| WhatsApp | 18 | 32.7% |
| Web Form | 18 | 32.7% |

Channels are evenly distributed — the system must treat all three as equal first-class citizens, not email as primary with the others as secondary.

### Message Length by Channel
| Channel | Avg Words | Min | Max |
|---|---|---|---|
| Email | 40 words | 27 | 57 |
| Web Form | 34 words | 24 | 48 |
| WhatsApp | 9 words | 5 | 17 |

**Key finding:** WhatsApp messages are ~4x shorter than email and web form. This is not a style preference — it is a structural constraint of the channel. The agent must detect channel and adapt response length accordingly.

### WhatsApp Language Patterns (observed across all 18 tickets)
- No capital letters in 15 of 18 messages
- No punctuation in most messages
- Single-question focus — one thing per message
- Keyword-style phrasing: "can i send texts to clients from estateflow"
- No subject line (null in all cases)
- Urgent tone even for low-priority questions ("i cant get in")

**Implication:** WhatsApp messages require a normalizer that strips the expectation of grammar before NLP processing. The agent cannot assume proper sentence structure as a signal of intent.

### Email Language Patterns
- Full sentences with proper grammar
- Multi-part questions common (e.g., "Can I do X? Also, how does Y work?")
- Self-identification common ("Hi, I just signed up...")
- Context setting before the question
- Always has a subject line

**Implication:** Emails often contain multiple questions. The agent must identify and answer ALL questions in a single email, not just the first one detected.

### Web Form Language Patterns
- Structured, complete sentences — more formal than WhatsApp but less than email
- Scenario-first format: describes the situation, then asks the question
- No subject line creativity — subject tends to be a direct summary of the issue
- More specific than WhatsApp, less verbose than email

---

## 2. Topic Distribution

| Category | Count | % |
|---|---|---|
| Feature Questions | 18 | 32.7% |
| Billing | 10 | 18.2% |
| Account | 5 | 9.1% |
| Technical Issues | 5 | 9.1% |
| Integration | 4 | 7.3% |
| Data | 4 | 7.3% |
| Automation | 3 | 5.5% |
| Mobile | 3 | 5.5% |
| Onboarding | 3 | 5.5% |

**Key finding:** Feature questions dominate at 33%. Most customers aren't broken — they just don't know how to use the product. This means the knowledge base search tool is the most critical tool in the agent's arsenal.

**Hidden finding:** Billing questions (18%) are disproportionately high-stakes. A wrong answer about a refund, charge, or cancellation can cause immediate churn or legal exposure. Billing is the most dangerous category for autonomous handling.

---

## 3. Escalation Analysis

- **Total escalations:** 10 out of 55 (18.2%)
- This is close to the ≤20% target from the FTE spec — the system is designed correctly
- **0 WhatsApp escalations** — WhatsApp tickets tend to be simple, quick-answer questions
- **7 email escalations** — complex, sensitive, or multi-issue tickets cluster in email
- **3 web form escalations** — mid-complexity, some reach escalation threshold

### Escalation Root Causes (discovered)
| Root Cause | Count |
|---|---|
| Billing dispute / financial | 3 |
| High-frustration / churn risk | 2 |
| Technical bug (confirmed, engineering needed) | 1 |
| Security incident | 1 |
| Data loss / deletion | 1 |
| Enterprise configuration (SSO) | 1 |
| Large-scale migration | 1 |

**Key finding:** The agent can handle 82% of tickets autonomously. The 18% that require escalation fall into predictable, rule-based categories — not random or ambiguous cases. Escalation logic can be deterministic.

**Critical finding — the follow-up escalation (TKT-055):** A customer who was already escalated once and received no response re-contacted support 3 days later. The system must track escalation status and flag unresolved escalations proactively. This is a hidden requirement not in the original spec.

---

## 4. Sentiment Analysis

| Sentiment | Count |
|---|---|
| Neutral | 18 |
| Positive | 17 |
| Frustrated | 8 |
| Anxious | 2 |
| Angry / Very Angry | 2 |
| Other (panicked, alarmed, concerned, hesitant, excited, curious) | 8 |

**Key finding:** 64% of customers are neutral or positive — the majority of tickets are straightforward support interactions, not fires to put out. The agent should not default to a defensive or over-apologetic tone.

**Key finding:** Frustration clusters around: bugs that persist after troubleshooting (TKT-008, TKT-021, TKT-028, TKT-035), billing errors (TKT-040), and unresolved multi-issue situations (TKT-046).

**Hidden requirement:** Sentiment must be tracked across the conversation, not just detected per message. TKT-050 starts hesitant (near-cancellation) and becomes an opportunity — the same customer who said "before I cancel" represents a winnable retention case. Sentiment trajectory matters as much as current sentiment.

---

## 5. Customer Plan Distribution

| Plan | Count | % |
|---|---|---|
| Professional | 24 | 43.6% |
| Starter | 13 | 23.6% |
| Team | 11 | 20.0% |
| Brokerage | 7 | 12.7% |

**Key finding:** Professional plan customers generate the most tickets. This is the "power user" segment — they use more features and hit more edge cases. They also represent the highest revenue-per-seat tier below enterprise.

**Key finding:** Brokerage customers (12.7% of tickets) punch above their weight in complexity. All 7 brokerage tickets involve higher-stakes issues (SSO, compliance, audit logs, migration, branding). These need white-glove handling.

---

## 6. Priority Distribution

| Priority | Count |
|---|---|
| Low | 19 (34.5%) |
| Medium | 15 (27.3%) |
| High | 15 (27.3%) |
| Urgent | 6 (10.9%) |

**Key finding:** 38% of tickets are high or urgent. The agent must be capable of recognizing urgency signals (data loss, security, payment errors, app completely broken) and acting on them immediately — not treating them in the same queue as "how do I export my data."

---

## 7. Cross-Channel Customer Patterns

**Discovered:** The same customer contacts support across multiple channels (TKT-001 Sarah via email, TKT-005 Sarah via WhatsApp). The agent must unify identity across channels using email address as the primary key and phone number as a secondary key.

**Discovered:** TKT-008 and TKT-021 are the same customer (Tom Walsh) — first contacting via WhatsApp about a crash, then via web form after the issue persisted. Without cross-channel memory:
- The web form agent would start fresh and lose the troubleshooting context
- The customer would have to repeat themselves
- The issue would look like a new ticket instead of an escalation

**Critical hidden requirement:** Cross-channel conversation continuity is not optional. It is the difference between a good experience and an infuriating one.

---

## 8. Hidden Requirements Discovered

These requirements were NOT in the original brief but emerged from ticket analysis:

### HR-1: Multi-Question Detection (Email)
Email messages frequently contain 2–3 questions in one message. The agent must detect all questions and answer all of them. Answering only the first question will frustrate professional users.

### HR-2: Upsell Signal Detection
Multiple tickets from Starter/Professional customers ask about features on higher plans (TKT-005 SMS, TKT-025 contact limit, TKT-039 client portal). The agent must recognize these as soft upsell signals, answer the question, and note the upgrade path — without hard-selling.

### HR-3: Retention Trigger Detection
TKT-050 shows a customer on the edge of cancellation who can be re-engaged with the right question ("what specifically isn't working?"). The agent needs a retention skill that activates on cancellation language before following escalation rules.

### HR-4: Escalation Continuity Tracking
TKT-055 reveals that escalated tickets can go unresolved and the customer returns. The system needs to track escalation status and alert if an escalated ticket receives no human response within SLA.

### HR-5: Proactive Feature Education
Many questions are about features the customer doesn't know exist. The agent should match the customer's described workflow to a relevant feature, not just answer the literal question. Example: TKT-034 (agents not logging calls) → suggest automation task reminder, not just explain manual logging.

### HR-6: Contextual Tone Calibration
The agent must not just format by channel — it must calibrate tone based on the combination of channel + sentiment + plan. A frustrated brokerage customer on email needs a different tone than a curious new agent on WhatsApp.

### HR-7: Empty/Minimal Message Handling
WhatsApp messages like "hey" or single-word inputs are possible (not in sample but implied by the pattern). The agent needs a graceful handler for incomplete or context-free messages.

---

## 9. System Architecture Implications

Based on the above discoveries, the system must include:

### Core Processing Pipeline
```
Incoming message
    → Channel detection (email / whatsapp / web_form)
    → Customer identification (email/phone → customer_id)
    → Cross-channel history retrieval
    → Message normalization (grammar-agnostic for WhatsApp)
    → Multi-question extraction (especially for email)
    → Intent classification (what category is this?)
    → Sentiment detection (current + trajectory)
    → Knowledge base search (per question/intent)
    → Response generation
    → Escalation check (rule-based, deterministic)
    → Channel-specific response formatting
    → Response delivery
    → Ticket creation/update
```

### Required Tools (MCP layer)
1. `search_knowledge_base(query, category?)` — semantic search over product-docs.md
2. `create_ticket(customer_id, issue, priority, channel, sentiment)` — log every interaction
3. `get_customer_history(customer_id)` — cross-channel history
4. `escalate_to_human(ticket_id, reason, level, context_summary)` — with full context
5. `send_response(ticket_id, message, channel)` — channel-aware delivery
6. `update_ticket_status(ticket_id, status, resolution_notes)` — track resolution
7. `detect_upsell_signal(plan, feature_requested)` — flag upgrade opportunities

### Agent Skills Required
1. Knowledge Retrieval
2. Sentiment Analysis (per-message + trend)
3. Escalation Decision (rule-based)
4. Channel Adaptation (format + tone)
5. Customer Identification (cross-channel unification)
6. Multi-Question Parser (email-specific)
7. Retention Trigger Detection (cancellation language)

---

## 10. Edge Cases Identified

| Edge Case | How to Handle |
|---|---|
| Customer contacts on WhatsApp but previously emailed — different identifiers | Match by name + company if email/phone don't resolve; flag for manual review |
| Email with 3+ questions | Answer all; number the responses to match the questions |
| Angry customer who calms down mid-conversation | Update sentiment trajectory; de-escalate tone accordingly |
| Customer asks about a competitor feature | Redirect to EstateFlow equivalent; never mention competitor by name |
| WhatsApp message with only emoji or one word | Reply asking them to describe their issue; offer to send a web form link |
| Customer replies to a closed ticket | Re-open the ticket; do not create a duplicate |
| Two escalations to the same customer with no response | Flag as SLA breach; notify on-call immediately |
| Customer on trial asks billing question about post-trial pricing | Answer accurately; do not up-sell aggressively during trial |
| Brokerage plan customer asks a simple question | Answer directly but flag for human check-in follow-up |
| Customer asks something not in product-docs.md | Acknowledge honestly; do not invent an answer; escalate if needed |

---

## 11. Performance Baseline Targets

Based on the ticket distribution and escalation analysis:

| Metric | Target | Basis |
|---|---|---|
| Autonomous resolution rate | ≥82% | 18% escalation rate from sample |
| Response acknowledgment | <3 seconds | FTE spec requirement |
| Answer accuracy | >85% | FTE spec requirement |
| Escalation rate | <20% | Observed 18.2% in sample |
| Cross-channel ID accuracy | >95% | FTE spec requirement |
| Upsell signal detection | >80% recall | Observed ~6 clear signals in 55 tickets |
| Sentiment classification accuracy | >90% | Binary (positive/neutral/negative) before fine-grained |

---

## 12. Next Steps (Exercise 1.2)

Build the core prototype loop in this order:

1. **Message intake + channel normalization** — single `IncomingMessage` dataclass with channel metadata
2. **Customer identification** — email as primary key, phone as secondary
3. **Knowledge base search** — simple keyword/semantic search over product-docs.md
4. **Response generation** — Claude API with system prompt from brand-voice.md
5. **Channel-aware formatting** — post-process response based on channel
6. **Escalation check** — rule engine based on escalation-rules.md
7. **Ticket creation** — in-memory store (to be replaced with PostgreSQL in Stage 2)

Start with email only, then add WhatsApp and web form adapters.
