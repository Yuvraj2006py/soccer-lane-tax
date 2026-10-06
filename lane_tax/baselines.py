"""Baseline press features the Lane Tax has to beat.

Every baseline is oriented so that *higher = more pressing pressure* (distances are negated),
which lets validation compare them all with the same AUC.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd

from lane_tax.config import DEFENDERS_WITHIN_RADIUS_M
from lane_tax.metric import Scene

SC_PRESSURE_ORDINAL = {
    "no_pressure": 0, "low_pressure": 1, "medium_pressure": 2, "high_pressure": 3, "very_high_pressure": 4,
}
SC_EASE_ORDINAL = {"very_easy": 0, "easy": 1, "medium": 2, "hard": 3, "very_hard": 4}


@dataclass
class Baselines:
    presser_gap_m: float | None
    nearest_opponent_m: float | None
    opponents_within_5m: int
    presser_closing_speed: float
    presser_time_to_carrier_s: float | None
    sc_pressure: float | None
    sc_option_ease: float | None
    sc_n_passing_options: float | None
    sc_n_options_ahead: float | None

    def as_scores(self) -> dict[str, float | None]:
        """Each baseline as a 'more pressure = higher' score."""
        neg = lambda v: None if v is None else -float(v)  # noqa: E731
        return {
            "b_presser_gap": neg(self.presser_gap_m),
            "b_nearest_opponent": neg(self.nearest_opponent_m),
            "b_opponents_within_5m": float(self.opponents_within_5m),
            "b_closing_speed": self.presser_closing_speed,
            "b_presser_time": neg(self.presser_time_to_carrier_s),
            "b_sc_pressure": self.sc_pressure,
            "b_sc_option_ease": self.sc_option_ease,
            "b_sc_fewer_options": neg(self.sc_n_passing_options),
            "b_sc_fewer_options_ahead": neg(self.sc_n_options_ahead),
        }

    def to_dict(self) -> dict:
        return asdict(self)


def _num(v) -> float | None:
    return None if v is None or pd.isna(v) else float(v)


def compute_baselines(
    scene: Scene, p0: pd.Series, closing_speed: float, presser_time_s: float | None
) -> Baselines:
    c = np.array([scene.carrier.x, scene.carrier.y])
    d = np.array([np.hypot(o.x - c[0], o.y - c[1]) for o in scene.defenders]) if scene.defenders else np.array([])
    gap = None if scene.presser_idx is None else float(d[scene.presser_idx])
    return Baselines(
        presser_gap_m=gap,
        nearest_opponent_m=float(d.min()) if d.size else None,
        opponents_within_5m=int((d <= DEFENDERS_WITHIN_RADIUS_M).sum()),
        presser_closing_speed=float(closing_speed),
        presser_time_to_carrier_s=presser_time_s,
        sc_pressure=_num(SC_PRESSURE_ORDINAL.get(str(p0.get("overall_pressure_start")))),
        sc_option_ease=_num(SC_EASE_ORDINAL.get(str(p0.get("passing_option_ease_start")))),
        sc_n_passing_options=_num(p0.get("n_passing_options")),
        sc_n_options_ahead=_num(p0.get("n_passing_options_ahead")),
    )
