"""Full sports-director story of a single press, built from the event chain + tracking.

A press is judged on what it *made happen*, in four beats:

1. Context   - minute, score, zone, phase, how many teammates joined the press.
2. The press - how hard and how close the presser got, goal-side or not.
3. Response  - what the carrier was forced to do (pass back, go long, lose it, foul...).
4. Outcome   - follow every possession for up to ``HORIZON_S`` seconds until the
               pressing team wins the ball, the ball goes out, a foul, a shot, or
               the attack simply keeps it (then: forced back / contained / played through).

The possession chain comes from SkillCorner ``player_possession`` events (authoritative);
tracking is only used for positions, distances and ball progress.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from lane_tax.data import load_dynamic_events, load_match_meta, load_phases_of_play

HORIZON_S = 8.0
IN_FLIGHT_GRACE_S = 4.0
LONG_PASS_M = 30.0
FAST_REGAIN_S = 5.0
SHOT_AFTER_REGAIN_S = 15.0
PROGRESS_THROUGH_M = 10.0
PROGRESS_BACK_M = -5.0
TIGHT_AT_RELEASE_M = 3.5
FAR_AT_RELEASE_M = 5.5
ON_BALL_M = 3.0
EVENT_TRACKING_TOL_M = 1.5
NOT_A_PRESS_SPEED = 0.5
NOT_A_PRESS_GAP_M = 4.0
POSITIONAL_SPEED = 0.8
HIGH_PRESSURE_M = 2.5
MEDIUM_PRESSURE_M = 4.5
SUPPORT_RADIUS_M = 10.0

OUTCOMES: dict[str, dict[str, str]] = {
    "won_by_presser": {"title": "WON IT BACK — PRESSER HIMSELF", "grade": "win"},
    "won_fast": {"title": "WON IT BACK", "grade": "win"},
    "forced_long_won": {"title": "FORCED IT LONG — WON IT BACK", "grade": "win"},
    "forced_out": {"title": "FORCED IT OUT OF PLAY", "grade": "good"},
    "won_late": {"title": "WON IT BACK (LATE)", "grade": "good"},
    "forced_back": {"title": "FORCED THEM BACKWARDS", "grade": "good"},
    "contained": {"title": "CONTAINED — NO DAMAGE, NO WIN", "grade": "neutral"},
    "played_through": {"title": "PRESS PLAYED THROUGH", "grade": "bad"},
    "foul_given": {"title": "PRESS GAVE AWAY A FOUL", "grade": "bad"},
    "shot_conceded": {"title": "PRESS BEATEN — SHOT CONCEDED", "grade": "bad"},
}

GRADE_STYLE: dict[str, dict[str, str]] = {
    "win": {"color": "#1B5E20", "bg": "#E3F4E4"},
    "good": {"color": "#2E7D32", "bg": "#EEF7EE"},
    "neutral": {"color": "#546E7A", "bg": "#EEF2F4"},
    "bad": {"color": "#C62828", "bg": "#FCEBEA"},
}


@dataclass
class Segment:
    """One stretch of the timeline: a player holding the ball, or the ball between players."""

    start_frame: int
    end_frame: int
    kind: str  # "possession" | "transit"
    team_id: int | None = None
    player_id: int | None = None
    player_name: str = ""
    label: str = ""


@dataclass
class PressStory:
    review_id: str
    event_id: str
    subtype: str
    frame0: int
    period: int
    clock: str
    score_text: str
    phase_type: str
    zone: str
    attack_team_id: int
    attack_team: str
    attack_abbr: str
    press_team_id: int
    press_team: str
    press_abbr: str
    attack_sign: int
    presser_id: int
    presser_name: str
    carrier_id: int
    carrier_name: str
    d_start: float
    d_min: float
    closing_speed: float
    goal_side_start: bool | None
    chain_size: int
    chain_position: int
    chain_names: list[str]
    release_frame: int
    time_on_ball_s: float
    presser_dist_at_release: float | None
    response: str
    response_kind: str
    outcome: str
    outcome_title: str
    grade: str
    outcome_detail: str
    resolution_frame: int
    regain_frame: int | None
    regain_player: str
    regain_xy: tuple[float, float] | None
    ball_progress_m: float | None
    epv_start: float | None
    epv_end: float | None
    attack_shot: bool
    press_shot_after: bool
    credit: str
    credit_detail: str
    headline: str
    sequence_txt: str = ""
    press_type: str = ""
    pressure_level: str = ""
    presser_grade: str = "neutral"
    n_options: int | None = None
    teammates_near: int = 0
    ahead_m: float | None = None
    regain_player_id: int | None = None
    segments: list[Segment] = field(default_factory=list)
    checks: list[tuple[str, bool, str]] = field(default_factory=list)

    @property
    def checks_ok(self) -> bool:
        return all(ok for _, ok, _ in self.checks)

    def beats(self) -> list[tuple[str, int, str]]:
        """(beat title, frame it becomes true, text) for the four-beat story panel."""
        chain = (
            f"{self.chain_size}-man press ({', '.join(self.chain_names)})"
            if self.chain_size > 1
            else "pressing alone"
        )
        gs = {True: "goal-side", False: "NOT goal-side", None: "side unknown"}[self.goal_side_start]
        opts = f"{self.n_options} passing options" if self.n_options is not None else "options unknown"
        press_txt = (
            f"Setup: {PRESS_TYPE_LABEL.get(self.press_type, self.press_type)}. "
            f"{self.presser_name} closes {self.carrier_name}: {self.d_start:.1f}m -> {self.d_min:.1f}m "
            f"at {self.closing_speed:.1f} m/s, {gs}. {chain}; {opts}, "
            f"{self.teammates_near} teammates within {SUPPORT_RADIUS_M:.0f}m."
        )
        rel = (
            f"{self.presser_dist_at_release:.1f}m away when ball released"
            if self.presser_dist_at_release is not None
            else "release distance unknown"
        )
        resp_txt = f"{self.response} after {self.time_on_ball_s:.1f}s on the ball ({rel})."
        out_txt = self.outcome_detail
        if self.sequence_txt:
            out_txt += f" Ball went: {self.sequence_txt}."
        return [
            ("CONTEXT", self.frame0 - 10, f"{self.clock} | {self.score_text} | {self.phase_type} | {self.zone}"),
            ("THE PRESS", self.frame0, press_txt),
            ("FORCED RESPONSE", self.release_frame, resp_txt),
            ("TEAM OUTCOME", self.resolution_frame, out_txt),
        ]


def _f(v: Any) -> float | None:
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return None if np.isnan(x) else x


def _attack_sign(side: Any) -> int:
    return 1 if str(side) == "left_to_right" else -1


def _surname(name: Any) -> str:
    s = str(name) if pd.notna(name) else "?"
    return s.split(". ", 1)[-1] if ". " in s else s


class MatchContext:
    """Per-match lookups reused across many presses."""

    def __init__(self, match_id: int, players: pd.DataFrame, frame_meta: pd.DataFrame) -> None:
        self.match_id = match_id
        self.meta = load_match_meta(match_id)
        self.events = load_dynamic_events(match_id).sort_values("frame_start", kind="stable").reset_index(drop=True)
        self.phases = load_phases_of_play(match_id)
        self.pp = self.events[self.events["event_type"] == "player_possession"].reset_index(drop=True)
        self.eng = self.events[self.events["event_type"] == "on_ball_engagement"].reset_index(drop=True)
        self.team_of: dict[int, int] = {int(p["id"]): int(p["team_id"]) for p in self.meta["players"]}
        self.name_of: dict[int, str] = {
            int(p["id"]): f"{str(p.get('first_name', ''))[:1]}. {p.get('last_name', '')}".strip()
            for p in self.meta["players"]
        }
        self.teams = {
            int(self.meta["home_team"]["id"]): self.meta["home_team"],
            int(self.meta["away_team"]["id"]): self.meta["away_team"],
        }
        self.home_id = int(self.meta["home_team"]["id"])
        self.away_id = int(self.meta["away_team"]["id"])
        goals = self.pp[self.pp["game_interruption_after"] == "goal_for"]
        self.goals = [(int(r.frame_end), int(r.team_id)) for r in goals.itertuples()]
        self.players = players
        self.frame_meta = frame_meta.set_index("frame")
        self._pos = players.set_index(["frame", "player_id"])[["x", "y", "is_detected"]]

    def team_name(self, tid: int) -> str:
        return str(self.teams[tid]["short_name"])

    def team_abbr(self, tid: int) -> str:
        return str(self.teams[tid].get("acronym") or self.team_name(tid)[:3].upper())

    def xy(self, frame: int, pid: int) -> tuple[float, float, bool] | None:
        try:
            r = self._pos.loc[(frame, pid)]
        except KeyError:
            return None
        if pd.isna(r["x"]):
            return None
        return float(r["x"]), float(r["y"]), bool(r["is_detected"])

    def ball(self, frame: int) -> tuple[float, float] | None:
        if frame not in self.frame_meta.index:
            return None
        r = self.frame_meta.loc[frame]
        if pd.isna(r["ball_x"]):
            return None
        return float(r["ball_x"]), float(r["ball_y"])

    def ball_filled(self, frame: int, back: int = 15) -> tuple[float, float] | None:
        for f in range(frame, frame - back, -1):
            b = self.ball(f)
            if b is not None:
                return b
        return None

    def score_at(self, frame: int) -> dict[int, int]:
        s = {self.home_id: 0, self.away_id: 0}
        for gf, tid in self.goals:
            if gf < frame:
                s[tid] += 1
        return s

    def teammates_near(self, frame: int, carrier_id: int, presser_id: int, press_team: int) -> int:
        c = self.xy(frame, carrier_id)
        if c is None:
            return 0
        try:
            g = self._pos.loc[frame].reset_index()
        except KeyError:
            return 0
        mates = g[(g["player_id"].map(self.team_of) == press_team) & (g["player_id"] != presser_id)]
        return int((np.hypot(mates["x"] - c[0], mates["y"] - c[1]) <= SUPPORT_RADIUS_M).sum())

    def dist(self, frame: int, a: int, b: int) -> float | None:
        pa, pb = self.xy(frame, a), self.xy(frame, b)
        if pa is None or pb is None:
            return None
        return float(np.hypot(pa[0] - pb[0], pa[1] - pb[1]))


def _segments(ctx: MatchContext, start: int, end: int) -> list[Segment]:
    """Possessions + the ball-in-transit gaps between them, clipped to [start, end]."""
    pp = ctx.pp[(ctx.pp["frame_end"] >= start) & (ctx.pp["frame_start"] <= end)]
    segs: list[Segment] = []
    cursor = start
    prev: pd.Series | None = None
    for _, p in pp.iterrows():
        fs, fe = int(p["frame_start"]), int(p["frame_end"])
        if fs > cursor:
            if prev is not None and prev["end_type"] == "pass":
                lab = f"pass in flight from {_surname(prev['player_name'])}"
            elif prev is not None and pd.notna(prev.get("game_interruption_after")):
                lab = "ball out of play"
            else:
                lab = "loose ball — nobody has it"
            segs.append(Segment(cursor, fs - 1, "transit", label=lab))
        tid = int(p["team_id"])
        segs.append(
            Segment(
                max(fs, start), min(fe, end), "possession", tid, int(p["player_id"]),
                str(p["player_name"]), f"{_surname(p['player_name'])} ({ctx.team_abbr(tid)})",
            )
        )
        cursor = fe + 1
        prev = p
    if cursor <= end:
        lab = "ball out of play" if prev is not None and pd.notna(prev.get("game_interruption_after")) else "loose ball — nobody has it"
        segs.append(Segment(cursor, end, "transit", label=lab))
    return segs


def _response_text(p0: pd.Series) -> tuple[str, str]:
    et = str(p0["end_type"])
    if et == "pass":
        raw_dir = p0.get("pass_direction")
        direction = str(raw_dir).replace("sideway_", "sideways ").replace("_", " ") if pd.notna(raw_dir) else ""
        rng = str(p0["pass_range"]) if pd.notna(p0.get("pass_range")) else ""
        dist = _f(p0.get("pass_distance"))
        target = _surname(p0.get("player_targeted_name"))
        ok = str(p0.get("pass_outcome"))
        okt = {"successful": "completed", "unsuccessful": "NOT completed"}.get(ok, "outcome unknown")
        dtxt = f"{dist:.0f}m" if dist is not None else ""
        kind = "pass_back" if "backward" in direction else ("pass_long" if rng == "long" else "pass")
        if ok == "unsuccessful":
            kind = "pass_failed"
        desc = " ".join(w for w in (direction, rng, dtxt) if w)
        return (f"Plays a {desc} pass to {target}, {okt}" if desc else f"Tries a pass to {target}, {okt}"), kind
    if et == "possession_loss":
        return "Loses the ball under pressure", "lost"
    if et == "clearance":
        return "Forced to clear it", "clearance"
    if et == "foul_suffered":
        return "Gets fouled", "foul"
    if et == "shot":
        return "Gets a shot away", "shot"
    return "Ball comes off him (unclear action)", "unknown"


def build_story(ctx: MatchContext, press_event_id: str, review_id: str = "") -> PressStory:
    eng = ctx.eng[ctx.eng["event_id"] == press_event_id].iloc[0]
    frame0 = int(eng["frame_start"])
    presser_id = int(eng["player_id"])
    press_team = int(eng["team_id"])
    p0_rows = ctx.pp[ctx.pp["event_id"] == eng["associated_player_possession_event_id"]]
    if p0_rows.empty:
        p0_rows = ctx.pp[(ctx.pp["frame_start"] <= frame0) & (ctx.pp["frame_end"] >= frame0)]
    p0 = p0_rows.iloc[0]
    carrier_id = int(p0["player_id"])
    attack_team = int(p0["team_id"])
    sign = _attack_sign(p0["attacking_side"])

    checks: list[tuple[str, bool, str]] = []
    checks.append(("teams differ", ctx.team_of.get(presser_id) != ctx.team_of.get(carrier_id) and press_team != attack_team,
                   f"{ctx.team_abbr(press_team)} presser vs {ctx.team_abbr(attack_team)} carrier"))
    on_from = max(frame0, int(p0["frame_start"]))
    on_to = max(int(p0["frame_end"]), on_from + 3)
    cb = [ctx.xy(f, carrier_id) for f in range(on_from, on_to + 1)]
    bb = [ctx.ball(f) for f in range(on_from, on_to + 1)]
    on_ball = [np.hypot(c[0] - b[0], c[1] - b[1]) for c, b in zip(cb, bb) if c and b]
    checks.append(("carrier on ball", bool(on_ball) and min(on_ball) <= ON_BALL_M,
                   f"closest {min(on_ball):.1f}m to ball" if on_ball else "no ball/carrier position"))
    ph = ctx.phases[(ctx.phases["frame_start"] <= frame0) & (ctx.phases["frame_end"] >= frame0)
                    & (ctx.phases["team_in_possession_id"] == attack_team)]
    if not ph.empty:
        ok = _attack_sign(ph.iloc[0]["attacking_side"]) == sign
        checks.append(("attack direction", ok, f"{ctx.team_abbr(attack_team)} attacking {'->' if sign > 0 else '<-'}"))
    d_track = ctx.dist(frame0, presser_id, carrier_id)
    d_evt = _f(eng["interplayer_distance_start"])
    if d_track is not None and d_evt is not None:
        checks.append(("event vs tracking distance", abs(d_track - d_evt) <= EVENT_TRACKING_TOL_M,
                       f"event {d_evt:.1f}m / tracking {d_track:.1f}m"))
    pres = ctx.xy(frame0, presser_id)
    checks.append(("presser on camera", bool(pres and pres[2]), "detected" if pres and pres[2] else "estimated position"))

    # context
    score = ctx.score_at(frame0)
    sa, sp = score[attack_team], score[press_team]
    state = "level" if sa == sp else (f"{ctx.team_abbr(press_team)} leading" if sp > sa else f"{ctx.team_abbr(press_team)} trailing")
    hs, as_ = score[ctx.home_id], score[ctx.away_id]
    score_text = f"{ctx.team_abbr(ctx.home_id)} {hs}-{as_} {ctx.team_abbr(ctx.away_id)} ({state})"
    clock = f"{int(eng['minute_start'])}' (H{int(eng['period'])})"
    third_attack = str(p0["third_start"]).replace("_", " ")
    zone = f"ball in {ctx.team_abbr(attack_team)}'s {third_attack}, {str(p0['channel_start']).replace('_', ' ')}"
    phase_type = str(eng.get("team_in_possession_phase_type", "")).replace("_", " ")

    # the press
    d_start = _f(eng["interplayer_distance_start"]) or (d_track or np.nan)
    d_min = _f(eng["interplayer_distance_min"]) or d_start
    dur = max((int(eng["frame_end"]) - frame0) / 10.0, 0.1)
    closing_speed = max(d_start - d_min, 0.0) / dur
    gs = eng.get("goal_side_start")
    goal_side = None if pd.isna(gs) else bool(gs)
    chain_names: list[str] = [_surname(eng["player_name"])]
    chain_size, chain_pos = 1, 1
    if bool(eng.get("pressing_chain")) and pd.notna(eng.get("pressing_chain_index")):
        ch = ctx.eng[(ctx.eng["pressing_chain_index"] == eng["pressing_chain_index"]) & (ctx.eng["team_id"] == press_team)]
        ch = ch.sort_values("frame_start")
        chain_names = list(dict.fromkeys(_surname(n) for n in ch["player_name"]))
        chain_size = len(chain_names)
        chain_pos = int(eng.get("index_in_pressing_chain") or 1)

    # forced response
    release = int(p0["frame_end"])
    response, response_kind = _response_text(p0)
    time_on_ball = max(release - frame0, 0) / 10.0
    d_release = ctx.dist(release, presser_id, carrier_id)

    # follow the chain
    horizon = frame0 + int(HORIZON_S * 10)
    grace = horizon + int(IN_FLIGHT_GRACE_S * 10)
    later = ctx.pp[(ctx.pp["frame_start"] >= int(p0["frame_start"]))].reset_index(drop=True)
    outcome = ""
    resolution = horizon
    regain_frame: int | None = None
    regain_player = ""
    regain_player_id: int | None = None
    attack_shot = False
    last_attack = p0
    seq: list[pd.Series] = []
    control_frame: int | None = None
    eng_end = str(eng.get("end_type") or "")
    for _, p in later.iterrows():
        fs = int(p["frame_start"])
        if fs > horizon:
            in_flight = (
                int(last_attack["frame_end"]) <= horizon
                and pd.isna(last_attack.get("game_interruption_after"))
                and fs <= grace
            )
            if not in_flight:
                break
            if int(p["team_id"]) == attack_team:
                seq.append(p)
                last_attack, control_frame = p, fs
                break
        if int(p["team_id"]) != attack_team:
            regain_frame, regain_player = fs, str(p["player_name"])
            regain_player_id = int(p["player_id"])
            resolution = fs
            break
        seq.append(p)
        last_attack = p
        if p["end_type"] == "shot":
            attack_shot, resolution, outcome = True, int(p["frame_end"]), "shot_conceded"
            break
        gi = p.get("game_interruption_after")
        if p["end_type"] == "foul_suffered" or (pd.notna(gi) and str(gi) == "free_kick_for"):
            resolution, outcome = int(p["frame_end"]), "foul_given"
            break
        if pd.notna(gi):
            resolution = _ball_out_frame(ctx, int(p["frame_end"]))
            if str(gi).endswith("_against"):
                regain_frame, regain_player = resolution, f"{ctx.team_abbr(press_team)} restart"
                outcome = "forced_out"
            else:
                outcome = "contained"
            break
    if eng_end == "foul_committed":
        outcome, resolution = "foul_given", max(release, frame0 + 1)

    if control_frame is None:
        la_s, la_e = int(last_attack["frame_start"]), int(last_attack["frame_end"])
        control_frame = horizon if la_s <= horizon <= la_e else min(la_e, horizon)
    if regain_frame is None and not outcome:
        resolution = max(horizon, control_frame)

    went_long = any(
        q["end_type"] == "clearance"
        or (q["end_type"] == "pass" and (q.get("pass_range") == "long" or (_f(q.get("pass_distance")) or 0) >= LONG_PASS_M))
        for q in seq
    )
    t_regain = (regain_frame - frame0) / 10.0 if regain_frame is not None else None
    b0 = ctx.ball_filled(frame0)
    b1 = ctx.ball_filled(regain_frame if regain_frame is not None else control_frame)
    progress = (b1[0] - b0[0]) * sign if (b0 and b1) else None
    regain_xy = ctx.ball_filled(regain_frame) if regain_frame is not None else None
    escaped_then_lost = False
    if not outcome and regain_frame is not None:
        deep = regain_xy is not None and regain_xy[0] * -sign < -17.5
        late = t_regain is not None and t_regain > FAST_REGAIN_S
        if eng_end == "direct_regain" or regain_player == str(eng["player_name"]):
            outcome = "won_by_presser"
        elif progress is not None and progress >= PROGRESS_THROUGH_M and (deep or (late and not went_long)):
            escaped_then_lost = True
        elif went_long:
            outcome = "forced_long_won"
        else:
            outcome = "won_late" if late else "won_fast"
    if not outcome:
        played_past = False
        pr = ctx.xy(control_frame, presser_id)
        if pr and b1:
            played_past = (b1[0] - pr[0]) * sign > 5.0
        if escaped_then_lost or (
            progress is not None and (progress >= PROGRESS_THROUGH_M or (played_past and progress >= 5.0))
        ):
            outcome = "played_through"
        elif progress is not None and progress <= PROGRESS_BACK_M:
            outcome = "forced_back"
        else:
            outcome = "contained"

    press_shot = False
    if regain_frame is not None:
        nxt = ctx.pp[(ctx.pp["frame_start"] >= regain_frame) & (ctx.pp["frame_start"] <= regain_frame + int(SHOT_AFTER_REGAIN_S * 10))]
        for _, p in nxt.iterrows():
            if int(p["team_id"]) != press_team:
                break
            if p["end_type"] == "shot":
                press_shot = True
                break

    epv_start = _f(p0.get("possession_epv_for_start"))
    epv_end = 0.0 if regain_frame is not None else _f(last_attack.get("possession_epv_for_end"))

    # outcome detail
    a, pa = ctx.team_abbr(attack_team), ctx.team_abbr(press_team)
    prog_txt = f"ball moved {int(round(progress)) + 0:+d}m for {a}" if progress is not None else "ball progress unknown"
    hops = []
    for q in seq:
        tag = ""
        if q["end_type"] == "clearance":
            tag = " (clears)"
        elif q["end_type"] == "pass" and (q.get("pass_range") == "long" or (_f(q.get("pass_distance")) or 0) >= LONG_PASS_M):
            tag = " (long)"
        hops.append(_surname(q["player_name"]) + tag)
    if regain_frame is not None:
        hops.append(f"{_surname(regain_player)} ({pa})")
    sequence_txt = " > ".join(dict.fromkeys(hops)) if hops else ""
    if outcome == "forced_long_won":
        where = _regain_zone(regain_xy, -sign) if regain_xy else "location unknown"
        detail = f"{a} are forced to go long and {pa} win the second ball {t_regain:.1f}s after the press, {where}."
        if press_shot:
            detail += f" {pa} get a shot off it."
    elif outcome in ("won_by_presser", "won_fast", "won_late"):
        where = _regain_zone(regain_xy, -sign) if regain_xy else "location unknown"
        detail = f"{pa} win it back {t_regain:.1f}s after the press ({_surname(regain_player)}), {where}."
        if press_shot:
            detail += f" {pa} get a shot off it."
    elif outcome == "forced_out":
        detail = f"Ball goes out {(resolution - frame0) / 10:.1f}s later — {pa} restart ({str(last_attack['game_interruption_after']).split('_against')[0].replace('_', ' ')})."
    elif outcome == "foul_given":
        detail = f"Press ends in a free kick for {a} after {(resolution - frame0) / 10:.1f}s."
    elif outcome == "shot_conceded":
        detail = f"{a} keep it and shoot {(resolution - frame0) / 10:.1f}s after the press ({_surname(last_attack['player_name'])})."
    elif outcome == "played_through" and escaped_then_lost:
        detail = (
            f"{a} escape the press ({prog_txt}); {pa} only win it back {t_regain:.1f}s later, "
            f"{_regain_zone(regain_xy, -sign) if regain_xy else 'elsewhere'}."
        )
    elif outcome == "played_through":
        detail = f"{a} keep it and escape: {prog_txt} in {HORIZON_S:.0f}s, beyond the presser."
    elif outcome == "forced_back":
        detail = f"{a} keep it but go backwards: {prog_txt} in {HORIZON_S:.0f}s."
    else:
        detail = f"{a} keep it, no real progress: {prog_txt} in {HORIZON_S:.0f}s."
    if epv_start is not None and regain_frame is not None:
        detail += f" {a}'s possession value (EPV) {epv_start:.3f} -> gone."
    elif epv_start is not None and epv_end is not None:
        detail += f" {a}'s possession value (EPV) {epv_start:.3f} -> {epv_end:.3f}."

    forced_kind = response_kind in ("clearance", "lost", "pass_failed", "pass_long", "pass_back")
    sprint_forced = (
        closing_speed >= 4.0 and time_on_ball <= 1.0 and (d_release is None or d_release <= 9.0) and forced_kind
    )
    c0, pr0 = ctx.xy(frame0, carrier_id), ctx.xy(frame0, presser_id)
    ahead_m = (pr0[0] - c0[0]) * sign if (c0 and pr0) else None
    press_type = _press_type(goal_side, ahead_m, closing_speed, d_min)
    pressure = _pressure_level(d_release, d_min, sprint_forced)
    n_options = int(p0["n_passing_options"]) if pd.notna(p0.get("n_passing_options")) else None
    teammates_near = ctx.teammates_near(release, carrier_id, presser_id, press_team)
    credit, presser_grade, credit_detail = _presser_verdict(
        press_type, pressure, outcome, eng_end, response_kind, d_release, d_min, closing_speed,
        ahead_m, teammates_near,
    )
    info = OUTCOMES[outcome]
    headline = f"{_surname(eng['player_name'])} ({pa}) on {_surname(p0['player_name'])} ({a}): {info['title'].lower()} — {credit.lower()}"

    seg_start = frame0 - 20
    seg_end = max(resolution, frame0 + 10) + 20
    return PressStory(
        review_id=review_id, event_id=press_event_id, subtype=str(eng["event_subtype"]).replace("_", " "),
        frame0=frame0, period=int(eng["period"]), clock=clock, score_text=score_text, phase_type=phase_type,
        zone=zone, attack_team_id=attack_team, attack_team=ctx.team_name(attack_team), attack_abbr=a,
        press_team_id=press_team, press_team=ctx.team_name(press_team), press_abbr=pa, attack_sign=sign,
        presser_id=presser_id, presser_name=_surname(eng["player_name"]), carrier_id=carrier_id,
        carrier_name=_surname(p0["player_name"]), d_start=float(d_start), d_min=float(d_min),
        closing_speed=float(closing_speed), goal_side_start=goal_side, chain_size=chain_size,
        chain_position=chain_pos, chain_names=chain_names, release_frame=release, time_on_ball_s=time_on_ball,
        presser_dist_at_release=d_release, response=response, response_kind=response_kind, outcome=outcome,
        outcome_title=info["title"], grade=info["grade"], outcome_detail=detail, resolution_frame=resolution,
        regain_frame=regain_frame, regain_player=regain_player, regain_xy=regain_xy, ball_progress_m=progress,
        epv_start=epv_start, epv_end=epv_end, attack_shot=attack_shot, press_shot_after=press_shot,
        credit=credit, credit_detail=credit_detail, headline=headline, sequence_txt=sequence_txt,
        press_type=press_type, pressure_level=pressure, presser_grade=presser_grade, regain_player_id=regain_player_id,
        n_options=n_options, teammates_near=teammates_near, ahead_m=ahead_m,
        segments=_segments(ctx, seg_start, seg_end), checks=checks,
    )


def _ball_out_frame(ctx: MatchContext, from_frame: int, max_frames: int = 60) -> int:
    """First frame the ball crosses a pitch line after ``from_frame``; else the frame it is nearest a line."""
    half_l, half_w = ctx.meta["pitch_length"] / 2, ctx.meta["pitch_width"] / 2
    best_f, best_margin = from_frame, np.inf
    for f in range(from_frame, from_frame + max_frames + 1):
        b = ctx.ball(f)
        if b is None:
            continue
        margin = min(half_l - abs(b[0]), half_w - abs(b[1]))
        if margin <= 0:
            return f
        if margin < best_margin:
            best_f, best_margin = f, margin
    return best_f


def _regain_zone(xy: tuple[float, float], press_sign: int) -> str:
    """Where the pressing team won it, from the pressing team's point of view."""
    x = xy[0] * press_sign
    if x > 17.5:
        return "high up the pitch (their attacking third)"
    if x < -17.5:
        return "deep in their own third"
    return "in midfield"


PRESS_TYPE_LABEL = {
    "front_on": "front-on press (goal-side)",
    "positional": "positional — holds the lane, doesn't close",
    "chase_from_behind": "chasing from behind (not goal-side)",
    "not_a_press": "not a real press (never closed)",
}


def _press_type(goal_side: bool | None, ahead_m: float | None, closing_speed: float, d_min: float) -> str:
    """Setup: was the presser in a position to press, and how did he go about it?"""
    if closing_speed < NOT_A_PRESS_SPEED and d_min > NOT_A_PRESS_GAP_M:
        return "not_a_press"
    behind = goal_side is False or (goal_side is None and ahead_m is not None and ahead_m < -1.0)
    if behind:
        return "chase_from_behind"
    if closing_speed < POSITIONAL_SPEED and d_min <= NOT_A_PRESS_GAP_M:
        return "positional"
    return "front_on"


def _pressure_level(d_release: float | None, d_min: float, sprint_forced: bool) -> str:
    """Time taken away from the carrier, judged at the moment he releases the ball."""
    gap = d_release if d_release is not None else d_min
    if sprint_forced or gap <= HIGH_PRESSURE_M:
        return "high"
    if gap <= MEDIUM_PRESSURE_M:
        return "medium"
    return "low"


def _presser_verdict(
    press_type: str,
    pressure: str,
    outcome: str,
    eng_end: str,
    response_kind: str,
    d_release: float | None,
    d_min: float,
    closing_speed: float,
    ahead_m: float | None,
    teammates_near: int,
) -> tuple[str, str, str]:
    """Grade the presser on what he controlled (setup + pressure), not on the team result."""
    team = OUTCOMES[outcome]["grade"]
    rel = f"{d_release:.1f}m away at release" if d_release is not None else f"closest {d_min:.1f}m"
    if outcome == "foul_given":
        if eng_end == "foul_committed":
            return "GAVE AWAY THE FOUL", "bad", "Presser committed the foul himself."
        return "PRESS ENDED IN A FOUL", "bad", f"The press nearly won it, but a foul handed the ball straight back ({rel})."
    if outcome == "won_by_presser" and response_kind in ("pass_failed", "lost"):
        if press_type == "positional":
            return "CUT THE LANE — INTERCEPTED", "win", f"Didn't need to close: stood in the passing lane ({rel}) and the pass came to him."
        return "WON IT HIMSELF", "win", f"Pressure forced the error and he collected it ({rel})."
    if press_type == "not_a_press":
        return "NOT A REAL PRESS", "neutral", f"Closed at {closing_speed:.1f} m/s and stayed {d_min:.1f}m away — shouldn't count as a press."
    if press_type == "chase_from_behind":
        behind = f"started {abs(ahead_m):.1f}m behind the ball" if ahead_m is not None and ahead_m < 0 else "started on the wrong side"
        if team in ("win", "good"):
            return "CHASED BACK — IT WORKED", "good", f"He {behind}, but the chase plus {teammates_near} teammates nearby forced the outcome."
        return "OUT OF POSITION FROM THE START", "bad", f"He {behind}; chasing from behind can't cut the forward lanes."
    if pressure == "high":
        if team == "bad":
            return "STRONG PRESSURE — LANE LEFT OPEN", "neutral", f"Took his time away ({rel}) but the pass went into a lane he didn't cut off."
        return "STRONG PRESSURE", "good", f"Took his time away ({rel}) and forced the next action."
    if pressure == "medium":
        return "SOME PRESSURE", "neutral", f"Got reasonably close ({rel}) without really forcing the carrier."
    if team in ("win", "good"):
        return "TEAM PRESS — LITTLE PERSONAL PRESSURE", "neutral", f"Good team outcome, but he was {rel}; the run may have closed an option (Lane Tax will tell)."
    return "WENT THROUGH THE MOTIONS", "bad", f"Ran at it but was {rel}; nothing forced."
