"""Phase 2: score every focus press in one match with the Lane Tax and compare it with the baselines.

Outputs (docs/phase2/):
  lane_tax_events.csv   one row per press: tax, components, baselines, labels
  xpass_check.csv       our pass openness vs SkillCorner xPass on their passing options
  auc.csv               every score x every label, with bootstrap 95% intervals
  presser_table.csv     per-presser totals (who actually takes lanes away)
  summary.md            plain-football summary + R01-R15 against your review
  lane_maps/*.png       reality vs presser-deleted lane maps
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

from lane_tax.config import DEFAULT_MATCH_ID
from lane_tax.data import load_tracking_frames
from lane_tax.explore import focus_press_events, sample_review_presses
from lane_tax.lane_map import render_lane_map
from lane_tax.metric import build_scene, score_scene
from lane_tax.press_story import MatchContext, build_story
from lane_tax.press_tax import chain_ids, key_frames, press_rows, scene_at, score_press
from lane_tax.validate import auc, auc_table, paired_auc_gain, spearman

OUT = ROOT / "docs" / "phase2"
YOUR_REVIEW = ROOT / "docs" / "phase1_review" / "your_review.csv"
MAP_IDS = ("R01", "R03", "R04", "R06", "R08", "R09", "R12", "R15")

TEAM_SCORES = ["neg_escape", "neg_ways_out", "squeeze_total", "unit_tax"]
CREDIT_SCORES = ["lane_tax", "ways_tax", "peak_lane_tax", "d_lane_tax", "lanes_cut", "trap_tax",
                 "lane_tax_block", "lane_tax_rush"]
TAX_SCORES = TEAM_SCORES + CREDIT_SCORES
BASELINES = ["b_presser_gap", "b_nearest_opponent", "b_opponents_within_5m", "b_closing_speed", "b_presser_time",
             "b_sc_pressure", "b_sc_option_ease", "b_sc_fewer_options", "b_sc_fewer_options_ahead"]
LABELS = ["y_press_success", "y_contained", "y_sc_effect", "y_forced_error", "y_regain"]
LABEL_TEXT = {
    "y_press_success": "team outcome good (story engine, ~8 s)",
    "y_contained": "attack did NOT escape under control within 4 s",
    "y_sc_effect": "SkillCorner says the press forced back / reduced / stopped danger",
    "y_forced_error": "carrier's response was a failed pass, a loss or a clearance",
    "y_regain": "press team won it back within 5 s",
}
SCORE_TEXT = {
    "neg_escape": "TEAM: best way out left (fewer = higher)", "neg_ways_out": "TEAM: ways out left (fewer = higher)",
    "squeeze_total": "TEAM: total squeeze from defenders near the ball", "unit_tax": "TEAM: pressing-chain tax",
    "lane_tax": "Lane Tax (presser, at release)", "ways_tax": "Ways-out tax (presser)",
    "peak_lane_tax": "Lane Tax (presser, peak)", "d_lane_tax": "Lane Tax (presser, 1 s in)",
    "lanes_cut": "Lanes cut (presser, every lane)", "trap_tax": "Trap tax (presser)",
    "lane_tax_block": "Lane Tax — block part", "lane_tax_rush": "Lane Tax — rush part",
    "b_presser_gap": "Presser gap (closer = higher)", "b_nearest_opponent": "Nearest opponent",
    "b_opponents_within_5m": "Opponents within 5 m", "b_closing_speed": "Closing speed",
    "b_presser_time": "Presser time-to-carrier", "b_sc_pressure": "SkillCorner pressure band",
    "b_sc_option_ease": "SkillCorner option ease (harder = higher)",
    "b_sc_fewer_options": "SkillCorner fewer passing options", "b_sc_fewer_options_ahead": "SkillCorner fewer options ahead",
}


def run_presses(ctx: MatchContext, review_map: dict[str, str]) -> tuple[pd.DataFrame, dict]:
    focus = focus_press_events(ctx.match_id)
    rows, kept, errors = [], {}, []
    t0 = time.time()
    for i, ev in enumerate(focus["event_id"]):
        rid = review_map.get(ev, "")
        try:
            story = build_story(ctx, ev, rid)
            row, results = score_press(ctx, story)
            rows.append(row)
            if rid:
                kept[rid] = (story, results)
        except Exception as exc:  # noqa: BLE001 - one bad press must not stop the run
            errors.append({"event_id": ev, "error": f"{type(exc).__name__}: {exc}"})
        if (i + 1) % 50 == 0:
            print(f"  {i + 1}/{len(focus)} presses ({time.time() - t0:.0f}s)")
    df = pd.DataFrame(rows)
    df["neg_escape"] = -df["escape"]
    df["neg_ways_out"] = -df["ways_out"]
    df["y_contained"] = 1 - df["y_escaped"]
    df["top_squeezer"] = df["top_squeezer_id"].map(lambda v: ctx.name_of.get(int(v), "") if pd.notna(v) else "")
    if errors:
        pd.DataFrame(errors).to_csv(OUT / "errors.csv", index=False)
    print(f"scored {len(df)} presses, {len(errors)} errors")
    return df, kept


def xpass_check(ctx: MatchContext) -> pd.DataFrame:
    """Is our 'is this pass on?' in line with SkillCorner's xPass for the same options?"""
    po = ctx.events[(ctx.events["event_type"] == "passing_option") & ctx.events["xpass_completion"].notna()]
    pp = ctx.pp.set_index("event_id")
    rows = []
    for o in po.itertuples():
        poss = getattr(o, "associated_player_possession_event_id")
        if poss not in pp.index:
            continue
        p = pp.loc[poss]
        f = int(o.frame_start)
        sign = 1 if str(p["attacking_side"]) == "left_to_right" else -1
        scene = build_scene(ctx._pos, ctx.team_of, f, int(p["player_id"]), None, sign,
                            ctx.meta["pitch_length"] / 2, ctx.meta["pitch_width"] / 2)
        if scene is None:
            continue
        res = score_scene(scene)
        mine = next((x for x in res.options if x.kind == "pass" and x.target_id == int(o.player_id)), None)
        if mine is None:
            continue
        rows.append({"event_id": o.event_id, "frame": f, "receiver": int(o.player_id), "length_m": mine.length,
                     "our_openness": mine.open_prob(), "our_clear": mine.clear_prob(),
                     "sc_xpass": float(o.xpass_completion), "targeted": bool(o.targeted)})
    return pd.DataFrame(rows)


def within_gap_auc(df: pd.DataFrame, score: str, label: str, bands: int = 3) -> float | None:
    """AUC of ``score`` among presses at a similar presser distance: does it add anything beyond
    'how close is he'? Averaged over gap bands, weighted by size."""
    sub = df[[score, label, "b_presser_gap"]].dropna()
    if len(sub) < 30:
        return None
    sub = sub.assign(band=pd.qcut(-sub["b_presser_gap"], bands, labels=False, duplicates="drop"))
    tot, w = 0.0, 0
    for _, g in sub.groupby("band"):
        a = auc(g[score], g[label])
        if a is not None:
            tot += a * len(g)
            w += len(g)
    return tot / w if w else None


def lane_maps(ctx: MatchContext, kept: dict) -> list[str]:
    out = []
    for rid in MAP_IDS:
        if rid not in kept:
            continue
        story, _ = kept[rid]
        eng, p0 = press_rows(ctx, story.event_id)
        _, _, f_rel = key_frames(story, p0)
        scene = scene_at(ctx, story, f_rel, chain_ids(ctx, eng))
        if scene is None:
            continue
        res = score_scene(scene)
        path = render_lane_map(
            scene, res,
            f"{rid} — {story.presser_name} ({story.press_abbr}) pressing {story.carrier_name} ({story.attack_abbr})",
            f"{story.clock} · setup: {story.press_type.replace('_', ' ')} · presser: {story.credit} · "
            f"team: {story.outcome_title}",
            OUT / "lane_maps" / f"{rid}.png",
        )
        out.append(path.name)
    return out


def presser_table(df: pd.DataFrame, min_presses: int = 4) -> pd.DataFrame:
    g = df.groupby(["presser", "press_team"]).agg(
        presses=("event_id", "size"), lanes_cut=("lanes_cut", "sum"), mean_lane_tax=("lane_tax", "mean"),
        mean_credit_share=("credit_share", "mean"), mean_unit_tax=("unit_tax", "mean"),
        mean_gap_m=("b_presser_gap", lambda s: -s.mean()),
        success_rate=("y_press_success", "mean"), contained_rate=("y_contained", "mean"),
    ).reset_index()
    return g[g["presses"] >= min_presses].sort_values("mean_lane_tax", ascending=False).round(3)


def disagreements(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """'Looks like a press, tax says no' (tight but low tax) and 'quiet press' (far but high tax)."""
    pressed = df[df["press_type"] != "not_a_press"]
    low, high = pressed["lane_tax"].quantile(0.25), pressed["lane_tax"].quantile(0.75)
    gap = -pressed["b_presser_gap"]
    looks = pressed[(gap <= 2.5) & (pressed["lane_tax"] <= low)]
    quiet = pressed[(gap >= 5.0) & (pressed["lane_tax"] >= high)]
    cols = ["clock", "presser", "press_team", "carrier", "press_type", "presser_verdict", "outcome",
            "lane_tax", "credit_share", "top_squeezer", "escape", "b_presser_gap", "best_option", "y_contained"]
    return looks[cols].sort_values("lane_tax"), quiet[cols].sort_values("lane_tax", ascending=False)


def _fmt(v, nd: int = 2) -> str:
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "—"
    return f"{v:.{nd}f}" if isinstance(v, (float, np.floating)) else str(v)


def _md(df: pd.DataFrame) -> str:
    head = "| " + " | ".join(df.columns) + " |"
    sep = "|" + "---|" * len(df.columns)
    body = ["| " + " | ".join(_fmt(v) for v in r) + " |" for r in df.itertuples(index=False)]
    return "\n".join([head, sep, *body])


def write_summary(df: pd.DataFrame, aucs: pd.DataFrame, xp: pd.DataFrame, gains: pd.DataFrame,
                  gap_aware: pd.DataFrame, looks: pd.DataFrame, quiet: pd.DataFrame, pressers: pd.DataFrame,
                  maps: list[str], match_id: int) -> None:
    pressed = df[df["press_type"] != "not_a_press"]
    rho, n_xp = spearman(xp["our_openness"], xp["sc_xpass"]) if not xp.empty else (np.nan, 0)
    rho_t, n_t = spearman(pressed["lane_tax"], pressed["chosen_xpass"])
    lines = [
        f"# Phase 2 — Lane Tax on match {match_id}",
        "",
        "> **One match, in-sample.** Nothing here is fitted, but the constants were sanity-checked on this match,",
        "> so these numbers are a smoke test. The real test is Phase 3: all matches, held out.",
        "",
        f"- Presses scored: **{len(df)}** ({len(df) - len(pressed)} flagged *not a real press* and left out of the tests below)",
        f"- Median Lane Tax {pressed['lane_tax'].median():.2f}; top quarter above {pressed['lane_tax'].quantile(0.75):.2f}",
        f"- Our 'is this pass on?' vs SkillCorner xPass on {n_xp} of their passing options: Spearman **{rho:.2f}**",
        f"- Higher Lane Tax -> carrier ends up playing a lower-xPass pass? Spearman {rho_t:.2f} (n={n_t}; negative = yes)",
        "",
        "## Does it separate presses that worked from ones that didn't?",
        "",
        "AUC = if you pick one press that worked and one that didn't, how often the score ranks the one that worked",
        "higher. 0.50 is a coin flip. Brackets are 95% bootstrap intervals.",
        "",
    ]
    for lab in LABELS:
        sub = aucs[aucs["label"] == lab].copy()
        if sub.empty:
            continue
        sub = sub.sort_values("auc", ascending=False)
        lines += [f"### {LABEL_TEXT[lab]}  (n={int(sub['n'].iloc[0])}, worked={int(sub['positives'].iloc[0])})", "",
                  "| score | AUC | 95% interval |", "|---|---|---|"]
        for r in sub.itertuples():
            star = " **(tax)**" if r.score in TAX_SCORES else ""
            lines.append(f"| {SCORE_TEXT.get(r.score, r.score)}{star} | {_fmt(r.auc)} | {_fmt(r.ci_lo)}–{_fmt(r.ci_hi)} |")
        lines.append("")
    lines += ["## Our scores vs the best simple baseline (same presses, paired bootstrap)", "", _md(gains), "",
              "## Among presses at the same distance, does the tax still tell them apart?", "",
              "AUC within presser-gap terciles (so 'he was just closer' is taken out).", "", _md(gap_aware), "",
              f"## 'Looks like a press, tax says no' ({len(looks)} presses)", "",
              "Presser within 2.5 m at release, but bottom-quarter Lane Tax: close, yet the carrier still had a way out.",
              "", _md(looks.head(12)), "",
              f"## 'Quiet press' ({len(quiet)} presses)", "",
              "Presser 5 m+ away but top-quarter Lane Tax: he took the lane without getting tight.", "",
              _md(quiet.head(12)), "",
              "## Who takes lanes away (pressers with 4+ presses)", "", _md(pressers.head(15)), ""]

    rev = df[df["review_id"] != ""].sort_values("review_id")
    if not rev.empty:
        cols = ["review_id", "press_type", "outcome", "escape_no_presser", "escape", "ways_out", "lane_tax",
                "lane_tax_rush", "ways_tax", "credit_share", "top_squeezer", "unit_tax", "trap_tax", "your_take"]
        lines += ["## Your 15 reviewed presses", "", _md(rev[[c for c in cols if c in rev.columns]]), ""]
    if maps:
        lines += ["## Lane maps", ""] + [f"![{m}](lane_maps/{m})" for m in maps] + [""]
    (OUT / "summary.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--match-id", type=int, default=DEFAULT_MATCH_ID)
    parser.add_argument("--skip-xpass", action="store_true")
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)

    sample = sample_review_presses(match_id=args.match_id)
    review_map = dict(zip(sample["event_id"], sample["review_id"]))
    players, frame_meta = load_tracking_frames(args.match_id, use_cache=True)
    ctx = MatchContext(args.match_id, players, frame_meta)

    df, kept = run_presses(ctx, review_map)
    if YOUR_REVIEW.exists():
        df = df.merge(pd.read_csv(YOUR_REVIEW)[["review_id", "your_take"]], on="review_id", how="left")
    df.to_csv(OUT / "lane_tax_events.csv", index=False)

    pressed = df[df["press_type"] != "not_a_press"]
    aucs = auc_table(pressed, TAX_SCORES + BASELINES, LABELS)
    aucs.to_csv(OUT / "auc.csv", index=False)

    gains, gap_aware = [], []
    for lab in LABELS:
        base = aucs[(aucs["label"] == lab) & aucs["score"].isin(BASELINES)].sort_values("auc", ascending=False)
        if base.empty:
            continue
        best = base.iloc[0]["score"]
        for sc in ("neg_ways_out", "neg_escape", "lane_tax"):
            d, lo, hi = paired_auc_gain(pressed[sc], pressed[best], pressed[lab])
            gains.append({"label": lab, "score": SCORE_TEXT[sc], "best_baseline": SCORE_TEXT[best],
                          "auc_gain": d, "ci_lo": lo, "ci_hi": hi})
        gap_aware.append({"label": lab, **{sc: within_gap_auc(pressed, sc, lab) for sc in
                          ("neg_ways_out", "neg_escape", "squeeze_total", "lane_tax", "ways_tax",
                           "b_opponents_within_5m", "b_sc_pressure", "b_sc_fewer_options_ahead")}})
    gains, gap_aware = pd.DataFrame(gains), pd.DataFrame(gap_aware)

    xp = pd.DataFrame() if args.skip_xpass else xpass_check(ctx)
    if not xp.empty:
        xp.to_csv(OUT / "xpass_check.csv", index=False)
    looks, quiet = disagreements(df)
    pressers = presser_table(df[df["press_type"] != "not_a_press"])
    pressers.to_csv(OUT / "presser_table.csv", index=False)
    maps = lane_maps(ctx, kept)
    write_summary(df, aucs, xp, gains, gap_aware, looks, quiet, pressers, maps, args.match_id)
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
