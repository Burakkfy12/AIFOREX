from __future__ import annotations

import time
from typing import Dict, Optional

from autotrader.utils.logger import logger

from autotrader.feeds.feeds_mt5 import BrokerConfig

try:  # pragma: no cover - optional dependency at runtime
    import MetaTrader5 as mt5  # type: ignore
except ImportError:  # pragma: no cover
    mt5 = None  # type: ignore


class MT5Broker:
    """Execution helper for MetaTrader5 with retry/backoff and guardrails."""

    def __init__(self, config: BrokerConfig) -> None:
        self.config = config
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

    def _enforce_stop_distance(self, symbol: str, direction: str, price: float, sl: Optional[float], tp: Optional[float]) -> tuple[Optional[float], Optional[float]]:
        if mt5 is None or not self.connected:
            return sl, tp
        info = mt5.symbol_info(symbol)  # pragma: no cover - requires MT5 terminal
        if info is None:
            return sl, tp
        point = info.point
        stop_level = info.stops_level * point
        if stop_level <= 0:
            return sl, tp
        if sl is not None:
            desired = price - stop_level if direction == "long" else price + stop_level
            if direction == "long" and sl > desired:
                logger.debug("Adjusting SL from %.5f to %.5f due to stop level", sl, desired)
                sl = desired
            if direction == "short" and sl < desired:
                logger.debug("Adjusting SL from %.5f to %.5f due to stop level", sl, desired)
                sl = desired
        if tp is not None:
            desired = price + stop_level if direction == "long" else price - stop_level
            if direction == "long" and tp < desired:
                logger.debug("Adjusting TP from %.5f to %.5f due to stop level", tp, desired)
                tp = desired
            if direction == "short" and tp > desired:
                logger.debug("Adjusting TP from %.5f to %.5f due to stop level", tp, desired)
                tp = desired
        return sl, tp

    def place_order(
        self,
        symbol: str,
        direction: str,
        lot: float,
        sl: Optional[float],
        tp: Optional[float],
        slippage: Optional[int] = None,
        max_retries: int = 3,
    ) -> Dict[str, object]:
        if mt5 is None or not self.connected:
            logger.info("Simulated order %s lot=%.2f", direction, lot)
            return {"ticket": 0, "status": "simulated", "reason": "offline"}

        price = self._current_price(symbol, direction)
        sl, tp = self._enforce_stop_distance(symbol, direction, price, sl, tp)
        order_type = mt5.ORDER_TYPE_BUY if direction == "long" else mt5.ORDER_TYPE_SELL
        deviation = slippage if slippage is not None else self.config.slippage_points
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": float(lot),
            "type": order_type,
            "price": price,
            "sl": sl,
            "tp": tp,
            "deviation": int(deviation),
            "type_filling": mt5.ORDER_FILLING_FOK,
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
            time.sleep(min(2 ** attempt, 5))
        error = getattr(mt5, "last_error", lambda: (None, ""))()
        return {"ticket": 0, "status": "failed", "reason": last_comment, "error": error}

    def close_position(self, ticket: int, slippage: Optional[int] = None) -> Dict[str, object]:
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
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": float(pos.volume),
            "type": order_type,
            "position": ticket,
            "price": price,
            "deviation": int(slippage if slippage is not None else self.config.slippage_points),
            "type_filling": mt5.ORDER_FILLING_FOK,
            "type_time": mt5.ORDER_TIME_GTC,
        }
        result = mt5.order_send(request)  # pragma: no cover - requires MT5 terminal
        if result and result.retcode == mt5.TRADE_RETCODE_DONE:
            logger.info("Closed position ticket=%s price=%.5f", ticket, result.price)
            return {"ticket": int(result.order), "status": "closed", "price": float(result.price)}
        comment = getattr(result, "comment", "unknown") if result else "no_result"
        logger.error("Failed to close ticket %s: %s", ticket, comment)
        return {"ticket": ticket, "status": "failed", "reason": comment}


def connect(config: Dict) -> MT5Broker:
    broker = MT5Broker(BrokerConfig(**config))
    broker.connect()
    return broker
