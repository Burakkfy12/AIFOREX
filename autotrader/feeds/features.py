from __future__ import annotations

from datetime import datetime
from typing import Dict

import numpy as np
import pandas as pd


def compute_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high_low = df["high"] - df["low"]
    high_close = (df["high"] - df["close"].shift()).abs()
    low_close = (df["low"] - df["close"].shift()).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    return tr.rolling(window=period).mean()


def trend_score(df: pd.DataFrame) -> pd.Series:
    ema_fast = df["close"].ewm(span=12).mean()
    ema_slow = df["close"].ewm(span=26).mean()
    score = (ema_fast - ema_slow) / df["close"].rolling(window=26).std().replace(0, np.nan)
    return score.fillna(0)


def session_code(ts: datetime) -> int:
    hour = ts.hour
    if 0 <= hour < 8:
        return 0  # Asia
    if 8 <= hour < 16:
        return 1  # Europe
    return 2  # US


def build_context(symbol: str, timeframe: str, df: pd.DataFrame, news_state: Dict[str, float]) -> Dict[str, float]:
    atr = compute_atr(df).iloc[-1]
    trend = trend_score(df).iloc[-1]
    now = pd.Timestamp.utcnow()
    context = {
        "symbol": symbol,
        "timeframe": timeframe,
        "atr": float(atr),
        "trend_score": float(trend),
        "spread": float(news_state.get("spread", 0.0)),
        "session_code": float(session_code(now.to_pydatetime())),
        "llm_news_bias": float(news_state.get("llm_bias", 0.0)),
        "news_uncertainty": float(news_state.get("uncertainty", 0.0)),
        "calendar_surprise_z": float(news_state.get("calendar_surprise_z", 0.0)),
    }
    return context
