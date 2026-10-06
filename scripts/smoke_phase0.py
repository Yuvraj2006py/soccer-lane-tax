"""Smoke test for Phase 0: load one match and join presses to tracking."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lane_tax.data import (
    DEFAULT_MATCH_ID,
    join_press_to_tracking,
    join_summary,
    load_match_meta,
    load_press_events,
    load_tracking_frames,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--match-id", type=int, default=DEFAULT_MATCH_ID)
    parser.add_argument("--rebuild-cache", action="store_true")
    args = parser.parse_args()

    meta = load_match_meta(args.match_id)
    home = meta["home_team"]["short_name"]
    away = meta["away_team"]["short_name"]
    print(f"match {args.match_id}: {home} vs {away}")
    print(f"pitch {meta['pitch_length']}x{meta['pitch_width']} m")

    press = load_press_events(args.match_id)
    print(f"press events: {len(press)}")
    print(press["event_subtype"].value_counts().to_string())

    t0 = time.perf_counter()
    players, frame_meta = load_tracking_frames(
        args.match_id,
        use_cache=True,
        rebuild_cache=args.rebuild_cache,
    )
    elapsed = time.perf_counter() - t0
    print(
        f"tracking: {len(frame_meta)} frames, "
        f"{len(players)} player-rows ({elapsed:.1f}s)"
    )

    joined = join_press_to_tracking(press, frame_meta)
    summary = join_summary(joined)
    print("join summary:", summary)

    if summary["hit_rate"] < 1.0:
        raise SystemExit("FAIL: some press frame_start values missing in tracking")
    if summary["populated_rate"] < 0.95:
        raise SystemExit("FAIL: too many press frames have zero players")

    sample = joined.loc[
        joined["tracking_n_players"] > 0,
        [
            "event_id",
            "event_subtype",
            "frame_start",
            "player_id",
            "player_in_possession_id",
            "tracking_n_players",
            "tracking_ball_x",
            "tracking_ball_y",
        ],
    ].head(5)
    print("sample joined rows:")
    print(sample.to_string(index=False))
    print("Phase 0 smoke test OK")


if __name__ == "__main__":
    main()
