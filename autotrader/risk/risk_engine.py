"""Risk management utilities for the HANN Autotrader."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, Iterable

from loguru import logger


@dataclass
class RiskPolicy:
    symbol: str
    daily_max_drawdown_pct: float
    max_positions: int
    per_trade_risk_pct: float
    spread_max_points: float
    news_blackout_minutes: int
    atr_stop_mult: float
    atr_trail_mult: float
    lot_policy: Iterable[Dict[str, float]]
    kill_switch_on_broker_error: bool


class RiskEngine:
    def __init__(self, policy: RiskPolicy) -> None:
        self.policy = policy
        self.kill_switch_triggered = False

    def check_daily_dd(self, dd_pct: float) -> bool:
        if dd_pct >= self.policy.daily_max_drawdown_pct:
            self.kill_switch_triggered = True
            logger.warning("Daily drawdown %.2f%% breached, kill-switch engaged", dd_pct)
            return True
        return False

    def calc_lot(self, balance: float) -> float:
        lot = 0.01
        for tier in self.policy.lot_policy:
            min_bal = tier.get("balance_min", 0)
            max_bal = tier.get("balance_max", float("inf"))
            if min_bal <= balance < max_bal:
                lot = tier["lot"]
                break
        logger.debug("Calculated lot %.2f for balance %.2f", lot, balance)
        return lot

    def spread_ok(self, spread: float) -> bool:
        ok = spread <= self.policy.spread_max_points
        if not ok:
            logger.info("Spread %.2f exceeds policy limit %.2f", spread, self.policy.spread_max_points)
        return ok

    def news_blackout(self, now: datetime, news_events: Iterable[Dict[str, str]]) -> bool:
        blackout_delta = timedelta(minutes=self.policy.news_blackout_minutes)
        for event in news_events:
            ts = event.get("ts")
            if not ts:
                continue
            event_ts = datetime.fromisoformat(ts)
            if abs(now - event_ts) <= blackout_delta:
                logger.info("News blackout due to event %s at %s", event.get("event"), event_ts)
                return True
        return False

    def max_positions_ok(self, open_positions: int) -> bool:
        return open_positions < self.policy.max_positions


def load_policy(config: Dict[str, Any]) -> RiskPolicy:
    return RiskPolicy(**config)
