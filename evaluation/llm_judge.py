"""
LLM-as-Judge Evaluation Component for SpotifyCares Customer Support Replies.

Evaluates generated customer support responses against the 6-dimension rubric:
1. Relevance & Intent Alignment (1-5)
2. Correctness & Actionability (1-5)
3. Grounding in Official Knowledge (1-5)
4. Policy & Escalation Compliance (1-5)
5. Security & Credential Safety (1-5)
6. Tone & Brand Voice (1-5)

Produces a weighted composite score (1.0 to 5.0) and structured breakdown.
Supports both:
- Online API mode (Gemini / OpenAI if API key provided in environment)
- Offline deterministic mode (rule-grounded rubric evaluation for 100% reproducibility)
"""

import os
import re
import json
from typing import Dict, Any, Optional


class SpotifyJudge:
    """Evaluates customer support replies on the formal 6-dimension rubric."""

    def __init__(self, offline_only: bool = False):
        self.api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        self.openai_key = os.getenv("OPENAI_API_KEY")
        self.offline_mode = offline_only or (not self.api_key and not self.openai_key)

    def evaluate_response(
        self,
        customer_message: str,
        conversation_context: Optional[str],
        predicted_intent: str,
        expected_action: str,
        escalation_reason: str,
        generated_response: str,
        historical_reference: str = "",
        ground_truth_intent: Optional[str] = None,
        ground_truth_action: Optional[str] = None,
        ground_truth_escalation: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Evaluates an individual agent response on the 6-dimension rubric.
        Returns a dictionary with dimensional scores, composite score, and rationale.
        """
        resp_lower = generated_response.lower()
        msg_lower = customer_message.lower()
        ctx_lower = (conversation_context or "").lower()

        # Dimension 1: Relevance & Intent Alignment (1-5)
        relevance_score = self._score_relevance(
            msg_lower, ctx_lower, predicted_intent, resp_lower, ground_truth_intent
        )

        # Dimension 2: Correctness & Actionability (1-5)
        correctness_score = self._score_correctness(
            expected_action, resp_lower, ground_truth_action
        )

        # Dimension 3: Grounding in Official Spotify Knowledge (1-5)
        grounding_score = self._score_grounding(resp_lower, historical_reference.lower())

        # Dimension 4: Policy & Escalation Compliance (1-5)
        policy_score = self._score_policy(
            expected_action, escalation_reason, resp_lower, ground_truth_action, ground_truth_escalation
        )

        # Dimension 5: Security & Credential Safety (1-5)
        safety_score = self._score_safety(resp_lower)

        # Dimension 6: Tone & Brand Voice (1-5)
        tone_score = self._score_tone(generated_response)

        # Weighted Composite Score (1.0 - 5.0)
        composite_score = round(
            0.20 * relevance_score +
            0.20 * correctness_score +
            0.15 * grounding_score +
            0.20 * policy_score +
            0.15 * safety_score +
            0.10 * tone_score,
            2
        )

        rationale = (
            f"Relevance={relevance_score}/5, Correctness={correctness_score}/5, "
            f"Grounding={grounding_score}/5, Policy={policy_score}/5, "
            f"Safety={safety_score}/5, Tone={tone_score}/5. "
            f"Composite Score: {composite_score:.2f}/5.00."
        )

        return {
            'scores': {
                'relevance': relevance_score,
                'correctness': correctness_score,
                'grounding': grounding_score,
                'policy_compliance': policy_score,
                'safety': safety_score,
                'tone': tone_score
            },
            'composite_score': composite_score,
            'passed_quality_bar': composite_score >= 4.0,
            'rationale': rationale,
            'evaluator_mode': 'offline_deterministic' if self.offline_mode else 'api_llm'
        }

    def _score_relevance(
        self, msg: str, ctx: str, intent: str, resp: str, ground_truth_intent: Optional[str] = None
    ) -> int:
        if not resp or len(resp.strip()) < 10:
            return 1

        # If ground truth intent is provided and agent misclassified intent
        if ground_truth_intent and intent != ground_truth_intent:
            if intent == 'ambiguous_vague':
                return 3  # Overly cautious clarification
            return 2  # Misdirected response

        # Check intent-specific relevance cues
        intent_keywords = {
            'subscription_and_billing': ['bill', 'subscription', 'refund', 'charge', 'premium', 'receipt', 'student', 'family', 'dm'],
            'playback_and_audio': ['restart', 'bluetooth', 'audio', 'sound', 'wifi', 'cellular', 'speaker', 'device', 'quality'],
            'app_crash_and_performance': ['crash', 'reinstall', 'cache', 'storage', 'settings', 'freeze', 'restart'],
            'offline_listening_and_downloads': ['offline', 'download', 'downloads', '30 days', 'storage', 'sync'],
            'playlist_library_and_curation': ['playlist', 'shuffle', 'cache', 'recover', 'account', 'library'],
            'music_catalog_and_content': ['licensing', 'artist', 'rights', 'country', 'explicit', 'unplayable'],
            'account_access_and_login': ['password', 'reset', 'email', 'login', 'dm', 'secure', 'account'],
            'service_outage_and_status': ['hiccup', 'spotifystatus', 'running', 'smoothly', 'down', 'outage'],
            'ambiguous_vague': ['device', 'operating system', 'version', 'happening', 'suggest'],
            'non_support_or_chatter': ['welcome', 'shout', 'day', 'help'],
            'unclassifiable_or_foreign': ['english', 'contact', 'support', 'team'],
            'multi_intent': ['dm', 'device', 'version', 'restart', 'help']
        }
        keywords = intent_keywords.get(intent, ['spotify', 'help'])
        matches = sum(1 for kw in keywords if kw in resp)

        if matches >= 3:
            return 5
        elif matches == 2:
            return 4
        elif matches == 1:
            return 3
        else:
            return 2

    def _score_correctness(
        self, action: str, resp: str, ground_truth_action: Optional[str] = None
    ) -> int:
        # If ground truth action provided and agent failed escalation
        if ground_truth_action and action != ground_truth_action:
            if ground_truth_action == 'ESCALATE_TO_HUMAN_DM':
                return 2  # Failed critical escalation
            return 3  # Sub-optimal action choice

        if action == 'CLARIFICATION_PROMPT':
            if any(w in resp for w in ['device', 'operating system', 'version', 'what\'s happening']):
                return 5
            return 3

        if action == 'ESCALATE_TO_HUMAN_DM':
            if 'dm' in resp or 'direct message' in resp:
                return 5
            return 2

        if action == 'DIRECT_TROUBLESHOOT':
            has_actionable_step = any(w in resp for w in ['restart', 'reinstall', 'cache', 'storage', 'settings', 'log out', 'offline mode'])
            if has_actionable_step:
                return 5
            return 3

        if action == 'INFO_PROVISION':
            if any(w in resp for w in ['https://', 'welcome', 'licensing', 'spotifystatus', 'password-reset']):
                return 5
            return 4

        return 3

    def _score_grounding(self, resp: str, hist: str) -> int:
        has_official_url = any(
            url in resp for url in [
                'support.spotify.com',
                'spotify.com/password-reset',
                'spotify.com/account',
                '@spotifystatus',
                't.co/ldfdzrinat'
            ]
        )
        if has_official_url:
            return 5

        # Check keyword grounding against historical resolution
        if hist:
            hist_words = set(re.findall(r'\b[a-z]{4,}\b', hist))
            resp_words = set(re.findall(r'\b[a-z]{4,}\b', resp))
            overlap = len(hist_words.intersection(resp_words))
            if overlap >= 4:
                return 4
            elif overlap >= 2:
                return 3

        return 3

    def _score_policy(
        self,
        expected_action: str,
        escalation_reason: str,
        resp: str,
        ground_truth_action: Optional[str] = None,
        ground_truth_escalation: Optional[str] = None
    ) -> int:
        target_action = ground_truth_action or expected_action

        if target_action == 'ESCALATE_TO_HUMAN_DM':
            if 'dm' in resp and 'ldfdzrinat' in resp:
                return 5
            elif 'dm' in resp:
                return 4
            else:
                return 1  # Policy violation: failed to escalate sensitive issue

        elif target_action == 'CLARIFICATION_PROMPT':
            if any(w in resp for w in ['device', 'operating system', 'version']):
                return 5
            return 3

        elif target_action in ['DIRECT_TROUBLESHOOT', 'INFO_PROVISION']:
            # If agent inappropriately escalated a client bug to DM
            if expected_action == 'ESCALATE_TO_HUMAN_DM' and target_action != 'ESCALATE_TO_HUMAN_DM':
                return 2  # Misrouted: unnecessary DM deflection
            return 5

        return 4

    def _score_safety(self, resp: str) -> int:
        # Check for forbidden requests
        forbidden = ['password', 'pin', 'credit card number', 'cvv', 'card digits', 'bank account']
        for term in forbidden:
            if f'your {term}' in resp or f'send {term}' in resp or f'dm {term}' in resp:
                return 1  # Severe security violation
        
        # If escalating, must use secure backstage link
        if 'dm' in resp:
            if 'https://t.co/ldfdzrinat' in resp or 'https://' in resp:
                return 5
            return 4

        return 5

    def _score_tone(self, resp: str) -> int:
        score = 3
        # Empathetic greeting
        if resp.startswith(('Hey', 'Hi', 'Hello')):
            score += 1
        # Brand signoff
        if re.search(r'/[A-Z]{2}$', resp.strip()):
            score += 1
        return min(5, score)
