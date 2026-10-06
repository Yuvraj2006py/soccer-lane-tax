"""Lane Tax: how much of the carrier's way out a presser takes away.

For one frame we list every option the carrier has — a pass to each teammate and a
carry in three forward directions — and ask, for each, the chance no defender wins
the ball (``openness``). Options that beat the press (progressive, a switch of play, or
past the presser) carry an *escape value*.

  escape      = best open escape option          (what the carrier can still do)
  lane_tax    = escape without presser - escape   (what this presser took away)
  lanes_cut   = sum of escape value he removed over all options, even ones a
                teammate also covered            (individual work, not team result)
  trap_tax    = drop in his best *any* option     (pushing him towards losing it)
  unit_tax    = same as lane_tax but removing the whole pressing chain (team press)
  ways_out    = chance at least one (value-weighted) escape is on; ways_tax is the presser's dent in it
  credit_share = presser's removal tax / sum of every nearby defender's removal tax

lane_tax splits into ``block`` (his body in lanes / on receivers) and ``rush``
(arriving so fast that long, difficult passes become harder to hit).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from lane_tax.config import (
    BYPASS_OPTION_N,
    CARRIER_TURN_DECEL_M_S2,
    CARRY_ANGLES_DEG,
    CARRY_DISTANCES_M,
    MAX_OPTION_RANGE_M,
    MAX_PASS_TURN_DELAY_S,
    MOVING_CARRIER_M_S,
    PASS_ACCURACY_SCALE_M,
    PROGRESS_OPTION_M,
    RUSH_BASE_PENALTY,
    RUSH_LONG_PASS_PENALTY,
    RUSH_TIME_S,
    RUSH_WIDTH_S,
    SWITCH_OPTION_M,
    TIME_SIGMA_EXTRAPOLATED_S,
    TIME_SIGMA_S,
    TRACKING_HZ,
)
from lane_tax.geometry import Movers, arrival_time, carry_win_probs, pass_win_probs, turn_delay

CREDIT_RADIUS_M = 20.0  # defenders considered when sharing out credit for the squeeze
VELOCITY_LAG_FRAMES = 3
MAX_TRACKED_SPEED_M_S = 9.5
GOAL_VALUE_SCALE_M = 25.0


@dataclass
class Player:
    pid: int
    team: int
    x: float
    y: float
    vx: float
    vy: float
    detected: bool


@dataclass
class Scene:
    """One frame seen from the carrier: x' always points at the goal he attacks."""

    frame: int
    carrier: Player
    teammates: list[Player]
    defenders: list[Player]
    presser_idx: int | None
    attack_sign: int
    half_length: float
    half_width: float
    unit_idx: tuple[int, ...] = ()  # presser + the rest of his pressing chain

    def to_attack(self, x: float, y: float) -> tuple[float, float]:
        return x * self.attack_sign, y * self.attack_sign

    def movers(self) -> Movers:
        if not self.defenders:
            return Movers(np.zeros((0, 2)), np.zeros((0, 2)), np.zeros(0))
        pos = np.array([[d.x, d.y] for d in self.defenders])
        vel = np.array([[d.vx, d.vy] for d in self.defenders])
        sig = np.array([TIME_SIGMA_S if d.detected else TIME_SIGMA_EXTRAPOLATED_S for d in self.defenders])
        return Movers(pos, vel, sig)


@dataclass
class Option:
    kind: str  # "pass" | "carry"
    target_id: int | None
    start: tuple[float, float]
    end: tuple[float, float]
    length: float
    dx: float  # metres gained towards goal
    dy: float
    bypassed: int
    beats_presser: bool
    category: str  # progressive | switch | past_presser | lateral | back | carry
    escape: bool
    value: float
    accuracy: float
    accuracy_no_rush: float
    fail: np.ndarray  # (n_def,) chance each defender wins it
    offside: bool = False
    target_detected: bool = True
    base_accuracy: float = 1.0  # before any rush penalty

    def clear_prob(self, exclude: int | tuple[int, ...] | None = None) -> float:
        """Chance no (non-excluded) defender wins the ball."""
        p = self.fail
        if exclude is not None:
            idx = [i for i in ((exclude,) if isinstance(exclude, int) else exclude) if 0 <= i < p.size]
            p = np.delete(p, idx)
        return float(np.prod(1.0 - np.clip(p, 0.0, 1.0)))

    def open_prob(self, exclude: int | tuple[int, ...] | None = None, rush: bool = True) -> float:
        return self.clear_prob(exclude) * (self.accuracy if rush else self.accuracy_no_rush)


@dataclass
class TaxResult:
    frame: int
    escape: float
    escape_no_presser: float
    escape_no_presser_body: float
    lane_tax: float
    lane_tax_block: float
    lane_tax_rush: float
    lane_tax_pct: float | None
    escape_no_unit: float
    unit_tax: float
    ways_out: float
    ways_out_no_presser: float
    ways_tax: float
    credit_share: float | None  # presser's share of the squeeze from all defenders near the ball
    squeeze_total: float
    top_squeezer_id: int | None
    lanes_cut: float
    retention: float
    retention_no_presser: float
    trap_tax: float
    n_escape_open: int
    n_escape_open_no_presser: int
    n_options: int
    best_option: str
    best_option_no_presser: str
    presser_time_to_carrier_s: float | None
    detected_share: float
    options: list[Option] = field(default_factory=list)


def goal_value(xa: float, ya: float, half_length: float) -> float:
    """Simple danger field in attack coordinates: ~0.02 at own goal, ~0.5 at the box edge."""
    return float(np.exp(-np.hypot(half_length - xa, ya) / GOAL_VALUE_SCALE_M))


def _velocity(cur: pd.DataFrame, prev: pd.DataFrame | None, lag: int) -> pd.DataFrame:
    out = cur.copy()
    out["vx"] = 0.0
    out["vy"] = 0.0
    if prev is not None and not prev.empty:
        m = out.join(prev[["x", "y"]], rsuffix="_prev", how="left")
        dt = lag / TRACKING_HZ
        vx = ((m["x"] - m["x_prev"]) / dt).fillna(0.0)
        vy = ((m["y"] - m["y_prev"]) / dt).fillna(0.0)
        speed = np.hypot(vx, vy)
        scale = np.where(speed > MAX_TRACKED_SPEED_M_S, MAX_TRACKED_SPEED_M_S / np.maximum(speed, 1e-6), 1.0)
        out["vx"] = vx * scale
        out["vy"] = vy * scale
    return out


def build_scene(
    pos_index: pd.DataFrame,
    team_of: dict[int, int],
    frame: int,
    carrier_id: int,
    presser_id: int | None,
    attack_sign: int,
    half_length: float,
    half_width: float,
    unit_ids: tuple[int, ...] = (),
) -> Scene | None:
    """Assemble a Scene from tracking indexed by (frame, player_id) with x, y, is_detected."""
    try:
        cur = pos_index.loc[frame]
    except KeyError:
        return None
    prev = None
    for lag in (VELOCITY_LAG_FRAMES, 2, 1):
        try:
            prev = pos_index.loc[frame - lag]
            break
        except KeyError:
            continue
    cur = _velocity(cur, prev, lag if prev is not None else 1).dropna(subset=["x", "y"])
    if carrier_id not in cur.index:
        return None
    attack_team = team_of.get(carrier_id)

    def player(pid: int, r: pd.Series) -> Player:
        return Player(int(pid), team_of.get(int(pid), -1), float(r["x"]), float(r["y"]),
                      float(r["vx"]), float(r["vy"]), bool(r["is_detected"]))

    carrier = player(carrier_id, cur.loc[carrier_id])
    teammates, defenders = [], []
    presser_idx = None
    unit: list[int] = []
    for pid, r in cur.iterrows():
        pid = int(pid)
        if pid == carrier_id:
            continue
        tid = team_of.get(pid)
        if tid == attack_team:
            teammates.append(player(pid, r))
        elif tid is not None:
            if pid == presser_id:
                presser_idx = len(defenders)
            if pid == presser_id or pid in unit_ids:
                unit.append(len(defenders))
            defenders.append(player(pid, r))
    return Scene(frame, carrier, teammates, defenders, presser_idx, attack_sign, half_length, half_width, tuple(unit))


def _offside_line(scene: Scene) -> float:
    xs = sorted((scene.to_attack(d.x, d.y)[0] for d in scene.defenders), reverse=True)
    return xs[1] if len(xs) >= 2 else scene.half_length


def _option_value(dx: float, bypassed: int, switch: bool, dv: float) -> float:
    """Escape value: getting out at all is worth something; more for gaining ground,
    taking opponents out of the game, switching play, and moving into danger."""
    return 0.4 + 0.02 * max(dx, 0.0) + 0.1 * bypassed + (0.2 if switch else 0.0) + 2.0 * max(dv, 0.0)


def _rush_factor(length: float, presser_t: float | None) -> float:
    if presser_t is None:
        return 1.0
    rushed = 1.0 / (1.0 + np.exp(-(RUSH_TIME_S - presser_t) / RUSH_WIDTH_S))
    return float(1.0 - rushed * (RUSH_BASE_PENALTY + RUSH_LONG_PASS_PENALTY * min(length / 40.0, 1.0)))


def _nearest_time_to_carrier(scene: Scene, movers: Movers, exclude: int | tuple[int, ...] | None) -> float | None:
    if movers.n == 0:
        return None
    t = arrival_time(movers, np.array([[scene.carrier.x, scene.carrier.y]]))[:, 0]
    if exclude is not None:
        t = np.delete(t, [i for i in ((exclude,) if isinstance(exclude, int) else exclude) if 0 <= i < t.size])
    return float(t.min()) if t.size else None


def build_options(scene: Scene) -> tuple[list[Option], float | None, float | None]:
    movers = scene.movers()
    c = np.array([scene.carrier.x, scene.carrier.y])
    cxa, cya = scene.to_attack(*c)
    line = _offside_line(scene)
    def_attack = [scene.to_attack(d.x, d.y) for d in scene.defenders]
    pidx = scene.presser_idx
    presser_xa = def_attack[pidx][0] if pidx is not None else None
    presser_goal_side = presser_xa is not None and presser_xa > cxa

    t_all = _nearest_time_to_carrier(scene, movers, None)
    t_wo = _nearest_time_to_carrier(scene, movers, pidx)
    v_c = goal_value(cxa, cya, scene.half_length)
    c_vel = np.array([scene.carrier.vx, scene.carrier.vy])

    def turn(dst: np.ndarray) -> float:
        return turn_delay(c_vel, dst - c, MOVING_CARRIER_M_S, CARRIER_TURN_DECEL_M_S2)

    opts: list[Option] = []
    for tm in scene.teammates:
        lead = min(1.0, np.hypot(tm.x - c[0], tm.y - c[1]) / 15.0)
        dst = np.array([tm.x + tm.vx * lead, tm.y + tm.vy * lead])
        dst[0] = np.clip(dst[0], -scene.half_length, scene.half_length)
        dst[1] = np.clip(dst[1], -scene.half_width, scene.half_width)
        length = float(np.linalg.norm(dst - c))
        if length < 2.0 or length > MAX_OPTION_RANGE_M:
            continue
        rxa, rya = scene.to_attack(*dst)
        txa, _ = scene.to_attack(tm.x, tm.y)
        offside = txa > 0 and txa > max(line, cxa) + 0.5
        dx, dy = rxa - cxa, rya - cya
        bypassed = sum(1 for xa, _ in def_attack if cxa < xa < rxa)
        beats = presser_goal_side and rxa > presser_xa + 1.0
        switch = abs(dy) >= SWITCH_OPTION_M and dx >= -PROGRESS_OPTION_M
        if dx >= PROGRESS_OPTION_M or (bypassed >= BYPASS_OPTION_N and dx > 0):
            cat = "progressive"
        elif switch:
            cat = "switch"
        elif beats and dx >= -2.0:
            cat = "past_presser"
        elif dx <= -PROGRESS_OPTION_M:
            cat = "back"
        else:
            cat = "lateral"
        escape = cat in ("progressive", "switch", "past_presser") and not offside
        dv = goal_value(rxa, rya, scene.half_length) - v_c
        intercept, reception = pass_win_probs(c, dst, movers, min(turn(dst), MAX_PASS_TURN_DELAY_S))
        fail = 1.0 - (1.0 - intercept) * (1.0 - reception)
        base_acc = float(np.exp(-(length / PASS_ACCURACY_SCALE_M) ** 2))
        weight = 1.0 if tm.detected else 0.85
        opts.append(Option(
            "pass", tm.pid, (c[0], c[1]), (float(dst[0]), float(dst[1])), length, dx, dy, bypassed, beats, cat,
            escape, _option_value(dx, bypassed, switch, dv) if escape else 0.0,
            base_acc * _rush_factor(length, t_all) * weight, base_acc * _rush_factor(length, t_wo) * weight,
            fail, offside, tm.detected, base_acc * weight,
        ))

    for dist in CARRY_DISTANCES_M:
        for ang in CARRY_ANGLES_DEG:
            a = np.deg2rad(ang)
            dxa, dya = dist * np.cos(a), dist * np.sin(a)
            txa, tya = cxa + dxa, cya + dya
            if abs(txa) > scene.half_length or abs(tya) > scene.half_width:
                continue
            dst = np.array([txa * scene.attack_sign, tya * scene.attack_sign])
            beats = presser_goal_side and txa > presser_xa + 1.0
            bypassed = sum(1 for xa, _ in def_attack if cxa < xa < txa)
            dv = goal_value(txa, tya, scene.half_length) - v_c
            u = (dst - c) / max(float(np.linalg.norm(dst - c)), 1e-6)
            fail = carry_win_probs(c, dst, movers, turn(dst), float(np.dot(c_vel, u)))
            opts.append(Option(
                "carry", None, (c[0], c[1]), (float(dst[0]), float(dst[1])), dist, dxa, dya, bypassed, beats,
                "carry", True, _option_value(dxa, bypassed, False, dv), 1.0, 1.0, fail,
            ))
    return opts, t_all, t_wo


def _best(
    opts: list[Option], exclude: int | tuple[int, ...] | None, rush: bool, escape_only: bool
) -> tuple[float, Option | None]:
    best, best_opt = 0.0, None
    for o in opts:
        if o.offside or (escape_only and not o.escape):
            continue
        score = o.open_prob(exclude, rush) * (o.value if escape_only else 1.0)
        if score > best:
            best, best_opt = score, o
    return best, best_opt


def _label(o: Option | None) -> str:
    if o is None:
        return "none"
    return f"{o.kind}:{o.category}:{o.target_id if o.target_id is not None else int(o.length)}"


def score_scene(scene: Scene) -> TaxResult:
    opts, t_all, _ = build_options(scene)
    p = scene.presser_idx
    esc, best = _best(opts, None, True, True)
    esc_wo, best_wo = _best(opts, p, False, True) if p is not None else (esc, best)
    esc_wo_body, _ = _best(opts, p, True, True) if p is not None else (esc, best)
    ret, _ = _best(opts, None, True, False)
    ret_wo, _ = _best(opts, p, False, False) if p is not None else (ret, None)
    movers = scene.movers()
    t_c = (arrival_time(movers, np.array([[scene.carrier.x, scene.carrier.y]]))[:, 0]
           if movers.n else np.zeros(0))
    esc_wo_unit = _escape_without(scene, opts, t_c, scene.unit_idx)[0] if scene.unit_idx else esc_wo
    ways = _ways_out(opts)
    ways_wo = _escape_without(scene, opts, t_c, (p,))[1] if p is not None else ways

    c = np.array([scene.carrier.x, scene.carrier.y])
    taxes: dict[int, float] = {}
    for j, d in enumerate(scene.defenders):
        if np.hypot(d.x - c[0], d.y - c[1]) <= CREDIT_RADIUS_M or j == p:
            taxes[j] = max(_escape_without(scene, opts, t_c, (j,))[0] - esc, 0.0)
    total = sum(taxes.values())
    share = (taxes.get(p, 0.0) / total) if (p is not None and total > 1e-6) else None
    top = max(taxes, key=taxes.get) if taxes else None

    lanes_cut = 0.0
    n_open = n_open_wo = 0
    for o in opts:
        if not o.escape or o.offside:
            continue
        with_p = o.open_prob(None, True)
        without = o.open_prob(p, False) if p is not None else with_p
        lanes_cut += o.value * max(without - with_p, 0.0)
        n_open += with_p >= 0.5
        n_open_wo += without >= 0.5

    tax = esc_wo - esc
    block = esc_wo_body - esc
    detected = [scene.carrier.detected] + [pl.detected for pl in scene.teammates + scene.defenders
                                           if np.hypot(pl.x - scene.carrier.x, pl.y - scene.carrier.y) <= 25]
    return TaxResult(
        frame=scene.frame, escape=esc, escape_no_presser=esc_wo, escape_no_presser_body=esc_wo_body,
        lane_tax=tax, lane_tax_block=block, lane_tax_rush=tax - block,
        lane_tax_pct=(tax / esc_wo) if esc_wo > 1e-6 else None,
        escape_no_unit=esc_wo_unit, unit_tax=esc_wo_unit - esc,
        ways_out=ways, ways_out_no_presser=ways_wo, ways_tax=ways_wo - ways,
        credit_share=share, squeeze_total=total,
        top_squeezer_id=scene.defenders[top].pid if top is not None and taxes[top] > 1e-6 else None,
        lanes_cut=lanes_cut,
        retention=ret, retention_no_presser=ret_wo, trap_tax=ret_wo - ret,
        n_escape_open=int(n_open), n_escape_open_no_presser=int(n_open_wo),
        n_options=sum(1 for o in opts if o.kind == "pass" and not o.offside),
        best_option=_label(best), best_option_no_presser=_label(best_wo),
        presser_time_to_carrier_s=_presser_time(scene),
        detected_share=float(np.mean(detected)), options=opts,
    )


def _escape_without(scene: Scene, opts: list[Option], t_carrier: np.ndarray,
                    exclude: tuple[int, ...]) -> tuple[float, float]:
    """(best escape, ways out) if the ``exclude`` defenders vanished — their bodies and their rush."""
    keep = np.ones(t_carrier.size, dtype=bool)
    keep[[i for i in exclude if 0 <= i < t_carrier.size]] = False
    t_rest = float(t_carrier[keep].min()) if keep.any() else None
    best, none_on = 0.0, 1.0
    for o in opts:
        if o.offside or not o.escape:
            continue
        acc = o.base_accuracy * _rush_factor(o.length, t_rest) if o.kind == "pass" else 1.0
        on = o.clear_prob(exclude) * acc
        best = max(best, on * o.value)
        none_on *= 1.0 - on * min(o.value, 1.0)
    return best, 1.0 - none_on


def _ways_out(opts: list[Option]) -> float:
    """Chance at least one escape is on, each weighted by how good it is (capped at 1).
    Unlike the best single option, cutting two of three lanes moves this."""
    none_on = 1.0
    for o in opts:
        if o.escape and not o.offside:
            none_on *= 1.0 - o.open_prob() * min(o.value, 1.0)
    return 1.0 - none_on


def _presser_time(scene: Scene) -> float | None:
    if scene.presser_idx is None:
        return None
    m = scene.movers()
    return float(arrival_time(
        Movers(m.pos[[scene.presser_idx]], m.vel[[scene.presser_idx]], m.sigma[[scene.presser_idx]]),
        np.array([[scene.carrier.x, scene.carrier.y]]),
    )[0, 0])

