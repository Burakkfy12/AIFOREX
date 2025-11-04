from __future__ import annotations

import pandas as pd

from .base import Signal, StrategyBase


class BreakoutM30Strategy(StrategyBase):
    name = "breakout_M30"
    timeframe = "M30"

    def prepare(self, df: pd.DataFrame) -> None:
        super().prepare(df)
        df["high_roll"] = df["high"].rolling(window=24).max()
        df["low_roll"] = df["low"].rolling(window=24).min()

    def signal(self, df: pd.DataFrame) -> Signal:
        if len(df) < 30:
            return Signal("flat", 0.0, {})
        price = df["close"].iloc[-1]
        high_roll = df["high_roll"].iloc[-2]
        low_roll = df["low_roll"].iloc[-2]
        if price > high_roll:
            return Signal("long", 0.55, {"break": "up"})
        if price < low_roll:
            return Signal("short", 0.55, {"break": "down"})
        return Signal("flat", 0.0, {})


def get_strategy() -> BreakoutM30Strategy:
    return BreakoutM30Strategy()
