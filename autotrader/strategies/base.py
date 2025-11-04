"""Strategy base classes."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

import numpy as np
import pandas as pd


@dataclass
class Signal:
    direction: str
    confidence: float
    meta: Dict[str, float]


class StrategyBase:
    name: str = "base"
    timeframe: str = "M1"

    def prepare(self, df: pd.DataFrame) -> None:
        """Perform indicator calculations in place."""
        if "close" not in df:
            raise ValueError("DataFrame must contain OHLC data")

    def signal(self, df: pd.DataFrame) -> Signal:
        return Signal(direction="flat", confidence=0.0, meta={})

    def stop_take(self, df: pd.DataFrame, risk_policy) -> Dict[str, float]:
        atr = df.get("atr", pd.Series([np.nan])).iloc[-1]
        price = df["close"].iloc[-1]
        stop = price - atr * risk_policy.atr_stop_mult
        take = price + atr * risk_policy.atr_trail_mult
        return {"sl": float(stop), "tp": float(take)}
