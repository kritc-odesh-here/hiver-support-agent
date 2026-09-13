"""
CLI Entry Point for the SpotifyCares AI Support Agent.

Usage:
  1. Interactive Shell:
     python src/main.py
  2. Single-Query Diagnostic:
     python src/main.py --query "My songs keep stopping over bluetooth"
     python src/main.py --query "I was charged twice for Premium" --context "Prior Turn: What plan?"
  3. Batch Edge Case Evaluation:
     python src/main.py --eval
"""

import os
import sys
import argparse
import json

# Ensure project root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.agent import SpotifySupportAgent, TaxonomyIntent, AgentAction, EscalationReason

# Ensure UTF-8 output on Windows consoles
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass


def print_response_card(resp):
    print("\n" + "=" * 80)
    print("SPOTIFYCARES SUPPORT AGENT DIAGNOSTIC REPORT")
    print("=" * 80)
    print(f"Customer Message:      \"{resp.customer_message}\"")
    print(f"Conversation Context:  {resp.conversation_context}")
    print("-" * 80)
    print(f"Predicted Intent:      {resp.intent} (Confidence: {resp.confidence:.2f})")
    if resp.sub_intents:
        print(f"Sub-Intents:           {', '.join(resp.sub_intents)}")
    print(f"Expected Action:       {resp.expected_action}")
    print(f"Escalation Reason:     {resp.escalation_reason}")
    esc_status = "[!] ESCALATE TO HUMAN DM" if resp.requires_escalation else "[+] AUTO-HANDLE"
    print(f"Escalation Status:     {esc_status}")
    print("-" * 80)
    print(f"Historical Reference:\n  {resp.historical_reference}")
    print("-" * 80)
    print(f"Generated Agent Response:\n  \"{resp.generated_response}\"")
    print("-" * 80)
    print(f"Decision Rationale:\n  {resp.rationale}")
    print("=" * 80 + "\n")


def run_interactive():
    agent = SpotifySupportAgent()
    print("=" * 80)
    print("WELCOME TO SPOTIFYCARES AI SUPPORT AGENT (INTERACTIVE SHELL)")
    print("=" * 80)
    print("Type your customer query and press Enter. Leave empty or type 'exit' to quit.")
    print("You will also have an optional prompt to add conversation context.\n")

    while True:
        try:
            msg = input("Customer Message > ").strip()
            if not msg or msg.lower() in ['exit', 'quit', 'q']:
                print("\nGoodbye!")
                break

            ctx = input("Context (press Enter if None) > ").strip()
            context = ctx if ctx else None

            resp = agent.process(msg, context=context)
            print_response_card(resp)
        except (KeyboardInterrupt, EOFError):
            print("\nSession ended.")
            break


def run_eval():
    agent = SpotifySupportAgent()
    print("=" * 80)
    print("RUNNING BATCH EVALUATION ACROSS TAXONOMY EDGE CASES")
    print("=" * 80)

    test_cases = [
        # 1. Playback & Audio
        ("My bluetooth speaker keeps disconnecting and music skips on android", None, TaxonomyIntent.PLAYBACK_AND_AUDIO, AgentAction.DIRECT_TROUBLESHOOT, EscalationReason.NA),
        # 2. Billing with refund request -> Escalate
        ("I was charged twice on my credit card for Premium and I need a refund", None, TaxonomyIntent.SUBSCRIPTION_AND_BILLING, AgentAction.ESCALATE_TO_HUMAN_DM, EscalationReason.BILLING_RECEIPT_OR_PAYMENT_VERIFICATION),
        # 3. Account hacked -> Escalate
        ("Someone changed my email and hacked my spotify account please help", None, TaxonomyIntent.ACCOUNT_ACCESS_AND_LOGIN, AgentAction.ESCALATE_TO_HUMAN_DM, EscalationReason.REQUIRES_ACCOUNT_BACKEND_ACCESS),
        # 4. App Crash -> Auto-handle
        ("Spotify app crashes immediately on launch with black screen on iPhone", None, TaxonomyIntent.APP_CRASH_AND_PERFORMANCE, AgentAction.DIRECT_TROUBLESHOOT, EscalationReason.NA),
        # 5. Offline listening -> Auto-handle
        ("My downloaded songs won't play offline on airplane mode", None, TaxonomyIntent.OFFLINE_LISTENING_AND_DOWNLOADS, AgentAction.DIRECT_TROUBLESHOOT, EscalationReason.NA),
        # 6. Music Catalog -> Info Provision
        ("Why are all Taylor Swift songs greyed out in my country?", None, TaxonomyIntent.MUSIC_CATALOG_AND_CONTENT, AgentAction.INFO_PROVISION, EscalationReason.NA),
        # 7. Playlist & Library -> Direct troubleshoot
        ("My shuffle button keeps playing the exact same 5 songs in my playlist", None, TaxonomyIntent.PLAYLIST_LIBRARY_AND_CURATION, AgentAction.DIRECT_TROUBLESHOOT, EscalationReason.NA),
        # 8. Service Outage -> Info Provision
        ("Is Spotify servers down for everyone else or just me?", None, TaxonomyIntent.SERVICE_OUTAGE_AND_STATUS, AgentAction.INFO_PROVISION, EscalationReason.NA),
        # 9. Vague / Ambiguous -> Clarification Prompt
        ("My Spotify is broken please fix it", None, TaxonomyIntent.AMBIGUOUS_VAGUE, AgentAction.CLARIFICATION_PROMPT, EscalationReason.NA),
        # 10. Multi-intent -> Multi-intent handling
        ("The app crashed while downloading songs and now my billing says expired", None, TaxonomyIntent.MULTI_INTENT, AgentAction.DIRECT_TROUBLESHOOT, EscalationReason.NA),
        # 11. Non-support chatter -> Friendly closure
        ("Thank you so much Spotify, all sorted now cheers!", None, TaxonomyIntent.NON_SUPPORT_OR_CHATTER, AgentAction.INFO_PROVISION, EscalationReason.NA),
        # 12. Foreign language -> Email redirect
        ("เพลงใน spotify ฟังไม่ได้ ช่วยหน่อยครับ", None, TaxonomyIntent.UNCLASSIFIABLE_OR_FOREIGN, AgentAction.INFO_PROVISION, EscalationReason.NA),
        # 13. Persistent failure after reinstall -> Escalate
        ("I've restarted and tried reinstalling several times but songs still pause", "Prior Turn: Restart device", TaxonomyIntent.PLAYBACK_AND_AUDIO, AgentAction.ESCALATE_TO_HUMAN_DM, EscalationReason.PERSISTENT_BUG_INTERNAL_LOGS)
    ]

    passed = 0
    total = len(test_cases)

    print(f"{'#':<3} | {'Query':<35} | {'Predicted Intent':<28} | {'Action':<22} | {'Status':<8}")
    print("-" * 105)

    for idx, (msg, ctx, exp_intent, exp_action, exp_esc) in enumerate(test_cases, start=1):
        resp = agent.process(msg, context=ctx)
        intent_match = (resp.intent == exp_intent)
        action_match = (resp.expected_action == exp_action)
        is_ok = intent_match and action_match
        if is_ok:
            passed += 1
        status_str = "PASS" if is_ok else "FAIL"
        trunc_msg = (msg[:32] + "...") if len(msg) > 35 else msg
        print(f"{idx:<3} | {trunc_msg:<35} | {resp.intent:<28} | {resp.expected_action:<22} | {status_str:<8}")

    print("-" * 105)
    print(f"Evaluation Results: {passed} / {total} Passed ({passed/total*100:.1f}%)\n")


def main():
    parser = argparse.ArgumentParser(description="SpotifyCares AI Support Agent CLI")
    parser.add_argument('--query', type=str, default=None, help="Single query to evaluate")
    parser.add_argument('--context', type=str, default=None, help="Conversation context for single query")
    parser.add_argument('--eval', action='store_true', help="Run automated evaluation across edge cases")
    parser.add_argument('--json', action='store_true', help="Output single query result as JSON")
    args = parser.parse_args()

    agent = SpotifySupportAgent()

    if args.eval:
        run_eval()
    elif args.query:
        resp = agent.process(args.query, context=args.context)
        if args.json:
            print(json.dumps(resp.to_dict(), indent=2))
        else:
            print_response_card(resp)
    else:
        run_interactive()


if __name__ == "__main__":
    main()
