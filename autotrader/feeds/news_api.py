from __future__ import annotations

from datetime import datetime, timedelta
from typing import Dict, List


def get_recent_headlines(window_minutes: int = 30) -> List[Dict[str, str]]:
    now = datetime.utcnow()
    return [
        {
            "ts": (now - timedelta(minutes=10)).isoformat(),
            "headline": "Gold edges higher as USD weakens",
            "source": "MockWire",
        }
    ]
