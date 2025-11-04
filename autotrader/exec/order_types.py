from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Order:
    direction: str
    price: float
    sl: float
    tp: float
    lot: float


def market_order(direction: str, price: float, sl: float, tp: float, lot: float) -> Order:
    return Order(direction=direction, price=price, sl=sl, tp=tp, lot=lot)
