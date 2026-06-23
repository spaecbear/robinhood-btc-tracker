#!/usr/bin/env python3
"""
Bitcoin 15-minute interval tracker for pattern study.
Polls CoinGecko API every 15 seconds, logs price ticks, and computes interval metrics.
"""

import json
import csv
import time
import datetime
import urllib.request
import urllib.error
import threading
import argparse
import os
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
import sys

DATA_DIR = "data"
INTERVALS_CSV = os.path.join(DATA_DIR, "intervals.csv")
RAW_TICKS_CSV = os.path.join(DATA_DIR, "raw_ticks.csv")
LATEST_JSON = os.path.join(DATA_DIR, "latest.json")

class Tracker:
    def __init__(self, poll_seconds=15, checkpoint_minutes=5, retention_days=90,
                 bet_amount=50.0, entry_price=0.90):
        self.poll_seconds = poll_seconds
        self.checkpoint_minutes = checkpoint_minutes
        self.retention_days = retention_days
        self.bet_amount = bet_amount
        self.entry_price = entry_price

        self.running = False
        self.lock = threading.Lock()

        # Current state
        self.current_price = None
        self.current_timestamp = None
        self.price_history = []  # [(timestamp, price), ...]

        # Completed intervals tracking
        self.last_logged_interval = None

        self._ensure_data_dir()
        self._load_initial_state()
        self._cleanup_old_data()

    def _ensure_data_dir(self):
        Path(DATA_DIR).mkdir(exist_ok=True)

        # Initialize CSVs if they don't exist
        if not os.path.exists(INTERVALS_CSV):
            with open(INTERVALS_CSV, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'interval_start', 'open_price', 'close_price', 'checkpoint_price',
                    'checkpoint_minutes_before_close', 'close_direction', 'checkpoint_direction',
                    'checkpoint_matched_close', 'missed', 'bet_amount', 'entry_price'
                ])

        if not os.path.exists(RAW_TICKS_CSV):
            with open(RAW_TICKS_CSV, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['timestamp', 'price'])

    def _load_initial_state(self):
        """Load the last logged interval to avoid duplication."""
        try:
            with open(INTERVALS_CSV, 'r') as f:
                reader = csv.DictReader(f)
                rows = list(reader)
                if rows:
                    self.last_logged_interval = rows[-1]['interval_start']
        except:
            pass

    def _cleanup_old_data(self):
        """Remove data older than retention_days."""
        cutoff = datetime.datetime.utcnow() - datetime.timedelta(days=self.retention_days)
        cutoff_iso = cutoff.isoformat() + 'Z'

        # Clean raw ticks
        temp_ticks = []
        try:
            with open(RAW_TICKS_CSV, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row['timestamp'] > cutoff_iso:
                        temp_ticks.append(row)
        except:
            return

        with open(RAW_TICKS_CSV, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=['timestamp', 'price'])
            writer.writeheader()
            writer.writerows(temp_ticks)

        # Clean intervals
        temp_intervals = []
        try:
            with open(INTERVALS_CSV, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row['interval_start'] > cutoff_iso:
                        temp_intervals.append(row)
        except:
            return

        with open(INTERVALS_CSV, 'w', newline='') as f:
            fieldnames = [
                'interval_start', 'open_price', 'close_price', 'checkpoint_price',
                'checkpoint_minutes_before_close', 'close_direction', 'checkpoint_direction',
                'checkpoint_matched_close', 'missed', 'bet_amount', 'entry_price'
            ]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(temp_intervals)

    def fetch_price(self):
        """Fetch BTC/USD price from CoinGecko."""
        try:
            import ssl
            url = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd"
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})

            # Handle SSL certificate verification issues
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE

            with urllib.request.urlopen(req, timeout=5, context=ssl_context) as response:
                data = json.loads(response.read().decode())
                price = data['bitcoin']['usd']
                return price
        except urllib.error.URLError as e:
            print(f"[ERROR] API fetch failed: {e}")
            return None
        except Exception as e:
            print(f"[ERROR] Unexpected error: {e}")
            return None

    def run(self):
        """Main polling loop."""
        self.running = True
        print(f"[TRACKER] Starting with poll interval={self.poll_seconds}s, checkpoint={self.checkpoint_minutes}min")

        while self.running:
            price = self.fetch_price()
            now = datetime.datetime.utcnow()

            if price is not None:
                with self.lock:
                    self.current_price = price
                    self.current_timestamp = now
                    self.price_history.append((now, price))

                    # Keep history to recent ticks only (last 2 hours)
                    cutoff = now - datetime.timedelta(hours=2)
                    self.price_history = [(t, p) for t, p in self.price_history if t > cutoff]

                    # Log raw tick
                    self._log_raw_tick(now, price)

                    # Check if an interval has completed
                    self._check_and_log_intervals(now)

                print(f"[{now.strftime('%H:%M:%S')}] BTC: ${price:,.2f}")

            time.sleep(self.poll_seconds)

    def _log_raw_tick(self, timestamp, price):
        """Append a raw tick to the CSV."""
        with open(RAW_TICKS_CSV, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([timestamp.isoformat() + 'Z', price])

    def _get_15min_boundary(self, dt):
        """Get the current 15-minute interval start time."""
        minute = dt.minute
        interval_minute = (minute // 15) * 15
        return dt.replace(minute=interval_minute, second=0, microsecond=0)

    def _check_and_log_intervals(self, now):
        """Check if we've crossed an interval boundary and log the completed interval."""
        current_interval = self._get_15min_boundary(now)

        # Check if the previous interval is complete
        previous_interval = current_interval - datetime.timedelta(minutes=15)
        previous_interval_iso = previous_interval.isoformat() + 'Z'

        # Don't log the same interval twice
        if self.last_logged_interval and self.last_logged_interval == previous_interval_iso:
            return

        # If we have price history and enough time has passed since interval start
        if len(self.price_history) > 0:
            earliest_history_time = self.price_history[0][0]
            # If we have history before the current interval, we can compute the previous one
            if earliest_history_time < current_interval:
                self._log_interval(previous_interval)
                self.last_logged_interval = previous_interval_iso

    def _log_interval(self, interval_start):
        """Compute and log a completed interval."""
        interval_end = interval_start + datetime.timedelta(minutes=15)
        checkpoint_offset = datetime.timedelta(minutes=self.checkpoint_minutes)
        checkpoint_time = interval_end - checkpoint_offset

        # Find prices at key times
        open_price = self._interpolate_price(interval_start)
        close_price = self._interpolate_price(interval_end)
        checkpoint_price = self._interpolate_price(checkpoint_time)

        if open_price is None or close_price is None or checkpoint_price is None:
            # Not enough data
            return

        # Compute directions
        close_direction = "above" if close_price > open_price else "below"
        checkpoint_direction = "above" if checkpoint_price > open_price else "below"
        checkpoint_matched = close_direction == checkpoint_direction

        # Compute simulated profit/loss
        contracts = self.bet_amount / self.entry_price
        if checkpoint_matched:
            payout = contracts * 1.0
            profit = payout - self.bet_amount
        else:
            payout = 0
            profit = -self.bet_amount

        # Log interval
        with open(INTERVALS_CSV, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                interval_start.isoformat() + 'Z',
                round(open_price, 2),
                round(close_price, 2),
                round(checkpoint_price, 2),
                self.checkpoint_minutes,
                close_direction,
                checkpoint_direction,
                checkpoint_matched,
                'false',  # missed
                self.bet_amount,
                self.entry_price
            ])

        print(f"[INTERVAL] {interval_start.isoformat()} | O: ${open_price:.2f} C: ${close_price:.2f} ({close_direction}) | "
              f"CP: ${checkpoint_price:.2f} ({checkpoint_direction}) | Match: {checkpoint_matched} | P&L: ${profit:+.2f}")

    def _interpolate_price(self, target_time):
        """Interpolate price at a specific time using available history."""
        if not self.price_history:
            return None

        # Find two closest points
        before = None
        after = None

        for t, p in self.price_history:
            if t <= target_time:
                before = (t, p)
            if t >= target_time and after is None:
                after = (t, p)

        if before and after:
            if before[0] == after[0]:
                return before[1]
            # Linear interpolation
            t_before, p_before = before
            t_after, p_after = after
            fraction = (target_time - t_before) / (t_after - t_before)
            return p_before + (p_after - p_before) * fraction
        elif before:
            return before[1]
        elif after:
            return after[1]

        return None

    def update_latest_json(self):
        """Write current state to latest.json for the dashboard."""
        with self.lock:
            if self.current_price is None or self.current_timestamp is None:
                return

            current_interval = self._get_15min_boundary(self.current_timestamp)
            next_interval = current_interval + datetime.timedelta(minutes=15)
            seconds_until_close = (next_interval - self.current_timestamp).total_seconds()

            # Compute daily stats
            daily_profit, daily_intervals = self._get_daily_stats()

            data = {
                'current_price': round(self.current_price, 2),
                'current_timestamp': self.current_timestamp.isoformat() + 'Z',
                'current_interval_start': current_interval.isoformat() + 'Z',
                'current_interval_end': next_interval.isoformat() + 'Z',
                'current_open_price': self._interpolate_price(current_interval),
                'time_until_close_seconds': int(max(0, seconds_until_close)),
                'checkpoint_price': None,
                'intervals_completed_today': daily_intervals,
                'total_intervals_logged': self._count_total_intervals(),
                'daily_profit_loss': round(daily_profit, 2),
                'current_checkpoint_offset_minutes': self.checkpoint_minutes
            }

            with open(LATEST_JSON, 'w') as f:
                json.dump(data, f, indent=2)

    def _get_daily_stats(self):
        """Compute daily profit and interval count."""
        today = datetime.datetime.utcnow().date()
        total_profit = 0.0
        count = 0

        try:
            with open(INTERVALS_CSV, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    try:
                        interval_start = datetime.datetime.fromisoformat(row['interval_start'].replace('Z', '+00:00'))
                        if interval_start.date() == today and row['missed'].lower() != 'true':
                            # Compute profit
                            bet = float(row['bet_amount'])
                            entry = float(row['entry_price'])
                            contracts = bet / entry
                            matched = row['checkpoint_matched_close'].lower() == 'true'
                            profit = (contracts - bet) if matched else -bet
                            total_profit += profit
                            count += 1
                    except:
                        pass
        except:
            pass

        return total_profit, count

    def _count_total_intervals(self):
        """Count total intervals logged."""
        try:
            with open(INTERVALS_CSV, 'r') as f:
                reader = csv.DictReader(f)
                return sum(1 for _ in reader)
        except:
            return 0


class DashboardHandler(BaseHTTPRequestHandler):
    """HTTP handler for serving dashboard and API endpoints."""

    def do_GET(self):
        if self.path == '/':
            self.serve_dashboard()
        elif self.path == '/api/latest':
            self.serve_json_file(LATEST_JSON)
        elif self.path == '/api/intervals':
            self.serve_csv_file(INTERVALS_CSV)
        elif self.path == '/api/ticks':
            self.serve_csv_file(RAW_TICKS_CSV)
        elif self.path.startswith('/api/analyze'):
            self.analyze_offsets()
        elif self.path.startswith('/api/ml'):
            self.run_ml()
        else:
            self.send_error(404)

    def serve_dashboard(self):
        """Serve the dashboard HTML."""
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()

        with open('dashboard.html', 'r') as f:
            self.wfile.write(f.read().encode())

    def serve_json_file(self, filepath):
        """Serve a JSON file."""
        if not os.path.exists(filepath):
            self.send_error(404)
            return

        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()

        with open(filepath, 'rb') as f:
            self.wfile.write(f.read())

    def serve_csv_file(self, filepath):
        """Serve a CSV file."""
        if not os.path.exists(filepath):
            self.send_error(404)
            return

        self.send_response(200)
        self.send_header('Content-type', 'text/csv')
        self.end_headers()

        with open(filepath, 'rb') as f:
            self.wfile.write(f.read())

    def run_ml(self):
        """API endpoint: train + evaluate the ML model, return a JSON report."""
        try:
            import ml_model
            result = ml_model.run_ml_analysis()
            self.send_json(result, 200)
        except Exception as e:
            self.send_json({'status': 'error', 'error': str(e)}, 500)

    def analyze_offsets(self):
        """API endpoint for checkpoint offset analysis."""
        try:
            # Load raw ticks
            ticks = []
            with open(RAW_TICKS_CSV, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    try:
                        ts = datetime.datetime.fromisoformat(row['timestamp'].replace('Z', '+00:00'))
                        price = float(row['price'])
                        ticks.append((ts, price))
                    except:
                        pass

            if not ticks:
                self.send_json({'error': 'No tick data available'}, 400)
                return

            # Analyze multiple offsets (1-15 minutes)
            results = {}
            for offset in range(1, 16):
                accuracy, total, correct = self._analyze_offset(ticks, offset)
                results[offset] = {
                    'accuracy': round(accuracy, 2),
                    'total': total,
                    'correct': correct
                }

            self.send_json(results, 200)
        except Exception as e:
            self.send_json({'error': str(e)}, 500)

    def _analyze_offset(self, ticks, offset_minutes):
        """Compute accuracy for a specific offset."""
        from collections import defaultdict

        intervals_dict = defaultdict(list)
        for timestamp, price in ticks:
            interval_start = timestamp.replace(minute=(timestamp.minute // 15) * 15, second=0, microsecond=0)
            intervals_dict[interval_start].append((timestamp, price))

        correct = 0
        total = 0

        for interval_start in sorted(intervals_dict.keys()):
            interval_ticks = sorted(intervals_dict[interval_start])
            interval_end = interval_start + datetime.timedelta(minutes=15)
            checkpoint_time = interval_end - datetime.timedelta(minutes=offset_minutes)

            next_interval_start = interval_end
            ticks_for_next = intervals_dict.get(next_interval_start, [])

            # Interpolate prices
            open_price = self._interpolate_from_ticks(interval_ticks, interval_start)
            checkpoint_price = self._interpolate_from_ticks(interval_ticks, checkpoint_time)
            close_price = self._interpolate_from_ticks(ticks_for_next, interval_end) if ticks_for_next else None

            if open_price is None or checkpoint_price is None or close_price is None:
                continue

            close_dir = "above" if close_price > open_price else "below"
            cp_dir = "above" if checkpoint_price > open_price else "below"

            if close_dir == cp_dir:
                correct += 1

            total += 1

        accuracy = (correct / total * 100) if total > 0 else 0
        return accuracy, total, correct

    def _interpolate_from_ticks(self, ticks, target_time):
        """Interpolate price at target time from tick list."""
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

    def send_json(self, data, status_code=200):
        """Send a JSON response."""
        self.send_response(status_code)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def log_message(self, format, *args):
        """Suppress default logging."""
        pass


def main():
    parser = argparse.ArgumentParser(description='Bitcoin 15-minute interval tracker')
    parser.add_argument('--poll-seconds', type=int, default=15, help='Polling interval (default: 15)')
    parser.add_argument('--checkpoint-minutes', type=int, default=5, help='Minutes before close for checkpoint (default: 5)')
    parser.add_argument('--retention-days', type=int, default=90, help='Data retention in days (default: 90)')
    parser.add_argument('--bet-amount', type=float, default=50.0, help='Simulated bet amount (default: $50)')
    parser.add_argument('--entry-price', type=float, default=0.90, help='Contract entry price (default: $0.90)')
    parser.add_argument('--port', type=int, default=8000, help='Dashboard server port (default: 8000)')
    parser.add_argument('--no-server', action='store_true', help='Run tracker without dashboard server')

    args = parser.parse_args()

    # Create tracker
    tracker = Tracker(
        poll_seconds=args.poll_seconds,
        checkpoint_minutes=args.checkpoint_minutes,
        retention_days=args.retention_days,
        bet_amount=args.bet_amount,
        entry_price=args.entry_price
    )

    # Start tracker in background thread
    tracker_thread = threading.Thread(target=tracker.run, daemon=True)
    tracker_thread.start()

    # Update latest.json periodically
    def update_loop():
        while True:
            time.sleep(5)
            tracker.update_latest_json()

    update_thread = threading.Thread(target=update_loop, daemon=True)
    update_thread.start()

    # Start HTTP server if requested
    if not args.no_server:
        try:
            print(f"\n[SERVER] Dashboard starting at http://localhost:{args.port}")
            server = HTTPServer(('localhost', args.port), DashboardHandler)
            server.serve_forever()
        except KeyboardInterrupt:
            print("\n[SHUTDOWN] Received interrupt")
            tracker.running = False
    else:
        try:
            tracker_thread.join()
        except KeyboardInterrupt:
            print("\n[SHUTDOWN] Received interrupt")
            tracker.running = False


if __name__ == '__main__':
    main()
