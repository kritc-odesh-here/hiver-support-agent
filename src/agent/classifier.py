"""
Context-Aware Intent Classifier for SpotifyCares.

Classifies incoming customer messages into the 12-category SpotifyCares taxonomy:
8 core functional support intents + 4 edge classes (ambiguous_vague, multi_intent,
non_support_or_chatter, unclassifiable_or_foreign).
"""

import re
from typing import Optional, Tuple, List
from .types import TaxonomyIntent


class IntentClassifier:
    """Classifies customer messages based on domain patterns, semantic cues, and conversation context."""

    def __init__(self):
        self._init_patterns()

    def _init_patterns(self):
        self.patterns = {
            'thanks_chatter': re.compile(
                r'^(thanks|thank you|thx|cheers|brilliant|sorted|fixed|no worries|great thanks|appreciate it|worked)\b|'
                r'(@SpotifyCares (thanks|thank you|thx))|'
                r'(\b(sent (a )?dm|check (your )?dm|dm sent|sent you a dm|i dm\'ed you|you (guys )?rock|love (you|this app|spotify)|great job|kudos)\b)',
                re.I
            ),
            'outage': re.compile(
                r'\b(down|outage|servers? down|crash(ed)? for everyone|is spotify down|service down|hiccup|backstage|maintenance|server error|502|500)\b',
                re.I
            ),
            'billing': re.compile(
                r'\b(bill|billing|charge|charged|payment|receipt|refund|premium|family plan|student discount|subscription|renew|credit card|paypal|free trial|sheerid|invoice|deducted|overcharged|money back)\b',
                re.I
            ),
            'account': re.compile(
                r'\b(login|log in|logging in|password|reset password|email|username|sign in|logged out|locked out|compromised|hacked|account hijacked|recover account|credentials|two-factor|2fa|can\'t (log in|access)|cannot (log in|access))\b',
                re.I
            ),
            'offline': re.compile(
                r'\b(offline|download|downloaded|downloading|sync|listen offline|without (wifi|internet)|airplane mode|no internet|no connection|storage|sd card|download limit)\b',
                re.I
            ),
            'crash': re.compile(
                r'\b(crash(es|ing)?|freez(e|es|ing)|black screen|blank screen|force close(d)?|(immediately|automatically|instantly|keeps?)\s+clos(e|es|ing|ed)|clos(e|es|ing)\s+(immediately|automatically|instantly|on launch|on startup)|quits?|won\'t open|shut(s)? down|app closed)\b',
                re.I
            ),
            'playback': re.compile(
                r'\b(skip|skips|skipping|stop|stops|stopping|pause|pauses|pausing|buffer|buffering|stutter|cuts out|cutting out|bluetooth|speaker|audio|sound|volume|playback|distort|distortion)\b',
                re.I
            ),
            'playlist': re.compile(
                r'\b(playlist|playlists|saved songs|library|shuffle|repeat|queue|song disappeared|tracks disappeared|local files|curation|playlist cover)\b',
                re.I
            ),
            'catalog': re.compile(
                r'\b(artist|album|discography|lyrics|explicit|greyed out|unavailable|not available|missing (song|track|album)s?|(song|track)s? (unavailable|removed|missing|greyed out)|catalog|licensing|rights|uncensored|clean version)\b',
                re.I
            ),
            'vague': re.compile(
                r'\b(not working|broken|help me|won\'t work|doesn\'t work|wtf|acting up|fix this|problem|issue|what is going on|sucks|terrible|horrible|useless)\b',
                re.I
            ),
            'foreign_latin': re.compile(
                r'\b(hola|ayuda|por favor|no puedo|musica|cancion(es)?|bonjour|merci|je ne|nao consigo|obrigado|tidak bisa|terima kasih|ich kann|hilfe)\b',
                re.I
            )
        }

    def classify(self, message: str, context: Optional[str] = None) -> Tuple[str, List[str], float, str]:
        """
        Classifies a customer message into (intent, sub_intents, confidence, rationale).
        """
        if not message or not message.strip():
            return TaxonomyIntent.AMBIGUOUS_VAGUE, [], 0.5, "Empty message provided."

        text = message.strip()
        text_lower = text.lower()
        context_lower = (context or "").lower()

        # 1. Unclassifiable / Foreign Language / Media-only Check
        ascii_chars = sum(1 for c in text if ord(c) < 128)
        if len(text) > 0 and (ascii_chars / len(text)) < 0.6:
            return (
                TaxonomyIntent.UNCLASSIFIABLE_OR_FOREIGN,
                [],
                0.95,
                "Query contains non-Latin or predominantly non-English characters."
            )

        # Check for media-only tweet
        if 'https://t.co/' in text and len(re.sub(r'https://t\.co/\S+', '', text).strip()) < 5:
            return (
                TaxonomyIntent.UNCLASSIFIABLE_OR_FOREIGN,
                [],
                0.85,
                "Media or link attachment only without sufficient accompanying text."
            )

        # Check for Latin-script foreign language keywords
        if self.patterns['foreign_latin'].search(text):
            return (
                TaxonomyIntent.UNCLASSIFIABLE_OR_FOREIGN,
                [],
                0.95,
                "Query contains non-English Latin keywords (Spanish, Portuguese, French, etc.)."
            )

        # 2. Non-Support / Chatter / Gratitude Check
        if self.patterns['thanks_chatter'].search(text):
            # Check that user isn't also reporting a live technical or billing problem
            has_active_issue = any(
                self.patterns[k].search(text)
                for k in ['billing', 'account', 'offline', 'crash', 'playback', 'playlist', 'catalog']
            )
            if not has_active_issue:
                return (
                    TaxonomyIntent.NON_SUPPORT_OR_CHATTER,
                    [],
                    0.95,
                    "Customer expresses gratitude, closure, social banter, or DM notification."
                )

        # 3. Match Intent Keywords
        matches = []
        if self.patterns['outage'].search(text):
            matches.append(TaxonomyIntent.SERVICE_OUTAGE_AND_STATUS)
        if self.patterns['billing'].search(text):
            matches.append(TaxonomyIntent.SUBSCRIPTION_AND_BILLING)
        if self.patterns['account'].search(text):
            matches.append(TaxonomyIntent.ACCOUNT_ACCESS_AND_LOGIN)
        if self.patterns['offline'].search(text):
            matches.append(TaxonomyIntent.OFFLINE_LISTENING_AND_DOWNLOADS)
        if self.patterns['crash'].search(text):
            matches.append(TaxonomyIntent.APP_CRASH_AND_PERFORMANCE)
        if self.patterns['playback'].search(text):
            matches.append(TaxonomyIntent.PLAYBACK_AND_AUDIO)
        if self.patterns['playlist'].search(text):
            matches.append(TaxonomyIntent.PLAYLIST_LIBRARY_AND_CURATION)
        if self.patterns['catalog'].search(text):
            matches.append(TaxonomyIntent.MUSIC_CATALOG_AND_CONTENT)

        # 4. Context Influence
        # If message provides diagnostic response to a prior question (e.g. "iOS 11.2, iPhone 7")
        if not matches and context_lower:
            for k, intent_type in [
                ('billing', TaxonomyIntent.SUBSCRIPTION_AND_BILLING),
                ('account', TaxonomyIntent.ACCOUNT_ACCESS_AND_LOGIN),
                ('offline', TaxonomyIntent.OFFLINE_LISTENING_AND_DOWNLOADS),
                ('crash', TaxonomyIntent.APP_CRASH_AND_PERFORMANCE),
                ('playback', TaxonomyIntent.PLAYBACK_AND_AUDIO),
                ('playlist', TaxonomyIntent.PLAYLIST_LIBRARY_AND_CURATION),
                ('catalog', TaxonomyIntent.MUSIC_CATALOG_AND_CONTENT),
                ('outage', TaxonomyIntent.SERVICE_OUTAGE_AND_STATUS)
            ]:
                if self.patterns[k].search(context_lower):
                    matches.append(intent_type)
                    break

        # 5. Handle Multi-Intent vs Single Intent
        if len(matches) > 1:
            # Check for closely-coupled intents (e.g., catalog and playlist can overlap, but distinct)
            primary = TaxonomyIntent.MULTI_INTENT
            rationale = f"Detected multiple overlapping functional intents: {', '.join(matches)}."
            return primary, matches, 0.90, rationale

        elif len(matches) == 1:
            primary = matches[0]
            rationale = f"Matched primary functional intent '{primary}' based on diagnostic keywords."
            return primary, [], 0.95, rationale

        # 6. Check for Vague or Unelaborated Complaint
        if self.patterns['vague'].search(text) or len(text.split()) < 6:
            return (
                TaxonomyIntent.AMBIGUOUS_VAGUE,
                [],
                0.85,
                "Complaint lacks specific diagnostic symptoms (requires clarification prompt)."
            )

        # Default fallback
        return (
            TaxonomyIntent.AMBIGUOUS_VAGUE,
            [],
            0.70,
            "Unspecified symptoms; cannot safely classify into functional troubleshooting category."
        )
