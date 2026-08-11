#!/usr/bin/env python3
"""
Optimizer for $10 Micro Scalper - MAX POTENTIAL
Grid + random search over strategy + risk + exit params
Finds best Sharpe-like score: (Return * PF) / (DD + 1) with constraints

Run: python optimize.py --preset EURUSD_M5 --iters 80 --bars 3000
      python optimize.py --all --iters 50 --bars 3000 --plot

This upgrades the bot to MAX POTENTIAL while keeping hard risk caps.
"""
import argparse, random, copy, itertools, json
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from config import BotConfig, PRESETS, RiskConfig, StrategyConfig, ExitConfig, ExecutionConfig
from backtest import generate_synthetic_ohlc, backtest, stats, load_csv

# faster synthetic with momentum
def generate_synthetic_ohlc_fast(n=3000, start_price=1.085, volatility=0.0008, drift=0.0):
    np.random.seed(123)
    # regime switching trend + momentum
    prices=[start_price]
    prev_ret=0
    trend_phase=0
    for i in range(1,n):
        # regime: 0=chop, 1=up, 2=down, switches every 300-600 bars
        if i % random.randint(300,600)==0:
            trend_phase = random.choice([0,1,2])
        drift_local = {0:0, 1:0.00008, 2:-0.00008}[trend_phase]
        # momentum
        mom = 0.25 * prev_ret
        vol = volatility * (0.8 + 0.4*np.sin(i/70) + abs(np.random.randn())*0.15)
        ret = np.random.randn()*vol + drift_local + mom + drift
        prev_ret = ret
        prices.append(max(start_price*0.5, prices[-1]*(1+ret)))
    closes=np.array(prices)
    # create realistic OHLC with wicks
    opens=np.roll(closes,1); opens[0]=closes[0]
    highs=closes * (1+ np.abs(np.random.randn(n))*0.0006 + 0.0002)
    lows=closes * (1- np.abs(np.random.randn(n))*0.0006 - 0.0002)
    highs=np.maximum(highs, np.maximum(opens, closes))
    lows=np.minimum(lows, np.minimum(opens, closes))
    # time: M5
    times=[datetime.utcnow() - timedelta(minutes=5*(n-i)) for i in range(n)]
    df=pd.DataFrame({"time":times,"open":opens,"high":highs,"low":lows,"close":closes,"tick_volume":np.random.randint(80,600,n)})
    return df

def score_stats(s):
    if s.get("total",0) < 15:
        return -1
    if s["profit_factor"] < 1.0:
        return s["return_pct"] * 0.1 # penalize
    # score favours return, PF, winrate, low DD
    dd_penalty = max(1, s["max_dd_pct"])
    return (s["return_pct"] * s["profit_factor"] * (s["winrate"]/55)) / dd_penalty

def random_params(base: BotConfig):
    cfg = copy.deepcopy(base)
    # Strategy variations
    cfg.strategy.ema_fast = random.choice([7,8,9,10])
    cfg.strategy.ema_slow = random.choice([20,21,26,30])
    cfg.strategy.rsi_period = random.choice([14,12,10])
    cfg.strategy.rsi_buy_min = random.choice([48,50,52,55])
    cfg.strategy.rsi_buy_max = random.choice([65,68,70,72])
    cfg.strategy.rsi_sell_min = random.choice([28,30,32,35])
    cfg.strategy.rsi_sell_max = random.choice([45,48,50,52])
    cfg.strategy.atr_period = random.choice([10,14])
    cfg.strategy.atr_sl_mult = random.choice([1.2,1.5,1.8,2.0,2.2])
    cfg.strategy.atr_tp_mult = random.choice([0.9,1.0,1.2,1.5,1.8])
    cfg.strategy.min_atr_points = random.choice([40,50,60,80])
    cfg.strategy.max_atr_points = random.choice([700,800,1200,1500] if cfg.execution.symbol=="EURUSD" else [1200,1500,2000,5000])

    # Risk aggressive but capped for max potential
    cfg.risk.risk_percent = random.choice([1.2,1.5,1.8,2.0,2.2])
    cfg.risk.max_lot = random.choice([0.03,0.05,0.07]) if cfg.risk.risk_percent<2.0 else random.choice([0.04,0.05])
    # keep hard cap 0.05 for $10 live, but optimizer can try 0.07 for simulation
    cfg.risk.max_daily_loss_pct = random.choice([4.5,5.0,6.0])
    cfg.risk.daily_target_pct = random.choice([4.0,5.0,6.0,8.0])
    cfg.risk.max_trades_per_day = random.choice([12,15,18])

    # Exit tuning
    cfg.exit.breakeven_trigger_points = random.choice([80,100,120,150])
    cfg.exit.breakeven_plus_points = random.choice([30,50,70])
    cfg.exit.trailing_start_points = random.choice([90,120,150,180])
    cfg.exit.trailing_step_points = random.choice([40,60,80])
    cfg.exit.max_hold_minutes = random.choice([60,90,120,150])

    # Session filter for max potential: only London/NY
    if random.random() < 0.3:
        cfg.execution.start_hour = 7  # London
        cfg.execution.end_hour = 17
    else:
        cfg.execution.start_hour = 0
        cfg.execution.end_hour = 23

    return cfg

def optimize_preset(preset_name, iters=60, bars=3000, df=None, verbose=True):
    base = PRESETS[preset_name]
    if df is None:
        preset_vol = {"EURUSD_M5":0.0007, "GBPUSD_M1":0.0010, "XAUUSD_M5":0.0018, "VOLATILITY75_M1":0.0025}
        preset_price = {"EURUSD_M5":1.085, "GBPUSD_M1":1.275, "XAUUSD_M5":2685, "VOLATILITY75_M1":135000}
        vol = preset_vol.get(preset_name, 0.0008)
        price = preset_price.get(preset_name, 1.085)
        df = generate_synthetic_ohlc_fast(n=bars, start_price=price, volatility=vol)

    best_score = -1e9
    best_cfg = None
    best_stats = None
    history=[]

    # include baseline
    baseline_trades, eq, _, _ = backtest(df, base, start_balance=10)
    base_s = stats(baseline_trades, eq, 10)
    base_score = score_stats(base_s)
    if verbose:
        print(f"\n[BASELINE] {preset_name}: {base_s.get('total',0)}tr ret {base_s.get('return_pct',0):+.2f}% PF {base_s.get('profit_factor',0):.2f} WR {base_s.get('winrate',0):.1f}% DD {base_s.get('max_dd_pct',0):.2f}% score {base_score:.3f}")
    best_score = base_score
    best_cfg = base
    best_stats = base_s

    for i in range(iters):
        cfg = random_params(base)
        # ensure EMA fast < slow
        if cfg.strategy.ema_fast >= cfg.strategy.ema_slow:
            cfg.strategy.ema_slow = cfg.strategy.ema_fast + random.choice([12,13,15])
        try:
            trades, eq, _, _ = backtest(df, cfg, start_balance=10)
            s = stats(trades, eq, 10)
        except Exception as e:
            continue
        sc = score_stats(s)
        history.append((sc, s, cfg))
        # penalize excessive risk: cap DD
        if s.get("max_dd_pct",99) > 9:
            sc *= 0.7
        if s.get("total",0) < 12:
            sc *= 0.5
        if sc > best_score:
            best_score = sc
            best_cfg = copy.deepcopy(cfg)
            best_stats = s
            if verbose:
                print(f"[{i+1:3d}] NEW BEST score {sc:.3f} | {s['total']:2d}tr ret {s['return_pct']:+.2f}% PF {s['profit_factor']:.2f} WR {s['winrate']:.1f}% DD {s['max_dd_pct']:.2f}% | EMA {cfg.strategy.ema_fast}/{cfg.strategy.ema_slow} RSI {cfg.strategy.rsi_buy_min}-{cfg.strategy.rsi_buy_max}/{cfg.strategy.rsi_sell_min}-{cfg.strategy.rsi_sell_max} ATR {cfg.strategy.atr_sl_mult}/{cfg.strategy.atr_tp_mult} risk {cfg.risk.risk_percent}% TP{cfg.exit.trailing_start_points}/{cfg.exit.trailing_step_points} hold {cfg.exit.max_hold_minutes}m")

    if verbose and best_cfg is not base:
        print(f"\n[BEST] {preset_name} score {best_score:.3f} -> ret {best_stats['return_pct']:+.2f}% PF {best_stats['profit_factor']:.2f} WR {best_stats['winrate']:.1f}% DD {best_stats['max_dd_pct']:.2f}%")

    return best_cfg, best_stats, base_s, history, df

def main():
    import argparse
    p=argparse.ArgumentParser()
    p.add_argument("--preset", default="EURUSD_M5", choices=list(PRESETS.keys()))
    p.add_argument("--all", action="store_true")
    p.add_argument("--iters", type=int, default=50)
    p.add_argument("--bars", type=int, default=3000)
    p.add_argument("--plot", action="store_true")
    args=p.parse_args()

    presets = list(PRESETS.keys()) if args.all else [args.preset]

    results={}
    for preset in presets:
        print("="*78)
        print(f" OPTIMIZING {preset} | {args.iters} iters | {args.bars} bars (M5~ {args.bars*5/60/24:.1f} days)")
        print("="*78)
        best_cfg, best_s, base_s, history, df = optimize_preset(preset, iters=args.iters, bars=args.bars)
        results[preset] = (best_cfg, best_s, base_s)

        # final verbose
        print(f"\n--- {preset} SUMMARY ---")
        print(f"Baseline: {base_s.get('total')}tr {base_s.get('return_pct',0):+.2f}% PF{base_s.get('profit_factor',0):.2f} WR{base_s.get('winrate',0):.1f}% DD{base_s.get('max_dd_pct',0):.2f}%")
        if best_s is not base_s:
            print(f"OPTIMIZED MAX: {best_s.get('total')}tr {best_s.get('return_pct',0):+.2f}% PF{best_s.get('profit_factor',0):.2f} WR{best_s.get('winrate',0):.1f}% DD{best_s.get('max_dd_pct',0):.2f}% score {score_stats(best_s):.3f}")
            # show config diff
            print("\nOPTIMIZED PARAMS:")
            print(f" EMA {best_cfg.strategy.ema_fast}/{best_cfg.strategy.ema_slow} RSI buy {best_cfg.strategy.rsi_buy_min}-{best_cfg.strategy.rsi_buy_max} sell {best_cfg.strategy.rsi_sell_min}-{best_cfg.strategy.rsi_sell_max} ATR SL {best_cfg.strategy.atr_sl_mult} TP {best_cfg.strategy.atr_tp_mult} ATRpts {best_cfg.strategy.min_atr_points}-{best_cfg.strategy.max_atr_points}")
            print(f" Risk {best_cfg.risk.risk_percent}% maxLot {best_cfg.risk.max_lot} daily {best_cfg.risk.max_daily_loss_pct}/{best_cfg.risk.daily_target_pct}% maxTrades {best_cfg.risk.max_trades_per_day}")
            print(f" Exit BE {best_cfg.exit.breakeven_trigger_points}+{best_cfg.exit.breakeven_plus_points} trail {best_cfg.exit.trailing_start_points}/{best_cfg.exit.trailing_step_points} hold {best_cfg.exit.max_hold_minutes}m session {best_cfg.execution.start_hour}-{best_cfg.execution.end_hour}")

            # save best to json for later
            out = {
                "preset": preset,
                "baseline": base_s,
                "optimized": best_s,
                "params": {
                    "ema_fast": best_cfg.strategy.ema_fast,
                    "ema_slow": best_cfg.strategy.ema_slow,
                    "rsi_period": best_cfg.strategy.rsi_period,
                    "rsi_buy_min": best_cfg.strategy.rsi_buy_min,
                    "rsi_buy_max": best_cfg.strategy.rsi_buy_max,
                    "rsi_sell_min": best_cfg.strategy.rsi_sell_min,
                    "rsi_sell_max": best_cfg.strategy.rsi_sell_max,
                    "atr_period": best_cfg.strategy.atr_period,
                    "atr_sl_mult": best_cfg.strategy.atr_sl_mult,
                    "atr_tp_mult": best_cfg.strategy.atr_tp_mult,
                    "min_atr": best_cfg.strategy.min_atr_points,
                    "max_atr": best_cfg.strategy.max_atr_points,
                    "risk_percent": best_cfg.risk.risk_percent,
                    "max_lot": best_cfg.risk.max_lot,
                    "max_daily_loss": best_cfg.risk.max_daily_loss_pct,
                    "daily_target": best_cfg.risk.daily_target_pct,
                    "max_trades": best_cfg.risk.max_trades_per_day,
                    "be_trigger": best_cfg.exit.breakeven_trigger_points,
                    "be_plus": best_cfg.exit.breakeven_plus_points,
                    "trail_start": best_cfg.exit.trailing_start_points,
                    "trail_step": best_cfg.exit.trailing_step_points,
                    "hold": best_cfg.exit.max_hold_minutes,
                    "session": f"{best_cfg.execution.start_hour}-{best_cfg.execution.end_hour}"
                }
            }
            with open(f"optimized_{preset}.json","w") as f:
                json.dump(out, f, indent=2)
            print(f"[SAVE] optimized_{preset}.json")

            if args.plot:
                # run backtest with plot for best
                trades, eq, times, _ = backtest(df, best_cfg, start_balance=10)
                import matplotlib.pyplot as plt
                plt.figure(figsize=(13,5))
                plt.plot(eq, label="Optimized MAX", linewidth=1.6)
                # also baseline
                trades0, eq0, _, _ = backtest(df, PRESETS[preset], start_balance=10)
                plt.plot(eq0, label="Baseline", alpha=0.7, linestyle="--")
                plt.axhline(10, color="gray", linestyle=":")
                plt.title(f"{preset} Optimized MAX: {best_s['return_pct']:+.1f}% (PF {best_s['profit_factor']:.2f}) vs Baseline {base_s['return_pct']:+.1f}%")
                plt.ylabel("Balance $"); plt.xlabel(f"Bars (M5) - {len(df)} bars")
                plt.legend(); plt.grid(alpha=0.3)
                plt.tight_layout(); plt.savefig(f"equity_{preset}_MAX.png", dpi=150)
                print(f"[PLOT] equity_{preset}_MAX.png")
        else:
            print("No improvement over baseline.")

    # summary table
    print("\n" + "="*78)
    print(" FINAL OPTIMIZATION TABLE (MAX POTENTIAL)")
    print("="*78)
    print(f"{'Preset':<18} {'Trades':>6} {'Return':>8} {'PF':>5} {'WR':>6} {'DD%':>6} {'Score':>7} | vs Baseline")
    for preset in presets:
        best_cfg, best_s, base_s = results[preset]
        sc = score_stats(best_s)
        base_ret = base_s.get('return_pct',0)
        delta = best_s.get('return_pct',0) - base_ret
        print(f"{preset:<18} {best_s.get('total',0):6d} {best_s.get('return_pct',0):+7.2f}% {best_s.get('profit_factor',0):5.2f} {best_s.get('winrate',0):5.1f}% {best_s.get('max_dd_pct',0):5.2f}% {sc:7.3f} | {base_ret:+.2f}% → {delta:+.2f}%")

if __name__=="__main__":
    main()
