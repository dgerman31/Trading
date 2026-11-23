# Session Liquidity Sweep + 1m FVG Reversal (NQ)

A complete, rule-based day-trading plan built from the core idea in the
[@doctradesnq reel](docs/source-transcript.md):

> Mark the Asia and London highs/lows → wait for New York to sweep one →
> drop to the 1-minute → enter the fair value gap on the reversal →
> stop at the swing → target the next draw on liquidity.

> **Disclaimer:** This is an educational trading plan, not financial advice.
> Futures are leveraged and you can lose more than you expect. Paper-trade and
> backtest it before risking real money. The reel's "this makes you a lot of
> money" claim is unverified marketing; your own results are the only proof.

---

## 1. Overview

| Item | Spec |
|---|---|
| Instrument | NQ (E-mini Nasdaq-100) or **MNQ** (Micro, 1/10 size; start here) |
| Also works on | ES/MES, YM, GC; any liquid market with clear session ranges |
| Style | Intraday reversal: liquidity sweep → displacement → FVG entry |
| Bias timeframe | 15m / 5m (context and draw on liquidity) |
| Execution timeframe | **1m** |
| Session | New York AM: **09:30–11:30 ET** (killzone), prep from 09:00 ET |
| Trades/day | Max **2**. Stop after **1 win** or **2 losses** |
| Target R:R | Minimum **1:2**; target is the next liquidity pool |
| Holding time | Typically 5–60 minutes; always flat by 12:00 ET (hard flat 15:55) |

**Why it works (the thesis):** Session highs/lows sit above/below obvious
stop-loss clusters and breakout orders ("liquidity pools"). Large participants
push price through those levels to fill size, then reverse. A sweep followed by
a strong opposite move that leaves an FVG (imbalance) shows that the sweep
filled the orders and price is now moving toward the *other* side's liquidity.

---

## 2. Key definitions

All times are **New York (America/New_York)** and include daylight saving.

| Term | Definition |
|---|---|
| **Asia range** | High and low from **20:00–00:00 ET** (prior evening → midnight) |
| **London range** | High and low from **02:00–05:00 ET** |
| **PDH / PDL** | Prior RTH day's high / low (09:30–16:00) |
| **Pre-market range** | 08:00–09:30 high/low (optional extra pool) |
| **Liquidity pool / draw on liquidity (DOL)** | A level where stops rest: session highs/lows, PDH/PDL, equal highs/lows, untested swing points |
| **Sweep** | Price trades **beyond** a level (by ≥ 1 tick) and then trades back inside it. A sweep is a wick through the level, not acceptance beyond it |
| **Swing high / low** | A 1m candle whose high (low) is higher (lower) than the 2 candles either side (5-bar fractal) |
| **Displacement** | 1–3 large-bodied candles that move away from the sweep with conviction (body ≥ 60% of range, range ≥ the average of the last 10 bars) |
| **Market structure shift (MSS)** | After the sweep, a candle **closes** beyond the most recent opposite swing point (e.g. after a low sweep, closes above the last 1m swing high) |
| **Bullish FVG** | 3-candle pattern where candle 3's **low** > candle 1's **high**. The gap is `[high₁, low₃]` |
| **Bearish FVG** | Candle 3's **high** < candle 1's **low**. The gap is `[high₃, low₁]` |

---

## 3. Daily routine

### 08:45–09:15: Prep (the "wake up at 9am" part)
1. **Check the economic calendar** (ForexFactory, Econoday). Note any
   high-impact releases (CPI, NFP, FOMC, PCE, GDP, ISM, 10:00 data).
2. **Mark levels** on the 15m chart with horizontal lines:
   - Asia high / low
   - London high / low
   - PDH / PDL
   - Obvious equal highs/lows and untested 15m swing points
3. **Note what's already taken.** If London already swept the Asia high, that
   pool is spent; the London high is now the bigger draw above.
4. **Form a bias** (optional but improves results):
   - Where is price relative to the overnight range? Opening near the top
     favors a sweep of the highs → short; near the bottom → long.
   - Which side has the most unswept liquidity on the 15m/1h? That's the
     likely **draw** for the day.
5. Write the plan in the journal: *"If price sweeps the London low and shifts,
   I look for longs to the Asia high (DOL)."*

### 09:30–11:30: Execution window
- Do nothing until a marked level is swept **during the window** (sweeps that
  happened before 09:30 count only as already-taken liquidity).
- When a sweep happens, switch to the **1m** and run the entry checklist.

### 11:30–12:00: Wind down
- No new entries after 11:30. Manage open trades; flat by 12:00 unless the
  target is within reach and the stop is at breakeven.

### Post-session (10 minutes)
- Screenshot every trade (entry, sweep, FVG, target) and fill in the journal.

---

## 4. Entry rules

### Long setup (sweep of a LOW)
1. **Sweep:** In the NY window, price trades below the Asia low, London low,
   or PDL by ≥ 1 tick.
2. **Reaction:** On the 1m, price reverses with **displacement** up.
3. **Structure:** A 1m candle **closes above the most recent swing high**
   formed before/during the sweep (MSS). *(Strongly recommended; the
   aggressive variant skips it.)*
4. **FVG:** The displacement leaves a **bullish FVG** that formed after the
   sweep's low.
5. **Room to target:** The next draw on liquidity above is at least
   **2× the risk** away (see §6). If not, **no trade**.
6. **Entry:** Limit buy at the **top of the FVG** (`low₃`). Conservative
   alternative: the **FVG midpoint** (consequent encroachment), with a better
   R:R but fewer fills.
7. **Expiry:** Cancel the order if it is not filled within **15 minutes**, if
   price hits the target first, or if price trades below the stop first.

### Short setup (sweep of a HIGH)
Mirror image: sweep above Asia high / London high / PDH → bearish
displacement → close below the last swing low → **bearish FVG** → limit sell at
the **bottom of the FVG** (`high₃`) → stop above the sweep high.

### Grade the setup (A+ / A / B)
| Factor | Points |
|---|---|
| Swept level is London or Asia high/low (vs minor level) | +1 |
| Two pools swept at once (e.g. Asia low + London low) | +1 |
| MSS confirmed with a close | +1 |
| Direction agrees with 15m/1h bias & DOL | +1 |
| Clean displacement (≥2 large candles) | +1 |
| Inside 09:30–10:30 (best hour) | +1 |

**5–6 = A+** (full size) · **3–4 = A** (half size) · **≤2 = B** (skip)

---

## 5. Stop-loss rules
- **Long:** 2 ticks below the **swing low made by the sweep** (the sweep's
  extreme). **Short:** 2 ticks above the sweep's swing high.
- **Max stop:** 40 NQ points (≈ $800/NQ, $80/MNQ). If the swing is farther,
  skip or wait for a deeper entry; don't size down to force it.
- **Min stop:** 5 points. Tighter stops get wicked out by noise.
- The stop is **never moved further away**.

---

## 6. Targets (draw on liquidity)

The reel's refinement: *"instead of just targeting a 1:2 RR, use market
structure, target draws on liquidity."*

**Target selection (long; mirror for shorts):**
1. List every liquidity pool **above** entry: 1m/5m swing highs, the London
   high, the Asia high, pre-market high, PDH, equal highs.
2. Pick the **nearest pool that gives ≥ 2R**. Set the take-profit **2 ticks
   in front of it** (stops cluster just beyond, so price often tags it and
   reverses).
3. If no pool gives ≥ 2R, **skip the trade**. (Backtester option:
   fall back to a fixed 2R.)
4. **Most common target:** the opposite side of the range that was swept.
   Sweep the London low, target the London high or Asia high.

**Optional scaling (once consistent):**
- TP1: 50% at the first internal swing (~1.5–2R), move the stop to breakeven.
- TP2: the remainder at the main draw on liquidity.

---

## 7. Trade management
| Event | Action |
|---|---|
| Price reaches +1R | Optional: move stop to breakeven **only after** a new 1m swing forms in your favor (avoid premature BE) |
| An opposing FVG forms and price closes through your FVG | Exit early; the setup is invalidated |
| 11:30 ET with trade open | Tighten stop to the last 1m swing |
| 12:00 ET | Close the trade |
| Major news in < 2 minutes | Close or don't enter |

---

## 8. Do-not-trade filters
- **High-impact news:** no entries from 2 min before to 5 min after any red-folder
  release. **FOMC days:** don't trade before 14:00; consider sitting out.
- **CPI/NFP mornings:** the 08:30 move often runs the levels before the open.
  Re-mark: the swept pools are gone.
- **Range too small:** if the Asia+London combined range < 50 NQ pts, the
  pools are too close together for 2R. Skip.
- **Range too large:** if the overnight range > 300 pts (trend day), sweeps
  tend to fail. Trade with the trend only.
- **Holiday / half days**, the week between Christmas and New Year, and
  contract rollover week (the second week of Mar/Jun/Sep/Dec) unless you trade the new contract.
- **No reversal:** a sweep followed by price **closing and holding** beyond the
  level is a breakout, not a sweep. No trade.

---

## 9. Risk management & position sizing

**Contract values:** NQ = **$20/pt** ($5/tick) · MNQ = **$2/pt** ($0.50/tick)

```
contracts = floor( risk_$ / (stop_points × $_per_point) )
```

Example: $500 risk, 20-pt stop on MNQ → 500 / (20 × 2) = **12 MNQ**.
On NQ → 500 / (20 × 20) = 1.25 → **1 NQ** (actual risk $400).

| Rule | Personal account | Prop firm (eval/funded) |
|---|---|---|
| Risk per trade | 0.5–1% of account | ≤ 20–25% of the daily loss limit |
| Max daily loss | 2% (or 2 losses) | Half of the firm's daily limit |
| Max weekly loss | 5% → stop for the week | 50% of trailing drawdown → reassess |
| After 3 losing days in a row | Cut size in half until a green day | Same |
| Scale up | Only after 40+ trades with positive expectancy | Same |

**Expectancy check:** at 2R targets you break even at a **33% win rate**
(before costs). Aim for ≥ 40%.

```
expectancy (R) = win% × avg_win_R − loss% × avg_loss_R
```

**Prop-firm notes** (the reel advertises one): check the firm's rules on
trailing drawdown (intraday vs EOD), consistency rules (max % of profit from one
day), news trading bans and contract limits *before* trading. A 2-loss daily
stop protects trailing-drawdown accounts.

---

## 10. Checklists

### Pre-trade (all must be ✅)
- [ ] Inside 09:30–11:30 ET, no news within 2 min
- [ ] A **marked** level (Asia/London/PDH/PDL) was swept by ≥ 1 tick
- [ ] Displacement away from the sweep
- [ ] MSS: 1m close beyond the last opposite swing
- [ ] FVG formed after the sweep extreme
- [ ] Stop = sweep extreme ± 2 ticks, between 5 and 40 pts
- [ ] Next DOL ≥ 2R away; TP set 2 ticks in front of it
- [ ] Size calculated; under daily loss limit; < 2 trades today
- [ ] Setup grade A or A+

### Post-trade
- [ ] Screenshot (15m context + 1m execution)
- [ ] Journal entry filled in (§11)
- [ ] Rule followed? If not, write which one and why

---

## 11. Journal template
Copy into a spreadsheet, one row per trade:

| Date | Day | Level swept | Direction | Grade | Sweep time | Entry | Stop | Target (DOL) | Stop pts | Planned R | Result R | $ P/L | MSS? | News? | Followed rules? | Notes / screenshot |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|

Review weekly: win rate and avg R **by level swept**, **by grade**, **by
hour**, and **by day of week**. Cut what doesn't work.

---

## 12. Backtesting & validation plan
1. **Manual replay (20–30 days):** TradingView Bar Replay on NQ 1m. Mark
   levels each morning, play forward, log every valid setup, including ones
   you'd have skipped.
2. **Automated backtest:** run [`backtest/`](backtest/README.md) on 1m NQ
   data (≥ 1 year, ideally 2–3). Compare the variants:
   - entry at the FVG edge vs the midpoint
   - MSS required vs not
   - DOL targets vs fixed 2R (the reel's original vs refined version)
   - 09:30–10:30 vs 09:30–11:30
3. **Accept the strategy only if:** ≥ 100 trades, profit factor > 1.3,
   expectancy > +0.2R after costs, max drawdown < 10R, and results hold in
   both halves of the data (no single month carrying it).
4. **Forward test:** 4 weeks on sim/MNQ at minimum size before scaling.

---

## 13. Common mistakes
- Entering on the sweep itself (catching a knife) instead of waiting for
  displacement + FVG.
- Treating a breakout as a sweep. Wait for price to close back inside.
- Taking FVGs that formed *before* the sweep.
- Targeting a fixed 2R straight into an opposing liquidity pool or
  higher-timeframe FVG.
- Re-entering after the daily stop ("revenge trading").
- Marking levels in the wrong time zone. Use New York time.

---

## 14. Tools in this repo
| Path | What it does |
|---|---|
| [`tradingview/session_sweep_fvg.pine`](tradingview/session_sweep_fvg.pine) | Pine v5 strategy: plots Asia/London levels, flags sweeps and FVG entries, backtests in TradingView's Strategy Tester, sends alerts |
| [`backtest/`](backtest/README.md) | Python backtester for 1m OHLC CSV data, with every rule above as a parameter |
| [`docs/source-transcript.md`](docs/source-transcript.md) | Full transcript of the source reel |
