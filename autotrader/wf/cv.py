from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Tuple

import numpy as np


@dataclass
class Fold:
    train_idx: np.ndarray
    test_idx: np.ndarray


def purged_kfold(n_samples: int, n_splits: int = 5, embargo: int = 1) -> Iterable[Fold]:
    indices = np.arange(n_samples)
    fold_sizes = (n_samples // n_splits) * np.ones(n_splits, dtype=int)
    fold_sizes[: n_samples % n_splits] += 1
    current = 0
    for fold_size in fold_sizes:
        start, stop = current, current + fold_size
        test_idx = indices[start:stop]
        train_idx = np.concatenate((indices[: max(0, start - embargo)], indices[min(n_samples, stop + embargo) :]))
        yield Fold(train_idx=train_idx, test_idx=test_idx)
        current = stop
