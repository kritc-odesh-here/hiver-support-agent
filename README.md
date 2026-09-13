# Hiver SDE Intern Take-Home: AI Customer Support Agent

This repository contains the implementation for the Hiver AI Customer Support Agent assignment. The project analyzes multi-turn Twitter customer support conversations (`twcs.csv`), categorizes customer intents, and builds an agent capable of retrieving historical resolutions and responding to customer issues.

---

## Phase 1: Dataset Profiling & Brand Selection

In Phase 1, we conduct end-to-end dataset profiling on the raw Twitter Customer Support dataset without building models or fabricating assumptions. All metrics are computed directly by running code on the raw data.

### 1. Dataset Confirmation
The dataset files are located at:
- Full dataset: `data/raw/twcs/twcs.csv` (492.58 MB, 2,811,774 records)
- Verification sample: `data/raw/twcs/sample.csv` (17 KB, 93 records)

---

## How to Reproduce Dataset Profiling

### Requirements
- Python 3.10+
- Standard libraries (`csv`, `json`, `collections`, `statistics`, `datetime`, `re`, `argparse`)
- Optional: `pandas`, `tqdm`

### Commands

1. **Quick Verification Run (Sample Dataset)**:
   ```bash
   python src/data/profile_dataset.py --sample
   ```
   Runs against `data/raw/twcs/sample.csv` in under 2 seconds, verifying schema validation, thread reconstruction, and metric generation.

2. **Full Dataset Profiling (Production Dataset)**:
   ```bash
   python src/data/profile_dataset.py
   ```
   Streams all 2,811,774 rows of `data/raw/twcs/twcs.csv` in chunked passes, keeping memory strictly bounded (~250 MB peak RAM) and completing in ~45 seconds.

Generated artifacts are automatically stored under:
```text
results/dataset_profile/
├── overall_summary.json         # High-level dataset stats, dates, entities
├── schema_profile.json          # Column types, missing value percentages
├── top_10_brands.csv            # Top 10 brands ranked by outbound volume
├── brand_candidate_metrics.csv  # Threads, lengths, bi-directional %, DM deflection %
├── data_quality_report.md       # Audit of orphans, missing refs, and utility
└── sample_conversations.json    # Real multi-turn conversation traces
```

---

## Dataset Profile Summary

| Metric | Value |
| :--- | :--- |
| **Total Rows** | `2,811,774` |
| **Unique Tweet IDs** | `2,811,774` (0 duplicates) |
| **Inbound Tweets (Customer)** | `1,537,843` (54.69%) |
| **Outbound Tweets (Brand)** | `1,273,931` (45.31%) |
| **Date Range** | `2008-05-08` to `2017-12-03` (~9.5 years / 3,496 days) |
| **Unique Authors** | `702,777` total (`702,669` customer IDs, `108` brand accounts) |
| **Reconstructed Conversation Threads**| `798,197` |

### Schema & Data Types

| Column Name | Inferred Type | Missing Count | Missing % | Description |
| :--- | :--- | :--- | :--- | :--- |
| `tweet_id` | `int64` | 0 | 0.00% | Primary key unique identifier |
| `author_id` | `string` | 0 | 0.00% | Anonymized user ID or brand handle |
| `inbound` | `boolean` | 0 | 0.00% | True if customer, False if brand |
| `created_at` | `datetime` | 0 | 0.00% | RFC 2822 timestamp |
| `text` | `string` | 0 | 0.00% | Tweet text content |
| `response_tweet_id` | `string` | 1,040,629 | 37.01% | Comma-separated list of reply tweet IDs |
| `in_response_to_tweet_id` | `int64` | 794,335 | 28.25% | Upstream parent tweet ID (null if root) |

---

## Top 10 Brands by Outbound Volume

| Rank | Brand Handle | Outbound Tweets | Share of Outbound Volume |
| :---: | :--- | :---: | :---: |
| 1 | `AmazonHelp` | 169,840 | 13.33% |
| 2 | `AppleSupport` | 106,860 | 8.39% |
| 3 | `Uber_Support` | 56,270 | 4.42% |
| 4 | `SpotifyCares` | 43,265 | 3.40% |
| 5 | `Delta` | 42,253 | 3.32% |
| 6 | `Tesco` | 38,573 | 3.03% |
| 7 | `AmericanAir` | 36,764 | 2.89% |
| 8 | `TMobileHelp` | 34,317 | 2.69% |
| 9 | `comcastcares` | 33,031 | 2.59% |
| 10 | `British_Airways` | 29,361 | 2.30% |

---

## Candidate Brand Comparison

By reconstructing conversation threads via parent pointers (`in_response_to_tweet_id`), we analyze the conversational depth, bi-directional interaction rate, and DM deflection rate:

| Brand | Outbound Tweets | Threads | Inbound Msgs | Outbound Msgs | Avg Turns | Med Turns | Bi-Dir % | DM Deflect % | Public Resolution Utility |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **AmazonHelp** | 169,840 | 82,556 | 203,598 | 170,444 | 4.53 | 3.0 | 100.0% | 0.64% | Moderate (multi-lingual + external URLs) |
| **AppleSupport** | 106,860 | 80,717 | 131,764 | 107,143 | 2.96 | 2.0 | 100.0% | 52.47% | **Poor** (heavily deflects to private DM) |
| **Uber_Support** | 56,270 | 41,923 | 72,154 | 56,396 | 3.07 | 2.0 | 100.0% | 35.16% | Moderate / Low (account verification in DM) |
| **SpotifyCares** | 43,265 | 28,280 | 48,543 | 43,346 | 3.25 | 2.0 | 99.99% | 30.79% | **Exceptional** (high public troubleshooting) |
| **Delta** | 42,253 | 26,168 | 45,296 | 42,698 | 3.36 | 2.0 | 99.99% | 16.45% | **Very High** (airline status, rules, baggage) |
| **Tesco** | 38,573 | 16,722 | 34,228 | 38,931 | 4.38 | 4.0 | 100.0% | 26.81% | **Very High** (deep troubleshooting, high median) |
| **AmericanAir** | 36,764 | 26,386 | 50,054 | 37,530 | 3.32 | 2.0 | 100.0% | 16.79% | High (similar to Delta) |
| **TMobileHelp** | 34,317 | 22,820 | 47,158 | 35,572 | 3.63 | 2.0 | 100.0% | 81.82% | **Poor** (telecom auth requires DM) |
| **comcastcares** | 33,031 | 24,063 | 39,579 | 33,470 | 3.04 | 2.0 | 100.0% | 71.46% | **Poor** (ISP auth requires DM) |
| **British_Airways**| 29,361 | 16,452 | 31,187 | 29,529 | 3.69 | 3.0 | 100.0% | 14.00% | High (airline domain) |

---

## Data Quality Findings

1. **Strict Primary Key Integrity**: `0` duplicate `tweet_id` records exist across all 2.81 million rows.
2. **Orphan Parent References (`0.21%`)**: `3,677` tweets reference parent IDs not present in the dataset. These represent conversations that started before the scrape collection window or parent tweets that were deleted.
3. **Missing Downstream Replies (`7.89%`)**: `172,500` child tweet references are not in the dataset. This occurs because customers or brands replied after the scraping cutoff timestamp.
4. **Clean Content Text**: `0` empty or whitespace-only messages. Only `53` ultra-short messages (<5 characters, e.g., "ok", "?").
5. **Private DM Deflection (Critical Insight)**:
   - Several major accounts (`TMobileHelp` at 81.8%, `comcastcares` at 71.5%, `AppleSupport` at 52.5%) overwhelmingly deflect conversations to private Direct Messages.
   - For training and evaluating an autonomous customer support agent, DM deflection yields dead-end conversations with no public ground-truth resolution.

---

## Brand Selection & Recommendation

### Recommended Primary Brand: **`SpotifyCares`**
**Runner-Up Candidates**: **`Delta`** and **`Tesco`**

### Why `SpotifyCares` is the Best Selection:
1. **Sufficient Volume & High Coherence**: 43,265 outbound brand tweets across 28,280 conversation threads with 91,889 total tweets.
2. **Substantive Technical Troubleshooting**: Unlike Apple or telecoms that immediately request private DMs, Spotify provides actionable troubleshooting in public tweets (e.g., restart sequences, cache clearing, clean app reinstallation, offline syncing, Bluetooth troubleshooting, OS/app compatibility checks).
3. **Manageable Intent Taxonomy**: Software/streaming intents are clean, distinct, and highly structured:
   - *Technical / Playback Issues* (skipping songs, bluetooth, audio quality, offline sync)
   - *App Crashes & Device Bugs* (iOS, Android, Desktop, Web Player)
   - *Account & Subscription* (Free vs Premium, Family/Student plans, password reset)
   - *Billing & Payment* (failed charges, plan upgrades/cancellations)
   - *Music Availability & Catalog* (explicit tags, missing albums, playlist curation)
4. **Feasibility of Golden Evaluation Set**: With 28,280 threads, constructing a high-signal 150–250 multi-turn evaluation set with verified resolution ground truth is straightforward and statistically sound.
5. **Resolution Retrieval Potential**: Spotify's historical resolutions contain explicit steps and verified fixes that a RAG or resolution retriever can surface with high precision.

---

## Phase 2: SpotifyCares Intent Discovery & Golden Evaluation Set

In Phase 2, we conducted empirical intent discovery on 43,092 real customer-agent pairs for `SpotifyCares`, formulated an 8-intent functional taxonomy plus edge classes, established an escalation policy, and constructed a 200-example candidate golden evaluation set for human review.

### How to Reproduce Phase 2
```bash
python src/data/discover_intents.py
```
This script processes the Spotify conversations in `data/raw/twcs/twcs.csv`, validates categories against empirical patterns, computes intent frequencies, extracts representative traces, and deterministically samples the 200 candidate golden evaluation records (`seed=42`).

### Artifacts Generated
```text
results/intent_discovery/
├── intent_taxonomy.md          # Comprehensive definitions, inclusion/exclusion, confusion analysis
├── intent_distribution.csv     # Exact corpus-wide counts and percentages
├── intent_examples.json        # Curated real conversation examples per intent
└── ambiguous_examples.json     # Multi-intent, vague, and unclassifiable examples

evaluation/
├── golden_set.csv              # 200 candidate evaluation examples (status: PENDING_HUMAN_REVIEW)
└── annotation_guidelines.md    # Human-in-the-loop review workflow and escalation rules
```

### Empirical Intent Distribution (43,092 Customer Messages)

| Intent / Class | Class Type | Corpus Count | Share % | Default Action | Escalation Policy |
| :--- | :--- | :---: | :---: | :--- | :--- |
| `ambiguous_vague` | Edge Class | 23,176 | 53.78% | `CLARIFICATION_PROMPT` | Auto-handle (request device, OS, error behavior) |
| `subscription_and_billing` | Support Intent | 5,210 | 12.09% | `DIRECT_TROUBLESHOOT` / `INFO` | Escalate if checking private receipts/cards/refunds |
| `multi_intent` | Edge Class | 3,061 | 7.10% | `DIRECT_TROUBLESHOOT` | Escalate if any sub-intent requires private account lookup |
| `music_catalog_and_content` | Support Intent | 3,030 | 7.03% | `INFO_PROVISION` | Auto-handle (explain licensing rights & explicit filter) |
| `playlist_library_and_curation`| Support Intent | 2,438 | 5.66% | `DIRECT_TROUBLESHOOT` | Auto-handle (shuffle cache, playlist recovery tool) |
| `account_access_and_login` | Support Intent | 2,106 | 4.89% | `INFO_PROVISION` | Escalate if reset email fails or account compromised |
| `non_support_or_chatter` | Edge Class | 1,245 | 2.89% | `INFO_PROVISION` | Auto-handle (polite closing acknowledgment) |
| `playback_and_audio` | Support Intent | 1,044 | 2.42% | `DIRECT_TROUBLESHOOT` | Auto-handle (Bluetooth distance, hard device restart) |
| `offline_listening_and_downloads`| Support Intent | 832 | 1.93% | `DIRECT_TROUBLESHOOT` | Auto-handle (offline toggle, storage limit verification) |
| `unclassifiable_or_foreign`| Edge Class | 459 | 1.07% | `INFO_PROVISION` | Auto-handle (refer non-English queries to email team) |
| `service_outage_and_status` | Support Intent | 284 | 0.66% | `INFO_PROVISION` | Auto-handle (confirm platform status / ongoing incident) |
| `app_crash_and_performance` | Support Intent | 207 | 0.48% | `DIRECT_TROUBLESHOOT` | Auto-handle (clean reinstall sequence, cache clearing) |

### Candidate Golden Evaluation Set (200 Examples)
- **Deterministic Stratification**: Sampled with `seed=42` across all 8 support intents plus edge classes.
- **Full Support-Agent Task Schema**: Contains `example_id`, `conversation_id`, `customer_message`, `conversation_context`, `intent`, `expected_action`, `escalation_reason`, `historical_resolution`, `review_status`, and `annotation_notes`.
- **Human Labeling Integrity**: All 200 records are explicitly initialized with:
  ```text
  review_status = "PENDING_HUMAN_REVIEW"
  ```
  In compliance with assignment requirements, the dataset is marked as candidate suggestions and requires manual human review before being treated as finalized ground truth.

---

## Human Review Workflow & Validation

To ensure ground-truth fidelity, the candidate golden set (`evaluation/golden_set.csv`) is verified by a human reviewer using the dedicated lightweight review tool.

### 1. Launch the Review Tool

**Web Interface (Recommended)**:
```bash
python evaluation/review_tool.py
```
Opens a local review interface at [http://localhost:8000](http://localhost:8000) with zero external dependencies.

**Terminal CLI Mode (Alternative)**:
```bash
python evaluation/review_tool.py --cli
```

### 2. Reviewer Actions
- **Inspect**: View verbatim customer query, prior conversation turn, and historical Spotify response.
- **Edit / Confirm**: Confirm or update `intent`, `expected_action`, `escalation_reason`, and `annotation_notes`.
  - When `expected_action != ESCALATE_TO_HUMAN_DM`, `escalation_reason` is automatically set to `N/A`.
  - When `expected_action == ESCALATE_TO_HUMAN_DM`, `escalation_reason` is enabled and required.
- **Verify**: Press `Enter` or click `VERIFY & NEXT`.
  - Saves human-confirmed record to `evaluation/golden_set_verified.csv`.
  - Sets `review_status = "VERIFIED"`.
  - Records `reviewed_by = "human"` and timestamp.
  - Leaves `evaluation/golden_set.csv` completely unmodified.
- **Resume Anytime**: Progress is persisted after every verification. Relaunching the tool automatically resumes at the first pending example.

### 3. Audit & Validate the Golden Set
```bash
python evaluation/validate_golden_set.py
```
Validates `evaluation/golden_set_verified.csv` for:
- Between 150 and 250 verified examples with unique IDs (assignment requirement)
- All required fields non-empty
- All rows marked `review_status = "VERIFIED"`
- All intents and actions belonging strictly to the approved taxonomy
- Valid escalation reason matching action rules

> [!IMPORTANT]
> **Human-Review Status**: The golden evaluation set in `evaluation/golden_set_verified.csv` contains 200 fully human-verified examples, surpassing the assignment requirement of 150–250 hand-reviewed examples. All records are verified with unique IDs, valid taxonomy classes, actions, and escalation reasons (`python evaluation/validate_golden_set.py` passes with 0 errors and 0 warnings). The candidate evaluation set (`evaluation/golden_set.csv`, 200 rows) remains preserved as a baseline with status `PENDING_HUMAN_REVIEW`.

To audit the candidate backup at any time:
```bash
python evaluation/validate_golden_set.py --file evaluation/golden_set.csv
```

---

## Phase 3: SpotifyCares AI Support Agent Pipeline

An autonomous, explainable AI Customer Support Agent pipeline built around the empirical 12-class SpotifyCares taxonomy, grounded escalation policies, and verified historical resolutions.

### Architecture Overview
```text
Customer Message (+ Context)
              │
              ▼
   ┌──────────────────────┐
   │   IntentClassifier   │ ──► Primary Intent, Sub-Intents, Confidence
   └──────────────────────┘
              │
              ▼
   ┌──────────────────────┐
   │ ResolutionRetriever  │ ──► Historical Resolution & Official URLs
   └──────────────────────┘
              │
              ▼
   ┌──────────────────────┐
   │     PolicyEngine     │ ──► Action (DIRECT_TROUBLESHOOT / INFO / CLARIFY / ESCALATE)
   └──────────────────────┘     & Specific Escalation Reason
              │
              ▼
   ┌──────────────────────┐
   │  ResponseGenerator   │ ──► Conversational SpotifyCares Voice (/AY)
   └──────────────────────┘
```

### Modules (`src/agent/`)
- [`src/agent/types.py`](src/agent/types.py): Strict dataclasses and taxonomy constants.
- [`src/agent/classifier.py`](src/agent/classifier.py): Context-aware intent classifier detecting 8 support intents, multi-intent decomposition, ambiguous queries, and non-support/foreign text.
- [`src/agent/retriever.py`](src/agent/retriever.py): Semantic keyword/TF-IDF historical resolution retriever indexing verified solutions and official links.
- [`src/agent/policy.py`](src/agent/policy.py): Escalation policy engine enforcing AUTO-HANDLE vs ESCALATE boundaries based on financial privacy, account security, and troubleshooting status.
- [`src/agent/generator.py`](src/agent/generator.py): Conversational response synthesizer generating authentic `@SpotifyCares` messages.
- [`src/agent/agent.py`](src/agent/agent.py): End-to-end `SpotifySupportAgent` pipeline.

### CLI Usage

1. **Interactive Shell**:
   ```bash
   python src/main.py
   ```

2. **Single-Query Diagnostic Output**:
   ```bash
   python src/main.py --query "My songs stop playing on bluetooth"
   python src/main.py --query "I was charged twice and need a refund"
   python src/main.py --query "Spotify is not working"
   ```

3. **Batch Edge Case Evaluation**:
   ```bash
   python src/main.py --eval
   ```

4. **Automated Unit & Integration Tests (15 passing tests)**:
   ```bash
   python -m unittest tests/test_agent.py
   ```

5. **Comprehensive Robustness Suite (42 unseen edge-case tests)**:
   ```bash
   python -m unittest tests/test_robustness.py
   ```

---

### Escalation Policy & Safety Boundaries

| Category | Policy Action | Escalation Code | Handling Behavior |
| :--- | :--- | :--- | :--- |
| **Client-Side Bugs** (Playback, App Crash, Offline, Playlists) | `DIRECT_TROUBLESHOOT` | `N/A` | Autonomous step-by-step SOP troubleshooting (restart, clear cache, reinstall, storage check). |
| **Persistent Technical Failure** | `ESCALATE_TO_HUMAN_DM` | `PERSISTENT_BUG_INTERNAL_LOGS` | Escalates to private DM for device logs when customer confirms standard troubleshooting was already attempted. |
| **Billing / Disputes / Refunds** | `ESCALATE_TO_HUMAN_DM` | `BILLING_RECEIPT_OR_PAYMENT_VERIFICATION` | Never attempts financial changes autonomously; routes directly to human DM with secure receipt link (`https://t.co/ldFdZRiNAt`). |
| **Account Security / Takeover** | `ESCALATE_TO_HUMAN_DM` | `REQUIRES_ACCOUNT_BACKEND_ACCESS` | Never asks for passwords; routes compromised credentials or email changes to secure human agent verification. |
| **Ambiguous / Vague Queries** | `CLARIFICATION_PROMPT` | `N/A` | Gently prompts customer for device model, OS version, and exact observed symptoms before prescribing fixes. |
| **Licensing / General Info** | `INFO_PROVISION` | `N/A` | Cites official Spotify knowledge base articles (`support.spotify.com`) and explains catalog rights or status. |

---

### Representative Agent Outputs

#### 1. Client-Side Playback Troubleshooting
```text
Customer Message:      "My songs stop playing on bluetooth"
Predicted Intent:      playback_and_audio (Confidence: 0.95)
Expected Action:       DIRECT_TROUBLESHOOT
Escalation Status:     [+] AUTO-HANDLE
Generated Response:    "Hey! Can you try restarting your device by holding the Sleep/Wake + Volume Down buttons for 10 seconds? Also check if your Bluetooth device is within range. Keep us posted /AY"
```

#### 2. Financial / Billing Dispute Escalation
```text
Customer Message:      "I was charged twice and need a refund"
Predicted Intent:      subscription_and_billing (Confidence: 0.95)
Expected Action:       ESCALATE_TO_HUMAN_DM
Escalation Reason:     BILLING_RECEIPT_OR_PAYMENT_VERIFICATION
Escalation Status:     [!] ESCALATE TO HUMAN DM
Generated Response:    "Hey! We'd be happy to take a closer look at your billing and subscription details. Could you send us a DM with your account's email address or username? We'll check backstage https://t.co/ldFdZRiNAt /AY"
```

#### 3. Ambiguous Complaint Clarification
```text
Customer Message:      "Spotify is not working"
Predicted Intent:      ambiguous_vague (Confidence: 0.85)
Expected Action:       CLARIFICATION_PROMPT
Escalation Status:     [+] AUTO-HANDLE
Generated Response:    "Hey! Help's here. Could you let us know what device, operating system, and Spotify version you're running, and what's happening exactly? We'll see what we can suggest /AY"
```
