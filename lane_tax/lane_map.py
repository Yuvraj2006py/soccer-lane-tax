"""Lane map: the carrier's ways out at the moment he chooses, with and without the presser.

Left panel = reality. Right panel = the same frame with the presser deleted. Each line is an
option (solid = pass, dotted = carry); colour = how open it is, width = what it is worth.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
from mplsoccer import Pitch

from lane_tax.metric import Scene, TaxResult

ATTACK_C = "#1E63B4"
PRESS_C = "#D7263D"
OPEN_CMAP = LinearSegmentedColormap.from_list("open", ["#B0B0B0", "#F4A261", "#2A9D8F"])


def _zoom(scene: Scene, res: TaxResult) -> tuple[float, float, float, float]:
    xs = [scene.carrier.x] + [o.end[0] for o in res.options if not o.offside]
    ys = [scene.carrier.y] + [o.end[1] for o in res.options if not o.offside]
    x0, x1 = min(xs) - 8, max(xs) + 8
    y0, y1 = min(ys) - 6, max(ys) + 6
    hl, hw = scene.half_length + 3, scene.half_width + 3
    return max(x0, -hl), min(x1, hl), max(y0, -hw), min(y1, hw)


def _panel(ax, pitch: Pitch, scene: Scene, res: TaxResult, without_presser: bool) -> None:
    pitch.draw(ax=ax)
    p = scene.presser_idx
    for o in sorted(res.options, key=lambda o: o.escape):
        if o.offside:
            continue
        op = o.open_prob(p if without_presser else None, rush=not without_presser)
        colour = OPEN_CMAP(op) if o.escape else "#DDDDDD"
        width = 1.0 + 2.5 * min(o.value, 1.5) if o.escape else 0.8
        ax.plot([o.start[0], o.end[0]], [o.start[1], o.end[1]], color=colour, lw=width,
                ls="-" if o.kind == "pass" else ":", alpha=0.9, zorder=2, solid_capstyle="round")
    for pl in scene.teammates:
        ax.scatter(pl.x, pl.y, s=70, color=ATTACK_C if pl.detected else "white", edgecolors=ATTACK_C, zorder=4)
    for i, pl in enumerate(scene.defenders):
        if without_presser and i == p:
            ax.scatter(pl.x, pl.y, s=160, marker="D", facecolors="none", edgecolors=PRESS_C, ls="--", zorder=4)
            continue
        is_p = i == p
        ax.scatter(pl.x, pl.y, s=160 if is_p else 70, marker="D" if is_p else "o",
                   color=PRESS_C if pl.detected else "white", edgecolors=PRESS_C, zorder=4)
        if is_p:
            ax.arrow(pl.x, pl.y, pl.vx * 0.6, pl.vy * 0.6, color=PRESS_C, width=0.12, head_width=0.8, zorder=5)
    c = scene.carrier
    ax.scatter(c.x, c.y, s=180, color=ATTACK_C, edgecolors="#FFD23F", linewidths=2.5, zorder=6)
    if abs(c.vx) + abs(c.vy) > 0.5:
        ax.arrow(c.x, c.y, c.vx * 0.6, c.vy * 0.6, color=ATTACK_C, width=0.12, head_width=0.8, zorder=6)


def render_lane_map(scene: Scene, res: TaxResult, title: str, subtitle: str, out_path: Path) -> Path:
    pitch = Pitch(pitch_type="skillcorner", pitch_length=scene.half_length * 2, pitch_width=scene.half_width * 2,
                  line_color="#9E9E9E", pitch_color="#F7F7F2", linewidth=1.0)
    x0, x1, y0, y1 = _zoom(scene, res)
    fig, axs = plt.subplots(1, 2, figsize=(14, 6.4))
    _panel(axs[0], pitch, scene, res, without_presser=False)
    _panel(axs[1], pitch, scene, res, without_presser=True)
    for ax, t in zip(axs, (f"REALITY — best way out {res.escape:.2f}",
                           f"PRESSER DELETED — best way out {res.escape_no_presser:.2f}")):
        ax.set_xlim(x0, x1)
        ax.set_ylim(y0, y1)
        ax.set_title(t, fontsize=12, fontweight="bold")
    arrow = "->" if scene.attack_sign > 0 else "<-"
    fig.suptitle(f"{title}\n{subtitle}", fontsize=13, fontweight="bold", y=0.99)
    fig.text(0.5, 0.015,
             f"Lane Tax {res.lane_tax:.2f} (block {res.lane_tax_block:.2f}, rush {res.lane_tax_rush:.2f}) · "
             f"unit tax {res.unit_tax:.2f} · lanes cut {res.lanes_cut:.2f} · attack {arrow} · "
             "line colour: grey = shut, teal = open · solid = pass, dotted = carry · hollow = off camera",
             ha="center", fontsize=9.5, color="#444444")
    sm = plt.cm.ScalarMappable(cmap=OPEN_CMAP, norm=plt.Normalize(0, 1))
    cb = fig.colorbar(sm, ax=axs, fraction=0.015, pad=0.01)
    cb.set_label("chance the option is on")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=110, bbox_inches="tight")
    plt.close(fig)
    return out_path
