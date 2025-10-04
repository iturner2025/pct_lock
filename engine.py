"""
Core calculation engine for the Criteria Weight Balancer.

This module contains pure, UI-agnostic functions used by the Streamlit app.
Keep all math and algorithmic logic here so it can be tested or reused
independently of the UI layer.
"""
from __future__ import annotations

import math
from typing import List, Tuple


def compute_weighting_state(
    scores: List[float],
    locked: List[bool],
    locked_pct: List[float],
    slider_weights: List[float],
) -> Tuple[float, List[float], List[float], List[float]]:
    """
    Compute the effective weighting state for all rows given the current inputs.

    Parameters
    - scores: per-row base scores
    - locked: per-row flag indicating whether the row's %-w Total is locked
    - locked_pct: per-row target %-w Total (fractions 0..1) for locked rows
    - slider_weights: per-row slider values (0..10) for unlocked rows

    Returns
    - total_weighted (T): the total weighted sum across rows
    - eff_weights: effective weights per row (locked rows are solved to keep their target %)
    - weighted_scores: per-row weighted scores (score * effective weight)
    - pct_w_total: per-row %-w Total as fractions (0..1), derived from weighted_scores / T

    Notes
    - If the sum of locked percentages is >= 1.0, the total T becomes NaN and locked
      rows' effective weights are set to 0 (since the system is unsolvable). The UI
      layer should prevent or display an error for this case.
    - Effective weights are clamped to [0, 10] to respect slider bounds.
    """
    n = len(scores)

    # Sum of target locked percentages
    sum_locked_pct = sum(locked_pct[i] for i in range(n) if locked[i])

    # Unlocked weighted sum from sliders
    unlocked_weighted_sum = 0.0
    for i in range(n):
        if not locked[i]:
            # Clamp slider values to [0, 10]
            w = max(0.0, min(10.0, float(slider_weights[i])))
            unlocked_weighted_sum += scores[i] * w

    # Guard against invalid total locked percent
    denom = 1.0 - sum_locked_pct
    if denom <= 0:
        # Avoid division by zero; T is undefined in this edge case
        T = float("nan")
    else:
        T = unlocked_weighted_sum / denom

    # Effective weights per row
    eff_weights = [0.0] * n
    weighted_scores = [0.0] * n
    for i in range(n):
        if locked[i]:
            s = scores[i]
            target = locked_pct[i]
            if s <= 0:
                # Score is zero: can only support 0% target share.
                eff_w = 0.0
            else:
                if not math.isfinite(T):
                    eff_w = 0.0
                else:
                    eff_w = (target * T) / s
            # Constrain to slider bounds [0,10]
            eff_w = max(0.0, min(10.0, eff_w))
        else:
            eff_w = max(0.0, min(10.0, float(slider_weights[i])))
        eff_weights[i] = eff_w
        weighted_scores[i] = scores[i] * eff_w

    total_weighted = sum(weighted_scores)
    if total_weighted <= 0:
        pct_w_total = [0.0] * n
    else:
        pct_w_total = [ws / total_weighted for ws in weighted_scores]

    return total_weighted, eff_weights, weighted_scores, pct_w_total
