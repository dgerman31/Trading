"""Hand-built scenario tests for the backtester.  Run: python -m pytest -q  (or python test_engine.py)

Scenario (Tue 2025-03-04, NQ):
  Asia 20990-21010, London 20970-21030, prior RTH 20900-21100.
  09:31-09:32 rally to 21012 (sweeps Asia high, makes a 1m swing high).
  09:35 sweeps the London low (20970) down to 20960.
  09:37-09:38 bullish displacement, closes above 21012 (MSS) and leaves an FVG 20972-20990.
  09:39 retraces to 20990 -> filled. Then rallies to the PDH (21100).
Expected: long, entry 20990, stop 20959.5, target 21099.5 (PDH - 2 ticks), exit at target.
"""
import pandas as pd

from session_sweep_fvg import Config, run

BASE = 21000.0


def _flat(start, end):
    ts = pd.date_range(start, end, freq="1min", inclusive="left", tz="America/New_York")
    return [(t, BASE, BASE + 3, BASE - 3, BASE) for t in ts]


def _set(rows, when, o, h, l, c):
    t = pd.Timestamp(when, tz="America/New_York")
    for k, r in enumerate(rows):
        if r[0] == t:
            rows[k] = (t, o, h, l, c)
            return
    raise KeyError(when)


def scenario() -> pd.DataFrame:
    rows = _flat("2025-03-03 07:00", "2025-03-04 09:30")
    _set(rows, "2025-03-03 10:00", BASE, 21100, BASE - 1, BASE)        # PDH
    _set(rows, "2025-03-03 11:00", BASE, BASE + 1, 20900, BASE)        # PDL
    _set(rows, "2025-03-03 21:00", BASE, 21010, BASE - 1, BASE)        # Asia high
    _set(rows, "2025-03-03 22:00", BASE, BASE + 1, 20990, BASE)        # Asia low
    _set(rows, "2025-03-04 03:00", BASE, 21030, BASE - 1, BASE)        # London high
    _set(rows, "2025-03-04 04:00", BASE, BASE + 1, 20970, BASE)        # London low
    ny = [
        (21000, 21004, 20998, 21000),  # 09:30
        (21000, 21010, 20999, 21008),  # 09:31
        (21008, 21012, 21005, 21006),  # 09:32 swing high
        (21006, 21007, 20990, 20992),  # 09:33
        (20992, 20994, 20975, 20978),  # 09:34
        (20978, 20980, 20960, 20965),  # 09:35 sweep London low
        (20965, 20972, 20962, 20970),  # 09:36 FVG candle 1
        (20970, 20995, 20969, 20994),  # 09:37 displacement
        (20994, 21015, 20990, 21014),  # 09:38 FVG candle 3, MSS close
        (21014, 21016, 20989, 20995),  # 09:39 retrace -> fill 20990
    ]
    p = 20995.0
    for k in range(10, 40):  # grind up to 21100+
        o = p
        p = min(p + 4.0, 21104.0)
        ny.append((o, p + 1, o - 1, p))
    t0 = pd.Timestamp("2025-03-04 09:30", tz="America/New_York")
    for k, (o, h, l, c) in enumerate(ny):
        rows.append((t0 + pd.Timedelta(minutes=k), o, h, l, c))
    rows += _flat("2025-03-04 10:10", "2025-03-04 12:30")
    df = pd.DataFrame(rows, columns=["ts", "open", "high", "low", "close"]).set_index("ts")
    return df


def mirror(df: pd.DataFrame) -> pd.DataFrame:
    m = 2 * BASE
    return pd.DataFrame({"open": m - df.open, "high": m - df.low,
                         "low": m - df.high, "close": m - df.close}, index=df.index)


def _only_test_day(tdf):
    if tdf.empty:
        return tdf
    return tdf[tdf.date == "2025-03-04"].reset_index(drop=True)


def test_long_liquidity_target():
    tdf, _ = run(scenario(), Config())
    tdf = _only_test_day(tdf)
    assert len(tdf) == 1, tdf
    t = tdf.iloc[0]
    assert t.direction == "long"
    assert t.swept == "london_low"
    assert t.entry == 20990 and t.stop == 20959.5
    assert t.target == 21099.5 and t.target_src == "pdh"
    assert t.exit_reason == "target"
    assert abs(t.r - (21099.5 - 20990) / 30.5) < 1e-9
    assert t.mss


def test_short_is_mirror_image():
    tdf, _ = run(mirror(scenario()), Config())
    t = _only_test_day(tdf).iloc[0]
    assert t.direction == "short"
    assert t.swept == "london_high"
    assert t.entry == 2 * BASE - 20990 and t.target == 2 * BASE - 21099.5
    assert t.exit_reason == "target"
    assert abs(t.r - (21099.5 - 20990) / 30.5) < 1e-9


def test_fixed_2r_target():
    tdf, _ = run(scenario(), Config(target_mode="fixed", fixed_rr=2.0))
    t = _only_test_day(tdf).iloc[0]
    assert t.target == 20990 + 2 * 30.5 and t.exit_reason == "target"
    assert abs(t.r - 2.0) < 1e-9


def test_mid_entry_not_filled():
    # FVG 20972-20990 -> midpoint 20981; the 09:39 retrace only reaches 20989,
    # so the limit order never fills and no trade is taken.
    tdf, _ = run(scenario(), Config(entry_mode="mid"))
    assert len(_only_test_day(tdf)) == 0


def test_no_trade_when_stop_too_wide():
    tdf, _ = run(scenario(), Config(max_stop_pts=20))
    assert len(_only_test_day(tdf)) == 0


def test_range_filter():
    tdf, infos = run(scenario(), Config(min_overnight_range=100))
    assert len(_only_test_day(tdf)) == 0
    assert infos.set_index("date").loc["2025-03-04", "skipped"] == "overnight_range_small"


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
