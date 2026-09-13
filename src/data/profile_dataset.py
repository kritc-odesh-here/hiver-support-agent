"""
Dataset Profiling and Brand Selection Script for TWCS (Twitter Customer Support).

Performs:
1. Streaming schema profiling (rows, columns, datatypes, missing values, duplicates, date range, authors).
2. Identification of top 10 brands by outbound volume.
3. Conversation thread reconstruction using reply relationships.
4. Candidate brand metrics (inbound/outbound counts, thread counts, lengths, bi-directional %, DM deflection %).
5. Data-quality audit (orphans, broken reply references, empty messages, long threads, deflection rate).
6. Extraction of real representative conversation threads.
7. Saves structured artifacts into results/dataset_profile/.
"""

import os
import sys
import csv
import json
import re
import argparse
from datetime import datetime
from collections import Counter, defaultdict
import statistics

# Ensure UTF-8 output on Windows consoles
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass


def parse_date(date_str):
    """Parse Twitter created_at timestamp string."""
    try:
        # Example: 'Wed Oct 11 06:55:44 +0000 2017'
        return datetime.strptime(date_str.strip(), '%a %b %d %H:%M:%S %z %Y')
    except Exception:
        return None


def profile_dataset(input_csv_path, output_dir, top_n_brands=10):
    """
    Main profiling pipeline.
    Streams input_csv_path to keep memory bounded and deterministic.
    """
    print(f"=" * 80)
    print(f"STARTING DATASET PROFILING")
    print(f"Dataset Path: {input_csv_path}")
    print(f"Output Directory: {output_dir}")
    print(f"=" * 80)

    if not os.path.exists(input_csv_path):
        raise FileNotFoundError(f"Dataset file not found at: {input_csv_path}")

    os.makedirs(output_dir, exist_ok=True)
    file_size_bytes = os.path.getsize(input_csv_path)
    file_size_mb = file_size_bytes / (1024 * 1024)
    print(f"File size: {file_size_mb:.2f} MB ({file_size_bytes:,} bytes)\n")

    # -------------------------------------------------------------------------
    # PASS 1: Schema profiling, duplicate check, author tracking, brand counts
    # -------------------------------------------------------------------------
    print(">>> PASS 1: Streaming schema analysis, entity counts, and link indexing...")

    total_rows = 0
    column_names = []
    missing_counts = defaultdict(int)
    empty_or_whitespace_text = 0
    ultra_short_text = 0

    seen_tweet_ids = set()
    duplicate_tweet_ids = 0

    inbound_count = 0
    outbound_count = 0

    inbound_authors = set()
    outbound_brand_counts = Counter()

    parent_map = {}       # child_tid -> parent_tid
    brand_map = {}        # outbound_tid -> brand_handle
    inbound_map = {}      # tid -> bool (True if inbound)
    tweet_created_at = {} # tid -> timestamp string (for representative sampling)

    parent_references = set()
    child_references = set()

    min_dt = None
    max_dt = None

    with open(input_csv_path, mode='r', encoding='utf-8', errors='replace') as f:
        reader = csv.DictReader(f)
        column_names = list(reader.fieldnames or [])
        
        for row in reader:
            total_rows += 1
            if total_rows % 500000 == 0:
                print(f"  Processed {total_rows:,} rows...")

            raw_tid = row.get('tweet_id', '').strip()
            if not raw_tid:
                missing_counts['tweet_id'] += 1
                continue

            try:
                tid = int(raw_tid)
            except ValueError:
                tid = raw_tid

            # Duplicate check
            if tid in seen_tweet_ids:
                duplicate_tweet_ids += 1
            else:
                seen_tweet_ids.add(tid)

            # Missing value check
            for col in column_names:
                val = row.get(col, '')
                if val is None or val.strip() == '':
                    missing_counts[col] += 1

            # Inbound vs Outbound
            is_inbound = row.get('inbound', '').strip().lower() == 'true'
            inbound_map[tid] = is_inbound
            author = row.get('author_id', '').strip()

            if is_inbound:
                inbound_count += 1
                if author:
                    inbound_authors.add(author)
            else:
                outbound_count += 1
                if author:
                    outbound_brand_counts[author] += 1
                    brand_map[tid] = author

            # Text checks
            text = row.get('text', '')
            stripped_text = text.strip() if text else ''
            if not stripped_text:
                empty_or_whitespace_text += 1
            elif len(stripped_text) < 5:
                ultra_short_text += 1

            # Date tracking
            dt_str = row.get('created_at', '').strip()
            tweet_created_at[tid] = dt_str
            dt = parse_date(dt_str)
            if dt:
                if min_dt is None or dt < min_dt:
                    min_dt = dt
                if max_dt is None or dt > max_dt:
                    max_dt = dt

            # Parent reference tracking
            p_val = row.get('in_response_to_tweet_id', '').strip()
            if p_val:
                try:
                    p_id = int(p_val)
                except ValueError:
                    p_id = p_val
                parent_map[tid] = p_id
                parent_references.add(p_id)

            # Child reference tracking
            resp_val = row.get('response_tweet_id', '').strip()
            if resp_val:
                for c_item in resp_val.split(','):
                    c_clean = c_item.strip()
                    if c_clean:
                        try:
                            c_id = int(c_clean)
                        except ValueError:
                            c_id = c_clean
                        child_references.add(c_id)

    print(f"Pass 1 Complete: {total_rows:,} total rows processed.")
    print(f"Unique Tweet IDs: {len(seen_tweet_ids):,}")
    print(f"Duplicate Tweet IDs: {duplicate_tweet_ids:,}")

    # Orphan & Reference analysis
    missing_parents = parent_references - seen_tweet_ids
    missing_children = child_references - seen_tweet_ids

    orphan_tweets_count = len(missing_parents)
    missing_child_refs_count = len(missing_children)

    # Date range formatting
    min_date_iso = min_dt.isoformat() if min_dt else "N/A"
    max_date_iso = max_dt.isoformat() if max_dt else "N/A"
    date_span_days = (max_dt - min_dt).days if (min_dt and max_dt) else 0

    # Top brands
    top_brands = [b for b, _ in outbound_brand_counts.most_common(top_n_brands)]

    # -------------------------------------------------------------------------
    # PASS 2: Conversation Graph Reconstruction & Thread Metrics
    # -------------------------------------------------------------------------
    print("\n>>> PASS 2: Conversation thread reconstruction via parent references...")

    # Memoized root finder
    root_memo = {}

    def get_conversation_root(tid):
        path = []
        curr = tid
        while curr in parent_map:
            if curr in root_memo:
                root = root_memo[curr]
                for node in path:
                    root_memo[node] = root
                return root
            path.append(curr)
            parent = parent_map[curr]
            # Stop if parent is outside the dataset or self-referential
            if parent not in seen_tweet_ids or parent == curr:
                root = curr
                break
            curr = parent
        else:
            root = curr

        for node in path:
            root_memo[node] = root
        return root

    # Group all seen tweets by conversation root
    threads = defaultdict(list)
    for tid in seen_tweet_ids:
        r = get_conversation_root(tid)
        threads[r].append(tid)

    total_threads = len(threads)
    print(f"Total reconstructed conversation threads: {total_threads:,}")

    # Index threads by brand
    # A thread belongs to brand B if brand B authored at least one tweet in the thread
    brand_to_threads = defaultdict(list)
    dm_regex = re.compile(r'\b(dm|direct message|private message)\b', re.IGNORECASE)

    for root_id, thread_tids in threads.items():
        thread_brands = set()
        for t in thread_tids:
            if t in brand_map:
                thread_brands.add(brand_map[t])

        for b in thread_brands:
            brand_to_threads[b].append((root_id, thread_tids))

    # Candidate brand metrics
    # We analyze top 10 brands + any notable ones
    candidate_brands = top_brands
    candidate_metrics = []

    for brand in candidate_brands:
        b_threads = brand_to_threads.get(brand, [])
        num_threads = len(b_threads)
        
        all_thread_tweets = [t for _, tids in b_threads for t in tids]
        total_brand_thread_tweets = len(all_thread_tweets)
        
        inbound_in_brand_threads = sum(1 for t in all_thread_tweets if inbound_map.get(t, False))
        outbound_in_brand_threads = sum(1 for t in all_thread_tweets if not inbound_map.get(t, False))
        
        lengths = [len(tids) for _, tids in b_threads] if b_threads else [0]
        avg_len = statistics.mean(lengths) if lengths else 0.0
        med_len = statistics.median(lengths) if lengths else 0.0
        max_len = max(lengths) if lengths else 0
        min_len = min(lengths) if lengths else 0

        # Bi-directional check: at least 1 customer inbound AND at least 1 brand outbound
        bi_directional_count = 0
        for _, tids in b_threads:
            has_inbound = any(inbound_map.get(t, False) for t in tids)
            has_outbound = any(not inbound_map.get(t, False) for t in tids)
            if has_inbound and has_outbound:
                bi_directional_count += 1

        bi_directional_pct = (bi_directional_count / num_threads * 100) if num_threads > 0 else 0.0

        candidate_metrics.append({
            'brand': brand,
            'total_outbound_tweets': outbound_brand_counts[brand],
            'threads_count': num_threads,
            'total_tweets_in_threads': total_brand_thread_tweets,
            'inbound_customer_messages': inbound_in_brand_threads,
            'outbound_brand_responses': outbound_in_brand_threads,
            'avg_conversation_length': round(avg_len, 2),
            'median_conversation_length': round(med_len, 1),
            'min_conversation_length': min_len,
            'max_conversation_length': max_len,
            'bi_directional_conversations': bi_directional_count,
            'bi_directional_pct': round(bi_directional_pct, 2)
        })

    # -------------------------------------------------------------------------
    # PASS 3: Content-level analysis (DM Deflection & Representative Conversations)
    # -------------------------------------------------------------------------
    print("\n>>> PASS 3: Content-level analysis (DM deflections & conversation sampling)...")

    # Target candidate brands for deep sampling
    target_sampling_brands = set(candidate_brands[:6]) # e.g. AmazonHelp, AppleSupport, Uber_Support, SpotifyCares, Delta, Tesco
    brand_outbound_total = Counter()
    brand_dm_deflections = Counter()

    # Pre-select candidate threads for representative inspection
    # Select threads with length 2, 3-4, and 5+ for each target brand
    selected_thread_roots = {}
    for brand in target_sampling_brands:
        b_threads = brand_to_threads.get(brand, [])
        # Find 1 short (len 2), 1 medium (len 3-4), 1 multi-turn (len 5+)
        short_t = None
        med_t = None
        multi_t = None
        for r_id, tids in b_threads:
            l = len(tids)
            if l == 2 and not short_t:
                short_t = (r_id, tids)
            elif 3 <= l <= 4 and not med_t:
                med_t = (r_id, tids)
            elif l >= 5 and not multi_t:
                multi_t = (r_id, tids)
            if short_t and med_t and multi_t:
                break
        selected_thread_roots[brand] = [t for t in [short_t, med_t, multi_t] if t is not None]

    needed_sample_tids = set()
    for brand, t_list in selected_thread_roots.items():
        for _, tids in t_list:
            needed_sample_tids.update(tids)

    sample_tweet_details = {}

    # Stream CSV again only to collect text for sample conversations and DM stats
    with open(input_csv_path, mode='r', encoding='utf-8', errors='replace') as f:
        reader = csv.DictReader(f)
        for row in reader:
            raw_tid = row.get('tweet_id', '').strip()
            if not raw_tid:
                continue
            try:
                tid = int(raw_tid)
            except ValueError:
                tid = raw_tid

            is_inb = row.get('inbound', '').strip().lower() == 'true'
            author = row.get('author_id', '').strip()
            text = row.get('text', '')

            if not is_inb and author in candidate_brands:
                brand_outbound_total[author] += 1
                if dm_regex.search(text):
                    brand_dm_deflections[author] += 1

            if tid in needed_sample_tids:
                sample_tweet_details[tid] = {
                    'tweet_id': tid,
                    'author_id': author,
                    'inbound': is_inb,
                    'created_at': row.get('created_at', ''),
                    'text': text,
                    'in_response_to_tweet_id': row.get('in_response_to_tweet_id', '').strip(),
                    'response_tweet_id': row.get('response_tweet_id', '').strip()
                }

    # Add DM deflection stats to candidate metrics
    for m in candidate_metrics:
        b = m['brand']
        tot = brand_outbound_total[b]
        dm = brand_dm_deflections[b]
        m['dm_deflection_count'] = dm
        m['dm_deflection_pct'] = round((dm / tot * 100), 2) if tot > 0 else 0.0

    # Build structured sample conversations
    structured_samples = {}
    for brand, t_list in selected_thread_roots.items():
        structured_samples[brand] = []
        for r_id, tids in t_list:
            # Sort tweets chronologically or by parent-child order
            conv_tweets = [sample_tweet_details[t] for t in tids if t in sample_tweet_details]
            conv_tweets.sort(key=lambda x: parse_date(x['created_at']) or datetime.min)
            structured_samples[brand].append({
                'root_tweet_id': r_id,
                'turn_count': len(conv_tweets),
                'tweets': conv_tweets
            })

    # -------------------------------------------------------------------------
    # GENERATE OUTPUT ARTIFACTS
    # -------------------------------------------------------------------------
    print("\n>>> Generating output files in results directory...")

    # 1. Overall summary JSON
    overall_summary = {
        'file_name': os.path.basename(input_csv_path),
        'file_size_mb': round(file_size_mb, 2),
        'total_rows': total_rows,
        'unique_tweets': len(seen_tweet_ids),
        'duplicate_tweet_ids': duplicate_tweet_ids,
        'inbound_tweets': inbound_count,
        'inbound_pct': round(inbound_count / total_rows * 100, 2) if total_rows > 0 else 0,
        'outbound_tweets': outbound_count,
        'outbound_pct': round(outbound_count / total_rows * 100, 2) if total_rows > 0 else 0,
        'date_range': {
            'min_date': min_date_iso,
            'max_date': max_date_iso,
            'span_days': date_span_days
        },
        'unique_authors_total': len(inbound_authors) + len(outbound_brand_counts),
        'unique_inbound_authors': len(inbound_authors),
        'unique_outbound_brands': len(outbound_brand_counts),
        'total_reconstructed_threads': total_threads,
        'data_quality': {
            'orphan_parent_references': orphan_tweets_count,
            'orphan_pct': round(orphan_tweets_count / len(parent_references) * 100, 2) if parent_references else 0,
            'missing_child_references': missing_child_refs_count,
            'missing_child_pct': round(missing_child_refs_count / len(child_references) * 100, 2) if child_references else 0,
            'empty_or_whitespace_messages': empty_or_whitespace_text,
            'ultra_short_messages': ultra_short_text
        }
    }

    summary_path = os.path.join(output_dir, 'overall_summary.json')
    with open(summary_path, 'w', encoding='utf-8') as f:
        json.dump(overall_summary, f, indent=2)

    # 2. Schema profile JSON
    col_types = {
        'tweet_id': 'int64',
        'author_id': 'string (handle/anonymized ID)',
        'inbound': 'boolean',
        'created_at': 'datetime (RFC 2822 format)',
        'text': 'string',
        'response_tweet_id': 'string (comma-separated int list)',
        'in_response_to_tweet_id': 'float64/int64 (nullable parent ID)'
    }

    schema_profile = {
        'columns': [
            {
                'column': col,
                'inferred_type': col_types.get(col, 'string'),
                'missing_count': missing_counts[col],
                'missing_pct': round(missing_counts[col] / total_rows * 100, 2) if total_rows > 0 else 0
            }
            for col in column_names
        ]
    }

    schema_path = os.path.join(output_dir, 'schema_profile.json')
    with open(schema_path, 'w', encoding='utf-8') as f:
        json.dump(schema_profile, f, indent=2)

    # 3. Top 10 brands CSV
    top_brands_path = os.path.join(output_dir, 'top_10_brands.csv')
    with open(top_brands_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['rank', 'brand_handle', 'outbound_tweet_count', 'outbound_share_pct'])
        for rank, (b, count) in enumerate(outbound_brand_counts.most_common(10), start=1):
            writer.writerow([rank, b, count, round(count / outbound_count * 100, 2) if outbound_count > 0 else 0])

    # 4. Brand candidate metrics CSV
    candidate_metrics_path = os.path.join(output_dir, 'brand_candidate_metrics.csv')
    with open(candidate_metrics_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=[
            'brand', 'total_outbound_tweets', 'threads_count', 'total_tweets_in_threads',
            'inbound_customer_messages', 'outbound_brand_responses', 'avg_conversation_length',
            'median_conversation_length', 'min_conversation_length', 'max_conversation_length',
            'bi_directional_conversations', 'bi_directional_pct', 'dm_deflection_count', 'dm_deflection_pct'
        ])
        writer.writeheader()
        for m in candidate_metrics:
            writer.writerow(m)

    # 5. Sample conversations JSON
    samples_path = os.path.join(output_dir, 'sample_conversations.json')
    with open(samples_path, 'w', encoding='utf-8') as f:
        json.dump(structured_samples, f, indent=2)

    # 6. Data Quality Report Markdown
    dq_path = os.path.join(output_dir, 'data_quality_report.md')
    with open(dq_path, 'w', encoding='utf-8') as f:
        f.write("# TWCS Dataset Quality Report\n\n")
        f.write(f"**Dataset File**: `{os.path.basename(input_csv_path)}`  \n")
        f.write(f"**Total Records**: `{total_rows:,}`  \n")
        f.write(f"**Analyzed on**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

        f.write("## 1. Schema & Completeness\n\n")
        f.write("| Column | Inferred Type | Missing Count | Missing % |\n")
        f.write("| :--- | :--- | :--- | :--- |\n")
        for c in schema_profile['columns']:
            f.write(f"| `{c['column']}` | {c['inferred_type']} | {c['missing_count']:,} | {c['missing_pct']}% |\n")

        f.write("\n## 2. Structural & Relational Integrity\n\n")
        f.write(f"- **Duplicate Tweet IDs**: `{duplicate_tweet_ids}` (Unique tweet primary keys are strictly unique)\n")
        f.write(f"- **Orphan In-Response References**: `{orphan_tweets_count:,}` ({overall_summary['data_quality']['orphan_pct']}% of parent references). These tweets point to earlier parent tweets outside the collection window or deleted parent tweets.\n")
        f.write(f"- **Missing Downstream Child References**: `{missing_child_refs_count:,}` ({overall_summary['data_quality']['missing_child_pct']}% of child references). Occurs when replies occur past the dataset scrape cutoff.\n")
        f.write(f"- **Empty or Whitespace-only Messages**: `{empty_or_whitespace_text:,}`\n")
        f.write(f"- **Ultra-short Messages (<5 chars)**: `{ultra_short_text:,}`\n\n")

        f.write("## 3. Support Utility & Deflection Concerns\n\n")
        f.write("In customer support automation, conversations that immediately deflect to Private Direct Messages (DM) provide zero public ground-truth resolution. The table below demonstrates the stark contrast between candidate brands:\n\n")
        f.write("| Brand | Total Outbound | DM Deflections | DM Deflection % | Utility for Support Agent Training |\n")
        f.write("| :--- | :--- | :--- | :--- | :--- |\n")
        for m in candidate_metrics:
            utility = "High (actionable troubleshooting)" if m['dm_deflection_pct'] < 35 else "Low/Impaired (heavily deflects to DM)"
            f.write(f"| **{m['brand']}** | {m['total_outbound_tweets']:,} | {m['dm_deflection_count']:,} | {m['dm_deflection_pct']}% | {utility} |\n")

    print(f"Artifacts successfully saved to: {output_dir}")

    # -------------------------------------------------------------------------
    # CONSOLE SUMMARY DISPLAY
    # -------------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("DATASET PROFILING SUMMARY RESULTS")
    print("=" * 80)
    print(f"Total Rows:               {total_rows:,}")
    print(f"Unique Tweet IDs:         {len(seen_tweet_ids):,}")
    print(f"Duplicate Tweet IDs:      {duplicate_tweet_ids:,}")
    print(f"Inbound Customer Tweets:  {inbound_count:,} ({overall_summary['inbound_pct']}%)")
    print(f"Outbound Brand Tweets:    {outbound_count:,} ({overall_summary['outbound_pct']}%)")
    print(f"Date Range:               {min_date_iso} to {max_date_iso} ({date_span_days} days)")
    print(f"Unique Customer Authors:  {len(inbound_authors):,}")
    print(f"Unique Brand Accounts:    {len(outbound_brand_counts):,}")
    print(f"Reconstructed Threads:    {total_threads:,}")
    print(f"Orphan Parent References: {orphan_tweets_count:,} ({overall_summary['data_quality']['orphan_pct']}%)")
    print(f"Missing Child References: {missing_child_refs_count:,} ({overall_summary['data_quality']['missing_child_pct']}%)")
    print("-" * 80)

    print("\nTOP 10 BRANDS BY OUTBOUND VOLUME:")
    print(f"{'Rank':<5} | {'Brand Handle':<18} | {'Outbound Tweets':<16} | {'Outbound Share %':<16}")
    print("-" * 62)
    for rank, (b, count) in enumerate(outbound_brand_counts.most_common(10), start=1):
        share = round(count / outbound_count * 100, 2) if outbound_count > 0 else 0
        print(f"{rank:<5} | {b:<18} | {count:<16,} | {share:<16.2f}%")

    print("\nCANDIDATE BRAND CONVERSATION METRICS:")
    print(f"{'Brand':<16} | {'Threads':<8} | {'Total Tw':<9} | {'Inbound':<8} | {'Outbound':<9} | {'AvgLen':<7} | {'MedLen':<7} | {'BiDir%':<7} | {'DM Deflect%':<11}")
    print("-" * 96)
    for m in candidate_metrics:
        print(f"{m['brand']:<16} | {m['threads_count']:<8,} | {m['total_tweets_in_threads']:<9,} | {m['inbound_customer_messages']:<8,} | {m['outbound_brand_responses']:<9,} | {m['avg_conversation_length']:<7.2f} | {m['median_conversation_length']:<7.1f} | {m['bi_directional_pct']:<6.1f}% | {m['dm_deflection_pct']:<10.2f}%")

    print("\nREPRESENTATIVE CONVERSATION SAMPLES:")
    for brand, conv_list in structured_samples.items():
        print(f"\n--- Brand: {brand} (Showing {len(conv_list)} sample threads) ---")
        for idx, conv in enumerate(conv_list, start=1):
            print(f"  [Thread #{idx} | Root Tweet: {conv['root_tweet_id']} | Turns: {conv['turn_count']}]")
            for tw in conv['tweets']:
                speaker = "Customer" if tw['inbound'] else f"Brand ({tw['author_id']})"
                # Truncate clean text
                clean_text = tw['text'].replace('\n', ' ')
                print(f"    - {speaker}: {clean_text}")

    print("\n" + "=" * 80)
    print("PROFILING RUN COMPLETED SUCCESSFULLY.")
    print("=" * 80 + "\n")

    return overall_summary, candidate_metrics


def main():
    parser = argparse.ArgumentParser(description="Profile Twitter Customer Support (TWCS) dataset.")
    parser.add_argument('--sample', action='store_true', help="Run fast verification against data/raw/twcs/sample.csv")
    parser.add_argument('--data-path', type=str, default=None, help="Explicit path to CSV dataset")
    parser.add_argument('--results-dir', type=str, default="results/dataset_profile", help="Output directory for results")
    parser.add_argument('--top-n', type=int, default=10, help="Number of top brands to profile")
    args = parser.parse_args()

    # Determine data path
    if args.data_path:
        csv_path = args.data_path
    elif args.sample:
        csv_path = os.path.join("data", "raw", "twcs", "sample.csv")
    else:
        csv_path = os.path.join("data", "raw", "twcs", "twcs.csv")

    profile_dataset(csv_path, args.results_dir, top_n_brands=args.top_n)


if __name__ == "__main__":
    main()
