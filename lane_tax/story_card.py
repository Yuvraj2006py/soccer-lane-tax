"""Ultra-simple press story cards for human review."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import Circle, FancyBboxPatch, FancyArrowPatch
from mplsoccer import Pitch

from lane_tax.config import TAX_WINDOW_FRAMES
from lane_tax.explore import attacking_sign_for_frame
from lane_tax.review_viz import judge_press


VERDICT_STYLE = {
    "cut_off": {
        "title": "PRESS WORKED",
        "color": "#1B7F4E",
        "bg": "#E7F7EE",
        "blurb": "The presser got close and the attack did not move forward usefully.",
    },
    "motion_only": {
        "title": "PRESS DIDN'T STOP THEM",
        "color": "#A15C00",
        "bg": "#FFF4E5",
        "blurb": "Someone pressed, but the attack still progressed.",
    },
    "unclear": {
        "title": "HARD TO CREDIT THIS PRESS",
        "color": "#5C6B7A",
        "bg": "#EEF2F5",
        "blurb": "The attack may have stalled, but this presser wasn't clearly the reason.",
    },
}


def _story_bullets(row: pd.Series, label: str) -> list[str]:
    d0 = row.get("interplayer_distance_start")
    d1 = row.get("interplayer_distance_end")
    adv = row.get("outcome_advance_m")
    end = row.get("associated_player_possession_end_type")
    name = row.get("player_in_possession_name") or "the carrier"

    bullets: list[str] = []
    if pd.notna(d0) and pd.notna(d1):
        delta = float(d0) - float(d1)
        if delta >= 2.5 or float(d1) <= 4.0:
            bullets.append(
                f"1) Presser closed in hard: {float(d0):.1f}m → {float(d1):.1f}m"
            )
        elif float(d1) >= 7.5:
            bullets.append(
                f"1) Presser stayed far away: still about {float(d1):.1f}m from {name}"
            )
        else:
            bullets.append(
                f"1) Presser edged closer: {float(d0):.1f}m → {float(d1):.1f}m"
            )

    if pd.notna(adv):
        adv = float(adv)
        if adv >= 8:
            bullets.append(f"2) After the press, the attack still went forward {adv:.1f}m")
        elif adv >= 0:
            bullets.append(f"2) After the press, almost no progress ({adv:.1f}m forward)")
        else:
            bullets.append(f"2) After the press, play went backwards ({abs(adv):.1f}m)")

    if isinstance(end, str):
        pretty = {
            "pass": "they passed the ball",
            "possession_loss": "they lost the ball",
            "clearance": "they cleared it long",
            "shot": "they got a shot",
            "foul_suffered": "they won a foul",
        }.get(end, end)
        bullets.append(f"3) What happened next: {pretty}")

    if label == "cut_off":
        bullets.append("Bottom line: this looks like a useful press.")
    elif label == "motion_only":
        bullets.append("Bottom line: the press looked busy, but didn't kill the attack.")
    else:
        bullets.append("Bottom line: don't strongly credit this presser.")
    return bullets


def _draw_mini(
    ax,
    players: pd.DataFrame,
    frame_meta: pd.DataFrame,
    frame: int,
    carrier_id: int | None,
    presser_id: int | None,
    team_of: dict[int, int],
    carrier_team: int | None,
    attack_sign: float,
    meta: dict[str, Any],
    center: tuple[float, float],
) -> None:
    pitch = Pitch(
        pitch_type="skillcorner",
        pitch_length=meta["pitch_length"],
        pitch_width=meta["pitch_width"],
        line_color="#B0B0B0",
        pitch_color="white",
        linewidth=0.8,
    )
    pitch.draw(ax=ax)

    fp = players[players["frame"] == frame]
    # Only draw nearby players to reduce clutter
    cx, cy = center
    nearby = fp[
        (fp["x"] - cx).abs().le(30) & (fp["y"] - cy).abs().le(22)
    ]

    for _, p in nearby.iterrows():
        pid = int(p["player_id"])
        if carrier_id is not None and pid == carrier_id:
            continue
        if presser_id is not None and pid == presser_id:
            continue
        tid = team_of.get(pid)
        color = "#9BB8D3" if carrier_team is not None and tid == carrier_team else "#E7A6A6"
        ax.scatter(p["x"], p["y"], s=35, c=color, zorder=2, alpha=0.7)

    # carrier
    if carrier_id is not None:
        crow = fp[fp["player_id"] == carrier_id]
        if not crow.empty:
            ax.scatter(
                crow.iloc[0]["x"],
                crow.iloc[0]["y"],
                s=220,
                c="#0B3C6E",
                zorder=5,
                edgecolors="white",
                linewidths=1.5,
            )
            ax.text(
                crow.iloc[0]["x"],
                crow.iloc[0]["y"] + 2.8,
                "HAS BALL",
                ha="center",
                fontsize=8,
                fontweight="bold",
                color="#0B3C6E",
            )
            ax.annotate(
                "",
                xy=(float(crow.iloc[0]["x"]) + attack_sign * 7, float(crow.iloc[0]["y"])),
                xytext=(float(crow.iloc[0]["x"]), float(crow.iloc[0]["y"])),
                arrowprops=dict(arrowstyle="->", color="#1B7F4E", lw=2.5),
                zorder=4,
            )

    # presser
    if presser_id is not None:
        prow = fp[fp["player_id"] == presser_id]
        if not prow.empty:
            ax.scatter(
                prow.iloc[0]["x"],
                prow.iloc[0]["y"],
                s=220,
                c="#C62828",
                marker="X",
                zorder=5,
                linewidths=2,
            )
            ax.text(
                prow.iloc[0]["x"],
                prow.iloc[0]["y"] + 2.8,
                "PRESSER",
                ha="center",
                fontsize=8,
                fontweight="bold",
                color="#C62828",
            )

    # ball
    fm = frame_meta[frame_meta["frame"] == frame]
    if not fm.empty and pd.notna(fm.iloc[0]["ball_x"]):
        ax.scatter(
            fm.iloc[0]["ball_x"],
            fm.iloc[0]["ball_y"],
            s=70,
            c="black",
            zorder=6,
        )

    ax.set_xlim(cx - 26, cx + 26)
    ax.set_ylim(cy - 18, cy + 18)


def plot_story_card(
    row: pd.Series,
    players: pd.DataFrame,
    frame_meta: pd.DataFrame,
    phases: pd.DataFrame,
    team_of: dict[int, int],
    meta: dict[str, Any],
    out_path: Path,
) -> tuple[str, str]:
    label, note = judge_press(row)
    style = VERDICT_STYLE[label]
    bullets = _story_bullets(row, label)

    frame0 = int(row["frame_start"])
    frame1 = frame0 + TAX_WINDOW_FRAMES
    carrier_id = (
        int(row["player_in_possession_id"])
        if pd.notna(row.get("player_in_possession_id"))
        else None
    )
    presser_id = int(row["player_id"]) if pd.notna(row.get("player_id")) else None
    carrier_team = team_of.get(carrier_id) if carrier_id is not None else None
    attack_sign = attacking_sign_for_frame(phases, frame0)

    cx = row.get("carrier_x0")
    cy = row.get("carrier_y0")
    if pd.isna(cx) or pd.isna(cy):
        fm = frame_meta[frame_meta["frame"] == frame0]
        cx = fm.iloc[0]["ball_x"] if not fm.empty else 0.0
        cy = fm.iloc[0]["ball_y"] if not fm.empty else 0.0
    center = (float(cx), float(cy))

    fig = plt.figure(figsize=(12, 8.2))
    # Verdict banner
    banner = FancyBboxPatch(
        (0.04, 0.86),
        0.92,
        0.11,
        transform=fig.transFigure,
        boxstyle="round,pad=0.02,rounding_size=0.02",
        facecolor=style["bg"],
        edgecolor=style["color"],
        linewidth=3,
        clip_on=False,
    )
    fig.patches.append(banner)
    fig.text(
        0.5,
        0.935,
        f"{row['review_id']}  ·  {style['title']}",
        ha="center",
        va="center",
        fontsize=22,
        fontweight="bold",
        color=style["color"],
    )
    fig.text(
        0.5,
        0.885,
        style["blurb"],
        ha="center",
        va="center",
        fontsize=12,
        color="#222222",
    )

    # Story bullets
    story = "\n".join(bullets)
    fig.text(
        0.06,
        0.82,
        story,
        ha="left",
        va="top",
        fontsize=13,
        family="sans-serif",
        linespacing=1.45,
    )

    # Before / after pitches
    ax0 = fig.add_axes([0.05, 0.08, 0.44, 0.48])
    ax1 = fig.add_axes([0.51, 0.08, 0.44, 0.48])
    _draw_mini(
        ax0, players, frame_meta, frame0, carrier_id, presser_id, team_of,
        carrier_team, attack_sign, meta, center,
    )
    _draw_mini(
        ax1, players, frame_meta, frame1, carrier_id, presser_id, team_of,
        carrier_team, attack_sign, meta, center,
    )
    ax0.set_title("BEFORE", fontsize=16, fontweight="bold", pad=10)
    ax1.set_title("AFTER (1 second)", fontsize=16, fontweight="bold", pad=10)

    # Big distance callouts under titles
    d0 = row.get("interplayer_distance_start")
    d1 = row.get("interplayer_distance_end")
    if pd.notna(d0):
        ax0.text(
            0.5,
            -0.08,
            f"Presser is {float(d0):.1f}m away",
            transform=ax0.transAxes,
            ha="center",
            fontsize=12,
            fontweight="bold",
        )
    if pd.notna(d1):
        ax1.text(
            0.5,
            -0.08,
            f"Presser is {float(d1):.1f}m away",
            transform=ax1.transAxes,
            ha="center",
            fontsize=12,
            fontweight="bold",
        )

    # Giant arrow between panels
    fig.text(0.485, 0.32, "→", ha="center", va="center", fontsize=28, color="#444444")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=160, facecolor="white")
    plt.close(fig)
    return label, note
