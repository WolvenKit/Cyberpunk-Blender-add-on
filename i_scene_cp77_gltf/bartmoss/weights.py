from __future__ import annotations

import numpy as np


def normalization_divisors(totals):
    """Preserve float32 unit weights while normalizing materially non-unit sums"""
    totals = np.asarray(totals, dtype=np.float64)
    precision = 8 * np.finfo(np.float32).eps
    return np.where(np.abs(totals - 1.0) <= precision, 1.0, totals)
