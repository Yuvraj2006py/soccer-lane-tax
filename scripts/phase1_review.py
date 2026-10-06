"""Phase 1: generate easy story cards + labels."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lane_tax.config import DEFAULT_MATCH_ID, REVIEW_SAMPLE_SIZE
from lane_tax.data import load_match_meta, load_phases_of_play, load_tracking_frames
from lane_tax.explore import review_columns, sample_review_presses
from lane_tax.review_viz import roster_team_map
from lane_tax.story_card import plot_story_card


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--match-id", type=int, default=DEFAULT_MATCH_ID)
    parser.add_argument("--n", type=int, default=REVIEW_SAMPLE_SIZE)
    args = parser.parse_args()

    out_dir = ROOT / "docs" / "phase1_review"
    fig_dir = out_dir / "figures_easy"
    fig_dir.mkdir(parents=True, exist_ok=True)

    meta = load_match_meta(args.match_id)
    sample = sample_review_presses(match_id=args.match_id, n=args.n)
    players, frame_meta = load_tracking_frames(args.match_id, use_cache=True)
    phases = load_phases_of_play(args.match_id)
    team_of = roster_team_map(args.match_id)

    labels = []
    notes = []
    for _, row in sample.iterrows():
        label, note = plot_story_card(
            row,
            players,
            frame_meta,
            phases,
            team_of,
            meta,
            fig_dir / f"{row['review_id']}.png",
        )
        labels.append(label)
        notes.append(note)

    table = review_columns(sample)
    table["agent_label"] = labels
    table["agent_notes"] = notes
    table["your_label"] = labels
    table["your_notes"] = notes
    csv_path = out_dir / "review_sample.csv"
    table.to_csv(csv_path, index=False)

    summary_path = out_dir / "LABELS.md"
    lines = [
        "# Phase 1 press labels",
        "",
        "Use the easy story cards in `figures_easy/` (big verdict + before/after).",
        "",
        "| ID | Label | Why |",
        "|---|---|---|",
    ]
    for _, row in table.iterrows():
        lines.append(
            f"| {row['review_id']} | **{row['your_label']}** | {row['your_notes']} |"
        )
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"wrote {csv_path}")
    print(f"wrote {summary_path}")
    print(f"wrote {len(sample)} easy cards to {fig_dir}")
    print(table["your_label"].value_counts().to_string())
    print("\nOpen figures_easy/R04.png or R08.png — look at the colored banner first.")


if __name__ == "__main__":
    main()
