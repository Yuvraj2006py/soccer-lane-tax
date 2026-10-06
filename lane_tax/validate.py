"""Validation helpers: rank AUC with bootstrap intervals, and leave-one-match-out scaffolding.

AUC here = probability that a randomly picked positive press scores higher than a randomly picked
negative one (0.5 = coin flip). Every score is oriented "higher = more pressing pressure".
"""

from __future__ import annotations

from collections.abc import Iterable

import numpy as np
import pandas as pd
from scipy.stats import rankdata, spearmanr

BOOTSTRAP_N = 1000
SEED = 7


def auc(score: Iterable[float], y: Iterable[int]) -> float | None:
    s, t = np.asarray(list(score), float), np.asarray(list(y), float)
    ok = ~(np.isnan(s) | np.isnan(t))
    s, t = s[ok], t[ok].astype(int)
    n1, n0 = int(t.sum()), int((1 - t).sum())
    if n1 == 0 or n0 == 0:
        return None
    r = rankdata(s)
    return float((r[t == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def auc_ci(score: pd.Series, y: pd.Series, n: int = BOOTSTRAP_N, seed: int = SEED) -> tuple[float | None, float, float]:
    df = pd.DataFrame({"s": pd.to_numeric(score, errors="coerce"), "y": pd.to_numeric(y, errors="coerce")}).dropna()
    point = auc(df["s"], df["y"])
    if point is None:
        return None, np.nan, np.nan
    rng = np.random.default_rng(seed)
    idx = np.arange(len(df))
    boots = []
    for _ in range(n):
        b = df.iloc[rng.choice(idx, len(idx))]
        a = auc(b["s"], b["y"])
        if a is not None:
            boots.append(a)
    lo, hi = np.percentile(boots, [2.5, 97.5]) if boots else (np.nan, np.nan)
    return point, float(lo), float(hi)


def paired_auc_gain(a: pd.Series, b: pd.Series, y: pd.Series, n: int = BOOTSTRAP_N, seed: int = SEED) -> tuple[float, float, float]:
    """AUC(a) - AUC(b) on the same presses, with a paired bootstrap interval."""
    df = pd.DataFrame({"a": pd.to_numeric(a, errors="coerce"), "b": pd.to_numeric(b, errors="coerce"),
                       "y": pd.to_numeric(y, errors="coerce")}).dropna()
    if df.empty:
        return np.nan, np.nan, np.nan
    pa, pb = auc(df["a"], df["y"]), auc(df["b"], df["y"])
    if pa is None or pb is None:
        return np.nan, np.nan, np.nan
    rng = np.random.default_rng(seed)
    idx = np.arange(len(df))
    diffs = []
    for _ in range(n):
        bs = df.iloc[rng.choice(idx, len(idx))]
        x, z = auc(bs["a"], bs["y"]), auc(bs["b"], bs["y"])
        if x is not None and z is not None:
            diffs.append(x - z)
    lo, hi = np.percentile(diffs, [2.5, 97.5]) if diffs else (np.nan, np.nan)
    return pa - pb, float(lo), float(hi)


def auc_table(df: pd.DataFrame, scores: list[str], labels: list[str]) -> pd.DataFrame:
    rows = []
    for lab in labels:
        sub = df[df[lab].notna()]
        n1 = int(sub[lab].sum())
        for sc in scores:
            point, lo, hi = auc_ci(sub[sc], sub[lab])
            rows.append({"label": lab, "score": sc, "n": len(sub), "positives": n1,
                         "auc": point, "ci_lo": lo, "ci_hi": hi})
    return pd.DataFrame(rows)


def spearman(a: pd.Series, b: pd.Series) -> tuple[float, int]:
    df = pd.DataFrame({"a": pd.to_numeric(a, errors="coerce"), "b": pd.to_numeric(b, errors="coerce")}).dropna()
    if len(df) < 3:
        return np.nan, len(df)
    return float(spearmanr(df["a"], df["b"]).statistic), len(df)


def leave_one_match_out(df: pd.DataFrame, score: str, label: str, match_col: str = "match_id") -> pd.DataFrame:
    """Phase 3: per held-out match AUC. The metric has no fitted parameters, so LOMO here just guards
    against one match driving the result; any future calibrated model must be fit on the other matches."""
    rows = []
    for mid, g in df.groupby(match_col):
        rows.append({"match_id": mid, "n": len(g), "auc": auc(g[score], g[label])})
    return pd.DataFrame(rows)
