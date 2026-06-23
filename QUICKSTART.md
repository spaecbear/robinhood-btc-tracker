# Quick Start Guide

Get your Bitcoin pattern tracker running in 30 seconds.

## 1. Start the Tracker

Open a terminal and run:

```bash
python3 tracker.py
```

You'll see:
```
[TRACKER] Starting with poll interval=15s, checkpoint=5min
[SERVER] Dashboard starting at http://localhost:8000
[14:15:22] BTC: $67,234.56
[14:15:37] BTC: $67,235.00
...
```

**Done!** The tracker is now:
- ✅ Polling BTC price every 15 seconds
- ✅ Logging to `data/intervals.csv` and `data/raw_ticks.csv`
- ✅ Serving the dashboard on `http://localhost:8000`

## 2. Open the Dashboard

Click here or paste into your browser:
```
http://localhost:8000
```

You'll see:
- **Live Status**: Current BTC price, interval open, countdown timer
- **Chart Tab**: Price line with interval markers
- **History Tab**: Table of recent intervals
- **Backtest Tab**: P&L simulation
- **Analysis Tab**: Test different checkpoint offsets

## 3. Let It Run

The tracker runs 24/7 and accumulates data. Come back anytime to:
- Watch live prices and intervals
- Browse historical data
- Backtest different bet amounts
- Analyze which checkpoint offsets work best

---

## Common Tweaks

### Change the checkpoint offset (minutes before close)
```bash
python3 tracker.py --checkpoint-minutes 3
```

### Simulate bigger bets
```bash
python3 tracker.py --bet-amount 100
```

### Different contract entry price
```bash
python3 tracker.py --entry-price 0.80
```

### Combine settings
```bash
python3 tracker.py --checkpoint-minutes 3 --bet-amount 100 --entry-price 0.80
```

### Use a different dashboard port
```bash
python3 tracker.py --port 9000
```
Then visit `http://localhost:9000`

---

## Analyze Checkpoints (CLI)

After running for a few hours, test different checkpoint offsets:

```bash
python3 analysis.py --offsets 1,3,5,7,10
```

Output:
```
============================================================
CHECKPOINT OFFSET ACCURACY ANALYSIS
============================================================
Offset (min)    Accuracy         Correct/Total
============================================================
1                      42.50%                 17/40
3                      50.00%                 20/40
5                      52.50%                 21/40
7                      45.00%                 18/40
10                     40.00%                 16/40
============================================================
```

Or use the dashboard's **Analysis** tab to run it live.

---

## Stop the Tracker

Press `Ctrl+C` in the terminal where it's running.

Data is automatically saved—restart anytime to pick up where you left off.

---

## What's Being Tracked?

| File | Contains |
|------|----------|
| `data/raw_ticks.csv` | Every price tick (~5,000+ rows/day) |
| `data/intervals.csv` | Completed 15-min intervals with P&L |
| `data/latest.json` | Current live state (updated every 5s) |

---

## Next Steps

📖 **Full documentation**: See [README.md](README.md)

🧪 **Try the backtest simulator**: In the dashboard, go to **Backtest** tab and adjust:
- Bet amount
- Entry price
- Starting seed (bankroll)

See how much capital you'd need to survive a day's losing streaks.

📊 **Analyze patterns**: Zoom into the chart to inspect individual intervals. Look for:
- Time-of-day patterns
- Price range behaviors
- Win-rate clusters

🎯 **Study before betting**: This is purely for pattern familiarization—don't place real bets until you're confident in the data.

---

## Troubleshooting

**Dashboard won't load?**
- Make sure `python3 tracker.py` is still running in the terminal.
- Try refreshing the browser (`Cmd+R` or `Ctrl+R`).

**No price data?**
- Check your internet connection.
- Make sure you gave it time to log a full 15-minute interval.

**Want to start fresh?**
```bash
rm -rf data/
python3 tracker.py
```

---

**Ready? Run `python3 tracker.py` now!** 🚀
