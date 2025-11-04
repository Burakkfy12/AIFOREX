from __future__ import annotations

import time
from typing import Dict, Optional

from autotrader.utils.logger import logger

from autotrader.feeds.feeds_mt5 import BrokerConfig
from autotrader.risk.risk_engine import RiskPolicy

try:  # pragma: no cover - optional dependency at runtime
    import MetaTrader5 as mt5  # type: ignore
except ImportError:  # pragma: no cover
    mt5 = None  # type: ignore


class MT5Broker:
    """Execution helper for MetaTrader5 with retry/backoff and guardrails."""

    def __init__(self, config: BrokerConfig, policy: Optional[RiskPolicy] = None) -> None:
        self.config = config
        self.policy = policy
        self.connected = False

    def connect(self) -> bool:
        if mt5 is None:
            logger.warning("MetaTrader5 package not available; broker running in simulation mode")
            return False
        if not mt5.initialize():  # pragma: no cover - requires MT5 terminal
            logger.error("Failed to initialise MT5 for broker: %s", getattr(mt5, "last_error", lambda: "")())
            return False
        if not mt5.login(self.config.login, password=self.config.password, server=self.config.server):
            logger.error("Failed to login MT5 broker: %s", getattr(mt5, "last_error", lambda: "")())
            return False
        self.connected = True
        logger.info("Broker connected to MT5 server %s", self.config.server)
        return True

    def disconnect(self) -> None:
        if mt5 is not None and self.connected:
            mt5.shutdown()  # pragma: no cover - requires MT5 terminal
        self.connected = False

    def _current_price(self, symbol: str, direction: str) -> float:
        if mt5 is None or not self.connected:
            return 0.0
        tick = mt5.symbol_info_tick(symbol)  # pragma: no cover - requires MT5 terminal
        if tick is None:
            raise RuntimeError(f"symbol_info_tick returned None for {symbol}")
        return float(tick.ask if direction == "long" else tick.bid)

    def _adjust_stops(
        self, symbol: str, price: float, sl: Optional[float], tp: Optional[float]
    ) -> tuple[Optional[float], Optional[float]]:
        if mt5 is None or not self.connected:
            return sl, tp
        info = mt5.symbol_info(symbol)  # pragma: no cover - requires MT5 terminal
        if info is None:
            return sl, tp
        point = info.point or 0.0
        policy_points = self.policy.min_stop_distance_points if self.policy else 0.0
        min_dist = max(policy_points, getattr(info, "stops_level", 0.0)) * point
        if min_dist <= 0:
            return sl, tp

        def ensure_distance(target: Optional[float], bias: int) -> Optional[float]:
            if target is None:
                return None
            if abs(target - price) >= min_dist:
                return target
            adjusted = price + bias * min_dist
            logger.debug(
                "Adjusting stop level from %.5f to %.5f to satisfy min distance %.5f",
                target,
                adjusted,
                min_dist,
            )
            return adjusted

        sl_bias = -1 if sl is None or sl <= price else 1
        tp_bias = 1 if tp is None or tp >= price else -1
        sl = ensure_distance(sl, sl_bias)
        tp = ensure_distance(tp, tp_bias)
        return sl, tp

    def place_order(
        self,
        symbol: str,
        direction: str,
        lot: float,
        sl: Optional[float],
        tp: Optional[float],
        slippage_points: Optional[int],
        filling: str = "FOK",
        max_retries: int = 3,
    ) -> Dict[str, object]:
        if mt5 is None or not self.connected:
            logger.info("Simulated order %s lot=%.2f", direction, lot)
            return {"ticket": 0, "status": "simulated", "reason": "offline"}

        price = self._current_price(symbol, direction)
        sl, tp = self._adjust_stops(symbol, price, sl, tp)
        order_type = mt5.ORDER_TYPE_BUY if direction == "long" else mt5.ORDER_TYPE_SELL
        deviation = int(
            slippage_points
            if slippage_points is not None
            else (self.policy.max_slippage_points if self.policy else self.config.slippage_points)
        )
        filling_map = {
            "FOK": getattr(mt5, "ORDER_FILLING_FOK", None),
            "IOC": getattr(mt5, "ORDER_FILLING_IOC", None),
        }
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": float(lot),
            "type": order_type,
            "price": price,
            "sl": sl,
            "tp": tp,
            "deviation": deviation,
            "type_filling": filling_map.get(filling.upper(), filling_map.get("FOK")),
            "type_time": mt5.ORDER_TIME_GTC,
        }

        attempt = 0
        last_comment = ""
        while attempt <= max_retries:
            attempt += 1
            result = mt5.order_send(request)  # pragma: no cover - requires MT5 terminal
            if result and result.retcode == mt5.TRADE_RETCODE_DONE:
                logger.info("Order filled ticket=%s price=%.5f", result.order, result.price)
                return {
                    "ticket": int(result.order),
                    "status": "filled",
                    "price": float(result.price),
                    "sl": sl,
                    "tp": tp,
                }
            last_comment = getattr(result, "comment", "unknown") if result else "no_result"
            logger.warning("Order attempt %s failed: %s", attempt, last_comment)
            if request["type_filling"] == filling_map.get("FOK"):
                request["type_filling"] = filling_map.get("IOC")
            time.sleep(min(0.5 * attempt, 2.0))
        error = getattr(mt5, "last_error", lambda: (None, ""))()
        logger.error("Order failed after %s attempts: %s", max_retries + 1, error)
        return {"ticket": 0, "status": "error", "reason": last_comment, "error": error}

    def close_position(self, ticket: int, slippage_points: Optional[int] = None) -> Dict[str, object]:
        if mt5 is None or not self.connected:
            logger.info("Simulated close position ticket=%s", ticket)
            return {"ticket": ticket, "status": "simulated", "reason": "offline"}
        positions = mt5.positions_get(ticket=ticket)  # pragma: no cover - requires MT5 terminal
        if not positions:
            logger.warning("No position found for ticket %s", ticket)
            return {"ticket": ticket, "status": "not_found"}
        pos = positions[0]
        direction = "long" if pos.type == mt5.POSITION_TYPE_BUY else "short"
        symbol = pos.symbol
        price = self._current_price(symbol, direction)
        order_type = mt5.ORDER_TYPE_SELL if direction == "long" else mt5.ORDER_TYPE_BUY
        deviation = int(
            slippage_points
            if slippage_points is not None
            else (self.policy.max_slippage_points if self.policy else self.config.slippage_points)
        )
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": float(pos.volume),
            "type": order_type,
            "position": ticket,
            "price": price,
            "deviation": deviation,
            "type_filling": getattr(mt5, "ORDER_FILLING_IOC", None),
            "type_time": mt5.ORDER_TIME_GTC,
        }
        result = mt5.order_send(request)  # pragma: no cover - requires MT5 terminal
        if result and result.retcode == mt5.TRADE_RETCODE_DONE:
            logger.info("Closed position ticket=%s price=%.5f", ticket, result.price)
            return {"ticket": int(result.order), "status": "closed", "price": float(result.price)}
        comment = getattr(result, "comment", "unknown") if result else "no_result"
        logger.error("Failed to close ticket %s: %s", ticket, comment)
        return {"ticket": ticket, "status": "failed", "reason": comment}


def connect(config: Dict, policy: Optional[RiskPolicy] = None) -> MT5Broker:
    broker = MT5Broker(BrokerConfig(**config), policy=policy)
    broker.connect()
    return broker
