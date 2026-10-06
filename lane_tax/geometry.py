"""Who gets there first: arrival times, pass interception and carry contests.

Pure numpy so it can be tested on toy pitches. Coordinates are metres. Every
"probability" here is the chance a *defender* wins the ball at that spot; an option's
openness is the chance no defender does.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from lane_tax.config import (
    CARRY_ACCEL_M_S2,
    CARRY_REACTION_S,
    CARRY_SPEED_M_S,
    CONTROL_TIME_S,
    GROUND_PASS_SPEED_M_S,
    LANE_STEP_M,
    LOFTED_LANDING_M,
    LOFTED_PASS_M,
    LOFTED_PASS_SPEED_M_S,
    LUNGE_M,
    MAX_SPEED_M_S,
    PASS_RELEASE_S,
    REACH_M,
    REACTION_TIME_S,
)


@dataclass(frozen=True)
class Movers:
    """Players who might contest the ball: positions, velocities and time uncertainty."""

    pos: np.ndarray  # (n, 2)
    vel: np.ndarray  # (n, 2)
    sigma: np.ndarray  # (n,)

    @property
    def n(self) -> int:
        return int(self.pos.shape[0])


def arrival_time(movers: Movers, targets: np.ndarray, reaction_s: float = REACTION_TIME_S) -> np.ndarray:
    """Seconds for each mover to reach each target, shape (n, m).

    Spearman-style: keep running on the current velocity for the reaction time, then
    go straight at top speed. A target already within body reach costs no time, and
    reaction time ramps in over LUNGE_M so a defender next to a lane can stick a leg out.
    """
    targets = np.atleast_2d(targets)
    if movers.n == 0:
        return np.empty((0, targets.shape[0]))
    near = np.linalg.norm(targets[None, :, :] - movers.pos[:, None, :], axis=2)
    excess_near = np.clip(near - REACH_M, 0.0, None)
    ramp = np.clip(excess_near / LUNGE_M, 0.0, 1.0)

    after = movers.pos + movers.vel * reaction_s
    far = np.linalg.norm(targets[None, :, :] - after[:, None, :], axis=2)
    run = reaction_s + np.clip(far - REACH_M, 0.0, None) / MAX_SPEED_M_S
    direct = excess_near / MAX_SPEED_M_S + ramp * reaction_s
    return np.minimum(run, direct)


def carry_time(s: np.ndarray, v0: float) -> np.ndarray:
    """Seconds for the carrier to dribble ``s`` metres starting at ``v0`` along the line,
    accelerating at CARRY_ACCEL_M_S2 up to CARRY_SPEED_M_S."""
    v0 = float(np.clip(v0, 0.0, CARRY_SPEED_M_S))
    a = CARRY_ACCEL_M_S2
    t_top = (CARRY_SPEED_M_S - v0) / a
    d_top = v0 * t_top + 0.5 * a * t_top**2
    s = np.asarray(s, dtype=float)
    accel_phase = (-v0 + np.sqrt(v0**2 + 2 * a * np.minimum(s, d_top))) / a
    return np.where(s <= d_top, accel_phase, t_top + (s - d_top) / CARRY_SPEED_M_S)


def win_probability(t_ball: np.ndarray, t_defender: np.ndarray, sigma: np.ndarray) -> np.ndarray:
    """Chance a defender arriving at t_defender beats a ball arriving at t_ball."""
    k = np.pi / (np.sqrt(3.0) * sigma)
    if np.ndim(k) == 1 and np.ndim(t_defender) == 2:
        k = k[:, None]
    return 1.0 / (1.0 + np.exp(-k * (t_ball - t_defender)))


def is_lofted(length: float) -> bool:
    return length > LOFTED_PASS_M


def pass_check_points(src: np.ndarray, dst: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Points along a pass where it can be won, and the distance of each from the passer.

    A ground pass can be cut anywhere. A lofted ball can only be blocked as it is struck
    (within reach + lunge of the passer) or won around where it lands.
    """
    length = float(np.linalg.norm(dst - src))
    if length < 1e-6:
        return dst[None, :], np.array([0.0])
    s = np.arange(LANE_STEP_M, length + 1e-6, LANE_STEP_M)
    if s.size == 0 or s[-1] < length:
        s = np.append(s, length)
    if is_lofted(length):
        keep = (s <= REACH_M + LUNGE_M) | (s >= length - LOFTED_LANDING_M)
        s = s[keep]
    direction = (dst - src) / length
    return src[None, :] + s[:, None] * direction[None, :], s


def pass_win_probs(
    src: np.ndarray, dst: np.ndarray, defenders: Movers, turn_delay_s: float = 0.0
) -> tuple[np.ndarray, np.ndarray]:
    """Per-defender chance to (a) cut the pass in flight and (b) beat the receiver to it.

    Returns two (n_def,) arrays. Openness of the option is
    prod(1 - intercept) * prod(1 - reception), so removing one defender is just
    dropping his factor. ``turn_delay_s`` is extra set-up time when the carrier has to
    turn to play it.
    """
    if defenders.n == 0:
        return np.zeros(0), np.zeros(0)
    length = float(np.linalg.norm(dst - src))
    speed = LOFTED_PASS_SPEED_M_S if is_lofted(length) else GROUND_PASS_SPEED_M_S
    release = PASS_RELEASE_S + turn_delay_s
    pts, s = pass_check_points(src, dst)
    t_ball = release + s / speed
    t_def = arrival_time(defenders, pts)
    p_int = win_probability(t_ball[None, :], t_def, defenders.sigma)
    flight = p_int[:, :-1] if p_int.shape[1] > 1 else np.zeros((defenders.n, 1))
    intercept = flight.max(axis=1)
    t_rec = release + length / speed + CONTROL_TIME_S
    reception = win_probability(np.array([t_rec]), t_def[:, -1:], defenders.sigma)[:, 0]
    return intercept, reception


def turn_delay(carrier_vel: np.ndarray, direction: np.ndarray, moving_speed: float, decel: float) -> float:
    """Seconds to kill the part of the carrier's run that points away from ``direction``."""
    if float(np.linalg.norm(carrier_vel)) < moving_speed:
        return 0.0
    u = direction / max(float(np.linalg.norm(direction)), 1e-6)
    against = max(0.0, -float(np.dot(carrier_vel, u)))
    return against / decel


def carry_win_probs(
    src: np.ndarray, dst: np.ndarray, defenders: Movers, turn_delay_s: float = 0.0, v0: float = 0.0
) -> np.ndarray:
    """Per-defender chance to get to the carrier's path before he does, shape (n_def,).

    Defenders are already watching the man on the ball, so they react to a dribble faster
    (CARRY_REACTION_S) than to a pass they have to read."""
    if defenders.n == 0:
        return np.zeros(0)
    length = float(np.linalg.norm(dst - src))
    s = np.arange(2.0, length + 1e-6, 2.0)
    if s.size == 0 or s[-1] < length:
        s = np.append(s, length)
    direction = (dst - src) / max(length, 1e-6)
    pts = src[None, :] + s[:, None] * direction[None, :]
    t_carrier = turn_delay_s + carry_time(s, v0)
    t_def = arrival_time(defenders, pts, CARRY_REACTION_S)
    return win_probability(t_carrier[None, :], t_def, defenders.sigma).max(axis=1)


def openness(defender_probs: np.ndarray, exclude: int | None = None) -> float:
    """Chance no defender wins the ball, optionally pretending one defender isn't there."""
    p = np.asarray(defender_probs, dtype=float)
    if exclude is not None and 0 <= exclude < p.size:
        p = np.delete(p, exclude)
    return float(np.prod(1.0 - np.clip(p, 0.0, 1.0)))
