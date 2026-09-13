"""
Main Orchestrator for the SpotifyCares AI Support Agent.

Integrates:
- Intent Classification (classifier.py)
- Historical Resolution Retrieval (retriever.py)
- Escalation Policy Enforcement (policy.py)
- Conversational Response Generation (generator.py)
"""

from typing import Optional
from .types import AgentResponse
from .classifier import IntentClassifier
from .retriever import ResolutionRetriever
from .policy import PolicyEngine
from .generator import ResponseGenerator


class SpotifySupportAgent:
    """End-to-end AI Support Agent for Spotify customer support."""

    def __init__(
        self,
        classifier: Optional[IntentClassifier] = None,
        retriever: Optional[ResolutionRetriever] = None,
        policy: Optional[PolicyEngine] = None,
        generator: Optional[ResponseGenerator] = None,
        agent_signoff: str = "/AY"
    ):
        self.classifier = classifier or IntentClassifier()
        self.retriever = retriever or ResolutionRetriever()
        self.policy = policy or PolicyEngine()
        self.generator = generator or ResponseGenerator(agent_signoff=agent_signoff)

    def process(self, message: str, context: Optional[str] = None) -> AgentResponse:
        """
        Processes an incoming customer message and optional conversation context.
        Returns a structured AgentResponse dataclass.
        """
        clean_msg = message.strip() if message else ""
        clean_ctx = context.strip() if context else "None (thread root)"

        # 1. Classify Intent & Sub-Intents
        intent, sub_intents, confidence, cls_rationale = self.classifier.classify(
            clean_msg, context=context
        )

        # 2. Retrieve Relevant Historical Resolution
        historical_res, res_source, match_score = self.retriever.retrieve(
            intent=intent, query=clean_msg, context=context
        )

        # 3. Evaluate Escalation Policy
        expected_action, escalation_reason, requires_esc, policy_rationale = self.policy.evaluate(
            intent=intent,
            sub_intents=sub_intents,
            message=clean_msg,
            context=context
        )

        # 4. Generate Customer Response
        generated_resp = self.generator.generate(
            intent=intent,
            sub_intents=sub_intents,
            expected_action=expected_action,
            escalation_reason=escalation_reason,
            retrieved_resolution=historical_res,
            customer_message=clean_msg,
            conversation_context=clean_ctx
        )

        full_rationale = f"{cls_rationale} Policy: {policy_rationale}"

        return AgentResponse(
            customer_message=clean_msg,
            conversation_context=clean_ctx,
            intent=intent,
            sub_intents=sub_intents,
            confidence=confidence,
            expected_action=expected_action,
            escalation_reason=escalation_reason,
            requires_escalation=requires_esc,
            historical_reference=historical_res,
            generated_response=generated_resp,
            rationale=full_rationale
        )
