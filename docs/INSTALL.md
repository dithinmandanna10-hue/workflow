# Installation Guide — $10 Micro Scalp Bot

## Option A: MT5 Expert Advisor (Recommended for live imitation/copy)

MT5 EA is the **real** bot that runs inside MetaTrader 5. Python bot is for testing/monitoring.

### 1. Get MT5
- Download MT5 from your broker:
  - Forex: Exness, IC Markets, Pepperstone, XM (cent/standard with $10 minimum)
  - Synthetic indices: Deriv (allows $5 deposit, Volatility 75, Boom/Crash)
- Install and log in with a **demo first**, then $10 real/cent account.

### 2. Install the EA
1. Open MT5 → `File → Open Data Folder`
2. Go to `MQL5 → Experts`
3. Copy `MQL5/ScalpMicro_10USD.mq5` there
4. Restart MT5 or right-click `Expert Advisors` → `Refresh`
5. The EA appears as `ScalpMicro_10USD`.

### 3. Attach to chart
1. Open chart: `EURUSD, M5` (best for $10 start) or `XAUUSD, M5` or `Volatility 75 Index, M1`
2. Drag `ScalpMicro_10USD` onto chart.
3. In dialog:
   - Check ✅ `Allow Algo Trading`, `Allow DLL imports` (not needed)
   - On `Inputs` tab: click `Load` → select `MQL5/ScalpMicro_10USD.set`
   - For $10: keep `InpRiskPercent=1.5`, `InpMaxLot=0.05`, `InpMaxDailyLossPct=5`, `InpDailyTargetPct=4`
4. Click OK. Smiley face / blue cap should appear top-right.

### 4. Enable Algo Trading
Press `Ctrl+E` or click `Algo Trading` button green.

### 5. Recommended symbols for $10

| Symbol | TF | Spread setting | Notes |
|---|---|---|---|
| **EURUSD** | M5 | 20 points | Safest for $10, low spread |
| **GBPUSD** | M1 | 25 | More trades, needs VPS |
| **XAUUSD (Gold)** | M5 | 400 | Volatile, set risk 1.2% |
| **Volatility 75 Index (Deriv)** | M1 | 800 | Best for small account scalps, 24/7 |
| **Boom/Crash 500/1000** | M1 | 500 | Synthetics, no spread spikes |

> **Cent account tip:** If broker offers cent account, your $10 = 1000 usc → EA auto-scales correctly. Best for beginners.

---

## Option B: Python Bot (backtest + optional live via MetaTrader5 package)

Works on **Windows only** for live trading (MetaTrader5 pip requires Windows + MT5 terminal). Linux/Mac can still backtest.

```bash
cd python_bot
pip install -r requirements.txt
# On Windows live:
pip install MetaTrader5 python-dotenv

cp .env.example .env
# edit .env with MT5_LOGIN, MT5_PASSWORD, MT5_SERVER

# Test signal without trading
python mt5_scalp_bot.py --preset EURUSD_M5 --dry-run --once

# Backtest $10 synthetic
python backtest.py --balance 10 --preset EURUSD_M5 --bars 3000 --plot

# Backtest real data (export CSV from MT5: File -> Open Data Folder -> ...)
python backtest.py --csv ../data/EURUSD_M5.csv --preset EURUSD_M5

# LIVE (Windows + MT5 open)
python mt5_scalp_bot.py --preset EURUSD_M5
# or custom
python mt5_scalp_bot.py --symbol XAUUSD --timeframe M5 --risk 1.2
```

---

## VPS (for 24/7)
- Cheap VPS: $3-6/mo (Contabo, ForexVPS). Install MT5 there, run EA nonstop.
- Alternative: use MetaQuotes VPS inside MT5: right-click account → `Register Virtual Server`.

## First Week Checklist for $10
- [ ] Demo 2-3 days, verify 10-15 trades, max DD <5%
- [ ] Switch to real $10, **do not increase lot** even if winning
- [ ] Daily target 4% = $0.40/day on $10 → lock and stop. Do NOT “let it run”
- [ ] If 3 losses in row, EA pauses 45 min automatically — leave it
- [ ] Weekly: withdraw profit above $15, keep base $10-15 to avoid blowing up
- [ ] Log: keep screenshot of MT5 Journal/Experts tab

## Common Fixes
- **“Spread too high”** → Normal during news. EA skips those bars (protects you).
- **“Not enough money”** → Your SL is too wide vs. $10. Reduce `InpATR_SL_Mult` from 1.8 → 1.5.
- **No trades** → Check `Algo Trading` green, EA smiley, correct TF (M5), allow live trading.
- **MT5 AutoTrading disabled after reboot** → Re-enable or use VPS.
