"""Phase 1 tests for focus filtering, outcome labels, and review sample."""

from __future__ import annotations

import pandas as pd

from lane_tax.config import (
    DEFAULT_MATCH_ID,
    FOCUS_ATTACK_PHASES,
    OUTCOME_WINDOW_FRAMES,
    PROGRESSIVE_ADVANCE_M,
    TAX_WINDOW_FRAMES,
)
from lane_tax.explore import (
    focus_press_events,
    outcome_label_for_press,
    provisional_cut_off_label,
    sample_review_presses,
)


def test_focus_phases_only():
    focus = focus_press_events(DEFAULT_MATCH_ID)
    assert len(focus) > 0
    assert set(focus["team_in_possession_phase_type"].unique()).issubset(
        set(FOCUS_ATTACK_PHASES)
    )


def test_outcome_windows_match_config():
    assert TAX_WINDOW_FRAMES == 10
    assert OUTCOME_WINDOW_FRAMES == 30
    assert PROGRESSIVE_ADVANCE_M == 8.0


def test_outcome_label_keys():
    focus = focus_press_events(DEFAULT_MATCH_ID).head(1)
    from lane_tax.data import load_phases_of_play, load_tracking_frames

    players, frame_meta = load_tracking_frames(DEFAULT_MATCH_ID, use_cache=True)
    phases = load_phases_of_play(DEFAULT_MATCH_ID)
    out = outcome_label_for_press(players, frame_meta, phases, focus.iloc[0])
    assert "outcome_progressive" in out
    assert out["outcome_progressive"] in (0, 1)


def test_provisional_label_values():
    row = pd.Series(
        {
            "interplayer_distance_start": 9.0,
            "interplayer_distance_end": 5.0,
            "outcome_progressive": 0,
        }
    )
    assert provisional_cut_off_label(row) == "cut_off"
    row2 = pd.Series(
        {
            "interplayer_distance_start": 9.0,
            "interplayer_distance_end": 5.0,
            "outcome_progressive": 1,
        }
    )
    assert provisional_cut_off_label(row2) == "motion_only"


def test_review_sample_size():
    sample = sample_review_presses(DEFAULT_MATCH_ID, n=15)
    assert len(sample) == 15
    assert sample["review_id"].nunique() == 15
    assert sample["provisional_label"].isin(
        ["cut_off", "motion_only", "unclear"]
    ).all()
