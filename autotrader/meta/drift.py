from __future__ import annotations

from dataclasses import dataclass

from river.drift import ADWIN


@dataclass
class DriftDetector:
    delta: float = 0.002

    def __post_init__(self) -> None:
        self._adwin = ADWIN(delta=self.delta)

    def update(self, value: float) -> bool:
        self._adwin.update(value)
        return self._adwin.change_detected
