"""
Data models and constants for the SpotifyCares AI Support Agent.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any


class TaxonomyIntent:
    SUBSCRIPTION_AND_BILLING = 'subscription_and_billing'
    MUSIC_CATALOG_AND_CONTENT = 'music_catalog_and_content'
    PLAYLIST_LIBRARY_AND_CURATION = 'playlist_library_and_curation'
    ACCOUNT_ACCESS_AND_LOGIN = 'account_access_and_login'
    PLAYBACK_AND_AUDIO = 'playback_and_audio'
    OFFLINE_LISTENING_AND_DOWNLOADS = 'offline_listening_and_downloads'
    SERVICE_OUTAGE_AND_STATUS = 'service_outage_and_status'
    APP_CRASH_AND_PERFORMANCE = 'app_crash_and_performance'
    AMBIGUOUS_VAGUE = 'ambiguous_vague'
    MULTI_INTENT = 'multi_intent'
    NON_SUPPORT_OR_CHATTER = 'non_support_or_chatter'
    UNCLASSIFIABLE_OR_FOREIGN = 'unclassifiable_or_foreign'

    ALL = [
        SUBSCRIPTION_AND_BILLING,
        MUSIC_CATALOG_AND_CONTENT,
        PLAYLIST_LIBRARY_AND_CURATION,
        ACCOUNT_ACCESS_AND_LOGIN,
        PLAYBACK_AND_AUDIO,
        OFFLINE_LISTENING_AND_DOWNLOADS,
        SERVICE_OUTAGE_AND_STATUS,
        APP_CRASH_AND_PERFORMANCE,
        AMBIGUOUS_VAGUE,
        MULTI_INTENT,
        NON_SUPPORT_OR_CHATTER,
        UNCLASSIFIABLE_OR_FOREIGN
    ]


class AgentAction:
    DIRECT_TROUBLESHOOT = 'DIRECT_TROUBLESHOOT'
    INFO_PROVISION = 'INFO_PROVISION'
    CLARIFICATION_PROMPT = 'CLARIFICATION_PROMPT'
    ESCALATE_TO_HUMAN_DM = 'ESCALATE_TO_HUMAN_DM'

    ALL = [
        DIRECT_TROUBLESHOOT,
        INFO_PROVISION,
        CLARIFICATION_PROMPT,
        ESCALATE_TO_HUMAN_DM
    ]


class EscalationReason:
    NA = 'N/A'
    BILLING_RECEIPT_OR_PAYMENT_VERIFICATION = 'BILLING_RECEIPT_OR_PAYMENT_VERIFICATION'
    REQUIRES_ACCOUNT_BACKEND_ACCESS = 'REQUIRES_ACCOUNT_BACKEND_ACCESS'
    PERSISTENT_BUG_INTERNAL_LOGS = 'PERSISTENT_BUG_INTERNAL_LOGS'
    COMPLEX_MULTI_ISSUE_ACCOUNT_AUDIT = 'COMPLEX_MULTI_ISSUE_ACCOUNT_AUDIT'
    STUDENT_OR_FAMILY_VERIFICATION_MANUAL_CHECK = 'STUDENT_OR_FAMILY_VERIFICATION_MANUAL_CHECK'
    OTHER_ESCALATION = 'OTHER_ESCALATION'


@dataclass
class AgentResponse:
    customer_message: str
    conversation_context: str
    intent: str
    sub_intents: List[str] = field(default_factory=list)
    confidence: float = 1.0
    expected_action: str = AgentAction.DIRECT_TROUBLESHOOT
    escalation_reason: str = EscalationReason.NA
    requires_escalation: bool = False
    historical_reference: str = ""
    generated_response: str = ""
    rationale: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            'customer_message': self.customer_message,
            'conversation_context': self.conversation_context,
            'intent': self.intent,
            'sub_intents': self.sub_intents,
            'confidence': round(self.confidence, 2),
            'expected_action': self.expected_action,
            'escalation_reason': self.escalation_reason,
            'requires_escalation': self.requires_escalation,
            'historical_reference': self.historical_reference,
            'generated_response': self.generated_response,
            'rationale': self.rationale
        }
