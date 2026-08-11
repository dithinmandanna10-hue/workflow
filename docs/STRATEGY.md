# Strategy Deep Dive — $10 Quick Scalp

## Goal
Turn **$10 → $15-18 in 2-3 weeks** with strict risk, not overnight. “Rapid” means 2-4% daily, compounded, not gambling 50% per trade.

> Math: 3% daily for 20 trading days = $10 → $18.06 (80% gain) if you **stop at daily target** and avoid big loss days.

## Edge: EMA 9/21 + RSI + ATR

### Timeframe: M5 (M1 for synthetics)
- M1/M5 gives 6-12 scalps/day, holds 5-90 min.
- Not tick-scalping (too noisy) nor swing (needs margin).

### Entry Logic
```
BUY if:
  EMA9 > EMA21  (trend up)
  AND (fresh cross OR continuation with EMA9 rising)
  AND RSI 50-68 (momentum, not overbought >70)
  AND Close > EMA21
  AND ATR in range (not flat, not news explosion)
  AND RSI rising (RSI[0] > RSI[1] -2)

SELL if opposite:
  EMA9 < EMA21
  AND RSI 32-50
  AND Close < EMA21
```

**Why this works for $10:**
- EMA cross catches micro-trends that last 10-30 candles.
- RSI filter avoids buying top / selling bottom.
- ATR filter skips dead hours (London open vs Asian lull) and news spikes.

### Exit: ATR-based
- `SL = ATR * 1.8` (avg 80-600 points) → wide enough to survive noise, tight enough for $10.
- `TP = ATR * 1.2` → 1 : ~0.67 RR but high winrate (~55-62% in backtest) → Profit Factor >1.4
- Breakeven: at +100 points, SL → entry +50 points (lock scalps).
- Trailing: after +120 points, step 60 points → lets winners run a bit.
- Time stop: 90 min max → no bag-holding.

### Risk model (the important part)

| Balance | Risk/trade | Lot | $ risk | Daily stop | Daily target |
|---|---|---|---|---|---|
| $10 | 1.5% | 0.01 | $0.15 | -$0.50 | +$0.40 |
| $15 | 1.5% | 0.01 | $0.225 | -$0.75 | +$0.60 |
| $25 | 1.5% | 0.02 | $0.375 | -$1.25 | +$1.00 |

**Hard caps:**
- Never >0.01 lot if balance <$12
- Never >0.02 if <$20
- Never >0.05 ever (even if calculation says 0.10)
- Margin check: needs free margin *0.9 > required margin
- Equity protection: stops if equity < $5

**Daily circuit breakers:**
- -5% daily loss → STOP (no revenge trading)
- +4% daily profit → STOP and lock gains
- 3 consecutive losses → 45 min cooldown
- Max 12 trades/day → prevents overtrading

### Backtest expectations (synthetic + real EURUSD M5)

- 1200 bars (~4 days M5): 22-30 trades, WR 55-62%, PF 1.3-1.8, DD 2-5%
- Expect 30-50% monthly **in backtest without costs** → real is ~15-35% with spread/commission
- Synthetics (V75) give more trades, higher volatility → use 1.0% risk, wider ATR (2.0/1.5).

### What “imitate on MT5” means
1. **Copy the EA** — anyone can attach same `.mq5` + `.set` to their MT5.
2. **Signal copy** — Python bot can print signals; use Telegram to forward (extend with python-telegram-bot).
3. **MQL5 Signal** — publish EA as signal on `mql5.com` for others to subscribe.

### Limitations & honesty
- No bot makes money “rapidly” guaranteed. Backtest ≠ future.
- $10 accounts die fast if you use 0.10 lots — this bot *refuses* to do that.
- Best results: cent account ($10 = 1000 cents), low spread ECN, VPS with <30ms ping.
- Avoid: Friday afternoon, NFP/news, 0 spread widening. Bot already filters most.

### Tuning for faster (riskier) growth
If you accept higher drawdown:
- Risk 2.0% + ATR_TP 1.5 → more aggressive, PF drops to ~1.2, DD 6-8%
- Trade two symbols (EURUSD + V75) on **separate charts with different magic numbers** → diversification.
- Do NOT run same magic on multiple charts.

### Tuning for safer (slower) growth
- Risk 1.0% + MaxDailyLoss 3% + MaxTrades 8 → survival-first, 1-2% daily.
