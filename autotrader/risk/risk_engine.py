"""Risk management utilities for the HANN Autotrader."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List

from autotrader.utils.logger import logger


@dataclass
class RiskPolicy:
    daily_max_drawdown_pct: float
    spread_max_points: float
    max_positions: int
    news_blackout_minutes: int
    lot_min: float
    lot_step: float
    max_slippage_points: float
    min_stop_distance_points: float
    symbol: str | None = None
    important_events: List[str] = field(default_factory=list)
    per_trade_risk_pct: float | None = None
    atr_stop_mult: float | None = None
    atr_trail_mult: float | None = None
    lot_policy: List[Dict[str, Any]] = field(default_factory=list)
    kill_switch_on_broker_error: bool = True


class RiskEngine:
    def __init__(self, policy: RiskPolicy) -> None:
        self.policy = policy
        self.kill_switch_triggered = False

    def check_daily_dd(self, dd_pct: float) -> bool:
        if dd_pct >= self.policy.daily_max_drawdown_pct:
            self.kill_switch_triggered = True
            logger.warning(
                "Daily drawdown %.2f%% breached (limit %.2f%%)",
                dd_pct,
                self.policy.daily_max_drawdown_pct,
            )
            return True
        return False

    def spread_ok(self, spread_points: float) -> bool:
        ok = spread_points <= self.policy.spread_max_points
        if not ok:
            logger.info(
                "Spread %.2f points exceeds policy limit %.2f",
                spread_points,
                self.policy.spread_max_points,
            )
        return ok

    def max_positions_ok(self, open_positions: int) -> bool:
        ok = open_positions < self.policy.max_positions
        if not ok:
            logger.info(
                "Open positions %s reached policy cap %s",
                open_positions,
                self.policy.max_positions,
            )
        return ok

    def calc_lot(self, balance: float) -> float:
        raw = max(self.policy.lot_min, self.policy.lot_min)
        step = self.policy.lot_step or 0.01
        rounded = round(raw / step) * step
        rounded = max(self.policy.lot_min, rounded)
        rounded = round(rounded, 6)
        logger.debug("Calculated lot %.4f (rounded %.4f) for balance %.2f", raw, rounded, balance)
        return rounded

    def news_blackout(self, now_utc: datetime, events: Iterable[dict[str, Any]]) -> bool:
        if self.policy.news_blackout_minutes <= 0:
            return False
        if now_utc.tzinfo is None:
            now_utc = now_utc.replace(tzinfo=timezone.utc)
        else:
            now_utc = now_utc.astimezone(timezone.utc)
        window = timedelta(minutes=self.policy.news_blackout_minutes)
        important = {evt.upper() for evt in self.policy.important_events}
        for event in events:
            name = str(
                event.get("event")
                or event.get("id")
                or event.get("name")
                or ""
            ).upper()
            if important and name and name not in important:
                continue
            raw_ts = event.get("time_utc") or event.get("ts") or event.get("time")
            if raw_ts is None:
                continue
            event_ts = _coerce_datetime(raw_ts)
            if event_ts is None:
                continue
            delta = now_utc - event_ts
            if abs(delta) <= window:
                logger.info("News blackout triggered by %s at %s", name or "event", event_ts)
                return True
        return False


def _coerce_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    try:
        text = str(value).replace("Z", "+00:00")
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        else:
            dt = dt.astimezone(timezone.utc)
        return dt
    except Exception:
        logger.debug("Unable to parse datetime from %s", value)
        return None


def load_policy(config: dict[str, Any]) -> RiskPolicy:
    return RiskPolicy(**config)
