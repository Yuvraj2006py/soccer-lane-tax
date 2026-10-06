"""Phase 0 tests: data loading and press→tracking frame joins."""

from __future__ import annotations

import pytest

from lane_tax.data import (
    DEFAULT_MATCH_ID,
    PRESS_SUBTYPES,
    join_press_to_tracking,
    join_summary,
    list_match_ids,
    load_match_meta,
    load_press_events,
    load_tracking_frames,
)


@pytest.fixture(scope="module")
def match_id() -> int:
    ids = list_match_ids()
    assert DEFAULT_MATCH_ID in ids
    return DEFAULT_MATCH_ID


def test_list_match_ids_nonempty():
    ids = list_match_ids()
    assert len(ids) >= 1
    assert all(isinstance(i, int) for i in ids)


def test_load_match_meta(match_id: int):
    meta = load_match_meta(match_id)
    assert meta["id"] == match_id
    assert meta.get("pitch_length")
    assert meta.get("pitch_width")


def test_load_press_events(match_id: int):
    press = load_press_events(match_id)
    assert len(press) > 0
    assert set(press["event_subtype"].unique()).issubset(set(PRESS_SUBTYPES))
    assert press["frame_start"].isna().sum() == 0
    assert (press["frame_end"] >= press["frame_start"]).all()


def test_press_joins_tracking_frames(match_id: int):
    press = load_press_events(match_id)
    _players, frame_meta = load_tracking_frames(match_id, use_cache=True)
    joined = join_press_to_tracking(press, frame_meta)
    summary = join_summary(joined)

    assert summary["n_press_events"] == len(press)
    # Exact frame ids from SkillCorner events should exist in tracking.
    assert summary["hit_rate"] == 1.0
    # Almost all press starts should land on populated on-ball frames.
    assert summary["populated_rate"] >= 0.95
    assert summary["missing_frames"] == []
