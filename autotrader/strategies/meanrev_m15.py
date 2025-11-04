from __future__ import annotations

import pandas as pd

from .base import Signal, StrategyBase


class MeanRevM15Strategy(StrategyBase):
    name = "meanrev_M15"
    timeframe = "M15"

    def prepare(self, df: pd.DataFrame) -> None:
        super().prepare(df)
        df["sma"] = df["close"].rolling(window=20).mean()
        df["std"] = df["close"].rolling(window=20).std()

    def signal(self, df: pd.DataFrame) -> Signal:
        if len(df) < 25:
            return Signal("flat", 0.0, {})
        price = df["close"].iloc[-1]
        sma = df["sma"].iloc[-1]
        std = df["std"].iloc[-1]
        if price < sma - std:
            return Signal("long", 0.5, {"z": (price - sma) / std})
        if price > sma + std:
            return Signal("short", 0.5, {"z": (price - sma) / std})
        return Signal("flat", 0.0, {})


def get_strategy() -> MeanRevM15Strategy:
    return MeanRevM15Strategy()
