from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path


def generate(path: Path, n: int = 10) -> None:
    now = datetime.utcnow()
    headlines = [
        {
            "ts": (now - timedelta(minutes=i * 5)).isoformat(),
            "headline": f"Mock news item {i}",
        }
        for i in range(n)
    ]
    path.write_text(json.dumps(headlines, indent=2), encoding="utf-8")


if __name__ == "__main__":
    generate(Path("fake_news.json"))
