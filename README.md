# Bitcoin 15-Minute Pattern Tracker

A self-contained pattern-study tool for analyzing Bitcoin price movements across 15-minute intervals. Designed for backtesting predictive signals on Robinhood-style "above/below" contracts—purely for educational pattern recognition, not live trading.

## Features

- **Live price polling**: Fetches BTC/USD every 15 seconds (configurable) from CoinGecko's free API.
- **15-minute interval tracking**: Captures open, close, and checkpoint prices for each interval.
- **Pattern analysis**: Compares early checkpoint readings to final interval close to measure predictive accuracy.
- **Raw tick logging**: Stores all price ticks for retroactive checkpoint offset analysis.
- **Live dashboard**: Interactive HTML dashboard served locally, with:
  - Real-time price and interval status.
  - Zoomable, pannable price chart with interval markers.
  - Historical interval browsing.
  - Simulated P&L based on checkpoint direction calls.
  - Bankroll simulation with drawdown analysis.
  - Offset accuracy analysis (test different checkpoint positions).
- **CSV data persistence**: All data appended to CSV files for durability and offline analysis.
- **Zero dependencies**: Pure Python standard library—no pip installs required.

## Installation & Setup

### Requirements
- **Python 3.7+** on macOS, Windows, or Linux.
- Internet connection (to fetch BTC prices from CoinGecko).
- Any modern web browser for the dashboard.

### Quick Start

1. **Clone or download this repository** to a folder on your machine.

2. **Navigate to the folder**:
   ```bash
   cd /path/to/robinhood
   ```

3. **Start the tracker and dashboard**:
   ```bash
   python3 tracker.py
   ```

   This will:
   - Start polling BTC price every 15 seconds.
   - Log all ticks and completed intervals to CSV files in the `data/` folder.
   - Launch the live dashboard at `http://localhost:8000`.

4. **Open your browser** and go to:
   ```
   http://localhost:8000
   ```

   The dashboard will display live price data, intervals, and backtest metrics.

## Configuration

### Command-Line Flags

All flags are optional; defaults are shown:

```bash
python3 tracker.py \
  --poll-seconds 15 \
  --checkpoint-minutes 5 \
  --retention-days 90 \
  --bet-amount 50.0 \
  --entry-price 0.90 \
  --port 8000
```

| Flag | Default | Description |
|------|---------|-------------|
| `--poll-seconds` | 15 | Seconds between price polls. Min: 10 (don't hammer the API). |
| `--checkpoint-minutes` | 5 | Minutes before interval close to capture checkpoint price. |
| `--retention-days` | 90 | Keep this much historical data; purge older records. |
| `--bet-amount` | 50.0 | Simulated bet size in dollars per interval. |
| `--entry-price` | 0.90 | Contract entry price (payout multiplier). |
| `--port` | 8000 | HTTP port for the dashboard. |
| `--no-server` | (flag) | Skip the web server; just run the tracker (useful for headless mode). |

### Examples

**Tighter polling (more data granularity, but more API calls)**:
```bash
python3 tracker.py --poll-seconds 10
```

**Checkpoint at 3 minutes instead of 5**:
```bash
python3 tracker.py --checkpoint-minutes 3
```

**Different dashboard port**:
```bash
python3 tracker.py --port 9000
```
Then visit `http://localhost:9000`.

**Keep 180 days of data**:
```bash
python3 tracker.py --retention-days 180
```

**Run without the web dashboard** (useful for a server or background process):
```bash
python3 tracker.py --no-server
```

## Data Files

All data is stored in the `data/` folder (created automatically):

| File | Contents |
|------|----------|
| `intervals.csv` | One row per completed 15-minute interval: start time, open/close/checkpoint prices, directions, whether checkpoint predicted close direction, missed toggle, simulated bet/entry price, and P&L. |
| `raw_ticks.csv` | Every price tick: timestamp and price. ~5,000–6,000 rows/day at 15-second polling. |
| `latest.json` | Current live state: latest price, interval boundaries, counts, daily P&L. Updated every 5 seconds. |

### CSV Column Reference

**intervals.csv:**
```
interval_start,open_price,close_price,checkpoint_price,checkpoint_minutes_before_close,
close_direction,checkpoint_direction,checkpoint_matched_close,missed,bet_amount,entry_price
```

- `interval_start`: ISO 8601 timestamp (UTC) of the interval's start (e.g., `2026-06-22T14:15:00Z`).
- `open_price`, `close_price`, `checkpoint_price`: USD prices (float).
- `checkpoint_minutes_before_close`: How many minutes before the close the checkpoint was sampled.
- `close_direction`: `above` or `below` relative to `open_price`.
- `checkpoint_direction`: `above` or `below` relative to `open_price`.
- `checkpoint_matched_close`: `true` if checkpoint direction matched close direction, `false` otherwise.
- `missed`: `true` if you manually marked this interval as not placed (excluded from P&L), `false` otherwise.
- `bet_amount`: Simulated bet size used.
- `entry_price`: Contract entry price used.

**raw_ticks.csv:**
```
timestamp,price
```

- `timestamp`: ISO 8601 UTC (e.g., `2026-06-22T14:15:30.123456Z`).
- `price`: USD price (float).

## Dashboard Overview

### Live Status Panel
- **Current Price**: Real-time BTC/USD.
- **Interval Open**: Price at the start of the current 15-minute interval.
- **Change**: $-amount and color-coded direction from open.
- **Time to Close**: Countdown timer to the next interval boundary.

### Chart Tab
- **Line chart** of the last 24 hours of price ticks.
- **Navigation buttons**: Zoom in/out, previous/next, back-to-live.
- **Time display**: Shows the current chart's date/time range.
- **Legend**: Explains the visual markers.

### History Tab
- **Interval table**: Lists recent completed intervals with open, close, checkpoint, directions, and P&L.
- **Date filter**: (Coming soon) Filter by specific dates.

### Backtest Tab
- **Inputs**:
  - **Bet Amount**: Change the simulated bet size; recalculates P&L.
  - **Entry Price**: Change the contract entry price; recalculates payout and profit.
  - **Start Seed**: Simulate starting with a specific bankroll; shows balance trajectory.
  
- **Stats**:
  - **Win Rate**: % of intervals where checkpoint correctly predicted close.
  - **Daily P&L**: Net profit/loss for today.
  - **Max Drawdown**: Largest balance dip during the day.
  - **Min Required Seed**: Smallest starting balance that would have survived all losing streaks.
  - **Period totals**: Daily, monthly, yearly sums (monthly/yearly when applicable).

### Analysis Tab
- **Offset Analysis**: Run a backtest across multiple checkpoint offsets (1–10 minutes) to see which offset has the best prediction accuracy.
- Results shown as a table with accuracy % and correct/total count for each offset.

## Pattern Study Workflow

### Step 1: Collect baseline data
Run the tracker for several hours or days to build a history:

```bash
python3 tracker.py --checkpoint-minutes 5
```

Let it log intervals in the background.

### Step 2: Test different checkpoint offsets
Use the analysis tool to find which checkpoint offset (minutes before close) has the best predictive power:

```bash
python3 analysis.py --offsets 1,2,3,4,5,6,7,8,9,10 --json
```

This recomputes accuracy using the raw ticks for each offset, showing which reads the checkpoint price most predictively.

Or use the dashboard's **Analysis** tab to run the analysis interactively.

### Step 3: Simulate bets with that offset
Once you've identified a promising offset (say, 3 minutes), restart the tracker with that offset and monitor the live P&L:

```bash
python3 tracker.py --checkpoint-minutes 3
```

Adjust bet amount and entry price as desired.

### Step 4: Study patterns visually
Browse historical intervals in the **History** tab and zoom into the **Chart** to spot patterns:
- Do winning intervals cluster at certain times of day?
- Are there specific price ranges where checkpoint readings are more reliable?
- What's the worst drawdown in a losing streak?

### Step 5: Simulate bankroll survival
Use the **Backtest** tab to ask: "If I start with $100 and place $50 bets, would I survive a day like June 22?"

Adjust the start seed to find the minimum bankroll needed.

## Analysis Script

For offline or command-line analysis:

```bash
python3 analysis.py --offsets 1,3,5,7,10 --checkpoint-minutes 5
```

**Flags:**
| Flag | Description |
|------|-------------|
| `--offsets` | Comma-separated list of offsets to test (default: `1,3,5,7,10`). |
| `--checkpoint-minutes` | Which offset to analyze in detail (default: 5). |
| `--by-date` | Show accuracy grouped by calendar date. |
| `--json` | Output as JSON instead of pretty-printed table. |

**Examples:**

Accuracy for offsets 1–10 minutes:
```bash
python3 analysis.py --offsets 1,2,3,4,5,6,7,8,9,10
```

Accuracy by date for the 5-minute offset:
```bash
python3 analysis.py --checkpoint-minutes 5 --by-date
```

JSON output (for scripting):
```bash
python3 analysis.py --offsets 1,5,10 --json
```

## Data Retention & Cleanup

By default, data older than **90 days** is automatically purged on tracker startup and periodically while running.

To keep more history:
```bash
python3 tracker.py --retention-days 180
```

To keep less:
```bash
python3 tracker.py --retention-days 30
```

To manually clean the `data/` folder:
```bash
rm -rf data/
```

The tracker will recreate empty CSV files on the next run.

## API Reference & Notes

### CoinGecko Free API
The tracker uses CoinGecko's free endpoint:
```
https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd
```

- **Rate limit**: ~10–30 calls per minute for free users.
- **Minimum polling interval**: ~15 seconds is safe; don't go below 10 seconds.
- **Fallback**: If a fetch fails, the tracker logs an error and retries on the next poll. It won't crash.

### Interval Boundaries
Intervals are defined as:
- **0:00–0:15, 0:15–0:30, 0:30–0:45, 0:45–1:00**, etc., in UTC.

All timestamps are in UTC for consistency across timezones.

### Checkpoint & Direction Calculation
- **Open**: Price at the interval's start.
- **Checkpoint**: Price at (interval_start + (15 - checkpoint_minutes)).
- **Close**: Price at the next interval's start (interval_start + 15 minutes).
- **Direction**: `above` if price > open, `below` if price ≤ open.

### Payout Simulation
Given bet size and entry price:
```
contracts = bet_amount / entry_price
if checkpoint_direction == close_direction:
    payout = contracts × $1.00
    profit = payout - bet_amount
else:
    payout = $0
    profit = -bet_amount  # Full loss
```

This models a binary options contract that pays $1 per contract if the prediction is correct, $0 if wrong.

## Troubleshooting

### Dashboard won't load
- Check that the tracker is running: `python3 tracker.py` should be in the terminal.
- Verify the port (default 8000) isn't in use. Use `--port 9000` to change it.
- Clear your browser cache and refresh.

### No price data appearing
- Check your internet connection.
- Verify CoinGecko API is reachable: `curl https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd`
- Check the tracker terminal for error messages.

### CSV files are huge / want to reset data
- Stop the tracker.
- Delete the `data/` folder: `rm -rf data/`
- Restart the tracker; it will create fresh empty CSVs.

### Wrong or missing intervals
- Make sure the tracker has been running long enough to capture a full 15-minute interval.
- Check that `data/intervals.csv` exists and has rows.
- Verify time on your machine is correct (intervals are UTC).

### Checkpoint offset doesn't seem to change results
- Run the analysis script with multiple offsets to compare: `python3 analysis.py --offsets 1,5,10`.
- Ensure enough history is logged (at least a few hours).
- Remember: some price movements are inherently unpredictable; not all offsets will show big differences.

## Important Disclaimers

**This tool is for backtesting and pattern study only.** It simulates P&L but does not place real trades or bets:

- ✅ Do: Use it to understand historical accuracy of checkpoint readings before risking real money.
- ✅ Do: Log your trades manually and mark "missed" intervals to compare simulation vs. reality.
- ❌ Don't: Automate betting with this tool; always make manual trading decisions.
- ❌ Don't: Assume past accuracy predicts future returns; markets change.
- ❌ Don't: Ignore the asymmetric payoff (small upside, full downside loss); starting capital matters.

See the **Bankroll / Starting Capital Simulation** section above to understand how much seed capital you'd actually need.

## Development & Customization

### Changing polling behavior
Edit the `poll_seconds` in `tracker.py` or pass `--poll-seconds` at startup.

### Adding custom metrics
The `Tracker` class in `tracker.py` can be extended:
- Modify `_log_interval()` to compute additional fields.
- Add new columns to the CSV header in `_ensure_data_dir()`.

### Customizing the dashboard
Edit `dashboard.html` directly:
- CSS styling is inline; update colors, fonts, layout in the `<style>` block.
- Chart.js config is in the `<script>` section; adjust chart appearance there.
- Add new API endpoints in `tracker.py`'s `DashboardHandler` class.

### Running without the web server
Use the `--no-server` flag to run the tracker in the background without serving the dashboard. The CSV files will still be updated. Then, analyze them manually with `analysis.py` or a spreadsheet app.

## Example Session

```bash
# 1. Start the tracker
python3 tracker.py --checkpoint-minutes 5 --bet-amount 50

# Tracker outputs:
# [TRACKER] Starting with poll interval=15s, checkpoint=5min
# [SERVER] Dashboard starting at http://localhost:8000
# [14:15:22] BTC: $67,234.56
# [14:15:37] BTC: $67,235.00
# ...
# [INTERVAL] 2026-06-22T14:00:00Z | O: $67100.00 C: $67150.00 (above) | CP: $67120.00 (above) | Match: true | P&L: +$5.56

# 2. Open http://localhost:8000 in your browser
# → See live price, chart, interval markers.

# 3. After a few hours, analyze offsets:
python3 analysis.py --offsets 1,3,5,7,10

# Output:
# ============================================================
# CHECKPOINT OFFSET ACCURACY ANALYSIS
# ============================================================
# Offset (min)    Accuracy         Correct/Total
# ============================================================
# 1                      42.50%                 17/40
# 3                      50.00%                 20/40
# 5                      52.50%                 21/40
# 7                      45.00%                 18/40
# 10                     40.00%                 16/40
# ============================================================

# 4. Looks like 5 minutes is best; continue with the current settings.
# 5. Use the Backtest tab to simulate: "If I start with $200 and bet $50 per interval, what's my max drawdown today?"
```

## License

This tool is provided as-is for educational and personal research purposes. Use at your own risk.

---

**Questions or issues?** Check the Troubleshooting section, or review the code comments in `tracker.py` and `analysis.py`.
