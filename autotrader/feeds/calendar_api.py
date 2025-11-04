from __future__ import annotations

from datetime import datetime, timedelta
from typing import Dict, List


def get_upcoming_events(horizon_hours: int = 24) -> List[Dict[str, str]]:
    now = datetime.utcnow()
    return [
        {
            "ts": (now + timedelta(hours=1)).isoformat(),
            "event": "US_CPI",
            "surprise_z": 0.5,
        }
    ]


def get_recent_results(window_hours: int = 4) -> List[Dict[str, str]]:
    now = datetime.utcnow()
    return [
        {
            "ts": (now - timedelta(hours=1)).isoformat(),
            "event": "US_NFP",
            "surprise_z": -1.2,
        }
    ]
