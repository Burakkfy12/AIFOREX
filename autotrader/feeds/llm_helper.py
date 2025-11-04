from __future__ import annotations

from typing import Dict


def summarize_headline(headline: str) -> Dict[str, float]:
    headline_lower = headline.lower()
    if "gold" in headline_lower and "higher" in headline_lower:
        return {"bias": "bull_gold", "confidence": 0.7, "uncertainty_flag": False}
    return {"bias": "neutral", "confidence": 0.5, "uncertainty_flag": True}
