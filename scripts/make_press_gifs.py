"""Delete old press GIFs and render full-story GIFs for the Phase 1 review sample."""

from __future__ import annotations

import argparse
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd

from lane_tax.config import DEFAULT_MATCH_ID, REVIEW_SAMPLE_SIZE
from lane_tax.data import load_tracking_frames
from lane_tax.explore import sample_review_presses
from lane_tax.press_gif import render_press_gif
from lane_tax.press_story import MatchContext, PressStory, build_story

REVIEW_DIR = ROOT / "docs" / "phase1_review"
GIF_DIR = REVIEW_DIR / "gifs"
REVIEW_LABEL = {"win": "cut_off", "good": "cut_off", "neutral": "motion_only", "bad": "motion_only"}
YOUR_REVIEW = REVIEW_DIR / "your_review.csv"


def review_label(s: PressStory) -> str:
    """Phase 2 target from the team outcome; presses that never were presses are left out."""
    return "excluded" if s.press_type == "not_a_press" else REVIEW_LABEL[s.grade]


def load_your_review() -> dict[str, dict[str, str]]:
    if not YOUR_REVIEW.exists():
        return {}
    df = pd.read_csv(YOUR_REVIEW)
    return {r.review_id: {"your_take": r.your_take, "agreement": r.agreement} for r in df.itertuples()}


def story_row(s: PressStory) -> dict:
    return {
        "review_id": s.review_id, "event_id": s.event_id, "frame_start": s.frame0, "clock": s.clock,
        "score": s.score_text, "phase": s.phase_type, "zone": s.zone, "subtype": s.subtype,
        "pressing_team": s.press_abbr, "presser": s.presser_name, "attacking_team": s.attack_abbr,
        "carrier": s.carrier_name, "gap_start_m": round(s.d_start, 2), "gap_min_m": round(s.d_min, 2),
        "gap_at_release_m": None if s.presser_dist_at_release is None else round(s.presser_dist_at_release, 2),
        "closing_speed_m_s": round(s.closing_speed, 2), "goal_side_start": s.goal_side_start,
        "chain_size": s.chain_size, "time_on_ball_s": s.time_on_ball_s, "response": s.response,
        "response_kind": s.response_kind, "outcome": s.outcome, "outcome_title": s.outcome_title,
        "grade": s.grade, "outcome_detail": s.outcome_detail,
        "seconds_to_outcome": round((s.resolution_frame - s.frame0) / 10, 1),
        "ball_gain_m": None if s.ball_progress_m is None else round(s.ball_progress_m, 1),
        "epv_start": s.epv_start, "epv_end": s.epv_end, "press_shot_after_regain": s.press_shot_after,
        "press_type": s.press_type, "pressure_level": s.pressure_level,
        "n_passing_options": s.n_options, "teammates_within_10m": s.teammates_near,
        "presser_verdict": s.credit, "presser_grade": s.presser_grade, "presser_detail": s.credit_detail,
        "review_label": review_label(s), "checks_ok": s.checks_ok,
        "check_warnings": "; ".join(f"{n}: {d}" for n, ok, d in s.checks if not ok),
    }


def write_docs(stories: list[PressStory]) -> None:
    yours = load_your_review()
    rows = []
    for s in stories:
        row = story_row(s)
        row.update(yours.get(s.review_id, {"your_take": "", "agreement": ""}))
        rows.append(row)
    pd.DataFrame(rows).to_csv(REVIEW_DIR / "review_sample.csv", index=False)

    lines = [
        "# Phase 1 press labels (three layers)",
        "",
        "Each press is graded on three separate questions:",
        "",
        "1. **Setup** — was the presser in a position to press? (front-on, positional, chasing from behind, not a real press)",
        "2. **Presser verdict** — what he controlled: time taken away (gap at release, closing speed).",
        "   Options taken away is the Lane Tax itself (Phase 2).",
        "3. **Team outcome** — what the team got within ~8s. Used to *validate* the metric, not to grade the presser.",
        "",
        "`review_label` (Phase 2 target) comes from the team outcome; `not_a_press` rows are `excluded`.",
        "",
        "| ID | Setup | Presser verdict | Team outcome | Your take | Agree? |",
        "|---|---|---|---|---|---|",
    ]
    for s in stories:
        y = yours.get(s.review_id, {})
        lines.append(
            f"| {s.review_id} | {s.press_type.replace('_', ' ')} | {s.credit} | {s.outcome_title} | "
            f"{y.get('your_take', '')} | {y.get('agreement', '')} |"
        )
    (REVIEW_DIR / "LABELS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    out = ["# Press stories (sports-director view)", ""]
    for s in stories:
        y = yours.get(s.review_id, {})
        out += [f"## {s.review_id} — presser: {s.credit} · team: {s.outcome_title}", "",
                f"**{s.presser_name} ({s.press_abbr}) on {s.carrier_name} ({s.attack_abbr})** — "
                f"{s.credit_detail}", ""]
        if y:
            out += [f"_Your take ({y['agreement']}):_ {y['your_take']}", ""]
        for i, (title, _, txt) in enumerate(s.beats(), 1):
            out.append(f"{i}. **{title}** — {txt}")
        warn = [f"{n} ({d})" for n, ok, d in s.checks if not ok]
        out += ["", f"_Data checks:_ {'all passed' if not warn else 'warning — ' + '; '.join(warn)}",
                f"![{s.review_id}](gifs/{s.review_id}.gif)", ""]
    (REVIEW_DIR / "STORIES.md").write_text("\n".join(out), encoding="utf-8")

    (GIF_DIR / "README.md").write_text(
        "\n".join([
            "# Press GIFs",
            "",
            "- **Blue** = team on the ball when the press starts; **red** = pressing team.",
            "- Big blue dot = carrier, red diamond = presser (white fill = presser off camera, position estimated).",
            "- Yellow ring = whoever has the ball right now (from SkillCorner possession events).",
            "- Banner = presser verdict (what he controlled); second line = setup and team outcome.",
            "- Right panel lights up the four beats: context -> press (incl. setup) -> forced response -> team outcome.",
            "- Bottom bar = who had the ball second by second; grey = ball travelling, loose or dead.",
            "- Charts: presser gap to carrier, and how many metres the attack gained (above 0 = bad for the press).",
            "- Footer = data checks that the press, teams, direction and tracking line up.",
            "",
        ]),
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--match-id", type=int, default=DEFAULT_MATCH_ID)
    parser.add_argument("--n", type=int, default=REVIEW_SAMPLE_SIZE)
    parser.add_argument("--only", nargs="*", default=None)
    args = parser.parse_args()

    sample = sample_review_presses(match_id=args.match_id, n=args.n)
    players, frame_meta = load_tracking_frames(args.match_id, use_cache=True)
    ctx = MatchContext(args.match_id, players, frame_meta)
    stories = [build_story(ctx, r.event_id, r.review_id) for r in sample.itertuples()]

    todo = [s for s in stories if s.review_id in args.only] if args.only else stories
    staging = GIF_DIR.with_name("gifs_rendering")
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)

    print(f"rendering {len(todo)} GIFs -> {staging} (swapped into {GIF_DIR} when all finish)")
    for s in todo:
        t0 = time.time()
        path = render_press_gif(ctx, s, staging / f"{s.review_id}.gif")
        print(f"  {s.review_id}: {s.outcome_title} | {s.credit} ({time.time() - t0:.0f}s, "
              f"{path.stat().st_size / 1e6:.1f} MB)")

    GIF_DIR.mkdir(parents=True, exist_ok=True)
    if not args.only:
        for old in GIF_DIR.glob("*.gif"):
            old.unlink()
    for new in staging.glob("*.gif"):
        shutil.move(str(new), GIF_DIR / new.name)
    shutil.rmtree(staging)
    write_docs(stories)
    print("done")


if __name__ == "__main__":
    main()
