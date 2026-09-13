"""
Conversational Response Generator for SpotifyCares.

Generates empathetic, actionable, and policy-compliant responses in the authentic
voice of @SpotifyCares, grounded in verified historical resolutions.
"""

from typing import Optional, List
from .types import TaxonomyIntent, AgentAction, EscalationReason


class ResponseGenerator:
    """Generates customer support replies tailored to intent, action, and escalation status."""

    def __init__(self, agent_signoff: str = "/AY"):
        self.agent_signoff = agent_signoff

    def generate(
        self,
        intent: str,
        sub_intents: List[str],
        expected_action: str,
        escalation_reason: str,
        retrieved_resolution: str,
        customer_message: str,
        conversation_context: Optional[str] = None
    ) -> str:
        """
        Synthesizes an agent response adhering to the escalation policy and authentic tone.
        """
        # 1. CLARIFICATION PROMPT (Ambiguous / Vague queries)
        if expected_action == AgentAction.CLARIFICATION_PROMPT:
            return (
                f"Hey! Help's here. Could you let us know what device, operating system, and "
                f"Spotify version you're running, and what's happening exactly? We'll see what we can suggest {self.agent_signoff}"
            )

        # 2. ESCALATION TO HUMAN DM
        if expected_action == AgentAction.ESCALATE_TO_HUMAN_DM:
            if escalation_reason == EscalationReason.BILLING_RECEIPT_OR_PAYMENT_VERIFICATION:
                return (
                    f"Hey! We'd be happy to take a closer look at your billing and subscription details. "
                    f"Could you send us a DM with your account's email address or username? We'll check backstage "
                    f"https://t.co/ldFdZRiNAt {self.agent_signoff}"
                )
            elif escalation_reason == EscalationReason.REQUIRES_ACCOUNT_BACKEND_ACCESS:
                return (
                    f"Hey, that doesn't sound right! To help you recover and secure your account safely, "
                    f"please send us a DM with the email address linked to your account: https://t.co/ldFdZRiNAt {self.agent_signoff}"
                )
            elif escalation_reason == EscalationReason.STUDENT_OR_FAMILY_VERIFICATION_MANUAL_CHECK:
                return (
                    f"Hi there! Verification issues can be tricky. Could you drop us a DM with your account email "
                    f"so we can check your SheerID or Family Plan invite backstage? https://t.co/ldFdZRiNAt {self.agent_signoff}"
                )
            elif escalation_reason == EscalationReason.PERSISTENT_BUG_INTERNAL_LOGS:
                return (
                    f"Thanks for trying those troubleshooting steps. Since the issue is still persisting, "
                    f"please send us a DM with your account username and device details so we can file an internal report "
                    f"https://t.co/ldFdZRiNAt {self.agent_signoff}"
                )
            else:
                return (
                    f"We'd like to look into this more closely for you. Please drop us a DM with your account's "
                    f"email address or username so we can assist backstage: https://t.co/ldFdZRiNAt {self.agent_signoff}"
                )

        # 3. DIRECT TROUBLESHOOTING (Client-side technical issues)
        if expected_action == AgentAction.DIRECT_TROUBLESHOOT:
            if retrieved_resolution:
                clean_res = retrieved_resolution.strip()
                if not clean_res.lower().startswith(('hey', 'hi', 'hello')):
                    clean_res = f"Hey! {clean_res}"
                if not clean_res.endswith(self.agent_signoff):
                    clean_res = f"{clean_res} {self.agent_signoff}"
                return clean_res
            return (
                f"Hey there! Can you try logging out, restarting your device, and logging back in? "
                f"If that doesn't help, try clearing your cache under Settings > Storage. Let us know how it goes! {self.agent_signoff}"
            )

        # 4. INFO PROVISION (Licensing, Status, Features, Gratitude)
        if expected_action == AgentAction.INFO_PROVISION:
            if intent == TaxonomyIntent.NON_SUPPORT_OR_CHATTER:
                return (
                    f"You're very welcome! If there's anything else we can ever help with, just give us a shout. "
                    f"Have a wonderful day 🙂 {self.agent_signoff}"
                )
            elif intent == TaxonomyIntent.UNCLASSIFIABLE_OR_FOREIGN:
                return (
                    f"We can only provide support in English via Twitter. For assistance in other languages, "
                    f"please reach out to our team at https://support.spotify.com/contact-spotify-support/ {self.agent_signoff}"
                )
            elif intent == TaxonomyIntent.SERVICE_OUTAGE_AND_STATUS:
                return (
                    f"We had a little hiccup backstage, but everything should be running smoothly now! "
                    f"You can also check live updates on @SpotifyStatus. Let us know if you're still having trouble {self.agent_signoff}"
                )
            elif retrieved_resolution:
                clean_res = retrieved_resolution.strip()
                if not clean_res.lower().startswith(('hey', 'hi', 'hello')):
                    clean_res = f"Hi there! {clean_res}"
                if not clean_res.endswith(self.agent_signoff):
                    clean_res = f"{clean_res} {self.agent_signoff}"
                return clean_res

        # Default fallback
        return (
            f"Hey there! Let us know your device and operating system, and we'll see what we can suggest. "
            f"We're here if you need us! {self.agent_signoff}"
        )
