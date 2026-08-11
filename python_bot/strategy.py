"""
Scalping Strategy: EMA 9/21 + RSI 14 + ATR 14
Timeframe M1/M5, quick scalp holding 5-90 minutes
"""
import numpy as np
import pandas as pd

try:
    import talib  # optional, if not available we use pandas
    HAS_TALIB = True
except:
    HAS_TALIB = False

def ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()

def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.where(delta > 0, 0).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    tr1 = high - low
    tr2 = (high - close.shift()).abs()
    tr3 = (low - close.shift()).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.rolling(window=period).mean()

class ScalpStrategy:
    def __init__(self, config):
        self.c = config.strategy

    def generate_signal(self, df: pd.DataFrame) -> dict:
        """
        df needs columns: open, high, low, close, tick_volume (optional)
        Returns: {"signal": 1 buy, -1 sell, 0 none, "sl_points": float, "tp_points": float, "reason": str}
        """
        if len(df) < max(self.c.ema_slow, self.c.rsi_period, self.c.atr_period) + 5:
            return {"signal": 0, "sl_points": 0, "tp_points": 0, "reason": "Not enough bars"}

        close = df["close"]
        high = df["high"]
        low = df["low"]

        df = df.copy()
        df["ema_fast"] = ema(close, self.c.ema_fast)
        df["ema_slow"] = ema(close, self.c.ema_slow)
        df["rsi"] = rsi(close, self.c.rsi_period)
        df["atr"] = atr(high, low, close, self.c.atr_period)

        last = df.iloc[-1]
        prev = df.iloc[-2]

        # point handling: for 5-digit forex point = 0.00001, for gold 0.01, for indices varies
        # We assume point inferred externally, here we work in price units
        point = 0.00001 if last["close"] < 10 else 0.01  # heuristic
        # But to match MQL: sl_points = ATR / point
        atr_price = last["atr"]
        if pd.isna(atr_price) or atr_price == 0:
            return {"signal": 0, "sl_points": 0, "tp_points": 0, "reason": "ATR NaN"}

        atr_points = atr_price / point

        # ATR filters - avoid flat or chaos
        if atr_points < self.c.min_atr_points:
            return {"signal": 0, "sl_points": 0, "tp_points": 0, "reason": f"ATR too low {atr_points:.0f}"}
        if atr_points > self.c.max_atr_points:
            return {"signal": 0, "sl_points": 0, "tp_points": 0, "reason": f"ATR too high {atr_points:.0f}"}

        sl_points = atr_points * self.c.atr_sl_mult
        tp_points = atr_points * self.c.atr_tp_mult

        # Clamp for scalp realism
        sl_points = max(80, min(sl_points, 600))
        tp_points = max(60, min(tp_points, 500))

        # EMA logic
        # Fresh cross OR continuation with slope
        # Use small tolerance for cross detection
        tol = point * 5
        ema_bull_cross = last["ema_fast"] > last["ema_slow"] and prev["ema_fast"] <= prev["ema_slow"] + tol
        ema_bear_cross = last["ema_fast"] < last["ema_slow"] and prev["ema_fast"] >= prev["ema_slow"] - tol

        ema_bull_cont = last["ema_fast"] > last["ema_slow"] and last["ema_fast"] > prev["ema_fast"]
        ema_bear_cont = last["ema_fast"] < last["ema_slow"] and last["ema_fast"] < prev["ema_fast"]

        rsi_val = last["rsi"]
        rsi_prev = prev["rsi"]

        # BUY
        if (ema_bull_cross or ema_bull_cont) and self.c.rsi_buy_min <= rsi_val <= self.c.rsi_buy_max and last["close"] > last["ema_slow"]:
            # rising momentum filter
            if rsi_val > rsi_prev - 2:
                return {"signal": 1, "sl_points": sl_points, "tp_points": tp_points,
                        "reason": f"BUY ema {last['ema_fast']:.5f}>{last['ema_slow']:.5f} rsi {rsi_val:.1f} atr {atr_points:.0f}",
                        "rsi": rsi_val, "atr_points": atr_points}

        # SELL
        if (ema_bear_cross or ema_bear_cont) and self.c.rsi_sell_min <= rsi_val <= self.c.rsi_sell_max and last["close"] < last["ema_slow"]:
            if rsi_val < rsi_prev + 2:
                return {"signal": -1, "sl_points": sl_points, "tp_points": tp_points,
                        "reason": f"SELL ema {last['ema_fast']:.5f}<{last['ema_slow']:.5f} rsi {rsi_val:.1f} atr {atr_points:.0f}",
                        "rsi": rsi_val, "atr_points": atr_points}

        return {"signal": 0, "sl_points": sl_points, "tp_points": tp_points, "reason": f"No signal rsi {rsi_val:.1f} ema {last['ema_fast']:.5f}/{last['ema_slow']:.5f}"}

    def should_exit_time(self, entry_time, current_time, max_hold_minutes: int) -> bool:
        if max_hold_minutes <= 0:
            return False
        elapsed = (current_time - entry_time).total_seconds() / 60
        return elapsed >= max_hold_minutes

    def get_breakeven_sl(self, entry_price: float, current_price: float, position_type: str, point: float,
                         trigger_points: float, plus_points: float, current_sl: float) -> float | None:
        profit_points = (current_price - entry_price)/point if position_type=="buy" else (entry_price - current_price)/point
        if profit_points < trigger_points:
            return None
        if position_type == "buy":
            new_sl = entry_price + plus_points * point
            if current_sl is None or current_sl < new_sl:
                return new_sl
        else:
            new_sl = entry_price - plus_points * point
            if current_sl is None or current_sl > new_sl:
                return new_sl
        return None

    def get_trailing_sl(self, entry_price: float, current_price: float, position_type: str, point: float,
                        start_points: float, step_points: float, current_sl: float) -> float | None:
        profit_points = (current_price - entry_price)/point if position_type=="buy" else (entry_price - current_price)/point
        if profit_points < start_points:
            return None
        if position_type == "buy":
            trail = current_price - step_points * point
            if current_sl is None or trail > current_sl:
                return trail
        else:
            trail = current_price + step_points * point
            if current_sl is None or trail < current_sl:
                return trail
        return None
