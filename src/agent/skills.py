"""
EstateFlow Customer Success FTE — Agent Skills

Skills are discrete, reusable capabilities the agent invokes at defined
points in the processing pipeline. Each skill has a clear trigger condition,
typed inputs, typed outputs, and is independently testable.

Skills defined here:
  1. KnowledgeRetrievalSkill    — search product docs for answers
  2. SentimentAnalysisSkill     — classify customer sentiment + confidence
  3. EscalationDecisionSkill    — decide whether and how to escalate
  4. ChannelAdaptationSkill     — format response for the target channel
  5. CustomerIdentificationSkill — unify customer identity across channels
  6. MultiQuestionParserSkill   — extract all questions from a single message
  7. RetentionTriggerSkill      — detect and respond to cancellation signals
"""

import re
from dataclasses import dataclass
from typing import Optional

from .models import Channel, Sentiment
from . import knowledge_base
from . import escalation as esc_engine
from . import formatter


# ─────────────────────────────────────────────────────────────────────────────
# Skill output types
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class KnowledgeRetrievalOutput:
    results: list                   # list of knowledge_base.SearchResult
    formatted_context: str          # ready to inject into Claude prompt
    result_count: int
    query_used: str


@dataclass
class SentimentOutput:
    sentiment: Sentiment
    confidence: float               # 0.0–1.0
    signals_found: list[str]        # which words triggered the classification
    is_negative: bool
    escalation_advised: bool
    tone_guidance: str              # how agent should adjust its tone


@dataclass
class EscalationOutput:
    should_escalate: bool
    reason: Optional[str]
    level: Optional[str]            # L1/L2/L3/L4
    rule_triggered: Optional[str]
    sentiment_worsening: bool
    troubleshooting_exhausted: bool


@dataclass
class ChannelAdaptationOutput:
    formatted_response: str
    channel: Channel
    word_count: int
    char_count: int
    truncated: bool


@dataclass
class CustomerIdentificationOutput:
    customer_id: str
    is_new_customer: bool
    email: Optional[str]
    phone: Optional[str]
    name: Optional[str]
    plan: Optional[str]
    channels_used: list[str]
    cross_channel_match: bool       # True if matched via secondary key


@dataclass
class MultiQuestionOutput:
    questions: list[str]            # list of individual questions extracted
    question_count: int
    has_multiple_questions: bool
    original_message: str


@dataclass
class RetentionTriggerOutput:
    cancellation_detected: bool
    signal_phrase: Optional[str]    # the exact phrase that triggered detection
    retention_question: str         # the one question the agent should ask
    escalate_if_confirmed: bool


# ─────────────────────────────────────────────────────────────────────────────
# Skill 1 — Knowledge Retrieval
# ─────────────────────────────────────────────────────────────────────────────

class KnowledgeRetrievalSkill:
    """
    TRIGGER: Customer asks a product question, describes a workflow,
             or reports an issue that may have a documented solution.

    INPUTS:  query (str), max_results (int)
    OUTPUTS: KnowledgeRetrievalOutput
    """

    name = "knowledge_retrieval"
    trigger = "Customer asks product questions or needs how-to guidance"

    def run(self, query: str, max_results: int = 3) -> KnowledgeRetrievalOutput:
        results = knowledge_base.search(query, max_results=max_results)
        formatted = knowledge_base.format_results(results)
        return KnowledgeRetrievalOutput(
            results=results,
            formatted_context=formatted,
            result_count=len(results),
            query_used=query,
        )


# ─────────────────────────────────────────────────────────────────────────────
# Skill 2 — Sentiment Analysis
# ─────────────────────────────────────────────────────────────────────────────

_SENTIMENT_SIGNALS = {
    Sentiment.ANGRY: [
        r'\b(unacceptable|outrageous|furious|livid|lawsuit|sue|absolutely (terrible|awful|broken))\b',
        r'\b(worst.*ever|complete (joke|failure|garbage)|getting a lawyer)\b',
    ],
    Sentiment.FRUSTRATED: [
        r'\b(frustrated|annoyed|terrible|awful|broken|useless|ridiculous|waste|disaster)\b',
        r'\b(still (not working|broken|crashing)|nothing works|keeps (failing|crashing))\b',
        r'\b(i(\'ve| have) tried|already (tried|did|checked)|same (issue|problem|thing))\b',
    ],
    Sentiment.NEGATIVE: [
        r'\b(not (working|happy|satisfied|great)|disappointed|unhappy|poor|bad)\b',
        r'\b(doesn\'t work|doesn\'t help|not what i expected)\b',
    ],
    Sentiment.POSITIVE: [
        r'\b(great|thanks|thank you|love|excited|perfect|awesome|helpful|appreciate|amazing)\b',
        r'\b(works (great|perfectly|well)|exactly what|this is (great|perfect|helpful))\b',
    ],
}

_TONE_GUIDANCE = {
    Sentiment.POSITIVE:   "Customer is in a positive state. Answer directly, be warm and efficient.",
    Sentiment.NEUTRAL:    "Customer is neutral. Be clear, professional, and helpful.",
    Sentiment.NEGATIVE:   "Customer is dissatisfied. Acknowledge once briefly, then solve completely.",
    Sentiment.FRUSTRATED: "Customer is frustrated. Lead with one empathy sentence, then solve fast.",
    Sentiment.ANGRY:      "Customer is angry. Acknowledge, do not defend, escalate if needed.",
}


class SentimentAnalysisSkill:
    """
    TRIGGER: Every incoming customer message — run before any other skill.

    INPUTS:  message (str)
    OUTPUTS: SentimentOutput
    """

    name = "sentiment_analysis"
    trigger = "Every incoming customer message"

    def run(self, message: str) -> SentimentOutput:
        text = message.lower()
        signals_found = []
        detected_sentiment = Sentiment.NEUTRAL

        # Check from most severe to least
        for sentiment_level in [Sentiment.ANGRY, Sentiment.FRUSTRATED,
                                 Sentiment.NEGATIVE, Sentiment.POSITIVE]:
            for pattern in _SENTIMENT_SIGNALS[sentiment_level]:
                matches = re.findall(pattern, text, re.IGNORECASE)
                if matches:
                    signals_found.extend([m if isinstance(m, str) else m[0] for m in matches])
                    if detected_sentiment == Sentiment.NEUTRAL:
                        detected_sentiment = sentiment_level

        # Confidence: based on signal count
        if len(signals_found) >= 3:
            confidence = 0.95
        elif len(signals_found) == 2:
            confidence = 0.85
        elif len(signals_found) == 1:
            confidence = 0.75
        else:
            confidence = 0.60   # default neutral — moderate confidence

        negative_states = {Sentiment.FRUSTRATED, Sentiment.NEGATIVE, Sentiment.ANGRY}
        is_negative = detected_sentiment in negative_states

        return SentimentOutput(
            sentiment=detected_sentiment,
            confidence=confidence,
            signals_found=list(set(signals_found)),
            is_negative=is_negative,
            escalation_advised=detected_sentiment == Sentiment.ANGRY,
            tone_guidance=_TONE_GUIDANCE[detected_sentiment],
        )


# ─────────────────────────────────────────────────────────────────────────────
# Skill 3 — Escalation Decision
# ─────────────────────────────────────────────────────────────────────────────

class EscalationDecisionSkill:
    """
    TRIGGER: After sentiment is known and before response is generated.
             Also checks sentiment trend from session memory.

    INPUTS:  message (str), sentiment (Sentiment), channel (Channel),
             plan (str), troubleshooting_attempts (int),
             prior_sentiment_trend (list[Sentiment])
    OUTPUTS: EscalationOutput
    """

    name = "escalation_decision"
    trigger = "After sentiment analysis, before generating a response"

    def run(
        self,
        message: str,
        sentiment: Sentiment,
        channel: Channel,
        plan: Optional[str],
        troubleshooting_attempts: int = 0,
        prior_sentiment_trend: Optional[list] = None,
    ) -> EscalationOutput:
        decision = esc_engine.check(
            message=message,
            sentiment=sentiment,
            channel=channel,
            plan=plan,
            troubleshooting_attempts=troubleshooting_attempts,
            prior_sentiment_trend=prior_sentiment_trend or [],
        )

        negative_states = {Sentiment.FRUSTRATED, Sentiment.NEGATIVE, Sentiment.ANGRY}
        trend = prior_sentiment_trend or []
        sentiment_worsening = (
            len(trend) >= 2 and
            all(s in negative_states for s in trend[-2:])
        )

        return EscalationOutput(
            should_escalate=decision.should_escalate,
            reason=decision.reason,
            level=decision.level,
            rule_triggered=decision.rule,
            sentiment_worsening=sentiment_worsening,
            troubleshooting_exhausted=troubleshooting_attempts >= 2,
        )


# ─────────────────────────────────────────────────────────────────────────────
# Skill 4 — Channel Adaptation
# ─────────────────────────────────────────────────────────────────────────────

class ChannelAdaptationSkill:
    """
    TRIGGER: Before sending any response — always the final step before delivery.

    INPUTS:  response_text (str), channel (Channel), customer_name (str)
    OUTPUTS: ChannelAdaptationOutput
    """

    name = "channel_adaptation"
    trigger = "Before sending any response — final formatting step"

    def run(
        self,
        response_text: str,
        channel: Channel,
        customer_name: str = "",
    ) -> ChannelAdaptationOutput:
        formatted = formatter.format_for_channel(
            response=response_text,
            channel=channel,
            customer_name=customer_name,
        )

        original_len = len(response_text)
        formatted_len = len(formatted)
        truncated = formatted_len < original_len - 50   # significant shortening

        return ChannelAdaptationOutput(
            formatted_response=formatted,
            channel=channel,
            word_count=len(formatted.split()),
            char_count=formatted_len,
            truncated=truncated,
        )


# ─────────────────────────────────────────────────────────────────────────────
# Skill 5 — Customer Identification
# ─────────────────────────────────────────────────────────────────────────────

class CustomerIdentificationSkill:
    """
    TRIGGER: On every incoming message — the very first skill to run.

    INPUTS:  email (str), phone (str), name (str), plan (str), channel (Channel),
             store (CustomerStore)
    OUTPUTS: CustomerIdentificationOutput
    """

    name = "customer_identification"
    trigger = "On every incoming message — first skill in the pipeline"

    def run(
        self,
        store,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        name: Optional[str] = None,
        plan: Optional[str] = None,
        channel: Optional[Channel] = None,
    ) -> CustomerIdentificationOutput:
        # Check if customer already exists before creating
        existing_by_email = email and email in store._email_index
        existing_by_phone = phone and phone in store._phone_index
        cross_channel_match = (
            (existing_by_email and phone and phone not in store._phone_index) or
            (existing_by_phone and email and email not in store._email_index)
        )
        is_existing = existing_by_email or existing_by_phone

        customer = store.identify_customer(
            email=email,
            phone=phone,
            name=name,
            plan=plan,
            channel=channel,
        )

        return CustomerIdentificationOutput(
            customer_id=customer.customer_id,
            is_new_customer=not is_existing,
            email=customer.email,
            phone=customer.phone,
            name=customer.name,
            plan=customer.plan,
            channels_used=[c.value for c in customer.channels_used],
            cross_channel_match=cross_channel_match,
        )


# ─────────────────────────────────────────────────────────────────────────────
# Skill 6 — Multi-Question Parser
# ─────────────────────────────────────────────────────────────────────────────

# Signals that separate questions within a single message
_QUESTION_SPLIT_PATTERNS = [
    r'\?\s+(?=[A-Z])',              # ? followed by capital letter
    r'\?\s+(?:also|additionally|and also|one more|another question)',
    r'\n+',                         # line breaks between questions
    r'(?<=[.!])\s+(?=(?:also|additionally|can you also|and can))',
]

_QUESTION_PATTERN = re.compile(r'[^.!?]*\?', re.DOTALL)


class MultiQuestionParserSkill:
    """
    TRIGGER: On email messages — emails frequently contain multiple questions.
             Run after customer identification, before knowledge base search.

    INPUTS:  message (str), channel (Channel)
    OUTPUTS: MultiQuestionOutput

    NOTE: For WhatsApp and Web Form, single-question assumption is usually safe.
          For email, ALWAYS run this skill.
    """

    name = "multi_question_parser"
    trigger = "On every email message — before knowledge base search"

    def run(self, message: str, channel: Channel) -> MultiQuestionOutput:
        if channel != Channel.EMAIL:
            # Non-email channels: treat as single question
            return MultiQuestionOutput(
                questions=[message.strip()],
                question_count=1,
                has_multiple_questions=False,
                original_message=message,
            )

        # Extract question sentences
        raw_questions = _QUESTION_PATTERN.findall(message)
        questions = [q.strip() for q in raw_questions if len(q.strip()) > 10]

        # Deduplicate and filter noise
        seen = set()
        unique_questions = []
        for q in questions:
            key = q.lower()[:40]
            if key not in seen:
                seen.add(key)
                unique_questions.append(q)

        if not unique_questions:
            unique_questions = [message.strip()]

        return MultiQuestionOutput(
            questions=unique_questions,
            question_count=len(unique_questions),
            has_multiple_questions=len(unique_questions) > 1,
            original_message=message,
        )


# ─────────────────────────────────────────────────────────────────────────────
# Skill 7 — Retention Trigger
# ─────────────────────────────────────────────────────────────────────────────

_CANCELLATION_SIGNALS = [
    (r'\bcancel\b', "cancel"),
    (r'\bcancel(lation|ling)?\b', "cancellation"),
    (r'\bswitching to\b', "switching to competitor"),
    (r'\bmoving (away|to a competitor)\b', "moving away"),
    (r'\bdone with\b', "done with product"),
    (r'\bnot (useful|working) for (me|us)\b', "product not working for them"),
    (r'\bstop(ping)? (my )?subscription\b', "stopping subscription"),
    (r'\bwant to (leave|quit|stop using)\b', "wants to leave"),
    (r'\bbefore i cancel\b', "pre-cancellation hesitation"),
]

_RETENTION_QUESTIONS = {
    "cancel": "Before I process that, can I ask — what's the main thing that isn't working for you?",
    "cancellation": "Before I process that, can I ask — what's the main thing that isn't working for you?",
    "switching to competitor": "I understand — what's the feature you're hoping to find elsewhere? I'd love to see if we can help.",
    "moving away": "I'd hate to see you go — is there a specific issue that's been frustrating you?",
    "done with product": "I'm sorry to hear that. Can you tell me what's not clicking? We might be able to fix it.",
    "product not working for them": "Happy to help figure that out — what part of your workflow isn't fitting?",
    "stopping subscription": "Before you do, can I ask what's been the biggest pain point?",
    "wants to leave": "I understand. What would make EstateFlow work better for you?",
    "pre-cancellation hesitation": "Of course — what specifically feels hard or confusing about the pipeline right now?",
}


class RetentionTriggerSkill:
    """
    TRIGGER: When cancellation language is detected in any message.
             Run BEFORE escalation decision — give retention one chance first.

    INPUTS:  message (str)
    OUTPUTS: RetentionTriggerOutput

    BEHAVIOR:
    - If cancellation language is found, return a retention question to ask
    - The agent should ask the question BEFORE following escalation rules
    - If the customer confirms they want to cancel despite engagement,
      THEN escalate per Rule 3
    """

    name = "retention_trigger"
    trigger = "When cancellation language is detected in the customer message"

    def run(self, message: str) -> RetentionTriggerOutput:
        text = message.lower()

        for pattern, signal_name in _CANCELLATION_SIGNALS:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                retention_question = _RETENTION_QUESTIONS.get(
                    signal_name,
                    "Before we proceed, can I ask what isn't working for you?"
                )
                return RetentionTriggerOutput(
                    cancellation_detected=True,
                    signal_phrase=match.group(0),
                    retention_question=retention_question,
                    escalate_if_confirmed=True,
                )

        return RetentionTriggerOutput(
            cancellation_detected=False,
            signal_phrase=None,
            retention_question="",
            escalate_if_confirmed=False,
        )


# ─────────────────────────────────────────────────────────────────────────────
# Skills registry — single place to access all skills
# ─────────────────────────────────────────────────────────────────────────────

class SkillsRegistry:
    """
    Central registry of all agent skills.
    Access skills via registry.skill_name
    """

    def __init__(self):
        self.knowledge_retrieval    = KnowledgeRetrievalSkill()
        self.sentiment_analysis     = SentimentAnalysisSkill()
        self.escalation_decision    = EscalationDecisionSkill()
        self.channel_adaptation     = ChannelAdaptationSkill()
        self.customer_identification = CustomerIdentificationSkill()
        self.multi_question_parser  = MultiQuestionParserSkill()
        self.retention_trigger      = RetentionTriggerSkill()

    def list_skills(self) -> list[dict]:
        skills = [
            self.knowledge_retrieval,
            self.sentiment_analysis,
            self.escalation_decision,
            self.channel_adaptation,
            self.customer_identification,
            self.multi_question_parser,
            self.retention_trigger,
        ]
        return [{"name": s.name, "trigger": s.trigger} for s in skills]


# Default registry instance
registry = SkillsRegistry()
