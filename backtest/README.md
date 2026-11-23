# Backtester

Runs the rules in [`../STRATEGY.md`](../STRATEGY.md) on 1-minute OHLC data.

## Install
```bash
pip install pandas numpy pytest
```

## Data
A CSV with a timestamp column (`timestamp`/`datetime`/`date`/`time`) and
`open,high,low,close`. Naive timestamps are read as New York time; pass
`--tz UTC` (etc.) if your file is in another zone. You need the overnight
Globex session (from 18:00 ET) so the Asia/London ranges exist.

Sources for NQ 1m history: your broker/platform export (NinjaTrader,
Tradovate, Sierra Chart, TradingView), Databento, FirstRate Data, Kibot.
Use **continuous, back-adjusted** front-month data.

## Run
```bash
python session_sweep_fvg.py nq_1m.csv                        # refined version: liquidity targets
python session_sweep_fvg.py nq_1m.csv --target fixed         # reel's original: fixed 1:2
python session_sweep_fvg.py nq_1m.csv --entry mid            # FVG midpoint entries
python session_sweep_fvg.py nq_1m.csv --no-mss               # aggressive: no structure shift needed
python session_sweep_fvg.py nq_1m.csv --window 09:30-10:30   # first hour only
python session_sweep_fvg.py nq_1m.csv --instrument MNQ --sizing risk --risk-dollars 250
python session_sweep_fvg.py nq_1m.csv --news news.csv        # block entries around news (CSV of ET datetimes)
python session_sweep_fvg.py --help                           # every option
```
It prints summary stats (win rate, expectancy in R, profit factor, drawdown,
breakdowns by direction / level swept / target type) and writes every trade to
`trades.csv`.

## Smoke test with fake data
```bash
python make_sample_data.py sample.csv --days 120
python session_sweep_fvg.py sample.csv --no-range-filter
```
The sample data is a random walk. Results on it say **nothing** about the
strategy; this only checks that the pipeline works.

## Tests
```bash
python -m pytest -q        # or: python test_engine.py
```
The tests build a hand-made NY session (Asia/London ranges, a London-low
sweep, displacement, MSS, FVG retrace) and check the exact entry, stop,
target, exit and R, plus the mirrored short and the filters.

## Modeling assumptions (conservative)
- Limit entries fill when price **touches** the price (no queue modeling).
- On the bar the order fills, only the stop can trigger, not the target.
- If a bar touches both stop and target, the **stop** is assumed first.
- Stops and time exits pay `slippage_ticks` (default 1); commission $4.50 RT per NQ.
- A level counts only if it wasn't traded through between its session's end
  and 09:30. Each level can be swept only once per day.
- Swing highs/lows use a 5-bar fractal, and are only used after confirmation (no look-ahead).
