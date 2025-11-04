from __future__ import annotations

from datetime import datetime
from typing import Dict, Optional

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


def build_context(
    symbol: str,
    df: pd.DataFrame,
    spread_points: float,
    news_state: Optional[Dict[str, float]] = None,
) -> Dict[str, float]:
    if df.empty:
        raise ValueError("DataFrame is empty; cannot build context")
    news_state = news_state or {}
    atr_series = compute_atr(df)
    atr_value = float(atr_series.dropna().iloc[-1]) if not atr_series.dropna().empty else 0.0
    trend_series = trend_score(df)
    trend_value = float(trend_series.iloc[-1]) if not trend_series.empty else 0.0
    last_ts = df.index[-1]
    if isinstance(last_ts, pd.Timestamp):
        ts = last_ts.to_pydatetime()
    else:
        ts = datetime.utcnow()
    ctx = {
        "symbol": symbol,
        "atr": atr_value,
        "trend_score": trend_value,
        "session_code": float(session_code(ts)),
        "spread_points": float(spread_points),
        "llm_news_bias": float(news_state.get("llm_bias", 0.0)),
        "news_uncertainty": float(news_state.get("uncertainty", 0.0)),
        "calendar_surprise_z": float(news_state.get("calendar_surprise_z", 0.0)),
    }
    return ctx
