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

# --------------------------- Core Calculations ---------------------------
from engine import compute_weighting_state


# --------------------------- State Initialization ---------------------------

criteria_names = [
    "Employee Count",
    "Profit Margin",
    "Proximity to Office",
    "Company Age",
    "% IT Staff",
    "PE Backed",
    "CFO Changed Recently",
    "Has CIO",
    "Has CISO",
    "Industry",
    "Company Key Word",
    "About Us Key Words",
    "Employee Growth",
    "Revenue Growth",
]


def init_state(n: int) -> None:
    """Initialize session state for n criteria."""
    st.session_state.n = int(n)
    # Randomly pick unique criteria names for these n rows
    st.session_state.names = random.sample(criteria_names, int(n))
    # Generate random scores between 0 and 200 inclusive
    st.session_state.scores = [random.randint(25, 200) for _ in range(n)]
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


# --------------------------- UI Rendering ---------------------------

def main() -> None:
    st.set_page_config(page_title="ICP Criteria Balancer", layout="wide")
    st.title("Criteria Weight Balancer")

    # Compact UI spacing
    st.markdown(
        """
        <style>
        
        layout_styles = {
            "div[data-testid='stHorizontalBlock']": {"margin-bottom": "0.25rem"},
            "div[data-testid='stVerticalBlock']": {"gap": "0.25rem !important"},
            "section.main > div.block-container": {
                "padding-top": "0.75rem",
                "padding-bottom": "0.75rem"
            },
            "div[data-baseweb='slider']": {
                "margin-top": "0.1rem",
                "margin-bottom": "0.1rem"
            }
        }
        
        
        #    2. Force the primary colour to bright green everywhere
        #    ────────────────────────────────────────────────────────────── 
        root_styles = {
            ":root": {
                "--primary-color": "#00ff00 !important",
                "--theme-primaryColor": "#00ff00 !important",
                "--theme-primary-color": "#00ff00 !important",
                "--slider-thumb-color": "#00ff00 !important",  # BaseWeb var
                "--slider-track-active": "#00ff00 !important",  # custom var we’ll use
                "--slider-track-inactive": "#d3d3d3 !important"  # grey
            }
        }
        
        # /* ──────────────────────────────────────────────────────────────
        #    3. Thumb (handle) – green, no shadow
        #    ────────────────────────────────────────────────────────────── */
        thumb_styles = {
            "div[data-baseweb='slider'] [role='slider']": {
                "background-color": "var(--primary-color) !important",
                "border-color": "var(--primary-color) !important",
                "box-shadow": "none !important"
            },
            # Focus ring – green outline
            "div[data-baseweb='slider'] [role='slider']:focus": {
                "outline": "2px solid var(--primary-color) !important"
            }
        }
        
        # /* ──────────────────────────────────────────────────────────────
        #    4. Track – wipe any gradient that Streamlit injects inline
        #    ────────────────────────────────────────────────────────────── */
        track_styles = {
            # 4a – BaseWeb track elements (Track, InnerTrack, etc.)
            "div[data-baseweb='slider'] [class*='Track'], div[data-baseweb='slider'] [class*='InnerTrack']": {
                "background-image": "none !important",
                "background": "none !important"
            },
            # 4b – The *inline* gradient that Streamlit adds via style attribute
            "div[data-baseweb='slider'] [style*='gradient'], div[data-baseweb='slider'] [style*='linear-gradient']": {
                "background": "linear-gradient(to right, var(--slider-track-active)   0%, var(--slider-track-active)   var(--value-percentage, 0%), var(--slider-track-inactive) var(--value-percentage, 0%), var(--slider-track-inactive) 100%) !important"
            },
            # 4c – Fallback: any element that still receives a background colour
            "div[data-baseweb='slider'] [class*='Track'], div[data-baseweb='slider'] [class*='InnerTrack']": {
                "background-color": "var(--slider-track-inactive) !important"
            },
            # 4d – The “active” part (left of thumb) – painted by BaseWeb via ::before
            "div[data-baseweb='slider'] [class*='Track']::before, div[data-baseweb='slider'] [class*='InnerTrack']": {
                "background-color": "var(--slider-track-active) !important"
            }
        }
        
        # /* ──────────────────────────────────────────────────────────────
        #    5. Numeric label / tooltip – green text
        #    ────────────────────────────────────────────────────────────── */
        tooltip_styles = {
            "div[data-testid='stSlider'] [data-testid*='Value'], div[data-testid='stSlider'] [class*='value'], div[data-baseweb='slider'] [data-baseweb='tooltip'] *": {
                "color": "var(--primary-color) !important",
                "border-color": "var(--primary-color) !important"
            }
        }
        
        # /* ──────────────────────────────────────────────────────────────
        #    6. Extra safety – catch any stray red that may come from a theme
        #    ────────────────────────────────────────────────────────────── */
        extra_safety_styles = {
            "div[data-baseweb='slider'] *": {
                # Force every child to ignore a red primary colour
                "--primary-color": "#00ff00 !important"
            }
        }
        
        </style>
        """,
        unsafe_allow_html=True,
    )

    with st.sidebar:
        st.markdown("### Setup")
        n = st.number_input(
            "How many criteria?",
            min_value=2,
            max_value=len(criteria_names),
            value=6,
            step=1,
            help=f"Enter a number from 2 to {len(criteria_names)}.",
        )
        ensure_initialized(int(n))

        if st.button("Regenerate Scores", help="Randomize scores 0–200 and reset locks."):
            # Only regenerate scores and reset locks/targets; keep names as-is
            st.session_state.scores = [random.randint(0, 200) for _ in range(int(n))]
            st.session_state.locked = [False] * int(n)
            st.session_state.locked_pct = [0.0] * int(n)
            # Remove any existing weight_* keys to avoid conflicts
            for k in list(st.session_state.keys()):
                if isinstance(k, str) and k.startswith("weight_"):
                    del st.session_state[k]
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
        "Criteria",
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
        name = st.session_state.names[i] if "names" in st.session_state and i < len(st.session_state.names) else f"Criteria {i + 1}"
        with c1:
            st.write(name)
        with c2:
            st.write(f"{scores[i]:.0f}")
        with c3:
            st.write(f"{(score_pct[i] * 100):.0f}%")
        with c4:
            if locked[i]:
                # Show disabled slider reflecting computed effective weight
                st.slider(
                    label="",
                    min_value=0.0,
                    max_value=10.0,
                    step=0.1,
                    value=float(round(eff_weights[i], 2)),
                    key=f"display_weight_{i}",
                    disabled=True,
                    label_visibility="hidden",
                )
            else:
                # Interactive slider bound to session state
                new_val = st.slider(
                    label="",
                    min_value=0.0,
                    max_value=10.0,
                    step=0.1,
                    value=float(round(slider_weights[i], 2)),
                    key=f"weight_{i}",
                    disabled=False,
                    label_visibility="hidden",
                )
        with c5:
            st.write(f"{weighted_scores[i]:.0f}")
        with c6:
            pct_display = pct_w_total[i] * 100.0
            st.write(f"{pct_display:.0f}%")
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
        st.markdown(f"**{sum_score_pct:.0f}%**")
    with c4:
        st.markdown("")
    with c5:
        st.markdown(f"**{T:.0f}**" if math.isfinite(T) else "**—**")
    with c6:
        st.markdown(f"**{sum_pct_w:.0f}%**")
    with c7:
        st.markdown("")

    # Footer info and safeguards
    with st.expander("Details & Notes"):
        st.markdown(
            "- Weighted Total: "
            + (f"{T:.0f}" if math.isfinite(T) else "(not defined when locked total ≥ 100%)")
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
        st.markdown(f"- Total locked %-w: {total_locked_pct * 100:.0f}%")
        if total_locked_pct >= 1.0:
            st.error("Invalid state: total locked %-w is 100% or more. Unlock one or more rows.")


if __name__ == "__main__":

    main()
