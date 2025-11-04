from __future__ import annotations

from datetime import datetime, timedelta, timezone

from autotrader.risk.risk_engine import RiskEngine, RiskPolicy


def _policy() -> RiskPolicy:
    return RiskPolicy(
        symbol="XAUUSD",
        daily_max_drawdown_pct=10,
        max_positions=1,
        per_trade_risk_pct=1.0,
        spread_max_points=35,
        news_blackout_minutes=20,
        atr_stop_mult=1.8,
        atr_trail_mult=1.2,
        max_slippage_points=30,
        min_stop_distance_points=100,
        lot_step=0.01,
        lot_min=0.01,
        important_events=["US_NFP"],
        lot_policy=[
            {"balance_max": 100, "lot": 0.05},
            {"balance_min": 100, "balance_max": 500, "lot": 0.1},
            {"balance_min": 500, "balance_max": 2000, "lot": 0.5},
        ],
        kill_switch_on_broker_error=True,
    )


def test_risk_engine_checkers():
    engine = RiskEngine(_policy(), lot_min=0.05, lot_step=0.01)

    assert engine.check_daily_dd(12.0) is True
    assert engine.kill_switch_triggered is True
    assert engine.spread_ok(20.0) is True
    assert engine.spread_ok(50.0) is False

    now = datetime.now(timezone.utc)
    events = [{"event": "US_NFP", "ts": (now + timedelta(minutes=5)).isoformat()}]
    assert engine.news_blackout(now, events) is True
    assert engine.news_blackout(now, [{"event": "OTHER", "ts": (now + timedelta(minutes=5)).isoformat()}]) is False
    assert engine.max_positions_ok(0) is True
    assert engine.max_positions_ok(1) is False


def test_calc_lot_rounding():
    engine = RiskEngine(_policy(), lot_min=0.05, lot_step=0.01)
    assert engine.calc_lot(50) == 0.05
    assert engine.calc_lot(150) == 0.1
    assert engine.calc_lot(1000) == 0.5
