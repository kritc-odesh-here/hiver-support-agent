# SpotifyCares Golden Evaluation Set: Annotation Guidelines

This document defines the manual human review workflow for validating the candidate golden evaluation set (`evaluation/golden_set.csv`).

## 1. Ground-Truth Schema Definition

| Field | Description | Allowed Values |
| :--- | :--- | :--- |
| `example_id` | Unique evaluation identifier | `SPOT-GOLD-001` to `SPOT-GOLD-200` |
| `conversation_id` | Root tweet ID in TWCS | Integer string |
| `customer_message` | Verbatim text of customer complaint | Preserved original string |
| `conversation_context` | Prior conversation turns | Preceding turn or 'None (thread root)' |
| `intent` | Functional customer intent | One of 8 core intents, `multi_intent`, `ambiguous_vague`, `non_support_or_chatter` |
| `expected_action` | Target autonomous agent response | `DIRECT_TROUBLESHOOT`, `INFO_PROVISION`, `CLARIFICATION_PROMPT`, `ESCALATE_TO_HUMAN_DM` |
| `escalation_reason` | Security/Policy justification | `BILLING_RECEIPT_OR_PAYMENT_VERIFICATION`, `REQUIRES_ACCOUNT_BACKEND_ACCESS`, `PERSISTENT_BUG_INTERNAL_LOGS`, `N/A` |
| `historical_resolution` | Real resolution advice from SpotifyCares | Verbatim response from dataset |
| `review_status` | Human validation status | Initial: `PENDING_HUMAN_REVIEW` -> Final: `VERIFIED` |
| `annotation_notes` | Annotator reasoning & edge-case notes | Text |

## 2. Step-by-Step Human Review Workflow

As an annotator reviewing `evaluation/golden_set.csv`:

1. **Read `customer_message` and `conversation_context`**: Check if the customer's problem is understandable.
2. **Validate `intent`**:
   - If candidate intent accurately matches the taxonomy definitions in `results/intent_discovery/intent_taxonomy.md`, leave as is.
   - If the candidate intent was misclassified (e.g. `playback_and_audio` was assigned to an app crash), update `intent` to the correct category.
   - If the message bundles multiple unresolvable problems, set to `multi_intent`.
   - If the message lacks sufficient detail to diagnose, set to `ambiguous_vague`.
3. **Verify `expected_action` and `escalation_reason`**:
   - **AUTO-HANDLE**: Set to `DIRECT_TROUBLESHOOT` (reboot, clear cache, reinstall) or `INFO_PROVISION` (licensing rules, explicit filters). `escalation_reason` MUST be `N/A`.
   - **ESCALATE**: If customer requires private account access (billing refund, compromised password, SheerID verification), set to `ESCALATE_TO_HUMAN_DM` and record appropriate `escalation_reason`.
4. **Update `review_status`**:
   - Once reviewed and confirmed, change `review_status` from `PENDING_HUMAN_REVIEW` to `VERIFIED`.
   - If the example is low quality, spam, or non-English, mark `EXCLUDED`.

## 3. Escalation Policy Rules

### Strict Rules for Autonomous Agent Escalation:
1. **NEVER attempt financial or account modifications**: The agent must NEVER claim to execute a refund, cancel a credit card charge, or reset a password directly. These cases MUST be escalated to human DM.
2. **Safe Public Troubleshooting**: For client-side technical bugs, the agent should always provide non-destructive standard operating procedures (restart app, toggle offline mode, reinstall app) before escalating.
3. **No Halucinated URLs or Endpoints**: The agent must only provide verified Spotify official links (`support.spotify.com`, `spotify.com/password-reset`).
