from __future__ import annotations

from datetime import datetime, timezone

import pytest

from autotrader.risk.risk_engine import RiskEngine, RiskPolicy


def test_spread_gate():
    policy = RiskPolicy(
        daily_max_drawdown_pct=10,
        spread_max_points=35,
        max_positions=1,
        news_blackout_minutes=20,
        lot_min=0.01,
        lot_step=0.01,
        max_slippage_points=30,
        min_stop_distance_points=100,
    )
    engine = RiskEngine(policy)
    assert engine.spread_ok(20.0) is True
    assert engine.spread_ok(50.0) is False


def test_news_blackout_and_lot_rounding():
    policy = RiskPolicy(
        daily_max_drawdown_pct=10,
        spread_max_points=35,
        max_positions=1,
        news_blackout_minutes=20,
        lot_min=0.01,
        lot_step=0.01,
        max_slippage_points=30,
        min_stop_distance_points=100,
        important_events=["US_NFP"],
        lot_policy=[
            {"balance_max": 100, "lot": 0.05},
            {"balance_min": 100, "balance_max": 500, "lot": 0.1},
        ],
    )
    engine = RiskEngine(policy)
    now = datetime.now(timezone.utc)
    event = {"event": "US_NFP", "time_utc": now.isoformat()}
    assert engine.news_blackout(now, [event]) is True
    assert engine.news_blackout(now, []) is False
    lot_small = engine.calc_lot(50.0)
    lot_large = engine.calc_lot(250.0)
    assert lot_small == pytest.approx(0.05)
    assert lot_large == pytest.approx(0.1)
