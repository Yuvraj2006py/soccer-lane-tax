"""Animated press GIF: pitch replay + four-beat story + possession timeline + live charts.

Blue = team on the ball when the press starts. Red = pressing team. Hollow dots are
players SkillCorner could not see on camera (estimated positions).
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import FancyBboxPatch
from mplsoccer import Pitch
from PIL import Image

from lane_tax.press_story import GRADE_STYLE, PRESS_TYPE_LABEL, MatchContext, PressStory

ATTACK_C = "#1E63B4"
PRESS_C = "#D7263D"
TRANSIT_C = "#D5D5D5"
FUTURE_C = "#BDBDBD"
PRE_FRAMES = 20
POST_RESOLUTION_FRAMES = 15
MAX_AFTER_PRESS_FRAMES = 135
FRAME_MS = 100
PITCH_AX = (0.01, 0.205, 0.60, 0.64)
END_MARK = {
    "won_by_presser": "WON BACK",
    "won_fast": "WON BACK",
    "won_late": "WON BACK",
    "forced_long_won": "WON BACK",
    "forced_out": "OUT",
    "shot_conceded": "SHOT",
    "foul_given": "FOUL",
}


def _window(story: PressStory) -> tuple[int, int]:
    start = story.frame0 - PRE_FRAMES
    end = max(story.resolution_frame + POST_RESOLUTION_FRAMES, story.frame0 + 30)
    return start, min(end, story.frame0 + MAX_AFTER_PRESS_FRAMES)


def _camera(ctx: MatchContext, story: PressStory, frames: range, aspect: float) -> tuple[float, float, float, float]:
    pts = [ctx.ball(f) for f in frames]
    for pid in (story.carrier_id, story.presser_id):
        p = ctx.xy(story.frame0, pid)
        if p:
            pts.append((p[0], p[1]))
    pts = [p for p in pts if p is not None]
    xs, ys = np.array([p[0] for p in pts]), np.array([p[1] for p in pts])
    half_l, half_w = ctx.meta["pitch_length"] / 2 + 4, ctx.meta["pitch_width"] / 2 + 4
    x0, x1 = xs.min() - 10, xs.max() + 10
    y0, y1 = ys.min() - 8, ys.max() + 8
    w = max(x1 - x0, 50.0)
    h = max(y1 - y0, w / aspect)
    w = max(w, h * aspect)
    if w >= 2 * half_l:
        w = 2 * half_l
        h = w / aspect
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    cx = float(np.clip(cx, -half_l + w / 2, half_l - w / 2))
    cy = float(np.clip(cy, -half_w + h / 2, half_w - h / 2)) if h < 2 * half_w else 0.0
    return cx - w / 2, cx + w / 2, cy - h / 2, cy + h / 2


def _holder(story: PressStory, frame: int) -> tuple[str, int | None, int | None]:
    for s in story.segments:
        if s.start_frame <= frame <= s.end_frame:
            return (s.label, s.player_id, s.team_id) if s.kind == "possession" else (s.label, None, None)
    return ("", None, None)


def _wrap(txt: str, width: int = 60) -> str:
    return textwrap.fill(txt, width=width)


def render_press_gif(ctx: MatchContext, story: PressStory, out_path: Path) -> Path:
    start, end = _window(story)
    frames = range(start, end + 1)
    style = GRADE_STYLE[story.grade]
    t = lambda f: (f - story.frame0) / 10.0  # noqa: E731

    sub = ctx.players[(ctx.players["frame"] >= start) & (ctx.players["frame"] <= end)]
    by_frame = {int(f): g for f, g in sub.groupby("frame")}

    fig = plt.figure(figsize=(14, 7.9), dpi=80, facecolor="white")

    # banner
    pstyle = GRADE_STYLE[story.presser_grade]
    fig.patches.append(FancyBboxPatch((0.008, 0.885), 0.984, 0.105, transform=fig.transFigure,
                                      boxstyle="round,pad=0.004,rounding_size=0.01",
                                      facecolor=pstyle["bg"], edgecolor=pstyle["color"], lw=2.5))
    fig.text(0.02, 0.955, f"{story.review_id}  ·  PRESSER: {story.credit}", fontsize=18, fontweight="bold",
             color=pstyle["color"], va="center")
    fig.text(0.02, 0.908,
             f"{story.presser_name} ({story.press_abbr}) on {story.carrier_name} ({story.attack_abbr})   ·   "
             f"setup: {PRESS_TYPE_LABEL.get(story.press_type, story.press_type)}",
             fontsize=11, color="#222222", va="center")
    fig.text(0.985, 0.958, "TEAM OUTCOME", color="#616161", fontsize=9.5, fontweight="bold", ha="right", va="center")
    fig.text(0.985, 0.915, story.outcome_title, color="white", fontsize=12, fontweight="bold", ha="right",
             va="center", bbox=dict(boxstyle="round,pad=0.3", fc=style["color"], ec="none"))

    # pitch
    ax = fig.add_axes(PITCH_AX)
    pitch = Pitch(pitch_type="skillcorner", pitch_length=ctx.meta["pitch_length"],
                  pitch_width=ctx.meta["pitch_width"], line_color="#9E9E9E", pitch_color="#F7F7F2", linewidth=1.2)
    pitch.draw(ax=ax)
    aspect = (PITCH_AX[2] * 14) / (PITCH_AX[3] * 7.9)
    x0, x1, y0, y1 = _camera(ctx, story, frames, aspect)
    ax.set_xlim(x0, x1)
    ax.set_ylim(y0, y1)
    arrow = "→" if story.attack_sign > 0 else "←"
    ax.set_title(f"{story.attack_abbr} attacking {arrow}", fontsize=11.5, fontweight="bold", color=ATTACK_C, pad=4)
    ax.text(0.0, 1.012, f"● {story.attack_abbr} on the ball", transform=ax.transAxes, color=ATTACK_C,
            fontsize=10.5, fontweight="bold", ha="left", va="bottom")
    ax.text(1.0, 1.012, f"◆ {story.press_abbr} pressing", transform=ax.transAxes, color=PRESS_C,
            fontsize=10.5, fontweight="bold", ha="right", va="bottom")

    att_sc = ax.scatter([], [], s=70, zorder=4, linewidths=1.6)
    prs_sc = ax.scatter([], [], s=70, zorder=4, linewidths=1.6)
    halo = ax.scatter([], [], s=520, facecolors="none", edgecolors="#F9A825", linewidths=3, zorder=5)
    carrier_sc = ax.scatter([], [], s=230, c=ATTACK_C, edgecolors="white", linewidths=2, zorder=6)
    presser_sc = ax.scatter([], [], s=260, c=PRESS_C, edgecolors="black", linewidths=1.8, zorder=6, marker="D")
    ball_sc = ax.scatter([], [], s=120, c="#FFEB3B", edgecolors="black", linewidths=1.6, zorder=9)
    (ball_trail,) = ax.plot([], [], color="#212121", lw=2.4, alpha=0.55, zorder=7)
    (presser_trail,) = ax.plot([], [], color=PRESS_C, lw=2, alpha=0.45, zorder=3)
    (link,) = ax.plot([], [], color=PRESS_C, ls="--", lw=1.6, zorder=5)
    link_txt = ax.text(0, 0, "", fontsize=10, fontweight="bold", color=PRESS_C, zorder=10, clip_on=True,
                       bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none", alpha=0.85))
    carrier_lbl = ax.text(0, 0, story.carrier_name, fontsize=10, fontweight="bold", color=ATTACK_C, ha="center", zorder=10, clip_on=True)
    presser_lbl = ax.text(0, 0, story.presser_name, fontsize=10, fontweight="bold", color=PRESS_C, ha="left",
                          va="center", zorder=10, clip_on=True,
                          bbox=dict(boxstyle="round,pad=0.12", fc="white", ec="none", alpha=0.8))
    holder_lbl = ax.text(0, 0, "", fontsize=10, fontweight="bold", color="#5D4037", ha="center", zorder=10, clip_on=True,
                         bbox=dict(boxstyle="round,pad=0.15", fc="#FFF8E1", ec="#F9A825"))
    status = ax.text(0.012, 0.03, "", transform=ax.transAxes, fontsize=11.5, fontweight="bold", va="bottom",
                     zorder=12, bbox=dict(boxstyle="round,pad=0.35", fc="white", ec="#616161", alpha=0.95))
    ax.text(0.99, 0.03, "hollow = off camera (estimated)", transform=ax.transAxes, ha="right", va="bottom",
            fontsize=8.5, color="#757575", zorder=12)
    release_mk = ax.scatter([], [], s=150, facecolors="none", edgecolors="#212121", linewidths=2, zorder=8)
    release_txt = ax.text(0, 0, "", fontsize=9, color="#212121", ha="center", zorder=10, clip_on=True)
    end_mk = ax.scatter([], [], s=420, marker="*", c=style["color"], edgecolors="white", linewidths=1.2, zorder=11)
    end_txt = ax.text(0, 0, "", fontsize=10, fontweight="bold", color=style["color"], ha="center", zorder=11, clip_on=True)

    # story panel
    sax = fig.add_axes([0.625, 0.34, 0.365, 0.53])
    sax.axis("off")
    beat_artists = []
    y = 0.99
    for i, (title, bframe, txt) in enumerate(story.beats()):
        h = sax.text(0.0, y, f"{i + 1}. {title}  (t={t(bframe):+.1f}s)" if i else f"{i + 1}. {title}",
                     fontsize=11.5, fontweight="bold", va="top", color=FUTURE_C)
        body = _wrap(txt, 68)
        b = sax.text(0.02, y - 0.055, body, fontsize=9.3, va="top", color=FUTURE_C, linespacing=1.25)
        beat_artists.append((bframe, h, b, i == 3))
        y -= 0.055 + 0.05 * (body.count("\n") + 1) + 0.035
    credit_txt = sax.text(0.0, max(y, 0.02), _wrap(f"PRESSER: {story.credit} — {story.credit_detail}", 64),
                          fontsize=9.5, fontweight="bold", va="top", color=pstyle["color"], visible=False,
                          bbox=dict(boxstyle="round,pad=0.35", fc=pstyle["bg"], ec=pstyle["color"]))

    # live charts
    ts = np.array([t(f) for f in frames])
    dist = np.array([ctx.dist(f, story.presser_id, story.carrier_id) if f <= story.release_frame else np.nan
                     for f in frames], dtype=float)
    b0 = ctx.ball_filled(story.frame0)
    prog = []
    for f in frames:
        ff = min(f, story.resolution_frame)
        b = ctx.ball_filled(ff)
        prog.append((b[0] - b0[0]) * story.attack_sign if (b and b0 and f >= story.frame0) else np.nan)
    prog = np.array(prog, dtype=float)

    dax = fig.add_axes([0.665, 0.20, 0.32, 0.10])
    dax.plot(ts, dist, color=PRESS_C, alpha=0.18, lw=2)
    (dline,) = dax.plot([], [], color=PRESS_C, lw=2.4)
    dax.axhline(2.0, color="#9E9E9E", ls=":", lw=1)
    dax.set_ylabel("presser\ngap (m)", fontsize=9)
    dax.set_xlim(ts[0], ts[-1])
    finite = dist[np.isfinite(dist)]
    dax.set_ylim(0, max(10.0, float(finite.max()) + 1) if finite.size else 10)
    dax.tick_params(labelsize=8, labelbottom=False)
    dcur = dax.axvline(ts[0], color="#424242", lw=1)

    pax = fig.add_axes([0.665, 0.075, 0.32, 0.10])
    pax.axhline(0, color="#616161", lw=1)
    pax.plot(ts, prog, color=ATTACK_C, alpha=0.18, lw=2)
    (pline,) = pax.plot([], [], color=ATTACK_C, lw=2.4)
    pax.set_ylabel(f"ball gain\nfor {story.attack_abbr} (m)", fontsize=9)
    pax.set_xlim(ts[0], ts[-1])
    pf = prog[np.isfinite(prog)]
    lim = max(12.0, float(np.abs(pf).max()) + 3) if pf.size else 12.0
    pax.set_ylim(-lim, lim)
    pax.axhspan(0, lim, color=PRESS_C, alpha=0.05)
    pax.axhspan(-lim, 0, color="#2E7D32", alpha=0.06)
    pax.text(ts[0] + 0.1, lim * 0.7, "attack gaining", fontsize=8, color=PRESS_C)
    pax.text(ts[0] + 0.1, -lim * 0.85, "pushed back", fontsize=8, color="#2E7D32")
    pax.set_xlabel("seconds from press start", fontsize=9)
    pax.tick_params(labelsize=8)
    pcur = pax.axvline(ts[0], color="#424242", lw=1)

    # possession timeline
    tax = fig.add_axes([0.03, 0.085, 0.565, 0.075])
    for s in story.segments:
        a, b = max(s.start_frame, start), min(s.end_frame, end)
        if b < a:
            continue
        col = TRANSIT_C if s.kind == "transit" else (ATTACK_C if s.team_id == story.attack_team_id else PRESS_C)
        tax.broken_barh([(t(a), t(b + 1) - t(a))], (0, 1), facecolors=col, edgecolors="white", lw=1)
        if s.kind == "possession" and (b - a) >= 9:
            tax.text((t(a) + t(b + 1)) / 2, 0.5, s.label.split(" (")[0], ha="center", va="center", fontsize=8.5,
                     color="white", fontweight="bold", clip_on=True)
    last_lab_t = -np.inf
    for f, lab in ((story.frame0, "press"), (story.release_frame, "release"), (story.resolution_frame, "outcome")):
        if start <= f <= end:
            tax.axvline(t(f), color="#212121", lw=1.2, ls=":")
            if t(f) - last_lab_t >= 0.6:
                tax.text(t(f), 1.12, lab, ha="center", fontsize=8.5, color="#212121")
                last_lab_t = t(f)
    tax.set_xlim(ts[0], ts[-1] + 0.1)
    tax.set_ylim(0, 1)
    tax.set_yticks([])
    tax.tick_params(labelsize=8)
    tax.set_title("who has the ball  (blue = attack · red = pressing team · grey = ball travelling / loose / dead)",
                  fontsize=9, loc="left", pad=12)
    tcur = tax.axvline(ts[0], color="black", lw=2.5)

    checks = "   ".join(("✓ " if ok else "⚠ ") + f"{name}: {detail}" for name, ok, detail in story.checks)
    fig.text(0.01, 0.012, f"data checks  {checks}", fontsize=8, color="#616161")

    ball_hist: list[tuple[float, float]] = []
    pres_hist: list[tuple[float, float]] = []
    images: list[Image.Image] = []
    durations: list[int] = []

    for f in frames:
        g = by_frame.get(f)
        if g is not None:
            tids = g["player_id"].map(ctx.team_of).to_numpy()
            xy = g[["x", "y"]].to_numpy(dtype=float)
            det = g["is_detected"].to_numpy(dtype=bool)
            for sc, tid, col in ((att_sc, story.attack_team_id, ATTACK_C), (prs_sc, story.press_team_id, PRESS_C)):
                m = tids == tid
                sc.set_offsets(xy[m] if m.any() else np.empty((0, 2)))
                fc = np.array([matplotlib.colors.to_rgba(col, 0.9 if d else 0.0) for d in det[m]]).reshape(-1, 4)
                sc.set_facecolors(fc)
                sc.set_edgecolors(col)

        c = ctx.xy(f, story.carrier_id)
        p = ctx.xy(f, story.presser_id)
        bl = ctx.ball(f)
        carrier_sc.set_offsets([c[:2]] if c else np.empty((0, 2)))
        presser_sc.set_offsets([p[:2]] if p else np.empty((0, 2)))
        presser_sc.set_facecolors([PRESS_C if (p and p[2]) else "white"])
        if c:
            carrier_lbl.set_position((c[0], c[1] + 2.4))
        if p:
            presser_lbl.set_position((p[0] + 1.6, p[1] - 0.6))
            pres_hist.append(p[:2])
            presser_trail.set_data(*zip(*pres_hist[-20:]))
        if bl:
            ball_sc.set_offsets([bl])
            if f >= story.frame0:
                ball_hist.append(bl)
        if len(ball_hist) > 1:
            ball_trail.set_data(*zip(*ball_hist))

        pressing = story.frame0 <= f <= story.release_frame
        if pressing and c and p:
            link.set_data([p[0], c[0]], [p[1], c[1]])
            d = float(np.hypot(p[0] - c[0], p[1] - c[1]))
            link_txt.set_text(f"{d:.1f}m")
            link_txt.set_position(((p[0] + c[0]) / 2 + 0.6, (p[1] + c[1]) / 2 + 0.6))
        else:
            link.set_data([], [])
            link_txt.set_text("")

        label, hpid, htid = _holder(story, f)
        hxy = ctx.xy(f, hpid) if hpid is not None else None
        if hxy:
            halo.set_offsets([hxy[:2]])
            show_lbl = hpid not in (story.carrier_id, story.presser_id)
            holder_lbl.set_text(label.split(" (")[0] if show_lbl else "")
            holder_lbl.set_position((hxy[0], hxy[1] + 2.6))
        else:
            halo.set_offsets(np.empty((0, 2)))
            holder_lbl.set_text("")

        if f == story.release_frame and c:
            release_mk.set_offsets([c[:2]])
            release_txt.set_text("ball released")
            release_txt.set_position((c[0], c[1] - 3.6))
        if f == story.resolution_frame:
            winner = ctx.xy(f, story.regain_player_id) if story.regain_player_id is not None else None
            ex = winner[:2] if winner else ctx.ball_filled(f)
            mark = END_MARK.get(story.outcome)
            if ex and mark:
                end_mk.set_offsets([ex])
                end_txt.set_text(mark)
                end_txt.set_position((ex[0], ex[1] + 3.2))

        if f < story.frame0:
            phase = "BEFORE THE PRESS"
        elif f <= story.release_frame:
            dd = ctx.dist(f, story.presser_id, story.carrier_id)
            phase = f"PRESS ON — {story.presser_name} closing" + (f" ({dd:.1f}m)" if dd is not None else "")
        elif f < story.resolution_frame:
            phase = f"AFTERMATH — {label or 'ball travelling'}"
        else:
            phase = f"TEAM OUTCOME — {story.outcome_title.split(' —')[0]}"
        status.set_text(f"t = {t(f):+.1f}s   {phase}")
        done = f >= story.resolution_frame
        status.set_color("white" if done else "#212121")
        status.get_bbox_patch().set_facecolor(style["color"] if done else "white")

        for bframe, h, b, is_outcome in beat_artists:
            on = f >= bframe
            h.set_color((style["color"] if is_outcome else "#212121") if on else FUTURE_C)
            b.set_color("#212121" if on else FUTURE_C)
        credit_txt.set_visible(f >= story.resolution_frame)

        k = f - start + 1
        dline.set_data(ts[:k], dist[:k])
        pline.set_data(ts[:k], prog[:k])
        for cur in (dcur, pcur, tcur):
            cur.set_xdata([t(f), t(f)])

        fig.canvas.draw()
        img = Image.fromarray(np.asarray(fig.canvas.buffer_rgba())[..., :3])
        images.append(img.quantize(colors=160, method=Image.Quantize.MEDIANCUT))
        hold = 0
        if f == start:
            hold = 1200
        elif f in (story.frame0, story.release_frame):
            hold = 700
        elif f == story.resolution_frame:
            hold = 1200
        durations.append(FRAME_MS + hold)
    durations[-1] = 3500
    plt.close(fig)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    images[0].save(out_path, save_all=True, append_images=images[1:], duration=durations, loop=0)
    return out_path
