from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

try:
    import MetaTrader5 as mt5
except ImportError:  # pragma: no cover
    mt5 = None


@dataclass
class OrderResult:
    ticket: int
    price: float
    sl: float
    tp: float
    lot: float
    comment: str = ""


def place_order(symbol: str, direction: str, lot: float, sl: float, tp: float, slippage: int) -> Dict[str, float]:
    if mt5 is None:
        return {"ticket": 0, "status": "simulated"}
    order_type = mt5.ORDER_TYPE_BUY if direction == "long" else mt5.ORDER_TYPE_SELL
    price = mt5.symbol_info_tick(symbol).ask if direction == "long" else mt5.symbol_info_tick(symbol).bid
    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": lot,
        "type": order_type,
        "price": price,
        "sl": sl,
        "tp": tp,
        "deviation": slippage,
        "type_filling": mt5.ORDER_FILLING_FOK,
        "type_time": mt5.ORDER_TIME_GTC,
    }
    result = mt5.order_send(request)
    return {"ticket": result.order, "status": result.comment}


def close_position(ticket: int) -> Dict[str, float]:
    if mt5 is None:
        return {"ticket": ticket, "status": "simulated"}
    position = mt5.positions_get(ticket=ticket)
    if not position:
        return {"ticket": ticket, "status": "not_found"}
    pos = position[0]
    direction = "long" if pos.type == mt5.POSITION_TYPE_BUY else "short"
    price = mt5.symbol_info_tick(pos.symbol).bid if direction == "long" else mt5.symbol_info_tick(pos.symbol).ask
    order_type = mt5.ORDER_TYPE_SELL if direction == "long" else mt5.ORDER_TYPE_BUY
    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": pos.symbol,
        "volume": pos.volume,
        "type": order_type,
        "position": ticket,
        "price": price,
        "deviation": 30,
        "type_filling": mt5.ORDER_FILLING_FOK,
        "type_time": mt5.ORDER_TIME_GTC,
    }
    result = mt5.order_send(request)
    return {"ticket": result.order, "status": result.comment}
