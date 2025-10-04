"""
Criteria Weight Balancer

Run with: streamlit run main.py

This app lets you balance criteria by adjusting Weighting sliders (0–10 step 0.1) and
locking rows to preserve their share of the total weighted score ("%-w Total").

Columns:
1) Criteria Name
2) Score
3) % of Total (of scores)
4) Weighting (slider)
5) Weighted Score (Score * Weighting)
6) %-w Total (Weighted Score / Total Weighted Score)
7) w-%-Lock (padlock toggle)

Locking behavior:
- Clicking the padlock stores the current %-w Total for that row and disables its slider.
- When other sliders change, locked rows' weights auto-adjust to preserve their stored share.
- You cannot lock rows to 100% or more in total, and you cannot lock a nonzero % for a row with score 0.
"""

from __future__ import annotations

import math
import random
from typing import List, Tuple

import streamlit as st


# --------------------------- State Initialization ---------------------------

def init_state(n: int) -> None:
    """Initialize session state for n criteria."""
    st.session_state.n = int(n)
    # Generate random scores between 0 and 200 inclusive
    st.session_state.scores = [random.randint(0, 200) for _ in range(n)]
    st.session_state.locked = [False] * n
    st.session_state.locked_pct = [0.0] * n  # stores target %-w Total (0..1) for locked rows
    # Remove any existing weight_* keys to avoid conflicts with widget-managed state
    for k in list(st.session_state.keys()):
        if isinstance(k, str) and k.startswith("weight_"):
            del st.session_state[k]


def ensure_initialized(n: int) -> None:
    """Ensure session state exists and matches n criteria."""
    if "scores" not in st.session_state or len(st.session_state.scores) != n:
        init_state(n)


# --------------------------- Core Calculations ---------------------------

def compute_weighting_state(
    scores: List[float],
    locked: List[bool],
    locked_pct: List[float],
    slider_weights: List[float],
) -> Tuple[float, List[float], List[float], List[float]]:
    """
    Given scores, lock flags, target locked percentages, and current unlocked slider weights,
    compute:
      - total weighted sum T
      - effective weights per row (locked rows computed to maintain target %)
      - weighted scores per row
      - %-w Total per row (as fractions 0..1)
    """
    n = len(scores)
    # Sum of target locked percentages
    sum_locked_pct = sum(locked_pct[i] for i in range(n) if locked[i])

    # Unlocked weighted sum from sliders
    unlocked_weighted_sum = 0.0
    for i in range(n):
        if not locked[i]:
            unlocked_weighted_sum += scores[i] * max(0.0, min(10.0, float(slider_weights[i])))

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


# --------------------------- UI Rendering ---------------------------

def main() -> None:
    st.set_page_config(page_title="Criteria Weight Balancer", layout="wide")
    st.title("Criteria Weight Balancer")

    # Compact UI spacing
    st.markdown(
        """
        <style>
        div[data-testid='stHorizontalBlock'] { margin-bottom: 0.25rem; }
        div[data-testid='stVerticalBlock'] { gap: 0.25rem !important; }
        section.main > div.block-container { padding-top: 0.75rem; padding-bottom: 0.75rem; }
        div[data-baseweb='slider'] { margin-top: 0.1rem; margin-bottom: 0.1rem; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    with st.sidebar:
        st.markdown("### Setup")
        n = st.number_input(
            "How many criteria?",
            min_value=2,
            max_value=20,
            value=5,
            step=1,
            help="Enter a number from 2 to 20.",
        )
        ensure_initialized(int(n))

        if st.button("Regenerate Scores", help="Randomize scores 0–200 and reset locks."):
            init_state(int(n))
            # Trigger full rerun
            try:
                st.rerun()
            except Exception:
                st.experimental_rerun()

        if st.button("Reset Locks", help="Unlock all rows and clear targets."):
            st.session_state.locked = [False] * int(n)
            st.session_state.locked_pct = [0.0] * int(n)
            try:
                st.rerun()
            except Exception:
                st.experimental_rerun()

    scores: List[float] = st.session_state.scores
    n = len(scores)

    # Precompute unweighted score totals and percentages
    total_score = sum(scores)
    score_pct = [((s / total_score) if total_score > 0 else 0.0) for s in scores]

    # Prepare slider weights array from session state keys
    slider_weights = [float(st.session_state.get(f"weight_{i}", 1.0)) for i in range(n)]
    locked: List[bool] = list(st.session_state.locked)
    locked_pct: List[float] = list(st.session_state.locked_pct)

    # Compute effective current state
    T, eff_weights, weighted_scores, pct_w_total = compute_weighting_state(
        scores, locked, locked_pct, slider_weights
    )

    # Display headers
    header_cols = st.columns([2.0, 1.2, 1.2, 3.0, 1.6, 1.6, 1.1], gap="small")
    headers = [
        "Criteria Name",
        "Score",
        "% of Total",
        "Weighting",
        "Weighted Score",
        "%-w Total",
        "w-%-Lock",
    ]
    for col, h in zip(header_cols, headers):
        col.markdown(f"**{h}**")

    # Render rows
    any_lock_toggle = False

    for i in range(n):
        c1, c2, c3, c4, c5, c6, c7 = st.columns([2.0, 1.2, 1.2, 3.0, 1.6, 1.6, 1.1], gap="small")
        name = f"Criteria {i + 1}"
        with c1:
            st.write(name)
        with c2:
            st.write(f"{scores[i]:.0f}")
        with c3:
            st.write(f"{(score_pct[i] * 100):.2f}%")
        with c4:
            if locked[i]:
                # Show disabled slider reflecting computed effective weight
                st.slider(
                    label="Weighting",
                    min_value=0.0,
                    max_value=10.0,
                    value=float(round(eff_weights[i], 2)),
                    step=0.1,
                    key=f"display_weight_{i}",
                    disabled=True,
                    label_visibility="collapsed",
                )
            else:
                # Interactive slider bound to session state
                new_val = st.slider(
                    label="Weighting",
                    min_value=0.0,
                    max_value=10.0,
                    value=float(round(slider_weights[i], 2)),
                    step=0.1,
                    key=f"weight_{i}",
                    label_visibility="collapsed",
                )
        with c5:
            st.write(f"{weighted_scores[i]:.2f}")
        with c6:
            pct_display = pct_w_total[i] * 100.0
            st.write(f"{pct_display:.2f}%")
        with c7:
            icon = "🔒" if locked[i] else "🔓"
            pressed = st.button(icon, key=f"lockbtn_{i}", help=(
                "Unlock row" if locked[i] else "Lock row: preserve current %-w Total"
            ))
            if pressed:
                # Handle toggling
                if not locked[i]:
                    # Attempt to lock: capture current %-w Total
                    current_pct = pct_w_total[i] if math.isfinite(pct_w_total[i]) else 0.0
                    # Guard: zero score cannot hold nonzero percent
                    if scores[i] == 0 and current_pct > 0:
                        st.warning(
                            f"Cannot lock {name} at nonzero % because its Score is 0.")
                    else:
                        prospective_total = sum(
                            locked_pct[j] for j in range(n) if locked[j]
                        ) + current_pct
                        if prospective_total >= 0.999999:  # Prevent ≥ 100%
                            st.warning(
                                "Total locked %-w must be less than 100%. Unlock another row or reduce other locks.")
                        else:
                            st.session_state.locked[i] = True
                            st.session_state.locked_pct[i] = float(current_pct)
                            any_lock_toggle = True
                else:
                    # Unlock
                    st.session_state.locked[i] = False
                    st.session_state.locked_pct[i] = 0.0
                    any_lock_toggle = True

    # After handling locks, if any toggled, trigger rerun for consistent recomputation
    if any_lock_toggle:
        try:
            st.rerun()
        except Exception:
            st.experimental_rerun()

    # Totals row
    sum_score_pct = sum(score_pct) * 100.0
    sum_pct_w = sum(pct_w_total) * 100.0
    c1, c2, c3, c4, c5, c6, c7 = st.columns([2.0, 1.2, 1.2, 3.0, 1.6, 1.6, 1.1], gap="small")
    with c1:
        st.markdown("**Totals**")
    with c2:
        st.markdown(f"**{total_score:.0f}**")
    with c3:
        st.markdown(f"**{sum_score_pct:.2f}%**")
    with c4:
        st.markdown("")
    with c5:
        st.markdown(f"**{T:.2f}**" if math.isfinite(T) else "**—**")
    with c6:
        st.markdown(f"**{sum_pct_w:.2f}%**")
    with c7:
        st.markdown("")

    # Footer info and safeguards
    with st.expander("Details & Notes"):
        st.markdown(
            "- Weighted Total: "
            + (f"{T:.2f}" if math.isfinite(T) else "(not defined when locked total ≥ 100%)")
        )
        locked_rows = [i + 1 for i, v in enumerate(st.session_state.locked) if v]
        if locked_rows:
            st.markdown(
                f"- Locked rows: {', '.join(map(str, locked_rows))}. Their % shares are preserved."
            )
        total_locked_pct = sum(
            st.session_state.locked_pct[i]
            for i in range(n)
            if st.session_state.locked[i]
        )
        st.markdown(f"- Total locked %-w: {total_locked_pct * 100:.2f}%")
        if total_locked_pct >= 1.0:
            st.error("Invalid state: total locked %-w is 100% or more. Unlock one or more rows.")


if __name__ == "__main__":

    main()
