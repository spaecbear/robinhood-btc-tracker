#!/usr/bin/env python3
"""
ml_model.py — A real, trainable logistic-regression model for predicting
whether a 15-minute interval will close ABOVE or BELOW its open price.

Key honesty principle: the prediction is made AT THE START of the interval.
That means every feature is computed from data available *before* the
interval opens (previous intervals, recent momentum leading up to the open,
time of day). We never peek at price action inside the interval we're
predicting — that would be lookahead leakage and would make the accuracy a lie.

Everything here is pure Python standard library: no numpy, no scikit-learn,
no pip installs. The logistic regression is implemented from scratch with
gradient descent so you can read exactly how it works and tweak it.

How to read the output:
  - baseline_accuracy : accuracy of just always guessing the majority class.
                        The model must BEAT this to have learned anything.
  - train_accuracy    : accuracy on the data it trained on (optimistic).
  - test_accuracy     : accuracy on a held-out chronological tail it never saw.
  - cv_accuracy       : walk-forward out-of-sample accuracy (the honest number).
  - If train >> test, the model is overfitting (memorizing noise).
"""

import csv
import json
import math
import os
import datetime

DATA_DIR = "data"
INTERVALS_CSV = os.path.join(DATA_DIR, "intervals.csv")
RAW_TICKS_CSV = os.path.join(DATA_DIR, "raw_ticks.csv")
MODEL_JSON = os.path.join(DATA_DIR, "ml_model.json")

# Minimum usable samples before we'll even try to train.
MIN_SAMPLES = 30

# Feature names, in the exact order build_dataset() emits them.
# Keeping this list small guards against overfitting on limited data.
FEATURE_NAMES = [
    # Recent price direction and momentum
    "prev_return",        # last interval's return (close-open)/open
    "prev2_return",       # 2 intervals ago
    "prev3_return",       # 3 intervals ago
    "prev4_return",       # 4 intervals ago
    "prev5_return",       # 5 intervals ago

    # Trend and volatility
    "run_length",         # signed streak of same-direction prior intervals (normalized)
    "direction_ratio",    # % of last 10 intervals that went up (0.0 to 1.0)
    "recent_vol",         # volatility: stdev of last 5 interval returns
    "dist_from_ma5",      # how far the open is from the mean of the last 5 opens

    # Pre-open momentum (minutes before interval starts)
    "mom_5m",             # price momentum over the 5 min BEFORE the open
    "mom_10m",            # price momentum over the 10 min BEFORE the open
    "velocity",           # rate of price change leading into the open
    "acceleration",       # is momentum speeding up or slowing down

    # Time of day / week
    "hour_sin",           # cyclical encoding of time-of-day (hours)
    "hour_cos",
    "dow_sin",            # cyclical encoding of day-of-week (0=Monday, 6=Sunday)
    "dow_cos",
    "is_weekend",         # 1 if Saturday/Sunday, 0 otherwise
]

# Simple in-process cache so the API doesn't retrain on every page refresh.
# Keyed on the number of interval rows; recomputes only when new data arrives.
_CACHE = {"key": None, "result": None}


# --------------------------------------------------------------------------
# Data loading
# --------------------------------------------------------------------------

def _parse_ts(s):
    """Parse an ISO timestamp that may end in 'Z'."""
    return datetime.datetime.fromisoformat(s.replace("Z", "+00:00"))


def load_intervals():
    """Load completed intervals in chronological order."""
    rows = []
    try:
        with open(INTERVALS_CSV, "r") as f:
            for row in csv.DictReader(f):
                try:
                    rows.append({
                        "start": _parse_ts(row["interval_start"]),
                        "open": float(row["open_price"]),
                        "close": float(row["close_price"]),
                    })
                except (ValueError, KeyError):
                    continue
    except FileNotFoundError:
        return []
    rows.sort(key=lambda r: r["start"])
    return rows


def load_ticks():
    """Load raw price ticks in chronological order."""
    ticks = []
    try:
        with open(RAW_TICKS_CSV, "r") as f:
            for row in csv.DictReader(f):
                try:
                    ticks.append((_parse_ts(row["timestamp"]), float(row["price"])))
                except (ValueError, KeyError):
                    continue
    except FileNotFoundError:
        return []
    ticks.sort(key=lambda t: t[0])
    return ticks


def interpolate_price(ticks, target_time):
    """Linearly interpolate the price at target_time from sorted ticks."""
    if not ticks:
        return None
    before = after = None
    for t, p in ticks:
        if t <= target_time:
            before = (t, p)
        if t >= target_time and after is None:
            after = (t, p)
    if before and after:
        if before[0] == after[0]:
            return before[1]
        frac = (target_time - before[0]) / (after[0] - before[0])
        return before[1] + (after[1] - before[1]) * frac
    if before:
        return before[1]
    if after:
        return after[1]
    return None


# --------------------------------------------------------------------------
# Feature engineering (leak-free: only uses data before the interval opens)
# --------------------------------------------------------------------------

def _stdev(values):
    n = len(values)
    if n < 2:
        return 0.0
    mean = sum(values) / n
    return math.sqrt(sum((v - mean) ** 2 for v in values) / (n - 1))


def build_dataset(intervals, ticks):
    """
    Build (features, label, meta) tuples for every interval we have enough
    history for. Features use ONLY information available at the interval's open.

    label = 1 if the interval closed above its open, else 0.
    """
    samples = []
    # Precompute each prior interval's return for streak/vol features.
    returns = [(iv["close"] - iv["open"]) / iv["open"] for iv in intervals]

    for i in range(len(intervals)):
        # Need at least 5 prior intervals to compute the history features.
        if i < 5:
            continue

        iv = intervals[i]
        open_time = iv["start"]
        open_price = iv["open"]
        label = 1 if iv["close"] > open_price else 0

        # --- History-based features (from prior intervals only) ---
        prev_return = returns[i - 1]
        prev2_return = returns[i - 2]
        prev3_return = returns[i - 3]
        prev4_return = returns[i - 4]
        prev5_return = returns[i - 5]

        # Signed streak: how many consecutive prior intervals went the same
        # direction as the most recent one. Normalized by 5 to keep it ~[-1,1].
        last_dir = 1 if returns[i - 1] > 0 else -1
        streak = 0
        j = i - 1
        while j >= 0 and (1 if returns[j] > 0 else -1) == last_dir:
            streak += 1
            j -= 1
        run_length = (streak * last_dir) / 5.0

        # Direction ratio: what % of the last 10 intervals went up?
        last10_returns = returns[max(0, i - 10):i]
        ups = sum(1 for r in last10_returns if r > 0)
        direction_ratio = ups / len(last10_returns) if last10_returns else 0.5

        recent_vol = _stdev(returns[i - 5:i])

        last5_opens = [intervals[k]["open"] for k in range(i - 5, i)]
        ma5 = sum(last5_opens) / 5.0
        dist_from_ma5 = (open_price - ma5) / open_price

        # --- Momentum leading INTO the open (from ticks before open_time) ---
        prior_ticks = [(t, p) for (t, p) in ticks if t <= open_time]
        p_open = interpolate_price(prior_ticks, open_time)
        p_5m = interpolate_price(prior_ticks, open_time - datetime.timedelta(minutes=5))
        p_10m = interpolate_price(prior_ticks, open_time - datetime.timedelta(minutes=10))
        p_15m = interpolate_price(prior_ticks, open_time - datetime.timedelta(minutes=15))

        mom_5m = ((p_open - p_5m) / p_5m) if (p_open and p_5m) else 0.0
        mom_10m = ((p_open - p_10m) / p_10m) if (p_open and p_10m) else 0.0

        # Velocity: rate of change from 15m to 5m before open
        # (capturing whether price is accelerating or decelerating)
        if p_15m and p_5m and p_open:
            mom_15m_to_5m = (p_5m - p_15m) / p_15m
            mom_5m_to_0m = (p_open - p_5m) / p_5m
            velocity = mom_5m_to_0m  # current momentum
            # Acceleration: is it speeding up (positive) or slowing (negative)?
            acceleration = (mom_5m_to_0m - mom_15m_to_5m) / (abs(mom_15m_to_5m) + 0.0001)
        else:
            velocity = mom_5m
            acceleration = 0.0

        # --- Time-of-day, cyclically encoded so 23:59 is near 00:00 ---
        frac_day = (open_time.hour + open_time.minute / 60.0) / 24.0
        hour_sin = math.sin(2 * math.pi * frac_day)
        hour_cos = math.cos(2 * math.pi * frac_day)

        # --- Day-of-week, cyclically encoded so Sunday is near Monday ---
        # Monday=0, Tuesday=1, ..., Sunday=6
        dow = open_time.weekday()  # 0=Monday, 6=Sunday
        frac_week = dow / 7.0
        dow_sin = math.sin(2 * math.pi * frac_week)
        dow_cos = math.cos(2 * math.pi * frac_week)
        is_weekend = 1.0 if dow >= 4 else 0.0  # Saturday=5, Sunday=6

        features = [
            # Prior returns (longer history)
            prev_return, prev2_return, prev3_return, prev4_return, prev5_return,
            # Trend and volatility
            run_length, direction_ratio, recent_vol, dist_from_ma5,
            # Pre-open momentum
            mom_5m, mom_10m, velocity, acceleration,
            # Time features
            hour_sin, hour_cos, dow_sin, dow_cos, is_weekend,
        ]
        samples.append((features, label, {
            "start": iv["start"].isoformat() + "Z",
            "open": open_price,
            "close": iv["close"],
        }))
    return samples


# --------------------------------------------------------------------------
# Standardization (z-score). LR converges far better on scaled inputs.
# --------------------------------------------------------------------------

def fit_scaler(X):
    n_feat = len(X[0])
    means, stds = [], []
    for j in range(n_feat):
        col = [row[j] for row in X]
        m = sum(col) / len(col)
        s = _stdev(col) or 1.0  # avoid divide-by-zero on constant columns
        means.append(m)
        stds.append(s)
    return means, stds


def apply_scaler(X, means, stds):
    return [[(row[j] - means[j]) / stds[j] for j in range(len(row))] for row in X]


# --------------------------------------------------------------------------
# Logistic regression from scratch (gradient descent + L2 regularization)
# --------------------------------------------------------------------------

def _sigmoid(z):
    # Clamp to avoid math.exp overflow on large |z|.
    if z < -35:
        return 0.0
    if z > 35:
        return 1.0
    return 1.0 / (1.0 + math.exp(-z))


def train_logreg(X, y, lr=0.1, epochs=400, l2=0.01):
    """Train weights + bias by batch gradient descent. Returns (weights, bias)."""
    n_feat = len(X[0])
    w = [0.0] * n_feat
    b = 0.0
    n = len(X)

    for _ in range(epochs):
        grad_w = [0.0] * n_feat
        grad_b = 0.0
        for xi, yi in zip(X, y):
            z = b + sum(w[j] * xi[j] for j in range(n_feat))
            err = _sigmoid(z) - yi
            for j in range(n_feat):
                grad_w[j] += err * xi[j]
            grad_b += err
        # Average gradient + L2 penalty on weights (not bias).
        for j in range(n_feat):
            w[j] -= lr * (grad_w[j] / n + l2 * w[j])
        b -= lr * (grad_b / n)
    return w, b


def predict_proba(w, b, xi):
    return _sigmoid(b + sum(w[j] * xi[j] for j in range(len(xi))))


def _accuracy(w, b, X, y):
    if not X:
        return 0.0
    correct = sum(1 for xi, yi in zip(X, y)
                  if (1 if predict_proba(w, b, xi) >= 0.5 else 0) == yi)
    return correct / len(X)


# --------------------------------------------------------------------------
# Evaluation: chronological holdout + walk-forward (the honest test)
# --------------------------------------------------------------------------

def walk_forward(samples, initial_frac=0.5, retrain_every=5):
    """
    Out-of-sample evaluation that respects time order: train on everything
    before sample i, predict sample i, then move forward. This is the number
    you should trust — every prediction is made with zero knowledge of its
    own outcome or any future data.

    Returns (predictions, accuracy) where predictions is a list of dicts.
    """
    n = len(samples)
    start = max(MIN_SAMPLES, int(n * initial_frac))
    if start >= n:
        start = max(1, n - 1)

    predictions = []
    w = b = None
    means = stds = None

    for i in range(start, n):
        # Retrain periodically (and on the first step) to bound CPU cost.
        if w is None or (i - start) % retrain_every == 0:
            X_hist = [s[0] for s in samples[:i]]
            y_hist = [s[1] for s in samples[:i]]
            means, stds = fit_scaler(X_hist)
            Xs = apply_scaler(X_hist, means, stds)
            w, b = train_logreg(Xs, y_hist)

        feat, label, meta = samples[i]
        xs = apply_scaler([feat], means, stds)[0]
        proba = predict_proba(w, b, xs)
        pred = 1 if proba >= 0.5 else 0
        predictions.append({
            "start": meta["start"],
            "open": meta["open"],
            "close": meta["close"],
            "prediction": "above" if pred == 1 else "below",
            "actual": "above" if label == 1 else "below",
            "confidence": round(proba if pred == 1 else 1 - proba, 3),
            "correct": pred == label,
        })

    acc = (sum(1 for p in predictions if p["correct"]) / len(predictions)
           if predictions else 0.0)
    return predictions, acc


# --------------------------------------------------------------------------
# Top-level analysis used by the dashboard API and the CLI
# --------------------------------------------------------------------------

def run_ml_analysis(use_cache=True):
    """
    Train, evaluate, and produce a JSON-serializable report for the dashboard.
    """
    intervals = load_intervals()

    cache_key = len(intervals)
    if use_cache and _CACHE["key"] == cache_key and _CACHE["result"] is not None:
        return _CACHE["result"]

    ticks = load_ticks()
    samples = build_dataset(intervals, ticks)

    if len(samples) < MIN_SAMPLES:
        result = {
            "status": "insufficient_data",
            "have": len(samples),
            "need": MIN_SAMPLES,
            "message": (
                f"Need at least {MIN_SAMPLES} usable intervals to train; "
                f"have {len(samples)}. Keep the tracker running."
            ),
        }
        _CACHE["key"] = cache_key
        _CACHE["result"] = result
        return result

    X = [s[0] for s in samples]
    y = [s[1] for s in samples]

    # Baseline: always guess the majority class.
    above_rate = sum(y) / len(y)
    baseline = max(above_rate, 1 - above_rate)

    # Chronological holdout: train on first 70%, test on last 30%.
    split = int(len(samples) * 0.7)
    Xtr, ytr = X[:split], y[:split]
    Xte, yte = X[split:], y[split:]
    means, stds = fit_scaler(Xtr)
    Xtr_s = apply_scaler(Xtr, means, stds)
    Xte_s = apply_scaler(Xte, means, stds)
    w, b = train_logreg(Xtr_s, ytr)
    train_acc = _accuracy(w, b, Xtr_s, ytr)
    test_acc = _accuracy(w, b, Xte_s, yte) if Xte_s else 0.0

    # Walk-forward out-of-sample predictions (the honest accuracy + the table).
    wf_predictions, wf_acc = walk_forward(samples)

    # Train a final model on ALL data to (a) report feature weights and
    # (b) predict the next interval's direction.
    means_all, stds_all = fit_scaler(X)
    Xs_all = apply_scaler(X, means_all, stds_all)
    w_all, b_all = train_logreg(Xs_all, y)

    # Feature weights (on standardized inputs => directly comparable importance).
    weights = sorted(
        [{"name": FEATURE_NAMES[j], "weight": round(w_all[j], 4)}
         for j in range(len(w_all))],
        key=lambda d: abs(d["weight"]), reverse=True,
    )

    # Predict the most recent interval's "next" — i.e. apply the model to the
    # latest feature row as a live forward-looking call.
    latest_feat = X[-1]
    latest_scaled = apply_scaler([latest_feat], means_all, stds_all)[0]
    latest_proba = predict_proba(w_all, b_all, latest_scaled)
    next_prediction = {
        "prediction": "above" if latest_proba >= 0.5 else "below",
        "confidence": round(latest_proba if latest_proba >= 0.5 else 1 - latest_proba, 3),
    }

    result = {
        "status": "ok",
        "samples": len(samples),
        "baseline_accuracy": round(baseline * 100, 1),
        "above_rate": round(above_rate * 100, 1),
        "train_accuracy": round(train_acc * 100, 1),
        "test_accuracy": round(test_acc * 100, 1),
        "cv_accuracy": round(wf_acc * 100, 1),
        "overfit_gap": round((train_acc - test_acc) * 100, 1),
        "edge_vs_baseline": round((wf_acc - baseline) * 100, 1),
        "feature_weights": weights,
        "next_prediction": next_prediction,
        # Most recent first for the table.
        "predictions": list(reversed(wf_predictions)),
    }

    # Persist the trained model so it's inspectable / reusable.
    try:
        with open(MODEL_JSON, "w") as f:
            json.dump({
                "weights": w_all, "bias": b_all,
                "means": means_all, "stds": stds_all,
                "feature_names": FEATURE_NAMES,
            }, f, indent=2)
    except OSError:
        pass

    _CACHE["key"] = cache_key
    _CACHE["result"] = result
    return result


def _print_report(r):
    if r["status"] != "ok":
        print(f"[ML] {r['message']}")
        return
    print("\n" + "=" * 60)
    print("MACHINE LEARNING MODEL REPORT")
    print("=" * 60)
    print(f"Usable samples        : {r['samples']}")
    print(f"Class balance (above) : {r['above_rate']}%")
    print("-" * 60)
    print(f"Baseline (majority)   : {r['baseline_accuracy']}%   <- must beat this")
    print(f"Walk-forward (honest) : {r['cv_accuracy']}%")
    print(f"Edge vs baseline      : {r['edge_vs_baseline']:+.1f} pts")
    print("-" * 60)
    print(f"Train accuracy        : {r['train_accuracy']}%")
    print(f"Test accuracy         : {r['test_accuracy']}%")
    print(f"Overfit gap (tr-te)   : {r['overfit_gap']:+.1f} pts")
    print("-" * 60)
    print("Feature importance (|weight| on standardized inputs):")
    for fw in r["feature_weights"]:
        print(f"   {fw['name']:<16} {fw['weight']:+.4f}")
    print("-" * 60)
    np = r["next_prediction"]
    print(f"Next-interval call    : {np['prediction'].upper()} "
          f"(confidence {np['confidence']*100:.1f}%)")
    print("=" * 60)


if __name__ == "__main__":
    _print_report(run_ml_analysis(use_cache=False))
