"""Generate synthetic NQ-like 1-minute data for smoke-testing the backtester.

Random data has no real edge, so results on it mean nothing about the
strategy. It only proves the pipeline runs. Use real NQ 1m data for research.

    python make_sample_data.py sample_nq_1m.csv --days 60
"""
import argparse

import numpy as np
import pandas as pd


def make(days: int = 60, start: str = "2025-01-06", seed: int = 7, price: float = 21000.0):
    rng = np.random.default_rng(seed)
    idx = []
    d = pd.Timestamp(start)
    made = 0
    while made < days:
        if d.weekday() < 5:
            # Globex: 18:00 prior day -> 17:00, skip 17:00-18:00 halt
            s = pd.Timestamp(f"{(d - pd.Timedelta(days=1)).date()} 18:00")
            idx.append(pd.date_range(s, periods=23 * 60, freq="1min"))
            made += 1
        d += pd.Timedelta(days=1)
    ts = pd.DatetimeIndex(np.concatenate([i.values for i in idx]))
    hours = ts.hour + ts.minute / 60
    # volatility profile: quiet Asia, busier London, busiest NY open
    vol = np.where((hours >= 9.5) & (hours < 11.5), 6.0,
          np.where((hours >= 2) & (hours < 5), 3.5,
          np.where((hours >= 8) & (hours < 16), 4.0, 2.0)))
    # mean-reverting noise so session extremes get swept and reclaimed
    ret = rng.standard_t(4, len(ts)) * vol * 0.6
    close = np.empty(len(ts))
    p = price
    anchor = price
    for k, r in enumerate(ret):
        if k % 1380 == 0:
            anchor = p
        p = p + r - 0.002 * (p - anchor)
        close[k] = p
    open_ = np.concatenate([[price], close[:-1]])
    wick = np.abs(rng.normal(0, vol * 0.5))
    high = np.maximum(open_, close) + wick
    low = np.minimum(open_, close) - np.abs(rng.normal(0, vol * 0.5))
    q = lambda x: np.round(x * 4) / 4
    return pd.DataFrame({"timestamp": ts, "open": q(open_), "high": q(high),
                         "low": q(low), "close": q(close)})


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--days", type=int, default=60)
    ap.add_argument("--seed", type=int, default=7)
    a = ap.parse_args()
    make(a.days, seed=a.seed).to_csv(a.out, index=False)
    print(f"wrote {a.out}")
