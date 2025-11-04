from __future__ import annotations

import pandas as pd

from .base import Signal, StrategyBase


class TrendM5Strategy(StrategyBase):
    name = "trend_M5"
    timeframe = "M5"

    def prepare(self, df: pd.DataFrame) -> None:
        super().prepare(df)
        df["ema_fast"] = df["close"].ewm(span=12).mean()
        df["ema_slow"] = df["close"].ewm(span=26).mean()

    def signal(self, df: pd.DataFrame) -> Signal:
        if len(df) < 30:
            return Signal("flat", 0.0, {})
        fast = df["ema_fast"].iloc[-1]
        slow = df["ema_slow"].iloc[-1]
        prev_fast = df["ema_fast"].iloc[-2]
        prev_slow = df["ema_slow"].iloc[-2]
        if fast > slow and prev_fast <= prev_slow:
            return Signal("long", 0.6, {"cross": "bull"})
        if fast < slow and prev_fast >= prev_slow:
            return Signal("short", 0.6, {"cross": "bear"})
        return Signal("flat", 0.0, {})


def get_strategy() -> TrendM5Strategy:
    return TrendM5Strategy()
