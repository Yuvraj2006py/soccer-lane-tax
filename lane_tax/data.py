"""Load SkillCorner open-data matches and join press events to tracking frames."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

PRESS_SUBTYPES = ("pressure", "pressing", "recovery_press", "counter_press")
DEFAULT_MATCH_ID = 2017461
TRACKING_HZ = 10

# Project root: Lane Tax Metric/
ROOT = Path(__file__).resolve().parents[1]
OPENDATA_DIR = ROOT / "opendata"
DATA_DIR = OPENDATA_DIR / "data"
CACHE_DIR = ROOT / ".cache" / "tracking"


def list_match_ids() -> list[int]:
    """Return match ids that have a data folder under opendata/data/matches."""
    matches_dir = DATA_DIR / "matches"
    if not matches_dir.exists():
        return []
    return sorted(
        int(p.name)
        for p in matches_dir.iterdir()
        if p.is_dir() and p.name.isdigit()
    )


def match_dir(match_id: int) -> Path:
    path = DATA_DIR / "matches" / str(match_id)
    if not path.is_dir():
        raise FileNotFoundError(f"Match folder not found: {path}")
    return path


def load_match_meta(match_id: int) -> dict[str, Any]:
    path = match_dir(match_id) / f"{match_id}_match.json"
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def load_dynamic_events(match_id: int) -> pd.DataFrame:
    path = match_dir(match_id) / f"{match_id}_dynamic_events.csv"
    return pd.read_csv(path, low_memory=False)


def load_phases_of_play(match_id: int) -> pd.DataFrame:
    path = match_dir(match_id) / f"{match_id}_phases_of_play.csv"
    return pd.read_csv(path, low_memory=False)


def load_press_events(
    match_id: int,
    subtypes: tuple[str, ...] = PRESS_SUBTYPES,
) -> pd.DataFrame:
    """Return press-like dynamic events with integer frame bounds."""
    events = load_dynamic_events(match_id)
    if "event_subtype" not in events.columns:
        raise KeyError("dynamic events missing event_subtype column")

    press = events[events["event_subtype"].isin(subtypes)].copy()
    press["match_id"] = match_id
    press["frame_start"] = press["frame_start"].astype(int)
    press["frame_end"] = press["frame_end"].astype(int)
    return press.reset_index(drop=True)


def _tracking_jsonl_path(match_id: int) -> Path:
    return match_dir(match_id) / f"{match_id}_tracking_extrapolated.jsonl"


def _cache_paths(match_id: int) -> tuple[Path, Path]:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return (
        CACHE_DIR / f"{match_id}_players.parquet",
        CACHE_DIR / f"{match_id}_frame_meta.parquet",
    )


def _parse_tracking_jsonl(path: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    player_rows: list[dict[str, Any]] = []
    meta_rows: list[dict[str, Any]] = []

    with path.open(encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            frame = json.loads(line)
            frame_id = int(frame["frame"])
            ball = frame.get("ball_data") or {}
            possession = frame.get("possession") or {}
            players = frame.get("player_data") or []

            meta_rows.append(
                {
                    "frame": frame_id,
                    "timestamp": frame.get("timestamp"),
                    "period": frame.get("period"),
                    "ball_x": ball.get("x"),
                    "ball_y": ball.get("y"),
                    "ball_z": ball.get("z"),
                    "ball_is_detected": ball.get("is_detected"),
                    "possession_player_id": possession.get("player_id"),
                    "possession_group": possession.get("group"),
                    "n_players": len(players),
                }
            )

            for player in players:
                player_rows.append(
                    {
                        "frame": frame_id,
                        "player_id": player.get("player_id"),
                        "x": player.get("x"),
                        "y": player.get("y"),
                        "is_detected": player.get("is_detected"),
                    }
                )

    players_df = pd.DataFrame(player_rows)
    meta_df = pd.DataFrame(meta_rows)
    return players_df, meta_df


def load_tracking_frames(
    match_id: int,
    *,
    use_cache: bool = True,
    rebuild_cache: bool = False,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load tracking as (players_long, frame_meta).

    players_long columns: frame, player_id, x, y, is_detected
    frame_meta columns: frame, timestamp, period, ball_*, possession_*, n_players
    """
    players_path, meta_path = _cache_paths(match_id)
    if use_cache and not rebuild_cache and players_path.exists() and meta_path.exists():
        return pd.read_parquet(players_path), pd.read_parquet(meta_path)

    players_df, meta_df = _parse_tracking_jsonl(_tracking_jsonl_path(match_id))
    if use_cache:
        players_df.to_parquet(players_path, index=False)
        meta_df.to_parquet(meta_path, index=False)
    return players_df, meta_df


def join_press_to_tracking(
    press_events: pd.DataFrame,
    frame_meta: pd.DataFrame,
    *,
    frame_col: str = "frame_start",
) -> pd.DataFrame:
    """Left-join press events to tracking frame metadata on frame_col.

    Adds join diagnostics:
    - tracking_hit: True if frame exists in tracking
    - tracking_n_players: players present on that frame
    """
    if frame_col not in press_events.columns:
        raise KeyError(f"press events missing {frame_col}")

    meta = frame_meta.rename(
        columns={
            "n_players": "tracking_n_players",
            "ball_x": "tracking_ball_x",
            "ball_y": "tracking_ball_y",
            "possession_player_id": "tracking_possession_player_id",
            "possession_group": "tracking_possession_group",
        }
    )
    keep = [
        "frame",
        "tracking_n_players",
        "tracking_ball_x",
        "tracking_ball_y",
        "tracking_possession_player_id",
        "tracking_possession_group",
        "period",
        "timestamp",
    ]
    meta = meta[[c for c in keep if c in meta.columns]].copy()

    joined = press_events.merge(
        meta,
        how="left",
        left_on=frame_col,
        right_on="frame",
        suffixes=("", "_tracking"),
    )
    joined["tracking_hit"] = joined["tracking_n_players"].notna()
    return joined


def join_summary(joined: pd.DataFrame) -> dict[str, Any]:
    """Summarize press→tracking join quality for smoke tests / logs."""
    n = len(joined)
    hits = int(joined["tracking_hit"].sum()) if n else 0
    populated = (
        int((joined["tracking_n_players"].fillna(0) > 0).sum()) if n else 0
    )
    return {
        "n_press_events": n,
        "n_tracking_hits": hits,
        "hit_rate": (hits / n) if n else 0.0,
        "n_populated_frames": populated,
        "populated_rate": (populated / n) if n else 0.0,
        "missing_frames": (
            joined.loc[~joined["tracking_hit"], "frame_start"].astype(int).tolist()
            if n
            else []
        ),
    }
