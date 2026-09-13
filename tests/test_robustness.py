"""
Deterministic Robustness Test Suite for SpotifyCares AI Support Agent.

Audits unseen, realistic, and edge-case customer queries across ALL 12 taxonomy classes:
1. subscription_and_billing
2. music_catalog_and_content
3. playlist_library_and_curation
4. account_access_and_login
5. playback_and_audio
6. offline_listening_and_downloads
7. service_outage_and_status
8. app_crash_and_performance
9. ambiguous_vague
10. multi_intent
11. non_support_or_chatter
12. unclassifiable_or_foreign

Also verifies:
- Security/Privacy: never requests passwords, CVVs, or full payment card numbers.
- Escalation safety: financial disputes, account takeovers, and persistent failures escalate to human DM.
- Grounding: responses do not expose internal policy codes or internal rationale.
"""

import os
import sys
import unittest

# Ensure project root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.agent import (
    SpotifySupportAgent,
    TaxonomyIntent,
    AgentAction,
    EscalationReason
)


class TestAgentRobustness(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.agent = SpotifySupportAgent()

    def _assert_response_safety(self, resp):
        """Verifies that generated response complies with security & privacy standards."""
        gen_lower = resp.generated_response.lower()
        # 1. Must never request customer passwords, CVVs, or credit card numbers
        sensitive_patterns = [
            "send your password", "what is your password", "provide your password",
            "dm your password", "share your password", "tell us your password",
            "your secret", "cvv", "cvc", "card number", "credit card digits"
        ]
        for pat in sensitive_patterns:
            self.assertNotIn(pat, gen_lower, f"Agent must never request sensitive secret: {pat}")
        # 2. Must not expose internal policy enum names
        self.assertNotIn("direct_troubleshoot", gen_lower)
        self.assertNotIn("escalate_to_human_dm", gen_lower)
        self.assertNotIn("info_provision", gen_lower)
        self.assertNotIn("clarification_prompt", gen_lower)
        # 3. Must be non-empty and have authentic signoff
        self.assertTrue(len(resp.generated_response) > 25)
        self.assertTrue(resp.generated_response.endswith("/AY"))

    # =========================================================================
    # 1. SUBSCRIPTION AND BILLING
    # =========================================================================
    def test_billing_unauthorized_deduction_escalates(self):
        """Financial deduction requiring private transaction lookup must escalate to DM."""
        query = "Money was deducted from my bank but Premium did not activate"
        resp = self.agent.process(query)
        self.assertEqual(resp.intent, TaxonomyIntent.SUBSCRIPTION_AND_BILLING)
        self.assertEqual(resp.expected_action, AgentAction.ESCALATE_TO_HUMAN_DM)
        self.assertEqual(resp.escalation_reason, EscalationReason.BILLING_RECEIPT_OR_PAYMENT_VERIFICATION)
        self.assertTrue(resp.requires_escalation)
        self.assertIn("https://t.co/ldFdZRiNAt", resp.generated_response)
        self._assert_response_safety(resp)

    def test_billing_unknown_charge_escalates(self):
        """Dispute over unexpected charge must escalate."""
        query = "I see an unknown charge of $9.99 from Spotify on my statement"
        resp = self.agent.process(query)
        self.assertEqual(resp.intent, TaxonomyIntent.SUBSCRIPTION_AND_BILLING)
        self.assertEqual(resp.expected_action, AgentAction.ESCALATE_TO_HUMAN_DM)
        self.assertEqual(resp.escalation_reason, EscalationReason.BILLING_RECEIPT_OR_PAYMENT_VERIFICATION)
        self.assertTrue(resp.requires_escalation)
        self._assert_response_safety(resp)

    def test_billing_cancellation_refund_escalates(self):
        """Subscription cancellation with refund request must escalate."""
        query = "I want to cancel my subscription and get my money back"
        resp = self.agent.process(query)
        self.assertEqual(resp.intent, TaxonomyIntent.SUBSCRIPTION_AND_BILLING)
        self.assertEqual(resp.expected_action, AgentAction.ESCALATE_TO_HUMAN_DM)
        self.assertEqual(resp.escalation_reason, EscalationReason.BILLING_RECEIPT_OR_PAYMENT_VERIFICATION)
        self._assert_response_safety(resp)

    def test_billing_plan_comparison_info_provision(self):
        """General plan comparison is auto-handled via INFO_PROVISION without escalation."""
        query = "Can I have two people on a regular Premium plan or do we need family?"
        resp = self.agent.process(query)
        self.assertEqual(resp.intent, TaxonomyIntent.SUBSCRIPTION_AND_BILLING)
        self.assertEqual(resp.expected_action, AgentAction.INFO_PROVISION)
        self.assertFalse(resp.requires_escalation)
        self._assert_response_safety(resp)

    def test_billing_student_sheerid_escalates(self):
        """SheerID verification failures must escalate with specific reason."""
        query = "My college enrollment cannot be verified by SheerID for student discount"
        resp = self.agent.process(query)
        self.assertEqual(resp.intent, TaxonomyIntent.SUBSCRIPTION_AND_BILLING)
        self.assertEqual(resp.expected_action, AgentAction.ESCALATE_TO_HUMAN_DM)
        self.assertEqual(resp.escalation_reason, EscalationReason.STUDENT_OR_FAMILY_VERIFICATION_MANUAL_CHECK)
        self._assert_response_safety(resp)

    # =========================================================================
    # 2. ACCOUNT ACCESS AND LOGIN
    # =========================================================================
    def test_account_compromised_escalates(self):
        """Compromised account must escalate to DM with REQUIRES_ACCOUNT_BACKEND_ACCESS."""
        query = "My account was compromised and the email was changed"
        resp = self.agent.process(query)
        self.assertEqual(resp.intent, TaxonomyIntent.ACCOUNT_ACCESS_AND_LOGIN)
        self.assertEqual(resp.expected_action, AgentAction.ESCALATE_TO_HUMAN_DM)
        self.assertEqual(resp.escalation_reason, EscalationReason.REQUIRES_ACCOUNT_BACKEND_ACCESS)
        self.assertTrue(resp.requires_escalation)
        self._assert_response_safety(resp)

    def test_account_locked_out_reset_fails_escalates(self):
        """Locked out customer not receiving reset links must escalate."""
        query = "I am locked out of my account and I don't get the password reset link"
        resp = self.agent.process(query)
        self.assertEqual(resp.intent, TaxonomyIntent.ACCOUNT_ACCESS_AND_LOGIN)
        self.assertEqual(resp.expected_action, AgentAction.ESCALATE_TO_HUMAN_DM)
        self.assertEqual(resp.escalation_reason, EscalationReason.REQUIRES_ACCOUNT_BACKEND_ACCESS)
        self._assert_response_safety(resp)

    def test_account_change_password_inquiry_info(self):
        """How-to password change inquiry is informational."""
        query = "How do I change my password if I know my old one?"
        resp = self.agent.process(query)
        self.assertEqual(resp.intent, TaxonomyIntent.ACCOUNT_ACCESS_AND_LOGIN)
        self.assertEqual(resp.expected_action, AgentAction.INFO_PROVISION)
        self.assertFalse(resp.requires_escalation)
        self._assert_response_safety(resp)

    def test_account_username_change_info(self):
        """Username inquiry is informational."""
        query = "Can I change my username on Spotify?"
        resp = self.agent.process(query)
        self.assertEqual(resp.intent, TaxonomyIntent.ACCOUNT_ACCESS_AND_LOGIN)
        self.assertEqual(resp.expected_action, AgentAction.INFO_PROVISION)
        self._assert_response_safety(resp)

    # =========================================================================
    # 3. PLAYBACK AND AUDIO
    # =========================================================================
    def test_playback_car_bluetooth_troubleshoot(self):
        """Car bluetooth playback glitch should auto-handle via DIRECT_TROUBLESHOOT."""
        query = "Music cuts out whenever my phone connects to car bluetooth"
        resp = self.agent.process(query)
        self.assertEqual(resp.intent, TaxonomyIntent.PLAYBACK_AND_AUDIO)
        self.assertEqual(resp.expected_action, AgentAction.DIRECT_TROUBLESHOOT)
        self.assertFalse(resp.requires_escalation)
        self._assert_response_safety(resp)

    def test_playback_audio_distortion_troubleshoot(self):
        """Crackling / distortion audio should auto-handle."""
        query = "There is a strange crackling distortion sound on every song"
        resp = self.agent.process(query)
        self.assertEqual(resp.intent, TaxonomyIntent.PLAYBACK_AND_AUDIO)
        self.assertEqual(resp.expected_action, AgentAction.DIRECT_TROUBLESHOOT)
        self._assert_response_safety(resp)

    def test_playback_random_pause_troubleshoot(self):
        """Random pause glitch should auto-handle."""
        query = "Songs randomly pause every 30 seconds"
        resp = self.agent.process(query)
        self.assertEqual(resp.intent, TaxonomyIntent.PLAYBACK_AND_AUDIO)
        self.assertEqual(resp.expected_action, AgentAction.DIRECT_TROUBLESHOOT)
        self._assert_response_safety(resp)

    def test_playback_persistent_failure_escalates(self):
        """Persistent playback failure after restart & reinstall must escalate."""
        query = "I already restarted my phone and reinstalled Spotify but songs still stutter"
        context = "Prior Turn [SpotifyCares]: Please restart your device"
        resp = self.agent.process(query, context=context)
        self.assertEqual(resp.intent, TaxonomyIntent.PLAYBACK_AND_AUDIO)
        self.assertEqual(resp.expected_action, AgentAction.ESCALATE_TO_HUMAN_DM)
        self.assertEqual(resp.escalation_reason, EscalationReason.PERSISTENT_BUG_INTERNAL_LOGS)
        self.assertTrue(resp.requires_escalation)
        self._assert_response_safety(resp)

    # =========================================================================
    # 4. APP CRASH AND PERFORMANCE
    # =========================================================================
    def test_crash_launch_freeze_troubleshoot(self):
        """Crash on launch is client-side technical issue."""
        query = "The app instantly closes as soon as I tap the icon"
        resp = self.agent.process(query)
        self.assertEqual(resp.intent, TaxonomyIntent.APP_CRASH_AND_PERFORMANCE)
        self.assertEqual(resp.expected_action, AgentAction.DIRECT_TROUBLESHOOT)
        self._assert_response_safety(resp)

    def test_crash_black_screen_troubleshoot(self):
        """Black screen freeze should auto-handle with storage/cache steps."""
        query = "Spotify completely freezes on a black screen when browsing"
        resp = self.agent.process(query)
        self.assertEqual(resp.intent, TaxonomyIntent.APP_CRASH_AND_PERFORMANCE)
        self.assertEqual(resp.expected_action, AgentAction.DIRECT_TROUBLESHOOT)
        self._assert_response_safety(resp)

    def test_crash_persistent_after_reinstall_escalates(self):
        """Crash persisting after clean reinstall must escalate for device logs."""
        query = "I did a clean reinstall and cleared cache but it keeps crashing on startup"
        context = "Prior Turn [SpotifyCares]: Try a clean reinstall of Spotify"
        resp = self.agent.process(query, context=context)
        self.assertEqual(resp.intent, TaxonomyIntent.APP_CRASH_AND_PERFORMANCE)
        self.assertEqual(resp.expected_action, AgentAction.ESCALATE_TO_HUMAN_DM)
        self.assertEqual(resp.escalation_reason, EscalationReason.PERSISTENT_BUG_INTERNAL_LOGS)
        self._assert_response_safety(resp)

    # =========================================================================
    # 5. OFFLINE LISTENING AND DOWNLOADS
    # =========================================================================
    def test_offline_subway_no_wifi_troubleshoot(self):
        """Offline playback failure without internet should auto-handle."""
        query = "My downloaded albums will not play on the subway without internet"
        resp = self.agent.process(query)
        self.assertEqual(resp.intent, TaxonomyIntent.OFFLINE_LISTENING_AND_DOWNLOADS)
        self.assertEqual(resp.expected_action, AgentAction.DIRECT_TROUBLESHOOT)
        self._assert_response_safety(resp)

    def test_offline_limit_sd_card_troubleshoot(self):
        """Download limit and SD card storage troubleshooting."""
        query = "Why does it say I reached the maximum download limit on my SD card?"
        resp = self.agent.process(query)
        self.assertEqual(resp.intent, TaxonomyIntent.OFFLINE_LISTENING_AND_DOWNLOADS)
        self.assertEqual(resp.expected_action, AgentAction.DIRECT_TROUBLESHOOT)
        self._assert_response_safety(resp)

    def test_offline_disappeared_30_days_troubleshoot(self):
        """Disappeared offline downloads inquiry."""
        query = "All my offline songs disappeared overnight"
        resp = self.agent.process(query)
        self.assertEqual(resp.intent, TaxonomyIntent.OFFLINE_LISTENING_AND_DOWNLOADS)
        self.assertEqual(resp.expected_action, AgentAction.DIRECT_TROUBLESHOOT)
        self._assert_response_safety(resp)

    # =========================================================================
    # 6. PLAYLIST LIBRARY AND CURATION
    # =========================================================================
    def test_playlist_accidental_delete_troubleshoot(self):
        """Accidentally deleted playlist recovery guidance."""
        query = "I accidentally deleted my favorite playlist can I recover it?"
        resp = self.agent.process(query)
        self.assertEqual(resp.intent, TaxonomyIntent.PLAYLIST_LIBRARY_AND_CURATION)
        self.assertEqual(resp.expected_action, AgentAction.DIRECT_TROUBLESHOOT)
        self._assert_response_safety(resp)

    def test_playlist_shuffle_same_songs_troubleshoot(self):
        """Shuffle algorithm repeat issue."""
        query = "Shuffle is broken, it plays the same 10 songs in exact same order"
        resp = self.agent.process(query)
        self.assertEqual(resp.intent, TaxonomyIntent.PLAYLIST_LIBRARY_AND_CURATION)
        self.assertEqual(resp.expected_action, AgentAction.DIRECT_TROUBLESHOOT)
        self._assert_response_safety(resp)

    def test_playlist_local_files_sync_troubleshoot(self):
        """Local files syncing between devices."""
        query = "My local files are not syncing from desktop to my phone library"
        resp = self.agent.process(query)
        self.assertEqual(resp.intent, TaxonomyIntent.PLAYLIST_LIBRARY_AND_CURATION)
        self.assertEqual(resp.expected_action, AgentAction.DIRECT_TROUBLESHOOT)
        self._assert_response_safety(resp)

    # =========================================================================
    # 7. MUSIC CATALOG AND CONTENT
    # =========================================================================
    def test_catalog_greyed_out_licensing_info(self):
        """Greyed out songs due to licensing rights."""
        query = "Why are half the songs on this album greyed out and unavailable?"
        resp = self.agent.process(query)
        self.assertEqual(resp.intent, TaxonomyIntent.MUSIC_CATALOG_AND_CONTENT)
        self.assertEqual(resp.expected_action, AgentAction.INFO_PROVISION)
        self._assert_response_safety(resp)

    def test_catalog_explicit_censored_info(self):
        """Explicit content filter settings."""
        query = "The explicit version of the album is censored, how do I uncensor it?"
        resp = self.agent.process(query)
        self.assertEqual(resp.intent, TaxonomyIntent.MUSIC_CATALOG_AND_CONTENT)
        self.assertEqual(resp.expected_action, AgentAction.INFO_PROVISION)
        self._assert_response_safety(resp)

    def test_catalog_release_timing_info(self):
        """Artist album release timing inquiry."""
        query = "When will the new Drake album be released on Spotify?"
        resp = self.agent.process(query)
        self.assertEqual(resp.intent, TaxonomyIntent.MUSIC_CATALOG_AND_CONTENT)
        self.assertEqual(resp.expected_action, AgentAction.INFO_PROVISION)
        self._assert_response_safety(resp)

    # =========================================================================
    # 8. SERVICE OUTAGE AND STATUS
    # =========================================================================
    def test_outage_server_error_500_info(self):
        """500 server error / platform outage inquiry."""
        query = "Is Spotify down right now? Keep getting 500 server error"
        resp = self.agent.process(query)
        self.assertEqual(resp.intent, TaxonomyIntent.SERVICE_OUTAGE_AND_STATUS)
        self.assertEqual(resp.expected_action, AgentAction.INFO_PROVISION)
        self.assertIn("@SpotifyStatus", resp.generated_response)
        self._assert_response_safety(resp)

    def test_outage_widespread_report_info(self):
        """Widespread outage confirmation."""
        query = "Is there an outage? None of my friends can connect either"
        resp = self.agent.process(query)
        self.assertEqual(resp.intent, TaxonomyIntent.SERVICE_OUTAGE_AND_STATUS)
        self.assertEqual(resp.expected_action, AgentAction.INFO_PROVISION)
        self._assert_response_safety(resp)

    # =========================================================================
    # 9. AMBIGUOUS AND VAGUE COMPLAINTS
    # =========================================================================
    def test_vague_not_working_clarification(self):
        """Unelaborated 'not working' complaint requires diagnostic questions."""
        query = "Spotify is not working"
        resp = self.agent.process(query)
        self.assertEqual(resp.intent, TaxonomyIntent.AMBIGUOUS_VAGUE)
        self.assertEqual(resp.expected_action, AgentAction.CLARIFICATION_PROMPT)
        self.assertIn("device", resp.generated_response.lower())
        self._assert_response_safety(resp)

    def test_vague_frustration_clarification(self):
        """Emotional complaint without technical symptoms requires clarification."""
        query = "Why does this app always suck so bad, please fix it"
        resp = self.agent.process(query)
        self.assertEqual(resp.intent, TaxonomyIntent.AMBIGUOUS_VAGUE)
        self.assertEqual(resp.expected_action, AgentAction.CLARIFICATION_PROMPT)
        self._assert_response_safety(resp)

    def test_vague_ultra_short_clarification(self):
        """Ultra-short complaint."""
        query = "It is broken again"
        resp = self.agent.process(query)
        self.assertEqual(resp.intent, TaxonomyIntent.AMBIGUOUS_VAGUE)
        self.assertEqual(resp.expected_action, AgentAction.CLARIFICATION_PROMPT)
        self._assert_response_safety(resp)

    # =========================================================================
    # 10. MULTI-INTENT COMPOSITE CASES
    # =========================================================================
    def test_multi_intent_technical_and_billing(self):
        """Crash combined with expired billing."""
        query = "The app crashed while downloading songs and now my billing says expired"
        resp = self.agent.process(query)
        self.assertEqual(resp.intent, TaxonomyIntent.MULTI_INTENT)
        self.assertTrue(len(resp.sub_intents) >= 2)
        self._assert_response_safety(resp)

    def test_multi_intent_playback_and_offline(self):
        """Playback stutter combined with offline download disappearance."""
        query = "Music keeps pausing on bluetooth and my downloaded songs disappeared"
        resp = self.agent.process(query)
        self.assertEqual(resp.intent, TaxonomyIntent.MULTI_INTENT)
        self.assertTrue(len(resp.sub_intents) >= 2)
        self.assertIn(TaxonomyIntent.PLAYBACK_AND_AUDIO, resp.sub_intents)
        self.assertIn(TaxonomyIntent.OFFLINE_LISTENING_AND_DOWNLOADS, resp.sub_intents)
        self._assert_response_safety(resp)

    def test_multi_intent_hacked_and_deleted_playlists_escalates(self):
        """Account takeover combined with deleted playlists must prioritize security escalation."""
        query = "My account was hacked and they deleted my saved playlists"
        resp = self.agent.process(query)
        self.assertEqual(resp.intent, TaxonomyIntent.MULTI_INTENT)
        self.assertEqual(resp.expected_action, AgentAction.ESCALATE_TO_HUMAN_DM)
        self.assertEqual(resp.escalation_reason, EscalationReason.REQUIRES_ACCOUNT_BACKEND_ACCESS)
        self.assertTrue(resp.requires_escalation)
        self._assert_response_safety(resp)

    # =========================================================================
    # 11. NON-SUPPORT CHATTER AND SOCIAL
    # =========================================================================
    def test_chatter_gratitude_closure(self):
        """Polite closure after issue resolution."""
        query = "Thanks a lot for the quick help, everything works now!"
        resp = self.agent.process(query)
        self.assertEqual(resp.intent, TaxonomyIntent.NON_SUPPORT_OR_CHATTER)
        self.assertEqual(resp.expected_action, AgentAction.INFO_PROVISION)
        self.assertFalse(resp.requires_escalation)
        self._assert_response_safety(resp)

    def test_chatter_social_praise(self):
        """Praise / social banter should acknowledge politely without troubleshooting."""
        query = "Spotify Wrapped is so good this year, you guys rock"
        resp = self.agent.process(query)
        self.assertEqual(resp.intent, TaxonomyIntent.NON_SUPPORT_OR_CHATTER)
        self.assertEqual(resp.expected_action, AgentAction.INFO_PROVISION)
        self._assert_response_safety(resp)

    def test_chatter_dm_notification(self):
        """DM notification from user."""
        query = "Sent you a DM with the details"
        resp = self.agent.process(query)
        self.assertEqual(resp.intent, TaxonomyIntent.NON_SUPPORT_OR_CHATTER)
        self.assertEqual(resp.expected_action, AgentAction.INFO_PROVISION)
        self._assert_response_safety(resp)

    # =========================================================================
    # 12. UNCLASSIFIABLE OR FOREIGN LANGUAGE
    # =========================================================================
    def test_foreign_spanish_redirect(self):
        """Spanish message redirects to official multi-lingual web support."""
        query = "Hola, no puedo escuchar mi musica en Spotify"
        resp = self.agent.process(query)
        self.assertEqual(resp.intent, TaxonomyIntent.UNCLASSIFIABLE_OR_FOREIGN)
        self.assertEqual(resp.expected_action, AgentAction.INFO_PROVISION)
        self.assertIn("english", resp.generated_response.lower())
        self._assert_response_safety(resp)

    def test_foreign_japanese_redirect(self):
        """Japanese characters redirect to official support."""
        query = "ログインができません。パスワードを忘れました。"
        resp = self.agent.process(query)
        self.assertEqual(resp.intent, TaxonomyIntent.UNCLASSIFIABLE_OR_FOREIGN)
        self.assertEqual(resp.expected_action, AgentAction.INFO_PROVISION)
        self._assert_response_safety(resp)

    def test_foreign_link_only_redirect(self):
        """Link only tweet without context."""
        query = "https://t.co/abc1234"
        resp = self.agent.process(query)
        self.assertEqual(resp.intent, TaxonomyIntent.UNCLASSIFIABLE_OR_FOREIGN)
        self.assertEqual(resp.expected_action, AgentAction.INFO_PROVISION)
        self._assert_response_safety(resp)

    # =========================================================================
    # 13. CONVERSATION CONTEXT & FOLLOW-UP TURNS
    # =========================================================================
    def test_context_diagnostic_os_for_crash(self):
        """Follow-up specifying device/OS when context mentions crashing."""
        query = "iOS 11.2, iPhone 8"
        context = "Prior Turn [SpotifyCares]: What device and OS are you using? Does the app keep crashing?"
        resp = self.agent.process(query, context=context)
        self.assertEqual(resp.intent, TaxonomyIntent.APP_CRASH_AND_PERFORMANCE)
        self.assertEqual(resp.expected_action, AgentAction.DIRECT_TROUBLESHOOT)
        self._assert_response_safety(resp)

    def test_context_connectivity_for_playback(self):
        """Follow-up on WiFi/cellular data when context mentions music stopping."""
        query = "Yes, tried on both WiFi and 4G"
        context = "Prior Turn [SpotifyCares]: Does music stop playing on cellular data or WiFi?"
        resp = self.agent.process(query, context=context)
        self.assertEqual(resp.intent, TaxonomyIntent.PLAYBACK_AND_AUDIO)
        self.assertEqual(resp.expected_action, AgentAction.DIRECT_TROUBLESHOOT)
        self._assert_response_safety(resp)

    def test_context_receipt_confirmation_for_billing(self):
        """Follow-up on missing receipt when context asks about Premium subscription confirmation."""
        query = "No receipt was emailed to me"
        context = "Prior Turn [SpotifyCares]: Did you get a confirmation email for your Premium subscription?"
        resp = self.agent.process(query, context=context)
        self.assertEqual(resp.intent, TaxonomyIntent.SUBSCRIPTION_AND_BILLING)
        self.assertEqual(resp.expected_action, AgentAction.ESCALATE_TO_HUMAN_DM)
        self.assertEqual(resp.escalation_reason, EscalationReason.BILLING_RECEIPT_OR_PAYMENT_VERIFICATION)
        self._assert_response_safety(resp)


if __name__ == '__main__':
    unittest.main()
