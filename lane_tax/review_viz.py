"""Clearer Phase 1 review visuals: zoomed before/after with all players + lanes."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import FancyBboxPatch, Polygon
from mplsoccer import Pitch

from lane_tax.config import (
    BACK_LANE_LENGTH_M,
    LANE_HALF_WIDTH_M,
    LANE_LENGTH_M,
    TAX_WINDOW_FRAMES,
)
from lane_tax.data import load_match_meta, load_phases_of_play, load_tracking_frames
from lane_tax.explore import ATTACK_SIGN, attacking_sign_for_frame


def roster_team_map(match_id: int) -> dict[int, int]:
    meta = load_match_meta(match_id)
    return {int(p["id"]): int(p["team_id"]) for p in meta["players"]}


def _lane_polygon(
    cx: float,
    cy: float,
    direction_xy: tuple[float, float],
    length: float,
    half_width: float,
) -> np.ndarray:
    dx, dy = direction_xy
    norm = np.hypot(dx, dy) or 1.0
    ux, uy = dx / norm, dy / norm
    px, py = -uy, ux  # perpendicular
    tip_x, tip_y = cx + ux * length, cy + uy * length
    return np.array(
        [
            [cx + px * half_width, cy + py * half_width],
            [tip_x + px * half_width, tip_y + py * half_width],
            [tip_x - px * half_width, tip_y - py * half_width],
            [cx - px * half_width, cy - py * half_width],
        ]
    )


def lane_polys_for_carrier(
    cx: float, cy: float, attack_sign: float
) -> dict[str, np.ndarray]:
    """Progressive (attack dir), wide (perpendicular), back (away from goal)."""
    return {
        "progressive": _lane_polygon(
            cx, cy, (attack_sign, 0.0), LANE_LENGTH_M, LANE_HALF_WIDTH_M
        ),
        "wide": _lane_polygon(
            cx, cy, (0.0, 1.0 if cy >= 0 else -1.0), LANE_LENGTH_M, LANE_HALF_WIDTH_M
        ),
        "back": _lane_polygon(
            cx, cy, (-attack_sign, 0.0), BACK_LANE_LENGTH_M, LANE_HALF_WIDTH_M
        ),
    }


def _frame_players(players: pd.DataFrame, frame: int) -> pd.DataFrame:
    return players[players["frame"] == frame].copy()


def _plain_english(row: pd.Series) -> str:
    d0 = row.get("interplayer_distance_start")
    d1 = row.get("interplayer_distance_end")
    adv = row.get("outcome_advance_m")
    end = row.get("associated_player_possession_end_type")
    parts = []
    if pd.notna(d0) and pd.notna(d1):
        parts.append(f"Presser distance {d0:.1f}m → {d1:.1f}m")
    if pd.notna(adv):
        if adv >= 8:
            parts.append(f"attack advanced {adv:.1f}m (progressive)")
        elif adv >= 0:
            parts.append(f"little progress ({adv:.1f}m)")
        else:
            parts.append(f"went backwards ({adv:.1f}m)")
    if isinstance(end, str):
        parts.append(f"possession ended: {end}")
    ease0 = row.get("passing_option_ease_start")
    ease1 = row.get("passing_option_ease_end")
    if isinstance(ease0, str) and isinstance(ease1, str):
        parts.append(f"pass options felt {ease0} → {ease1}")
    return " | ".join(parts)


def plot_review_card(
    row: pd.Series,
    players: pd.DataFrame,
    frame_meta: pd.DataFrame,
    phases: pd.DataFrame,
    team_of: dict[int, int],
    meta: dict[str, Any],
    out_path: Path,
) -> None:
    home_id = int(meta["home_team"]["id"])
    frame0 = int(row["frame_start"])
    frame1 = frame0 + TAX_WINDOW_FRAMES
    carrier_id = int(row["player_in_possession_id"]) if pd.notna(row["player_in_possession_id"]) else None
    presser_id = int(row["player_id"]) if pd.notna(row["player_id"]) else None
    attack_sign = attacking_sign_for_frame(phases, frame0)

    carrier_team = team_of.get(carrier_id) if carrier_id is not None else None

    pitch = Pitch(
        pitch_type="skillcorner",
        pitch_length=meta["pitch_length"],
        pitch_width=meta["pitch_width"],
        line_color="#666666",
        pitch_color="#f7f7f7",
        linewidth=1,
    )
    fig, axs = pitch.draw(nrows=1, ncols=2, figsize=(14, 7))
    fig.subplots_adjust(top=0.78, bottom=0.08, wspace=0.06)

    titles = [
        f"START of press (frame {frame0})",
        f"1 second later (frame {frame1})",
    ]

    # Zoom center from start carrier/ball
    cx0 = row.get("carrier_x0")
    cy0 = row.get("carrier_y0")
    if pd.isna(cx0) or pd.isna(cy0):
        meta0 = frame_meta[frame_meta["frame"] == frame0]
        if not meta0.empty:
            cx0, cy0 = meta0.iloc[0]["ball_x"], meta0.iloc[0]["ball_y"]
    zoom_r = 28.0

    for ax, frame, title in zip(axs, [frame0, frame1], titles):
        fp = _frame_players(players, frame)
        # draw all players
        for _, p in fp.iterrows():
            pid = int(p["player_id"])
            tid = team_of.get(pid)
            if carrier_team is not None and tid == carrier_team:
                color = "#4C78A8"  # attack
            else:
                color = "#E45756"  # defense / unknown
            size = 60
            marker = "o"
            z = 3
            if presser_id is not None and pid == presser_id:
                color = "#B22222"
                size = 180
                marker = "X"
                z = 6
            if carrier_id is not None and pid == carrier_id:
                color = "#1F4E79"
                size = 200
                marker = "o"
                z = 6
            ax.scatter(
                p["x"],
                p["y"],
                s=size,
                c=color,
                marker=marker,
                zorder=z,
                edgecolors="white",
                linewidths=0.6,
            )

        # ball
        fm = frame_meta[frame_meta["frame"] == frame]
        if not fm.empty and pd.notna(fm.iloc[0]["ball_x"]):
            ax.scatter(
                fm.iloc[0]["ball_x"],
                fm.iloc[0]["ball_y"],
                s=90,
                c="black",
                zorder=7,
                label="ball",
            )

        # lanes from carrier position this frame
        crow = fp[fp["player_id"] == carrier_id] if carrier_id is not None else fp.iloc[0:0]
        if not crow.empty:
            cx, cy = float(crow.iloc[0]["x"]), float(crow.iloc[0]["y"])
            polys = lane_polys_for_carrier(cx, cy, attack_sign)
            colors = {
                "progressive": ("#2ca02c", 0.18, "forward lane"),
                "wide": ("#ff7f0e", 0.14, "wide lane"),
                "back": ("#7f7f7f", 0.12, "back lane"),
            }
            for name, poly in polys.items():
                c, a, _lab = colors[name]
                ax.add_patch(
                    Polygon(
                        poly,
                        closed=True,
                        facecolor=c,
                        edgecolor=c,
                        alpha=a,
                        linewidth=1.5,
                        zorder=2,
                    )
                )

            # arrow attack direction
            ax.annotate(
                "",
                xy=(cx + attack_sign * 8, cy),
                xytext=(cx, cy),
                arrowprops=dict(arrowstyle="->", color="#2ca02c", lw=2.5),
                zorder=5,
            )

        # zoom
        if pd.notna(cx0) and pd.notna(cy0):
            ax.set_xlim(cx0 - zoom_r, cx0 + zoom_r)
            ax.set_ylim(cy0 - zoom_r * 0.7, cy0 + zoom_r * 0.7)

        ax.set_title(title, fontsize=12, pad=8)

    # Legend strip
    legend_txt = (
        "Blue dots = attacking team   |   Red dots = defending team\n"
        "Big dark blue = ball carrier   |   Red X = presser   |   Black = ball\n"
        "Green wedge = forward options   |   Orange = wide   |   Grey = back pass\n"
        "Green arrow = direction toward the opponent goal"
    )
    fig.text(0.5, 0.91, legend_txt, ha="center", va="top", fontsize=10, family="sans-serif")

    header = (
        f"{row['review_id']}  ·  {row['event_subtype']} during {row['team_in_possession_phase_type']}"
    )
    fig.suptitle(header, fontsize=14, fontweight="bold", y=0.995)

    explain = _plain_english(row)
    fig.text(0.5, 0.02, explain, ha="center", va="bottom", fontsize=10)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def judge_press(row: pd.Series) -> tuple[str, str]:
    """Compatibility wrapper — full logic lives in press_eval.evaluate_press."""
    from lane_tax.press_eval import evaluate_press

    story = evaluate_press(row)
    return story.review_label, story.one_liner
