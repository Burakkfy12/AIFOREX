from __future__ import annotations

import json
import time
from pathlib import Path

import pandas as pd


def replay(csv_path: Path, callback) -> None:
    df = pd.read_csv(csv_path)
    for _, row in df.iterrows():
        callback(row.to_dict())
        time.sleep(0.1)


if __name__ == "__main__":
    def printer(tick):
        print(json.dumps(tick))

    replay(Path("ticks.csv"), printer)
