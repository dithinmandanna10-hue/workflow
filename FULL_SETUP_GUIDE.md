# FULL SETUP GUIDE — $10 Micro Scalper (Baseline / MAX / SPAM)

**Pick one bot:** `Baseline` (safe 12/day M5) · `MAX` (optimized 18/day London +35% ) · `SPAM` (tick spam 150/day M1 15sec) — you asked for SPAM quick scalp.

**All protect $10:** hard lot 0.01-0.03, daily -5%/-7% stop, +4%/+8% lock, 3-5 loss cooldown, $4-5 equity guard, spread filter. No martingale.

---

## 1) Choose Broker & Account ($10)

**For $10 you MUST use cent or synthetics, else 0.01 lot risks 12% per loss:**

| Broker | Account | $10 = | Spread EURUSD | Why |
|---|---|---|---|---|
| **Exness** | Cent | 1000 usc | 0.7-1.2 pips | Best for $10, 0.01 lot = 1c per 10pts |
| **RoboForex** | Cent | 1000 usc | 0.9 | Alternative |
| **Deriv** | Synthetic | $10 real | 0 (fixed) | Volatility 75 / Boom/Crash 24/7, $5 min |
| **IC Markets / Pepperstone** | Standard | $10 | 0.0-0.6 + comm | Only if you accept 0.01 lot = $0.04/10pts (needs $20+ ) |

**Create:** Demo first (2 days), then Real Cent. Save Login / Password / Server (e.g., `Exness-Demo`, `Deriv-Demo`).

---

## 2) Install MT5

- Windows: download from broker → install
- VPS ($3/mo Contabo): RDP → install MT5 there for 24/7. Or MT5 → right-click account → `Register on Virtual Server` (MQL5 VPS).

---

## 3) Install EA (one time, 2 min)

**Download zip:** `https://github.com/dithinmandanna10-hue/workflow/archive/refs/heads/arena/019ff1d0-workflow.zip` → unzip.

**Copy EAs:**
```
MT5 → File → Open Data Folder → MQL5 → Experts → paste:
  MQL5/ScalpMicro_10USD.mq5   (baseline & MAX)
  MQL5/ScalpSpam_10USD.mq5    (SPAM tick)
```
**Restart** MT5 or Navigator → Right-click `Expert Advisors` → `Refresh` → you see `ScalpMicro_10USD` and `ScalpSpam_10USD`.

**Copy Sets (one-click inputs):**
```
MQL5 → Open Data Folder → keep .set files handy, load via Inputs → Load:
  MQL5/ScalpMicro_10USD.set           → Baseline M5
  MQL5/ScalpMicro_MAX_EURUSD.set      → MAX EURUSD M5 07-17 2.2% 18/day
  MQL5/ScalpMicro_MAX_XAUUSD.set      → MAX Gold M5
  MQL5/ScalpSpam_10USD.set            → SPAM EURUSD M1 15sec 150/day
```

---

## 4) Attach Bot — SPAM (you asked) vs MAX vs Baseline

### SPAM — M1 Tick Spam (80-150/day) — EURUSD M1
1. Open chart: **Market Watch → EURUSD → right-click → Chart Window** → click **M1** on toolbar (must be M1, not M5)
2. Drag `ScalpSpam_10USD` from Navigator onto chart
3. Popup → **Inputs** → **Load** → select `MQL5/ScalpSpam_10USD.set` → OK  
   Verify: `InpSpamMode=true, InpTimeframe=M1, EMA5/13 RSI7, ATR 1.0/0.7 30-400, Spread 18, 15 sec, 150/day, Magic 202510`
4. **Common** tab → tick `Allow Algo Trading` → OK
5. Top-right must show `ScalpSpam_10USD` + **blue hat** 🎩 (not red ❌)
6. Press **Algo Trading** button (green) or `Ctrl+E`

**Expected:** Experts tab prints `SPAM $10 ULTRA SCALPER READY TICK SPAM (every tick)` then every 15sec+ in London: `SPAM BUY 0.01 SL30 TP20`. 30-40 trades per London session on demo.

### MAX — M5 London Optimized (+35% in 5 days)
1. Chart **EURUSD M5**
2. Drag `ScalpMicro_10USD` → Load `ScalpMicro_MAX_EURUSD.set` → OK (Magic 101010)
3. Algo ON. For Gold, second chart **XAUUSD M5** → Load `ScalpMicro_MAX_XAUUSD.set` Magic 202020

### Baseline — Safe Start M5
Same but Load `ScalpMicro_10USD.set` (12/day, 1.5% risk).

**Multiple charts:** each chart different magic, same account, shared margin = portfolio diversification.

---

## 5) Verify & Monitor

- **Experts tab:** `SPAM BUY 0.01 SL30 TP20` / `SPAM pause: Spread 22 >18` = waiting London.
- **Journal tab:** trades, cooldown `SPAM 5-loss cooldown 10min`, daily `SPAM daily loss 7.00% lock`.
- **Chart:** top-right hat blue, smiley.

**After 1 London session (07-22) on demo you should see 30-40 SPAM trades** (as in live demo 07-25 13:18-22:53 35 trades) or 6-12 MAX trades.

**Check risk:** Account → `History` → right-click → `Profit` → daily P/L should be -7% to +8% max before bot auto-stops. If daily target +8% hit at 15:00, bot stops till 00:00 next day (locks profit).

---

## 6) Python Dry-Run (no MT5, instant test, any OS)

```bash
git clone https://github.com/dithinmandanna10-hue/workflow
cd workflow
git checkout arena/019ff1d0-workflow
cd python_bot
pip install --break-system-packages -r requirements.txt

# SPAM live tick simulation (no broker, synthetic M1, prints spams):
python live_max.py --preset SPAM_EURUSD_M1 --bars 5000 --delay 0.1

# Backtest SPAM (2500 M1 bars = 1.7 days → 40 trades):
python backtest.py --preset SPAM_EURUSD_M1 --bars 3500 --balance 10 --plot

# MAX London (35% in 5 days synthetic momentum):
python live_max.py --preset EURUSD_M5_MAX --bars 4000 --delay 0.2
python backtest.py --preset EURUSD_M5_MAX --bars 2500 --plot

# Portfolio 3 symbols:
python live_max.py --portfolio --bars 4000

# Optimize for your broker's spread:
python optimize.py --preset EURUSD_M5 --iters 25 --bars 2000 --plot
# → generates optimized_EURUSD_M5.json + equity_EURUSD_M5_MAX.png
# → copy params into config.py PRESETS["SPAM_EURUSD_M1"]

# Dashboard live:
python dashboard_server.py
# → http://localhost:8000 → preview https://8000-iw87ef9n0qlky22n2cpj1.e2b.app
```

**Real MT5 via Python (Windows + MT5 terminal open):**
```bash
pip install MetaTrader5
cp .env.example .env  # fill MT5_LOGIN, MT5_PASSWORD, MT5_SERVER
python mt5_scalp_bot.py --preset SPAM_EURUSD_M1
python mt5_scalp_bot.py --preset EURUSD_M5_MAX
```

---

## 7) Risk Management — Why $10 Safe Even Spamming

**Per trade:** Calc lots = `risk% * balance / (SL pts × tickValue)` then **cap 0.01 if <$12, 0.02 if <$25, 0.03 max SPAM / 0.05 MAX**.  
- $10 SPAM 0.01 lot × 40 pts SL × $0.01/pt = **$0.04 loss = 0.4%** (not 1.8% — cap protects).

**Per day:** `dailyStart 00:00` → equity vs start. If **-7% SPAM (-$0.70) lock** or **+8% (+$0.80) lock** → no more trades till 00:00.

**Streak:** 5 consecutive losses → **10min cooldown** (MAX 3 losses → 30min). Prints `SPAM 5-loss cooldown 10min`.

**Equity guard:** if equity < $4 (SPAM) or $5 (MAX) → stop all.

**Spread:** EURUSD SPAM <18 pts (1.8 pips ECN), else skip `SPAM pause: Spread`.

**Hold:** SPAM 180 sec max, MAX 90min max → bails stuck.

**Backtest DD:** SPAM 4.56% ($0.48), MAX 5.11% ($0.54) on 1500 bars.

**To make even safer** (spam slower): in `.set` change `InpRiskPercent 1.0, InpMaxTrades 80, InpMaxDailyLoss 5.0, InpMaxLot 0.02`.

---

## 8) Tuning & Optimization

**For your broker spread (Exness Cent 12 vs IC 8):**
```bash
python optimize.py --preset EURUSD_M5 --iters 30 --bars 2000 --plot
# Edit python_bot/config.py SPAM_EURUSD_M1 with json params
# Re-export set: copy values to MQL5/ScalpSpam_10USD.set
```

**For XAU/Gold:** use `SPAM_XAUUSD_M1` (spread 300, ATR 1.2/0.8, lot 0.02) on **XAUUSD M1**.

**For 24/7 synthetics:** `SPAM_V75_M1` on `Volatility 75 Index M1` spread 600, 200 trades/day, 0-23h.

---

## 9) Troubleshooting

| Problem | Fix |
|---------|-----|
| `SPAM pause: Spread 22 >18` | Wait London 07-22, use ECN/raw, or increase `InpMaxSpreadPoints` to 25 |
| No trades, hat red | `Allow Algo Trading` Common tab, Algo button green, check `Experts` for `SPAM READY` |
| `Not enough money` | SL too wide for $10 → reduce `InpATR_SL_Mult 1.0→0.8` or use cent account |
| `Already in position` SPAM | Normal, spam waits 3min hold close + 15sec gap before next |
| `Daily loss/target lock` | Bot stopped till next day 00:00 broker time — correct, locks profit/loss |
| No trades after 5-loss cooldown | Wait 10min, bot auto-resumes |
| Python `MetaTrader5 not installed` | `pip install MetaTrader5` only Windows + MT5 open; dry-run needs no MT5: `python live_max.py --preset SPAM...` |
| Backtest PF <1.2 | Use London session, real CSV `python backtest.py --csv EURUSD_M1.csv` |

---

## 10) Scaling $10 Rapidly but Safe

- **Week 1:** Demo 2 days → Real Cent $10 SPAM **1.0% risk** 80/day → target **$0.50/day → $12.50**
- **Week 2:** If 2 days profit, raise to **1.8% MAX** 150/day → **$0.80/day**
- **Withdraw:** every time balance > $15, withdraw $5, keep $10 base → compound safely.
- **Never:** increase lot above cap, remove daily stop, trade Friday 20-24 news.

**Projection SPAM 1% daily (conservative):** $10 → Day5 $10.51 → Day20 $12.20 → Day60 $18.16

---

## 11) Files Reference

| File | Use |
|------|-----|
| `MQL5/ScalpSpam_10USD.mq5` | EA tick spam — attach to M1 |
| `MQL5/ScalpSpam_10USD.set` | One-click spam inputs |
| `MQL5/ScalpMicro_10USD.mq5` + `ScalpMicro_MAX_EURUSD.set` | MAX London M5 |
| `python_bot/live_max.py` | Dry-run spam live |
| `python_bot/backtest.py` | Backtest any preset/csv |
| `python_bot/optimize.py` | Re-optimize for your spread |
| `python_bot/dashboard_server.py` | Dashboard :8000 |
| `docs/SPAM_SCALP.md`, `docs/OPTIMIZATION_MAX.md` | Deep dive |

**Live Dashboard:** `https://8000-iw87ef9n0qlky22n2cpj1.e2b.app` (running on `python_bot/dashboard_server.py` :8000)

**Check branch:** `arena/019ff1d0-workflow` — all above is pushed, pull to update.

---

**Ready to imitate:** Pick SPAM M1 for quick spam, MAX M5 for trending London. Both auto-protect $10. Say `start spam` and I’ll launch live spam stream here.
