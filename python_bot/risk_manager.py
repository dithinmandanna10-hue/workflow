"""
Risk Manager for $10 account - STRICT, no blow-up
Handles lot sizing, daily limits, cooldowns, equity protection
"""
import time
from datetime import datetime, timedelta
from typing import Optional
from config import BotConfig

class RiskManager:
    def __init__(self, config: BotConfig):
        self.config = config
        self.daily_start_balance = 10.0
        self.daily_start_day = None
        self.trades_today = 0
        self.consecutive_losses = 0
        self.cooldown_until: Optional[datetime] = None
        self.last_trade_time: Optional[datetime] = None
        self.daily_profit = 0.0
        self.history_pnl = []  # last 20 trades

        self.reset_daily(10.0)

    def reset_daily(self, balance: float, now: Optional[datetime] = None):
        today = (now or datetime.utcnow()).date()
        if self.daily_start_day != today:
            self.daily_start_day = today
            self.daily_start_balance = balance
            self.trades_today = 0
            self.daily_profit = 0.0
            print(f"[RISK] New day {today} start balance ${balance:.2f}")

    def update_balance(self, balance: float, equity: float, now: Optional[datetime] = None):
        self.reset_daily(balance, now=now)
        self.daily_profit = equity - self.daily_start_balance

    def record_trade_result(self, profit: float, now: Optional[datetime] = None):
        self.trades_today += 1
        self.last_trade_time = now or datetime.utcnow()
        self.history_pnl.append(profit)
        if len(self.history_pnl) > 20:
            self.history_pnl.pop(0)

        if profit < 0:
            self.consecutive_losses += 1
            if self.consecutive_losses >= self.config.risk.max_consecutive_losses:
                base = now or datetime.utcnow()
                self.cooldown_until = base + timedelta(minutes=self.config.risk.cooldown_minutes)
                print(f"[RISK] LOSS STREAK {self.consecutive_losses} -> cooldown {self.config.risk.cooldown_minutes} min until {self.cooldown_until}")
        else:
            self.consecutive_losses = 0  # reset on win
            self.cooldown_until = None

    def is_trading_allowed(self, balance: float, equity: float, spread_points: int, now: Optional[datetime] = None) -> tuple[bool, str]:
        now = now or datetime.utcnow()
        self.update_balance(balance, equity, now=now)

        # equity emergency
        if equity < self.config.risk.balance_protection_equity:
            return False, f"Equity too low ${equity:.2f} < ${self.config.risk.balance_protection_equity}"

        # cooldown
        if self.cooldown_until and now < self.cooldown_until:
            return False, f"Cooldown until {self.cooldown_until.strftime('%H:%M:%S')}"

        # consecutive losses (if cooldown not set yet but limit hit)
        if self.consecutive_losses >= self.config.risk.max_consecutive_losses:
            if not self.cooldown_until or now >= self.cooldown_until:
                # set cooldown now if not set
                self.cooldown_until = now + timedelta(minutes=self.config.risk.cooldown_minutes)
            return False, f"Loss streak {self.consecutive_losses}"

        # daily loss / target
        if self.daily_start_balance > 0:
            pct = (equity - self.daily_start_balance) / self.daily_start_balance * 100
            if pct <= -self.config.risk.max_daily_loss_pct:
                return False, f"Daily loss limit {pct:.2f}% (${equity - self.daily_start_balance:.2f})"
            if pct >= self.config.risk.daily_target_pct:
                return False, f"Daily target hit {pct:.2f}% - locking profit!"

        if self.trades_today >= self.config.risk.max_trades_per_day:
            return False, f"Max trades {self.trades_today}/{self.config.risk.max_trades_per_day}"

        # time filter
        hour = now.hour  # broker time ideally, use UTC for demo
        # Note: MT5 version uses broker time; here we use UTC - adjust per broker
        if hour < self.config.execution.start_hour or hour > self.config.execution.end_hour:
            return False, f"Outside hours {hour}:00"

        # spread
        if self.config.execution.use_spread_filter and spread_points > self.config.execution.max_spread_points:
            return False, f"Spread {spread_points} > {self.config.execution.max_spread_points}"

        # min bars between trades - approximate with time
        if self.last_trade_time:
            mins_since = (now - self.last_trade_time).total_seconds() / 60
            tf_mins = {"M1":1, "M5":5, "M15":15}.get(self.config.strategy.timeframe, 5)
            need = self.config.execution.min_bars_between_trades * tf_mins
            if mins_since < need:
                return False, f"Too soon {mins_since:.1f}min < {need}min"

        return True, "OK"

    def calculate_lots(self, balance: float, sl_points: float, tick_value: float, tick_size: float, point: float,
                       vol_min: float, vol_max: float, vol_step: float) -> float:
        """
        Position sizing: risk% of balance / SL distance
        Strictly capped for $10 account
        """
        if sl_points <= 0 or tick_value == 0:
            return self.config.risk.fixed_lot

        risk_money = balance * self.config.risk.risk_percent / 100.0

        # Cap for micro account
        if balance <= 15:
            risk_money = min(risk_money, 0.40)
            risk_money = max(risk_money, 0.10)
        elif balance <= 50:
            risk_money = min(risk_money, 1.0)

        sl_money_per_lot = (sl_points * point / tick_size) * tick_value
        if sl_money_per_lot <= 0:
            return self.config.risk.fixed_lot

        lots = risk_money / sl_money_per_lot

        # Round to step
        lots = (lots // vol_step) * vol_step
        lots = max(lots, vol_min)
        lots = min(lots, vol_max)
        lots = min(lots, self.config.risk.max_lot)

        # Extra safety tiers for $10
        if balance < 12 and lots > 0.01:
            lots = 0.01
        elif balance < 20 and lots > 0.02:
            lots = 0.02
        elif balance < 50 and lots > 0.05:
            lots = 0.05

        # Normalize
        # find decimals from vol_step
        import math
        decimals = max(0, int(round(-math.log10(vol_step))) if vol_step < 1 else 0)
        lots = round(lots, decimals)
        return lots

    def get_status(self, balance: float, equity: float) -> dict:
        pct = (equity - self.daily_start_balance) / max(self.daily_start_balance, 1) * 100
        return {
            "daily_start": self.daily_start_balance,
            "balance": balance,
            "equity": equity,
            "daily_pnl": equity - self.daily_start_balance,
            "daily_pnl_pct": pct,
            "trades_today": self.trades_today,
            "consecutive_losses": self.consecutive_losses,
            "cooldown_until": str(self.cooldown_until) if self.cooldown_until else None,
        }
