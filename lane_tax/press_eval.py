"""What matters when evaluating a press (v1).

A press is not just \"did a defender get close.\" The useful question is:

1. Close quality — did the presser actually shrink useful options?
2. Forced action — what did the carrier do because of that?
3. Ball destination — after a pass/clearance, where did the ball go?
4. Aftermath — did the attacking team keep the ball, or turn it over?

GIF / labels should make those four beats obvious over time.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from lane_tax.config import OUTCOME_WINDOW_FRAMES, PROGRESSIVE_ADVANCE_M
from lane_tax.explore import attacking_sign_for_frame


# Extra time after the main outcome window so we can watch the pass land / turnover.
AFTERMATH_EXTRA_FRAMES = 20  # +2.0s beyond the 3s outcome window
BALL_LEAVE_M = 3.0
RECEIVE_M = 2.5


@dataclass
class PressStory:
    """Structured story used by GIFs and labeling."""

    review_label: str
    verdict_title: str
    one_liner: str
    close_quality: str
    forced_action: str
    ball_destination: str
    aftermath: str
    possession_lost: bool
    progressive: bool
    presser_end_dist_m: float | None
    advance_m: float | None


def _ease_harder(ease0: Any, ease1: Any) -> bool:
    rank = {"very_easy": 0, "easy": 1, "medium": 2, "hard": 3, "very_hard": 4}
    if not isinstance(ease0, str) or not isinstance(ease1, str):
        return False
    return rank.get(ease1, 2) > rank.get(ease0, 2)


def classify_forced_action(row: pd.Series) -> str:
    end = row.get("associated_player_possession_end_type")
    adv = row.get("outcome_advance_m")
    if end == "possession_loss":
        return "lost the ball"
    if end == "clearance":
        return "cleared it long"
    if end == "foul_suffered":
        return "won a foul"
    if end == "shot":
        return "got a shot"
    if end == "pass":
        if pd.notna(adv) and float(adv) >= PROGRESSIVE_ADVANCE_M:
            return "passed forward (progressive)"
        if pd.notna(adv) and float(adv) < 0:
            return "passed / recycled backwards"
        return "passed (little progress)"
    return "unknown next action"


def classify_aftermath(row: pd.Series) -> str:
    """Team-level aftermath using SkillCorner flags we already joined."""
    press_end = row.get("end_type")
    lost = bool(row.get("outcome_possession_lost") or 0)
    phase_loss = bool(row.get("team_possession_loss_in_phase")) if pd.notna(
        row.get("team_possession_loss_in_phase")
    ) else False

    if isinstance(press_end, str):
        if "regain" in press_end:
            return f"pressing team regained ({press_end})"
        if "disruption" in press_end:
            return f"press disrupted the attack ({press_end})"

    if lost:
        return "attacking team lost possession on this touch"
    if phase_loss:
        return "attacking team eventually lost the ball in this phase"
    if int(row.get("outcome_progressive") or 0) == 1:
        return "attack kept the ball and progressed"
    return "attack kept the ball but did not progress much"


def classify_close_quality(row: pd.Series) -> str:
    d0 = row.get("interplayer_distance_start")
    d1 = row.get("interplayer_distance_end")
    if pd.isna(d0) or pd.isna(d1):
        return "unknown close"
    d0, d1 = float(d0), float(d1)
    if d1 <= 4.0 or (d0 - d1) >= 2.5:
        return f"closed hard ({d0:.1f}m → {d1:.1f}m)"
    if d1 >= 7.5 and (d0 - d1) < 2.0:
        return f"stayed far ({d0:.1f}m → {d1:.1f}m)"
    return f"edged closer ({d0:.1f}m → {d1:.1f}m)"


def evaluate_press(row: pd.Series) -> PressStory:
    """Full press evaluation for labels + GIF banners."""
    close = classify_close_quality(row)
    forced = classify_forced_action(row)
    aftermath = classify_aftermath(row)
    lost = bool(row.get("outcome_possession_lost") or 0)
    progressive = bool(int(row.get("outcome_progressive") or 0))
    d1 = row.get("interplayer_distance_end")
    d1f = float(d1) if pd.notna(d1) else None
    adv = row.get("outcome_advance_m")
    advf = float(adv) if pd.notna(adv) else None

    closed_hard = d1f is not None and (
        d1f <= 4.0
        or (
            pd.notna(row.get("interplayer_distance_start"))
            and float(row["interplayer_distance_start"]) - d1f >= 2.5
        )
    )
    stayed_far = d1f is not None and d1f >= 7.5 and not closed_hard
    options_harder = _ease_harder(
        row.get("passing_option_ease_start"), row.get("passing_option_ease_end")
    )

    # Destination blurb from advance + end type (geometry of pass comes in the GIF)
    if lost:
        destination = "ball ended in a turnover"
    elif row.get("associated_player_possession_end_type") == "clearance":
        destination = "ball was cleared away from danger"
    elif progressive:
        destination = "ball moved into more advanced space"
    elif advf is not None and advf < 0:
        destination = "ball went backwards / sideways to safety"
    else:
        destination = "ball moved but without real progress"

    # Verdict logic — aftermath matters
    if closed_hard and (lost or (not progressive and (options_harder or (advf is not None and advf < 4)))):
        label = "cut_off"
        title = "PRESS WORKED"
        one = "Presser closed useful space and the attack broke down or went backwards."
    elif closed_hard and progressive:
        label = "motion_only"
        title = "PRESS DIDN'T STOP THEM"
        one = "Presser got close, but the attack still progressed after the ball moved on."
    elif stayed_far and (lost or not progressive):
        label = "unclear"
        title = "HARD TO CREDIT THIS PRESS"
        one = "The attack stalled or turned over, but this presser stayed too far to clearly own it."
    elif stayed_far and progressive:
        label = "motion_only"
        title = "PRESS DIDN'T STOP THEM"
        one = "Presser never really arrived; attack progressed anyway."
    elif lost:
        label = "unclear"
        title = "TURNOVER — ATTRIBUTION UNCLEAR"
        one = "There was a turnover, but presser engagement was only moderate."
    else:
        label = "unclear"
        title = "MIXED / UNCLEAR"
        one = "Signals disagree between close quality, pass destination, and aftermath."

    return PressStory(
        review_label=label,
        verdict_title=title,
        one_liner=one,
        close_quality=close,
        forced_action=forced,
        ball_destination=destination,
        aftermath=aftermath,
        possession_lost=lost,
        progressive=progressive,
        presser_end_dist_m=d1f,
        advance_m=advf,
    )


def story_bullets(story: PressStory) -> list[str]:
    return [
        f"1) Close: {story.close_quality}",
        f"2) Forced action: {story.forced_action}",
        f"3) Ball destination: {story.ball_destination}",
        f"4) Aftermath: {story.aftermath}",
        f"Bottom line: {story.one_liner}",
    ]
