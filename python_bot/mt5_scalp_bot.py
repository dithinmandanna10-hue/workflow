#!/usr/bin/env python3
"""
MT5 SCALP BOT - Live Trading for $10 Micro Account
Works with MetaTrader5 Python package + MT5 Terminal

QUICK START:
  pip install -r requirements.txt
  cp .env.example .env   # fill login / server
  python mt5_scalp_bot.py --symbol EURUSD --timeframe M5 --preset EURUSD_M5

Features:
  - Auto lot sizing 1.5% risk capped at 0.01-0.05 for $10
  - ATR SL/TP, breakeven + trailing
  - Daily profit/loss limits, max trades, spread filter
  - Cooldown after 3 losses
  - Every tick manages existing position, only new bar opens new trade
"""

import argparse
import time
from datetime import datetime
import os
import sys

# Optional MT5 import - allows testing without MT5 installed
try:
    import MetaTrader5 as mt5
    HAS_MT5 = True
except ImportError:
    HAS_MT5 = False
    print("[WARN] MetaTrader5 not installed - running in DEMO/backtest mode only")

import pandas as pd
from dotenv import load_dotenv

from config import BotConfig, PRESETS
from risk_manager import RiskManager
from strategy import ScalpStrategy

load_dotenv()

TIMEFRAME_MAP = {
    "M1": 1,
    "M5": 5,
    "M15": 15,
    "M30": 30,
    "H1": 60,
}

def mt5_timeframe(tf_str: str):
    if not HAS_MT5:
        return None
    return {
        "M1": mt5.TIMEFRAME_M1,
        "M5": mt5.TIMEFRAME_M5,
        "M15": mt5.TIMEFRAME_M15,
        "M30": mt5.TIMEFRAME_M30,
        "H1": mt5.TIMEFRAME_H1,
    }.get(tf_str, mt5.TIMEFRAME_M5)

class MT5ScalpBot:
    def __init__(self, config: BotConfig, dry_run: bool = False):
        self.config = config
        self.risk = RiskManager(config)
        self.strategy = ScalpStrategy(config)
        self.dry_run = dry_run or not HAS_MT5
        self.last_bar_time = None
        self.symbol = config.execution.symbol

        if not self.dry_run:
            self._connect_mt5()

    def _connect_mt5(self):
        if not HAS_MT5:
            raise RuntimeError("MetaTrader5 package not installed")

        login = self.config.mt5_login or int(os.getenv("MT5_LOGIN", "0"))
        password = self.config.mt5_password or os.getenv("MT5_PASSWORD", "")
        server = self.config.mt5_server or os.getenv("MT5_SERVER", "")
        path = self.config.mt5_path or os.getenv("MT5_PATH", "")

        kwargs = {}
        if path:
            kwargs["path"] = path

        if not mt5.initialize(**kwargs):
            print(f"[ERROR] MT5 initialize failed: {mt5.last_error()}")
            sys.exit(1)

        if login and password and server:
            if not mt5.login(login, password=password, server=server):
                print(f"[ERROR] MT5 login failed: {mt5.last_error()}")
                mt5.shutdown()
                sys.exit(1)
            print(f"[MT5] Connected: login {login} server {server}")
        else:
            print("[MT5] Connected to running terminal (no login provided)")

        # Enable symbol
        if not mt5.symbol_select(self.symbol, True):
            print(f"[WARN] symbol_select failed for {self.symbol}")

        acc = mt5.account_info()
        if acc:
            print(f"[ACCOUNT] Balance ${acc.balance:.2f} Equity ${acc.equity:.2f} Leverage 1:{acc.leverage} | {acc.server}")
            self.risk.reset_daily(acc.balance)

    def get_rates(self, n=100) -> pd.DataFrame | None:
        if self.dry_run:
            return None
        tf = mt5_timeframe(self.config.strategy.timeframe)
        rates = mt5.copy_rates_from_pos(self.symbol, tf, 0, n)
        if rates is None or len(rates) == 0:
            print(f"[WARN] copy_rates failed: {mt5.last_error()}")
            return None
        df = pd.DataFrame(rates)
        df["time"] = pd.to_datetime(df["time"], unit="s")
        df.rename(columns={"open":"open","high":"high","low":"low","close":"close","tick_volume":"tick_volume"}, inplace=True)
        return df

    def get_symbol_info(self):
        if self.dry_run:
            # mock for $10 account
            return {
                "point": 0.00001 if "JPY" not in self.symbol and "XAU" not in self.symbol else (0.01 if "XAU" in self.symbol else 0.001),
                "tick_value": 1.0 if "USD" in self.symbol else 1.0,
                "tick_size": 0.00001 if "JPY" not in self.symbol else 0.001,
                "spread_points": 12,
                "vol_min": 0.01,
                "vol_max": 100.0,
                "vol_step": 0.01,
                "stops_level": 10,
            }
        info = mt5.symbol_info(self.symbol)
        tick = mt5.symbol_info_tick(self.symbol)
        if info is None or tick is None:
            return None
        spread_pts = int(round((tick.ask - tick.bid) / info.point)) if info.point else 0
        return {
            "point": info.point,
            "tick_value": info.trade_tick_value,
            "tick_size": info.trade_tick_size,
            "spread_points": spread_pts,
            "vol_min": info.volume_min,
            "vol_max": info.volume_max,
            "vol_step": info.volume_step,
            "stops_level": info.trade_stops_level,
            "bid": tick.bid,
            "ask": tick.ask,
        }

    def account_info(self):
        if self.dry_run:
            # simulate
            return {"balance": 10.0, "equity": 10.0, "free_margin": 10.0}
        acc = mt5.account_info()
        if acc is None:
            return None
        return {"balance": acc.balance, "equity": acc.equity, "free_margin": acc.margin_free}

    def has_open_position(self) -> bool:
        if self.dry_run:
            return False
        pos = mt5.positions_get(symbol=self.symbol)
        if pos is None:
            return False
        for p in pos:
            if p.magic == self.config.execution.magic:
                return True
        return False

    def manage_position(self):
        if self.dry_run or not HAS_MT5:
            return
        positions = mt5.positions_get(symbol=self.symbol)
        if not positions:
            return
        info = self.get_symbol_info()
        if not info:
            return
        point = info["point"]
        for p in positions:
            if p.magic != self.config.execution.magic:
                continue
            # current price
            tick = mt5.symbol_info_tick(self.symbol)
            current = tick.bid if p.type == mt5.POSITION_TYPE_BUY else tick.ask
            pos_type = "buy" if p.type == mt5.POSITION_TYPE_BUY else "sell"
            # breakeven
            if self.config.exit.use_breakeven:
                new_sl = self.strategy.get_breakeven_sl(p.price_open, current, pos_type, point,
                                                        self.config.exit.breakeven_trigger_points,
                                                        self.config.exit.breakeven_plus_points,
                                                        p.sl)
                if new_sl:
                    req = {"action": mt5.TRADE_ACTION_SLTP, "symbol": self.symbol, "sl": new_sl, "tp": p.tp, "position": p.ticket}
                    res = mt5.order_send(req)
                    if res and res.retcode == mt5.TRADE_RETCODE_DONE:
                        print(f"[EXIT] Breakeven -> SL {new_sl:.5f} for #{p.ticket}")
            # trailing
            if self.config.exit.use_trailing:
                new_sl = self.strategy.get_trailing_sl(p.price_open, current, pos_type, point,
                                                       self.config.exit.trailing_start_points,
                                                       self.config.exit.trailing_step_points,
                                                       p.sl)
                if new_sl:
                    req = {"action": mt5.TRADE_ACTION_SLTP, "symbol": self.symbol, "sl": new_sl, "tp": p.tp, "position": p.ticket}
                    res = mt5.order_send(req)
                    if res and res.retcode == mt5.TRADE_RETCODE_DONE:
                        print(f"[TRAIL] New SL {new_sl:.5f} for #{p.ticket}")

            # time exit
            elapsed_min = (datetime.utcnow() - datetime.fromtimestamp(p.time)).total_seconds()/60
            if elapsed_min >= self.config.exit.max_hold_minutes:
                print(f"[TIME EXIT] Closing #{p.ticket} after {elapsed_min:.0f} min")
                self.close_position(p)

            # daily P/L already handled in risk manager

    def close_position(self, pos):
        if self.dry_run:
            return
        tick = mt5.symbol_info_tick(self.symbol)
        close_price = tick.bid if pos.type == mt5.POSITION_TYPE_BUY else tick.ask
        close_type = mt5.ORDER_TYPE_SELL if pos.type == mt5.POSITION_TYPE_BUY else mt5.ORDER_TYPE_BUY
        req = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": self.symbol,
            "volume": pos.volume,
            "type": close_type,
            "position": pos.ticket,
            "price": close_price,
            "deviation": self.config.execution.deviation,
            "magic": self.config.execution.magic,
            "comment": "time exit",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        res = mt5.order_send(req)
        print(f"[CLOSE] {res}")

    def try_open(self, signal: dict):
        sig = signal["signal"]
        if sig == 0:
            return

        acc = self.account_info()
        sinfo = self.get_symbol_info()
        if not acc or not sinfo:
            print("[WARN] No acc/symbol info")
            return

        allowed, reason = self.risk.is_trading_allowed(acc["balance"], acc["equity"], sinfo["spread_points"])
        if not allowed:
            # throttle log
            print(f"[SKIP] {reason}")
            return

        if self.has_open_position():
            print("[SKIP] Already in position")
            return

        # lot calc
        lots = self.risk.calculate_lots(acc["balance"], signal["sl_points"], sinfo["tick_value"], sinfo["tick_size"], sinfo["point"],
                                        sinfo["vol_min"], sinfo["vol_max"], sinfo["vol_step"])
        print(f"[SIGNAL] {'BUY' if sig==1 else 'SELL'} lots {lots} SL {signal['sl_points']:.0f} TP {signal['tp_points']:.0f} | {signal['reason']}")

        if self.dry_run:
            print(f"[DRY RUN] Would {'BUY' if sig==1 else 'SELL'} {lots} {self.symbol} SL {signal['sl_points']:.0f} TP {signal['tp_points']:.0f}")
            self.risk.trades_today += 1
            self.risk.last_trade_time = datetime.utcnow()
            return

        # Build request
        point = sinfo["point"]
        if sig == 1:
            price = sinfo["ask"]
            sl = price - signal["sl_points"] * point
            tp = price + signal["tp_points"] * point
            otype = mt5.ORDER_TYPE_BUY
        else:
            price = sinfo["bid"]
            sl = price + signal["sl_points"] * point
            tp = price - signal["tp_points"] * point
            otype = mt5.ORDER_TYPE_SELL

        # stops level
        stops = sinfo["stops_level"] * point
        if sig == 1:
            if price - sl < stops:
                sl = price - stops - 10*point
            if tp - price < stops:
                tp = price + stops + 10*point
        else:
            if sl - price < stops:
                sl = price + stops + 10*point
            if price - tp < stops:
                tp = price - stops - 10*point

        # margin check
        margin = mt5.order_calc_margin(otype, self.symbol, lots, price)
        if margin and margin > acc["free_margin"] * 0.9:
            print(f"[MARGIN] Not enough: need {margin:.2f} free {acc['free_margin']:.2f}")
            return

        req = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": self.symbol,
            "volume": lots,
            "type": otype,
            "price": price,
            "sl": sl,
            "tp": tp,
            "deviation": self.config.execution.deviation,
            "magic": self.config.execution.magic,
            "comment": self.config.execution.comment,
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        res = mt5.order_send(req)
        if res is None:
            print(f"[ERROR] order_send None: {mt5.last_error()}")
            return
        if res.retcode != mt5.TRADE_RETCODE_DONE:
            print(f"[FAIL] {res.retcode} {res.comment}")
        else:
            print(f"[OPEN] {'BUY' if sig==1 else 'SELL'} {lots} @ {price:.5f} SL {sl:.5f} TP {tp:.5f} ticket {res.order}")
            self.risk.trades_today += 1
            self.risk.last_trade_time = datetime.utcnow()

    def run_once(self):
        self.manage_position()

        # only new bar triggers new entry
        df = self.get_rates(200)
        if df is None:
            # dry run demo data hack - generate fake df for test?
            return
        bar_time = df.iloc[-1]["time"]
        if self.last_bar_time is not None and bar_time == self.last_bar_time:
            return
        self.last_bar_time = bar_time

        sig = self.strategy.generate_signal(df)
        # print occasional heartbeat
        # print(f"[BAR] {bar_time} {sig['reason']}")
        self.try_open(sig)

    def run_loop(self, poll_seconds: int = 5):
        print(f"=== MT5 $10 SCALP BOT LIVE ===")
        print(f"Symbol {self.symbol} TF {self.config.strategy.timeframe} Risk {self.config.risk.risk_percent}%")
        print(f"Daily target +{self.config.risk.daily_target_pct}% / stop -{self.config.risk.max_daily_loss_pct}%")
        print("Press Ctrl+C to stop\n")
        try:
            while True:
                try:
                    self.run_once()
                except Exception as e:
                    print(f"[LOOP ERROR] {e}")
                    import traceback; traceback.print_exc()
                time.sleep(poll_seconds)
        except KeyboardInterrupt:
            print("\n[STOP] Bot stopped by user")
        finally:
            if HAS_MT5 and not self.dry_run:
                mt5.shutdown()
                print("[MT5] Shutdown")

    def print_status(self):
        acc = self.account_info()
        sinfo = self.get_symbol_info()
        if acc:
            s = self.risk.get_status(acc["balance"], acc["equity"])
            print(s)
        if sinfo:
            print(f"Spread {sinfo['spread_points']} point {sinfo['point']}")

def main():
    parser = argparse.ArgumentParser(description="$10 MT5 Scalp Bot")
    parser.add_argument("--symbol", default="EURUSD", help="EURUSD, XAUUSD, GBPUSD, Volatility 75 Index")
    parser.add_argument("--timeframe", default="M5", choices=["M1","M5","M15","M30","H1"])
    parser.add_argument("--preset", default=None, help="EURUSD_M5,XAUUSD_M5,GBPUSD_M1,VOLATILITY75_M1")
    parser.add_argument("--risk", type=float, default=None, help="risk % per trade (1.5)")
    parser.add_argument("--dry-run", action="store_true", help="no MT5, simulation only")
    parser.add_argument("--once", action="store_true", help="run once and exit (for testing)")
    args = parser.parse_args()

    if args.preset and args.preset in PRESETS:
        cfg = PRESETS[args.preset]
        print(f"[PRESET] {args.preset}")
    else:
        cfg = BotConfig()
        cfg.execution.symbol = args.symbol
        cfg.strategy.timeframe = args.timeframe
        if args.risk:
            cfg.risk.risk_percent = args.risk

    # override with args if preset not used OR even if preset, allow overrides
    if args.symbol != "EURUSD" and args.preset is None:
        cfg.execution.symbol = args.symbol
    if args.timeframe != "M5" and args.preset is None:
        cfg.strategy.timeframe = args.timeframe

    # Load MT5 creds from env if present
    try:
        cfg.mt5_login = int(os.getenv("MT5_LOGIN", "0"))
    except:
        pass
    cfg.mt5_password = os.getenv("MT5_PASSWORD", "")
    cfg.mt5_server = os.getenv("MT5_SERVER", "")
    cfg.mt5_path = os.getenv("MT5_PATH", "")

    bot = MT5ScalpBot(cfg, dry_run=args.dry_run)

    if args.once:
        bot.print_status()
        df = bot.get_rates(200)
        if df is not None:
            sig = bot.strategy.generate_signal(df)
            print(f"[TEST SIGNAL] {sig}")
            bot.try_open(sig)
        else:
            print("[ONCE] No data (dry-run). Run backtest.py for simulation.")
        return

    bot.run_loop()

if __name__ == "__main__":
    main()
