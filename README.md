# Hiver SDE Intern Take-Home: AI Customer Support Agent

This repository contains the complete implementation for the Hiver AI Customer Support Agent take-home assignment. The project analyzes multi-turn Twitter customer support conversations (`twcs.csv`), empirically selects and models `@SpotifyCares`, establishes a 12-class intent taxonomy and grounded escalation policy, builds an autonomous support agent pipeline, and evaluates results against two baselines on a 200-example golden evaluation set (25 initial hand-verified examples + 175 AI-assisted human-confirmed examples in `golden_set_verified.csv`, with 200 pending candidate records in `golden_set.csv`).

---

## Quickstart: Reproduce Headline Results in Under 15 Minutes

The entire project runs with standard Python (no external database or GPU required):

```bash
# 1. (Optional) Create & activate a virtual environment
python -m venv venv
# Windows:
venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

# 2. Run Comprehensive Evaluation Harness across 200 Golden Evaluation Examples:
#    (Evaluates SpotifySupportAgent + 2 Baselines + LLM Judge + Human Agreement in < 5 seconds)
python evaluation/evaluate.py

# 3. Run Automated Unit & Robustness Test Suite (57/57 tests passing):
python -m unittest discover -s tests -p "test*.py" -v

# 4. Validate the 200-Example Golden Evaluation Set:
python evaluation/validate_golden_set.py

# 5. Run Interactive Agent Shell or Single-Query Diagnostics:
python src/main.py --eval
python src/main.py --query "I was charged twice on my card and need a refund"
```

---

## Try the Agent Yourself

You can immediately interact with the SpotifyCares Support Agent locally without any external dependencies:

```bash
# 1. Launch the interactive diagnostic shell:
python src/main.py

# 2. Run single-query diagnostics with detailed prediction cards:
python src/main.py --query "I was charged twice on my card and need a refund"
python src/main.py --query "My songs stop playing on bluetooth"
python src/main.py --query "Spotify is not working"

# 3. Run automated batch evaluation across all 13 core edge-case patterns:
python src/main.py --eval
```

### Interactive Shell Features
When launching `python src/main.py`, the shell prompts for:
- **Customer Message** (required): The inbound customer tweet or issue description.
- **Conversation Context** (optional): The preceding conversation turn or prior agent response, allowing the classifier and policy engine to resolve follow-up replies and diagnostic information.

### Zero External Dependencies for Inference
The core support agent and evaluation harness run completely locally and do **NOT** require:
- No API keys (e.g. OpenAI, Anthropic, or Google Cloud keys)
- No GPU or specialized hardware
- No external database (e.g. Pinecone, Chroma, PostgreSQL, or Redis)
- No external microservices or network calls

*(Note: The 516.5 MB (492.58 MiB) raw TWCS dataset is only needed if you wish to rerun the entire Phase 1 profiling or Phase 2 intent discovery pipeline from scratch; all derived artifacts, knowledge bases, and evaluation records are already bundled in the repository.)*

---

## Submission Deliverables

The table below maps every assignment deliverable to its concrete repository location:

| Deliverable | Repository Path | Description |
| :--- | :--- | :--- |
| **Agent Implementation** | [`src/agent/`](src/agent/) | Modular pipeline: `types.py`, `classifier.py`, `retriever.py`, `policy.py`, `generator.py`, `agent.py` |
| **Agent Entry Point & CLI** | [`src/main.py`](src/main.py) | Interactive shell, single-query diagnostic runner, and batch evaluation |
| **Golden Evaluation Set** | [`evaluation/golden_set_verified.csv`](evaluation/golden_set_verified.csv) | 200 validated multi-turn examples (25 manual + 175 AI-assisted human confirmations) |
| **Candidate Golden Set** | [`evaluation/golden_set.csv`](evaluation/golden_set.csv) | Untouched candidate baseline (all 200 rows `PENDING_HUMAN_REVIEW`) |
| **Annotation Guidelines** | [`evaluation/annotation_guidelines.md`](evaluation/annotation_guidelines.md) | Standardized taxonomy definitions, escalation boundaries, and review protocol |
| **Sampling & Labeling Note** | [`evaluation/SAMPLING_AND_LABELING.md`](evaluation/SAMPLING_AND_LABELING.md) | Stratified sampling methodology (`seed=42`) and two-phase human review workflow |
| **Evaluation Harness** | [`evaluation/evaluate.py`](evaluation/evaluate.py) | Automated harness computing task metrics, baseline comparisons, and judge scores |
| **LLM-as-Judge Rubric** | [`evaluation/judge_rubric.md`](evaluation/judge_rubric.md) | Formal 6-dimension 1–5 scoring rubric for reply quality evaluation |
| **Executable LLM Judge** | [`evaluation/llm_judge.py`](evaluation/llm_judge.py) | Rule-grounded offline evaluator + API mode for reply quality assessment |
| **Human Reply Ratings** | [`evaluation/human_reply_ratings.csv`](evaluation/human_reply_ratings.csv) | 50 human-evaluated replies across all 12 classes for judge calibration |
| **Human Agreement Results** | [`results/evaluation/human_agreement.json`](results/evaluation/human_agreement.json) | Agreement statistics ($r = 0.7527$, $\kappa = 0.581$, MAE = 0.356) |
| **Automated Evaluation Results** | [`results/evaluation/eval_results.json`](results/evaluation/eval_results.json) | Full task metrics, per-class breakdown, and failure analysis data |
| **Baseline Comparison** | [`results/evaluation/baseline_comparison.csv`](results/evaluation/baseline_comparison.csv) | Head-to-head benchmark: Trivial vs. Simple TF-IDF vs. SpotifySupportAgent |
| **Dataset Profiling Artifacts** | [`results/dataset_profile/`](results/dataset_profile/) | Empirical metrics, schema profiling, top 10 brands, and brand comparison CSVs |
| **Intent Discovery Artifacts** | [`results/intent_discovery/`](results/intent_discovery/) | 12-class taxonomy documentation, intent distribution, and curated examples |
| **Comprehensive Final Report** | [`README.md`](#phase-4-comprehensive-evaluation-baselines--project-report) | Problem framing, non-goals, misleading headline analysis, failure modes, roadmap, decision log |

---

## Note on Raw Dataset & Reproducibility

- **Raw Dataset Omission in Git**: The raw Twitter Customer Support CSV (`data/raw/twcs/twcs.csv`, 516.5 MB / 492.58 MiB, 2,811,774 rows) is intentionally excluded from Git tracking via `.gitignore` to keep the repository lightweight and prevent clone timeouts.
- **Self-Contained Evaluation & Inference**: The repository **already contains** all derived knowledge artifacts, representative conversation traces, curated resolution SOPs, and the 200-example golden evaluation set. You can run the agent (`python src/main.py`), execute the comprehensive evaluation harness (`python evaluation/evaluate.py`), run both baselines, and execute the full test suite (`python -m unittest discover -s tests -p "test*.py"`) immediately without downloading or processing the 516.5 MB raw dataset.
- **When is the Raw Dataset Required?**: The raw `twcs.csv` is needed **only** if you wish to re-stream the entire 2.8-million row dataset from scratch using `python src/data/profile_dataset.py` or re-run corpus-wide intent discovery across all 43,000 Spotify tweets with `python src/data/discover_intents.py`.

---

## Phase 1: Dataset Profiling & Brand Selection

In Phase 1, we conduct end-to-end dataset profiling on the raw Twitter Customer Support dataset without building models or fabricating assumptions. All metrics are computed directly by running code on the raw data.

### 1. Dataset Confirmation
The dataset files are located at:
- Full dataset: `data/raw/twcs/twcs.csv` (516.5 MB / 492.58 MiB, 2,811,774 records)
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
1. **Sufficient Volume & High Coherence**: 43,265 outbound brand tweets across 28,280 conversation threads with 91,808 total tweets (43,265 outbound + 48,543 inbound).
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

| Intent / Class | Category Type | Corpus Count | Share % | Default Action | Escalation Policy |
| :--- | :--- | :---: | :---: | :--- | :--- |
| `ambiguous_vague` | Edge/Special Class | 23,176 | 53.78% | `CLARIFICATION_PROMPT` | Auto-handle (request device, OS, error behavior) |
| `subscription_and_billing` | Support Intent | 5,210 | 12.09% | `INFO_PROVISION` | Escalate if checking private receipts/cards/refunds |
| `multi_intent` | Edge/Special Class | 3,061 | 7.10% | `DIRECT_TROUBLESHOOT` | Escalate if any sub-intent requires private account lookup |
| `music_catalog_and_content` | Support Intent | 3,030 | 7.03% | `INFO_PROVISION` | Auto-handle (explain licensing rights & explicit filter) |
| `playlist_library_and_curation`| Support Intent | 2,438 | 5.66% | `DIRECT_TROUBLESHOOT` | Auto-handle (shuffle cache, playlist recovery tool) |
| `account_access_and_login` | Support Intent | 2,106 | 4.89% | `INFO_PROVISION` | Escalate if reset email fails or account compromised |
| `non_support_or_chatter` | Edge/Special Class | 1,245 | 2.89% | `INFO_PROVISION` | Auto-handle (polite closing acknowledgment) |
| `playback_and_audio` | Support Intent | 1,044 | 2.42% | `DIRECT_TROUBLESHOOT` | Auto-handle (Bluetooth distance, hard device restart) |
| `offline_listening_and_downloads`| Support Intent | 832 | 1.93% | `DIRECT_TROUBLESHOOT` | Auto-handle (offline toggle, storage limit verification) |
| `unclassifiable_or_foreign`| Edge/Special Class | 459 | 1.07% | `INFO_PROVISION` | Auto-handle (refer non-English queries to email team) |
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
> **Human-Review Status & Provenance**: The golden evaluation set in `evaluation/golden_set_verified.csv` contains 200 validated evaluation records, meeting the assignment requirement of 150–250 examples. The provenance comprises two tiers: **25 examples** were verified entirely through manual review from scratch during initial annotation, while the remaining **175 examples** were processed through an AI-assisted human review workflow (`evaluation/review_tool.py`) comparing candidate annotations against independent Gemini review proposals (`evaluation/ai_proposals.json`) and historical `@SpotifyCares` agent resolutions before confirmation. All 200 records in `evaluation/golden_set_verified.csv` carry `review_status = "VERIFIED"`, `reviewed_by = "human"`, and ISO timestamps under `reviewed_at` (`python evaluation/validate_golden_set.py` passes with 0 errors and 0 warnings). The candidate evaluation set (`evaluation/golden_set.csv`, 200 rows) remains preserved as an untouched baseline with all 200 rows marked `review_status = "PENDING_HUMAN_REVIEW"`. AI proposals served strictly as review aids and never modified records autonomously.

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

---

## Phase 4: Comprehensive Evaluation, Baselines & Project Report

### 1. Problem Framing: What "Good" Means for `@SpotifyCares`

In public social media customer support on Twitter/X, "good" support behavior differs dramatically from internal enterprise ticketing or general-purpose chat:

1. **High First-Turn Public Troubleshooting**: Unlike telecommunications or banking brands that immediately deflect 70–80% of conversations to private DMs, a good Spotify agent autonomously resolves common client-side technical glitches (cache clearing, offline sync, clean reinstall sequences, bluetooth pairing) publicly in the first turn.
2. **Strict Financial & Credential Safety Boundaries**: A good agent must NEVER attempt to execute refunds, verify credit card receipts, or reset compromised passwords in public tweets. Any request involving billing disputes, SheerID verification failures, or account takeovers must immediately escalate to private Direct Messages via verified backstage links (`https://t.co/ldFdZRiNAt`).
3. **Grounded Explanations Over Hallucination**: The agent must provide verifiable steps and direct customers to official Spotify knowledge base articles (`support.spotify.com`), service status channels (`@SpotifyStatus`), or account recovery endpoints (`spotify.com/password-reset`).
4. **Empathetic, Concise Social Brand Voice**: Tweets must adhere to Twitter's brevity, maintain an empathetic, friendly tone ("Hey! Help's here"), and include standard support signoffs (e.g. `/AY`) to foster accountability.

---

### 2. What We Chose NOT to Build (Non-Goals)

To deliver a high-quality, reliable, and reproducible take-home project within scope, we explicitly chose **NOT** to build:

- **No Live Twitter/X API Bot**: Avoiding Twitter API v2 rate limits, enterprise pricing paywalls, and external auth flakiness. The agent is built as a self-contained, reproducible pipeline.
- **No Heavy Vector Database (e.g. Pinecone/Chroma)**: External vector services introduce network latency, API key fragility, and heavy C-extensions. A lightweight keyword and TF-IDF retriever operates locally in <5ms with 100% determinism.
- **No Live Customer Account Backend / Billing Database**: Generating fake billing databases or mock payment gateways creates false security assumptions. The agent strictly respects the boundary: financial operations require human DM escalation.
- **No Autonomous Password Reset or Account Recovery Execution**: The agent provides official self-service reset links or routes compromised accounts to human agents; it never solicits passwords or acts as an identity provider.
- **No Bloated Orchestration Frameworks (LangChain / LlamaIndex)**: Eliminating hundreds of transitive dependencies in favor of a clean, transparent 5-module pipeline (`types`, `classifier`, `retriever`, `policy`, `generator`).

---

### 3. Automated Evaluation Metrics & Headline Result

Evaluation is conducted across all **200 golden evaluation examples** (`evaluation/golden_set_verified.csv`), evaluating intent classification, action selection, and escalation decisions simultaneously:

```text
================================================================================
SPOTIFYCARES EVALUATION RESULTS SUMMARY (N = 200)
================================================================================
HEADLINE METRIC: Full Pipeline Accuracy = 91.00% (182 / 200)
  - Intent Classification Accuracy:  94.00% (Macro-F1: 0.9177)
  - Action Policy Accuracy:          93.00% (Macro-F1: 0.8788)
  - Escalation Decision Accuracy:    96.50% (Macro-F1: 0.6940)
================================================================================
```

#### Headline Result Definition
- **Headline Metric**: **Full Pipeline Accuracy = 91.00% (182 / 200)**
- **Definition**: The percentage of customer queries where the agent **simultaneously** predicts the correct intent, selects the correct policy action (`DIRECT_TROUBLESHOOT`, `INFO_PROVISION`, `CLARIFICATION_PROMPT`, `ESCALATE_TO_HUMAN_DM`), AND applies the correct escalation reason code.
- **Dataset**: `evaluation/golden_set_verified.csv` (200 records: 25 manual reviews + 175 AI-assisted human confirmations).
- **Denominator**: Exactly 200 unique multi-turn Twitter customer support conversations.

---

### 4. Benchmark Results versus Two Baselines

To rigorously evaluate our agent, we benchmark against two reproducible baselines on the exact same 200 golden evaluation records:

1. **Baseline 1 — Trivial (Majority Class)**: Predicts the majority corpus class (`ambiguous_vague` at 53.78% corpus share) with its default action (`CLARIFICATION_PROMPT`) and escalation (`N/A`) for all queries.
2. **Baseline 2 — Simple (TF-IDF Nearest-Neighbor)**: A lightweight unigram TF-IDF cosine-similarity classifier indexed on 96 representative intent examples from Phase 2 (`results/intent_discovery/intent_examples.json`), mapping predicted intents to standard default actions without context or escalation logic.
3. **Our Pipeline (`SpotifySupportAgent`)**: Full context-aware classifier, historical retriever, escalation policy engine, and conversational generator.

| Model / Architecture | Intent Accuracy | Intent Macro-F1 | Action Policy Accuracy | Escalation Accuracy | All-3 Pipeline Accuracy |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Baseline 1: Trivial (Majority Class)** | 7.00% | 0.0119 | 7.00% | 92.00% | 7.00% (14/200) |
| **Baseline 2: Simple (TF-IDF Similarity)** | 38.50% | 0.3538 | 59.00% | 92.00% | 34.00% (68/200) |
| **SpotifySupportAgent (Our Pipeline)** | **94.00%** | **0.9177** | **93.00%** | **96.50%** | **91.00% (182/200)** |

*Artifact saved: [`results/evaluation/baseline_comparison.csv`](results/evaluation/baseline_comparison.csv)*

---

### 5. LLM-as-Judge Rubric & Reply Quality Evaluation

Customer support replies were evaluated using a formal **6-dimension rubric** ([`evaluation/judge_rubric.md`](evaluation/judge_rubric.md)) on a 1–5 integer scale:

1. **Relevance & Intent Alignment (20%)**: Does the reply address the customer's actual complaint?
2. **Correctness & Actionability (20%)**: Are the troubleshooting steps technically accurate?
3. **Grounding in Official Knowledge (15%)**: Does it cite verified Spotify SOPs and official URLs?
4. **Policy & Escalation Compliance (20%)**: Does it auto-handle client bugs and route billing/security to DM?
5. **Security & Credential Safety (15%)**: Does it avoid requesting passwords or credit card details?
6. **Tone & Brand Voice (10%)**: Is it conversational, empathetic, and signed off (`/AY`)?

#### Aggregate Judge Results across 200 Golden Examples:
- **Mean Composite Quality Score**: **4.48 / 5.00**
- **Production Quality Pass Rate**: **84.0%** (composite score $\ge 4.0$)
- **Dimensional Breakdown**:
  - Relevance: `3.84 / 5.00`
  - Correctness: `4.23 / 5.00`
  - Grounding: `4.41 / 5.00`
  - Policy Compliance: `4.87 / 5.00`
  - Security & Safety: `4.96 / 5.00`
  - Tone & Voice: `4.89 / 5.00`

*Artifact saved: [`results/evaluation/judge_results.json`](results/evaluation/judge_results.json)*

---

### 6. Evidence of Human-vs-Judge Agreement

To validate judge calibration, a human evaluator rated a representative sample of **50 golden-set examples** across all 12 classes ([`evaluation/human_reply_ratings.csv`](evaluation/human_reply_ratings.csv)), including both routine successes and known agent edge cases:

| Agreement Metric | Value | Interpretation |
| :--- | :---: | :--- |
| **Sample Size ($N$)** | **50** | Stratified across all 12 taxonomy classes and failure cases |
| **Exact Score Agreement (rounded)** | **70.0%** (35 / 50) | High exact point concordance |
| **Within-1.0-Point Agreement** | **98.0%** (49 / 50) | 49 out of 50 scores within 1 rating point |
| **Mean Absolute Error (MAE)** | **0.356 points** | Average divergence under 0.4 points on a 5-point scale |
| **Pearson Correlation ($r$)** | **0.7527** | Strong positive linear correlation between human and judge |
| **Binary Quality Agreement ($P_o$)** | **82.0%** | Agreement on Pass ($\ge 4.0$) vs Fail ($< 4.0$) threshold |
| **Cohen's Kappa ($\kappa$)** | **0.5810** | Moderate-to-substantial inter-rater reliability |

#### Methodology & Limitations
- **What Humans Rated**: Human annotators evaluated whether the generated response accurately resolved the customer's intent, gave safe and correct advice, and properly adhered to escalation boundaries.
- **What Judge Rated**: The LLM Judge evaluated the exact same 50 responses on the 6-dimension rubric.
- **Limitations**: The judge tends to be slightly more lenient on subtle catalog licensing nuances (e.g. temporary geoblocking vs permanent track removal) where human annotators docked points for lack of country-specific context.

*Artifact saved: [`results/evaluation/human_agreement.json`](results/evaluation/human_agreement.json)*

---

### 7. "What is Misleading About My Headline Number?" (Mandatory Analysis)

While **91.00% Full Pipeline Accuracy** is an exceptional result on our 200-example golden set, presenting it as proof of "91% autonomous real-world customer support" would be dishonest and misleading for several reasons:

1. **Stratified Evaluation Set vs. Highly Skewed Real-World Traffic**:
   - In our 200-example golden set, classes are deliberately balanced (10–27 examples per category) to ensure rigorous testing across rare edge classes like outages, app crashes, and billing disputes.
   - In raw Twitter production traffic, **53.78% of inbound messages are vague complaints** ("spotify broken", "fix this"). On raw traffic, a trivial baseline predicting `ambiguous_vague` achieves 53.8% accuracy, while on our balanced golden set it achieves only 7.0%. Our headline metric measures multi-class diagnostic precision, not raw volume throughput.
2. **First-Turn Diagnostic Accuracy vs. End-to-End Resolution**:
   - Our headline number measures whether the agent generated the correct *first response* (e.g. correctly routing a double charge to DM or prescribing cache clearance for a freeze).
   - It does **NOT** measure whether the customer followed the instructions, whether the cache clear actually cured their device bug, or whether the human agent in DM successfully resolved their refund. High first-turn policy accuracy is a prerequisite for good support, not a guarantee of customer satisfaction (CSAT).
3. **200-Example Evaluation Size**:
   - 200 examples is statistically robust for take-home evaluation (surpassing the 150 requirement), but Twitter customer support conversations exhibit enormous lexical diversity, regional slang, and compound edge cases across millions of tweets.
4. **Historical Dataset Vintage (2017 TWCS Dataset)**:
   - The TWCS dataset was collected in 2017. Modern Spotify features—such as Spotify Blend, Canvas, Jam sessions, AI DJ, podcast video streaming, and two-factor authentication changes—do not exist in the 2017 corpus. An agent evaluated on 2017 data will face distribution drift when exposed to 2026 user complaints.
5. **Masked Private Resolutions**:
   - 30.79% of `@SpotifyCares` conversations deflect to private Direct Messages. Because TWCS contains only public tweets, ground truth for what happened inside the DM is hidden. We evaluate whether the agent *correctly escalated to DM*, not what internal tooling actions occurred backstage.

---

### 8. Failure Analysis: Top 5 Real Failure Modes

From the 18 errors observed during evaluation of the 200 golden examples, five primary failure modes emerged:

#### Failure Mode 1: Compounding Sibling Symptoms in Offline Playback
- **Real Example**: `SPOT-GOLD-002`  
  *Message*: *"@SpotifyCares why does my Spotify stop playing while offline? It is songs I've downloaded and haven't had the issue until yesterday."*
- **Expected**: `offline_listening_and_downloads` | `ESCALATE_TO_HUMAN_DM` | `PERSISTENT_BUG_INTERNAL_LOGS`
- **Actual**: `multi_intent` | `DIRECT_TROUBLESHOOT` | `N/A`
- **Why It Failed**: The message contained keywords for both playback ("stop playing") and offline storage ("offline", "downloaded"). The classifier split these into `multi_intent` rather than recognizing that playback failure while offline is a symptom of offline sync expiration. Policy subsequently offered standard playback steps rather than escalating for device logs.
- **Hypothesis for Improvement**: Introduce hierarchical intent subsumption rules: offline listening keywords subsume generic playback terms when qualified by phrases like "while offline" or "in airplane mode".

#### Failure Mode 2: Multi-Intent Policy Blindspot for Prepaid Gift Voucher Delivery
- **Real Example**: `SPOT-GOLD-004`  
  *Message*: *"@115888 hey there! I purchased a year subscription as a gift to be delivered on 11/18 and the email never was received. Could I please have it resent?"*
- **Expected**: `multi_intent` | `ESCALATE_TO_HUMAN_DM` | `BILLING_RECEIPT_OR_PAYMENT_VERIFICATION`
- **Actual**: `multi_intent` | `DIRECT_TROUBLESHOOT` | `N/A`
- **Why It Failed**: The query involves both account delivery ("email never was received") and subscription billing ("purchased a year subscription as a gift"). The multi-intent policy engine checked for explicit charge dispute terms ("refund", "charged twice") but lacked a rule for missing gift delivery tokens, defaulting to client troubleshooting.
- **Hypothesis for Improvement**: Expand financial escalation triggers to detect non-delivery of gift subscriptions, voucher codes, or promotional redemptions.

#### Failure Mode 3: Premature Plan Expiration vs. Routine Billing Inquiries
- **Real Example**: `SPOT-GOLD-007`  
  *Message*: *"@SpotifyCares i recently got premium but then my plan ended a week after I had set my plan. Please contact me asap."*
- **Expected**: `subscription_and_billing` | `ESCALATE_TO_HUMAN_DM` | `BILLING_RECEIPT_OR_PAYMENT_VERIFICATION`
- **Actual**: `subscription_and_billing` | `INFO_PROVISION` | `N/A`
- **Why It Failed**: The customer reported that their Premium plan abruptly ended after one week. The policy engine classified this as general subscription information (`INFO_PROVISION`) because it did not match explicit refund or double-charge keywords, failing to recognize that premature termination indicates a failed payment transaction requiring receipt lookup.
- **Hypothesis for Improvement**: Add pattern matching for temporal anomalies in paid duration (e.g. "plan ended early", "lost premium after a week") to trigger financial receipt verification.

#### Failure Mode 4: Over-Escalation of Self-Service Family Plan Admin Glitches
- **Real Example**: `SPOT-GOLD-008`  
  *Message*: *"@SpotifyCares just signed up for premium family plan my daughter cannot accept invite. We are both being treated as the plan admin."*
- **Expected**: `subscription_and_billing` | `INFO_PROVISION` | `N/A`
- **Actual**: `subscription_and_billing` | `ESCALATE_TO_HUMAN_DM` | `BILLING_RECEIPT_OR_PAYMENT_VERIFICATION`
- **Why It Failed**: The message triggered the policy rule for Family Plan verification failures, escalating to DM. However, Spotify's verified historical SOP handles address mismatch and family invitation admin role glitches via public account settings guidance (`spotify.com/account`).
- **Hypothesis for Improvement**: Separate self-service Family Plan invitation troubleshooting (address verification in account settings) from backend manual account audits.

#### Failure Mode 5: Feature Request Misclassified as Active Technical Bug
- **Real Example**: `SPOT-GOLD-009`  
  *Message*: *"@SpotifyCares listen spotify ima need y’all to make a way i can edit and tap multiple songs at a time and add them to a playlist instead of having to add them individually plz help me"*
- **Expected**: `playlist_library_and_curation` | `INFO_PROVISION` | `N/A`
- **Actual**: `playlist_library_and_curation` | `DIRECT_TROUBLESHOOT` | `N/A`
- **Why It Failed**: The customer made a feature suggestion ("make a way i can edit and tap multiple songs") but used distress language ("plz help me"). The agent classified the intent correctly but dispatched `DIRECT_TROUBLESHOOT` (prescribing cache clearance and shuffle reset) instead of providing informational feature status.
- **Hypothesis for Improvement**: Add an intentionality filter that detects feature request syntax ("make a way", "add a feature", "why can't we", "allow us to") to route to informational community feedback links rather than troubleshooting sequences.

---

### 9. What We'd Do Next with One More Week

If granted one additional week of engineering time, we would prioritize:

1. **Multi-Turn State Machine & Slot Filling**:
   Currently, context handling supports the immediate preceding turn. We would implement a lightweight finite-state machine (FSM) tracking slot variables across multiple turns (e.g., `device_os`, `spotify_version`, `troubleshooting_attempted: [reinstall, restart]`, `account_tier`), enabling progressive diagnostic narrowing without asking redundant clarification questions.
2. **Dense Semantic Retrieval with Embedding Re-Ranking**:
   Upgrade the keyword/TF-IDF retriever to a hybrid BM25 + dense bi-encoder retrieval architecture (e.g. `all-MiniLM-L6-v2`) indexed across 500+ official Spotify Community solutions, with cross-encoder re-ranking for complex technical symptoms.
3. **Live Sync with `@SpotifyStatus` / Downdetector Webhook**:
   Integrate real-time platform incident monitoring. When widespread outages occur, the agent should automatically elevate `service_outage_and_status` prior probability to 1.0 for incoming playback and login complaints, preventing fruitless cache-clearing advice during infrastructure downtime.
4. **Hierarchical Intent Subsumption Engine**:
   Resolve compound symptom overlap (e.g., offline download disappearance causing playback stops) by formalizing parent-child dependency trees across the 12 taxonomy classes.
5. **Expanded Multi-Annotator Golden Set Calibration**:
   Expand human verification to 500 examples with multi-annotator inter-rater agreement (Fleiss' kappa) to establish rigorous ground truth on ambiguous boundaries between licensing exclusions vs. regional catalog bugs.

---

### 10. Decision Log (12 Non-Obvious Engineering Decisions)

1. **DECISION**: Selecting `@SpotifyCares` over high-volume telecom accounts (`TMobileHelp`, `comcastcares`) or airlines.  
   **WHY**: Telecommunications brands in TWCS suffer from an extreme private DM deflection rate (81.8% for T-Mobile, 71.5% for Comcast) due to strict customer verification protocols, producing uninformative dead-end public threads. Spotify had a 30.8% DM deflection rate and provided public, actionable troubleshooting sequences (cache clears, restart sequences, reinstall guides) with genuine ground-truth resolution value.

2. **DECISION**: Formulating a 12-class taxonomy (8 functional support + 4 edge classes) rather than an unconstrained clustering.  
   **WHY**: Empirical analysis revealed that 53.78% of incoming tweets are unelaborated complaints ("broken", "help me") that cannot be classified into a technical domain without diagnostic clarification. Collapsing vague complaints into technical buckets forces hallucinated fixes; separating `ambiguous_vague` as an explicit class with a `CLARIFICATION_PROMPT` action prevents erroneous actions.

3. **DECISION**: Explicitly supporting `multi_intent` with sub-intent decomposition.  
   **WHY**: Approximately 7.1% of customer messages present compounding symptoms across domain boundaries (e.g. offline download disappearance combined with playback stuttering, or app crashes accompanied by billing lockouts). Decomposing these allows the policy engine to check whether *any* sub-intent requires financial or account escalation before prescribing client-side troubleshooting.

4. **DECISION**: Establishing a strict public vs. private escalation boundary for financial transactions and account takeovers.  
   **WHY**: An autonomous public social media bot must never attempt to resolve billing disputes, refund requests, or compromised passwords in public tweets. Attempting to do so risks leaking PII or executing unauthorized financial adjustments. These are strictly routed to private Direct Messages via verified links (`https://t.co/ldFdZRiNAt`) with specific reason codes.

5. **DECISION**: Constructing a 200-example golden set via stratified sampling (`seed=42`) rather than uniform random sampling.  
   **WHY**: A uniform random sample of TWCS would have resulted in ~108 vague complaints and fewer than 2 app-crash or outage examples. Stratified sampling ensured statistically meaningful coverage (10–27 examples) across every functional support intent and edge class, exceeding the 150-minimum requirement.

6. **DECISION**: Enforcing physical separation between `evaluation/golden_set.csv` and `evaluation/golden_set_verified.csv`.  
   **WHY**: To maintain strict provenance and avoid silently overwriting candidate suggestions with verified ground truth. `golden_set.csv` remains a permanent, unmodified candidate baseline with status `PENDING_HUMAN_REVIEW`, while `golden_set_verified.csv` records only human-approved annotations with timestamps and reviewer IDs.

7. **DECISION**: Using lightweight deterministic heuristic retrieval rather than an external vector database (e.g. Pinecone/Chroma).  
   **WHY**: For a take-home assignment and evaluation reproducibility, external vector databases add network latency, API key fragility, and heavy native dependencies. A curated keyword and TF-IDF retriever indexing official Spotify support articles and verified historical solutions operates offline in <5ms with 100% determinism.

8. **DECISION**: Providing dual-mode execution (Offline Deterministic vs. Online API) for the LLM Judge.  
   **WHY**: Evaluators should not be blocked from reproducing benchmark results or tests due to expired, missing, or rate-limited API keys. The deterministic judge mode implements the exact 6-dimension rubric rules locally, while API mode allows live LLM evaluation when keys are supplied.

9. **DECISION**: Keeping the raw 516.5 MB (492.58 MiB) TWCS dataset untracked in git via `.gitignore` while committing precomputed profiling artifacts.  
   **WHY**: Committing 516.5 MB raw CSVs bloats git repositories, exceeds GitHub file limits, and causes clone timeouts. Profiling scripts (`src/data/profile_dataset.py`) remain fully executable for local replication, while committed summaries under `results/dataset_profile/` provide immediate inspection.

10. **DECISION**: Defining Full Pipeline Accuracy (All-3: Intent + Action + Escalation simultaneously correct) as the headline metric.  
    **WHY**: In customer support automation, evaluating intent classification alone is dangerously misleading—an agent could correctly identify `subscription_and_billing` but prescribe self-service troubleshooting for an unauthorized credit card charge instead of escalating to human DM. Evaluating joint correctness enforces real-world operational safety.

11. **DECISION**: Implementing a lightweight built-in HTTP server (`review_tool.py`) for the human review workflow rather than a full React/Node stack.  
    **WHY**: Review tools for golden-set curation should have zero external npm dependencies, run on vanilla Python 3 standard library, and launch instantly across Windows, macOS, and Linux without build tooling.

12. **DECISION**: Retaining verbatim Twitter agent signoffs (e.g. `/AY`) and official redirect URLs in generated responses.  
    **WHY**: Authenticity to brand voice is a core evaluation dimension for public support bots. Emulating the real `@SpotifyCares` agent format ensures realistic evaluation against historical Twitter customer expectations.

