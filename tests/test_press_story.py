import pytest

from lane_tax.config import DEFAULT_MATCH_ID
from lane_tax.data import load_tracking_frames
from lane_tax.explore import sample_review_presses
from lane_tax.press_story import OUTCOMES, MatchContext, build_story


@pytest.fixture(scope="module")
def stories():
    players, frame_meta = load_tracking_frames(DEFAULT_MATCH_ID, use_cache=True)
    ctx = MatchContext(DEFAULT_MATCH_ID, players, frame_meta)
    sample = sample_review_presses(match_id=DEFAULT_MATCH_ID)
    return {r.review_id: build_story(ctx, r.event_id, r.review_id) for r in sample.itertuples()}


def _check(story, name):
    return next(ok for n, ok, _ in story.checks if n == name)


def test_every_press_maps_teams_and_direction(stories):
    for s in stories.values():
        assert _check(s, "teams differ"), s.review_id
        assert _check(s, "attack direction"), s.review_id
        assert _check(s, "carrier on ball"), s.review_id
        assert s.outcome in OUTCOMES


def test_long_ball_in_flight_at_horizon_is_followed_to_regain(stories):
    s = stories["R03"]
    assert s.outcome == "forced_long_won"
    assert s.regain_frame is not None and s.regain_frame > s.frame0 + 80


def test_out_of_play_resolves_when_ball_crosses_line(stories):
    s = stories["R08"]
    assert s.outcome == "forced_out"
    assert s.resolution_frame > s.release_frame


def test_positional_interception_is_credited_as_cutting_the_lane(stories):
    s = stories["R15"]
    assert s.outcome == "won_by_presser"
    assert s.press_type == "positional"
    assert s.credit == "CUT THE LANE — INTERCEPTED"


def test_tight_presser_bypassed_by_long_switch_is_not_a_win(stories):
    s = stories["R01"]
    assert s.grade == "bad"
    assert s.pressure_level == "high"
    assert s.credit == "STRONG PRESSURE — LANE LEFT OPEN"


def test_presser_never_closing_is_not_a_press(stories):
    assert stories["R13"].press_type == "not_a_press"


def test_presser_starting_behind_is_out_of_position_not_beaten(stories):
    for rid in ("R06", "R07", "R10"):
        s = stories[rid]
        assert s.press_type == "chase_from_behind", rid
        assert s.credit == "OUT OF POSITION FROM THE START", rid


def test_presser_verdict_independent_of_team_outcome_when_chase_works(stories):
    s = stories["R11"]
    assert s.press_type == "chase_from_behind"
    assert s.presser_grade == "good"
