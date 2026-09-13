"""
Unit and Integration Tests for the SpotifyCares AI Support Agent.
"""

import os
import sys
import unittest

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.agent import (
    SpotifySupportAgent,
    TaxonomyIntent,
    AgentAction,
    EscalationReason
)


class TestSpotifySupportAgent(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.agent = SpotifySupportAgent()

    # 1. Normal Client-Side Troubleshooting
    def test_client_side_troubleshooting_playback(self):
        query = "My bluetooth speaker keeps disconnecting and music skips on android"
        resp = self.agent.process(query)
        self.assertEqual(resp.intent, TaxonomyIntent.PLAYBACK_AND_AUDIO)
        self.assertEqual(resp.expected_action, AgentAction.DIRECT_TROUBLESHOOT)
        self.assertFalse(resp.requires_escalation)
        self.assertEqual(resp.escalation_reason, EscalationReason.NA)
        self.assertTrue(len(resp.generated_response) > 20)

    def test_client_side_troubleshooting_crash(self):
        query = "Spotify app crashes immediately on launch with black screen on iPhone"
        resp = self.agent.process(query)
        self.assertEqual(resp.intent, TaxonomyIntent.APP_CRASH_AND_PERFORMANCE)
        self.assertEqual(resp.expected_action, AgentAction.DIRECT_TROUBLESHOOT)
        self.assertFalse(resp.requires_escalation)

    def test_client_side_troubleshooting_offline(self):
        query = "My downloaded songs won't play offline on airplane mode"
        resp = self.agent.process(query)
        self.assertEqual(resp.intent, TaxonomyIntent.OFFLINE_LISTENING_AND_DOWNLOADS)
        self.assertEqual(resp.expected_action, AgentAction.DIRECT_TROUBLESHOOT)
        self.assertFalse(resp.requires_escalation)

    def test_client_side_troubleshooting_playlist(self):
        query = "My shuffle button keeps playing the exact same 5 songs in my playlist"
        resp = self.agent.process(query)
        self.assertEqual(resp.intent, TaxonomyIntent.PLAYLIST_LIBRARY_AND_CURATION)
        self.assertEqual(resp.expected_action, AgentAction.DIRECT_TROUBLESHOOT)
        self.assertFalse(resp.requires_escalation)

    # 2. Billing Issues Requiring Escalation
    def test_billing_refund_escalation(self):
        query = "I was charged twice on my credit card for Premium and I need a refund"
        resp = self.agent.process(query)
        self.assertEqual(resp.intent, TaxonomyIntent.SUBSCRIPTION_AND_BILLING)
        self.assertEqual(resp.expected_action, AgentAction.ESCALATE_TO_HUMAN_DM)
        self.assertEqual(resp.escalation_reason, EscalationReason.BILLING_RECEIPT_OR_PAYMENT_VERIFICATION)
        self.assertTrue(resp.requires_escalation)
        self.assertIn("https://t.co/ldFdZRiNAt", resp.generated_response)

    def test_billing_student_verification_escalation(self):
        query = "My student discount SheerID verification was declined, cannot verify my college"
        resp = self.agent.process(query)
        self.assertEqual(resp.intent, TaxonomyIntent.SUBSCRIPTION_AND_BILLING)
        self.assertEqual(resp.expected_action, AgentAction.ESCALATE_TO_HUMAN_DM)
        self.assertEqual(resp.escalation_reason, EscalationReason.STUDENT_OR_FAMILY_VERIFICATION_MANUAL_CHECK)
        self.assertTrue(resp.requires_escalation)

    def test_billing_general_public_inquiry(self):
        query = "How much does a Premium family plan cost per month?"
        resp = self.agent.process(query)
        self.assertEqual(resp.intent, TaxonomyIntent.SUBSCRIPTION_AND_BILLING)
        self.assertEqual(resp.expected_action, AgentAction.INFO_PROVISION)
        self.assertFalse(resp.requires_escalation)

    # 3. Account Access & Security Issues Requiring Escalation
    def test_account_hacked_escalation(self):
        query = "Someone changed my email and hacked my spotify account please help"
        resp = self.agent.process(query)
        self.assertEqual(resp.intent, TaxonomyIntent.ACCOUNT_ACCESS_AND_LOGIN)
        self.assertEqual(resp.expected_action, AgentAction.ESCALATE_TO_HUMAN_DM)
        self.assertEqual(resp.escalation_reason, EscalationReason.REQUIRES_ACCOUNT_BACKEND_ACCESS)
        self.assertTrue(resp.requires_escalation)

    def test_account_standard_password_reset(self):
        query = "Where can I reset password for my username?"
        resp = self.agent.process(query)
        self.assertEqual(resp.intent, TaxonomyIntent.ACCOUNT_ACCESS_AND_LOGIN)
        self.assertEqual(resp.expected_action, AgentAction.INFO_PROVISION)
        self.assertFalse(resp.requires_escalation)

    # 4. Vague Messages Requiring Clarification
    def test_vague_clarification_prompt(self):
        query = "My Spotify is broken please fix it"
        resp = self.agent.process(query)
        self.assertEqual(resp.intent, TaxonomyIntent.AMBIGUOUS_VAGUE)
        self.assertEqual(resp.expected_action, AgentAction.CLARIFICATION_PROMPT)
        self.assertFalse(resp.requires_escalation)
        self.assertIn("device", resp.generated_response.lower())
        self.assertIn("operating system", resp.generated_response.lower())

    # 5. Multi-Intent Handling
    def test_multi_intent_decomposition(self):
        query = "The app crashed while downloading songs and now my billing says expired"
        resp = self.agent.process(query)
        self.assertEqual(resp.intent, TaxonomyIntent.MULTI_INTENT)
        self.assertTrue(len(resp.sub_intents) >= 2)

    # 6. Non-Support Chatter
    def test_non_support_chatter(self):
        query = "Thank you so much Spotify, all sorted now cheers!"
        resp = self.agent.process(query)
        self.assertEqual(resp.intent, TaxonomyIntent.NON_SUPPORT_OR_CHATTER)
        self.assertEqual(resp.expected_action, AgentAction.INFO_PROVISION)
        self.assertFalse(resp.requires_escalation)

    # 7. Unclassifiable Foreign Language
    def test_foreign_language_redirection(self):
        query = "เพลงใน spotify ฟังไม่ได้ ช่วยหน่อยครับ"
        resp = self.agent.process(query)
        self.assertEqual(resp.intent, TaxonomyIntent.UNCLASSIFIABLE_OR_FOREIGN)
        self.assertEqual(resp.expected_action, AgentAction.INFO_PROVISION)
        self.assertIn("english", resp.generated_response.lower())

    # 8. Persistent Bug Escalation After Reinstallation
    def test_persistent_failure_escalation(self):
        query = "I've restarted and tried reinstalling several times but songs still pause"
        context = "Prior Turn [SpotifyCares]: Please restart your device"
        resp = self.agent.process(query, context=context)
        self.assertEqual(resp.intent, TaxonomyIntent.PLAYBACK_AND_AUDIO)
        self.assertEqual(resp.expected_action, AgentAction.ESCALATE_TO_HUMAN_DM)
        self.assertEqual(resp.escalation_reason, EscalationReason.PERSISTENT_BUG_INTERNAL_LOGS)
        self.assertTrue(resp.requires_escalation)

    # 9. Context Awareness
    def test_context_awareness(self):
        query = "iOS 11.2 and iPhone 7, music keeps cutting out"
        context = "Prior Turn [SpotifyCares]: What device and OS are you running?"
        resp = self.agent.process(query, context=context)
        self.assertEqual(resp.intent, TaxonomyIntent.PLAYBACK_AND_AUDIO)
        self.assertEqual(resp.expected_action, AgentAction.DIRECT_TROUBLESHOOT)


if __name__ == '__main__':
    unittest.main()
