"""
Escalation Policy Engine for SpotifyCares.

Enforces strict boundaries between:
- AUTO-HANDLE (DIRECT_TROUBLESHOOT, INFO_PROVISION)
- CLARIFICATION_PROMPT (ambiguous/vague queries)
- ESCALATE_TO_HUMAN_DM (financial transactions, credentials, persistent bugs)
"""

import re
from typing import Optional, List, Tuple
from .types import TaxonomyIntent, AgentAction, EscalationReason


class PolicyEngine:
    """Evaluates customer complaints and conversation context against SpotifyCares escalation policies."""

    def __init__(self):
        self.billing_escalation_keywords = re.compile(
            r'\b(refund|money back|charged? (me )?(twice|again|extra)|double charge|receipt|overcharg(ed)?|deduct(ed)?|(unknown|unauthorized|extra|wrong) charge|card declined|bank|cancel(l?ing)? (my |the )?subscription)\b',
            re.I
        )
        self.account_escalation_keywords = re.compile(
            r'\b(hacked|hijack(ed)?|compromis(ed)?|stolen|unauthorized|locked out|breach(ed)?|email (was |got )?changed|reset (link|email) (not|never|doesn\'t|don\'t|didn\'t)|can\'t (reset|recover)|not receiving (the )?reset)\b',
            re.I
        )
        self.repeated_failure_keywords = re.compile(
            r'\b((clean )?reinstall(ed|ing)?|already (restarted|reinstalled|cleared)|cleared cache|tried (restarting|reinstalling|everything)|keeps? (crashing|freezing|failing|pausing|skipping|stuttering) (still|after)|still (not working|happening|crashing|freezing|persisting))\b',
            re.I
        )

    def evaluate(
        self,
        intent: str,
        sub_intents: List[str],
        message: str,
        context: Optional[str] = None
    ) -> Tuple[str, str, bool, str]:
        """
        Determines (expected_action, escalation_reason, requires_escalation, rationale).
        """
        msg_lower = message.lower()
        ctx_lower = (context or "").lower()
        full_text = f"{msg_lower} {ctx_lower}"

        # 1. SUBSCRIPTION AND BILLING
        if intent == TaxonomyIntent.SUBSCRIPTION_AND_BILLING:
            if self.billing_escalation_keywords.search(full_text) or 'dm' in full_text:
                return (
                    AgentAction.ESCALATE_TO_HUMAN_DM,
                    EscalationReason.BILLING_RECEIPT_OR_PAYMENT_VERIFICATION,
                    True,
                    "Billing dispute or refund request requires private financial receipt lookup in backend."
                )
            if 'student' in msg_lower and ('sheerid' in msg_lower or 'cannot verify' in msg_lower or 'declined' in msg_lower):
                return (
                    AgentAction.ESCALATE_TO_HUMAN_DM,
                    EscalationReason.STUDENT_OR_FAMILY_VERIFICATION_MANUAL_CHECK,
                    True,
                    "SheerID student verification failure requires manual agent inspection."
                )
            return (
                AgentAction.INFO_PROVISION,
                EscalationReason.NA,
                False,
                "General subscription tier, family plan rules, or public pricing inquiry."
            )

        # 2. ACCOUNT ACCESS AND LOGIN
        if intent == TaxonomyIntent.ACCOUNT_ACCESS_AND_LOGIN:
            if self.account_escalation_keywords.search(full_text) or 'dm' in full_text:
                return (
                    AgentAction.ESCALATE_TO_HUMAN_DM,
                    EscalationReason.REQUIRES_ACCOUNT_BACKEND_ACCESS,
                    True,
                    "Account recovery or suspected compromised account requires secure DM credential lookup."
                )
            return (
                AgentAction.INFO_PROVISION,
                EscalationReason.NA,
                False,
                "Standard password reset procedure via public official reset endpoint."
            )

        # 3. AMBIGUOUS / VAGUE
        if intent == TaxonomyIntent.AMBIGUOUS_VAGUE:
            return (
                AgentAction.CLARIFICATION_PROMPT,
                EscalationReason.NA,
                False,
                "Complaint lacks symptom details; must prompt for device, OS, and observed behavior before diagnosing."
            )

        # 4. MULTI-INTENT
        if intent == TaxonomyIntent.MULTI_INTENT:
            # Check if any sub-intent requires financial or security escalation
            if TaxonomyIntent.SUBSCRIPTION_AND_BILLING in sub_intents and self.billing_escalation_keywords.search(full_text):
                return (
                    AgentAction.ESCALATE_TO_HUMAN_DM,
                    EscalationReason.COMPLEX_MULTI_ISSUE_ACCOUNT_AUDIT,
                    True,
                    "Complex multi-issue includes billing dispute requiring private account audit."
                )
            if TaxonomyIntent.ACCOUNT_ACCESS_AND_LOGIN in sub_intents and self.account_escalation_keywords.search(full_text):
                return (
                    AgentAction.ESCALATE_TO_HUMAN_DM,
                    EscalationReason.REQUIRES_ACCOUNT_BACKEND_ACCESS,
                    True,
                    "Multi-issue includes account access failure requiring secure identity verification."
                )
            return (
                AgentAction.DIRECT_TROUBLESHOOT,
                EscalationReason.NA,
                False,
                "Multi-issue is composed of client-side technical problems; offer primary troubleshooting steps."
            )

        # 5. CLIENT-SIDE TECHNICAL INTENTS
        if intent in [
            TaxonomyIntent.PLAYBACK_AND_AUDIO,
            TaxonomyIntent.APP_CRASH_AND_PERFORMANCE,
            TaxonomyIntent.OFFLINE_LISTENING_AND_DOWNLOADS,
            TaxonomyIntent.PLAYLIST_LIBRARY_AND_CURATION
        ]:
            # If user explicitly states they already performed clean reinstall / standard troubleshooting
            if self.repeated_failure_keywords.search(full_text):
                return (
                    AgentAction.ESCALATE_TO_HUMAN_DM,
                    EscalationReason.PERSISTENT_BUG_INTERNAL_LOGS,
                    True,
                    "Client-side troubleshooting has been exhausted; escalate to DM for device logs."
                )
            return (
                AgentAction.DIRECT_TROUBLESHOOT,
                EscalationReason.NA,
                False,
                "Safe, repeatable client-side troubleshooting (restart, cache clearing, reinstall, settings check)."
            )

        # 6. MUSIC CATALOG AND CONTENT
        if intent == TaxonomyIntent.MUSIC_CATALOG_AND_CONTENT:
            return (
                AgentAction.INFO_PROVISION,
                EscalationReason.NA,
                False,
                "Public explanation of licensing rights, explicit filter settings, or regional availability."
            )

        # 7. SERVICE OUTAGE AND STATUS
        if intent == TaxonomyIntent.SERVICE_OUTAGE_AND_STATUS:
            return (
                AgentAction.INFO_PROVISION,
                EscalationReason.NA,
                False,
                "Acknowledge platform status incident and refer to @SpotifyStatus."
            )

        # 8. NON-SUPPORT OR CHATTER
        if intent == TaxonomyIntent.NON_SUPPORT_OR_CHATTER:
            return (
                AgentAction.INFO_PROVISION,
                EscalationReason.NA,
                False,
                "Polite social acknowledgment and closure; no escalation."
            )

        # 9. UNCLASSIFIABLE OR FOREIGN
        if intent == TaxonomyIntent.UNCLASSIFIABLE_OR_FOREIGN:
            return (
                AgentAction.INFO_PROVISION,
                EscalationReason.NA,
                False,
                "Redirect non-English query to official email support channel."
            )

        # Default fallback
        return (
            AgentAction.CLARIFICATION_PROMPT,
            EscalationReason.NA,
            False,
            "Default safety fallback: ask clarifying diagnostic questions."
        )
