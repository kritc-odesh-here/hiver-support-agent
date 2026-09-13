"""
Comprehensive Evaluation Harness for SpotifyCares AI Support Agent.

Evaluates:
1. Automated Task Metrics across the 200 Verified Golden Examples:
   - Intent classification accuracy, precision, recall, macro-F1
   - Expected-action / policy accuracy, precision, recall
   - Escalation decision accuracy & sensitivity/specificity
   - Full pipeline (all-3) accuracy
2. Benchmark Comparison against Two Baselines:
   - Baseline 1 (Trivial): Majority-class predictor (ambiguous_vague)
   - Baseline 2 (Simple): TF-IDF nearest-neighbor similarity classifier
3. LLM-as-Judge Reply Quality Evaluation (6-dimension rubric)
4. Human-vs-Judge Agreement Analysis (Pearson r, MAE, Cohen's Kappa)

Saves detailed artifacts under results/evaluation/ and prints headline summary.
"""

import os
import sys
import csv
import json
import math
import argparse
from typing import Dict, Any, List, Tuple
from collections import Counter, defaultdict

# Ensure project root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.agent import SpotifySupportAgent, TaxonomyIntent, AgentAction, EscalationReason
from evaluation.llm_judge import SpotifyJudge

# Ensure UTF-8 output on Windows consoles
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

GOLDEN_VERIFIED_PATH = os.path.join("evaluation", "golden_set_verified.csv")
HUMAN_RATINGS_PATH = os.path.join("evaluation", "human_reply_ratings.csv")
TRAIN_EXAMPLES_PATH = os.path.join("results", "intent_discovery", "intent_examples.json")
RESULTS_DIR = os.path.join("results", "evaluation")


# ==============================================================================
# 1. BASELINE IMPLEMENTATIONS
# ==============================================================================

class TrivialBaseline:
    """Predicts majority corpus class (ambiguous_vague -> CLARIFICATION_PROMPT -> N/A)."""
    def __init__(self):
        self.name = "Baseline 1: Trivial (Majority Class)"

    def predict(self, message: str, context: str = None) -> Tuple[str, str, str]:
        return (
            TaxonomyIntent.AMBIGUOUS_VAGUE,
            AgentAction.CLARIFICATION_PROMPT,
            EscalationReason.NA
        )


class SimpleTFIDFBaseline:
    """Lightweight non-LLM unigram TF-IDF nearest-neighbor similarity classifier."""
    def __init__(self, examples_path: str = TRAIN_EXAMPLES_PATH):
        self.name = "Baseline 2: Simple (TF-IDF Similarity)"
        self.docs = []
        self.doc_labels = []
        self.idf = {}
        self.doc_vecs = []
        self.default_actions = {
            TaxonomyIntent.SUBSCRIPTION_AND_BILLING: AgentAction.INFO_PROVISION,
            TaxonomyIntent.MUSIC_CATALOG_AND_CONTENT: AgentAction.INFO_PROVISION,
            TaxonomyIntent.PLAYLIST_LIBRARY_AND_CURATION: AgentAction.DIRECT_TROUBLESHOOT,
            TaxonomyIntent.ACCOUNT_ACCESS_AND_LOGIN: AgentAction.INFO_PROVISION,
            TaxonomyIntent.PLAYBACK_AND_AUDIO: AgentAction.DIRECT_TROUBLESHOOT,
            TaxonomyIntent.OFFLINE_LISTENING_AND_DOWNLOADS: AgentAction.DIRECT_TROUBLESHOOT,
            TaxonomyIntent.SERVICE_OUTAGE_AND_STATUS: AgentAction.INFO_PROVISION,
            TaxonomyIntent.APP_CRASH_AND_PERFORMANCE: AgentAction.DIRECT_TROUBLESHOOT,
            TaxonomyIntent.AMBIGUOUS_VAGUE: AgentAction.CLARIFICATION_PROMPT,
            TaxonomyIntent.MULTI_INTENT: AgentAction.DIRECT_TROUBLESHOOT,
            TaxonomyIntent.NON_SUPPORT_OR_CHATTER: AgentAction.INFO_PROVISION,
            TaxonomyIntent.UNCLASSIFIABLE_OR_FOREIGN: AgentAction.INFO_PROVISION,
        }
        self._build_index(examples_path)

    def _tokenize(self, s: str) -> List[str]:
        import re
        return re.findall(r'\b[a-z]{2,}\b', s.lower())

    def _build_index(self, examples_path: str):
        if not os.path.exists(examples_path):
            return
        with open(examples_path, 'r', encoding='utf-8') as f:
            intent_examples = json.load(f)

        df = Counter()
        doc_tokens = []
        for intent, examples in intent_examples.items():
            for ex in examples:
                text = ex.get('customer_message', '')
                self.docs.append(text.lower())
                self.doc_labels.append(intent)
                toks = self._tokenize(text)
                doc_tokens.append(toks)
                for t in set(toks):
                    df[t] += 1

        N = len(self.docs)
        self.idf = {t: math.log((N + 1) / (count + 1)) + 1.0 for t, count in df.items()}

        for toks in doc_tokens:
            self.doc_vecs.append(self._to_vec(toks))

    def _to_vec(self, tokens: List[str]) -> Dict[str, float]:
        tf = Counter(tokens)
        vec = {}
        norm = 0.0
        for t, count in tf.items():
            weight = count * self.idf.get(t, 1.0)
            vec[t] = weight
            norm += weight * weight
        norm = math.sqrt(norm)
        if norm > 0:
            for t in vec:
                vec[t] /= norm
        return vec

    def predict(self, message: str, context: str = None) -> Tuple[str, str, str]:
        q_vec = self._to_vec(self._tokenize(message))
        best_score = -1.0
        best_intent = TaxonomyIntent.AMBIGUOUS_VAGUE

        for i, d_vec in enumerate(self.doc_vecs):
            score = sum(q_vec.get(t, 0.0) * w for t, w in d_vec.items())
            if score > best_score:
                best_score = score
                best_intent = self.doc_labels[i]

        pred_action = self.default_actions.get(best_intent, AgentAction.DIRECT_TROUBLESHOOT)
        pred_esc = EscalationReason.NA
        return best_intent, pred_action, pred_esc


# ==============================================================================
# 2. STATISTICAL METRICS HELPER
# ==============================================================================

def compute_classification_metrics(y_true: List[str], y_pred: List[str]) -> Dict[str, Any]:
    labels = sorted(list(set(y_true + y_pred)))
    total = len(y_true)
    correct = sum(1 for yt, yp in zip(y_true, y_pred) if yt == yp)
    accuracy = correct / total if total > 0 else 0.0

    per_class = {}
    f1_list = []
    for label in labels:
        tp = sum(1 for yt, yp in zip(y_true, y_pred) if yt == label and yp == label)
        fp = sum(1 for yt, yp in zip(y_true, y_pred) if yt != label and yp == label)
        fn = sum(1 for yt, yp in zip(y_true, y_pred) if yt == label and yp != label)

        prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (2 * prec * rec) / (prec + rec) if (prec + rec) > 0 else 0.0

        support = sum(1 for yt in y_true if yt == label)
        per_class[label] = {
            'precision': round(prec, 4),
            'recall': round(rec, 4),
            'f1': round(f1, 4),
            'support': support
        }
        if support > 0:
            f1_list.append(f1)

    macro_f1 = sum(f1_list) / len(f1_list) if f1_list else 0.0

    return {
        'accuracy': round(accuracy, 4),
        'macro_f1': round(macro_f1, 4),
        'correct': correct,
        'total': total,
        'per_class': per_class
    }


# ==============================================================================
# 3. MAIN EVALUATION RUNNER
# ==============================================================================

def run_evaluation(offline_judge: bool = True):
    print("=" * 80)
    print("SPOTIFYCARES AI SUPPORT AGENT — COMPREHENSIVE EVALUATION HARNESS")
    print("=" * 80)

    if not os.path.exists(GOLDEN_VERIFIED_PATH):
        print(f"[-] Golden verified set not found: {GOLDEN_VERIFIED_PATH}")
        sys.exit(1)

    with open(GOLDEN_VERIFIED_PATH, mode='r', encoding='utf-8', errors='replace') as f:
        golden_set = list(csv.DictReader(f))

    N = len(golden_set)
    print(f"[*] Loaded {N} human-verified golden evaluation records from: {GOLDEN_VERIFIED_PATH}")

    os.makedirs(RESULTS_DIR, exist_ok=True)

    # 1. Initialize models & baselines
    agent = SpotifySupportAgent()
    trivial_baseline = TrivialBaseline()
    simple_baseline = SimpleTFIDFBaseline()
    judge = SpotifyJudge(offline_only=offline_judge)

    # Ground truth targets
    true_intents = [r['intent'] for r in golden_set]
    true_actions = [r['expected_action'] for r in golden_set]
    true_escalations = [r['escalation_reason'] for r in golden_set]
    true_escalates_bin = [r['expected_action'] == AgentAction.ESCALATE_TO_HUMAN_DM for r in golden_set]

    # Predictions storage
    agent_intents = []
    agent_actions = []
    agent_escalations = []
    agent_escalates_bin = []
    agent_replies = []
    judge_results = []
    failures = []

    triv_intents = []
    triv_actions = []
    triv_escalations = []

    simp_intents = []
    simp_actions = []
    simp_escalations = []

    print("[*] Executing Agent and Baselines across 200 evaluation examples...")

    for idx, r in enumerate(golden_set):
        msg = r['customer_message']
        ctx = r['conversation_context']
        if ctx == 'None (thread root)':
            ctx = None

        # Agent Run
        resp = agent.process(msg, context=ctx)
        agent_intents.append(resp.intent)
        agent_actions.append(resp.expected_action)
        agent_escalations.append(resp.escalation_reason)
        agent_escalates_bin.append(resp.requires_escalation)
        agent_replies.append(resp.generated_response)

        # Failure tracking
        if not (resp.intent == r['intent'] and resp.expected_action == r['expected_action'] and resp.escalation_reason == r['escalation_reason']):
            failures.append({
                'example_id': r['example_id'],
                'customer_message': msg,
                'conversation_context': ctx,
                'true_intent': r['intent'],
                'pred_intent': resp.intent,
                'true_action': r['expected_action'],
                'pred_action': resp.expected_action,
                'true_escalation': r['escalation_reason'],
                'pred_escalation': resp.escalation_reason,
                'generated_response': resp.generated_response
            })

        # LLM Judge Run
        j_eval = judge.evaluate_response(
            customer_message=msg,
            conversation_context=ctx,
            predicted_intent=resp.intent,
            expected_action=resp.expected_action,
            escalation_reason=resp.escalation_reason,
            generated_response=resp.generated_response,
            historical_reference=resp.historical_reference,
            ground_truth_intent=r['intent'],
            ground_truth_action=r['expected_action'],
            ground_truth_escalation=r['escalation_reason']
        )
        j_eval['example_id'] = r['example_id']
        judge_results.append(j_eval)

        # Trivial Baseline Run
        ti, ta, te = trivial_baseline.predict(msg, ctx)
        triv_intents.append(ti)
        triv_actions.append(ta)
        triv_escalations.append(te)

        # Simple Baseline Run
        si, sa, se = simple_baseline.predict(msg, ctx)
        simp_intents.append(si)
        simp_actions.append(sa)
        simp_escalations.append(se)

    # ==============================================================================
    # 4. COMPUTE AUTOMATED METRICS
    # ==============================================================================
    agent_intent_metrics = compute_classification_metrics(true_intents, agent_intents)
    agent_action_metrics = compute_classification_metrics(true_actions, agent_actions)
    agent_esc_metrics = compute_classification_metrics(true_escalations, agent_escalations)

    agent_all3_correct = sum(
        1 for ti, ta, te, pi, pa, pe in zip(true_intents, true_actions, true_escalations, agent_intents, agent_actions, agent_escalations)
        if ti == pi and ta == pa and te == pe
    )
    agent_all3_acc = agent_all3_correct / N

    # Baselines Metrics
    triv_intent_metrics = compute_classification_metrics(true_intents, triv_intents)
    triv_action_metrics = compute_classification_metrics(true_actions, triv_actions)
    triv_esc_metrics = compute_classification_metrics(true_escalations, triv_escalations)
    triv_all3_correct = sum(
        1 for ti, ta, te, pi, pa, pe in zip(true_intents, true_actions, true_escalations, triv_intents, triv_actions, triv_escalations)
        if ti == pi and ta == pa and te == pe
    )

    simp_intent_metrics = compute_classification_metrics(true_intents, simp_intents)
    simp_action_metrics = compute_classification_metrics(true_actions, simp_actions)
    simp_esc_metrics = compute_classification_metrics(true_escalations, simp_escalations)
    simp_all3_correct = sum(
        1 for ti, ta, te, pi, pa, pe in zip(true_intents, true_actions, true_escalations, simp_intents, simp_actions, simp_escalations)
        if ti == pi and ta == pa and te == pe
    )

    # Judge Aggregate Metrics
    avg_composite = sum(j['composite_score'] for j in judge_results) / N
    pct_passing = sum(1 for j in judge_results if j['passed_quality_bar']) / N * 100
    avg_relevance = sum(j['scores']['relevance'] for j in judge_results) / N
    avg_correctness = sum(j['scores']['correctness'] for j in judge_results) / N
    avg_grounding = sum(j['scores']['grounding'] for j in judge_results) / N
    avg_policy = sum(j['scores']['policy_compliance'] for j in judge_results) / N
    avg_safety = sum(j['scores']['safety'] for j in judge_results) / N
    avg_tone = sum(j['scores']['tone'] for j in judge_results) / N

    # ==============================================================================
    # 5. HUMAN-JUDGE AGREEMENT ANALYSIS
    # ==============================================================================
    human_agreement_metrics = {}
    if os.path.exists(HUMAN_RATINGS_PATH):
        with open(HUMAN_RATINGS_PATH, mode='r', encoding='utf-8') as f:
            h_rows = list(csv.DictReader(f))

        h_N = len(h_rows)
        h_scores = [float(r['human_composite_score']) for r in h_rows]
        h_passes = [r['human_passed'].lower() == 'true' for r in h_rows]

        j_scores = []
        j_passes = []
        for r in h_rows:
            resp = agent.process(r['customer_message'])
            j_eval = judge.evaluate_response(
                customer_message=r['customer_message'],
                conversation_context=None,
                predicted_intent=resp.intent,
                expected_action=resp.expected_action,
                escalation_reason=resp.escalation_reason,
                generated_response=resp.generated_response,
                historical_reference=resp.historical_reference,
                ground_truth_intent=r['intent'],
                ground_truth_action=r['expected_action'],
                ground_truth_escalation=r['escalation_reason']
            )
            j_scores.append(j_eval['composite_score'])
            j_passes.append(j_eval['passed_quality_bar'])

        exact_cnt = sum(1 for h, j in zip(h_scores, j_scores) if round(h) == round(j))
        within1_cnt = sum(1 for h, j in zip(h_scores, j_scores) if abs(h - j) <= 1.0)
        mae = sum(abs(h - j) for h, j in zip(h_scores, j_scores)) / h_N

        mean_h = sum(h_scores) / h_N
        mean_j = sum(j_scores) / h_N
        cov = sum((h - mean_h) * (j - mean_j) for h, j in zip(h_scores, j_scores))
        var_h = sum((h - mean_h) ** 2 for h in h_scores)
        var_j = sum((j - mean_j) ** 2 for j in j_scores)
        pearson_r = cov / math.sqrt(var_h * var_j) if var_h * var_j > 0 else 0.0

        p00 = sum(1 for h, j in zip(h_passes, j_passes) if not h and not j)
        p01 = sum(1 for h, j in zip(h_passes, j_passes) if not h and j)
        p10 = sum(1 for h, j in zip(h_passes, j_passes) if h and not j)
        p11 = sum(1 for h, j in zip(h_passes, j_passes) if h and j)

        po = (p00 + p11) / h_N
        pe = ((p00 + p01) * (p00 + p10) + (p10 + p11) * (p01 + p11)) / (h_N * h_N)
        cohen_kappa = (po - pe) / (1 - pe) if (1 - pe) > 0 else 1.0

        human_agreement_metrics = {
            'sample_size': h_N,
            'exact_score_agreement_pct': round(exact_cnt / h_N * 100, 2),
            'within_1_point_agreement_pct': round(within1_cnt / h_N * 100, 2),
            'mean_absolute_error': round(mae, 4),
            'pearson_correlation': round(pearson_r, 4),
            'binary_quality_agreement_pct': round(po * 100, 2),
            'cohens_kappa': round(cohen_kappa, 4)
        }

    # ==============================================================================
    # 6. SAVE ARTIFACTS
    # ==============================================================================
    baseline_table = [
        {
            'Model': trivial_baseline.name,
            'Intent_Accuracy': f"{triv_intent_metrics['accuracy']*100:.2f}%",
            'Intent_Macro_F1': f"{triv_intent_metrics['macro_f1']:.4f}",
            'Action_Accuracy': f"{triv_action_metrics['accuracy']*100:.2f}%",
            'Escalation_Accuracy': f"{triv_esc_metrics['accuracy']*100:.2f}%",
            'All_3_Pipeline_Accuracy': f"{(triv_all3_correct/N)*100:.2f}%"
        },
        {
            'Model': simple_baseline.name,
            'Intent_Accuracy': f"{simp_intent_metrics['accuracy']*100:.2f}%",
            'Intent_Macro_F1': f"{simp_intent_metrics['macro_f1']:.4f}",
            'Action_Accuracy': f"{simp_action_metrics['accuracy']*100:.2f}%",
            'Escalation_Accuracy': f"{simp_esc_metrics['accuracy']*100:.2f}%",
            'All_3_Pipeline_Accuracy': f"{(simp_all3_correct/N)*100:.2f}%"
        },
        {
            'Model': "SpotifySupportAgent (Our Pipeline)",
            'Intent_Accuracy': f"{agent_intent_metrics['accuracy']*100:.2f}%",
            'Intent_Macro_F1': f"{agent_intent_metrics['macro_f1']:.4f}",
            'Action_Accuracy': f"{agent_action_metrics['accuracy']*100:.2f}%",
            'Escalation_Accuracy': f"{agent_esc_metrics['accuracy']*100:.2f}%",
            'All_3_Pipeline_Accuracy': f"{agent_all3_acc*100:.2f}%"
        }
    ]

    csv_path = os.path.join(RESULTS_DIR, "baseline_comparison.csv")
    with open(csv_path, mode='w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(baseline_table[0].keys()))
        writer.writeheader()
        writer.writerows(baseline_table)

    eval_summary = {
        'headline_result': {
            'metric_name': 'Full Pipeline Accuracy (All-3: Intent + Action + Escalation simultaneously correct)',
            'value': f"{agent_all3_acc*100:.2f}%",
            'correct_count': agent_all3_correct,
            'total_denominator': N,
            'dataset': '200 Human-Verified Golden Evaluation Records (evaluation/golden_set_verified.csv)'
        },
        'intent_metrics': agent_intent_metrics,
        'action_metrics': agent_action_metrics,
        'escalation_metrics': agent_esc_metrics,
        'llm_judge_aggregate': {
            'mean_composite_score': round(avg_composite, 2),
            'quality_pass_rate_pct': round(pct_passing, 2),
            'mean_relevance': round(avg_relevance, 2),
            'mean_correctness': round(avg_correctness, 2),
            'mean_grounding': round(avg_grounding, 2),
            'mean_policy_compliance': round(avg_policy, 2),
            'mean_safety': round(avg_safety, 2),
            'mean_tone': round(avg_tone, 2),
        },
        'human_judge_agreement': human_agreement_metrics,
        'failure_count': len(failures),
        'top_failures': failures[:10]
    }

    with open(os.path.join(RESULTS_DIR, "eval_results.json"), 'w', encoding='utf-8') as f:
        json.dump(eval_summary, f, indent=2, ensure_ascii=False)

    with open(os.path.join(RESULTS_DIR, "judge_results.json"), 'w', encoding='utf-8') as f:
        json.dump(judge_results, f, indent=2, ensure_ascii=False)

    with open(os.path.join(RESULTS_DIR, "human_agreement.json"), 'w', encoding='utf-8') as f:
        json.dump(human_agreement_metrics, f, indent=2)

    # ==============================================================================
    # 7. PRINT TERMINAL RESULTS REPORT
    # ==============================================================================
    print("\n" + "=" * 80)
    print("SPOTIFYCARES EVALUATION RESULTS SUMMARY")
    print("=" * 80)
    print(f"HEADLINE METRIC: Full Pipeline Accuracy = {agent_all3_acc*100:.2f}% ({agent_all3_correct}/{N})")
    print(f"  - Intent Accuracy:       {agent_intent_metrics['accuracy']*100:.2f}% (Macro-F1: {agent_intent_metrics['macro_f1']:.4f})")
    print(f"  - Action Policy Accuracy:{agent_action_metrics['accuracy']*100:.2f}% (Macro-F1: {agent_action_metrics['macro_f1']:.4f})")
    print(f"  - Escalation Accuracy:   {agent_esc_metrics['accuracy']*100:.2f}% (Macro-F1: {agent_esc_metrics['macro_f1']:.4f})")
    print("-" * 80)
    print("BENCHMARK COMPARISON VERSUS BASELINES (N = 200)")
    print("-" * 80)
    print(f"{'Model':<38} | {'Intent Acc':<11} | {'Action Acc':<11} | {'Esc Acc':<10} | {'All-3 Pipeline'}")
    print("-" * 80)
    for b in baseline_table:
        print(f"{b['Model']:<38} | {b['Intent_Accuracy']:<11} | {b['Action_Accuracy']:<11} | {b['Escalation_Accuracy']:<10} | {b['All_3_Pipeline_Accuracy']}")
    print("-" * 80)
    print("LLM-AS-JUDGE QUALITY SUMMARY (N = 200)")
    print(f"  - Mean Composite Quality Score: {avg_composite:.2f} / 5.00")
    print(f"  - Production Quality Pass Rate: {pct_passing:.1f}% (composite >= 4.0)")
    print(f"  - Dimensional Breakdown: Rel={avg_relevance:.2f}, Corr={avg_correctness:.2f}, Gnd={avg_grounding:.2f}, Pol={avg_policy:.2f}, Safe={avg_safety:.2f}, Tone={avg_tone:.2f}")
    print("-" * 80)
    if human_agreement_metrics:
        print("HUMAN-VS-JUDGE AGREEMENT EVIDENCE (N = 50)")
        print(f"  - Exact Score Agreement:        {human_agreement_metrics['exact_score_agreement_pct']}%")
        print(f"  - Within-1-Point Agreement:     {human_agreement_metrics['within_1_point_agreement_pct']}%")
        print(f"  - Mean Absolute Error (MAE):    {human_agreement_metrics['mean_absolute_error']} points")
        print(f"  - Pearson Correlation (r):      {human_agreement_metrics['pearson_correlation']}")
        print(f"  - Binary Quality Agreement:     {human_agreement_metrics['binary_quality_agreement_pct']}%")
        print(f"  - Cohen's Kappa (kappa):        {human_agreement_metrics['cohens_kappa']}")
    print("=" * 80)
    print(f"[+] All artifacts saved under: {RESULTS_DIR}/\n")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Evaluate SpotifyCares Support Agent")
    parser.add_argument("--api", action="store_true", help="Use live external API for LLM Judge if key available")
    args = parser.parse_args()

    run_evaluation(offline_judge=not args.api)
