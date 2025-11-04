from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

import pandas as pd

try:  # pragma: no cover - optional dependency at runtime
    import MetaTrader5 as mt5
except ImportError:  # pragma: no cover
    mt5 = None


@dataclass
class BrokerConfig:
    server: str
    login: int
    password: str
    symbol: str
    timeframes: list[str]
    lot_min: float
    lot_step: float
    slippage_points: int


class MT5Feed:
    def __init__(self, config: BrokerConfig) -> None:
        self.config = config

    def connect(self) -> bool:
        if mt5 is None:
            return False
        if not mt5.initialize(server=self.config.server, login=self.config.login, password=self.config.password):
            return False
        return True

    def get_account_info(self) -> Dict[str, float]:
        if mt5 is None:
            return {"balance": 0.0, "equity": 0.0}
        info = mt5.account_info()
        return {"balance": info.balance, "equity": info.equity}

    def get_bars(self, symbol: str, timeframe: str, n: int) -> pd.DataFrame:
        if mt5 is None:
            return pd.DataFrame({
                "open": [0.0] * n,
                "high": [0.0] * n,
                "low": [0.0] * n,
                "close": [0.0] * n,
                "tick_volume": [0] * n,
            })
        tf = getattr(mt5, f"TIMEFRAME_{timeframe}")
        rates = mt5.copy_rates_from_pos(symbol, tf, 0, n)
        return pd.DataFrame(rates)

    def get_tick(self, symbol: str) -> Dict[str, float]:
        if mt5 is None:
            return {"ask": 0.0, "bid": 0.0}
        tick = mt5.symbol_info_tick(symbol)
        return {"ask": tick.ask, "bid": tick.bid}

    def get_spread(self, symbol: str) -> float:
        tick = self.get_tick(symbol)
        return abs(tick["ask"] - tick["bid"]) * 10_000


def connect(config: Dict) -> MT5Feed:
    feed = MT5Feed(BrokerConfig(**config))
    feed.connect()
    return feed
