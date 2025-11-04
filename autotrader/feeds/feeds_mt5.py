from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, Optional

import pandas as pd

from autotrader.utils.logger import logger

try:  # pragma: no cover - optional dependency at runtime
    import MetaTrader5 as mt5  # type: ignore
except ImportError:  # pragma: no cover
    mt5 = None  # type: ignore


_TIMEFRAME_MAP = {
    "M1": "TIMEFRAME_M1",
    "M5": "TIMEFRAME_M5",
    "M15": "TIMEFRAME_M15",
    "M30": "TIMEFRAME_M30",
    "H1": "TIMEFRAME_H1",
    "H4": "TIMEFRAME_H4",
    "D1": "TIMEFRAME_D1",
}


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


def _tf_to_mt5(timeframe: str) -> Optional[int]:
    key = _TIMEFRAME_MAP.get(timeframe)
    if key is None:
        raise ValueError(f"Unsupported timeframe '{timeframe}'")
    if mt5 is None:
        return None
    return getattr(mt5, key)


class MT5Feed:
    """Wrapper around the MetaTrader5 python API with safe fallbacks."""

    def __init__(self, config: BrokerConfig) -> None:
        self.config = config
        self.connected = False

    def connect(self) -> bool:
        """Initialise MetaTrader and authenticate with the configured account."""
        if mt5 is None:
            logger.warning("MetaTrader5 package not available; running in offline mode")
            return False
        if not mt5.initialize():  # pragma: no cover - requires MT5 terminal
            last_error = getattr(mt5, "last_error", lambda: (None, ""))()
            logger.error("Failed to initialise MT5: %s", last_error)
            return False
        if not mt5.login(self.config.login, password=self.config.password, server=self.config.server):
            last_error = getattr(mt5, "last_error", lambda: (None, ""))()
            logger.error("Failed to login to MT5: %s", last_error)
            return False
        self.connected = True
        logger.info("Connected to MT5 server %s as login %s", self.config.server, self.config.login)
        return True

    def disconnect(self) -> None:
        if mt5 is not None and self.connected:
            mt5.shutdown()  # pragma: no cover - requires MT5 terminal
        self.connected = False

    def get_account_info(self) -> Dict[str, float]:
        if mt5 is None or not self.connected:
            logger.debug("Returning offline account info")
            return {"balance": 0.0, "equity": 0.0}
        info = mt5.account_info()  # pragma: no cover - requires MT5 terminal
        if info is None:
            logger.error("MT5 account_info returned None")
            return {"balance": 0.0, "equity": 0.0}
        return {"balance": info.balance, "equity": info.equity}

    def get_bars(self, symbol: str, timeframe: str, n: int = 1000) -> pd.DataFrame:
        columns = ["open", "high", "low", "close", "tick_volume"]
        if mt5 is None or not self.connected:
            logger.debug("Returning offline bars for %s/%s", symbol, timeframe)
            idx = pd.date_range(end=datetime.now(tz=timezone.utc), periods=n, freq="T")
            return pd.DataFrame(0.0, index=idx, columns=columns)

        mt5_tf = _tf_to_mt5(timeframe)
        rates = mt5.copy_rates_from_pos(symbol, mt5_tf, 0, n)  # pragma: no cover - requires MT5 terminal
        if rates is None or len(rates) == 0:
            logger.warning("No bars for %s %s", symbol, timeframe)
            return pd.DataFrame(columns=columns)
        df = pd.DataFrame(rates)
        if "time" not in df:
            logger.error("Rates payload missing time column for %s/%s", symbol, timeframe)
            return pd.DataFrame(columns=columns)
        df["time"] = pd.to_datetime(df["time"], unit="s", utc=True)
        if "real_volume" in df and "tick_volume" not in df:
            df.rename(columns={"real_volume": "tick_volume"}, inplace=True)
        df = df.set_index("time")
        for col in columns:
            if col not in df:
                df[col] = 0.0
        return df[columns]

    def get_tick(self, symbol: str) -> Dict[str, float]:
        if mt5 is None or not self.connected:
            return {"ask": 0.0, "bid": 0.0}
        tick = mt5.symbol_info_tick(symbol)  # pragma: no cover - requires MT5 terminal
        if tick is None:
            logger.error("symbol_info_tick returned None for %s", symbol)
            return {"ask": 0.0, "bid": 0.0}
        return {"ask": float(tick.ask), "bid": float(tick.bid)}

    def get_spread_points(self, symbol: str) -> float:
        if mt5 is None or not self.connected:
            logger.debug("Offline mode spread points fallback")
            return float("inf")
        tick = mt5.symbol_info_tick(symbol)  # pragma: no cover - requires MT5 terminal
        info = mt5.symbol_info(symbol)  # pragma: no cover - requires MT5 terminal
        if not tick or not info:
            logger.warning("tick/symbol_info missing for %s", symbol)
            return float("inf")
        point = info.point or 0.01
        spread_points = (float(tick.ask) - float(tick.bid)) / point
        return float(abs(spread_points))


def connect(config: Dict) -> MT5Feed:
    feed = MT5Feed(BrokerConfig(**config))
    feed.connect()
    return feed
