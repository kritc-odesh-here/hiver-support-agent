"""
AI-Assisted Human Review Tool for SpotifyCares Golden Evaluation Set.

Features:
- Web GUI mode (default, http://localhost:8000) using Python's built-in http.server.
- Interactive CLI mode (--cli) for fast terminal-based review.
- Integrates Gemini AI review proposals from evaluation/ai_proposals.json alongside original candidate suggestions.
- Fast-track review actions:
  1. [ACCEPT GEMINI PROPOSAL & VERIFY] - Adopts Gemini's verified recommendation in 1 click / 1 keystroke.
  2. [ACCEPT CURRENT CANDIDATE & VERIFY] - Adopts candidate suggestion.
  3. [EDIT & VERIFY] - Allows human annotator to override any field.
  4. [SKIP] - Keeps record in PENDING_HUMAN_REVIEW.
- Prioritized Review Queues:
  * High-confidence Gemini agreements first for rapid confirmation.
  * Medium-confidence cases second.
  * Disagreements and attention cases prioritized for closer scrutiny.
- Preserves evaluation/golden_set.csv untouched as candidate backup.
- Preserves all 25 existing verified records in evaluation/golden_set_verified.csv.
- Dynamic Progress Tracking:
  * Human Verified: X / 150 minimum target
  * Pending: X
  * AI Proposals Completed: 175 / 175
  * Gemini Disagreements: X
  * Needs Human Attention: X
"""

import os
import sys
import csv
import json
import argparse
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

# Ensure UTF-8 output on Windows consoles
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

GOLDEN_CANDIDATE_PATH = os.path.join("evaluation", "golden_set.csv")
GOLDEN_VERIFIED_PATH = os.path.join("evaluation", "golden_set_verified.csv")
AI_PROPOSALS_PATH = os.path.join("evaluation", "ai_proposals.json")
TARGET_VERIFIED_COUNT = 150

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

ESCALATION_REASONS = [
    'N/A',
    'BILLING_RECEIPT_OR_PAYMENT_VERIFICATION',
    'REQUIRES_ACCOUNT_BACKEND_ACCESS',
    'PERSISTENT_BUG_INTERNAL_LOGS',
    'COMPLEX_MULTI_ISSUE_ACCOUNT_AUDIT',
    'STUDENT_OR_FAMILY_VERIFICATION_MANUAL_CHECK',
    'OTHER_ESCALATION'
]

VERIFIED_FIELDNAMES = [
    'example_id',
    'conversation_id',
    'customer_message',
    'conversation_context',
    'intent',
    'expected_action',
    'escalation_reason',
    'historical_resolution',
    'review_status',
    'annotation_notes',
    'proposed_intent',
    'proposed_expected_action',
    'proposed_escalation_reason',
    'reviewed_by',
    'reviewed_at',
    'ai_proposed_intent',
    'ai_proposed_expected_action',
    'ai_proposed_escalation_reason',
    'ai_confidence',
    'ai_agrees_with_candidate'
]


class ReviewDataManager:
    def __init__(self, candidate_path=GOLDEN_CANDIDATE_PATH, verified_path=GOLDEN_VERIFIED_PATH, proposals_path=AI_PROPOSALS_PATH):
        self.candidate_path = candidate_path
        self.verified_path = verified_path
        self.proposals_path = proposals_path
        self.candidates = []
        self.verified_map = {}
        self.ai_proposals = {}
        self.load_data()

    def load_data(self):
        if not os.path.exists(self.candidate_path):
            raise FileNotFoundError(f"Candidate golden set not found: {self.candidate_path}")

        # 1. Load candidate set (read-only)
        with open(self.candidate_path, mode='r', encoding='utf-8', errors='replace') as f:
            reader = csv.DictReader(f)
            self.candidates = list(reader)

        # 2. Load existing verified records (resuming progress)
        if os.path.exists(self.verified_path):
            with open(self.verified_path, mode='r', encoding='utf-8', errors='replace') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    self.verified_map[row['example_id']] = row

        # 3. Load Gemini AI review proposals if available
        if os.path.exists(self.proposals_path):
            with open(self.proposals_path, mode='r', encoding='utf-8', errors='replace') as f:
                self.ai_proposals = json.load(f)

        self._recompute_queues()

    def _recompute_queues(self):
        """Builds prioritized review queues separating agreements vs disagreements."""
        high_conf_agreements = []
        med_conf_agreements = []
        disagreements_or_attention = []
        other_pending = []
        verified_indices = []

        for idx, cand in enumerate(self.candidates):
            ex_id = cand['example_id']
            if ex_id in self.verified_map:
                verified_indices.append(idx)
                continue

            prop = self.ai_proposals.get(ex_id, {})
            conf = prop.get('ai_confidence', 'MEDIUM')
            agrees = prop.get('ai_agrees_with_candidate', False)
            needs_attn = prop.get('needs_human_attention', False)

            if not agrees or needs_attn or conf == 'LOW':
                disagreements_or_attention.append(idx)
            elif conf == 'HIGH' and agrees:
                high_conf_agreements.append(idx)
            elif conf == 'MEDIUM' and agrees:
                med_conf_agreements.append(idx)
            else:
                other_pending.append(idx)

        # Standard priority queue: High conf agreements -> Med conf agreements -> Disagreements -> Other -> Verified
        self.priority_order = high_conf_agreements + med_conf_agreements + disagreements_or_attention + other_pending + verified_indices
        self.agreements_queue = high_conf_agreements + med_conf_agreements
        self.disagreements_queue = disagreements_or_attention

    def get_progress(self, queue_name='priority'):
        total = len(self.candidates)
        verified = len(self.verified_map)
        pending = total - verified

        # Count stats across pending
        unverified_ex_ids = [c['example_id'] for c in self.candidates if c['example_id'] not in self.verified_map]
        proposals_completed = sum(1 for eid in unverified_ex_ids if eid in self.ai_proposals)
        disagreements = sum(1 for eid in unverified_ex_ids if not self.ai_proposals.get(eid, {}).get('ai_agrees_with_candidate', True))
        needs_attention = sum(1 for eid in unverified_ex_ids if self.ai_proposals.get(eid, {}).get('needs_human_attention', False))

        # Determine queue indices
        if queue_name == 'agreements':
            active_queue = [i for i in self.agreements_queue if self.candidates[i]['example_id'] not in self.verified_map]
        elif queue_name == 'disagreements':
            active_queue = [i for i in self.disagreements_queue if self.candidates[i]['example_id'] not in self.verified_map]
        elif queue_name == 'seq':
            active_queue = [i for i, c in enumerate(self.candidates) if c['example_id'] not in self.verified_map]
        else: # 'priority'
            active_queue = [i for i in self.priority_order if self.candidates[i]['example_id'] not in self.verified_map]

        first_pending_idx = active_queue[0] if active_queue else 0

        return {
            'total': total,
            'verified': verified,
            'pending': pending,
            'target': TARGET_VERIFIED_COUNT,
            'target_met': verified >= TARGET_VERIFIED_COUNT,
            'target_remaining': max(0, TARGET_VERIFIED_COUNT - verified),
            'ai_proposals_completed': proposals_completed,
            'ai_disagreements': disagreements,
            'needs_attention_count': needs_attention,
            'first_pending_idx': first_pending_idx,
            'active_queue_count': len(active_queue),
            'queue_indices': active_queue
        }

    def get_example(self, index, queue_name='priority'):
        if index < 0 or index >= len(self.candidates):
            return None
        cand = self.candidates[index]
        ex_id = cand['example_id']
        is_verified = ex_id in self.verified_map
        ver = self.verified_map.get(ex_id, {})
        prop = self.ai_proposals.get(ex_id, {})

        # Determine next index in active queue
        prog = self.get_progress(queue_name)
        active_queue = prog['queue_indices']
        next_idx = None
        for q_idx in active_queue:
            if q_idx != index:
                next_idx = q_idx
                break
        if next_idx is None and self.candidates:
            next_idx = (index + 1) % len(self.candidates)

        return {
            'index': index,
            'example_id': ex_id,
            'conversation_id': cand['conversation_id'],
            'customer_message': cand['customer_message'],
            'conversation_context': cand['conversation_context'],
            'historical_resolution': cand['historical_resolution'],
            # Candidate values
            'candidate_intent': cand['intent'],
            'candidate_action': cand['expected_action'],
            'candidate_escalation_reason': cand['escalation_reason'],
            'candidate_notes': cand['annotation_notes'],
            # Gemini Review Proposal
            'has_ai_proposal': bool(prop),
            'ai_proposed_intent': prop.get('ai_proposed_intent', cand['intent']),
            'ai_proposed_action': prop.get('ai_proposed_expected_action', cand['expected_action']),
            'ai_proposed_escalation': prop.get('ai_proposed_escalation_reason', cand['escalation_reason']),
            'ai_confidence': prop.get('ai_confidence', 'MEDIUM'),
            'ai_notes': prop.get('ai_proposed_annotation_notes', 'AI Proposal based on Phase 2 taxonomy.'),
            'ai_agrees_with_candidate': prop.get('ai_agrees_with_candidate', True),
            'needs_human_attention': prop.get('needs_human_attention', False),
            # Current verified values if already reviewed
            'current_intent': ver.get('intent', prop.get('ai_proposed_intent', cand['intent'])),
            'current_action': ver.get('expected_action', prop.get('ai_proposed_expected_action', cand['expected_action'])),
            'current_escalation': ver.get('escalation_reason', prop.get('ai_proposed_escalation_reason', cand['escalation_reason'])),
            'current_notes': ver.get('annotation_notes', prop.get('ai_proposed_annotation_notes', cand['annotation_notes'])),
            'review_status': 'VERIFIED' if is_verified else 'PENDING_HUMAN_REVIEW',
            'reviewed_by': ver.get('reviewed_by', ''),
            'reviewed_at': ver.get('reviewed_at', ''),
            'next_queue_idx': next_idx
        }

    def save_verification(self, index, confirmed_intent, confirmed_action, confirmed_escalation, confirmed_notes, adopt_source='gemini'):
        if index < 0 or index >= len(self.candidates):
            return False
        cand = self.candidates[index]
        ex_id = cand['example_id']
        prop = self.ai_proposals.get(ex_id, {})

        # Enforce escalation reason rules
        if confirmed_action != 'ESCALATE_TO_HUMAN_DM':
            confirmed_escalation = 'N/A'
        elif confirmed_escalation == 'N/A' or not confirmed_escalation:
            confirmed_escalation = 'OTHER_ESCALATION'

        verified_row = {
            'example_id': ex_id,
            'conversation_id': cand['conversation_id'],
            'customer_message': cand['customer_message'],
            'conversation_context': cand['conversation_context'],
            'intent': confirmed_intent,
            'expected_action': confirmed_action,
            'escalation_reason': confirmed_escalation,
            'historical_resolution': cand['historical_resolution'],
            'review_status': 'VERIFIED',
            'annotation_notes': confirmed_notes.strip(),
            'proposed_intent': cand['intent'],
            'proposed_expected_action': cand['expected_action'],
            'proposed_escalation_reason': cand['escalation_reason'],
            'reviewed_by': 'human',
            'reviewed_at': datetime.now().isoformat(),
            'ai_proposed_intent': prop.get('ai_proposed_intent', ''),
            'ai_proposed_expected_action': prop.get('ai_proposed_expected_action', ''),
            'ai_proposed_escalation_reason': prop.get('ai_proposed_escalation_reason', ''),
            'ai_confidence': prop.get('ai_confidence', ''),
            'ai_agrees_with_candidate': str(prop.get('ai_agrees_with_candidate', ''))
        }

        self.verified_map[ex_id] = verified_row
        self.persist_verified_file()
        self._recompute_queues()
        return True

    def persist_verified_file(self):
        # Write verified records in candidate order, preserving existing 25 records
        with open(self.verified_path, mode='w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=VERIFIED_FIELDNAMES)
            writer.writeheader()
            for cand in self.candidates:
                ex_id = cand['example_id']
                if ex_id in self.verified_map:
                    writer.writerow(self.verified_map[ex_id])


HTML_UI = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>SpotifyCares Golden Set - AI-Assisted Rapid Reviewer</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
  :root {
    --bg-base: #101010;
    --bg-surface: #181818;
    --bg-card: #222222;
    --bg-hover: #2a2a2a;
    --spotify-green: #1db954;
    --spotify-green-hover: #1ed760;
    --gemini-purple: #8b5cf6;
    --gemini-gradient: linear-gradient(135deg, #6366f1 0%, #a855f7 50%, #ec4899 100%);
    --text-primary: #ffffff;
    --text-secondary: #b3b3b3;
    --border-color: #333333;
    --badge-pending: #f59e0b;
    --badge-verified: #10b981;
    --badge-danger: #ef4444;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: 'Inter', -apple-system, sans-serif;
    background-color: var(--bg-base);
    color: var(--text-primary);
    min-height: 100vh;
    display: flex;
    flex-direction: column;
  }
  header {
    background-color: var(--bg-surface);
    border-bottom: 1px solid var(--border-color);
    padding: 10px 24px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: 12px;
  }
  .brand { display: flex; align-items: center; gap: 10px; font-weight: 700; font-size: 1.1rem; }
  .brand-logo { color: var(--spotify-green); font-size: 1.35rem; }
  .progress-info { display: flex; align-items: center; gap: 12px; font-size: 0.84rem; flex-wrap: wrap; }
  .stat-badge {
    padding: 4px 10px;
    border-radius: 16px;
    background-color: var(--bg-card);
    font-weight: 600;
  }
  .stat-verified { color: var(--badge-verified); border: 1px solid var(--badge-verified); background: rgba(16, 185, 129, 0.1); }
  .stat-disagree { color: #f87171; border: 1px solid #f87171; }
  .stat-attn { color: var(--badge-pending); border: 1px solid var(--badge-pending); }
  .progress-bar-container {
    width: 120px;
    height: 8px;
    background: var(--bg-card);
    border-radius: 4px;
    overflow: hidden;
  }
  .progress-bar-fill {
    height: 100%;
    background: var(--spotify-green);
    width: 0%;
    transition: width 0.3s;
  }
  .queue-select-group {
    display: flex;
    background: var(--bg-card);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    overflow: hidden;
  }
  .queue-btn {
    padding: 6px 11px;
    font-size: 0.78rem;
    font-weight: 600;
    cursor: pointer;
    background: transparent;
    color: var(--text-secondary);
    border: none;
    transition: all 0.2s;
  }
  .queue-btn.active {
    background: var(--spotify-green);
    color: #000;
    font-weight: 700;
  }
  main {
    flex: 1;
    max-width: 1350px;
    width: 100%;
    margin: 16px auto;
    padding: 0 20px;
    display: grid;
    grid-template-columns: 1.15fr 0.85fr;
    gap: 18px;
  }
  .card {
    background-color: var(--bg-surface);
    border: 1px solid var(--border-color);
    border-radius: 12px;
    padding: 20px;
    display: flex;
    flex-direction: column;
    gap: 14px;
  }
  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    border-bottom: 1px solid var(--border-color);
    padding-bottom: 10px;
  }
  .meta-title { font-size: 1.2rem; font-weight: 700; color: var(--spotify-green); }
  .pill {
    padding: 3px 9px;
    border-radius: 12px;
    font-size: 0.72rem;
    font-weight: 700;
    text-transform: uppercase;
  }
  .pill.pending { background: rgba(245, 158, 11, 0.15); color: var(--badge-pending); border: 1px solid var(--badge-pending); }
  .pill.verified { background: rgba(16, 185, 129, 0.15); color: var(--badge-verified); border: 1px solid var(--badge-verified); }
  .pill.agree { background: rgba(16, 185, 129, 0.15); color: #34d399; border: 1px solid #10b981; }
  .pill.disagree { background: rgba(239, 68, 68, 0.15); color: #f87171; border: 1px solid #ef4444; }
  .pill.high { background: rgba(99, 102, 241, 0.15); color: #818cf8; border: 1px solid #6366f1; }
  .field-group { display: flex; flex-direction: column; gap: 5px; }
  .field-label { font-size: 0.75rem; text-transform: uppercase; font-weight: 700; color: var(--text-secondary); letter-spacing: 0.5px; }
  .message-box {
    background-color: var(--bg-card);
    border-left: 4px solid var(--spotify-green);
    padding: 12px 15px;
    border-radius: 0 8px 8px 0;
    font-size: 0.95rem;
    line-height: 1.45;
  }
  .context-box {
    background-color: rgba(255, 255, 255, 0.02);
    border: 1px dashed var(--border-color);
    padding: 9px 13px;
    border-radius: 8px;
    font-size: 0.83rem;
    color: var(--text-secondary);
    line-height: 1.35;
  }
  .resolution-box {
    background-color: var(--bg-card);
    border-left: 4px solid #3b82f6;
    padding: 10px 13px;
    border-radius: 0 8px 8px 0;
    font-size: 0.85rem;
    color: #cbd5e1;
    line-height: 1.4;
  }
  /* Dual Comparison Cards */
  .proposal-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 12px;
    margin-top: 4px;
  }
  .proposal-box {
    background: var(--bg-card);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    padding: 12px;
    display: flex;
    flex-direction: column;
    gap: 6px;
    font-size: 0.84rem;
  }
  .proposal-box.gemini-box {
    border-color: #6366f1;
    background: rgba(99, 102, 241, 0.04);
  }
  .box-title { font-weight: 700; font-size: 0.82rem; margin-bottom: 4px; display: flex; justify-content: space-between; align-items: center; }
  .val-row { display: flex; justify-content: space-between; padding: 2px 0; border-bottom: 1px solid rgba(255,255,255,0.05); }
  .val-label { color: var(--text-secondary); font-size: 0.75rem; }
  .val-content { font-weight: 600; text-align: right; max-width: 60%; word-break: break-word; }
  select, textarea {
    width: 100%;
    background-color: var(--bg-card);
    border: 1px solid var(--border-color);
    color: var(--text-primary);
    padding: 8px 11px;
    border-radius: 8px;
    font-size: 0.9rem;
    font-family: inherit;
  }
  select:focus, textarea:focus { outline: none; border-color: var(--spotify-green); }
  select:disabled { opacity: 0.4; cursor: not-allowed; }
  textarea { min-height: 60px; resize: vertical; font-size: 0.82rem; }
  .action-bar {
    grid-column: 1 / -1;
    background-color: var(--bg-surface);
    border: 1px solid var(--border-color);
    border-radius: 12px;
    padding: 12px 20px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: 10px;
  }
  .btn-group { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
  button {
    font-family: inherit;
    font-weight: 600;
    font-size: 0.88rem;
    padding: 9px 15px;
    border-radius: 8px;
    cursor: pointer;
    border: 1px solid var(--border-color);
    background-color: var(--bg-card);
    color: var(--text-primary);
    display: inline-flex;
    align-items: center;
    gap: 6px;
    transition: all 0.2s;
  }
  button:hover { background-color: var(--bg-hover); }
  .btn-gemini-accept {
    background: var(--gemini-gradient);
    border: none;
    color: #ffffff;
    font-weight: 700;
    box-shadow: 0 2px 8px rgba(139, 92, 246, 0.3);
  }
  .btn-gemini-accept:hover { opacity: 0.9; transform: translateY(-1px); }
  .btn-candidate-accept {
    background-color: #2e3a4e;
    border-color: #3b82f6;
    color: #93c5fd;
    font-weight: 600;
  }
  .btn-primary {
    background-color: var(--spotify-green);
    border-color: var(--spotify-green);
    color: #000;
    font-weight: 700;
  }
  .keyboard-hint { font-size: 0.72rem; opacity: 0.75; }
  .kbd {
    background: #333;
    padding: 1px 5px;
    border-radius: 3px;
    border: 1px solid #444;
    color: #eee;
    font-family: monospace;
    font-size: 0.75rem;
  }
</style>
</head>
<body>

<header>
  <div class="brand">
    <span class="brand-logo">♫</span>
    <span>SpotifyCares Golden Reviewer (AI-Assisted)</span>
  </div>

  <div class="progress-info">
    <div class="stat-badge stat-verified" id="stat-verified">Verified: 25 / 150 Target</div>
    <div class="stat-badge" id="stat-pending">Pending: 175</div>
    <div class="stat-badge stat-disagree" id="stat-disagree">Disagreements: --</div>
    <div class="stat-badge stat-attn" id="stat-attn">Needs Attention: --</div>
    <div class="progress-bar-container" title="Progress to 150 Golden Examples">
      <div class="progress-bar-fill" id="progress-fill"></div>
    </div>
  </div>

  <div class="queue-select-group">
    <button class="queue-btn active" id="qbtn-prio" onclick="setQueue('priority')">⚡ Fast Track (Agreements First)</button>
    <button class="queue-btn" id="qbtn-disagree" onclick="setQueue('disagreements')">⚠️ Disagreements Queue</button>
    <button class="queue-btn" id="qbtn-seq" onclick="setQueue('seq')">Sequential (1-200)</button>
  </div>
</header>

<main>
  <!-- Left Column: Customer Context & Conversation -->
  <section class="card">
    <div class="card-header">
      <div>
        <span class="meta-title" id="disp-example-id">SPOT-GOLD-026</span>
        <span style="color: var(--text-secondary); font-size: 0.85rem; margin-left: 8px;">
          Conv ID: <span id="disp-conv-id">#000000</span>
        </span>
      </div>
      <div style="display: flex; gap: 6px;">
        <span id="disp-agree-pill" class="pill agree">✓ Gemini Agrees</span>
        <span id="disp-status-pill" class="pill pending">PENDING</span>
      </div>
    </div>

    <div class="field-group">
      <div class="field-label">Customer Message (Verbatim)</div>
      <div class="message-box" id="disp-customer-message">Loading message...</div>
    </div>

    <div class="field-group">
      <div class="field-label">Conversation Context (Prior Turns)</div>
      <div class="context-box" id="disp-context">None (thread root)</div>
    </div>

    <div class="field-group">
      <div class="field-label">Historical SpotifyCares Resolution</div>
      <div class="resolution-box" id="disp-resolution">Loading response...</div>
    </div>

    <!-- Dual Comparison Panel -->
    <div class="field-group" style="margin-top: 6px;">
      <div class="field-label">Proposal Comparison: Candidate vs. Gemini Review</div>
      <div class="proposal-grid">
        <!-- Current Candidate -->
        <div class="proposal-box">
          <div class="box-title">
            <span>📋 Current Candidate</span>
          </div>
          <div class="val-row">
            <span class="val-label">Intent:</span>
            <span class="val-content" id="disp-cand-intent">--</span>
          </div>
          <div class="val-row">
            <span class="val-label">Action:</span>
            <span class="val-content" id="disp-cand-action">--</span>
          </div>
          <div class="val-row">
            <span class="val-label">Escalation:</span>
            <span class="val-content" id="disp-cand-esc">--</span>
          </div>
        </div>

        <!-- Gemini AI Review -->
        <div class="proposal-box gemini-box">
          <div class="box-title">
            <span>✨ Gemini Review</span>
            <span id="disp-gemini-conf" class="pill high">HIGH</span>
          </div>
          <div class="val-row">
            <span class="val-label">Proposed Intent:</span>
            <span class="val-content" id="disp-gemini-intent" style="color: #c084fc;">--</span>
          </div>
          <div class="val-row">
            <span class="val-label">Proposed Action:</span>
            <span class="val-content" id="disp-gemini-action" style="color: #c084fc;">--</span>
          </div>
          <div class="val-row">
            <span class="val-label">Proposed Escalation:</span>
            <span class="val-content" id="disp-gemini-esc" style="color: #c084fc;">--</span>
          </div>
          <div style="font-size: 0.74rem; color: var(--text-secondary); margin-top: 4px;" id="disp-gemini-notes">
            Reasoning...
          </div>
        </div>
      </div>
    </div>
  </section>

  <!-- Right Column: Human Validation Confirmation -->
  <section class="card">
    <div class="card-header">
      <span style="font-weight: 700; font-size: 1.05rem;">Human Validation Controls</span>
      <span style="font-size: 0.8rem; color: var(--text-secondary);">Index: <span id="disp-index-label">1</span> / 200</span>
    </div>

    <div class="field-group">
      <label class="field-label" for="select-intent">Confirmed Intent</label>
      <select id="select-intent"></select>
    </div>

    <div class="field-group">
      <label class="field-label" for="select-action">Confirmed Expected Action</label>
      <select id="select-action" onchange="handleActionChange()"></select>
    </div>

    <div class="field-group">
      <label class="field-label" for="select-escalation">Confirmed Escalation Reason</label>
      <select id="select-escalation"></select>
      <div id="esc-hint" style="font-size: 0.72rem; color: var(--text-secondary);">
        * Active only when Expected Action is ESCALATE_TO_HUMAN_DM
      </div>
    </div>

    <div class="field-group">
      <label class="field-label" for="text-notes">Human Reviewer Notes</label>
      <textarea id="text-notes" placeholder="Confirmed notes, reasoning, or edge-case context..."></textarea>
    </div>

    <div id="disp-verified-meta" style="font-size: 0.78rem; color: var(--badge-verified); min-height: 18px;"></div>
  </section>

  <!-- Action Bar -->
  <div class="action-bar">
    <div class="btn-group">
      <button onclick="navPrevious()">← Back <span class="keyboard-hint">(B)</span></button>
      <button onclick="navNext()">Skip → <span class="keyboard-hint">(S)</span></button>
      <button onclick="jumpToPending()">Next Unverified</button>
    </div>

    <div class="btn-group">
      <button class="btn-candidate-accept" onclick="acceptCandidate()">
        Accept Candidate <span class="keyboard-hint">(C)</span>
      </button>
      <button class="btn-gemini-accept" onclick="acceptGemini()">
        ✨ ACCEPT GEMINI & VERIFY <span class="keyboard-hint">(Enter)</span>
      </button>
      <button class="btn-primary" onclick="verifyManual()">
        Confirm Custom Edit <span class="keyboard-hint">(Ctrl+Enter)</span>
      </button>
    </div>
  </div>
</main>

<script>
let currentIndex = 0;
let currentQueue = 'priority';
let currentExample = null;

const INTENTS = """ + json.dumps(VALID_INTENTS) + """;
const ACTIONS = """ + json.dumps(VALID_ACTIONS) + """;
const ESCALATIONS = """ + json.dumps(ESCALATION_REASONS) + """;

function initDropdowns() {
  const iSel = document.getElementById('select-intent');
  iSel.innerHTML = INTENTS.map(i => `<option value="${i}">${i}</option>`).join('');

  const aSel = document.getElementById('select-action');
  aSel.innerHTML = ACTIONS.map(a => `<option value="${a}">${a}</option>`).join('');

  const eSel = document.getElementById('select-escalation');
  eSel.innerHTML = ESCALATIONS.map(e => `<option value="${e}">${e}</option>`).join('');
}

function setQueue(queue) {
  currentQueue = queue;
  document.getElementById('qbtn-prio').className = 'queue-btn ' + (queue === 'priority' ? 'active' : '');
  document.getElementById('qbtn-disagree').className = 'queue-btn ' + (queue === 'disagreements' ? 'active' : '');
  document.getElementById('qbtn-seq').className = 'queue-btn ' + (queue === 'seq' ? 'active' : '');
  jumpToPending();
}

function handleActionChange() {
  const action = document.getElementById('select-action').value;
  const escSel = document.getElementById('select-escalation');
  if (action === 'ESCALATE_TO_HUMAN_DM') {
    escSel.disabled = false;
    if (escSel.value === 'N/A') {
      escSel.value = 'BILLING_RECEIPT_OR_PAYMENT_VERIFICATION';
    }
  } else {
    escSel.value = 'N/A';
    escSel.disabled = true;
  }
}

async function loadProgress() {
  try {
    const res = await fetch(`/api/progress?queue=${currentQueue}`);
    const data = await res.json();

    document.getElementById('stat-verified').innerText = `Verified: ${data.verified} / ${data.target} Target`;
    document.getElementById('stat-pending').innerText = `Pending: ${data.pending}`;
    document.getElementById('stat-disagree').innerText = `Disagreements: ${data.ai_disagreements}`;
    document.getElementById('stat-attn').innerText = `Needs Attention: ${data.needs_attention_count}`;

    const pct = Math.min(100, (data.verified / data.target * 100)).toFixed(1);
    document.getElementById('progress-fill').style.width = pct + '%';
    return data;
  } catch (e) {
    console.error("Progress fetch error:", e);
  }
}

async function loadExample(idx) {
  try {
    const res = await fetch(`/api/example?index=${idx}&queue=${currentQueue}`);
    if (!res.ok) return;
    const data = await res.json();
    currentExample = data;
    currentIndex = idx;

    document.getElementById('disp-example-id').innerText = data.example_id;
    document.getElementById('disp-conv-id').innerText = '#' + data.conversation_id;
    document.getElementById('disp-index-label').innerText = (idx + 1);

    // Status pill
    const statusPill = document.getElementById('disp-status-pill');
    if (data.review_status === 'VERIFIED') {
      statusPill.className = 'pill verified';
      statusPill.innerText = 'VERIFIED';
      document.getElementById('disp-verified-meta').innerText =
        `✓ Human-reviewed by ${data.reviewed_by || 'human'} at ${(data.reviewed_at || '').replace('T', ' ').slice(0, 19)}`;
    } else {
      statusPill.className = 'pill pending';
      statusPill.innerText = 'PENDING REVIEW';
      document.getElementById('disp-verified-meta').innerText = '';
    }

    // Agreement pill
    const agreePill = document.getElementById('disp-agree-pill');
    if (data.ai_agrees_with_candidate) {
      agreePill.className = 'pill agree';
      agreePill.innerText = '✓ Gemini Agrees';
    } else {
      agreePill.className = 'pill disagree';
      agreePill.innerText = '≠ Gemini Disagrees';
    }

    // Conversation box
    document.getElementById('disp-customer-message').innerText = data.customer_message;
    document.getElementById('disp-context').innerText = data.conversation_context;
    document.getElementById('disp-resolution').innerText = data.historical_resolution;

    // Candidate box
    document.getElementById('disp-cand-intent').innerText = data.candidate_intent;
    document.getElementById('disp-cand-action').innerText = data.candidate_action;
    document.getElementById('disp-cand-esc').innerText = data.candidate_escalation_reason;

    // Gemini box
    document.getElementById('disp-gemini-conf').innerText = data.ai_confidence;
    document.getElementById('disp-gemini-conf').className = 'pill ' + (data.ai_confidence.toLowerCase());
    document.getElementById('disp-gemini-intent').innerText = data.ai_proposed_intent;
    document.getElementById('disp-gemini-action').innerText = data.ai_proposed_action;
    document.getElementById('disp-gemini-esc').innerText = data.ai_proposed_escalation;
    document.getElementById('disp-gemini-notes').innerText = data.ai_notes;

    // Form inputs default to Gemini proposal if unverified, or current verified
    document.getElementById('select-intent').value = data.current_intent;
    document.getElementById('select-action').value = data.current_action;
    document.getElementById('select-escalation').value = data.current_escalation;
    document.getElementById('text-notes').value = data.current_notes;

    handleActionChange();
    loadProgress();
  } catch (e) {
    console.error("Load example error:", e);
  }
}

// 1. Accept Gemini Proposal & Verify
async function acceptGemini() {
  if (!currentExample) return;
  const payload = {
    index: currentIndex,
    intent: currentExample.ai_proposed_intent,
    expected_action: currentExample.ai_proposed_action,
    escalation_reason: currentExample.ai_proposed_escalation,
    annotation_notes: currentExample.ai_notes,
    adopt_source: 'gemini'
  };
  await sendVerification(payload);
}

// 2. Accept Candidate & Verify
async function acceptCandidate() {
  if (!currentExample) return;
  const payload = {
    index: currentIndex,
    intent: currentExample.candidate_intent,
    expected_action: currentExample.candidate_action,
    escalation_reason: currentExample.candidate_escalation_reason,
    annotation_notes: currentExample.candidate_notes,
    adopt_source: 'candidate'
  };
  await sendVerification(payload);
}

// 3. Confirm Manual / Custom Edit & Verify
async function verifyManual() {
  const payload = {
    index: currentIndex,
    intent: document.getElementById('select-intent').value,
    expected_action: document.getElementById('select-action').value,
    escalation_reason: document.getElementById('select-escalation').value,
    annotation_notes: document.getElementById('text-notes').value,
    adopt_source: 'manual'
  };
  await sendVerification(payload);
}

async function sendVerification(payload) {
  try {
    const res = await fetch('/api/verify', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    if (res.ok) {
      const prog = await loadProgress();
      if (currentExample && currentExample.next_queue_idx !== undefined && currentExample.next_queue_idx !== null) {
        loadExample(currentExample.next_queue_idx);
      } else if (prog && prog.first_pending_idx !== undefined) {
        loadExample(prog.first_pending_idx);
      } else {
        navNext();
      }
    }
  } catch (e) {
    console.error("Verification save error:", e);
  }
}

function navNext() {
  if (currentExample && currentExample.next_queue_idx !== null && currentExample.next_queue_idx !== undefined) {
    loadExample(currentExample.next_queue_idx);
  } else if (currentIndex < 199) {
    loadExample(currentIndex + 1);
  }
}

function navPrevious() {
  if (currentIndex > 0) loadExample(currentIndex - 1);
}

async function jumpToPending() {
  const prog = await loadProgress();
  loadExample(prog.first_pending_idx);
}

// Global Keyboard Navigation
window.addEventListener('keydown', (e) => {
  const activeTag = document.activeElement.tagName;
  const isInput = activeTag === 'TEXTAREA' || activeTag === 'INPUT';

  if (isInput) {
    if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
      verifyManual();
      e.preventDefault();
    }
    return;
  }

  if (e.key === 'Enter') {
    acceptGemini();
    e.preventDefault();
  } else if (e.key === 'c' || e.key === 'C') {
    acceptCandidate();
    e.preventDefault();
  } else if (e.key === 's' || e.key === 'S' || e.key === 'ArrowRight') {
    navNext();
    e.preventDefault();
  } else if (e.key === 'b' || e.key === 'B' || e.key === 'ArrowLeft') {
    navPrevious();
    e.preventDefault();
  }
});

// Startup initialization
initDropdowns();
jumpToPending();
</script>
</body>
</html>
"""


class ReviewRequestHandler(BaseHTTPRequestHandler):
    def __init__(self, data_mgr, *args, **kwargs):
        self.data_mgr = data_mgr
        super().__init__(*args, **kwargs)

    def log_message(self, format, *args):
        pass

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)

        if path in ['/', '/index.html']:
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(HTML_UI.encode('utf-8'))

        elif path == '/api/progress':
            queue = query.get('queue', ['priority'])[0]
            prog = self.data_mgr.get_progress(queue_name=queue)
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(prog).encode('utf-8'))

        elif path == '/api/example':
            idx_str = query.get('index', ['0'])[0]
            queue = query.get('queue', ['priority'])[0]
            try:
                idx = int(idx_str)
            except ValueError:
                idx = 0
            ex = self.data_mgr.get_example(idx, queue_name=queue)
            if ex is not None:
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(ex).encode('utf-8'))
            else:
                self.send_response(404)
                self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path == '/api/verify':
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)
            try:
                data = json.loads(body.decode('utf-8'))
                idx = data.get('index', 0)
                intent = data.get('intent', '')
                action = data.get('expected_action', '')
                escalation = data.get('escalation_reason', '')
                notes = data.get('annotation_notes', '')
                source = data.get('adopt_source', 'gemini')

                success = self.data_mgr.save_verification(idx, intent, action, escalation, notes, adopt_source=source)
                if success:
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps({'status': 'ok'}).encode('utf-8'))
                else:
                    self.send_response(400)
                    self.end_headers()
            except Exception as e:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(str(e).encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()


def run_cli_review(data_mgr, queue_mode='priority'):
    """Terminal CLI review loop with AI-assisted proposals."""
    print("=" * 80)
    print("SPOTIFYCARES GOLDEN SET AI-ASSISTED REVIEW (CLI MODE)")
    print("=" * 80)

    progress = data_mgr.get_progress(queue_name=queue_mode)
    print(f"[*] Human Verified:       {progress['verified']} / {TARGET_VERIFIED_COUNT} Target")
    print(f"[*] Remaining to Target:  {progress['target_remaining']}")
    print(f"[*] AI Proposals Loaded:  {progress['ai_proposals_completed']} / 175")
    print(f"[*] Gemini Disagreements: {progress['ai_disagreements']}")
    print(f"[*] Needs Attention:      {progress['needs_attention_count']}")
    print(f"[*] Active Queue:         {queue_mode} ({progress['active_queue_count']} pending items)")

    queue = progress['queue_indices']
    if not queue:
        print("\n[+] All pending items in this queue have already been human-verified!")
        return

    q_pos = 0
    while 0 <= q_pos < len(queue):
        idx = queue[q_pos]
        ex = data_mgr.get_example(idx, queue_name=queue_mode)
        cur_prog = data_mgr.get_progress(queue_name=queue_mode)

        print("\n" + "=" * 80)
        print(f"[{cur_prog['verified']}/{TARGET_VERIFIED_COUNT} Verified] Item {ex['example_id']} | Conv #{ex['conversation_id']}")
        agree_str = "[✓ Gemini Agrees]" if ex['ai_agrees_with_candidate'] else "[≠ Gemini Disagrees]"
        print(f"Status: {agree_str} | Confidence: {ex['ai_confidence']} | Attention: {ex['needs_human_attention']}")
        print("-" * 80)
        print(f"Customer Message:\n  \"{ex['customer_message']}\"\n")
        print(f"Context:\n  {ex['conversation_context']}\n")
        print(f"Historical Resolution:\n  {ex['historical_resolution']}\n")
        print("-" * 40 + " COMPARISON " + "-" * 40)
        print(f"{'Field':<20} | {'Candidate':<30} | {'Gemini Review'}")
        print("-" * 80)
        print(f"{'Intent':<20} | {ex['candidate_intent']:<30} | {ex['ai_proposed_intent']}")
        print(f"{'Expected Action':<20} | {ex['candidate_action']:<30} | {ex['ai_proposed_action']}")
        print(f"{'Escalation Reason':<20} | {ex['candidate_escalation_reason']:<30} | {ex['ai_proposed_escalation']}")
        print(f"Gemini Notes: {ex['ai_notes']}")
        print("-" * 80)

        cmd = input("Press [Enter/G] to Accept Gemini & Verify | [C] Accept Candidate | [E] Edit | [S] Skip | [Q] Quit > ").strip().lower()

        if cmd in ['', 'g', 'y', '1']:
            data_mgr.save_verification(
                idx,
                ex['ai_proposed_intent'],
                ex['ai_proposed_action'],
                ex['ai_proposed_escalation'],
                ex['ai_notes'],
                adopt_source='gemini'
            )
            print(f"[+] Human verified {ex['example_id']} using Gemini proposal.")
            cur_prog = data_mgr.get_progress(queue_name=queue_mode)
            queue = cur_prog['queue_indices']
        elif cmd in ['c', '2']:
            data_mgr.save_verification(
                idx,
                ex['candidate_intent'],
                ex['candidate_action'],
                ex['candidate_escalation_reason'],
                ex['candidate_notes'],
                adopt_source='candidate'
            )
            print(f"[+] Human verified {ex['example_id']} using candidate values.")
            cur_prog = data_mgr.get_progress(queue_name=queue_mode)
            queue = cur_prog['queue_indices']
        elif cmd == 's':
            q_pos += 1
        elif cmd == 'q':
            print("\nExiting review tool. All human verifications preserved.")
            break
        elif cmd in ['e', '3']:
            print("\n--- MANUAL OVERRIDES ---")
            print("Intents:", ", ".join(VALID_INTENTS))
            new_intent = input(f"New intent [{ex['ai_proposed_intent']}]: ").strip() or ex['ai_proposed_intent']

            print("Actions:", ", ".join(VALID_ACTIONS))
            new_action = input(f"New action [{ex['ai_proposed_action']}]: ").strip() or ex['ai_proposed_action']

            if new_action == 'ESCALATE_TO_HUMAN_DM':
                print("Escalations:", ", ".join(ESCALATION_REASONS))
                new_esc = input(f"New escalation [{ex['ai_proposed_escalation']}]: ").strip() or ex['ai_proposed_escalation']
            else:
                new_esc = 'N/A'

            new_notes = input(f"New notes [{ex['ai_notes']}]: ").strip() or ex['ai_notes']

            data_mgr.save_verification(idx, new_intent, new_action, new_esc, new_notes, adopt_source='manual')
            print(f"[+] Human verified {ex['example_id']} with custom overrides.")
            cur_prog = data_mgr.get_progress(queue_name=queue_mode)
            queue = cur_prog['queue_indices']


def main():
    parser = argparse.ArgumentParser(description="SpotifyCares Golden Set AI-Assisted Human Review Tool")
    parser.add_argument('--port', type=int, default=8000, help="Port to host web review interface (default: 8000)")
    parser.add_argument('--cli', action='store_true', help="Run in interactive CLI terminal mode")
    parser.add_argument('--queue', type=str, default='priority', choices=['priority', 'agreements', 'disagreements', 'seq'],
                        help="Review queue: priority (agreements first), agreements, disagreements, or seq")
    args = parser.parse_args()

    data_mgr = ReviewDataManager()

    if args.cli:
        run_cli_review(data_mgr, queue_mode=args.queue)
    else:
        port = args.port
        handler_factory = lambda *a, **k: ReviewRequestHandler(data_mgr, *a, **k)
        server = HTTPServer(('127.0.0.1', port), handler_factory)

        prog = data_mgr.get_progress(queue_name=args.queue)
        print("=" * 80)
        print("SPOTIFYCARES GOLDEN SET AI-ASSISTED REVIEW SERVER STARTED")
        print("=" * 80)
        print(f"[*] Local Review URL:       http://localhost:{port}")
        print(f"[*] Human Verified:         {prog['verified']} / {TARGET_VERIFIED_COUNT} Target ({prog['target_remaining']} remaining)")
        print(f"[*] AI Proposals Loaded:    {prog['ai_proposals_completed']} / 175")
        print(f"[*] Candidate Disagreements: {prog['ai_disagreements']}")
        print(f"[*] Needs Attention Count:  {prog['needs_attention_count']}")
        print(f"[*] Default Active Queue:   {args.queue} ({prog['active_queue_count']} pending items)")
        print(f"[*] Candidate backup:       {GOLDEN_CANDIDATE_PATH} (read-only, untouched)")
        print(f"[*] Verified records:       {GOLDEN_VERIFIED_PATH} (25 human records preserved)")
        print("[*] Press Ctrl+C in terminal to stop server at any time.")
        print("=" * 80)

        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down review server. Progress is preserved in evaluation/golden_set_verified.csv.")
            server.server_close()


if __name__ == "__main__":
    main()
