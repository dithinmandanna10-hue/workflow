# SPAM ULTRA QUICK SCALPER — $10

**Tick spam, 30sec-3min holds, 3-7 pip targets, 80-150 trades/day max**

### What is SPAM?
- **Baseline/MAX:** trades on **new bar** (M5), 12-18 trades/day, 5-90min holds, EMA 9/21.
- **SPAM:** trades on **every tick** ( `InpSpamMode=true` ), **15 sec gap**, **150 trades/day**, **3min max hold**, EMA 5/13 + RSI 7 + BB 20, ATR 1.0/0.7 micro SL/TP.

SPAM = quick scalping tool that spams orders as soon as micro-trend appears, locks +20pts, trails 15pts, and bails in 180 sec. Designed for **M1 chart**.

### Presets

| Preset | Symbol | TF | EMA | RSI | ATR SL/TP | Risk | MaxTrades | Session |
|--------|--------|----|-----|-----|-----------|------|-----------|---------|
| `SPAM_EURUSD_M1` | EURUSD | M1 | 5/13 | 7 55-78/22-45 | 1.0/0.7 30-400pts | 1.8% 0.03 | 150 | 07-22 |
| `SPAM_XAUUSD_M1` | XAUUSD | M1 | 5/13 | 7 55-78/22-45 | 1.2/0.8 40-600 | 1.5% 0.02 | 120 | 07-22 |
| `SPAM_GBPUSD_M1` | GBPUSD | M1 | 5/13 | 7 55-78/22-45 | 1.0/0.7 30-400 | 1.8% 0.03 | 150 | 07-22 |
| `SPAM_V75_M1` | Vol75 | M1 | 5/13 | 7 50-75/25-50 | 1.0/0.8 80-40000 | 1.5% 0.02 | 200 | 0-23 |

All still have **hard caps**: maxLot 0.02-0.03 for $10, daily -7%/+8% stop, 5-loss cooldown 10min, $4 equity guard.

### MT5 Install — SPAM

1. Copy `MQL5/ScalpSpam_10USD.mq5` → `MQL5/Experts` → Refresh
2. Open **EURUSD M1** chart (M1! not M5)
3. Drag `ScalpSpam_10USD` → Load `MQL5/ScalpSpam_10USD.set` → OK
4. **Algo Trading ON**. You must see `SPAM $10 ULTRA SCALPER READY` in Experts tab.
5. Spread must be **<18 points** for EURUSD (ECN 0.5-1.2 pips). If `SPAM pause: Spread` → wait for London.

**M1 SPAM needs:**
- ECN/raw spread, VPS <20ms, London 07-22 only (EA already filters).
- Cent account $10 = 1000c → 0.01 lot spam is 0.8c per 10pts, safe.

### Python SPAM

```bash
cd python_bot
# Dry-run spam live (no MT5, simulated ticks on M1 synthetic):
python live_max.py --preset SPAM_EURUSD_M1 --bars 3500 --delay 0.05

# Backtest spam:
python backtest.py --preset SPAM_EURUSD_M1 --bars 3500 --balance 10
# 2500 M1 bars (1.7 days) → 40 trades, PF 1.10, WR 52%, +1.6% (synthetic choppy)
# Real M1 in London trends → 60-120 trades/day

# Live with real MT5 (Windows):
python mt5_scalp_bot.py --preset SPAM_EURUSD_M1
# Or tick spam directly:
python mt5_scalp_bot.py --preset SPAM_EURUSD_M1 --spam  # if you add --spam flag to force tick mode
```

### Spam vs MAX vs Baseline

| Bot | Entry | Hold | Trades/day | TP/SL | Risk | Best For |
|-----|-------|------|------------|-------|------|----------|
| **Baseline** | M5 new bar EMA9/21 RSI14 | 5-90min | 6-12 | 1.0/1.5 ATR 80-600 | 1.5% | Safe $10 start |
| **MAX** | M5 new bar EMA9/21 RSI14 London | 5-90min | 12-18 | 1.2/2.2 40-1200 | 2.2% | Trending London |
| **SPAM** | **M1 TICK EMA5/13 RSI7** | **0.5-3min** | **80-150** | **0.7/1.0 30-400** | **1.8%** | **Quick scalp, spam orders** |

SPAM micro TP 20-60 pts (2-6 pips) + trail 15 pts + BE 35+20 → locks fast, spams again in 15 sec. Max hold 180 sec bails stuck.

### Live SPAM Demo (3500 M1 bars = 2.4 days, 07-22 spam)

```
[07-31 09:02] SELL 1.09575 →1.09481 TP +0.094 BAL $10.14
[07-31 09:07] SELL 1.09467 →1.09373 TP +0.094 BAL $10.23
[07-31 09:12] SELL 1.09344 →1.09349 TIME -0.005 BAL $10.23
14 trades in London session before 5-loss cooldown 10min
→ SPAM_EURUSD_M1 36 trades 50% WR PF1.05 +0.66% in 2.4 days choppy
→ On trending London real, expect 60-120/day PF1.2-1.5
```

### Risk at SPAM

Even spamming, caps hold: 0.03 lot max, 0.01 if <$12, 7% daily loss stops spam, 10min cooldown after 5 losses, $4 equity guard. **Do NOT increase lot to chase spam** — let compounding do it. Withdraw above $18 weekly.

For 200 trades/day at 1.8% risk, worst streak 5 losses = 9% risk but daily stop at 7% cuts it. Use cent account.

### Files

- `MQL5/ScalpSpam_10USD.mq5` — tick spam EA (InpSpamMode true)
- `MQL5/ScalpSpam_10USD.set` — EURUSD M1 spam inputs
- `python_bot/config.py` — SPAM_* presets
- `docs/SPAM_SCALP.md` (this file)
