"""Score one press: Lane Tax at the moment that matters, baselines, and validation labels.

Timing, in football terms:
- ``f_start``     the carrier has the ball and the presser has started coming
- ``f_release``   0.3 s before the ball leaves his foot: the moment he actually chooses.
                  The headline (unprefixed) tax is read here. A one-touch pass is read at f_start.
- ``f_decision``  1 s in (``d_`` columns), the Phase 1 convention
- peak            the most the presser took at any point in between (``peak_lane_tax``)
``run_gain`` = tax(release) - tax(start) says whether the run itself took options away or
whether he simply started in the right place (positional press).
"""

from __future__ import annotations

import pandas as pd

from lane_tax.baselines import compute_baselines
from lane_tax.config import PEAK_STEP_FRAMES, RELEASE_LOOKBACK_FRAMES
from lane_tax.labels import build_labels
from lane_tax.metric import Scene, TaxResult, build_scene, score_scene
from lane_tax.press_story import MatchContext, PressStory

DECISION_DELAY_FRAMES = 10


def press_rows(ctx: MatchContext, event_id: str) -> tuple[pd.Series, pd.Series]:
    eng = ctx.eng[ctx.eng["event_id"] == event_id].iloc[0]
    p0 = ctx.pp[ctx.pp["event_id"] == eng["associated_player_possession_event_id"]]
    if p0.empty:
        f = int(eng["frame_start"])
        p0 = ctx.pp[(ctx.pp["frame_start"] <= f) & (ctx.pp["frame_end"] >= f)]
    return eng, p0.iloc[0]


def chain_ids(ctx: MatchContext, eng: pd.Series) -> tuple[int, ...]:
    if not bool(eng.get("pressing_chain")) or pd.isna(eng.get("pressing_chain_index")):
        return ()
    ch = ctx.eng[(ctx.eng["pressing_chain_index"] == eng["pressing_chain_index"])
                 & (ctx.eng["team_id"] == eng["team_id"])]
    return tuple(int(p) for p in ch["player_id"].unique())


def key_frames(story: PressStory, p0: pd.Series) -> tuple[int, int, int]:
    f_start = max(story.frame0, int(p0["frame_start"]))
    release = int(p0["frame_end"])
    f_decision = max(f_start, min(f_start + DECISION_DELAY_FRAMES, release - 1))
    f_release = max(f_start, release - RELEASE_LOOKBACK_FRAMES)
    return f_start, f_decision, f_release


def scene_at(ctx: MatchContext, story: PressStory, frame: int, unit: tuple[int, ...]) -> Scene | None:
    return build_scene(
        ctx._pos, ctx.team_of, frame, story.carrier_id, story.presser_id, story.attack_sign,
        ctx.meta["pitch_length"] / 2, ctx.meta["pitch_width"] / 2, unit,
    )


def _tax_cols(prefix: str, r: TaxResult | None) -> dict:
    keys = ("escape", "escape_no_presser", "lane_tax", "lane_tax_block", "lane_tax_rush", "lane_tax_pct",
            "unit_tax", "ways_out", "ways_out_no_presser", "ways_tax", "credit_share", "squeeze_total",
            "top_squeezer_id", "lanes_cut", "retention", "trap_tax", "n_escape_open", "n_escape_open_no_presser",
            "n_options", "best_option", "best_option_no_presser", "presser_time_to_carrier_s", "detected_share")
    return {f"{prefix}{k}": (None if r is None else getattr(r, k)) for k in keys}


def _score(ctx: MatchContext, story: PressStory, frame: int, unit: tuple[int, ...]) -> TaxResult | None:
    sc = scene_at(ctx, story, frame, unit)
    return score_scene(sc) if sc else None


def score_press(
    ctx: MatchContext, story: PressStory, *, compute_peak: bool = True
) -> tuple[dict, dict[str, TaxResult | None]]:
    """Score one press. ``compute_peak=False`` skips the between-frames sweep (Phase 3 speed);
    headline tax at release is unchanged."""
    eng, p0 = press_rows(ctx, story.event_id)
    unit = chain_ids(ctx, eng)
    f_start, f_dec, f_rel = key_frames(story, p0)
    r_start, r_dec = _score(ctx, story, f_start, unit), _score(ctx, story, f_dec, unit)
    r_rel = _score(ctx, story, f_rel, unit)
    sc_rel = scene_at(ctx, story, f_rel, unit)
    if compute_peak:
        window = [r for f in range(f_start, f_rel + 1, PEAK_STEP_FRAMES) if (r := _score(ctx, story, f, unit))]
        if r_rel is not None:
            window.append(r_rel)
    else:
        window = [r for r in (r_start, r_rel) if r is not None]

    row = {
        "event_id": story.event_id, "match_id": ctx.match_id, "review_id": story.review_id,
        "frame0": story.frame0, "f_start": f_start, "f_decision": f_dec, "f_release": f_rel,
        "release_frame": story.release_frame, "time_on_ball_s": story.time_on_ball_s,
        "clock": story.clock, "subtype": story.subtype, "phase": story.phase_type,
        "presser": story.presser_name, "press_team": story.press_abbr, "carrier": story.carrier_name,
        "press_type": story.press_type, "pressure_level": story.pressure_level,
        "presser_verdict": story.credit, "presser_grade": story.presser_grade,
        "outcome": story.outcome, "grade": story.grade, "chain_size": story.chain_size,
        "presser_on_camera": next((ok for n, ok, _ in story.checks if n == "presser on camera"), None),
        "checks_ok": story.checks_ok,
    }
    row.update(_tax_cols("", r_rel))
    row.update(_tax_cols("start_", r_start))
    row.update(_tax_cols("d_", r_dec))
    row["peak_lane_tax"] = max((r.lane_tax for r in window), default=None)
    row["peak_unit_tax"] = max((r.unit_tax for r in window), default=None)
    row["mean_lane_tax"] = sum(r.lane_tax for r in window) / len(window) if window else None
    if r_rel and r_start:
        row["run_gain"] = r_rel.lane_tax - r_start.lane_tax
        row["escape_drop"] = r_start.escape - r_rel.escape
    else:
        row["run_gain"] = row["escape_drop"] = None

    if sc_rel is not None:
        row.update(compute_baselines(sc_rel, p0, story.closing_speed,
                                     r_rel.presser_time_to_carrier_s if r_rel else None).as_scores())
    row.update(build_labels(ctx, story, eng, p0, f_start).to_dict())
    return row, {"start": r_start, "decision": r_dec, "release": r_rel}
