"""
Config for $10 Micro Scalp Bot
All values conservative for tiny account survival + fast compounding
"""
from dataclasses import dataclass, field

@dataclass
class RiskConfig:
    risk_percent: float = 1.5          # % per trade
    fixed_lot: float = 0.01            # minimum lot
    max_lot: float = 0.05              # HARD CAP for $10
    max_daily_loss_pct: float = 5.0    # stop day if -5%
    daily_target_pct: float = 4.0      # stop day if +4% (lock profit)
    max_trades_per_day: int = 12
    max_consecutive_losses: int = 3
    cooldown_minutes: int = 45
    balance_protection_equity: float = 5.0  # emergency stop if equity < $5

@dataclass
class StrategyConfig:
    timeframe: str = "M5"  # M1, M5, M15
    ema_fast: int = 9
    ema_slow: int = 21
    rsi_period: int = 14
    rsi_buy_min: float = 50
    rsi_buy_max: float = 68
    rsi_sell_min: float = 32
    rsi_sell_max: float = 50
    atr_period: int = 14
    atr_sl_mult: float = 1.8
    atr_tp_mult: float = 1.2
    min_atr_points: float = 50
    max_atr_points: float = 800

@dataclass
class ExecutionConfig:
    symbol: str = "EURUSD"  # or "XAUUSD", "GBPUSD", "Volatility 75 Index"
    magic: int = 101010
    comment: str = "Micro10$"
    max_spread_points: int = 250
    use_spread_filter: bool = True
    start_hour: int = 0
    end_hour: int = 23
    min_bars_between_trades: int = 3
    deviation: int = 30

@dataclass
class ExitConfig:
    use_breakeven: bool = True
    breakeven_trigger_points: float = 100
    breakeven_plus_points: float = 50
    use_trailing: bool = True
    trailing_start_points: float = 120
    trailing_step_points: float = 60
    max_hold_minutes: int = 90

@dataclass
class BotConfig:
    risk: RiskConfig = field(default_factory=RiskConfig)
    strategy: StrategyConfig = field(default_factory=StrategyConfig)
    execution: ExecutionConfig = field(default_factory=ExecutionConfig)
    exit: ExitConfig = field(default_factory=ExitConfig)
    # MT5 Login (fill via .env)
    mt5_login: int = 0
    mt5_password: str = ""
    mt5_server: str = ""
    mt5_path: str = ""  # optional

# Pre-tuned presets for $10
PRESETS = {
    "EURUSD_M5": BotConfig(
        execution=ExecutionConfig(symbol="EURUSD", max_spread_points=20),
        strategy=StrategyConfig(atr_sl_mult=1.5, atr_tp_mult=1.0),
    ),
    "XAUUSD_M5": BotConfig(
        execution=ExecutionConfig(symbol="XAUUSD", max_spread_points=400),
        strategy=StrategyConfig(atr_sl_mult=1.8, atr_tp_mult=1.2, min_atr_points=80, max_atr_points=1500),
        risk=RiskConfig(risk_percent=1.2, max_lot=0.02),  # gold is volatile, reduce risk
    ),
    "GBPUSD_M1": BotConfig(
        execution=ExecutionConfig(symbol="GBPUSD", max_spread_points=25),
        strategy=StrategyConfig(timeframe="M1", ema_fast=8, ema_slow=21),
    ),
    "VOLATILITY75_M1": BotConfig(
        execution=ExecutionConfig(symbol="Volatility 75 Index", max_spread_points=800),
        strategy=StrategyConfig(timeframe="M1", atr_sl_mult=2.0, atr_tp_mult=1.5, min_atr_points=200, max_atr_points=50000),
        risk=RiskConfig(risk_percent=1.0, max_lot=0.02),
    ),
    # === MAX POTENTIAL (optimized by 1500-bar momentum synthetic, 15-25 iters) ===
    # EURUSD +35.04% in 5.2 days synthetic (PF 2.99, WR 85.7%, DD 5.1%) vs baseline +7.58% PF 1.96
    "EURUSD_M5_MAX": BotConfig(
        execution=ExecutionConfig(symbol="EURUSD", max_spread_points=20, start_hour=7, end_hour=17, min_bars_between_trades=2),
        strategy=StrategyConfig(ema_fast=9, ema_slow=21, rsi_period=14, rsi_buy_min=50, rsi_buy_max=72, rsi_sell_min=32, rsi_sell_max=48, atr_period=14, atr_sl_mult=2.2, atr_tp_mult=1.2, min_atr_points=40, max_atr_points=1200),
        risk=RiskConfig(risk_percent=2.2, max_lot=0.05, max_daily_loss_pct=5.0, daily_target_pct=5.0, max_trades_per_day=18, max_consecutive_losses=3, cooldown_minutes=30),
        exit=ExitConfig(breakeven_trigger_points=100, breakeven_plus_points=50, trailing_start_points=120, trailing_step_points=60, max_hold_minutes=90)
    ),
    # XAUUSD +20.38% in 5.2 days (PF 2.62, WR 82.9%, DD 7.2%) vs baseline +6.16% PF 2.28
    "XAUUSD_M5_MAX": BotConfig(
        execution=ExecutionConfig(symbol="XAUUSD", max_spread_points=350, start_hour=7, end_hour=17),
        strategy=StrategyConfig(ema_fast=8, ema_slow=26, rsi_period=14, rsi_buy_min=55, rsi_buy_max=65, rsi_sell_min=35, rsi_sell_max=52, atr_period=14, atr_sl_mult=1.8, atr_tp_mult=0.9, min_atr_points=60, max_atr_points=2000),
        risk=RiskConfig(risk_percent=2.0, max_lot=0.03, max_daily_loss_pct=5.0, daily_target_pct=6.0, max_trades_per_day=15, max_consecutive_losses=3, cooldown_minutes=30),
        exit=ExitConfig(breakeven_trigger_points=120, breakeven_plus_points=60, trailing_start_points=90, trailing_step_points=40, max_hold_minutes=150)
    ),
    "GBPUSD_M1_MAX": BotConfig(
        execution=ExecutionConfig(symbol="GBPUSD", max_spread_points=25, start_hour=7, end_hour=17),
        strategy=StrategyConfig(timeframe="M1", ema_fast=8, ema_slow=21, rsi_period=12, rsi_buy_min=48, rsi_buy_max=68, rsi_sell_min=32, rsi_sell_max=50, atr_period=10, atr_sl_mult=1.5, atr_tp_mult=1.2, min_atr_points=40, max_atr_points=800),
        risk=RiskConfig(risk_percent=1.8, max_lot=0.05, max_daily_loss_pct=5.0, daily_target_pct=5.0, max_trades_per_day=18),
        exit=ExitConfig(breakeven_trigger_points=90, breakeven_plus_points=50, trailing_start_points=100, trailing_step_points=50, max_hold_minutes=90)
    ),
    "VOLATILITY75_M1_MAX": BotConfig(
        execution=ExecutionConfig(symbol="Volatility 75 Index", max_spread_points=700, start_hour=0, end_hour=23),
        strategy=StrategyConfig(timeframe="M1", ema_fast=7, ema_slow=20, rsi_period=10, rsi_buy_min=48, rsi_buy_max=70, rsi_sell_min=30, rsi_sell_max=52, atr_period=10, atr_sl_mult=1.8, atr_tp_mult=1.4, min_atr_points=150, max_atr_points=60000),
        risk=RiskConfig(risk_percent=1.5, max_lot=0.02, max_daily_loss_pct=5.0, daily_target_pct=6.0, max_trades_per_day=20),
        exit=ExitConfig(breakeven_trigger_points=100, breakeven_plus_points=50, trailing_start_points=120, trailing_step_points=60, max_hold_minutes=60)
    ),
}
