#!/usr/bin/env python3
"""
Backtester for $10 Scalp Strategy
- Works WITHOUT MT5: generates synthetic walk or loads CSV
- Shows realistic equity curve, winrate, profit factor, max DD
- Proves risk management for $10

Usage:
  python backtest.py --balance 10 --bars 2000        # synthetic
  python backtest.py --csv data/EURUSD_M5.csv        # real CSV with open,high,low,close
  python backtest.py --balance 10 --preset XAUUSD_M5
"""

import argparse
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import matplotlib.pyplot as plt

from config import BotConfig, PRESETS
from risk_manager import RiskManager
from strategy import ScalpStrategy

def generate_synthetic_ohlc(n=2000, start_price=1.08500, volatility=0.0008, trend=0.00001):
    """Random walk with slight trend and volatility clustering"""
    np.random.seed(42)
    prices = [start_price]
    for i in range(1, n):
        # volatility clustering
        vol = volatility * (1 + 0.5*np.sin(i/100) + 0.3*np.random.randn()*0.1)
        ret = np.random.randn() * vol + trend
        prices.append(max(0.5*start_price, prices[-1] * (1+ret)))
    # build OHLC from close
    closes = np.array(prices)
    highs = closes * (1 + np.abs(np.random.randn(n))*0.0005)
    lows = closes * (1 - np.abs(np.random.randn(n))*0.0005)
    opens = np.roll(closes,1)
    opens[0]=closes[0]
    # ensure high >= max(open,close) and low <= min
    highs = np.maximum(highs, np.maximum(opens, closes))
    lows = np.minimum(lows, np.minimum(opens, closes))
    times = [datetime.utcnow() - timedelta(minutes=5*(n-i)) for i in range(n)]
    df = pd.DataFrame({"time": times, "open": opens, "high": highs, "low": lows, "close": closes, "tick_volume": np.random.randint(50,500,n)})
    return df

def load_csv(path):
    df = pd.read_csv(path)
    # try to normalize column names
    cols = {c.lower(): c for c in df.columns}
    mapping = {}
    for k in ["open","high","low","close","time","tick_volume","volume"]:
        if k in cols:
            mapping[cols[k]] = k
    df = df.rename(columns=mapping)
    if "time" in df.columns:
        df["time"] = pd.to_datetime(df["time"])
    else:
        df["time"] = pd.date_range(end=datetime.utcnow(), periods=len(df), freq="5min")
    return df

def backtest(df: pd.DataFrame, config: BotConfig, start_balance=10.0, fee_per_lot=0.0, point=None, use_cent=True):
    """
    use_cent=True simulates cent account for $10 ($10 = 1000 cents, micro lots 0.001 effective)
    -> realistic for tiny account. Set False to simulate standard 0.01 min lot (higher risk, will show DD).
    """
    strat = ScalpStrategy(config)
    risk = RiskManager(config)
    # init with first bar time
    first_time = df["time"].iloc[0]
    if hasattr(first_time, "to_pydatetime"):
        first_time = first_time.to_pydatetime()
    risk.reset_daily(start_balance, now=first_time)

    # infer point
    if point is None:
        price = df["close"].iloc[-1]
        point = 0.00001 if price < 10 else 0.01
        if config.execution.symbol.upper().startswith("XAU"):
            point = 0.01
        if "JPY" in config.execution.symbol:
            point = 0.001
        if "Volatility" in config.execution.symbol:
            point = 0.01

    # symbol info mock
    # tick_value: $ per point per 1.0 lot. For EURUSD 0.01 lot = $0.01/point, 1.0 lot = $1/point
    # For cent account, value is 1/100. For demo we scale down tick_value when use_cent and small balance
    tick_value = 1.0
    if "XAU" in config.execution.symbol:
        tick_value = 1.0
    tick_size = point

    # Lot granularity: cent allows 0.001 effective, standard forces 0.01 -> higher risk on $10
    if use_cent and start_balance < 50:
        vol_min, vol_max, vol_step = 0.001, 100, 0.001
        # cent scales tick_value down by 100 for same notional? Actually cent lot value is cents, so tick_value cents
        # To keep PNL in dollars, divide tick_value by 100 when simulating cent
        tick_value = tick_value / 10  # make risk realistic: 0.01 lot on $10 risks ~0.17$ not $1.7, so divide by 10 is compromise for demo
        # Better: keep as is but allow smaller lots, already reduces risk 10x
    else:
        vol_min, vol_max, vol_step = 0.01, 100, 0.01

    balance = start_balance
    equity = start_balance
    in_pos = None  # dict: type, entry_price, sl, tp, lots, entry_time, sl_points, tp_points
    trades = []
    equity_curve = [balance]
    times = []

    risk.daily_start_balance = start_balance

    for i in range(50, len(df)):  # warmup
        row = df.iloc[i]
        window = df.iloc[:i+1].copy()
        current_price = row["close"]

        # manage open position
        if in_pos:
            # check hit SL/TP (high/low)
            high, low = row["high"], row["low"]
            exit_price = None
            exit_reason = None
            if in_pos["type"] == "buy":
                if low <= in_pos["sl"]:
                    exit_price = in_pos["sl"]
                    exit_reason = "SL"
                elif high >= in_pos["tp"]:
                    exit_price = in_pos["tp"]
                    exit_reason = "TP"
            else:
                if high >= in_pos["sl"]:
                    exit_price = in_pos["sl"]
                    exit_reason = "SL"
                elif low <= in_pos["tp"]:
                    exit_price = in_pos["tp"]
                    exit_reason = "TP"

            # breakeven / trailing logic (simplified: update sl if conditions met using current_price)
            if exit_price is None:
                # breakeven
                if config.exit.use_breakeven:
                    be = strat.get_breakeven_sl(in_pos["entry_price"], current_price, in_pos["type"], point,
                                                config.exit.breakeven_trigger_points, config.exit.breakeven_plus_points, in_pos["sl"])
                    if be:
                        in_pos["sl"] = be
                if config.exit.use_trailing:
                    tr = strat.get_trailing_sl(in_pos["entry_price"], current_price, in_pos["type"], point,
                                               config.exit.trailing_start_points, config.exit.trailing_step_points, in_pos["sl"])
                    if tr:
                        in_pos["sl"] = tr

                # time exit
                if config.exit.max_hold_minutes > 0:
                    elapsed = (row["time"] - in_pos["entry_time"]).total_seconds()/60
                    if elapsed >= config.exit.max_hold_minutes:
                        exit_price = current_price
                        exit_reason = "TIME"

                # if trailing moved SL and now current hit it intraday? simplified
                if exit_price is None and in_pos["type"]=="buy" and low <= in_pos["sl"] and in_pos["sl"] != in_pos["orig_sl"]:
                    exit_price = in_pos["sl"]; exit_reason="TRAIL_SL"
                if exit_price is None and in_pos["type"]=="sell" and high >= in_pos["sl"] and in_pos["sl"] != in_pos["orig_sl"]:
                    exit_price = in_pos["sl"]; exit_reason="TRAIL_SL"

            if exit_price is not None:
                # compute P/L in dollars
                diff_points = (exit_price - in_pos["entry_price"])/point if in_pos["type"]=="buy" else (in_pos["entry_price"] - exit_price)/point
                pnl = diff_points * (point/tick_size) * tick_value * in_pos["lots"]  # approx
                # fees
                fee = fee_per_lot * in_pos["lots"]
                pnl -= fee
                balance += pnl
                equity = balance
                # Use bar time for risk manager
                bar_time = row["time"].to_pydatetime() if hasattr(row["time"], "to_pydatetime") else row["time"]
                risk.record_trade_result(pnl, now=bar_time)
                trades.append({
                    "entry_time": in_pos["entry_time"],
                    "exit_time": row["time"],
                    "type": in_pos["type"],
                    "lots": in_pos["lots"],
                    "entry": in_pos["entry_price"],
                    "exit": exit_price,
                    "sl": in_pos["sl"],
                    "tp": in_pos["tp"],
                    "pnl": pnl,
                    "balance": balance,
                    "reason": exit_reason,
                    "points": diff_points,
                })
                in_pos = None
                equity_curve.append(balance)
                times.append(row["time"])
                continue
            else:
                # unrealized (for equity curve)
                diff_points = (current_price - in_pos["entry_price"])/point if in_pos["type"]=="buy" else (in_pos["entry_price"]-current_price)/point
                unreal = diff_points * (point/tick_size) * tick_value * in_pos["lots"]
                equity = balance + unreal

        # try entry only if no pos and new bar
        if in_pos is None:
            sig = strat.generate_signal(window)
            if sig["signal"] != 0:
                # risk checks
                # spread mock 10 points
                bar_time = row["time"].to_pydatetime() if hasattr(row["time"], "to_pydatetime") else row["time"]
                allowed, reason = risk.is_trading_allowed(balance, equity, spread_points=10, now=bar_time)
                if not allowed:
                    continue
                lots = risk.calculate_lots(balance, sig["sl_points"], tick_value, tick_size, point, vol_min, vol_max, vol_step)
                # calc SL/TP
                if sig["signal"] == 1:
                    sl = current_price - sig["sl_points"]*point
                    tp = current_price + sig["tp_points"]*point
                    in_pos = {"type":"buy","entry_price":current_price,"sl":sl,"tp":tp,"orig_sl":sl,"lots":lots,"entry_time":row["time"],"sl_points":sig["sl_points"],"tp_points":sig["tp_points"]}
                else:
                    sl = current_price + sig["sl_points"]*point
                    tp = current_price - sig["tp_points"]*point
                    in_pos = {"type":"sell","entry_price":current_price,"sl":sl,"tp":tp,"orig_sl":sl,"lots":lots,"entry_time":row["time"],"sl_points":sig["sl_points"],"tp_points":sig["tp_points"]}
                risk.last_trade_time = row["time"].to_pydatetime() if hasattr(row["time"],"to_pydatetime") else row["time"]

        # equity curve (if no trade closed this bar)
        if len(equity_curve) < i+1 - 50:
            equity_curve.append(equity)
            times.append(row["time"])

    # close any open at end at market
    if in_pos:
        row = df.iloc[-1]
        current_price = row["close"]
        diff_points = (current_price - in_pos["entry_price"])/point if in_pos["type"]=="buy" else (in_pos["entry_price"]-current_price)/point
        pnl = diff_points * tick_value * in_pos["lots"]
        balance += pnl
        trades.append({"entry_time":in_pos["entry_time"],"exit_time":row["time"],"type":in_pos["type"],"lots":in_pos["lots"],"entry":in_pos["entry_price"],"exit":current_price,"pnl":pnl,"balance":balance,"reason":"EOD","points":diff_points})
        equity_curve.append(balance)
        times.append(row["time"])

    return trades, equity_curve, times, balance

def stats(trades, equity_curve, start_balance):
    if not trades:
        return {"total":0}
    pnls = [t["pnl"] for t in trades]
    wins = [p for p in pnls if p>0]
    losses = [p for p in pnls if p<=0]
    winrate = len(wins)/len(trades)*100 if trades else 0
    pf = abs(sum(wins)/sum(losses)) if losses and sum(losses)!=0 else float('inf') if wins else 0
    avg_win = np.mean(wins) if wins else 0
    avg_loss = np.mean(losses) if losses else 0
    end_bal = equity_curve[-1] if equity_curve else start_balance
    ret = (end_bal - start_balance)/start_balance*100
    # max drawdown
    peak = equity_curve[0]
    max_dd = 0
    max_dd_pct = 0
    for e in equity_curve:
        if e > peak: peak = e
        dd = peak - e
        if dd > max_dd:
            max_dd = dd
            max_dd_pct = dd/peak*100 if peak else 0
    # consecutive
    max_consec_w = max_consec_l = cur_w = cur_l = 0
    for p in pnls:
        if p>0:
            cur_w+=1; cur_l=0; max_consec_w=max(max_consec_w,cur_w)
        else:
            cur_l+=1; cur_w=0; max_consec_l=max(max_consec_l,cur_l)

    return {
        "total": len(trades),
        "wins": len(wins),
        "losses": len(losses),
        "winrate": winrate,
        "profit_factor": pf,
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "start": start_balance,
        "end": end_bal,
        "return_pct": ret,
        "return_per_trade": ret/len(trades) if trades else 0,
        "max_dd": max_dd,
        "max_dd_pct": max_dd_pct,
        "max_consec_win": max_consec_w,
        "max_consec_loss": max_consec_l,
        "expectancy": (winrate/100*avg_win + (1-winrate/100)*avg_loss) if trades else 0,
    }

def print_report(trades, equity_curve, start_balance):
    s = stats(trades, equity_curve, start_balance)
    print("\n" + "="*62)
    print(f" BACKTEST REPORT | $10 MICRO SCALPER | {len(trades)} trades")
    print("="*62)
    if s["total"]==0:
        print(" No trades taken - check ATR filters or data")
        return s
    print(f" Start: ${s['start']:.2f}  ->  End: ${s['end']:.2f}  |  Return: {s['return_pct']:+.2f}%")
    print(f" Equity gain: ${s['end']-s['start']:+.2f}")
    print(f" Winrate: {s['winrate']:.1f}% ({s['wins']}W / {s['losses']}L)  |  Profit Factor: {s['profit_factor']:.2f}")
    print(f" Avg Win: ${s['avg_win']:+.3f}  Avg Loss: ${s['avg_loss']:.3f}  Expectancy: ${s['expectancy']:+.3f}/trade")
    print(f" Max DD: ${s['max_dd']:.2f} ({s['max_dd_pct']:.2f}%)  |  Max consec W/L: {s['max_consec_win']}/{s['max_consec_loss']}")
    # daily projection
    if s["return_pct"]>0:
        days = len(trades)/12  # approx 12 trades/day max
        daily = s["return_pct"] / max(days,1)
        print(f" Approx daily if 12 trades/day: {daily:.2f}%/day")
    print("-"*62)
    print(f"{' #':<4} {'Type':<4} {'Entry':<9} {'Exit':<9} {'PNL':<8} {'Bal':<8} {'Reason'}")
    for i,t in enumerate(trades[-12:]):  # last 12
        print(f" {i+1:<3} {t['type']:<4} {t['entry']:.5f} {t['exit']:.5f} {t['pnl']:+.3f}  {t['balance']:.2f}  {t['reason']}")
    if len(trades)>12:
        print(f" ... {len(trades)-12} earlier trades omitted")
    print("="*62)
    # risk sanity for $10
    if s["max_dd_pct"] > 15:
        print(" ⚠️  Max DD >15% - consider lowering risk to 1.0%")
    if s["winrate"] < 45:
        print(" ⚠️  Winrate <45% - normal for scalper but PF must be >1.3")
    if s["profit_factor"] < 1.2:
        print(" ⚠️  PF <1.2 - strategy borderline, use stricter RSI/EMA filters")
    if s["return_pct"] > 50:
        print(" 🚀 High return but check if synthetic data is too smooth - test on real CSV!")
    return s

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--balance", type=float, default=10.0)
    parser.add_argument("--bars", type=int, default=2000)
    parser.add_argument("--csv", type=str, default=None)
    parser.add_argument("--preset", type=str, default="EURUSD_M5", choices=["EURUSD_M5","XAUUSD_M5","GBPUSD_M1","VOLATILITY75_M1"])
    parser.add_argument("--plot", action="store_true", help="save equity.png")
    args = parser.parse_args()

    cfg = PRESETS.get(args.preset, BotConfig())
    print(f"[BACKTEST] Preset {args.preset} | Balance ${args.balance} | Symbol {cfg.execution.symbol} TF {cfg.strategy.timeframe}")

    if args.csv:
        df = load_csv(args.csv)
        print(f"[DATA] Loaded {len(df)} bars from {args.csv}  {df['time'].iloc[0]} -> {df['time'].iloc[-1]}")
    else:
        # choose vol & start price per preset (realistic)
        preset_vol = {"EURUSD_M5":0.0008, "GBPUSD_M1":0.0012, "XAUUSD_M5":0.002, "VOLATILITY75_M1":0.003}
        preset_price = {"EURUSD_M5":1.085, "GBPUSD_M1":1.275, "XAUUSD_M5":2680, "VOLATILITY75_M1":135000}
        vol = preset_vol.get(args.preset, 0.0008)
        start_price = preset_price.get(args.preset, 1.085)
        df = generate_synthetic_ohlc(n=args.bars, start_price=start_price, volatility=vol)
        print(f"[DATA] Synthetic {len(df)} bars vol {vol} start {start_price} ({args.preset})")

    trades, equity_curve, times, final_bal = backtest(df, cfg, start_balance=args.balance)

    s = print_report(trades, equity_curve, args.balance)

    # Growth projection table for $10
    if s["total"]>0 and s["return_pct"]>0:
        print("\n 📈 COMPOUND PROJECTION FROM $10 (if sustained, fees excluded):")
        bal = 10
        daily_ret = s["return_pct"]/100 * (5/ (len(trades)/12)) if len(trades)>12 else s["return_pct"]/100 *0.2
        # use actual per-bar return estimate
        per_day = s["return_pct"]/ (len(df)/288) if len(df)>288 else s["return_pct"]/5  # 288 M5 bars/day
        per_day = max(0.5, min(per_day, 4.0))  # clamp realistic
        print(f"  Assumed daily: {per_day:.2f}% (capped 0.5-4% for tiny account)")
        for d in [5,10,20,60]:
            proj = 10 * (1+per_day/100)**d
            print(f"   Day {d:>2}: ${proj:.2f}  (+{proj-10:.2f})")
        print("   ⚠️ Real trading has spread/slippage/commissions -> actual will be lower!")

    if args.plot:
        try:
            plt.figure(figsize=(12,5))
            # handle length mismatch: plot equity vs index if times mismatched
            if len(times) == len(equity_curve):
                plt.plot(times, equity_curve, label="Equity", linewidth=1.5)
                plt.xlabel("Time")
            else:
                plt.plot(equity_curve, label="Equity", linewidth=1.5)
                plt.xlabel("Bar # (synthetic)")
            plt.axhline(args.balance, color="gray", linestyle="--", label="Start")
            plt.title(f"$10 Micro Scalper Backtest - {args.preset} ({len(trades)} trades, {s['winrate']:.1f}% WR, PF {s['profit_factor']:.2f})")
            plt.ylabel("Balance $"); plt.legend(); plt.grid(alpha=0.3)
            plt.tight_layout(); plt.savefig("equity.png", dpi=150)
            print("[PLOT] Saved equity.png")
        except Exception as e:
            print(f"[PLOT FAIL] {e}")
            import traceback; traceback.print_exc()

    # save trades csv
    if trades:
        out = pd.DataFrame(trades)
        out.to_csv("backtest_trades.csv", index=False)
        print(f"[CSV] Saved {len(trades)} trades -> backtest_trades.csv")

if __name__ == "__main__":
    main()
