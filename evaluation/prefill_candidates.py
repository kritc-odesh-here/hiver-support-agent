"""
Pre-fill Candidate Labels for SpotifyCares Golden Set.

Generates high-accuracy candidate annotations (intent, expected_action, escalation_reason, notes)
and calculates uncertainty metrics for unreviewed examples in evaluation/golden_set.csv
using SpotifySupportAgent.

Key Principles:
1. NEVER marks any row as VERIFIED or human-reviewed. review_status remains 'PENDING_HUMAN_REVIEW'.
2. Preserves the 25 existing human-verified records in evaluation/golden_set_verified.csv intact.
3. Calculates uncertainty and assigns Priority Tiers so review_tool.py can surface
   ambiguous / difficult cases first for human audit.
4. Preserves evaluation/golden_set_backup.csv before making any modifications.
"""

import os
import sys
import csv
import shutil
import argparse
from typing import Dict, List, Tuple
from collections import Counter

# Ensure root directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.agent.agent import SpotifySupportAgent
from src.agent.types import TaxonomyIntent, AgentAction, EscalationReason

CANDIDATE_PATH = os.path.join("evaluation", "golden_set.csv")
BACKUP_PATH = os.path.join("evaluation", "golden_set_backup.csv")
VERIFIED_PATH = os.path.join("evaluation", "golden_set_verified.csv")

VALID_INTENTS = {
    'subscription_and_billing',
    'music_catalog_and_content',
    'playlist_library_and_curation',
    'account_access_and_login',
    'playback_and_audio',
    'offline_listening_and_downloads',
    'service_outage_and_status',
    'app_crash_and_performance',
    'ambiguous_vague',
    'multi_intent',
    'non_support_or_chatter'
}

VALID_ACTIONS = {
    'DIRECT_TROUBLESHOOT',
    'INFO_PROVISION',
    'CLARIFICATION_PROMPT',
    'ESCALATE_TO_HUMAN_DM'
}


def compute_uncertainty(agent_resp, customer_msg: str, historical_res: str) -> Tuple[float, str]:
    """
    Computes an uncertainty score in range [0.05, 0.99] and categorizes into Priority Tier.
    Higher uncertainty = higher priority for careful human review.
    """
    conf = getattr(agent_resp, 'confidence', 0.85)
    base_uncertainty = max(0.05, 1.0 - conf)

    uncertainty = base_uncertainty
    msg_lower = customer_msg.lower()
    res_lower = historical_res.lower()
    intent = agent_resp.intent
    action = agent_resp.expected_action

    # 1. Inherently ambiguous or multi-faceted queries need human eyes
    if intent == TaxonomyIntent.AMBIGUOUS_VAGUE:
        uncertainty += 0.28
    elif intent == TaxonomyIntent.MULTI_INTENT:
        uncertainty += 0.30

    # 2. Historical DM vs Policy Auto-troubleshoot Divergence
    # SpotifyCares historically used DM invites frequently. If historical went to DM but policy auto-handles,
    # or vice-versa, flag as high-value human validation case.
    historical_had_dm = any(k in res_lower for k in ['/dm', 'dm us', 'direct message', 't.co/ldfdzrinat', 'send us a dm'])
    if historical_had_dm and action != AgentAction.ESCALATE_TO_HUMAN_DM:
        uncertainty += 0.25
    elif not historical_had_dm and action == AgentAction.ESCALATE_TO_HUMAN_DM:
        uncertainty += 0.20

    # 3. Short / Vague expressions of frustration without clear symptoms
    if len(customer_msg.split()) < 6 or any(w in msg_lower for w in ["doesn't work", "broken", "sucks", "fix this", "wtf"]):
        uncertainty += 0.15

    # Clamp
    uncertainty = min(0.99, max(0.05, round(uncertainty, 2)))

    # Tier categorization
    if uncertainty >= 0.45 or intent in [TaxonomyIntent.AMBIGUOUS_VAGUE, TaxonomyIntent.MULTI_INTENT]:
        tier = "Tier 1 - Ambiguous / Edge Case (High Review Priority)"
    else:
        tier = "Tier 2 - Clear-Cut Candidate (Rapid Audit)"

    return uncertainty, tier


def main():
    parser = argparse.ArgumentParser(description="Pre-fill candidate labels using SpotifySupportAgent with uncertainty ranking.")
    parser.add_argument('--dry-run', action='store_true', help="Run pre-fill and print summary without overwriting golden_set.csv")
    args = parser.parse_args()

    print("=" * 80)
    print("SPOTIFYCARES GOLDEN SET: CANDIDATE PRE-FILL & UNCERTAINTY SCORING")
    print("=" * 80)

    if not os.path.exists(CANDIDATE_PATH):
        print(f"[-] Candidate file not found: {CANDIDATE_PATH}")
        sys.exit(1)

    # 1. Load existing human-verified records
    verified_ids = set()
    if os.path.exists(VERIFIED_PATH):
        with open(VERIFIED_PATH, mode='r', encoding='utf-8', errors='replace') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get('review_status') == 'VERIFIED':
                    verified_ids.add(row['example_id'])
        print(f"[*] Found {len(verified_ids)} genuinely human-verified records in {VERIFIED_PATH}.")
        print(f"    (These 25 records are 100% preserved and protected from alteration)")

    # 2. Read candidate rows
    with open(CANDIDATE_PATH, mode='r', encoding='utf-8', errors='replace') as f:
        reader = csv.DictReader(f)
        candidate_rows = list(reader)

    print(f"[*] Loaded {len(candidate_rows)} candidate rows from {CANDIDATE_PATH}.")

    # 3. Create backup if not already present
    if not os.path.exists(BACKUP_PATH) and not args.dry_run:
        shutil.copy2(CANDIDATE_PATH, BACKUP_PATH)
        print(f"[+] Created safety backup at: {BACKUP_PATH}")

    # 4. Initialize agent pipeline
    print("[*] Initializing SpotifySupportAgent for deterministic inference...")
    agent = SpotifySupportAgent()

    updated_rows = []
    prefilled_count = 0
    tier1_count = 0
    tier2_count = 0
    intent_counts = Counter()
    action_counts = Counter()

    for r in candidate_rows:
        ex_id = r['example_id']
        msg = r.get('customer_message', '')
        ctx = r.get('conversation_context', '')
        hist_res = r.get('historical_resolution', '')

        # If already human verified, preserve existing candidate values
        if ex_id in verified_ids:
            # Keep original row values, compute tier for completeness
            # review_status in candidate CSV remains PENDING_HUMAN_REVIEW
            updated_rows.append(r)
            continue

        # Process through agent
        agent_resp = agent.process(msg, context=ctx)

        # Normalize intent to valid 11 taxonomy classes
        proposed_intent = agent_resp.intent
        if proposed_intent not in VALID_INTENTS:
            proposed_intent = 'ambiguous_vague'

        proposed_action = agent_resp.expected_action
        if proposed_action not in VALID_ACTIONS:
            proposed_action = 'DIRECT_TROUBLESHOOT'

        # Determine escalation reason
        if proposed_action == 'ESCALATE_TO_HUMAN_DM':
            proposed_esc = agent_resp.escalation_reason
            if not proposed_esc or proposed_esc == 'N/A':
                if proposed_intent == 'subscription_and_billing':
                    proposed_esc = 'BILLING_RECEIPT_OR_PAYMENT_VERIFICATION'
                elif proposed_intent == 'account_access_and_login':
                    proposed_esc = 'REQUIRES_ACCOUNT_BACKEND_ACCESS'
                elif proposed_intent == 'multi_intent':
                    proposed_esc = 'COMPLEX_MULTI_ISSUE_ACCOUNT_AUDIT'
                else:
                    proposed_esc = 'PERSISTENT_BUG_INTERNAL_LOGS'
        else:
            proposed_esc = 'N/A'

        # Compute uncertainty and priority tier
        uncertainty, tier = compute_uncertainty(agent_resp, msg, hist_res)

        # Generate annotation note with decision rationale
        notes = (
            f"Agent proposal: {proposed_intent} (conf: {agent_resp.confidence:.2f}). "
            f"Action: {proposed_action} [{proposed_esc}]. "
            f"Policy rationale: {agent_resp.rationale}"
        )

        row_copy = dict(r)
        row_copy['intent'] = proposed_intent
        row_copy['expected_action'] = proposed_action
        row_copy['escalation_reason'] = proposed_esc
        row_copy['annotation_notes'] = notes
        row_copy['review_status'] = 'PENDING_HUMAN_REVIEW'  # Strictly preserved! Never auto-verified.
        row_copy['uncertainty_score'] = f"{uncertainty:.2f}"
        row_copy['priority_tier'] = tier

        updated_rows.append(row_copy)
        prefilled_count += 1
        if "Tier 1" in tier:
            tier1_count += 1
        else:
            tier2_count += 1
        intent_counts[proposed_intent] += 1
        action_counts[proposed_action] += 1

    print(f"\n[+] Pre-fill processing complete:")
    print(f"    - Already Human-Verified (Preserved): {len(verified_ids)}")
    print(f"    - Pending Candidates Pre-filled:      {prefilled_count}")
    print(f"    - Tier 1 (Ambiguous / Priority Review): {tier1_count}")
    print(f"    - Tier 2 (Clean-cut / Rapid Audit):    {tier2_count}")

    print("\n[*] Proposed Intent Distribution (Pending candidates):")
    for it, cnt in intent_counts.most_common():
        print(f"    - {it:<35}: {cnt:>3}")

    print("\n[*] Proposed Action Distribution (Pending candidates):")
    for act, cnt in action_counts.most_common():
        print(f"    - {act:<30}: {cnt:>3}")

    if not args.dry_run:
        # Determine all fieldnames
        fieldnames = list(candidate_rows[0].keys())
        for extra in ['uncertainty_score', 'priority_tier']:
            if extra not in fieldnames:
                fieldnames.append(extra)

        with open(CANDIDATE_PATH, mode='w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for r in updated_rows:
                writer.writerow(r)

        print(f"\n[+] Successfully saved updated candidate proposals to: {CANDIDATE_PATH}")
        print("    - All pending rows remain review_status = 'PENDING_HUMAN_REVIEW'")
        print("    - Zero artificial human-reviews created")
    else:
        print("\n[*] DRY RUN: No files were modified.")

    print("=" * 80)


if __name__ == "__main__":
    main()
