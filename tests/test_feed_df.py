from __future__ import annotations

from types import SimpleNamespace

import pytest

pd = pytest.importorskip("pandas")

from autotrader.feeds import feeds_mt5
from autotrader.feeds.feeds_mt5 import BrokerConfig, MT5Feed


class DummyMT5:
    TIMEFRAME_M5 = 1

    def __init__(self) -> None:
        self._ticks = SimpleNamespace(ask=1920.1, bid=1920.0)
        self._info = SimpleNamespace(point=0.01)

    def initialize(self):  # pragma: no cover - used in tests
        return True

    def login(self, *args, **kwargs):  # pragma: no cover - used in tests
        return True

    def copy_rates_from_pos(self, symbol, timeframe, start, count):  # pragma: no cover
        return [
            {
                "time": 1_700_000_000,
                "open": 1900.0,
                "high": 1905.0,
                "low": 1895.0,
                "close": 1902.0,
                "tick_volume": 150,
                "spread": 5,
                "real_volume": 120,
            }
        ]

    def symbol_info_tick(self, symbol):  # pragma: no cover
        return self._ticks

    def symbol_info(self, symbol):  # pragma: no cover
        return self._info


def test_get_bars_returns_utc(monkeypatch):
    dummy = DummyMT5()
    monkeypatch.setattr(feeds_mt5, "mt5", dummy)
    feed = MT5Feed(
        BrokerConfig(
            server="demo",
            login=1,
            password="x",
            symbol="XAUUSD",
            timeframes=["M5"],
            lot_min=0.01,
            lot_step=0.01,
            slippage_points=30,
        )
    )

    assert feed.connect() is True
    df = feed.get_bars("XAUUSD", "M5", 1)
    assert not df.empty
    assert isinstance(df.index, pd.DatetimeIndex)
    assert df.index.tz is not None

    spread = feed.get_spread("XAUUSD")
    assert spread == 10.0
