"""
AI Review Proposal Generator for SpotifyCares Golden Evaluation Set.

Analyzes each of the 175 pending candidate records in evaluation/golden_set.csv
against the Phase 2 taxonomy and annotation guidelines.

For every pending record, produces:
- example_id
- ai_proposed_intent
- ai_proposed_expected_action
- ai_proposed_escalation_reason
- ai_proposed_annotation_notes
- ai_confidence ('HIGH', 'MEDIUM', 'LOW')
- ai_agrees_with_candidate (bool)
- needs_human_attention (bool)

Saves all proposals to evaluation/ai_proposals.json.
Leaves evaluation/golden_set.csv, evaluation/golden_set_verified.csv, and raw data completely untouched.
Zero artificial human-reviews created. All pending rows remain PENDING_HUMAN_REVIEW.
"""

import os
import sys
import csv
import json
import re
from typing import Dict, Any, Tuple

# Ensure root directory is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.agent.classifier import IntentClassifier
from src.agent.policy import PolicyEngine
from src.agent.types import TaxonomyIntent, AgentAction, EscalationReason

CANDIDATE_PATH = os.path.join("evaluation", "golden_set.csv")
VERIFIED_PATH = os.path.join("evaluation", "golden_set_verified.csv")
PROPOSALS_PATH = os.path.join("evaluation", "ai_proposals.json")

VALID_INTENTS = [
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
]

VALID_ACTIONS = [
    'DIRECT_TROUBLESHOOT',
    'INFO_PROVISION',
    'CLARIFICATION_PROMPT',
    'ESCALATE_TO_HUMAN_DM'
]


def analyze_record(row: Dict[str, str], classifier: IntentClassifier, policy: PolicyEngine) -> Dict[str, Any]:
    """
    Performs deep inspection of customer message, conversation context, historical response,
    and candidate labels to determine Gemini's independent recommendation.
    """
    ex_id = row['example_id']
    msg = row.get('customer_message', '').strip()
    ctx = row.get('conversation_context', '').strip()
    hist = row.get('historical_resolution', '').strip()
    cand_intent = row.get('intent', '').strip()
    cand_action = row.get('expected_action', '').strip()
    cand_esc = row.get('escalation_reason', '').strip()

    msg_lower = msg.lower()
    ctx_lower = ctx.lower()
    hist_lower = hist.lower()
    full_text = f"{msg_lower} {ctx_lower}"

    # 1. Run classifier & policy pipeline as baseline
    cls_intent, sub_intents, confidence, cls_rationale = classifier.classify(msg, context=ctx)
    if cls_intent == 'unclassifiable_or_foreign':
        # Normalize to valid 11 taxonomy classes (map foreign to chatter closure or vague)
        cls_intent = 'non_support_or_chatter' if any(w in msg_lower for w in ['gracias', 'obrigado', 'merci']) else 'ambiguous_vague'

    pol_action, pol_esc, pol_requires_esc, pol_rationale = policy.evaluate(
        intent=cls_intent,
        sub_intents=sub_intents,
        message=msg,
        context=ctx
    )

    # 2. Expert Contextual & Domain Rules based on Phase 2 Guidelines
    # Check if historical response gives strong ground truth signal
    hist_had_dm = any(k in hist_lower for k in ['/dm', 'dm us', 'direct message', 't.co/ldfdzrinat', 'backstage'])
    hist_had_steps = any(k in hist_lower for k in ['logging out', 'restarting', 'reinstall', 'cache', 'settings', 'article'])
    hist_had_info = any(k in hist_lower for k in ['licensing', 'rights', 'student discount', 'family', '3,333'])

    ai_intent = cls_intent
    ai_action = pol_action
    ai_esc = pol_esc
    ai_conf = "HIGH"
    notes = []

    # Check for closure / gratitude / resolved issues
    if any(k in msg_lower for k in ['working fine now', 'sorted now', 'fixed now', 'working now', 'all good now']):
        ai_intent = TaxonomyIntent.NON_SUPPORT_OR_CHATTER
        ai_action = AgentAction.INFO_PROVISION
        ai_esc = EscalationReason.NA
        ai_conf = "HIGH"
        notes.append("Customer confirms issue is resolved/working now; polite closure.")

    # Check for specific billing disputes & money inquiries
    elif any(k in full_text for k in ['refund', 'charged twice', 'charged me twice', 'double charge', 'deducted', 'unknown charge', 'cancel my subscription', 'money back']):
        ai_intent = TaxonomyIntent.SUBSCRIPTION_AND_BILLING
        ai_action = AgentAction.ESCALATE_TO_HUMAN_DM
        ai_esc = EscalationReason.BILLING_RECEIPT_OR_PAYMENT_VERIFICATION
        ai_conf = "HIGH"
        notes.append("Explicit billing dispute or refund request requires secure human DM lookup.")

    # Check for Student / SheerID verification
    elif 'student' in full_text and any(k in full_text for k in ['sheerid', 'verification', 'verify', 'declined', 'discount']):
        ai_intent = TaxonomyIntent.SUBSCRIPTION_AND_BILLING
        ai_action = AgentAction.ESCALATE_TO_HUMAN_DM
        ai_esc = EscalationReason.STUDENT_OR_FAMILY_VERIFICATION_MANUAL_CHECK
        ai_conf = "HIGH"
        notes.append("Student discount or SheerID verification manual check.")

    # Check for Account takeover / compromise
    elif any(k in full_text for k in ['hacked', 'compromised', 'stolen', 'unauthorized login', 'email was changed', 'can\'t reset password', 'locked out']):
        ai_intent = TaxonomyIntent.ACCOUNT_ACCESS_AND_LOGIN
        ai_action = AgentAction.ESCALATE_TO_HUMAN_DM
        ai_esc = EscalationReason.REQUIRES_ACCOUNT_BACKEND_ACCESS
        ai_conf = "HIGH"
        notes.append("Security issue or account lockout requires credential lookup via DM.")

    # Check for explicit persistent failure after customer already attempted steps
    elif any(k in full_text for k in ['already restarted', 'tried reinstalling', 'reinstalled and', 'cleared cache but', 'clean reinstall', 'tried everything']):
        ai_action = AgentAction.ESCALATE_TO_HUMAN_DM
        ai_esc = EscalationReason.PERSISTENT_BUG_INTERNAL_LOGS
        ai_conf = "HIGH"
        notes.append("Customer explicitly tried standard troubleshooting; escalate for internal device logs.")

    # Check for Multi-Intent
    elif len(sub_intents) > 1 or ai_intent == TaxonomyIntent.MULTI_INTENT:
        ai_intent = TaxonomyIntent.MULTI_INTENT
        if any(si == TaxonomyIntent.SUBSCRIPTION_AND_BILLING for si in sub_intents) and hist_had_dm:
            ai_action = AgentAction.ESCALATE_TO_HUMAN_DM
            ai_esc = EscalationReason.COMPLEX_MULTI_ISSUE_ACCOUNT_AUDIT
        else:
            ai_action = AgentAction.DIRECT_TROUBLESHOOT
            ai_esc = EscalationReason.NA
        ai_conf = "MEDIUM"
        notes.append(f"Multi-issue query spanning: {', '.join(sub_intents)}.")

    # Check for Catalog / Licensing inquiry
    elif any(k in msg_lower for k in ['greyed out', 'licensing', 'explicit version', 'clean version', 'unavailable in my country', 'not available']):
        ai_intent = TaxonomyIntent.MUSIC_CATALOG_AND_CONTENT
        ai_action = AgentAction.INFO_PROVISION
        ai_esc = EscalationReason.NA
        ai_conf = "HIGH"
        notes.append("Catalog licensing, country availability, or explicit track filtering inquiry.")

    # Check for Outage
    elif any(k in msg_lower for k in ['is spotify down', 'server error 500', 'outage', 'crash for everyone']):
        ai_intent = TaxonomyIntent.SERVICE_OUTAGE_AND_STATUS
        ai_action = AgentAction.INFO_PROVISION
        ai_esc = EscalationReason.NA
        ai_conf = "HIGH"
        notes.append("Service outage or server status report; provide status info.")

    # Check for Vague complaints
    elif len(msg.split()) < 6 and any(k in msg_lower for k in ['broken', 'not working', 'sucks', 'fix this', 'help me']):
        ai_intent = TaxonomyIntent.AMBIGUOUS_VAGUE
        ai_action = AgentAction.CLARIFICATION_PROMPT
        ai_esc = EscalationReason.NA
        ai_conf = "HIGH"
        notes.append("Complaint lacks diagnostic details; ask for device, OS, and observed behavior.")

    # 3. Determine Confidence & Disagreement with Candidate
    # Normalize actions and escalation reason
    if ai_action != AgentAction.ESCALATE_TO_HUMAN_DM:
        ai_esc = EscalationReason.NA

    # Check candidate agreement
    intent_agree = (ai_intent == cand_intent)
    action_agree = (ai_action == cand_action)
    esc_agree = (ai_esc == cand_esc)
    agrees_with_candidate = intent_agree and action_agree and esc_agree

    # If Gemini disagrees with candidate, lower confidence to MEDIUM or LOW unless very obvious
    if not agrees_with_candidate:
        if ai_conf == "HIGH" and (ai_intent in [TaxonomyIntent.SUBSCRIPTION_AND_BILLING, TaxonomyIntent.ACCOUNT_ACCESS_AND_LOGIN]):
            # Very clear disagreement (e.g. candidate suggested direct troubleshoot for a refund)
            ai_conf = "HIGH"
        else:
            ai_conf = "MEDIUM"

    # Edge-case confidence adjustments
    if ai_intent in [TaxonomyIntent.AMBIGUOUS_VAGUE, TaxonomyIntent.MULTI_INTENT]:
        if ai_conf == "HIGH":
            ai_conf = "MEDIUM"
        needs_attention = True
    elif not agrees_with_candidate:
        needs_attention = True
    elif ai_action == AgentAction.ESCALATE_TO_HUMAN_DM:
        needs_attention = True
    else:
        needs_attention = False

    if not notes:
        notes.append(f"AI recommendation based on diagnostic symptoms: {ai_intent} -> {ai_action}.")

    notes_str = " ".join(notes)

    return {
        'example_id': ex_id,
        'ai_proposed_intent': ai_intent,
        'ai_proposed_expected_action': ai_action,
        'ai_proposed_escalation_reason': ai_esc,
        'ai_proposed_annotation_notes': notes_str,
        'ai_confidence': ai_conf,
        'ai_agrees_with_candidate': agrees_with_candidate,
        'needs_human_attention': needs_attention,
        'candidate_intent': cand_intent,
        'candidate_action': cand_action,
        'candidate_escalation_reason': cand_esc
    }


def main():
    print("=" * 80)
    print("GEMINI AI REVIEW PROPOSAL GENERATOR")
    print("=" * 80)

    if not os.path.exists(CANDIDATE_PATH):
        print(f"[-] Candidate golden set not found: {CANDIDATE_PATH}")
        sys.exit(1)

    # 1. Identify existing verified IDs
    verified_ids = set()
    if os.path.exists(VERIFIED_PATH):
        with open(VERIFIED_PATH, mode='r', encoding='utf-8', errors='replace') as f:
            reader = csv.DictReader(f)
            for r in reader:
                if r.get('review_status') == 'VERIFIED':
                    verified_ids.add(r['example_id'])
    print(f"[*] Found {len(verified_ids)} existing verified records in {VERIFIED_PATH}.")
    print(f"    (These records are protected and will NOT receive AI proposals)")

    # 2. Read candidate rows
    with open(CANDIDATE_PATH, mode='r', encoding='utf-8', errors='replace') as f:
        reader = csv.DictReader(f)
        all_rows = list(reader)

    pending_rows = [r for r in all_rows if r['example_id'] not in verified_ids]
    print(f"[*] Total candidate rows: {len(all_rows)}")
    print(f"[*] Total pending rows requiring AI review proposals: {len(pending_rows)}")

    # 3. Initialize reasoning engines
    classifier = IntentClassifier()
    policy = PolicyEngine()

    proposals = {}
    high_conf = 0
    med_conf = 0
    low_conf = 0
    agreements = 0
    disagreements = 0
    needs_attn = 0

    for row in pending_rows:
        prop = analyze_record(row, classifier, policy)
        ex_id = prop['example_id']
        proposals[ex_id] = prop

        if prop['ai_confidence'] == "HIGH":
            high_conf += 1
        elif prop['ai_confidence'] == "MEDIUM":
            med_conf += 1
        else:
            low_conf += 1

        if prop['ai_agrees_with_candidate']:
            agreements += 1
        else:
            disagreements += 1

        if prop['needs_human_attention']:
            needs_attn += 1

    # 4. Save proposals to JSON
    with open(PROPOSALS_PATH, mode='w', encoding='utf-8') as f:
        json.dump(proposals, f, indent=2, ensure_ascii=False)

    print(f"\n[+] Saved {len(proposals)} AI proposals to: {PROPOSALS_PATH}")
    print("=" * 80)
    print("PROPOSAL GENERATION SUMMARY:")
    print(f"  - Total AI Proposals Generated:     {len(proposals)} / {len(pending_rows)}")
    print(f"  - High Confidence Proposals:        {high_conf} ({(high_conf/len(proposals)*100):.1f}%)")
    print(f"  - Medium Confidence Proposals:      {med_conf} ({(med_conf/len(proposals)*100):.1f}%)")
    print(f"  - Low Confidence Proposals:         {low_conf} ({(low_conf/len(proposals)*100):.1f}%)")
    print(f"  - Candidate Agreements:             {agreements} ({(agreements/len(proposals)*100):.1f}%)")
    print(f"  - Candidate Disagreements:          {disagreements} ({(disagreements/len(proposals)*100):.1f}%)")
    print(f"  - Requiring Human Attention:        {needs_attn} ({(needs_attn/len(proposals)*100):.1f}%)")
    print(f"  - Existing Human-Verified Count:    {len(verified_ids)} / 150 minimum")
    print(f"  - Remaining to 150 Target:          {max(0, 150 - len(verified_ids))}")
    print("=" * 80)
    print("[*] All candidate records remain review_status = 'PENDING_HUMAN_REVIEW'.")
    print("[*] Zero records were marked VERIFIED automatically.")


if __name__ == '__main__':
    main()
