from __future__ import annotations

import pandas as pd

from .base import Signal, StrategyBase


class DoguSarStrategy(StrategyBase):
    name = "dogu_sar_M15"
    timeframe = "M15"

    def prepare(self, df: pd.DataFrame) -> None:
        super().prepare(df)
        df["sar"] = df["close"].ewm(span=5).mean()
        df["psar_dir"] = (df["close"] > df["sar"]).astype(int)

    def signal(self, df: pd.DataFrame) -> Signal:
        if len(df) < 10:
            return Signal("flat", 0.0, {})
        direction = df["psar_dir"].iloc[-1]
        prev_direction = df["psar_dir"].iloc[-2]
        if direction == 1 and prev_direction == 0:
            return Signal("long", 0.6, {"psar_flip": "up"})
        if direction == 0 and prev_direction == 1:
            return Signal("short", 0.6, {"psar_flip": "down"})
        return Signal("flat", 0.0, {})


def get_strategy() -> DoguSarStrategy:
    return DoguSarStrategy()
