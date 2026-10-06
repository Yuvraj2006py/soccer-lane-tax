"""Toy-pitch checks: the Lane Tax should agree with obvious football situations."""

import numpy as np
import pytest

from lane_tax.geometry import Movers, arrival_time, carry_time, openness, pass_win_probs
from lane_tax.metric import Player, Scene, score_scene

HALF_L, HALF_W = 52.5, 34.0


def _p(pid, team, x, y, vx=0.0, vy=0.0, detected=True):
    return Player(pid, team, x, y, vx, vy, detected)


def _scene(teammates, defenders, presser_idx, carrier=(0.0, 0.0), back_line=True, carrier_vel=(0.0, 0.0)):
    """Presser index refers to ``defenders``; a keeper and centre-back are appended so the
    offside line sits deep like a real back four would."""
    extra = [_p(90, 2, 50.0, 0.0), _p(91, 2, 38.0, -12.0)] if back_line else []
    return Scene(0, _p(1, 1, *carrier, *carrier_vel), teammates, list(defenders) + extra, presser_idx, 1,
                 HALF_L, HALF_W)


def _movers(*xy, vel=None):
    pos = np.array(xy, dtype=float)
    v = np.zeros_like(pos) if vel is None else np.array(vel, dtype=float)
    return Movers(pos, v, np.full(len(pos), 0.45))


def test_defender_standing_in_lane_blocks_pass():
    src, dst = np.array([0.0, 0.0]), np.array([20.0, 0.0])
    in_lane = pass_win_probs(src, dst, _movers([10.0, 0.0]))
    far = pass_win_probs(src, dst, _movers([10.0, 15.0]))
    open_in = openness(1 - (1 - in_lane[0]) * (1 - in_lane[1]))
    open_far = openness(1 - (1 - far[0]) * (1 - far[1]))
    assert open_in < 0.1
    assert open_far > 0.7


def test_running_defender_arrives_sooner():
    still = arrival_time(_movers([0.0, 0.0]), np.array([[10.0, 0.0]]))[0, 0]
    running = arrival_time(_movers([0.0, 0.0], vel=[[5.0, 0.0]]), np.array([[10.0, 0.0]]))[0, 0]
    assert running < still


def test_lofted_switch_flies_over_midway_defender_but_not_landing_one():
    src, dst = np.array([0.0, -25.0]), np.array([5.0, 15.0])
    mid = pass_win_probs(src, dst, _movers([2.5, -5.0]))
    landing = pass_win_probs(src, dst, _movers([5.0, 13.0]))
    assert mid[0] < 0.2
    assert max(landing) > 0.7


def test_presser_in_the_passing_lane_pays_tax():
    mate = [_p(2, 1, 20.0, 0.0)]
    presser_in_lane = [_p(10, 2, 8.0, 0.3), _p(11, 2, 30.0, 25.0)]
    r = score_scene(_scene(mate, presser_in_lane, 0))
    assert r.lane_tax > 0.2
    assert r.lanes_cut > 0.2


def test_presser_chasing_from_behind_hurries_but_blocks_nothing():
    mate = [_p(2, 1, 20.0, 0.0)]
    chaser = score_scene(_scene(mate, [_p(10, 2, -3.0, 0.0), _p(11, 2, 30.0, 25.0)], 0))
    in_lane = score_scene(_scene(mate, [_p(10, 2, 8.0, 0.3), _p(11, 2, 30.0, 25.0)], 0))
    assert chaser.lane_tax_block < 0.05
    assert chaser.lane_tax < in_lane.lane_tax / 2


def test_open_second_option_limits_tax_but_lanes_cut_still_credits_him():
    mates = [_p(2, 1, 20.0, 0.0), _p(3, 1, 18.0, 18.0)]
    defenders = [_p(10, 2, 8.0, 0.3), _p(11, 2, 40.0, -25.0)]
    one_option = score_scene(_scene(mates[:1], defenders, 0))
    two_options = score_scene(_scene(mates, defenders, 0))
    assert two_options.lane_tax < one_option.lane_tax
    assert two_options.lanes_cut == pytest.approx(one_option.lanes_cut, rel=0.25)


def test_redundant_cover_shows_in_unit_tax_not_individual_tax():
    mates = [_p(2, 1, 20.0, 0.0)]
    pair = [_p(10, 2, 8.0, 0.3), _p(11, 2, 12.0, -0.3)]
    scene = _scene(mates, pair, 0)
    scene.unit_idx = (0, 1)
    r = score_scene(scene)
    assert r.unit_tax > r.lane_tax + 0.1


def test_teammate_in_the_lane_gets_the_credit_not_the_presser():
    mate = [_p(2, 1, 20.0, 0.0)]
    presser_off_lane, teammate_in_lane = _p(10, 2, 3.0, 8.0), _p(11, 2, 10.0, 0.2)
    r = score_scene(_scene(mate, [presser_off_lane, teammate_in_lane], 0))
    assert r.credit_share is not None and r.credit_share < 0.3
    assert r.top_squeezer_id == 11


def test_cutting_one_of_two_lanes_moves_ways_out():
    mates = [_p(2, 1, 20.0, 0.0), _p(3, 1, 15.0, 15.0)]
    r = score_scene(_scene(mates, [_p(10, 2, 8.0, 0.3)], 0))
    assert r.ways_tax > 0.05


def test_carry_from_standing_takes_about_a_second_and_a_half_for_six_metres():
    assert carry_time(np.array([6.0]), 0.0)[0] == pytest.approx(1.55, abs=0.1)
    assert carry_time(np.array([6.0]), 5.5)[0] == pytest.approx(6.0 / 5.5, abs=0.01)


def test_offside_receiver_is_not_an_escape():
    mate = [_p(2, 1, 35.0, 0.0)]
    defenders = [_p(10, 2, 25.0, 5.0), _p(11, 2, 50.0, 0.0), _p(12, 2, 20.0, -20.0)]
    r = score_scene(_scene(mate, defenders, 0, carrier=(10.0, 0.0), back_line=False))
    passes = [o for o in r.options if o.kind == "pass"]
    assert passes and all(o.offside for o in passes)


def test_carrier_running_back_to_own_goal_finds_forward_carry_harder():
    defenders = [_p(10, 2, 4.0, 3.0)]
    facing = score_scene(_scene([], defenders, 0))
    running_back = score_scene(_scene([], defenders, 0, carrier_vel=(-4.5, 0.0)))
    assert running_back.escape < facing.escape


def test_rushed_carrier_finds_long_pass_harder():
    mate = [_p(2, 1, 30.0, 0.0)]
    close = score_scene(_scene(mate, [_p(10, 2, 0.8, 0.5, vx=-3.0)], 0))
    far = score_scene(_scene(mate, [_p(10, 2, 8.0, 12.0)], 0))
    long_close = next(o for o in close.options if o.kind == "pass")
    long_far = next(o for o in far.options if o.kind == "pass")
    assert long_close.accuracy < long_far.accuracy
    assert close.lane_tax_rush > 0.0
