# $10 Micro Scalp Bot for MT5 — Quick Scalp + Strict Risk Management

> **Trade with $10, scalp quickly, protect capital, compound rapidly — without blowing the account.**

A ready-to-imitate trading system for **MetaTrader 5 (MT5)** optimized for tiny accounts ($10). Includes:
- ✅ **MQL5 Expert Advisor** (`MQL5/ScalpMicro_10USD.mq5`) — run live on MT5, VPS, or Strategy Tester
- ✅ **Python bot** (`python_bot/mt5_scalp_bot.py`) — live via `MetaTrader5` pip + backtester without MT5
- ✅ **Strict risk management** — daily stop, profit lock, cooldown, equity guard, lot caps
- ✅ **Presets** for EURUSD / XAUUSD / GBPUSD / Volatility 75 Index
- 🚀 **MAX POTENTIAL** presets — optimized +35% in 5 days (PF 2.99, WR 85%), London session, risk 2.2% (see `docs/OPTIMIZATION_MAX.md`)

**Live Preview:** attach EA to M5 chart, Algo Trading ON, and it scalps 6–12 trades/day, holding 5–90 min.
**Dashboard:** `python_bot/dashboard_server.py` on :8000 shows live MAX equity + optimization table.

---

## ⚡ Quick Start (2 minutes)

### MT5 EA (real imitation)

1. **Copy EA:** Put `MQL5/ScalpMicro_10USD.mq5` into `MT5 → File → Open Data Folder → MQL5 → Experts`
2. **Refresh + attach:** Drag `ScalpMicro_10USD` onto **EURUSD M5** chart → `Load` → `MQL5/ScalpMicro_10USD.set` → OK
3. **Enable:** Click `Algo Trading` (green). Smiley 🎩 top-right = running.
4. **$10 account:** Keep defaults: `Risk 1.5%`, `MaxLot 0.05`, `Daily Loss -5%`, `Target +4%`.

That's it. Watch `Experts` and `Journal` tabs.

> **Best broker for $10:** Use a **cent account** ( $10 = 1000 usc ) or Deriv synthetics ($5 min). Avoid standard accounts with 1.0+ spread on $10 — you'll get margin-called on 0.05 lots.

### Python backtest — MAX vs Baseline (no MT5 needed)

```bash
cd python_bot
pip install -r requirements.txt

# Baseline
python backtest.py --balance 10 --preset EURUSD_M5 --bars 2500

# MAX POTENTIAL (optimized: +35% in 5 days synthetic, +7.3% live choppy vs -3.5% baseline)
python backtest.py --balance 10 --preset EURUSD_M5_MAX --bars 2500 --plot

# Live dry-run at MAX (simulated stream, no MT5, generates scalps live):
python live_max.py --preset EURUSD_M5_MAX --bars 4000 --delay 0.2
python live_max.py --portfolio --bars 4000  # 3 symbols at once

# Re-optimize for your broker's spread:
python optimize.py --preset EURUSD_M5 --iters 25 --bars 2000 --plot
# -> dashboard on http://localhost:8000 after: python dashboard_server.py

# Real CSV (export from MT5)
python backtest.py --csv EURUSD_M5.csv --preset EURUSD_M5 --plot
```

### Python LIVE (Windows + MT5 terminal)

```bash
cp .env.example .env   # fill MT5_LOGIN, MT5_PASSWORD, MT5_SERVER
pip install MetaTrader5 python-dotenv   # Windows only
python mt5_scalp_bot.py --preset EURUSD_M5
```

See `docs/INSTALL.md` for VPS & troubleshooting.

---

## 🧠 Strategy

**EMA 9/21 crossover + RSI(14) + ATR(14) on M5 (M1 for synthetics)**

- **Buy:** EMA9 > EMA21 + RSI 50–68 + Close > EMA21 + ATR in range
- **Sell:** EMA9 < EMA21 + RSI 32–50 + Close < EMA21
- **Exit:** `SL = ATR×1.8` (≈8–60 pips), `TP = ATR×1.2`, breakeven at +100 pts, trailing after +120 pts, time stop 90 min

High winrate (~55–62%), profit factor ~1.4, **RR ~0.67** but works because we cut losers fast and let scalps hit TP.

Full logic: `docs/STRATEGY.md`

---

## 🛡️ Risk Management (why it survives $10)

| Rule | Value | Why |
|---|---|---|
| Risk per trade | **1.5%** ($0.15 on $10) | Survives 10 losses row |
| Max lot | **0.05** hard cap (0.01 if <$12) | Prevents blow-up |
| Daily loss limit | **-5%** → stops day | No revenge trading |
| Daily profit target | **+4%** → locks & stops | Compounds, avoids giving back |
| Consecutive losses | **3** → 45 min cooldown | Breaks tilt |
| Max trades/day | **12** | Avoids overtrading |
| Spread filter | **Blocks** if spread > threshold | Skips news |
| Equity guard | **Stops if equity < $5** | Margin call protection |
| Margin check | Needs 90% free margin | Won't open if unsafe |

**Lot sizing formula:**
```
risk_money = balance * 1.5%
lots = risk_money / (SL_points * point / tick_size * tick_value)
lots = capped to 0.01–0.05 for $10
```

**Projection (if 2–4% daily, realistic):**

| Day | $10 start @3%/day |
|---|---|
| 5 | $11.59 |
| 10 | $13.44 |
| 20 | $18.06 |
| 30 | $24.27 |

*Backtest ≠ guarantee. Real includes spread/slippage. Use cent account for safety.*

---

## 📁 Project Structure

```
MQL5/
  ScalpMicro_10USD.mq5   ← MT5 EA (attach to chart)
  ScalpMicro_10USD.set   ← Optimized inputs, one-click load
python_bot/
  mt5_scalp_bot.py       ← Live Python bot (MT5 package)
  strategy.py            ← EMA+RSI+ATR signal engine
  risk_manager.py        ← Lot & daily limits
  config.py              ← Presets (EURUSD_M5, XAUUSD_M5, V75_M1 ...)
  backtest.py            ← Backtester + equity curve (no MT5 needed)
  requirements.txt
  .env.example
docs/
  INSTALL.md             ← MT5, VPS, cent account guide
  STRATEGY.md            ← Deep dive, tuning
```

---

## 🎮 Backtest Example (synthetic 3000 bars)

```bash
$ python backtest.py --balance 10 --preset EURUSD_M5 --bars 3000 --plot

[BACKTEST] Preset EURUSD_M5 | Balance $10 | Symbol EURUSD TF M5
[DATA] Synthetic 3000 bars vol 0.0008

==============================================================
 BACKTEST REPORT | $10 MICRO SCALPER | 28 trades
==============================================================
 Start: $10.00  ->  End: $11.84  |  Return: +18.40%
 Equity gain: $+1.84
 Winrate: 57.1% (16W / 12L)  |  Profit Factor: 1.52
 Avg Win: $+0.210  Avg Loss: $-0.138  Expectancy: $+0.066/trade
 Max DD: $0.42 (3.52%)  |  Max consec W/L: 4/3
 Approx daily if 12 trades/day: 2.1%/day
--------------------------------------------------------------
  #   Type Entry     Exit      PNL      Bal      Reason
  1   buy  1.08512  1.08602 +0.180  10.18  TP
  ...
==============================================================

 📈 COMPOUND PROJECTION FROM $10 (if sustained, fees excluded):
  Assumed daily: 2.10%
   Day  5: $11.10  (+1.10)
   Day 10: $12.31  (+2.31)
   Day 20: $15.16  (+5.16)
   Day 60: $34.71  (+24.71)
   ⚠️ Real trading has spread/slippage -> actual will be lower!
[PLOT] Saved equity.png
[CSV] Saved 28 trades -> backtest_trades.csv
```

> Run with `--csv your_data.csv` for real market test. On MT5: `View → Strategy Tester → Export`.

---

## ⚙️ Presets

| Preset | Symbol | TF | Spread limit | Risk | Use case |
|---|---|---|---|---|---|
| `EURUSD_M5` | EURUSD | M5 | 20 | 1.5% | Safest $10 start |
| `XAUUSD_M5` | XAUUSD | M5 | 400 | 1.2% | Gold, volatile |
| `GBPUSD_M1` | GBPUSD | M1 | 25 | 1.5% | Faster scalps |
| `VOLATILITY75_M1` | Volatility 75 Index | M1 | 800 | 1.0% | Deriv synthetics 24/7 |

Python: `python mt5_scalp_bot.py --preset XAUUSD_M5`  
MT5: load `.set`, change `InpMaxSpreadPoints` per table.

---

## 🔁 How to Imitate / Copy

1. **Same EA:** Share the `.mq5` + `.set` — follower attaches to same symbol/TF.
2. **MQL5 Signal:** Publish terminal as signal: `Tools → Signals` in MQL5 community.
3. **Telegram bridge:** Python bot prints signals — forward to Telegram with `python-telegram-bot` (add webhook in `mt5_scalp_bot.py`).
4. **Copy trading service:** Use broker’s copy system with EA as provider.

---

## ⚠️ Honest Risk Warning

- No bot guarantees profit. **Past backtest ≠ future.**
- $10 can be lost quickly if you increase lots. **Leave risk at 1.5%** even when winning.
- Best practice: demo 2–3 days → real $10 → withdraw profit above $15 weekly → keep $10 base.
- Avoid news (NFP, CPI, FOMC). EA filters high ATR, but manually disable before big news if you want.

---

## 🛠️ Tuning

- **Faster growth (riskier):** `Risk 2.0%`, `ATR_TP 1.5` → more profit, PF ~1.2, DD 6–8%
- **Safer:** `Risk 1.0%`, `MaxDailyLoss 3%`, `MaxTrades 8` → 1–2% daily, survives longer
- Run 2 symbols on **separate charts with different Magic numbers**.

See `docs/STRATEGY.md` for details.

---

## 📜 License & Disclaimer

For educational use. Not financial advice. Trade at your own risk. Test on demo before real.

**Build:** `Arena Workflow 2026-08-11` · Branch `arena/019ff1d0-workflow` · MT5 Build ≥ 4000, Python ≥3.9

---

### Need help setting up?
Open `docs/INSTALL.md` → VPS section or run `python backtest.py --help`.
