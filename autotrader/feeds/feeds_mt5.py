from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict

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

    def _resolve_timeframe(self, timeframe: str):
        key = _TIMEFRAME_MAP.get(timeframe)
        if key is None:
            raise ValueError(f"Unsupported timeframe '{timeframe}'")
        if mt5 is None:
            return None
        return getattr(mt5, key)

    def get_bars(self, symbol: str, timeframe: str, n: int = 1000) -> pd.DataFrame:
        columns = ["open", "high", "low", "close", "tick_volume", "spread", "real_volume"]
        if mt5 is None or not self.connected:
            logger.debug("Returning offline bars for %s/%s", symbol, timeframe)
            idx = pd.date_range(end=datetime.now(tz=timezone.utc), periods=n, freq="T")
            return pd.DataFrame(0.0, index=idx, columns=columns[:-2]).assign(spread=0.0, real_volume=0.0)

        mt5_tf = self._resolve_timeframe(timeframe)
        rates = mt5.copy_rates_from_pos(symbol, mt5_tf, 0, n)  # pragma: no cover - requires MT5 terminal
        if rates is None:
            logger.error("MT5 returned no rates for %s/%s", symbol, timeframe)
            return pd.DataFrame(columns=columns)
        if len(rates) == 0:
            logger.warning("MT5 returned empty rates for %s/%s", symbol, timeframe)
            return pd.DataFrame(columns=columns)
        df = pd.DataFrame(rates)
        if "time" not in df:
            logger.error("Rates payload missing time column for %s/%s", symbol, timeframe)
            return pd.DataFrame(columns=columns)
        df["time"] = pd.to_datetime(df["time"], unit="s", utc=True)
        df.set_index("time", inplace=True)
        # Ensure expected columns exist for downstream calculations
        for col in columns:
            if col not in df:
                df[col] = 0.0
        df = df[columns]
        return df

    def get_tick(self, symbol: str) -> Dict[str, float]:
        if mt5 is None or not self.connected:
            return {"ask": 0.0, "bid": 0.0}
        tick = mt5.symbol_info_tick(symbol)  # pragma: no cover - requires MT5 terminal
        if tick is None:
            logger.error("symbol_info_tick returned None for %s", symbol)
            return {"ask": 0.0, "bid": 0.0}
        return {"ask": float(tick.ask), "bid": float(tick.bid)}

    def get_spread(self, symbol: str) -> float:
        tick = self.get_tick(symbol)
        if mt5 is None or not self.connected:
            return 0.0
        info = mt5.symbol_info(symbol)  # pragma: no cover - requires MT5 terminal
        if info is None or info.point == 0:
            logger.error("symbol_info invalid for %s", symbol)
            return 0.0
        spread_points = (tick["ask"] - tick["bid"]) / info.point
        return float(abs(spread_points))


def connect(config: Dict) -> MT5Feed:
    feed = MT5Feed(BrokerConfig(**config))
    feed.connect()
    return feed
