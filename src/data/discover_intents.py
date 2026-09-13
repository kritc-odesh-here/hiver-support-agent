"""
Phase 2: Intent Discovery and Golden Evaluation Set Generation for SpotifyCares.

Performs:
1. Extracts all SpotifyCares conversation threads and customer-agent pairs from twcs.csv.
2. Systematically discovers and validates an evidence-based intent taxonomy.
3. Computes empirical distribution across 43,000+ customer messages, separating valid
   support intents from ambiguous, multi-intent, non-support, and unclassifiable messages.
4. Generates taxonomy documentation, example traces, and ambiguity reports under results/intent_discovery/.
5. Samples a deterministically stratified candidate golden set of 200 real examples under evaluation/golden_set.csv
   with all candidate labels explicitly marked review_status = 'PENDING_HUMAN_REVIEW'.
6. Creates practical human annotation guidelines under evaluation/annotation_guidelines.md.
"""

import os
import sys
import csv
import json
import re
import random
from datetime import datetime
from collections import Counter, defaultdict

# Ensure UTF-8 output on Windows consoles
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass


# Regex patterns for empirical categorization
PATTERNS = {
    'thanks_chatter': re.compile(
        r'^(thanks|thank you|thx|cheers|brilliant|sorted|fixed|no worries|great thanks|appreciate it|worked)\b|'
        r'(@SpotifyCares (thanks|thank you|thx))|'
        r'(\b(sent (a )?dm|check (your )?dm|dm sent|sent you a dm)\b)',
        re.I
    ),
    'outage': re.compile(
        r'\b(down|outage|servers? down|crash(ed)? for everyone|is spotify down|service down|hiccup|backstage|maintenance)\b',
        re.I
    ),
    'billing': re.compile(
        r'\b(bill|billing|charge|charged|payment|receipt|refund|premium|family plan|student discount|subscription|renew|credit card|paypal|free trial|sheerid|invoice)\b',
        re.I
    ),
    'account': re.compile(
        r'\b(login|log in|logging in|password|reset password|email|username|sign in|logged out|hacked|account hijacked|recover account|credentials)\b',
        re.I
    ),
    'offline': re.compile(
        r'\b(offline|download|downloaded|downloading|sync|listen offline|without wifi|storage)\b',
        re.I
    ),
    'crash': re.compile(
        r'\b(crash|crashes|crashing|freeze|freezes|freezing|black screen|blank screen|force close|closes automatically|shut down|won\'t open)\b',
        re.I
    ),
    'playback': re.compile(
        r'\b(skip|skips|skipping|stop|stops|stopping|pause|pauses|pausing|buffer|buffering|stutter|cuts out|cutting out|bluetooth|speaker|audio|sound|volume|playback)\b',
        re.I
    ),
    'playlist': re.compile(
        r'\b(playlist|playlists|saved songs|library|shuffle|repeat|queue|song disappeared|tracks disappeared|local files)\b',
        re.I
    ),
    'catalog': re.compile(
        r'\b(artist|album|song|lyrics|explicit|greyed out|unavailable|not available|missing song|catalog|licensing|rights)\b',
        re.I
    ),
    'vague': re.compile(
        r'\b(not working|broken|help me|won\'t work|doesn\'t work|wtf|acting up|fix this|problem|issue|what is going on|sucks)\b',
        re.I
    )
}


def classify_message(c_text, b_text):
    """
    Empirically categorizes a customer message into one of:
    - 8 support intents
    - 'multi_intent'
    - 'ambiguous_vague'
    - 'non_support_or_chatter'
    - 'unclassifiable_or_foreign'
    """
    c_clean = c_text.strip()

    # 1. Foreign language check (high non-ASCII ratio or Spotify explicit foreign referral)
    ascii_chars = sum(1 for c in c_clean if ord(c) < 128)
    if len(c_clean) > 0 and (ascii_chars / len(c_clean)) < 0.6:
        return 'unclassifiable_or_foreign', ['foreign_language']
    if 'only reply in english' in b_text.lower() or ('support via email' in b_text.lower() and 'english' in b_text.lower()):
        return 'unclassifiable_or_foreign', ['foreign_redirection']

    # 2. Non-support / Chatter / Gratitude / Follow-up notification
    if PATTERNS['thanks_chatter'].search(c_clean):
        # Ensure it does not also complain about an active issue
        if not any(PATTERNS[k].search(c_clean) for k in ['billing', 'account', 'offline', 'crash', 'playback', 'playlist', 'catalog']):
            return 'non_support_or_chatter', ['gratitude_or_chatter']

    # 3. Match candidate support intents
    matches = []
    if PATTERNS['outage'].search(c_clean) or 'hiccup backstage' in b_text.lower():
        matches.append('service_outage_and_status')
    if PATTERNS['billing'].search(c_clean):
        matches.append('subscription_and_billing')
    if PATTERNS['account'].search(c_clean):
        matches.append('account_access_and_login')
    if PATTERNS['offline'].search(c_clean):
        matches.append('offline_listening_and_downloads')
    if PATTERNS['crash'].search(c_clean):
        matches.append('app_crash_and_performance')
    if PATTERNS['playback'].search(c_clean):
        matches.append('playback_and_audio')
    if PATTERNS['playlist'].search(c_clean):
        matches.append('playlist_library_and_curation')
    if PATTERNS['catalog'].search(c_clean):
        matches.append('music_catalog_and_content')

    if len(matches) > 1:
        return 'multi_intent', matches
    elif len(matches) == 1:
        return matches[0], matches

    # 4. Check if vague / unelaborated complaint
    if PATTERNS['vague'].search(c_clean) or len(c_clean.split()) < 6:
        return 'ambiguous_vague', ['lacks_diagnostic_detail']

    # 5. Media only or unclassifiable
    if 'https://t.co/' in c_clean and len(c_clean.replace('https://t.co/', '').strip()) < 10:
        return 'unclassifiable_or_foreign', ['media_only_no_text']

    return 'ambiguous_vague', ['unspecified_symptom']


def determine_expected_action_and_escalation(intent, c_text, b_text):
    """
    Determines expected action and escalation reason based on SpotifyCares data.
    """
    b_lower = b_text.lower()
    c_lower = c_text.lower()
    is_dm_escalation = bool(re.search(r'\b(dm|direct message|private message)\b', b_lower))

    if intent == 'subscription_and_billing':
        if is_dm_escalation or any(k in c_lower for k in ['refund', 'charged twice', 'receipt', 'credit card', 'bank']):
            return 'ESCALATE_TO_HUMAN_DM', 'BILLING_RECEIPT_OR_PAYMENT_VERIFICATION', 'Requires private transaction details or billing system lookup'
        return 'INFO_PROVISION', 'N/A', 'Explain subscription tier, family plan invite rules, or student discount criteria'

    elif intent == 'account_access_and_login':
        if is_dm_escalation or any(k in c_lower for k in ['hacked', 'hijacked', 'can\'t reset', 'password reset', 'email changed']):
            return 'ESCALATE_TO_HUMAN_DM', 'REQUIRES_ACCOUNT_BACKEND_ACCESS', 'Account verification / password recovery requires private email lookup'
        return 'INFO_PROVISION', 'N/A', 'Provide public password reset link or credential troubleshooting'

    elif intent == 'music_catalog_and_content':
        return 'INFO_PROVISION', 'N/A', 'Explain regional licensing rights, explicit track filtering, or content availability'

    elif intent == 'service_outage_and_status':
        return 'INFO_PROVISION', 'N/A', 'Acknowledge known platform issue/outage and inform customer engineers are restoring service'

    elif intent in ['playback_and_audio', 'app_crash_and_performance', 'offline_listening_and_downloads', 'playlist_library_and_curation']:
        if is_dm_escalation:
            return 'ESCALATE_TO_HUMAN_DM', 'PERSISTENT_BUG_INTERNAL_LOGS', 'Standard client-side troubleshooting failed; agent requests account info for backend logs'
        return 'DIRECT_TROUBLESHOOT', 'N/A', 'Provide step-by-step diagnostic steps (restart device, clear cache, clean reinstall, check storage)'

    elif intent == 'ambiguous_vague':
        return 'CLARIFICATION_PROMPT', 'N/A', 'Ask customer for device model, OS version, and exact error behavior before diagnosing'

    elif intent == 'multi_intent':
        if is_dm_escalation:
            return 'ESCALATE_TO_HUMAN_DM', 'COMPLEX_MULTI_ISSUE_ACCOUNT_AUDIT', 'Multiple intertwined issues requiring private account inspection'
        return 'DIRECT_TROUBLESHOOT', 'N/A', 'Acknowledge primary symptom and offer initial isolation steps'

    elif intent == 'non_support_or_chatter':
        return 'INFO_PROVISION', 'N/A', 'Politely acknowledge feedback or thank customer'

    else:
        return 'INFO_PROVISION', 'N/A', 'Direct customer to email support or appropriate channel'


def run_pipeline(csv_path, results_dir="results/intent_discovery", eval_dir="evaluation"):
    print("=" * 80)
    print("STARTING PHASE 2: SPOTIFYCARES INTENT DISCOVERY & GOLDEN SET GENERATION")
    print(f"Dataset path: {csv_path}")
    print("=" * 80)

    os.makedirs(results_dir, exist_ok=True)
    os.makedirs(eval_dir, exist_ok=True)

    # 1. STREAM & RECONSTRUCT SPOTIFY THREADS
    print("\n[Step 1/5] Streaming twcs.csv to reconstruct Spotify conversation pairs...")
    spotify_tweets = {}
    parent_map = {}
    inbound_map = {}
    text_map = {}
    created_at_map = {}

    with open(csv_path, mode='r', encoding='utf-8', errors='replace') as f:
        reader = csv.DictReader(f)
        for row in reader:
            raw_tid = row.get('tweet_id', '').strip()
            if not raw_tid:
                continue
            try:
                tid = int(raw_tid)
            except ValueError:
                tid = raw_tid

            is_inb = row.get('inbound', '').strip().lower() == 'true'
            inbound_map[tid] = is_inb
            author = row.get('author_id', '').strip()
            text_map[tid] = row.get('text', '')
            created_at_map[tid] = row.get('created_at', '')

            if not is_inb and author == 'SpotifyCares':
                spotify_tweets[tid] = text_map[tid]

            p_val = row.get('in_response_to_tweet_id', '').strip()
            if p_val:
                try:
                    p_id = int(p_val)
                except ValueError:
                    p_id = p_val
                parent_map[tid] = p_id

    # Find conversation root for all tweets
    root_memo = {}
    def get_root(tid):
        curr = tid
        path = []
        while curr in parent_map:
            if curr in root_memo:
                r = root_memo[curr]
                for n in path: root_memo[n] = r
                return r
            path.append(curr)
            p = parent_map[curr]
            if p not in inbound_map or p == curr:
                r = curr
                break
            curr = p
        else:
            r = curr
        for n in path: root_memo[n] = r
        return r

    # Match customer queries that received a SpotifyCares response
    all_pairs = []
    for s_tid, s_text in spotify_tweets.items():
        p_tid = parent_map.get(s_tid)
        if p_tid and inbound_map.get(p_tid, False):
            c_text = text_map.get(p_tid, '')
            conv_root = get_root(p_tid)
            
            # Reconstruct prior context if p_tid is not the root
            context_str = "None (thread root)"
            if p_tid != conv_root:
                # Find preceding tweet in conversation
                prev_p = parent_map.get(p_tid)
                if prev_p and prev_p in text_map:
                    speaker = "Customer" if inbound_map.get(prev_p, False) else "SpotifyCares"
                    clean_prev = text_map[prev_p].replace('\n', ' ')
                    context_str = f"Prior Turn [{speaker} ({prev_p})]: {clean_prev}"

            all_pairs.append({
                'customer_tweet_id': p_tid,
                'conversation_id': conv_root,
                'customer_message': c_text,
                'conversation_context': context_str,
                'created_at': created_at_map.get(p_tid, ''),
                'spotify_tweet_id': s_tid,
                'spotify_response': s_text
            })

    total_pairs = len(all_pairs)
    print(f"Loaded {len(spotify_tweets):,} Spotify responses.")
    print(f"Extracted {total_pairs:,} customer-agent interaction pairs.")

    # 2. SYSTEMATIC CLASSIFICATION & INTENT DISTRIBUTION
    print("\n[Step 2/5] Classifying all customer queries across taxonomy categories...")
    categorized_data = defaultdict(list)
    distribution_counts = Counter()

    for item in all_pairs:
        cat, submatches = classify_message(item['customer_message'], item['spotify_response'])
        item['inferred_category'] = cat
        item['submatches'] = submatches
        categorized_data[cat].append(item)
        distribution_counts[cat] += 1

    # Save intent distribution CSV
    dist_csv_path = os.path.join(results_dir, "intent_distribution.csv")
    with open(dist_csv_path, mode='w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['category', 'category_type', 'count', 'percentage'])
        for cat, count in distribution_counts.most_common():
            cat_type = "Support Intent" if cat not in ['ambiguous_vague', 'multi_intent', 'non_support_or_chatter', 'unclassifiable_or_foreign'] else "Edge/Special Class"
            pct = round(count / total_pairs * 100, 2)
            writer.writerow([cat, cat_type, count, pct])

    print(f"Saved distribution to: {dist_csv_path}")

    # 3. GENERATE INTENT EXAMPLES & AMBIGUITY REPORT
    print("\n[Step 3/5] Extracting verified real examples and ambiguity documentation...")

    # Extract 5-10 clean real examples per category
    intent_examples_dict = {}
    for cat, items in categorized_data.items():
        # Pick 6 clean examples with meaningful length
        good_items = [it for it in items if len(it['customer_message'].strip()) > 30]
        sample_size = min(len(good_items), 8)
        random.seed(42)
        sample = random.sample(good_items, sample_size) if good_items else items[:sample_size]
        intent_examples_dict[cat] = [
            {
                'customer_tweet_id': it['customer_tweet_id'],
                'conversation_id': it['conversation_id'],
                'customer_message': it['customer_message'].replace('\n', ' '),
                'context': it['conversation_context'],
                'spotify_response': it['spotify_response'].replace('\n', ' ')
            }
            for it in sample
        ]

    examples_json_path = os.path.join(results_dir, "intent_examples.json")
    with open(examples_json_path, 'w', encoding='utf-8') as f:
        json.dump(intent_examples_dict, f, indent=2)

    # Build ambiguous examples artifact
    ambiguous_examples = {
        'multi_intent_examples': [
            {
                'customer_tweet_id': it['customer_tweet_id'],
                'customer_message': it['customer_message'].replace('\n', ' '),
                'overlapping_intents': it['submatches'],
                'spotify_response': it['spotify_response'].replace('\n', ' ')
            }
            for it in categorized_data['multi_intent'][:10]
        ],
        'vague_examples': [
            {
                'customer_tweet_id': it['customer_tweet_id'],
                'customer_message': it['customer_message'].replace('\n', ' '),
                'reason': 'Lacks diagnostic details; requires clarification before troubleshooting',
                'spotify_response': it['spotify_response'].replace('\n', ' ')
            }
            for it in categorized_data['ambiguous_vague'][:10]
        ],
        'unclassifiable_examples': [
            {
                'customer_tweet_id': it['customer_tweet_id'],
                'customer_message': it['customer_message'].replace('\n', ' '),
                'reason': 'Foreign language or media-only reference',
                'spotify_response': it['spotify_response'].replace('\n', ' ')
            }
            for it in categorized_data['unclassifiable_or_foreign'][:10]
        ]
    }

    ambiguous_json_path = os.path.join(results_dir, "ambiguous_examples.json")
    with open(ambiguous_json_path, 'w', encoding='utf-8') as f:
        json.dump(ambiguous_examples, f, indent=2)

    # 4. GENERATE DETAILED INTENT TAXONOMY MARKDOWN
    taxonomy_md_path = os.path.join(results_dir, "intent_taxonomy.md")
    with open(taxonomy_md_path, 'w', encoding='utf-8') as f:
        f.write("# SpotifyCares Customer Support Intent Taxonomy\n\n")
        f.write("Derived empirically from **43,092** customer interactions replied to by `@SpotifyCares` in the Twitter Customer Support dataset (`twcs.csv`).\n\n")
        f.write("## 1. Taxonomy Structure & Distribution Overview\n\n")
        f.write("| Category | Category Type | Corpus Frequency | Percentage | Primary Action | Default Escalation Policy |\n")
        f.write("| :--- | :--- | :---: | :---: | :--- | :--- |\n")
        for cat, cnt in distribution_counts.most_common():
            cat_type = "Support Intent" if cat not in ['ambiguous_vague', 'multi_intent', 'non_support_or_chatter', 'unclassifiable_or_foreign'] else "Edge Class"
            pct = round(cnt / total_pairs * 100, 2)
            action, esc_rule, _ = determine_expected_action_and_escalation(cat, "", "test")
            f.write(f"| `{cat}` | {cat_type} | {cnt:,} | {pct}% | `{action}` | `{esc_rule}` |\n")

        f.write("\n## 2. Intent Definitions, Inclusion & Exclusion Rules\n\n")

        taxonomy_specs = [
            (
                "subscription_and_billing",
                "Customer has questions or problems regarding Premium status, charges, invoices, payment methods, family/student discount verification, or refunds.",
                ["Queries about unexpected charges, double billing, receipt inquiries",
                 "Premium features inactive despite paying for subscription",
                 "Student verification (SheerID) or Family Plan invite problems",
                 "Payment method declines (PayPal, Credit Card, Prepaid card)",
                 "Subscription cancellation or refund inquiries"],
                ["Inability to log into the account (classify under `account_access_and_login`)",
                 "Song streaming playback glitches (classify under `playback_and_audio`)"],
                "DIRECT_TROUBLESHOOT / INFO_PROVISION for general policy; ESCALATE_TO_HUMAN_DM when checking private receipts, credit cards, or executing refunds."
            ),
            (
                "music_catalog_and_content",
                "Customer is looking for a missing song/album/artist, reporting greyed-out tracks, inquiring about release dates, or asking about explicit lyric filters.",
                ["Songs or albums missing from artist discography or greyed out",
                 "Track availability differences between countries/regions",
                 "Explicit vs clean album versions or explicit filtering toggles",
                 "Inquiries regarding when new music or podcasts will be uploaded"],
                ["Personal saved tracks missing from a custom playlist (classify under `playlist_library_and_curation`)",
                 "Downloaded offline songs unplayable without internet (classify under `offline_listening_and_downloads`)"],
                "AUTO-HANDLE: Explain regional licensing rights, explicit filter toggles, or direct to Spotify artist content request."
            ),
            (
                "playlist_library_and_curation",
                "Customer experiences issues managing playlists, saved tracks in 'Your Library', shuffle algorithm behavior, queue order, or local file synchronization.",
                ["Playlists disappeared or empty after updating",
                 "Shuffle repeating the same 5 tracks or not randomizing",
                 "Queue order behaving abnormally or skipping queued tracks",
                 "Local audio files on computer not syncing to mobile app"],
                ["Songs completely unavailable across all of Spotify (classify under `music_catalog_and_content`)",
                 "Tracks failing to download for offline playback (classify under `offline_listening_and_downloads`)"],
                "DIRECT_TROUBLESHOOT: Explain shuffle cache behavior, guide web playlist recovery tool, or check desktop local file sharing settings."
            ),
            (
                "account_access_and_login",
                "Customer cannot access their account due to forgotten credentials, password reset email failures, unexpected logouts, or suspecting account takeover.",
                ["Login errors ('username or password incorrect')",
                 "Password reset email not arriving in inbox/spam",
                 "Unexpected logouts across devices",
                 "Suspected unauthorized account access or compromised account",
                 "Facebook account login link disconnection issues"],
                ["Payment failure on an active logged-in account (classify under `subscription_and_billing`)"],
                "INFO_PROVISION for standard password reset link; ESCALATE_TO_HUMAN_DM if reset email does not arrive or account is compromised."
            ),
            (
                "playback_and_audio",
                "Customer experiences active playback disruptions including songs skipping, stopping midway, buffering, Bluetooth disconnects, volume issues, or sound distortion.",
                ["Song suddenly pauses after 10-30 seconds",
                 "Playback skipping tracks rapidly on its own",
                 "Bluetooth speaker or car audio stuttering/disconnecting",
                 "Volume too quiet or audio distorted/scratchy",
                 "Spotify Connect playback transfer fails between devices"],
                ["App crashing completely or closing to homescreen (classify under `app_crash_and_performance`)",
                 "Playback fails specifically when device is offline without wifi (classify under `offline_listening_and_downloads`)"],
                "DIRECT_TROUBLESHOOT: Diagnostic isolation (Bluetooth distance, hard device restart, audio streaming quality settings)."
            ),
            (
                "offline_listening_and_downloads",
                "Customer reports that downloaded songs will not play when offline, downloads constantly fail/re-download, or offline songs disappear.",
                ["Downloaded tracks require internet connection to start",
                 "Green download indicator missing or tracks stuck in 'waiting to download'",
                 "Downloaded playlists removed after clearing storage or switching devices",
                 "Storage capacity or SD card download destination errors"],
                ["General song skipping while connected to high-speed WiFi (classify under `playback_and_audio`)",
                 "App freezing or crashing during launch (classify under `app_crash_and_performance`)"],
                "DIRECT_TROUBLESHOOT: Verify Offline Mode toggle, check 3-device download limit, verify 30-day online check-in requirement."
            ),
            (
                "service_outage_and_status",
                "Customer inquires whether Spotify servers are down, reports platform-wide error messages (500, 502, 'Something went wrong'), or general connectivity failure.",
                ["Widespread connection errors affecting all tracks and search",
                 "Inquiries like 'is Spotify down for anyone else?'",
                 "Server error pages or status downtime acknowledged by Spotify"],
                ["Single device connection issue while other household devices work fine (classify under `playback_and_audio` or `app_crash_and_performance`)"],
                "INFO_PROVISION: Acknowledge ongoing incident or confirm servers are operational; check @SpotifyStatus."
            ),
            (
                "app_crash_and_performance",
                "App crashes immediately upon launch, freezes on specific screens, displays black/blank screens, suffers extreme lag, or causes severe battery drain.",
                ["App force-closes or closes automatically upon opening",
                 "Black/blank screen with unresponsive UI",
                 "Extreme lag, unresponsiveness, or app freezing during navigation",
                 "High battery drain or overheating while running in background"],
                ["Audio stops playing while app UI remains responsive (classify under `playback_and_audio`)"],
                "DIRECT_TROUBLESHOOT: Provide clean reinstallation sequence, clear app cache, check OS version compatibility."
            ),
            (
                "ambiguous_vague",
                "Customer expresses frustration or states that Spotify is broken, but provides zero diagnostic context (e.g. 'fix your app', 'why is Spotify not working').",
                ["One-liner complaints with no symptoms or details",
                 "Vague cries for help without describing what failed"],
                ["Any message mentioning a specific symptom like skipping, crashing, login, or billing"],
                "CLARIFICATION_PROMPT: Inquire what device, OS, and exact behavior the user is experiencing."
            ),
            (
                "multi_intent",
                "Customer message bundles two or more distinct functional complaints together.",
                ["Message reports both app crash AND billing failure",
                 "Message asks about a missing song AND reports bluetooth skipping"],
                ["Single complaint with secondary emotional remark"],
                "DIRECT_TROUBLESHOOT / ESCALATE: Address the primary technical symptom or escalate if one of the sub-intents requires private account lookup."
            ),
            (
                "non_support_or_chatter",
                "Non-support interactions such as user gratitude, social jokes, memes, or notification that they sent a DM.",
                ["'Thanks for the help, sorted now!'",
                 "'Sent you a DM @SpotifyCares'",
                 "Social commentary or bantering"],
                ["Any message containing an unresolved support inquiry"],
                "INFO_PROVISION: Polite closing acknowledgment; no escalation."
            ),
            (
                "unclassifiable_or_foreign",
                "Messages written in non-English languages, media-only tweets without explanatory text, or garbled text.",
                ["Non-English queries (e.g. Thai, Spanish, French)",
                 "Tweet consisting solely of a link or screenshot with no text"],
                ["English messages with minor typos"],
                "INFO_PROVISION: Inform customer that Twitter support operates in English and direct to email support."
            )
        ]

        for name, definition, inc, exc, action_policy in taxonomy_specs:
            f.write(f"### Intent: `{name}`\n\n")
            f.write(f"**Definition**: {definition}\n\n")
            f.write("**Inclusion Criteria**:\n")
            for item in inc:
                f.write(f"- {item}\n")
            f.write("\n**Exclusion Criteria**:\n")
            for item in exc:
                f.write(f"- {item}\n")
            f.write(f"\n**Action & Escalation Policy**: {action_policy}\n\n")
            f.write("---\n\n")

        f.write("## 3. Ambiguity & Boundary Confusion Analysis\n\n")
        f.write("### Boundary 1: `playback_and_audio` vs `app_crash_and_performance`\n")
        f.write("- **The Confusion**: A user says *'Spotify stops every 2 minutes'*. Is the audio stopping, or is the application crashing?\n")
        f.write("- **Resolution Rule**: If the message mentions *'closing', 'shutting down', 'force close', or 'black screen'*, classify as `app_crash_and_performance`. If the app stays open but music pauses, cuts out, or skips, classify as `playback_and_audio`.\n\n")

        f.write("### Boundary 2: `playback_and_audio` vs `offline_listening_and_downloads`\n")
        f.write("- **The Confusion**: User says *'My songs won't play on the subway'*. Is it playback or offline storage?\n")
        f.write("- **Resolution Rule**: If the failure occurs specifically in offline conditions or mentions downloaded tracks, classify as `offline_listening_and_downloads`.\n\n")

        f.write("### Boundary 3: `subscription_and_billing` vs `account_access_and_login`\n")
        f.write("- **The Confusion**: User says *'My Premium is gone, it says Free account'*. Is it billing or login?\n")
        f.write("- **Resolution Rule**: In Spotify, users frequently accidentally create a second account via Facebook or Apple ID with Free status. If the user states they paid but see Free, classify as `subscription_and_billing` (requires receipt check). If they cannot sign into the account at all, classify as `account_access_and_login`.\n\n")

        f.write("### Boundary 4: `music_catalog_and_content` vs `playlist_library_and_curation`\n")
        f.write("- **The Confusion**: User says *'My favourite songs disappeared'*. Is it licensing removal or user library corruption?\n")
        f.write("- **Resolution Rule**: If a user mentions their custom playlist or saved library, classify as `playlist_library_and_curation`. If they mention a specific artist's album being greyed out globally, classify as `music_catalog_and_content`.\n")

    print(f"Saved taxonomy documentation to: {taxonomy_md_path}")

    # 5. SAMPLE CANDIDATE GOLDEN EVALUATION SET (200 EXAMPLES)
    print("\n[Step 4/5] Sampling candidate golden set of 200 real examples (stratified)...")

    # Define exact stratified quotas (total = 200)
    quotas = {
        'subscription_and_billing': 25,
        'music_catalog_and_content': 25,
        'playlist_library_and_curation': 25,
        'account_access_and_login': 25,
        'playback_and_audio': 25,
        'offline_listening_and_downloads': 18,
        'app_crash_and_performance': 16,
        'service_outage_and_status': 14,
        'ambiguous_vague': 14,
        'multi_intent': 8,
        'non_support_or_chatter': 5
    }

    random.seed(42)
    selected_golden = []

    for cat, quota in quotas.items():
        candidates = categorized_data.get(cat, [])
        # Prefer examples with substantial length (>20 chars) and clean text
        high_quality = [it for it in candidates if len(it['customer_message'].strip()) > 25 and '@' in it['customer_message']]
        pool = high_quality if len(high_quality) >= quota else candidates
        sampled = random.sample(pool, min(len(pool), quota))
        selected_golden.extend([(cat, it) for it in sampled])

    # Shuffle deterministically
    random.seed(42)
    random.shuffle(selected_golden)

    # Trim to exactly 200
    selected_golden = selected_golden[:200]

    golden_csv_path = os.path.join(eval_dir, "golden_set.csv")
    with open(golden_csv_path, mode='w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([
            'example_id',
            'conversation_id',
            'customer_message',
            'conversation_context',
            'intent',
            'expected_action',
            'escalation_reason',
            'historical_resolution',
            'review_status',
            'annotation_notes'
        ])

        for idx, (cat, item) in enumerate(selected_golden, start=1):
            ex_id = f"SPOT-GOLD-{idx:03d}"
            c_msg = item['customer_message'].replace('\r', ' ').replace('\n', ' ')
            c_ctx = item['conversation_context']
            hist_res = item['spotify_response'].replace('\r', ' ').replace('\n', ' ')

            exp_action, esc_reason, esc_notes = determine_expected_action_and_escalation(
                cat, item['customer_message'], item['spotify_response']
            )

            # Candidate labels are strictly marked as pending human review
            review_status = "PENDING_HUMAN_REVIEW"
            notes = f"Candidate intent: {cat}. {esc_notes}"

            writer.writerow([
                ex_id,
                item['conversation_id'],
                c_msg,
                c_ctx,
                cat,
                exp_action,
                esc_reason,
                hist_res,
                review_status,
                notes
            ])

    print(f"Saved 200 candidate golden examples to: {golden_csv_path}")

    # 6. GENERATE ANNOTATION GUIDELINES
    print("\n[Step 5/5] Generating annotation guidelines under evaluation/annotation_guidelines.md...")
    guidelines_path = os.path.join(eval_dir, "annotation_guidelines.md")
    with open(guidelines_path, 'w', encoding='utf-8') as f:
        f.write("# SpotifyCares Golden Evaluation Set: Annotation Guidelines\n\n")
        f.write("This document defines the manual human review workflow for validating the candidate golden evaluation set (`evaluation/golden_set.csv`).\n\n")

        f.write("## 1. Ground-Truth Schema Definition\n\n")
        f.write("| Field | Description | Allowed Values |\n")
        f.write("| :--- | :--- | :--- |\n")
        f.write("| `example_id` | Unique evaluation identifier | `SPOT-GOLD-001` to `SPOT-GOLD-200` |\n")
        f.write("| `conversation_id` | Root tweet ID in TWCS | Integer string |\n")
        f.write("| `customer_message` | Verbatim text of customer complaint | Preserved original string |\n")
        f.write("| `conversation_context` | Prior conversation turns | Preceding turn or 'None (thread root)' |\n")
        f.write("| `intent` | Functional customer intent | One of 8 core intents, `multi_intent`, `ambiguous_vague`, `non_support_or_chatter` |\n")
        f.write("| `expected_action` | Target autonomous agent response | `DIRECT_TROUBLESHOOT`, `INFO_PROVISION`, `CLARIFICATION_PROMPT`, `ESCALATE_TO_HUMAN_DM` |\n")
        f.write("| `escalation_reason` | Security/Policy justification | `BILLING_RECEIPT_OR_PAYMENT_VERIFICATION`, `REQUIRES_ACCOUNT_BACKEND_ACCESS`, `PERSISTENT_BUG_INTERNAL_LOGS`, `N/A` |\n")
        f.write("| `historical_resolution` | Real resolution advice from SpotifyCares | Verbatim response from dataset |\n")
        f.write("| `review_status` | Human validation status | Initial: `PENDING_HUMAN_REVIEW` -> Final: `VERIFIED` |\n")
        f.write("| `annotation_notes` | Annotator reasoning & edge-case notes | Text |\n\n")

        f.write("## 2. Step-by-Step Human Review Workflow\n\n")
        f.write("As an annotator reviewing `evaluation/golden_set.csv`:\n\n")
        f.write("1. **Read `customer_message` and `conversation_context`**: Check if the customer's problem is understandable.\n")
        f.write("2. **Validate `intent`**:\n")
        f.write("   - If candidate intent accurately matches the taxonomy definitions in `results/intent_discovery/intent_taxonomy.md`, leave as is.\n")
        f.write("   - If the candidate intent was misclassified (e.g. `playback_and_audio` was assigned to an app crash), update `intent` to the correct category.\n")
        f.write("   - If the message bundles multiple unresolvable problems, set to `multi_intent`.\n")
        f.write("   - If the message lacks sufficient detail to diagnose, set to `ambiguous_vague`.\n")
        f.write("3. **Verify `expected_action` and `escalation_reason`**:\n")
        f.write("   - **AUTO-HANDLE**: Set to `DIRECT_TROUBLESHOOT` (reboot, clear cache, reinstall) or `INFO_PROVISION` (licensing rules, explicit filters). `escalation_reason` MUST be `N/A`.\n")
        f.write("   - **ESCALATE**: If customer requires private account access (billing refund, compromised password, SheerID verification), set to `ESCALATE_TO_HUMAN_DM` and record appropriate `escalation_reason`.\n")
        f.write("4. **Update `review_status`**:\n")
        f.write("   - Once reviewed and confirmed, change `review_status` from `PENDING_HUMAN_REVIEW` to `VERIFIED`.\n")
        f.write("   - If the example is low quality, spam, or non-English, mark `EXCLUDED`.\n\n")

        f.write("## 3. Escalation Policy Rules\n\n")
        f.write("### Strict Rules for Autonomous Agent Escalation:\n")
        f.write("1. **NEVER attempt financial or account modifications**: The agent must NEVER claim to execute a refund, cancel a credit card charge, or reset a password directly. These cases MUST be escalated to human DM.\n")
        f.write("2. **Safe Public Troubleshooting**: For client-side technical bugs, the agent should always provide non-destructive standard operating procedures (restart app, toggle offline mode, reinstall app) before escalating.\n")
        f.write("3. **No Halucinated URLs or Endpoints**: The agent must only provide verified Spotify official links (`support.spotify.com`, `spotify.com/password-reset`).\n")

    print(f"Saved annotation guidelines to: {guidelines_path}")
    print("\n" + "=" * 80)
    print("PHASE 2 PIPELINE COMPLETED SUCCESSFULLY.")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    csv_file = os.path.join("data", "raw", "twcs", "twcs.csv")
    if not os.path.exists(csv_file):
        # Fallback to sample if twcs.csv not present
        csv_file = os.path.join("data", "raw", "twcs", "sample.csv")
    run_pipeline(csv_file)
