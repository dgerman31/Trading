# Trading: Session Sweep + 1m FVG Strategy

A complete, testable day-trading strategy for NQ/MNQ futures, built from the
[@doctradesnq Instagram reel](docs/source-transcript.md):

> Wake up at 9am New York time, mark the Asia and London highs/lows, wait for
> one to get swept, drop to the 1-minute, take the fair value gap reversal,
> stop at the swing, target the next draw on liquidity.

| File | Contents |
|---|---|
| [`STRATEGY.md`](STRATEGY.md) | **The full playbook:** definitions, daily routine, entry/stop/target rules, setup grading, filters, risk & sizing, checklists, journal, validation plan |
| [`tradingview/session_sweep_fvg.pine`](tradingview/session_sweep_fvg.pine) | TradingView Pine v5 strategy: plots levels, marks sweeps & FVGs, places orders in the Strategy Tester, fires alerts |
| [`backtest/`](backtest/README.md) | Python backtester for 1-minute CSV data + tests |
| [`docs/source-transcript.md`](docs/source-transcript.md) | Transcript of the original reel |

**Not financial advice.** Backtest and paper-trade before risking money.
