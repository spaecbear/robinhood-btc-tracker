# Bitcoin 15-Min Pattern Tracker - Setup Guide

## Quick Start (All Platforms)

### Prerequisites
- **Python 3.7+** ([Download here](https://www.python.org/downloads/))
  - On Windows: Make sure to check "Add Python to PATH" during installation
- **Git** (optional, for cloning this repo)

### Installation

1. **Clone or download this repository**
   ```bash
   git clone https://github.com/YOUR_GITHUB_USERNAME/robinhood-btc-tracker.git
   cd robinhood-btc-tracker
   ```

2. **Start the tracker**
   ```bash
   python tracker.py
   ```
   
   On some systems you may need to use `python3` instead of `python`:
   ```bash
   python3 tracker.py
   ```

3. **Open your browser**
   - Navigate to: `http://localhost:8000`
   - The dashboard will auto-update as data is collected

## Configuration

### Command-line Flags

```bash
# Run with custom settings
python tracker.py --poll-seconds 15 --checkpoint-minutes 5 --port 8000

# Available options:
--poll-seconds       Polling interval in seconds (default: 15, min: 10)
--checkpoint-minutes Minutes before close for checkpoint (default: 5, range: 1-14)
--retention-days     Keep this much historical data (default: 90)
--bet-amount         Simulated bet size in dollars (default: 50)
--entry-price        Contract entry price (default: 0.90)
--port               Dashboard port (default: 8000)
--no-server          Run tracker without web server
```

### Example: Custom Settings
```bash
python tracker.py --checkpoint-minutes 3 --bet-amount 100 --port 9000
```

Then open: `http://localhost:9000`

## Data Files

All data is stored locally in the `data/` folder:
- `raw_ticks.csv` — Every price tick (timestamp, price)
- `intervals.csv` — Completed 15-min intervals with metrics
- `latest.json` — Current live state (for dashboard)

Data is kept for 90 days by default. To change retention:
```bash
python tracker.py --retention-days 180
```

## Running in the Background (Windows)

To keep the tracker running even when you close the terminal:

### Option 1: Task Scheduler (Recommended)
1. Open Task Scheduler (search "Task Scheduler" in Windows)
2. Create Basic Task → Name it "BTC Tracker"
3. Trigger: At startup
4. Action: Start program
   - Program: `C:\Python311\python.exe` (or your Python path)
   - Arguments: `C:\path\to\robinhood-btc-tracker\tracker.py`
   - Start in: `C:\path\to\robinhood-btc-tracker\`
5. Check "Run whether user is logged in or not"

### Option 2: Command Prompt (Simple)
Run this command to start the tracker in the background:
```bash
python tracker.py > tracker.log 2>&1 &
```

Or use `pythonw.exe` to run without a visible window:
```bash
pythonw.exe tracker.py
```

## Stopping the Tracker

- Press `Ctrl+C` in the terminal where it's running
- If running via Task Scheduler, disable the task

## Troubleshooting

### "Python not found"
- Reinstall Python and check "Add Python to PATH"
- Or use the full path: `C:\Python311\python.exe tracker.py`

### "Port 8000 already in use"
- Use a different port: `python tracker.py --port 9000`
- Or kill the process using that port

### "No data showing in dashboard"
- Wait 1-2 minutes for the first data point to arrive
- Check that you have an internet connection
- Make sure CoinGecko API is accessible

### Dashboard won't load
- Verify the tracker is running (you should see output in the terminal)
- Try a hard refresh: `Ctrl+Shift+R` in your browser
- Check if port 8000 is in use: `netstat -ano | findstr :8000`

## Features

- **Live price tracking**: Updates every 15 seconds (configurable)
- **15-minute interval analysis**: Open/close/checkpoint prices and directions
- **ML prediction model**: Tests if checkpoint readings predict close direction
- **Backtest simulator**: Simulate P&L with adjustable bet amounts and entry prices
- **Historical analysis**: Browse and analyze past intervals
- **Offset testing**: Find optimal checkpoint offset for your strategy

## Dashboard Tabs

- **📈 Chart**: Real-time price chart with interval markers
- **📊 History**: Table of recent intervals with P&L
- **💰 Backtest**: Simulate bets and bankroll over time
- **📉 Analysis**: Test different checkpoint offsets
- **🤖 ML Prediction**: Machine learning accuracy tracking

## Development

To run the analysis tool standalone:
```bash
python analysis.py --offsets 1,3,5,7,10 --by-date
```

## Important Notes

- This tool is for **educational and pattern study only**
- No real trades are placed — all calculations are simulations
- Keep the tracker running continuously for best results
- Data is stored locally and never sent anywhere

## Moving Between Computers

1. Copy the entire `robinhood-btc-tracker` folder to the new computer
2. (Optional) Copy the `data/` folder to preserve history
3. Run `python tracker.py` on the new computer
4. Open `http://localhost:8000`

All settings and data are portable!
