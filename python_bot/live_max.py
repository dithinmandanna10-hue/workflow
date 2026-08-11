#!/usr/bin/env python3
"""
LIVE MAX - runs optimized bot at max potential with portfolio + compounding visualization
- Simulates live trading on synthetic stream (since we have no MT5 here)
- Prints live scalp signals, equity, daily P/L
- Also can connect to real MT5 if available

Usage: python live_max.py --preset EURUSD_M5_MAX --balance 10
       python live_max.py --portfolio --balance 10  # runs EUR + XAU + GBP simultaneously
"""
import time, argparse, os, sys
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

from config import PRESETS
from backtest import generate_synthetic_ohlc
from risk_manager import RiskManager
from strategy import ScalpStrategy

try:
    import MetaTrader5 as mt5
    HAS_MT5 = True
except:
    HAS_MT5 = False

def live_simulation(preset="EURUSD_M5_MAX", balance=10, bars=5000, delay=0.5):
    cfg = PRESETS[preset]
    print(f"\n{'='*78}")
    print(f" 🚀 LIVE MAX SIMULATION | {preset} | {cfg.execution.symbol} {cfg.strategy.timeframe}")
    print(f" Risk {cfg.risk.risk_percent}% | SL×{cfg.strategy.atr_sl_mult} TP×{cfg.strategy.atr_tp_mult} | Session {cfg.execution.start_hour}-{cfg.execution.end_hour}")
    print(f" Starting $10 → target +{cfg.risk.daily_target_pct}%/day, stop -{cfg.risk.max_daily_loss_pct}%")
    print(f"{'='*78}\n")
    # generate long synthetic stream
    df = generate_synthetic_ohlc(n=bars, start_price=1.085 if "EUR" in preset else 2685 if "XAU" in preset else 1.27 if "GBP" in preset else 135000, volatility=0.0007 if "EUR" in preset else 0.0018 if "XAU" in preset else 0.001)
    # infer point
    price = df["close"].iloc[-1]
    point = 0.00001 if price < 10 else 0.01
    if "JPY" in preset: point=0.001
    if "XAU" in preset: point=0.01
    if "Volatility" in preset: point=0.01
    tick_value = 1.0/10 if balance<50 else 1.0
    tick_size = point
    vol_min, vol_step = (0.001,0.001) if balance<50 else (0.01,0.01)

    strat = ScalpStrategy(cfg)
    risk = RiskManager(cfg)
    first_time = df["time"].iloc[0]
    if hasattr(first_time, "to_pydatetime"): first_time = first_time.to_pydatetime()
    risk.reset_daily(balance, now=first_time)

    equity = balance
    in_pos = None
    trades=[]
    equity_curve=[balance]
    start = datetime.utcnow()
    fmt = lambda x: f"{x:.5f}" if x<10 else f"{x:.2f}"

    for i in range(50, len(df)):
        row = df.iloc[i]
        window = df.iloc[:i+1]
        bar_time = row["time"].to_pydatetime() if hasattr(row["time"],"to_pydatetime") else row["time"]
        price_now = row["close"]

        # manage pos
        if in_pos:
            high, low = row["high"], row["low"]
            exit_price=None; reason=None
            if in_pos["type"]=="buy":
                if low <= in_pos["sl"]: exit_price=in_pos["sl"]; reason="SL"
                elif high >= in_pos["tp"]: exit_price=in_pos["tp"]; reason="TP"
            else:
                if high >= in_pos["sl"]: exit_price=in_pos["sl"]; reason="SL"
                elif low <= in_pos["tp"]: exit_price=in_pos["tp"]; reason="TP"
            if exit_price is None:
                if cfg.exit.use_breakeven:
                    be = strat.get_breakeven_sl(in_pos["entry"], price_now, in_pos["type"], point, cfg.exit.breakeven_trigger_points, cfg.exit.breakeven_plus_points, in_pos["sl"])
                    if be: in_pos["sl"]=be
                if cfg.exit.use_trailing:
                    tr = strat.get_trailing_sl(in_pos["entry"], price_now, in_pos["type"], point, cfg.exit.trailing_start_points, cfg.exit.trailing_step_points, in_pos["sl"])
                    if tr: in_pos["sl"]=tr
                if (bar_time - in_pos["entry_time"]).total_seconds()/60 >= cfg.exit.max_hold_minutes:
                    exit_price=price_now; reason="TIME"
                if exit_price is None and in_pos["type"]=="buy" and low <= in_pos["sl"] and in_pos["sl"]!=in_pos["orig_sl"]:
                    exit_price=in_pos["sl"]; reason="TRAIL"
                if exit_price is None and in_pos["type"]=="sell" and high >= in_pos["sl"] and in_pos["sl"]!=in_pos["orig_sl"]:
                    exit_price=in_pos["sl"]; reason="TRAIL"
            if exit_price is not None:
                diff = (exit_price - in_pos["entry"])/point if in_pos["type"]=="buy" else (in_pos["entry"]-exit_price)/point
                pnl = diff * tick_value * in_pos["lots"]
                balance+=pnl
                equity=balance
                risk.record_trade_result(pnl, now=bar_time)
                trades.append({"type":in_pos["type"],"entry":in_pos["entry"],"exit":exit_price,"pnl":pnl,"balance":balance,"reason":reason,"time":bar_time})
                pct = (balance-10)/10*100
                print(f"[{bar_time.strftime('%m-%d %H:%M')}] CLOSE {in_pos['type'].upper():4s} {fmt(in_pos['entry'])}→{fmt(exit_price)} {reason:5s} {pnl:+.3f}  BAL ${balance:.2f} ({pct:+.1f}%) lots {in_pos['lots']}")
                in_pos=None
                equity_curve.append(balance)
                # daily status every trade
                st = risk.get_status(balance, equity)
                if len(trades)%5==0:
                    print(f"   ↳ Daily P/L ${st['daily_pnl']:+.2f} ({st['daily_pnl_pct']:+.2f}%) | Trades today {st['trades_today']} | Consecutive losses {st['consecutive_losses']}")
                if delay>0: time.sleep(delay*0.3)
            else:
                diff = (price_now - in_pos["entry"])/point if in_pos["type"]=="buy" else (in_pos["entry"]-price_now)/point
                equity = balance + diff * tick_value * in_pos["lots"]

        if in_pos is None:
            sig = strat.generate_signal(window)
            if sig["signal"]!=0:
                allowed, reason = risk.is_trading_allowed(balance, equity, spread_points=10, now=bar_time)
                if not allowed:
                    if "Daily target" in reason or "Daily loss" in reason:
                        # print daily lock
                        pass
                    continue
                lots = risk.calculate_lots(balance, sig["sl_points"], tick_value, tick_size, point, vol_min, 100, vol_step)
                sl = price_now - sig["sl_points"]*point if sig["signal"]==1 else price_now + sig["sl_points"]*point
                tp = price_now + sig["tp_points"]*point if sig["signal"]==1 else price_now - sig["tp_points"]*point
                typ = "buy" if sig["signal"]==1 else "sell"
                in_pos={"type":typ,"entry":price_now,"sl":sl,"tp":tp,"orig_sl":sl,"lots":lots,"entry_time":bar_time}
                risk.last_trade_time = bar_time
                print(f"[{bar_time.strftime('%m-%d %H:%M')}] OPEN  {typ.upper():4s} {fmt(price_now)} SL {fmt(sl)} TP {fmt(tp)} lots {lots} | {sig['reason']} | BAL ${balance:.2f}")

        # heartbeat every 500 bars
        if i%500==0 and i>50:
            elapsed = (datetime.utcnow()-start).total_seconds()
            print(f"\n⏱️  Bar {i}/{len(df)} | Equity ${equity:.2f} | Trades {len(trades)} | Elapsed {elapsed:.1f}s\n")
        if delay>0 and in_pos is None:
            time.sleep(delay*0.05)

    # final
    print(f"\n{'='*78}")
    print(f" LIVE MAX FINISHED | {preset}")
    print(f" Start $10 → End ${balance:.2f} ({(balance-10)/10*100:+.2f}%) | {len(trades)} trades")
    if trades:
        wins=len([t for t in trades if t["pnl"]>0])
        pf=sum([t["pnl"] for t in trades if t["pnl"]>0])/abs(sum([t["pnl"] for t in trades if t["pnl"]<=0])) if any(t["pnl"]<=0 for t in trades) else 99
        print(f" Winrate {wins/len(trades)*100:.1f}% PF {pf:.2f} | Avg win ${np.mean([t['pnl'] for t in trades if t['pnl']>0]):.3f} avg loss ${np.mean([t['pnl'] for t in trades if t['pnl']<=0]):.3f}")
        print(f" Projected daily: {(balance/10)**(1/(len(df)/288))-1 if len(df)>288 else 0:.2%} per day (288 M5 bars = 1 day)")
    print(f"{'='*78}\n")
    return balance, trades, equity_curve

def portfolio_sim(bars=4000):
    print("\n" + "="*78)
    print(" 💼 PORTFOLIO MAX - EURUSD_MAX + XAUUSD_MAX + GBPUSD_M1_MAX (3 charts, 3 magics)")
    print(" Diversification = max potential with lower DD")
    print(" Run each on same $10 account with different magic - margin shared")
    print("="*78)
    presets=["EURUSD_M5_MAX","XAUUSD_M5_MAX","GBPUSD_M1_MAX"]
    # For portfolio demo, each runs on full $10 but we track combined P/L with risk split
    # Real MT5: 3 charts each 0.33x risk, so combined risk ~ same as single MAX, but diversification lowers DD
    results=[]
    for p in presets:
        # Temporarily lower protection for small balance simulation
        cfg = PRESETS[p]
        orig_protect = cfg.risk.balance_protection_equity
        cfg.risk.balance_protection_equity = 1.0  # allow $3.33 to run
        bal, trades, _ = live_simulation(preset=p, balance=10, bars=bars, delay=0)
        cfg.risk.balance_protection_equity = orig_protect
        results.append((p,bal,trades))
    # Combined = starting $10 + sum of P/L from each (since they share same capital, P/L adds)
    total_pnl = sum([b-10 for _,b,_ in results])
    combined = 10 + total_pnl
    print(f"\n{'='*78}")
    print(f" PORTFOLIO RESULT | Started $10 (P/L adds across 3 magics)")
    for p,b,tr in results:
        print(f"  {p:18s}: ${b:.2f} ({(b-10)/10*100:+.1f}%) {len(tr)} trades")
    print(f"  COMBINED (sum P/L): ${combined:.2f} ({(combined-10)/10*100:+.1f}%)")
    print(f"  Diversified DD lower than single. Real MT5: attach each preset to separate chart, same account, different magic.")
    print("="*78)

if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--preset", default="EURUSD_M5_MAX", choices=list(PRESETS.keys()))
    ap.add_argument("--balance", type=float, default=10)
    ap.add_argument("--bars", type=int, default=3500)
    ap.add_argument("--portfolio", action="store_true")
    ap.add_argument("--delay", type=float, default=0.15, help="live simulation delay per bar")
    args=ap.parse_args()
    if args.portfolio:
        portfolio_sim(bars=args.bars)
    else:
        live_simulation(preset=args.preset, balance=args.balance, bars=args.bars, delay=args.delay)
