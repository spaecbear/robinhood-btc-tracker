#!/usr/bin/env python3
"""
Backtest analysis tool: compute checkpoint prediction accuracy for different offsets
against logged raw tick data.
"""

import csv
import json
import datetime
import argparse
import os
from collections import defaultdict

INTERVALS_CSV = os.path.join('data', 'intervals.csv')
RAW_TICKS_CSV = os.path.join('data', 'raw_ticks.csv')


def load_raw_ticks():
    """Load all raw tick data."""
    ticks = []
    try:
        with open(RAW_TICKS_CSV, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    timestamp = datetime.datetime.fromisoformat(row['timestamp'].replace('Z', '+00:00'))
                    price = float(row['price'])
                    ticks.append((timestamp, price))
                except:
                    pass
    except FileNotFoundError:
        print("[ERROR] raw_ticks.csv not found")
        return []

    return sorted(ticks, key=lambda x: x[0])


def load_intervals():
    """Load all completed intervals."""
    intervals = []
    try:
        with open(INTERVALS_CSV, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    intervals.append(row)
                except:
                    pass
    except FileNotFoundError:
        print("[ERROR] intervals.csv not found")
        return []

    return intervals


def interpolate_price(ticks, target_time):
    """Interpolate price at a specific time from tick data."""
    if not ticks:
        return None

    before = None
    after = None

    for t, p in ticks:
        if t <= target_time:
            before = (t, p)
        if t >= target_time and after is None:
            after = (t, p)

    if before and after:
        if before[0] == after[0]:
            return before[1]
        t_before, p_before = before
        t_after, p_after = after
        fraction = (target_time - t_before) / (t_after - t_before)
        return p_before + (p_after - p_before) * fraction
    elif before:
        return before[1]
    elif after:
        return after[1]

    return None


def analyze_checkpoint_offset(ticks, checkpoint_minutes):
    """
    Analyze accuracy of checkpoint direction vs close direction
    for a specific checkpoint offset, using raw ticks.

    Returns: (accuracy_pct, total_intervals, correct_count, details_list)
    """
    if not ticks:
        return 0, 0, 0, []

    # Group ticks by 15-minute intervals
    intervals_dict = defaultdict(list)
    for timestamp, price in ticks:
        interval_start = timestamp.replace(minute=(timestamp.minute // 15) * 15, second=0, microsecond=0)
        intervals_dict[interval_start].append((timestamp, price))

    correct_count = 0
    total_intervals = 0
    details = []

    for interval_start in sorted(intervals_dict.keys()):
        interval_ticks = sorted(intervals_dict[interval_start])
        interval_end = interval_start + datetime.timedelta(minutes=15)
        checkpoint_time = interval_end - datetime.timedelta(minutes=checkpoint_minutes)

        # Need ticks from before interval_end to compute close price
        next_interval_start = interval_end
        ticks_for_next = intervals_dict.get(next_interval_start, [])

        # Get prices at key times
        open_price = interpolate_price(interval_ticks, interval_start)
        checkpoint_price = interpolate_price(interval_ticks, checkpoint_time)

        # Close price is at next interval start, or from the next interval's ticks
        close_price = None
        if ticks_for_next:
            close_price = interpolate_price(ticks_for_next, interval_end)

        if open_price is None or checkpoint_price is None or close_price is None:
            continue

        # Compute directions
        close_direction = "above" if close_price > open_price else "below"
        checkpoint_direction = "above" if checkpoint_price > open_price else "below"
        matched = close_direction == checkpoint_direction

        if matched:
            correct_count += 1

        total_intervals += 1
        details.append({
            'interval_start': interval_start.isoformat() + 'Z',
            'open': round(open_price, 2),
            'close': round(close_price, 2),
            'checkpoint': round(checkpoint_price, 2),
            'close_direction': close_direction,
            'checkpoint_direction': checkpoint_direction,
            'matched': matched
        })

    accuracy = (correct_count / total_intervals * 100) if total_intervals > 0 else 0
    return accuracy, total_intervals, correct_count, details


def analyze_multiple_offsets(ticks, offsets):
    """Test multiple checkpoint offsets."""
    results = {}
    for offset in offsets:
        accuracy, total, correct, _ = analyze_checkpoint_offset(ticks, offset)
        results[offset] = {
            'accuracy': round(accuracy, 2),
            'total_intervals': total,
            'correct': correct
        }
    return results


def analyze_by_date(ticks, checkpoint_minutes):
    """Analyze accuracy grouped by date."""
    daily_stats = defaultdict(lambda: {'correct': 0, 'total': 0})

    if not ticks:
        return daily_stats

    intervals_dict = defaultdict(list)
    for timestamp, price in ticks:
        interval_start = timestamp.replace(minute=(timestamp.minute // 15) * 15, second=0, microsecond=0)
        intervals_dict[interval_start].append((timestamp, price))

    for interval_start in sorted(intervals_dict.keys()):
        interval_ticks = sorted(intervals_dict[interval_start])
        interval_end = interval_start + datetime.timedelta(minutes=15)
        checkpoint_time = interval_end - datetime.timedelta(minutes=checkpoint_minutes)

        next_interval_start = interval_end
        ticks_for_next = intervals_dict.get(next_interval_start, [])

        open_price = interpolate_price(interval_ticks, interval_start)
        checkpoint_price = interpolate_price(interval_ticks, checkpoint_time)
        close_price = None
        if ticks_for_next:
            close_price = interpolate_price(ticks_for_next, interval_end)

        if open_price is None or checkpoint_price is None or close_price is None:
            continue

        close_direction = "above" if close_price > open_price else "below"
        checkpoint_direction = "above" if checkpoint_price > open_price else "below"
        matched = close_direction == checkpoint_direction

        date_key = interval_start.date().isoformat()
        daily_stats[date_key]['total'] += 1
        if matched:
            daily_stats[date_key]['correct'] += 1

    return daily_stats


def print_accuracy_table(results):
    """Pretty-print accuracy results for multiple offsets."""
    print("\n" + "=" * 60)
    print("CHECKPOINT OFFSET ACCURACY ANALYSIS")
    print("=" * 60)
    print(f"{'Offset (min)':<15} {'Accuracy':<15} {'Correct/Total':<20}")
    print("-" * 60)

    for offset in sorted(results.keys()):
        r = results[offset]
        accuracy = r['accuracy']
        correct = r['correct']
        total = r['total_intervals']
        print(f"{offset:<15} {accuracy:>6.2f}% {' ' * 8} {correct}/{total}")

    print("=" * 60)


def print_daily_stats(daily_stats, checkpoint_minutes):
    """Pretty-print daily accuracy stats."""
    print("\n" + "=" * 70)
    print(f"DAILY ACCURACY (Checkpoint: {checkpoint_minutes} min before close)")
    print("=" * 70)
    print(f"{'Date':<15} {'Accuracy':<15} {'Correct/Total':<20}")
    print("-" * 70)

    for date_key in sorted(daily_stats.keys()):
        stats = daily_stats[date_key]
        accuracy = (stats['correct'] / stats['total'] * 100) if stats['total'] > 0 else 0
        print(f"{date_key:<15} {accuracy:>6.2f}% {' ' * 8} {stats['correct']}/{stats['total']}")

    print("=" * 70)


def main():
    parser = argparse.ArgumentParser(description='Analyze checkpoint prediction accuracy')
    parser.add_argument('--offsets', type=str, default='1,3,5,7,10',
                        help='Comma-separated checkpoint offsets to test (default: 1,3,5,7,10)')
    parser.add_argument('--checkpoint-minutes', type=int, default=5,
                        help='Specific checkpoint offset to analyze (default: 5)')
    parser.add_argument('--by-date', action='store_true',
                        help='Show daily breakdown for the specified checkpoint offset')
    parser.add_argument('--json', action='store_true',
                        help='Output results as JSON')

    args = parser.parse_args()

    print("[ANALYSIS] Loading tick data...")
    ticks = load_raw_ticks()
    print(f"[ANALYSIS] Loaded {len(ticks)} price ticks")

    if not ticks:
        print("[ERROR] No tick data available")
        return

    if args.by_date:
        # Analyze a specific offset by date
        daily_stats = analyze_by_date(ticks, args.checkpoint_minutes)
        print_daily_stats(daily_stats, args.checkpoint_minutes)
    else:
        # Analyze multiple offsets
        offsets = [int(x.strip()) for x in args.offsets.split(',')]
        results = analyze_multiple_offsets(ticks, offsets)

        if args.json:
            print(json.dumps(results, indent=2))
        else:
            print_accuracy_table(results)

        # Also compute single offset stats
        accuracy, total, correct, _ = analyze_checkpoint_offset(ticks, args.checkpoint_minutes)
        print(f"\n[SUMMARY] At {args.checkpoint_minutes}-min offset:")
        print(f"  Accuracy: {accuracy:.2f}%")
        print(f"  Correct:  {correct}/{total}")


if __name__ == '__main__':
    main()
