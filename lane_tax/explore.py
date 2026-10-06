"""Phase 1 exploration: sample presses, frame snapshots, provisional labels."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from lane_tax.config import (
    DEFAULT_MATCH_ID,
    FOCUS_ATTACK_PHASES,
    OUTCOME_WINDOW_FRAMES,
    POSSESSION_LOSS_END_TYPES,
    PROGRESSIVE_ADVANCE_M,
    REVIEW_SAMPLE_SIZE,
    REVIEW_SEED,
    TAX_WINDOW_FRAMES,
)
from lane_tax.data import (
    load_dynamic_events,
    load_match_meta,
    load_phases_of_play,
    load_press_events,
    load_tracking_frames,
)


ATTACK_SIGN = {
    "left_to_right": 1.0,
    "right_to_left": -1.0,
}


@dataclass(frozen=True)
class FrameSnapshot:
    frame: int
    carrier_id: int | None
    carrier_x: float | None
    carrier_y: float | None
    presser_id: int | None
    presser_x: float | None
    presser_y: float | None
    ball_x: float | None
    ball_y: float | None
    nearest_def_dist: float | None
    defenders_within_5m: int | None
    n_players: int


def focus_press_events(match_id: int = DEFAULT_MATCH_ID) -> pd.DataFrame:
    press = load_press_events(match_id)
    focus = press[
        press["team_in_possession_phase_type"].isin(FOCUS_ATTACK_PHASES)
    ].copy()
    return focus.reset_index(drop=True)


def _player_xy(
    players: pd.DataFrame, frame: int, player_id: int | float | None
) -> tuple[float | None, float | None]:
    if player_id is None or (isinstance(player_id, float) and np.isnan(player_id)):
        return None, None
    pid = int(player_id)
    rows = players[(players["frame"] == frame) & (players["player_id"] == pid)]
    if rows.empty:
        return None, None
    row = rows.iloc[0]
    if pd.isna(row["x"]) or pd.isna(row["y"]):
        return None, None
    return float(row["x"]), float(row["y"])


def _frame_meta_row(frame_meta: pd.DataFrame, frame: int) -> pd.Series | None:
    rows = frame_meta[frame_meta["frame"] == frame]
    if rows.empty:
        return None
    return rows.iloc[0]


def _defender_distances(
    players: pd.DataFrame,
    frame: int,
    carrier_id: int,
    carrier_x: float,
    carrier_y: float,
    possession_group: str | None,
) -> tuple[float | None, int]:
    """Distances from carrier to players not on the possession group."""
    frame_players = players[players["frame"] == frame].copy()
    if frame_players.empty:
        return None, 0

    # Infer defending players as everyone except carrier's teammates when group known.
    # SkillCorner possession.group is usually 'home team' / 'away team'.
    # Without roster side on each player row, approximate defenders as all other players
    # except the carrier; Phase 2 will refine with match.json sides.
    others = frame_players[frame_players["player_id"] != carrier_id]
    if others.empty:
        return None, 0
    dists = np.hypot(others["x"].to_numpy() - carrier_x, others["y"].to_numpy() - carrier_y)
    dists = dists[np.isfinite(dists)]
    if len(dists) == 0:
        return None, 0
    # Crude: take the closest half of other players as "opponents" proxy by distance
    # is wrong. Better: use presser + players closer than median of all others as
    # candidate defenders for baseline only.
    nearest = float(np.min(dists))
    within_5 = int(np.sum(dists <= 5.0))
    _ = possession_group  # reserved for Phase 2 roster-aware sides
    return nearest, within_5


def snapshot_at(
    players: pd.DataFrame,
    frame_meta: pd.DataFrame,
    frame: int,
    carrier_id: int | float | None,
    presser_id: int | float | None,
) -> FrameSnapshot:
    meta = _frame_meta_row(frame_meta, frame)
    cx, cy = _player_xy(players, frame, carrier_id)
    px, py = _player_xy(players, frame, presser_id)
    ball_x = ball_y = None
    n_players = 0
    possession_group = None
    if meta is not None:
        ball_x = meta["ball_x"] if pd.notna(meta["ball_x"]) else None
        ball_y = meta["ball_y"] if pd.notna(meta["ball_y"]) else None
        n_players = int(meta["n_players"]) if pd.notna(meta["n_players"]) else 0
        possession_group = meta["possession_group"]

    nearest = within5 = None
    if cx is not None and cy is not None and carrier_id is not None and pd.notna(carrier_id):
        nearest, within5 = _defender_distances(
            players, frame, int(carrier_id), cx, cy, possession_group
        )

    return FrameSnapshot(
        frame=frame,
        carrier_id=int(carrier_id) if carrier_id is not None and pd.notna(carrier_id) else None,
        carrier_x=cx,
        carrier_y=cy,
        presser_id=int(presser_id) if presser_id is not None and pd.notna(presser_id) else None,
        presser_x=px,
        presser_y=py,
        ball_x=float(ball_x) if ball_x is not None else None,
        ball_y=float(ball_y) if ball_y is not None else None,
        nearest_def_dist=nearest,
        defenders_within_5m=within5,
        n_players=n_players,
    )


def attacking_sign_for_frame(phases: pd.DataFrame, frame: int) -> float:
    hit = phases[(phases["frame_start"] <= frame) & (phases["frame_end"] >= frame)]
    if hit.empty:
        return 1.0
    side = hit.iloc[0]["attacking_side"]
    return ATTACK_SIGN.get(side, 1.0)


def outcome_label_for_press(
    players: pd.DataFrame,
    frame_meta: pd.DataFrame,
    phases: pd.DataFrame,
    press_row: pd.Series,
) -> dict[str, Any]:
    """Locked outcome definition for Phase 2+.

    progressive=1 if within OUTCOME_WINDOW the carrier/ball advances
    >= PROGRESSIVE_ADVANCE_M in the attacking direction and possession
    was not lost on the associated possession end type.
    Otherwise progressive=0 (forced/safe/non-progressive or loss).
    """
    frame0 = int(press_row["frame_start"])
    frame1 = frame0 + OUTCOME_WINDOW_FRAMES
    carrier_id = press_row.get("player_in_possession_id")
    presser_id = press_row.get("player_id")

    snap0 = snapshot_at(players, frame_meta, frame0, carrier_id, presser_id)
    snap1 = snapshot_at(players, frame_meta, frame1, carrier_id, presser_id)
    sign = attacking_sign_for_frame(phases, frame0)

    end_type = press_row.get("associated_player_possession_end_type")
    possession_lost = (
        isinstance(end_type, str) and end_type in POSSESSION_LOSS_END_TYPES
    )

    x0 = snap0.carrier_x if snap0.carrier_x is not None else snap0.ball_x
    x1 = snap1.carrier_x if snap1.carrier_x is not None else snap1.ball_x
    advance = None
    if x0 is not None and x1 is not None:
        advance = float((x1 - x0) * sign)

    progressive = False
    if not possession_lost and advance is not None and advance >= PROGRESSIVE_ADVANCE_M:
        progressive = True

    return {
        "outcome_progressive": int(progressive),
        "outcome_possession_lost": int(possession_lost),
        "outcome_advance_m": advance,
        "outcome_end_type": end_type,
        "attacking_sign": sign,
        "snap0_nearest_def": snap0.nearest_def_dist,
        "snap0_defs_within_5": snap0.defenders_within_5m,
        "snap1_nearest_def": snap1.nearest_def_dist,
        "carrier_x0": snap0.carrier_x,
        "carrier_y0": snap0.carrier_y,
        "carrier_x1": snap1.carrier_x,
        "carrier_y1": snap1.carrier_y,
        "presser_x0": snap0.presser_x,
        "presser_y0": snap0.presser_y,
        "ball_x0": snap0.ball_x,
        "ball_y0": snap0.ball_y,
        "tax_frame": frame0 + TAX_WINDOW_FRAMES,
    }


def provisional_cut_off_label(row: pd.Series) -> str:
    """Heuristic label for human review only — not the metric.

    cut_off: presser closes distance and outcome is non-progressive
    motion_only: presser close or closing but play still progresses
    unclear: missing geometry / mixed signals
    """
    d0 = row.get("interplayer_distance_start")
    d1 = row.get("interplayer_distance_end")
    progressive = row.get("outcome_progressive")
    if pd.isna(d0) or pd.isna(d1) or progressive is None or pd.isna(progressive):
        return "unclear"
    closing = float(d0) - float(d1) >= 1.0
    close_enough = float(d1) <= 7.0
    if (closing or close_enough) and int(progressive) == 0:
        return "cut_off"
    if (closing or close_enough) and int(progressive) == 1:
        return "motion_only"
    if int(progressive) == 0:
        return "cut_off"
    return "motion_only"


def sample_review_presses(
    match_id: int = DEFAULT_MATCH_ID,
    n: int = REVIEW_SAMPLE_SIZE,
    seed: int = REVIEW_SEED,
) -> pd.DataFrame:
    """Stratified sample across subtypes within focus phases."""
    focus = focus_press_events(match_id)
    players, frame_meta = load_tracking_frames(match_id, use_cache=True)
    phases = load_phases_of_play(match_id)
    events = load_dynamic_events(match_id)
    drop_empty = [
        "passing_option_ease_start",
        "passing_option_ease_end",
        "n_passing_options_ahead_at_start",
        "n_passing_options_ahead_at_end",
        "overall_pressure_start",
        "overall_pressure_end",
    ]
    focus = focus.drop(columns=[c for c in drop_empty if c in focus.columns])

    poss = events[events["event_type"] == "player_possession"][
        [
            "event_id",
            "passing_option_ease_start",
            "passing_option_ease_end",
            "n_passing_options_ahead_at_start",
            "n_passing_options_ahead_at_end",
            "overall_pressure_start",
            "overall_pressure_end",
        ]
    ].rename(columns={"event_id": "possession_event_id"})

    focus = focus.merge(
        poss,
        how="left",
        left_on="associated_player_possession_event_id",
        right_on="possession_event_id",
    )

    # Stratify by subtype
    parts: list[pd.DataFrame] = []
    subtypes = list(focus["event_subtype"].value_counts().index)
    rng = np.random.default_rng(seed)
    remaining = n
    for i, subtype in enumerate(subtypes):
        pool = focus[focus["event_subtype"] == subtype]
        take = max(1, n // len(subtypes))
        if i == len(subtypes) - 1:
            take = remaining
        take = min(take, len(pool), remaining)
        if take <= 0:
            continue
        idx = rng.choice(pool.index.to_numpy(), size=take, replace=False)
        parts.append(pool.loc[idx])
        remaining -= take
    sample = pd.concat(parts).sample(frac=1.0, random_state=seed).reset_index(drop=True)

    outcome_rows = []
    for _, row in sample.iterrows():
        outcome_rows.append(outcome_label_for_press(players, frame_meta, phases, row))
    outcomes = pd.DataFrame(outcome_rows)
    out = pd.concat([sample.reset_index(drop=True), outcomes], axis=1)
    out["provisional_label"] = out.apply(provisional_cut_off_label, axis=1)
    out["review_id"] = [f"R{i+1:02d}" for i in range(len(out))]
    out["match_id"] = match_id
    return out


def review_columns(df: pd.DataFrame) -> pd.DataFrame:
    cols = [
        "review_id",
        "match_id",
        "event_id",
        "event_subtype",
        "team_in_possession_phase_type",
        "frame_start",
        "frame_end",
        "player_id",
        "player_in_possession_id",
        "player_in_possession_name",
        "interplayer_distance_start",
        "interplayer_distance_end",
        "interplayer_distance_min",
        "passing_option_ease_start",
        "passing_option_ease_end",
        "n_passing_options_ahead_at_start",
        "n_passing_options_ahead_at_end",
        "associated_player_possession_end_type",
        "outcome_progressive",
        "outcome_advance_m",
        "outcome_possession_lost",
        "snap0_nearest_def",
        "snap0_defs_within_5",
        "provisional_label",
        "carrier_x0",
        "carrier_y0",
        "presser_x0",
        "presser_y0",
        "ball_x0",
        "ball_y0",
        "carrier_x1",
        "carrier_y1",
    ]
    return df[[c for c in cols if c in df.columns]].copy()
