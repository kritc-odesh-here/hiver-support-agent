# TWCS Dataset Quality Report

**Dataset File**: `sample.csv`  
**Total Records**: `93`  
**Analyzed on**: 2026-09-13 15:40:27

## 1. Schema & Completeness

| Column | Inferred Type | Missing Count | Missing % |
| :--- | :--- | :--- | :--- |
| `tweet_id` | int64 | 0 | 0.0% |
| `author_id` | string (handle/anonymized ID) | 0 | 0.0% |
| `inbound` | boolean | 0 | 0.0% |
| `created_at` | datetime (RFC 2822 format) | 0 | 0.0% |
| `text` | string | 0 | 0.0% |
| `response_tweet_id` | string (comma-separated int list) | 28 | 30.11% |
| `in_response_to_tweet_id` | float64/int64 (nullable parent ID) | 25 | 26.88% |

## 2. Structural & Relational Integrity

- **Duplicate Tweet IDs**: `0` (Unique tweet primary keys are strictly unique)
- **Orphan In-Response References**: `2` (3.03% of parent references). These tweets point to earlier parent tweets outside the collection window or deleted parent tweets.
- **Missing Downstream Child References**: `6` (8.33% of child references). Occurs when replies occur past the dataset scrape cutoff.
- **Empty or Whitespace-only Messages**: `0`
- **Ultra-short Messages (<5 chars)**: `0`

## 3. Support Utility & Deflection Concerns

In customer support automation, conversations that immediately deflect to Private Direct Messages (DM) provide zero public ground-truth resolution. The table below demonstrates the stark contrast between candidate brands:

| Brand | Total Outbound | DM Deflections | DM Deflection % | Utility for Support Agent Training |
| :--- | :--- | :--- | :--- | :--- |
| **AppleSupport** | 13 | 12 | 92.31% | Low/Impaired (heavily deflects to DM) |
| **SpotifyCares** | 8 | 0 | 0.0% | High (actionable troubleshooting) |
| **Tesco** | 8 | 2 | 25.0% | High (actionable troubleshooting) |
| **VirginTrains** | 4 | 0 | 0.0% | High (actionable troubleshooting) |
| **British_Airways** | 3 | 0 | 0.0% | High (actionable troubleshooting) |
| **ChaseSupport** | 1 | 1 | 100.0% | Low/Impaired (heavily deflects to DM) |
| **O2** | 1 | 1 | 100.0% | Low/Impaired (heavily deflects to DM) |
| **comcastcares** | 1 | 1 | 100.0% | Low/Impaired (heavily deflects to DM) |
| **sprintcare** | 1 | 1 | 100.0% | Low/Impaired (heavily deflects to DM) |
| **SouthwestAir** | 1 | 0 | 0.0% | High (actionable troubleshooting) |
