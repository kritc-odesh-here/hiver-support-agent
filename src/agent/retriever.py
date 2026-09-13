"""
Historical Resolution Knowledge Base & Retriever for SpotifyCares.

Indexes and retrieves verified historical resolutions, diagnostic steps,
and official policy references grounded in the TWCS dataset.
"""

import os
import json
import re
import math
from typing import Tuple, List, Dict, Optional
from collections import Counter, defaultdict
from .types import TaxonomyIntent


DEFAULT_RESOLUTIONS = {
    TaxonomyIntent.PLAYBACK_AND_AUDIO: [
        {
            'text': "Hmm. Can you try restarting your device by holding the Sleep/Wake + Volume Down buttons for 10 seconds? Also check if your Bluetooth device is within range. Keep us posted /LS",
            'source': "historical_spotifycares_troubleshooting",
            'keywords': ['bluetooth', 'speaker', 'device', 'audio', 'sound', 'volume', 'restart', 'headphones', 'stop', 'play']
        },
        {
            'text': "Can you try logging out and back in? If that doesn't work, try restarting your device. Let us know how you get on /MV",
            'source': "historical_spotifycares_troubleshooting",
            'keywords': ['stops', 'skipping', 'pause', 'cutting out', 'stutter', 'stop', 'play']
        },
        {
            'text': "Does this happen over WiFi, cellular data, or both? Also, check if lowering your streaming quality under Settings > Music Quality makes a difference /PL",
            'source': "historical_spotifycares_troubleshooting",
            'keywords': ['wifi', 'cellular', 'data', 'buffer', 'buffering']
        }
    ],
    TaxonomyIntent.APP_CRASH_AND_PERFORMANCE: [
        {
            'text': "Could you try performing a clean reinstall of the app? Steps here: https://support.spotify.com/article/reinstall-spotify/. Also make sure your device OS is up to date /KC",
            'source': "historical_spotifycares_troubleshooting",
            'keywords': ['crash', 'crashes', 'force close', 'clean reinstall', 'closes']
        },
        {
            'text': "Try heading to Settings > Storage and tap 'Delete Cache'. This clears temporary data without removing your downloaded music. Does that help? /JS",
            'source': "historical_spotifycares_troubleshooting",
            'keywords': ['freeze', 'freezing', 'lag', 'slow', 'cache', 'storage', 'black screen']
        }
    ],
    TaxonomyIntent.OFFLINE_LISTENING_AND_DOWNLOADS: [
        {
            'text': "Check out the steps under 'Downloads unexpectedly removed' at https://support.spotify.com/article/listen-offline/. Remember that you need to go online at least once every 30 days to keep your downloads active /CP",
            'source': "historical_spotifycares_troubleshooting",
            'keywords': ['offline', 'download', 'disappeared', '30 days', 'wifi']
        },
        {
            'text': "You can download up to 3,333 songs per device on a maximum of 3 devices. Try toggling Offline Mode on and off in Settings > Playback to see if that refreshes your sync /DV",
            'source': "historical_spotifycares_troubleshooting",
            'keywords': ['download limit', 'sync', 'songs per device', 'offline mode']
        }
    ],
    TaxonomyIntent.PLAYLIST_LIBRARY_AND_CURATION: [
        {
            'text': "If a playlist was accidentally removed, you can easily restore it by logging into your account page at https://spotify.com/account and selecting 'Recover playlists' /QI",
            'source': "historical_spotifycares_troubleshooting",
            'keywords': ['playlist disappeared', 'deleted playlist', 'recover playlist', 'library']
        },
        {
            'text': "Try clearing your cache under Settings > Storage to refresh the shuffle algorithm. You can also turn shuffle off and back on to re-randomize your queue /DF",
            'source': "historical_spotifycares_troubleshooting",
            'keywords': ['shuffle', 'repeat', 'queue', 'same songs']
        }
    ],
    TaxonomyIntent.MUSIC_CATALOG_AND_CONTENT: [
        {
            'text': "Music availability all boils down to licensing agreements with record labels and artists, which can vary by country. More info here: https://support.spotify.com/article/unplayable-songs/ /LM",
            'source': "historical_spotifycares_troubleshooting",
            'keywords': ['artist', 'album', 'song', 'greyed out', 'licensing', 'unavailable', 'country']
        },
        {
            'text': "Spotify doesn't censor music – we make it available in whatever form it's delivered by the artists and labels. Check if explicit filtering is toggled under Settings > Playback: https://support.spotify.com/article/explicit-content/ /JK",
            'source': "historical_spotifycares_troubleshooting",
            'keywords': ['explicit', 'clean', 'censor', 'censored', 'filter']
        }
    ],
    TaxonomyIntent.SUBSCRIPTION_AND_BILLING: [
        {
            'text': "Could you send us a DM with your account's email address or username? We'll take a look backstage at your receipt and subscription status /NQ https://t.co/ldFdZRiNAt",
            'source': "historical_spotifycares_troubleshooting",
            'keywords': ['bill', 'billing', 'charge', 'charged', 'refund', 'receipt', 'premium ended']
        },
        {
            'text': "For student discount verification via SheerID, make sure your college enrollment information matches your school documents exactly. More info at: https://support.spotify.com/article/student-discount/ /FR",
            'source': "historical_spotifycares_troubleshooting",
            'keywords': ['student', 'sheerid', 'discount', 'college', 'university']
        },
        {
            'text': "To accept a Family Plan invitation, the address entered must match the plan owner's address exactly. You can verify this in your account overview at https://spotify.com/account /KB",
            'source': "historical_spotifycares_troubleshooting",
            'keywords': ['family', 'family plan', 'invite', 'address', 'admin']
        }
    ],
    TaxonomyIntent.ACCOUNT_ACCESS_AND_LOGIN: [
        {
            'text': "You can request a password reset link at https://spotify.com/password-reset. Be sure to check your spam and junk folders if the email doesn't appear in your inbox /KM",
            'source': "historical_spotifycares_troubleshooting",
            'keywords': ['password', 'reset', 'email', 'forgot', 'login', 'sign in']
        },
        {
            'text': "Could you DM us your account's email address or username? We'll take a look backstage to help verify and secure your credentials /FR https://t.co/ldFdZRiNAt",
            'source': "historical_spotifycares_troubleshooting",
            'keywords': ['hacked', 'hijacked', 'can\'t login', 'email changed', 'credentials']
        }
    ],
    TaxonomyIntent.SERVICE_OUTAGE_AND_STATUS: [
        {
            'text': "We had a little hiccup backstage, but everything should be running smoothly now. You can also monitor live status updates at @SpotifyStatus /CE",
            'source': "historical_spotifycares_troubleshooting",
            'keywords': ['down', 'outage', 'servers', 'hiccup', 'service down', 'spotifystatus']
        }
    ],
    TaxonomyIntent.AMBIGUOUS_VAGUE: [
        {
            'text': "Hey! We'd love to help out. Could you let us know what device, operating system, and Spotify version you're running, and what's happening exactly? /CB",
            'source': "historical_spotifycares_troubleshooting",
            'keywords': ['device', 'operating system', 'version', 'what is happening']
        }
    ],
    TaxonomyIntent.NON_SUPPORT_OR_CHATTER: [
        {
            'text': "You're very welcome! If there's anything else we can ever help with, just give us a shout. Have a great day 🙂 /CP",
            'source': "historical_spotifycares_troubleshooting",
            'keywords': ['welcome', 'thanks', 'great day', 'shout']
        }
    ],
    TaxonomyIntent.UNCLASSIFIABLE_OR_FOREIGN: [
        {
            'text': "We can only provide support in English via Twitter. For assistance in other languages, please reach out to our team at https://support.spotify.com/contact-spotify-support/ /SJ",
            'source': "historical_spotifycares_troubleshooting",
            'keywords': ['english', 'contact', 'email support', 'language']
        }
    ]
}


STOP_WORDS = {
    'the', 'and', 'for', 'that', 'this', 'with', 'you', 'your', 'are', 'can',
    'not', 'have', 'from', 'what', 'why', 'how', 'when', 'where', 'who',
    'spotify', 'help', 'please', 'app', 'cant', 'dont', 'does', 'just',
    'song', 'songs', 'music'
}


def stem_token(word: str) -> str:
    w = word.lower()
    if w.endswith('ing') and len(w) > 5:
        return w[:-3]
    if w.endswith('es') and len(w) > 4:
        return w[:-2]
    if w.endswith('s') and len(w) > 3 and not w.endswith('ss'):
        return w[:-1]
    return w


def clean_resolution_text(text: str) -> str:
    """Strips raw historical tweet handles and trailing slash signoffs."""
    cleaned = re.sub(r'@\w+\s*', '', text)
    cleaned = re.sub(r'\s*/[A-Z]{2}\s*$', '', cleaned).strip()
    return cleaned


class ResolutionRetriever:
    """Retrieves verified historical resolutions based on intent and query similarity."""

    def __init__(self, examples_path: Optional[str] = None):
        self.examples_path = examples_path or os.path.join("results", "intent_discovery", "intent_examples.json")
        self.knowledge_base = defaultdict(list)
        self._load_knowledge_base()

    def _load_knowledge_base(self):
        # 1. Load built-in vetted resolutions
        for intent, items in DEFAULT_RESOLUTIONS.items():
            for item in items:
                self.knowledge_base[intent].append({
                    'text': clean_resolution_text(item['text']),
                    'source': item.get('source', 'vetted_template'),
                    'keywords': [stem_token(k) for k in item.get('keywords', [])],
                    'is_vetted': True
                })

        # 2. Augment with historical examples from Phase 2 if available
        if os.path.exists(self.examples_path):
            try:
                with open(self.examples_path, mode='r', encoding='utf-8', errors='replace') as f:
                    data = json.load(f)
                    for intent, examples in data.items():
                        for ex in examples:
                            resp = ex.get('spotify_response', '').strip()
                            cust = ex.get('customer_message', '').strip()
                            if resp:
                                cleaned_resp = clean_resolution_text(resp)
                                tokens = [stem_token(w) for w in re.findall(r'\b\w{3,}\b', cust.lower()) if w not in STOP_WORDS]
                                self.knowledge_base[intent].append({
                                    'text': cleaned_resp,
                                    'source': 'twcs_historical_trace',
                                    'keywords': tokens[:10],
                                    'is_vetted': False
                                })
            except Exception:
                pass

    def retrieve(self, intent: str, query: str, context: Optional[str] = None) -> Tuple[str, str, float]:
        """
        Retrieves the best historical resolution for an intent and query.
        Returns (resolution_text, source, match_score).
        """
        candidates = self.knowledge_base.get(intent) or self.knowledge_base.get(TaxonomyIntent.AMBIGUOUS_VAGUE, [])
        if not candidates:
            return "Please let us know your device and what issue you are experiencing so we can assist. /AY", "fallback", 0.5

        raw_tokens = re.findall(r'\b\w{3,}\b', (query + " " + (context or "")).lower())
        query_tokens = set(stem_token(w) for w in raw_tokens if w not in STOP_WORDS)
        best_cand = candidates[0]
        best_score = -1.0

        for cand in candidates:
            cand_keywords = set(cand.get('keywords', []))
            overlap = query_tokens.intersection(cand_keywords)
            # Jaccard/overlap metric with boost for vetted templates
            score = len(overlap) / max(1, math.sqrt(len(query_tokens) * max(1, len(cand_keywords))))
            if cand.get('is_vetted', False):
                score += 0.15  # Prefer structured SOP solutions

            if score > best_score:
                best_score = score
                best_cand = cand

        return best_cand['text'], best_cand['source'], min(1.0, 0.5 + max(0.0, best_score))
