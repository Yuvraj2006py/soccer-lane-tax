"""Outcome labels used to validate the Lane Tax.

Several independent views of "did the press work", so no single labelling choice decides the result:

- ``y_press_success``  team outcome from the story engine (win/good within ~8 s)
- ``y_escaped``        attack got out: controlled ball progress >= ESCAPE_PROGRESS_M or a completed
                       switch within ESCAPE_WINDOW_S, before the press team touched it
- ``y_sc_effect``      SkillCorner's own flags: force_backward / reduce / stop possession danger
- ``y_beaten``         SkillCorner: presser beaten by the possession or by movement
- ``y_forced_error``   carrier's response was a failed pass, a loss, or a clearance
- ``y_regain``         press team regained within REGAIN_WINDOW_S
- ``chosen_xpass``     SkillCorner xPass of the pass the carrier actually played (lower = forced into
                       a harder pass); ``chosen_xthreat`` its threat
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

import pandas as pd

from lane_tax.press_story import MatchContext, PressStory

ESCAPE_WINDOW_S = 4.0
ESCAPE_PROGRESS_M = 8.0
ESCAPE_SWITCH_M = 25.0
REGAIN_WINDOW_S = 5.0
SUCCESS_GRADES = {"win", "good"}
FORCED_ERROR_KINDS = {"pass_failed", "lost", "clearance"}


@dataclass
class Labels:
    excluded: bool
    y_press_success: int
    y_presser_good: int
    y_escaped: int | None
    escape_progress_m: float | None
    escape_how: str
    y_sc_effect: int
    y_beaten: int
    y_forced_error: int
    y_regain: int
    chosen_xpass: float | None
    chosen_xthreat: float | None

    def to_dict(self) -> dict:
        return asdict(self)


def _bool(v) -> bool:
    return bool(v) if v is not None and not pd.isna(v) else False


def _num(v) -> float | None:
    return None if v is None or pd.isna(v) else float(v)


def escape_label(ctx: MatchContext, s: PressStory, f_start: int) -> tuple[int | None, float | None, str]:
    """Did the attack get out under control? Progress is measured on *controlled* ball positions only
    (where an attacker starts a possession, or where the carrier finishes his), so a pass still in the air
    or a hopeful punt that the press wins never counts as an escape."""
    ref = ctx.xy(f_start, s.carrier_id)
    if ref is None:
        return None, None, "no carrier position"
    end = f_start + int(ESCAPE_WINDOW_S * 10)
    pp = ctx.pp[(ctx.pp["frame_end"] >= f_start) & (ctx.pp["frame_start"] <= end)].sort_values("frame_start")
    best, how = 0.0, "held"
    for p in pp.itertuples():
        if int(p.team_id) != s.attack_team_id:
            return 0, best, "press team touched it first"
        pid = int(p.player_id)
        frames = [max(int(p.frame_start), f_start)]
        if int(p.frame_end) <= end:
            frames.append(int(p.frame_end))
        for f in frames:
            xy = ctx.xy(f, pid)
            if xy is None:
                continue
            gain = (xy[0] - ref[0]) * s.attack_sign
            if gain > best:
                best = gain
            if gain >= ESCAPE_PROGRESS_M:
                return 1, gain, f"{gain:.0f}m controlled progress"
            if abs(xy[1] - ref[1]) >= ESCAPE_SWITCH_M and gain > -5.0:
                return 1, gain, "switched play"
    return 0, best, how


def build_labels(ctx: MatchContext, s: PressStory, eng: pd.Series, p0: pd.Series, f_start: int) -> Labels:
    escaped, prog, how = escape_label(ctx, s, f_start)
    regain = s.regain_frame is not None and s.regain_frame - f_start <= REGAIN_WINDOW_S * 10
    return Labels(
        excluded=s.press_type == "not_a_press",
        y_press_success=int(s.grade in SUCCESS_GRADES),
        y_presser_good=int(s.presser_grade in SUCCESS_GRADES),
        y_escaped=escaped,
        escape_progress_m=None if prog is None else round(float(prog), 1),
        escape_how=how,
        y_sc_effect=int(any(_bool(eng.get(k)) for k in ("force_backward", "reduce_possession_danger",
                                                          "stop_possession_danger"))),
        y_beaten=int(_bool(eng.get("beaten_by_possession")) or _bool(eng.get("beaten_by_movement"))),
        y_forced_error=int(s.response_kind in FORCED_ERROR_KINDS),
        y_regain=int(bool(regain)),
        chosen_xpass=_num(p0.get("player_targeted_xpass_completion")),
        chosen_xthreat=_num(p0.get("player_targeted_xthreat")),
    )
