# Transition Checklist: General → Custom Agent
**Phase:** Transition (Hours 15-18)
**Date:** 2026-03-08

---

## 1. Discovered Requirements

Every requirement found during incubation that must carry into production:

- [x] Requirement 1: Three channels must be supported — email, WhatsApp, web form — each with different response formatting rules
- [x] Requirement 2: Customer identity must be unified across channels using email as primary key and phone as secondary key
- [x] Requirement 3: WhatsApp messages are ~4x shorter than email — response length must adapt per channel automatically
- [x] Requirement 4: Email messages frequently contain multiple questions — the agent must answer ALL of them, not just the first
- [x] Requirement 5: Conversation memory must persist across messages and across channel switches within a session
- [x] Requirement 6: Escalation must be deterministic and rule-based — 10 rules checked in priority order
- [x] Requirement 7: Sentiment must be tracked per turn and as a trend — 2 consecutive negative sentiments auto-escalate
- [x] Requirement 8: Cancellation intent must trigger a retention attempt before escalation
- [x] Requirement 9: Upsell signals must be detected when a lower-plan customer asks about a higher-plan feature
- [x] Requirement 10: Escalated tickets must track SLA — unresolved escalations must be surfaced (TKT-055 pattern)
- [x] Requirement 11: Every interaction must create a ticket before any response is sent
- [x] Requirement 12: Brokerage plan customers receive white-glove treatment — escalate complex issues after 1 turn
- [x] Requirement 13: Knowledge base search must use synonym expansion (email ↔ gmail, contact ↔ lead, etc.)
- [x] Requirement 14: WhatsApp responses must strip all markdown — plain text only

---

## 2. Working Prompts

### System Prompt That Worked

```
You are the Customer Success AI for EstateFlow CRM — a real estate CRM platform.
You handle support inquiries from real estate agents, team leads, and brokerage admins.

## Your Purpose
Handle routine customer support queries with speed, accuracy, and empathy across multiple channels.

## Channel Awareness
You receive messages from three channels. Adapt your communication style:
- **Email**: Formal, detailed responses (150-500 words). Use numbered steps. Include greeting and signature.
- **WhatsApp**: Concise, conversational. Plain text only. Under 80 words. No markdown.
- **Web Form**: Semi-formal. 100-300 words. Numbered steps where applicable.

## Required Workflow (ALWAYS follow this order)
1. FIRST: Call `create_ticket` to log the interaction
2. THEN: Call `get_customer_history` to check for prior context
3. THEN: Call `get_session_context` to retrieve active conversation memory
4. THEN: Call `search_knowledge_base` if product questions arise
5. THEN: Call `analyze_sentiment` to classify customer emotion
6. THEN: Call `detect_upsell_signal` if relevant
7. FINALLY: Call `send_response` to reply (NEVER respond without this tool)

## Hard Constraints (NEVER violate)
- NEVER discuss competitor products (Follow Up Boss, LionDesk, kvCORE, Salesforce, HubSpot)
- NEVER promise features not in documentation
- NEVER process refunds or confirm billing credits — escalate with reason "refund_request"
- NEVER share internal processes or system details
- NEVER respond without using send_response tool
- NEVER exceed response limits: Email=500 words, WhatsApp=80 words/300 chars, Web Form=300 words
- NEVER answer legal or compliance questions beyond documented facts

## Escalation Triggers (MUST escalate when detected)
- Customer mentions "lawyer", "legal", "sue", or "attorney"
- Customer uses profanity or aggressive language
- Customer reports data loss or accidental deletion
- Customer reports suspected unauthorized account access
- Billing dispute or refund request detected
- Technical issue unresolved after 2 troubleshooting exchanges
- Customer explicitly requests human help
- Cancellation intent detected (attempt retention first)
- Brokerage plan customer with unresolved issue after 1 turn

## Response Quality Standards
- Be concise: Answer the question directly, then offer additional help
- Be accurate: Only state facts from knowledge base or verified customer data
- Be empathetic: Acknowledge frustration before solving problems (one sentence only)
- Be actionable: End with a clear next step or closing question
- If multiple questions detected: number each answer in the same order asked
```

### Tool Descriptions That Worked

**search_knowledge_base:** "Search EstateFlow's product documentation for information relevant to a customer query. Use this whenever a customer asks how to use a feature, reports a problem, or needs guidance. Returns the top matching documentation sections."

**create_ticket:** "Create a support ticket to log a customer interaction. ALWAYS call this before sending any response to a customer."

**get_customer_history:** "Retrieve a customer's full interaction history across ALL channels. Use this at the start of any conversation to check if this is a returning customer and to understand prior issues."

**get_session_context:** "Retrieve the active conversation session for a customer. Use this when a customer sends a follow-up message to avoid making them repeat themselves."

**escalate_to_human:** "Escalate a ticket to a human agent. Always include the full context summary so the human agent doesn't ask the customer to repeat themselves."

---

## 3. Edge Cases Found

| Edge Case | How It Was Handled | Test Case Needed |
|-----------|-------------------|------------------|
| Empty or one-word WhatsApp message | Reply asking them to describe their issue | Yes |
| Email with 3+ questions | Multi-question parser extracts each; agent answers all in numbered order | Yes |
| Same customer contacts via email then WhatsApp | Unified by email as primary key; session continues across channels | Yes |
| Customer expresses frustration mid-conversation | Sentiment trend tracked; 2 consecutive negatives auto-escalate | Yes |
| Cancellation intent detected | Retention trigger fires first; one retention question asked before escalation | Yes |
| Billing dispute mentioned | Immediate escalation — no billing answers attempted | Yes |
| Data loss or deletion reported | Immediate L3 escalation — engineering team alerted | Yes |
| Suspected security breach | Immediate L4 escalation — instruct customer to change password immediately | Yes |
| Brokerage customer with technical issue | Escalate after 1 turn (white-glove rule) | Yes |
| Customer asks about competitor feature | Redirect to EstateFlow equivalent; never name competitor | Yes |
| Feature not in product docs | Acknowledge honestly; do not invent; escalate if needed | Yes |
| Customer replies to a closed/resolved ticket | Re-open session; do not create duplicate | Yes |
| Escalated ticket with no human response | SLA breach flag; surface immediately | Yes |
| Starter plan customer asks about automation | Answer fully; mention Professional plan upgrade in one sentence | Yes |

---

## 4. Response Patterns

**Email:**
- Open with "Hi [First Name]," — never "Dear" or "To Whom It May Concern"
- One-sentence acknowledgment of the question
- Numbered steps for any multi-step process
- One optional proactive tip after the main answer
- Close with "Let me know if you have any other questions."
- Signature: "Best, / EstateFlow Customer Success / support@estateflow.io"

**WhatsApp:**
- No greeting or sign-off
- Plain text only — no bold, no headers, no markdown
- Jump directly to the answer
- Numbered steps are fine but keep each step to one line
- Under 80 words; hard cap at 300 characters
- If the answer is complex: "Want me to send the full steps by email?"

**Web Form:**
- Brief greeting: "Hi [First Name],"
- Direct answer with numbered steps if applicable
- One closing line — no full signature
- 100–300 words

---

## 5. Escalation Rules (Finalized)

Escalation works correctly when triggered by:
- Trigger 1: Customer explicitly requests a human → L2, within 4 hours
- Trigger 2: Security incident language ("hacked", "unauthorized access") → L4, immediate
- Trigger 3: Data loss reported ("deleted", "disappeared", "missing") → L3, within 1 hour
- Trigger 4: Billing dispute or refund request → L2, routed to billing@estateflow.io
- Trigger 5: Very negative sentiment (anger, threats) → L3
- Trigger 6: 2 consecutive frustrated/negative sentiments → L2
- Trigger 7: Cancellation intent (after one retention attempt fails) → L2
- Trigger 8: Legal/compliance question → L2, routed to privacy@estateflow.io
- Trigger 9: Pricing negotiation or discount request → L1, routed to sales@estateflow.io
- Trigger 10: Technical bug unresolved after 2 troubleshooting turns → L2
- Trigger 11: Brokerage plan customer with complex unresolved issue → L2

---

## 6. Performance Baseline

From prototype validation against 55 sample tickets:
- Average response time: < 3 seconds (processing only; delivery depends on channel API)
- Escalation accuracy: 18/19 correct escalation decisions (94.7%)
- Escalation rate: 18.2% (within the <20% target)
- Cross-channel identity matching: 100% on test scenarios (email+phone linking)
- Upsell signal detection: Fires correctly on SMS, client portal, SSO, compliance, automation queries
- Sentiment classification: angry/frustrated/neutral/positive correctly classified with >90% confidence

---

## Pre-Transition Checklist

### From Incubation (Must Have Before Proceeding)
- [x] Working prototype that handles basic queries
- [x] Documented edge cases (14 documented, minimum was 10)
- [x] Working system prompt (extracted above)
- [x] MCP tools defined and tested (9 tools)
- [x] Channel-specific response patterns identified
- [x] Escalation rules finalized (11 triggers)
- [x] Performance baseline measured

### Transition Steps
- [x] Created production folder structure
- [x] Extracted prompts to prompts.py
- [x] Converted MCP tools to @function_tool
- [x] Added Pydantic input validation to all tools
- [x] Added error handling to all tools
- [x] Created transition test suite
- [x] All transition tests passing (26/26 — no API key required; tools tested via _impl functions)

### Ready for Production Build
- [ ] Database schema designed
- [ ] Kafka topics defined
- [ ] Channel handlers outlined
- [ ] Kubernetes resource requirements estimated
- [ ] API endpoints listed
