"""Phase 3: score every focus press in all 20 matches; leave-one-match-out vs baselines.

Constants are frozen from Phase 2. Headline scores:
  - team:   neg_ways_out (fewer ways out = higher pressure)
  - credit: lane_tax (does not need to predict team outcomes)

Outputs under docs/phase3/:
  events/match_<id>.csv   per-match cache (resume-safe)
  all_events.csv          pooled presses
  auc_pooled.csv          all presses together
  auc_lomo.csv            mean AUC across held-out matches
  lomo_per_match.csv      per-match AUCs for the key scores
  logistic_lomo.csv       does ways_out add to SkillCorner options-ahead?
  disagreements.csv       looks-like-a-press / quiet-press examples
  summary.md              plain-language verdict
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd

from lane_tax.data import list_match_ids, load_tracking_frames
from lane_tax.explore import focus_press_events
from lane_tax.press_story import MatchContext, build_story
from lane_tax.press_tax import score_press
from lane_tax.validate import (
    auc,
    auc_ci,
    leave_one_match_out,
    lomo_logistic_auc,
    lomo_mean_auc,
    paired_auc_gain,
)

# Full 1000-draw bootstrap on ~7.5k presses is too slow; Phase 3 uses a lighter draw.
PHASE3_BOOT = 200


def auc_table_fast(df: pd.DataFrame, scores: list[str], labels: list[str]) -> pd.DataFrame:
    rows = []
    for lab in labels:
        sub = df[df[lab].notna()]
        n1 = int(sub[lab].sum())
        for sc in scores:
            point, lo, hi = auc_ci(sub[sc], sub[lab], n=PHASE3_BOOT)
            rows.append({"label": lab, "score": sc, "n": len(sub), "positives": n1,
                         "auc": point, "ci_lo": lo, "ci_hi": hi})
    return pd.DataFrame(rows)

OUT = ROOT / "docs" / "phase3"
EVENTS = OUT / "events"

SCORES = [
    "neg_ways_out", "neg_escape", "lane_tax", "ways_tax", "squeeze_total", "unit_tax",
    "b_presser_gap", "b_nearest_opponent", "b_opponents_within_5m", "b_closing_speed",
    "b_presser_time", "b_sc_pressure", "b_sc_option_ease", "b_sc_fewer_options",
    "b_sc_fewer_options_ahead",
]
LABELS = ["y_contained", "y_forced_error", "y_press_success", "y_regain"]
SCORE_TEXT = {
    "neg_ways_out": "Ways out left (fewer = higher)",
    "neg_escape": "Best way out left (fewer = higher)",
    "lane_tax": "Lane Tax (presser credit)",
    "ways_tax": "Ways-out tax (presser)",
    "squeeze_total": "Total squeeze near ball",
    "unit_tax": "Pressing-chain tax",
    "b_presser_gap": "Presser gap",
    "b_nearest_opponent": "Nearest opponent",
    "b_opponents_within_5m": "Opponents within 5 m",
    "b_closing_speed": "Closing speed",
    "b_presser_time": "Presser time-to-carrier",
    "b_sc_pressure": "SkillCorner pressure",
    "b_sc_option_ease": "SkillCorner option ease",
    "b_sc_fewer_options": "SkillCorner fewer options",
    "b_sc_fewer_options_ahead": "SkillCorner fewer options ahead",
    "rank_ways": "Ways out alone (rank)",
    "rank_sc": "SC options-ahead alone (rank)",
    "logistic_both": "Logistic: ways out + SC options-ahead",
}
LABEL_TEXT = {
    "y_contained": "attack did NOT escape under control within 4 s",
    "y_forced_error": "carrier's response was a failed pass / loss / clearance",
    "y_press_success": "team outcome good (~8 s story)",
    "y_regain": "press team won it back within 5 s",
}


def _score_match(match_id: int) -> pd.DataFrame:
    path = EVENTS / f"match_{match_id}.csv"
    if path.exists():
        print(f"  cache hit {path.name}")
        return pd.read_csv(path)

    focus = focus_press_events(match_id)
    print(f"  loading tracking ({len(focus)} focus presses)…")
    players, frame_meta = load_tracking_frames(match_id, use_cache=True)
    ctx = MatchContext(match_id, players, frame_meta)
    rows, errors = [], []
    t0 = time.time()
    for i, ev in enumerate(focus["event_id"]):
        try:
            story = build_story(ctx, ev, "")
            row, _ = score_press(ctx, story, compute_peak=False)
            rows.append(row)
        except Exception as exc:  # noqa: BLE001
            errors.append({"match_id": match_id, "event_id": ev, "error": f"{type(exc).__name__}: {exc}"})
        if (i + 1) % 50 == 0:
            print(f"    {i + 1}/{len(focus)} ({time.time() - t0:.0f}s)")
    df = pd.DataFrame(rows)
    if not df.empty:
        df["neg_escape"] = -df["escape"]
        df["neg_ways_out"] = -df["ways_out"]
        df["y_contained"] = 1 - df["y_escaped"]
        df["top_squeezer"] = df["top_squeezer_id"].map(
            lambda v: ctx.name_of.get(int(v), "") if pd.notna(v) else ""
        )
    EVENTS.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)
    if errors:
        err_path = EVENTS / f"errors_{match_id}.csv"
        pd.DataFrame(errors).to_csv(err_path, index=False)
        print(f"  scored {len(df)}, {len(errors)} errors -> {err_path.name}")
    else:
        print(f"  scored {len(df)} presses in {time.time() - t0:.0f}s")
    return df


def _fmt(v, nd: int = 3) -> str:
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "—"
    return f"{v:.{nd}f}" if isinstance(v, (float, np.floating)) else str(v)


def _md(df: pd.DataFrame) -> str:
    if df.empty:
        return "_(none)_"
    head = "| " + " | ".join(df.columns) + " |"
    sep = "|" + "---|" * len(df.columns)
    body = ["| " + " | ".join(_fmt(v) for v in r) + " |" for r in df.itertuples(index=False)]
    return "\n".join([head, sep, *body])


def disagreements(df: pd.DataFrame) -> pd.DataFrame:
    pressed = df[df["press_type"] != "not_a_press"].copy()
    low, high = pressed["lane_tax"].quantile(0.25), pressed["lane_tax"].quantile(0.75)
    gap = -pressed["b_presser_gap"]
    looks = pressed[(gap <= 2.5) & (pressed["lane_tax"] <= low)].assign(kind="looks_like_press_tax_says_no")
    quiet = pressed[(gap >= 5.0) & (pressed["lane_tax"] >= high)].assign(kind="quiet_press_tax_says_yes")
    cols = ["kind", "match_id", "clock", "presser", "press_team", "carrier", "press_type",
            "outcome", "lane_tax", "credit_share", "ways_out", "escape", "b_presser_gap", "y_contained"]
    out = pd.concat([looks, quiet], ignore_index=True)
    return out[[c for c in cols if c in out.columns]]


def write_summary(
    pressed: pd.DataFrame,
    pooled: pd.DataFrame,
    lomo: pd.DataFrame,
    per_match: pd.DataFrame,
    gains: pd.DataFrame,
    logistic: pd.DataFrame,
    disc: pd.DataFrame,
    n_matches: int,
    n_errors: int,
) -> None:
    lines = [
        "# Phase 3 — leave-one-match-out validation",
        "",
        "Constants frozen from Phase 2. No further tuning.",
        "",
        f"- Matches: **{n_matches}**",
        f"- Focus presses scored: **{len(pressed)}** (excluded `not_a_press`)",
        f"- Scoring errors logged: {n_errors}",
        "",
        "## How to read this",
        "",
        "**AUC** = pick one press that worked and one that didn't; how often the score ranks the good one higher.",
        "**0.50 = coin flip.** Leave-one-match-out = compute that on each match separately, then average",
        "(so one weird game can't carry the result).",
        "",
        "### Headline scores",
        "",
        "- **Ways out left** — team squeeze. Should predict containment / forced errors.",
        "- **Lane Tax** — presser credit. Should *not* need to predict team outcomes; checked via examples.",
        "",
        "## Leave-one-match-out mean AUC",
        "",
    ]
    for lab in LABELS:
        sub = lomo[lomo["label"] == lab].sort_values("mean_auc", ascending=False)
        if sub.empty:
            continue
        lines += [f"### {LABEL_TEXT[lab]}", "",
                  "| score | mean AUC | std across matches |", "|---|---|---|"]
        for r in sub.itertuples():
            lines.append(f"| {SCORE_TEXT.get(r.score, r.score)} | {_fmt(r.mean_auc)} | {_fmt(r.std_auc)} |")
        lines.append("")

    lines += [
        "## Ways out vs best proximity baseline (pooled, paired bootstrap)",
        "",
        _md(gains),
        "",
        "## Does ways out add to SkillCorner options-ahead?",
        "",
        "Logistic regression fit on 19 matches, tested on the held-out match.",
        "Features are rank-percentiles so units don't matter.",
        "",
    ]
    if not logistic.empty:
        summary = logistic.groupby("model")["auc"].agg(["mean", "std", "count"]).reset_index()
        summary.columns = ["model", "mean_auc", "std_auc", "n_matches"]
        summary["model"] = summary["model"].map(lambda m: SCORE_TEXT.get(m, m))
        lines += [_md(summary.round(3)), "", "Per held-out match:", "", _md(logistic.round(3)), ""]
    else:
        lines += ["_(could not fit)_", ""]

    # Per-match for ways_out on containment
    key = per_match[(per_match["label"] == "y_contained") & (per_match["score"] == "neg_ways_out")]
    if not key.empty:
        lines += ["## Per-match AUC: ways out → contained", "", _md(key[["match_id", "n", "positives", "auc"]].round(3)), ""]

    looks = disc[disc["kind"] == "looks_like_press_tax_says_no"]
    quiet = disc[disc["kind"] == "quiet_press_tax_says_yes"]
    lines += [
        f"## 'Looks like a press, tax says no' ({len(looks)} across all matches)",
        "",
        "Presser within 2.5 m, bottom-quartile Lane Tax.",
        "",
        _md(looks.head(15)),
        "",
        f"## 'Quiet press' ({len(quiet)} across all matches)",
        "",
        "Presser 5 m+ away, top-quartile Lane Tax.",
        "",
        _md(quiet.head(15)),
        "",
        "## Verdict",
        "",
    ]
    # Auto-draft a short verdict from numbers
    ways = lomo[(lomo["label"] == "y_contained") & (lomo["score"] == "neg_ways_out")]
    gap = lomo[(lomo["label"] == "y_contained") & (lomo["score"] == "b_presser_gap")]
    sc = lomo[(lomo["label"] == "y_contained") & (lomo["score"] == "b_sc_fewer_options_ahead")]
    tax = lomo[(lomo["label"] == "y_contained") & (lomo["score"] == "lane_tax")]
    w = float(ways["mean_auc"].iloc[0]) if len(ways) else np.nan
    g = float(gap["mean_auc"].iloc[0]) if len(gap) else np.nan
    s = float(sc["mean_auc"].iloc[0]) if len(sc) else np.nan
    t = float(tax["mean_auc"].iloc[0]) if len(tax) else np.nan
    lines += [
        f"- Ways out mean AUC on containment: **{_fmt(w)}** (presser gap **{_fmt(g)}**, "
        f"SC options-ahead **{_fmt(s)}**).",
        f"- Lane Tax mean AUC on containment: **{_fmt(t)}** (near 0.50 = credit ≠ team outcome, as designed).",
        "",
        "See `auc_lomo.csv` / `logistic_lomo.csv` for the full numbers.",
        "",
    ]
    (OUT / "summary.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--match-ids", nargs="*", type=int, default=None,
                        help="Subset of match ids (default: all 20)")
    parser.add_argument("--skip-score", action="store_true",
                        help="Only rebuild tables from cached event CSVs")
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    EVENTS.mkdir(parents=True, exist_ok=True)

    ids = args.match_ids or list_match_ids()
    frames = []
    for mid in ids:
        print(f"match {mid}")
        if args.skip_score:
            path = EVENTS / f"match_{mid}.csv"
            if not path.exists():
                print(f"  missing cache {path.name}, scoring…")
                frames.append(_score_match(mid))
            else:
                frames.append(pd.read_csv(path))
        else:
            frames.append(_score_match(mid))

    all_df = pd.concat(frames, ignore_index=True)
    all_df.to_csv(OUT / "all_events.csv", index=False)
    pressed = all_df[all_df["press_type"] != "not_a_press"].copy()
    print(f"pooled {len(all_df)} rows, {len(pressed)} after excluding not_a_press")

    # Ensure derived cols exist if loaded from older cache
    if "neg_ways_out" not in pressed.columns:
        pressed["neg_ways_out"] = -pressed["ways_out"]
        pressed["neg_escape"] = -pressed["escape"]
    if "y_contained" not in pressed.columns:
        pressed["y_contained"] = 1 - pressed["y_escaped"]

    pooled = auc_table_fast(pressed, SCORES, LABELS)
    pooled.to_csv(OUT / "auc_pooled.csv", index=False)

    lomo = lomo_mean_auc(pressed, SCORES, LABELS)
    lomo.to_csv(OUT / "auc_lomo.csv", index=False)

    per_rows = []
    for lab in LABELS:
        for sc in ("neg_ways_out", "lane_tax", "b_presser_gap", "b_sc_fewer_options_ahead",
                   "b_nearest_opponent", "b_opponents_within_5m"):
            part = leave_one_match_out(pressed, sc, lab)
            part["label"] = lab
            part["score"] = sc
            per_rows.append(part)
    per_match = pd.concat(per_rows, ignore_index=True)
    per_match.to_csv(OUT / "lomo_per_match.csv", index=False)

    gains = []
    for lab in LABELS:
        prox = ["b_presser_gap", "b_nearest_opponent", "b_opponents_within_5m", "b_closing_speed", "b_presser_time"]
        best_prox = max(prox, key=lambda s: auc(pressed[s], pressed[lab]) or 0.0)
        for sc in ("neg_ways_out", "lane_tax"):
            d, lo, hi = paired_auc_gain(pressed[sc], pressed[best_prox], pressed[lab], n=PHASE3_BOOT)
            gains.append({"label": lab, "score": SCORE_TEXT[sc], "vs": SCORE_TEXT[best_prox],
                          "auc_gain": d, "ci_lo": lo, "ci_hi": hi})
        d, lo, hi = paired_auc_gain(
            pressed["neg_ways_out"], pressed["b_sc_fewer_options_ahead"], pressed[lab], n=PHASE3_BOOT
        )
        gains.append({"label": lab, "score": SCORE_TEXT["neg_ways_out"],
                      "vs": SCORE_TEXT["b_sc_fewer_options_ahead"],
                      "auc_gain": d, "ci_lo": lo, "ci_hi": hi})
    gains = pd.DataFrame(gains)
    gains.to_csv(OUT / "paired_gains.csv", index=False)

    # Logistic LOMO: ways alone, SC alone, both
    log_parts = []
    for lab in ("y_contained", "y_forced_error"):
        for name, feats in (
            ("rank_ways", ["neg_ways_out"]),
            ("rank_sc", ["b_sc_fewer_options_ahead"]),
            ("logistic_both", ["neg_ways_out", "b_sc_fewer_options_ahead"]),
        ):
            part = lomo_logistic_auc(pressed, feats, lab)
            part["label"] = lab
            part["model"] = name
            log_parts.append(part)
    logistic = pd.concat(log_parts, ignore_index=True) if log_parts else pd.DataFrame()
    logistic.to_csv(OUT / "logistic_lomo.csv", index=False)

    disc = disagreements(pressed)
    disc.to_csv(OUT / "disagreements.csv", index=False)

    n_errors = sum(1 for p in EVENTS.glob("errors_*.csv"))
    write_summary(pressed, pooled, lomo, per_match, gains, logistic, disc, len(ids), n_errors)
    print(f"wrote {OUT / 'summary.md'}")


if __name__ == "__main__":
    main()
