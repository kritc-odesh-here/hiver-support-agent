"""
Golden Evaluation Set Validation Script.

Audits the golden evaluation set to ensure:
1. Between 150 and 250 examples exist (meets assignment requirement).
2. Unique example_id across all rows.
3. All required fields are non-empty.
4. All rows have review_status == 'VERIFIED'.
5. All intent values belong to the approved taxonomy.
6. expected_action values are valid.
7. escalation_reason is appropriately set ('N/A' for auto-handled, non-empty for escalations).
8. Preserves proposed/verified field integrity.
"""

import os
import sys
import csv
import argparse

# Valid Taxonomy Classes
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

REQUIRED_COLUMNS = [
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
]


def validate_file(file_path):
    print("=" * 80)
    print(f"VALIDATING GOLDEN SET: {file_path}")
    print("=" * 80)

    if not os.path.exists(file_path):
        print(f"[-] ERROR: Target file not found at: {file_path}")
        return False, ["File not found"]

    errors = []
    warnings = []
    rows = []

    with open(file_path, mode='r', encoding='utf-8', errors='replace') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        
        # Check required columns
        for col in REQUIRED_COLUMNS:
            if col not in fieldnames:
                errors.append(f"Missing required column header: '{col}'")

        if errors:
            print("\n[-] Schema validation failed with missing headers:")
            for err in errors:
                print(f"    - {err}")
            return False, errors

        for idx, row in enumerate(reader, start=1):
            rows.append((idx, row))

    # 1. Total count check
    total_rows = len(rows)
    print(f"[*] Total rows read: {total_rows}")
    if not (150 <= total_rows <= 250):
        errors.append(f"Expected between 150 and 250 rows (assignment requirement), but found {total_rows}.")

    # 2. Field-level checks
    seen_ids = set()
    pending_count = 0
    verified_count = 0

    for line_num, r in rows:
        ex_id = r.get('example_id', '').strip()
        if not ex_id:
            errors.append(f"Row {line_num}: Empty example_id.")
        elif ex_id in seen_ids:
            errors.append(f"Row {line_num}: Duplicate example_id '{ex_id}'.")
        else:
            seen_ids.add(ex_id)

        # Check required fields non-empty
        for col in REQUIRED_COLUMNS:
            val = r.get(col, '').strip()
            if not val:
                errors.append(f"Row {line_num} ({ex_id}): Empty value for required field '{col}'.")

        # Intent validation
        intent = r.get('intent', '').strip()
        if intent not in VALID_INTENTS:
            errors.append(f"Row {line_num} ({ex_id}): Invalid intent '{intent}'. Must be one of {sorted(VALID_INTENTS)}.")

        # Action validation
        action = r.get('expected_action', '').strip()
        if action not in VALID_ACTIONS:
            errors.append(f"Row {line_num} ({ex_id}): Invalid expected_action '{action}'. Must be one of {sorted(VALID_ACTIONS)}.")

        # Escalation reason validation
        esc_reason = r.get('escalation_reason', '').strip()
        if action == 'ESCALATE_TO_HUMAN_DM':
            if esc_reason == 'N/A' or not esc_reason:
                errors.append(f"Row {line_num} ({ex_id}): Action is 'ESCALATE_TO_HUMAN_DM' but escalation_reason is '{esc_reason}'.")
        else:
            if esc_reason != 'N/A' and esc_reason:
                warnings.append(f"Row {line_num} ({ex_id}): Action is '{action}' but escalation_reason is '{esc_reason}' (expected 'N/A').")

        # Review status check
        status = r.get('review_status', '').strip()
        if status == 'VERIFIED':
            verified_count += 1
        elif status == 'PENDING_HUMAN_REVIEW':
            pending_count += 1
            errors.append(f"Row {line_num} ({ex_id}): review_status is still 'PENDING_HUMAN_REVIEW'. Needs human verification.")
        else:
            errors.append(f"Row {line_num} ({ex_id}): Unknown review_status '{status}'.")

    print(f"\n[*] Audit Statistics:")
    print(f"    - Unique Example IDs: {len(seen_ids)} / {total_rows}")
    print(f"    - Verified Rows:     {verified_count} / {total_rows}")
    print(f"    - Pending Review:    {pending_count} / {total_rows}")
    print(f"    - Total Errors:      {len(errors)}")
    print(f"    - Total Warnings:    {len(warnings)}")

    if errors:
        print("\n[-] VALIDATION FAILED:")
        # Show first 15 errors
        for err in errors[:15]:
            print(f"    [!] {err}")
        if len(errors) > 15:
            print(f"    ... and {len(errors) - 15} more errors.")
        print("-" * 80)
        return False, errors
    else:
        print("\n[+] VALIDATION SUCCESSFUL: Dataset meets all golden evaluation standards!")
        print("-" * 80)
        return True, []


def main():
    parser = argparse.ArgumentParser(description="Validate Golden Evaluation Set integrity and review status.")
    parser.add_argument(
        '--file',
        type=str,
        default=os.path.join("evaluation", "golden_set_verified.csv"),
        help="Path to CSV file to validate (default: evaluation/golden_set_verified.csv)"
    )
    args = parser.parse_args()

    success, _ = validate_file(args.file)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
