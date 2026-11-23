"""
Session Liquidity Sweep + 1m FVG Reversal: backtester.

Implements the rules in ../STRATEGY.md on 1-minute OHLC data:

  1. Mark Asia (20:00-00:00 ET), London (02:00-05:00 ET), prior-day RTH and
     pre-market (08:00-09:30) highs/lows.
  2. In the NY window (default 09:30-11:30 ET) wait for a still-unswept
     level to be swept by >= 1 tick.
  3. After the sweep, require displacement + a fair value gap that formed
     after the sweep extreme (and, optionally, a market-structure shift).
  4. Limit entry at the FVG edge (or midpoint); stop beyond the sweep
     extreme; target the nearest draw on liquidity giving >= min_rr
     (or a fixed R multiple: the reel's original version).

Short setups are evaluated by mirroring prices (x -> -x) so a single
"long-space" implementation handles both directions.

Usage:
    python session_sweep_fvg.py data.csv [--target fixed] [--entry mid] ...
    python session_sweep_fvg.py --help
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import math
import sys
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta

import numpy as np
import pandas as pd

NY = "America/New_York"


# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------
@dataclass
class Config:
    # instrument
    tick: float = 0.25
    point_value: float = 20.0          # NQ $20/pt, MNQ $2/pt
    commission_rt: float = 4.50        # $ per contract round trip
    slippage_ticks: int = 1            # applied to stop & time exits

    # sessions (ET)
    asia_start: time = time(20, 0)     # previous calendar day
    asia_end: time = time(0, 0)
    london_start: time = time(2, 0)
    london_end: time = time(5, 0)
    premarket_start: time = time(8, 0)
    rth_start: time = time(9, 30)
    rth_end: time = time(16, 0)
    context_start: time = time(7, 0)   # bars loaded for swing structure
    window_start: time = time(9, 30)
    last_entry: time = time(11, 30)
    flat_time: time = time(12, 0)

    # which levels count as sweepable liquidity
    sweep_levels: tuple = ("asia", "london", "pd")
    use_premarket_as_target: bool = True

    # setup
    sweep_min_ticks: int = 1
    require_mss: bool = True
    displacement_body_frac: float = 0.6
    displacement_range_mult: float = 1.0   # x avg range of last 10 bars
    arm_timeout_bars: int = 30             # sweep -> setup must happen within
    entry_mode: str = "edge"               # "edge" | "mid"
    entry_timeout_bars: int = 15

    # risk
    stop_buffer_ticks: int = 2
    min_stop_pts: float = 5.0
    max_stop_pts: float = 40.0
    min_rr: float = 2.0
    target_mode: str = "liquidity"         # "liquidity" | "fixed"
    fixed_rr: float = 2.0
    target_buffer_ticks: int = 2
    fallback_fixed: bool = False           # if no pool >= min_rr, use fixed_rr
    breakeven_at_r: float | None = None    # e.g. 1.0 -> move stop to entry

    # daily limits
    max_trades_per_day: int = 2
    max_losses_per_day: int = 2
    stop_after_win: bool = True

    # day filters (overnight = Asia+London combined range, points)
    min_overnight_range: float | None = 50.0
    max_overnight_range: float | None = 300.0
    news_block_before_min: int = 2
    news_block_after_min: int = 5

    # sizing
    sizing: str = "fixed"                  # "fixed" | "risk"
    contracts: int = 1
    risk_dollars: float = 500.0


# --------------------------------------------------------------------------
# Data
# --------------------------------------------------------------------------
def load_csv(path: str, tz: str = NY) -> pd.DataFrame:
    """Load 1m OHLC CSV. Needs a timestamp column (timestamp/datetime/date/time)
    plus open, high, low, close. Naive timestamps are interpreted in `tz`."""
    df = pd.read_csv(path)
    df.columns = [c.strip().lower() for c in df.columns]
    ts_col = next((c for c in ("timestamp", "datetime", "date", "time", "ts")
                   if c in df.columns), None)
    if ts_col is None:
        raise ValueError(f"No timestamp column found in {list(df.columns)}")
    ts = pd.to_datetime(df[ts_col], utc=False)
    if ts.dt.tz is None:
        ts = ts.dt.tz_localize(tz, ambiguous="infer", nonexistent="shift_forward")
    df.index = ts.dt.tz_convert(NY)
    missing = {"open", "high", "low", "close"} - set(df.columns)
    if missing:
        raise ValueError(f"Missing columns: {missing}")
    df = df[["open", "high", "low", "close"]].astype(float)
    return df[~df.index.duplicated()].sort_index()


def load_news(path: str | None) -> list[pd.Timestamp]:
    """CSV with one datetime per row (column 'datetime' or first column), ET."""
    if not path:
        return []
    n = pd.read_csv(path)
    col = "datetime" if "datetime" in n.columns else n.columns[0]
    ts = pd.to_datetime(n[col])
    if ts.dt.tz is None:
        ts = ts.dt.tz_localize(NY)
    return list(ts.dt.tz_convert(NY))


def _at(d: date, t: time) -> pd.Timestamp:
    return pd.Timestamp(datetime.combine(d, t), tz=NY)


# --------------------------------------------------------------------------
# Per-direction engine (works in "long space")
# --------------------------------------------------------------------------
@dataclass
class Level:
    name: str
    price: float
    spent: bool = False


@dataclass
class Trade:
    date: str
    direction: str
    swept: str
    sweep_time: str
    signal_time: str
    entry_time: str
    exit_time: str
    entry: float
    stop: float
    target: float
    target_src: str
    exit: float
    exit_reason: str
    risk_pts: float
    planned_rr: float
    r: float
    contracts: int
    pnl_usd: float
    mss: bool


class Side:
    """Long-side logic on (possibly mirrored) arrays.

    For shorts, prices are multiplied by -1 so 'lows' are the original highs.
    """

    def __init__(self, direction: str, o, h, l, c, sweep_levels, target_levels, cfg: Config):
        self.dir = direction
        self.sgn = 1.0 if direction == "long" else -1.0
        s = self.sgn
        if s > 0:
            self.o, self.h, self.l, self.c = o, h, l, c
        else:
            self.o, self.h, self.l, self.c = -o, -l, -h, -c
        self.sweep_levels = sweep_levels      # list[Level] in side space
        self.target_levels = target_levels    # list[Level] in side space
        self.cfg = cfg
        n = len(self.h)
        rng = self.h - self.l
        self.avg_rng = pd.Series(rng).rolling(10, min_periods=3).mean().shift(1).to_numpy()
        # pivot highs (5-bar fractal) in side space
        ph = np.zeros(n, dtype=bool)
        for j in range(2, n - 2):
            hj = self.h[j]
            if hj > self.h[j - 1] and hj > self.h[j - 2] and hj >= self.h[j + 1] and hj >= self.h[j + 2]:
                ph[j] = True
        self.pivot_high = ph
        self.reset()

    def reset(self):
        self.armed = False
        self.sweep_idx = -1
        self.extreme_idx = -1
        self.extreme = math.inf
        self.swept_names: list[str] = []
        self.mss_level = None
        self.mss = False

    # -- helpers ----------------------------------------------------------
    def px(self, v: float) -> float:
        """side-space price -> real price"""
        return v * self.sgn

    def update_spent(self, i: int):
        for lv in self.target_levels:
            if not lv.spent and self.h[i] >= lv.price:
                lv.spent = True

    def _mss_level(self, i: int) -> float:
        """Most recent confirmed pivot high before the sweep extreme."""
        for j in range(self.extreme_idx - 1, 1, -1):
            if self.pivot_high[j] and j + 2 <= i:
                return self.h[j]
        lo = max(0, self.extreme_idx - 10)
        return float(np.max(self.h[lo:self.extreme_idx])) if self.extreme_idx > lo else self.h[self.extreme_idx]

    def targets(self, i: int, entry: float):
        """Candidate liquidity pools above entry as of bar i: (price, source)."""
        out = [(lv.price, lv.name) for lv in self.target_levels
               if not lv.spent and lv.price > entry]
        for j in range(2, i - 1):
            if self.pivot_high[j] and j + 2 <= i:
                hj = self.h[j]
                if hj > entry and np.max(self.h[j + 1:i + 1]) < hj:
                    out.append((hj, "swing"))
        return sorted(out)

    # -- signal step: returns an order dict or None -------------------------
    def step(self, i: int, can_signal: bool):
        cfg = self.cfg
        tk = cfg.tick
        # 1) sweep detection (always updates level state)
        new_sweep = []
        for lv in self.sweep_levels:
            if not lv.spent and self.l[i] <= lv.price - cfg.sweep_min_ticks * tk:
                lv.spent = True
                new_sweep.append(lv.name)
        if new_sweep and can_signal:
            if not self.armed:
                self.reset()
                self.armed = True
                self.sweep_idx = i
            self.swept_names += new_sweep
        if not self.armed:
            return None
        if not can_signal:
            self.reset()
            return None
        # 2) track extreme
        if self.l[i] < self.extreme:
            self.extreme = self.l[i]
            self.extreme_idx = i
            self.mss = False
            self.mss_level = None
        if i - self.sweep_idx > cfg.arm_timeout_bars:
            self.reset()
            return None
        if i <= self.extreme_idx:
            return None
        # 3) market structure shift
        if self.mss_level is None:
            self.mss_level = self._mss_level(i)
        if self.c[i] > self.mss_level:
            self.mss = True
        # 4) FVG formed after extreme: candles i-2, i-1, i
        if i - 2 < self.extreme_idx:
            return None
        if not (self.l[i] > self.h[i - 2]):
            return None
        mid = i - 1
        body = abs(self.c[mid] - self.o[mid])
        rng = self.h[mid] - self.l[mid]
        avg = self.avg_rng[mid]
        if rng <= 0 or self.c[mid] <= self.o[mid] or body < cfg.displacement_body_frac * rng:
            return None
        if not np.isnan(avg) and rng < cfg.displacement_range_mult * avg:
            return None
        if cfg.require_mss and not self.mss:
            return None
        gap_lo, gap_hi = self.h[i - 2], self.l[i]
        entry = gap_hi if cfg.entry_mode == "edge" else (gap_lo + gap_hi) / 2
        entry = round(entry / tk) * tk
        stop = self.extreme - cfg.stop_buffer_ticks * tk
        risk = entry - stop
        if risk < cfg.min_stop_pts or risk > cfg.max_stop_pts:
            return None  # keep armed: a later FVG may fit
        # 5) target
        if cfg.target_mode == "fixed":
            target, src = entry + cfg.fixed_rr * risk, f"fixed_{cfg.fixed_rr:g}R"
        else:
            target, src = None, None
            for p, name in self.targets(i, entry):
                t = p - cfg.target_buffer_ticks * tk
                if t - entry >= cfg.min_rr * risk:
                    target, src = t, name
                    break
            if target is None:
                if not cfg.fallback_fixed:
                    self.reset()
                    return None
                target, src = entry + cfg.fixed_rr * risk, f"fallback_{cfg.fixed_rr:g}R"
        order = dict(dir=self.dir, signal_idx=i, sweep_idx=self.sweep_idx,
                     swept="+".join(self.swept_names), entry=entry, stop=stop,
                     target=target, target_src=src, risk=risk, mss=self.mss)
        self.reset()
        return order


# --------------------------------------------------------------------------
# Day simulation
# --------------------------------------------------------------------------
def _range(df, a, b):
    seg = df.loc[(df.index >= a) & (df.index < b)]
    return (seg.high.max(), seg.low.min()) if len(seg) else (np.nan, np.nan)


def _touched_between(df, a, b, price, above: bool) -> bool:
    seg = df.loc[(df.index >= a) & (df.index < b)]
    if not len(seg):
        return False
    return bool(seg.high.max() >= price) if above else bool(seg.low.min() <= price)


def day_levels(df: pd.DataFrame, d: date, prev_rth: tuple | None, cfg: Config):
    """Return dict name -> (price, formed_at) for highs and lows."""
    asia_a = _at(d - timedelta(days=1), cfg.asia_start)
    asia_b = _at(d, cfg.asia_end)
    lon_a, lon_b = _at(d, cfg.london_start), _at(d, cfg.london_end)
    pm_a, pm_b = _at(d, cfg.premarket_start), _at(d, cfg.rth_start)
    ah, al = _range(df, asia_a, asia_b)
    lh, ll = _range(df, lon_a, lon_b)
    ph, pl = _range(df, pm_a, pm_b)
    highs, lows = {}, {}
    if not np.isnan(ah):
        highs["asia_high"], lows["asia_low"] = (ah, asia_b), (al, asia_b)
    if not np.isnan(lh):
        highs["london_high"], lows["london_low"] = (lh, lon_b), (ll, lon_b)
    if prev_rth is not None:
        highs["pdh"], lows["pdl"] = (prev_rth[0], prev_rth[2]), (prev_rth[1], prev_rth[2])
    if cfg.use_premarket_as_target and not np.isnan(ph):
        highs["pm_high"], lows["pm_low"] = (ph, pm_b), (pl, pm_b)
    overnight = None
    if not np.isnan(ah) and not np.isnan(lh):
        overnight = max(ah, lh) - min(al, ll)
    return highs, lows, overnight


def simulate_day(df, d, prev_rth, cfg: Config, news: list) -> tuple[list[Trade], dict]:
    info = {"date": str(d), "skipped": None}
    highs, lows, overnight = day_levels(df, d, prev_rth, cfg)
    info["overnight_range"] = overnight
    if overnight is None:
        info["skipped"] = "missing_session_data"
        return [], info
    if cfg.min_overnight_range is not None and overnight < cfg.min_overnight_range:
        info["skipped"] = "overnight_range_small"
        return [], info
    if cfg.max_overnight_range is not None and overnight > cfg.max_overnight_range:
        info["skipped"] = "overnight_range_large"
        return [], info

    ctx_a, win_a = _at(d, cfg.context_start), _at(d, cfg.window_start)
    flat = _at(d, cfg.flat_time)
    last_entry = _at(d, cfg.last_entry)
    day = df.loc[(df.index >= ctx_a) & (df.index <= flat)]
    if not len(day) or day.index[-1] < win_a:
        info["skipped"] = "no_rth_data"
        return [], info
    ts = day.index
    o, h, l, c = (day[k].to_numpy() for k in ("open", "high", "low", "close"))
    win_start = int(np.searchsorted(ts.values, win_a.to_datetime64()))

    def mk_levels(src: dict, is_high: bool, sgn: float, sweepable: bool):
        out = []
        for name, (p, formed) in src.items():
            if sweepable and not any(name.startswith(k) for k in cfg.sweep_levels):
                continue
            spent = _touched_between(df, formed, win_a, p, above=is_high)
            out.append(Level(name, p * sgn, spent))
        return out

    sides = {
        # long: sweep lows, target highs
        "long": Side("long", o, h, l, c,
                     [lv for lv in mk_levels(lows, False, 1.0, True) if not lv.name.startswith("pm")],
                     mk_levels(highs, True, 1.0, False), cfg),
        # short: sweep highs, target lows (mirrored)
        "short": Side("short", o, h, l, c,
                      [lv for lv in mk_levels(highs, True, -1.0, True) if not lv.name.startswith("pm")],
                      mk_levels(lows, False, -1.0, False), cfg),
    }

    def news_blocked(t: pd.Timestamp) -> bool:
        for nt in news:
            if nt - timedelta(minutes=cfg.news_block_before_min) <= t <= nt + timedelta(minutes=cfg.news_block_after_min):
                return True
        return False

    trades: list[Trade] = []
    state = {"wins": 0, "losses": 0}
    pending = None   # order dict + expiry
    pos = None       # open position dict

    def close(pos, s, i, exit_px, reason):
        pts = exit_px - pos["entry"]
        n = pos["contracts"]
        usd = pts * cfg.point_value * n - cfg.commission_rt * n
        trades.append(Trade(
            date=str(d), direction=pos["dir"], swept=pos["swept"],
            sweep_time=str(ts[pos["sweep_idx"]].time()),
            signal_time=str(ts[pos["signal_idx"]].time()),
            entry_time=str(pos["entry_time"].time()), exit_time=str(ts[i].time()),
            entry=s.px(pos["entry"]), stop=s.px(pos["orig_stop"]),
            target=s.px(pos["target"]), target_src=pos["target_src"],
            exit=s.px(exit_px), exit_reason=reason, risk_pts=pos["risk"],
            planned_rr=(pos["target"] - pos["entry"]) / pos["risk"],
            r=pts / pos["risk"], contracts=n, pnl_usd=usd, mss=pos["mss"]))
        state["wins" if usd > 0 else "losses"] += 1

    slip = cfg.slippage_ticks * cfg.tick
    for i in range(win_start, len(ts)):
        t = ts[i]
        busy = pos is not None or pending is not None
        for s in sides.values():
            s.update_spent(i)

        # ---- manage open position (side space) ----
        if pos is not None:
            s = sides[pos["dir"]]
            if t >= flat:
                close(pos, s, i, s.o[i] - slip, "time"); pos = None
            elif s.l[i] <= pos["stop"]:
                reason = "breakeven" if pos["stop"] >= pos["entry"] else "stop"
                close(pos, s, i, min(s.o[i], pos["stop"]) - slip, reason); pos = None
            elif s.h[i] >= pos["target"]:
                close(pos, s, i, pos["target"], "target"); pos = None
            elif cfg.breakeven_at_r and s.h[i] >= pos["entry"] + cfg.breakeven_at_r * pos["risk"]:
                pos["stop"] = max(pos["stop"], pos["entry"])

        # ---- pending limit order ----
        elif pending is not None:
            s = sides[pending["dir"]]
            if t > last_entry or i > pending["expiry"]:
                pending = None
            elif s.l[i] <= pending["entry"]:
                fill = min(s.o[i], pending["entry"])
                n = cfg.contracts
                if cfg.sizing == "risk":
                    n = int(cfg.risk_dollars // ((fill - pending["stop"]) * cfg.point_value))
                if n >= 1:
                    pos = dict(pending, entry=fill, orig_stop=pending["stop"],
                               risk=fill - pending["stop"], entry_time=t, contracts=n)
                    # conservative: the stop may trigger on the fill bar, the target may not
                    if s.l[i] <= pos["stop"]:
                        close(pos, s, i, pos["stop"] - slip, "stop"); pos = None
                pending = None
            elif s.h[i] >= pending["target"]:
                pending = None                       # ran to target without filling

        # ---- sweeps are always tracked; new signals only when flat ----
        done = (len(trades) >= cfg.max_trades_per_day
                or state["losses"] >= cfg.max_losses_per_day
                or (cfg.stop_after_win and state["wins"] > 0))
        can_signal = (not busy and pos is None and pending is None and not done
                      and t <= last_entry and not news_blocked(t))
        for s in sides.values():
            order = s.step(i, can_signal)
            if order and pending is None:
                order["expiry"] = i + cfg.entry_timeout_bars
                pending = order
                can_signal = False
                for other in sides.values():
                    if other is not s:
                        other.reset()

    if pos is not None:  # data ended before flat time
        s = sides[pos["dir"]]
        close(pos, s, len(ts) - 1, s.c[-1] - slip, "eod")
    info["trades"] = len(trades)
    return trades, info


# --------------------------------------------------------------------------
# Runner & stats
# --------------------------------------------------------------------------
def run(df: pd.DataFrame, cfg: Config, news: list | None = None):
    news = news or []
    trades, infos = [], []
    days = sorted({ts.date() for ts in df.index})
    prev_rth = None
    for d in days:
        rth = df.loc[(df.index >= _at(d, cfg.rth_start)) & (df.index < _at(d, cfg.rth_end))]
        if d.weekday() < 5 and len(rth):
            t, info = simulate_day(df, d, prev_rth, cfg, news)
            trades += t
            infos.append(info)
        if len(rth):
            prev_rth = (rth.high.max(), rth.low.min(), _at(d, cfg.rth_end))
    tdf = pd.DataFrame([dataclasses.asdict(t) for t in trades])
    return tdf, pd.DataFrame(infos)


def summarize(tdf: pd.DataFrame, infos: pd.DataFrame | None = None) -> dict:
    if tdf.empty:
        return {"trades": 0}
    r = tdf["r"]
    usd = tdf["pnl_usd"]
    eq_r = r.cumsum()
    dd_r = (eq_r - eq_r.cummax()).min()
    eq = usd.cumsum()
    dd = (eq - eq.cummax()).min()
    gross_win = usd[usd > 0].sum()
    gross_loss = -usd[usd <= 0].sum()
    out = {
        "trades": int(len(tdf)),
        "days_traded": int(tdf["date"].nunique()),
        "win_rate": round(float((usd > 0).mean()), 3),
        "avg_win_r": round(float(r[usd > 0].mean()), 2) if (usd > 0).any() else 0.0,
        "avg_loss_r": round(float(r[usd <= 0].mean()), 2) if (usd <= 0).any() else 0.0,
        "expectancy_r": round(float(r.mean()), 3),
        "total_r": round(float(r.sum()), 2),
        "profit_factor": round(float(gross_win / gross_loss), 2) if gross_loss > 0 else math.inf,
        "net_usd": round(float(usd.sum()), 2),
        "max_drawdown_r": round(float(dd_r), 2),
        "max_drawdown_usd": round(float(dd), 2),
        "avg_risk_pts": round(float(tdf["risk_pts"].mean()), 2),
        "exit_reasons": tdf["exit_reason"].value_counts().to_dict(),
        "by_direction": tdf.groupby("direction")["r"].agg(["count", "mean", "sum"]).round(3).to_dict("index"),
        "by_level_swept": tdf.groupby("swept")["r"].agg(["count", "mean", "sum"]).round(3).to_dict("index"),
        "by_target": tdf.groupby("target_src")["r"].agg(["count", "mean", "sum"]).round(3).to_dict("index"),
    }
    if infos is not None and len(infos):
        out["days_scanned"] = int(len(infos))
        out["days_skipped"] = infos["skipped"].value_counts().to_dict()
    return out


def _parse_time(s: str) -> time:
    return datetime.strptime(s, "%H:%M").time()


def main(argv=None):
    p = argparse.ArgumentParser(description="Backtest the Session Sweep + 1m FVG strategy")
    p.add_argument("csv", help="1-minute OHLC CSV (timestamp, open, high, low, close)")
    p.add_argument("--tz", default=NY, help="timezone of naive timestamps (default New York)")
    p.add_argument("--instrument", choices=["NQ", "MNQ", "ES", "MES"], default="NQ")
    p.add_argument("--entry", choices=["edge", "mid"], default="edge")
    p.add_argument("--target", choices=["liquidity", "fixed"], default="liquidity")
    p.add_argument("--min-rr", type=float, default=2.0)
    p.add_argument("--fixed-rr", type=float, default=2.0)
    p.add_argument("--fallback-fixed", action="store_true")
    p.add_argument("--no-mss", action="store_true", help="don't require market structure shift")
    p.add_argument("--window", default="09:30-11:30", help="entry window ET, e.g. 09:30-10:30")
    p.add_argument("--flat", default="12:00")
    p.add_argument("--max-stop", type=float, default=None, help="default: 40 (NQ) / 10 (ES)")
    p.add_argument("--min-stop", type=float, default=None, help="default: 5 (NQ) / 1.5 (ES)")
    p.add_argument("--breakeven-r", type=float, default=None)
    p.add_argument("--levels", default="asia,london,pd", help="sweepable levels: asia,london,pd")
    p.add_argument("--no-range-filter", action="store_true")
    p.add_argument("--sizing", choices=["fixed", "risk"], default="fixed")
    p.add_argument("--contracts", type=int, default=1)
    p.add_argument("--risk-dollars", type=float, default=500.0)
    p.add_argument("--news", help="CSV of high-impact news datetimes (ET)")
    p.add_argument("--out", default="trades.csv", help="where to write the trade log")
    a = p.parse_args(argv)

    inst = {"NQ": (0.25, 20.0, 4.5, 40, 5), "MNQ": (0.25, 2.0, 1.5, 40, 5),
            "ES": (0.25, 50.0, 4.5, 10, 1.5), "MES": (0.25, 5.0, 1.5, 10, 1.5)}[a.instrument]
    w0, w1 = a.window.split("-")
    cfg = Config(
        tick=inst[0], point_value=inst[1], commission_rt=inst[2],
        window_start=_parse_time(w0), last_entry=_parse_time(w1), flat_time=_parse_time(a.flat),
        entry_mode=a.entry, target_mode=a.target, min_rr=a.min_rr, fixed_rr=a.fixed_rr,
        fallback_fixed=a.fallback_fixed, require_mss=not a.no_mss,
        max_stop_pts=a.max_stop if a.max_stop is not None else inst[3],
        min_stop_pts=a.min_stop if a.min_stop is not None else inst[4],
        breakeven_at_r=a.breakeven_r, sweep_levels=tuple(a.levels.split(",")),
        sizing=a.sizing, contracts=a.contracts, risk_dollars=a.risk_dollars,
    )
    if a.no_range_filter or a.instrument in ("ES", "MES"):
        cfg.min_overnight_range = cfg.max_overnight_range = None

    df = load_csv(a.csv, a.tz)
    tdf, infos = run(df, cfg, load_news(a.news))
    stats = summarize(tdf, infos)
    print(json.dumps(stats, indent=2, default=str))
    if not tdf.empty:
        tdf.to_csv(a.out, index=False)
        print(f"\nTrade log written to {a.out}", file=sys.stderr)


if __name__ == "__main__":
    main()
