# Golden Evaluation Set: Sampling & Labeling Methodology

This document details the sampling strategy, schema specification, and two-phase human review workflow used to construct the 200-example golden evaluation set for the SpotifyCares AI Customer Support Agent.

---

## 1. Sampling Strategy

### Source Corpus
- **Dataset**: Twitter Customer Support dataset (`twcs.csv`, 2,811,774 total records).
- **Target Brand**: `@SpotifyCares` (43,265 outbound brand tweets across 28,280 multi-turn conversation threads).
- **Inbound Customer Messages Filtered**: 43,092 unique customer queries addressed to `@SpotifyCares`.

### Stratified Sampling (`seed=42`)
A uniform random sample of Twitter customer support messages would be overwhelmingly dominated by vague complaints (which comprise 53.78% of all inbound traffic). To ensure rigorous evaluation across all operational categories, we performed **deterministic stratified sampling** (`seed=42`):

- **Target Size**: Exactly 200 unique conversation threads (surpassing the assignment requirement of 150–250 hand-labelled examples).
- **Stratification Targets**:
  - `subscription_and_billing`: 27 examples (disputed charges, refunds, Student/Family verifications)
  - `playlist_library_and_curation`: 26 examples (shuffle algorithm, lost playlists, local files)
  - `playback_and_audio`: 25 examples (bluetooth stutter, device disconnection, audio cutting out)
  - `music_catalog_and_content`: 24 examples (licensing agreements, greyed-out songs, explicit filters)
  - `account_access_and_login`: 23 examples (password reset, locked accounts, compromised credentials)
  - `offline_listening_and_downloads`: 19 examples (disappeared downloads, 30-day online requirement)
  - `app_crash_and_performance`: 19 examples (startup crashes, black screen freezes, cache clearing)
  - `ambiguous_vague`: 14 examples (unelaborated complaints requiring diagnostic prompts)
  - `service_outage_and_status`: 10 examples (widespread server errors, platform status reports)
  - `non_support_or_chatter`: 8 examples (gratitude closures, polite compliments, social chatter)
  - `multi_intent`: 5 examples (compound issues requiring decomposition)

---

## 2. Dataset Schema & Fields

Every record in `evaluation/golden_set_verified.csv` adheres to the standardized task schema:

| Column Name | Type | Description |
| :--- | :--- | :--- |
| `example_id` | `string` | Unique identifier (`SPOT-GOLD-001` to `SPOT-GOLD-200`) |
| `conversation_id` | `int64` | Root tweet ID linking the multi-turn Twitter thread |
| `customer_message` | `string` | Verbatim text of the customer query |
| `conversation_context` | `string` | Preceding conversation context turn (or "None (thread root)") |
| `intent` | `string` | Ground-truth intent from the 12-class taxonomy |
| `expected_action` | `string` | Expected policy action (`DIRECT_TROUBLESHOOT`, `INFO_PROVISION`, `CLARIFICATION_PROMPT`, `ESCALATE_TO_HUMAN_DM`) |
| `escalation_reason` | `string` | Specific escalation code (e.g. `BILLING_RECEIPT_OR_PAYMENT_VERIFICATION`, or `N/A`) |
| `historical_resolution`| `string` | Actual historical reply provided by human `@SpotifyCares` agents |
| `review_status` | `string` | Verification status (`VERIFIED`) |
| `annotation_notes` | `string` | Justification and diagnostic notes |
| `reviewed_by` | `string` | Identifier of reviewer (`human`) |
| `reviewed_at` | `datetime`| ISO-8601 timestamp of human confirmation |
| `ai_proposed_intent` | `string` | Gemini AI proposal baseline |
| `ai_confidence` | `string` | Proposal confidence level (`HIGH`, `MEDIUM`, `LOW`) |
| `ai_agrees_with_candidate`| `boolean`| Whether AI agreed with initial candidate label |

---

## 3. Human Review & Verification Workflow

To guarantee genuine human-verified ground truth without fabrication, we implemented a structured two-phase human review workflow:

### Phase 1: Candidate Generation & AI Proposal Assistance
1. Candidate labels were extracted and prefilled using rule-based classification heuristics into `evaluation/golden_set.csv` (initialized with `review_status = 'PENDING_HUMAN_REVIEW'`).
2. Gemini AI independently evaluated all pending records against the Phase 2 taxonomy and annotation guidelines, generating structured proposals (`ai_proposals.json`) with confidence ratings and candidate disagreement flags.

### Phase 2: Interactive Human Verification
1. A dedicated local review tool (`evaluation/review_tool.py`) presented each record in a dual side-by-side comparison:
   - **Customer Query & Conversation Context**
   - **Candidate Suggestion vs. Gemini AI Recommendation**
   - **Historical Agent Resolution from TWCS**
2. For every record, a human annotator:
   - Verified the true customer intent.
   - Verified the correct policy action (ensuring client-side bugs are auto-handled while payment/credential issues are routed to DM).
   - Selected or confirmed the exact escalation reason code.
   - Confirmed and verified the record into `evaluation/golden_set_verified.csv`.
3. Candidate baseline `evaluation/golden_set.csv` remained strictly untouched as a pristine backup.

### Validation
Running `python evaluation/validate_golden_set.py` performs strict programmatic checks:
- Verifies exactly 200 rows (within the required 150–250 range).
- Verifies 200 unique `example_id`s with 0 duplicates.
- Confirms 100% of rows are marked `review_status = 'VERIFIED'`.
- Confirms 0 pending reviews, 0 schema errors, and 0 warnings.
