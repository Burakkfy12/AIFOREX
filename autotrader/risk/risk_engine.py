"""Risk management utilities for the HANN Autotrader."""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, Optional

from autotrader.utils.logger import logger


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
    max_slippage_points: float
    min_stop_distance_points: float
    lot_step: float
    lot_min: float
    important_events: list[str] = field(default_factory=list)
    lot_policy: Iterable[Dict[str, float]] = field(default_factory=list)
    kill_switch_on_broker_error: bool = True


def _round_to_step(value: float, step: float) -> float:
    return round(value / step) * step


class RiskEngine:
    def __init__(self, policy: RiskPolicy, lot_min: Optional[float] = None, lot_step: Optional[float] = None) -> None:
        self.policy = policy
        self.kill_switch_triggered = False
        self.lot_min = lot_min if lot_min is not None else policy.lot_min
        self.lot_step = lot_step if lot_step is not None else policy.lot_step

    def check_daily_dd(self, dd_pct: float) -> bool:
        if dd_pct >= self.policy.daily_max_drawdown_pct:
            self.kill_switch_triggered = True
            logger.warning("Daily drawdown %.2f%% breached, kill-switch engaged", dd_pct)
            return True
        return False

    def calc_lot(self, balance: float) -> float:
        if not self.policy.lot_policy:
            lot = self.lot_min
        else:
            lot = self.lot_min
            for tier in self.policy.lot_policy:
                min_bal = tier.get("balance_min", float("-inf"))
                max_bal = tier.get("balance_max")
                if max_bal is None:
                    in_range = balance >= min_bal
                else:
                    in_range = min_bal <= balance < max_bal or math.isclose(balance, max_bal, rel_tol=1e-9)
                if in_range:
                    lot = tier["lot"]
                    break
        lot = max(lot, self.lot_min)
        step = self.lot_step or 0.01
        rounded = _round_to_step(lot, step)
        rounded = max(self.lot_min, rounded)
        rounded = round(rounded, 6)
        logger.debug("Calculated lot %.4f (rounded %.4f) for balance %.2f", lot, rounded, balance)
        return rounded

    def spread_ok(self, spread: float) -> bool:
        ok = spread <= self.policy.spread_max_points
        if not ok:
            logger.info("Spread %.2f exceeds policy limit %.2f", spread, self.policy.spread_max_points)
        return ok

    def news_blackout(self, now: datetime, news_events: Iterable[Dict[str, Any]]) -> bool:
        window = timedelta(minutes=self.policy.news_blackout_minutes)
        important = {evt.upper() for evt in self.policy.important_events}
        for event in news_events:
            code = (event.get("event") or event.get("id") or event.get("name") or "").upper()
            if important and code not in important:
                continue
            raw_ts = event.get("ts") or event.get("time") or event.get("time_utc")
            if raw_ts is None:
                continue
            try:
                event_ts = datetime.fromisoformat(str(raw_ts).replace("Z", "+00:00"))
            except ValueError:
                logger.debug("Unable to parse event time %s", raw_ts)
                continue
            if event_ts.tzinfo is None:
                event_ts = event_ts.replace(tzinfo=timezone.utc)
            else:
                event_ts = event_ts.astimezone(timezone.utc)
            now_utc = now if now.tzinfo else now.replace(tzinfo=timezone.utc)
            if abs(now_utc - event_ts) <= window:
                logger.info("News blackout triggered by %s at %s", code, event_ts)
                return True
        return False

    def max_positions_ok(self, open_positions: int) -> bool:
        return open_positions < self.policy.max_positions


def load_policy(config: Dict[str, Any]) -> RiskPolicy:
    return RiskPolicy(**config)
