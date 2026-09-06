"""Run a multi-arm, multi-seed campaign and aggregate it.

Common random numbers: arm ``a`` and arm ``b`` at seed ``s`` see the same
household and firm draws, so contrasts are paired. See
:mod:`cdos.eval.uncertainty` for what the resulting intervals do and do not
mean.
"""

from __future__ import annotations

import itertools
import os
import warnings
from collections.abc import Sequence
from typing import Any

import numpy as np

from ..config import Config
from ..model.economy import ARMS, run
from .uncertainty import bootstrap_ci, holm_bonferroni, paired_contrast

__all__ = ["run_campaign", "aggregate", "AGG_KEYS", "PAIRED_KEYS"]

AGG_KEYS = ("Y", "eff_units", "headcount", "ws", "ws_end", "gi", "gw", "pov",
            "taul", "taul_cv", "fund", "divgdp", "adopt", "sac", "rev_cv",
            "dwl", "revenue", "revenue_per_dwl", "spend", "wage",
            "g_realised", "stability_margin", "leakage", "incidence_labour",
            "incidence_capital")

PAIRED_KEYS = ("Y", "eff_units", "headcount", "gi", "gw", "pov", "taul",
               "ws_end", "dwl", "revenue_per_dwl", "wage")


def _job(args: tuple[Config, int, str]) -> dict[str, Any]:
    cfg, seed, arm = args
    with warnings.catch_warnings():
        # Fund-stability warnings are recorded per run as `stability_margin`;
        # re-emitting one per worker would bury the campaign output.
        warnings.simplefilter("ignore", RuntimeWarning)
        return run(cfg, seed, arm)


def run_campaign(cfg: Config, arms: Sequence[str] = ARMS,
                 seeds: Sequence[int] = range(50),
                 processes: int | None = None) -> list[dict[str, Any]]:
    """Execute every (seed, arm) pair. Returns the raw per-run results."""
    unknown = [a for a in arms if a not in ARMS]
    if unknown:
        raise ValueError(f"unknown arms {unknown}; known arms are {list(ARMS)}")
    tasks = [(cfg, s, a) for s, a in itertools.product(seeds, arms)]
    if processes is None:
        processes = max(1, min(16, (os.cpu_count() or 2)))
    if processes <= 1 or len(tasks) < 4:
        return [_job(t) for t in tasks]
    from multiprocessing import Pool
    with Pool(processes=processes) as pool:
        return pool.map(_job, tasks, chunksize=4)


def aggregate(results: Sequence[dict[str, Any]], arms: Sequence[str],
              seeds: Sequence[int], baseline: str = "B0",
              reps: int = 2000, seed: int = 12345) -> dict[str, Any]:
    """Aggregate per-run results into per-arm statistics and paired contrasts.

    Adds Holm-corrected significance across arms for each paired metric: the
    audited campaign compared seven arms against a baseline on seven metrics
    without any multiplicity control.
    """
    by: dict[str, list[dict[str, Any]]] = {
        a: [r for r in results if r["arm"] == a] for a in arms}
    for a in arms:
        if len(by[a]) != len(seeds):
            raise ValueError(
                f"arm {a} has {len(by[a])} runs but {len(seeds)} seeds were "
                "requested; the campaign is not balanced and contrasts would "
                "not be paired")
        by[a].sort(key=lambda r: r["seed"])

    agg: dict[str, Any] = {}
    for a in arms:
        agg[a] = {}
        for k in AGG_KEYS:
            if k not in by[a][0]:
                continue
            v = np.array([r[k] for r in by[a]], dtype=float)
            ci = bootstrap_ci(v, reps, seed, kind="replication")
            agg[a][k] = {"mean": float(v.mean()),
                         "sd": float(v.std(ddof=1)) if v.size > 1 else 0.0,
                         "lo": ci.lo, "hi": ci.hi, "kind": ci.kind}

    if baseline not in by:
        raise ValueError(f"baseline arm {baseline!r} was not run")

    for a in arms:
        agg[a]["_paired"] = {}
        for k in PAIRED_KEYS:
            if k not in by[a][0]:
                continue
            t = [by[a][i][k] for i in range(len(seeds))]
            c = [by[baseline][i][k] for i in range(len(seeds))]
            contrast = paired_contrast(t, c, reps, seed, relative=True)
            agg[a]["_paired"][k] = {
                "diff": contrast["diff"]["point"],
                "lo": contrast["diff"]["lo"], "hi": contrast["diff"]["hi"],
                "kind": contrast["diff"]["kind"],
                "effect_size": contrast["effect_size"],
                "pct": contrast.get("pct", {}).get("point", 0.0),
                "plo": contrast.get("pct", {}).get("lo", 0.0),
                "phi": contrast.get("pct", {}).get("hi", 0.0),
            }

    # Multiplicity control across arms, per metric.
    agg["_multiplicity"] = {}
    for k in PAIRED_KEYS:
        pvals = {}
        for a in arms:
            if a == baseline or k not in agg[a].get("_paired", {}):
                continue
            d = np.array([by[a][i][k] - by[baseline][i][k]
                          for i in range(len(seeds))], dtype=float)
            pvals[a] = _paired_permutation_p(d, seed)
        if pvals:
            agg["_multiplicity"][k] = holm_bonferroni(pvals)

    agg["_meta"] = {
        "baseline": baseline, "arms": list(arms), "seeds": list(seeds),
        "bootstrap_reps": reps, "bootstrap_seed": seed,
        "uncertainty_note": (
            "All intervals are REPLICATION uncertainty under common random "
            "numbers: bootstrap over seeds at one fixed parameter vector. They "
            "do not quantify parameter or structural uncertainty. See E1 for "
            "the sigma-gamma sweep, which is where structural uncertainty is "
            "measured."),
    }
    return agg


def _paired_permutation_p(diff: np.ndarray, seed: int, reps: int = 10000
                          ) -> float:
    """Two-sided sign-flip permutation test on paired differences.

    Exact under the sharp null of no treatment effect at any seed, which is the
    right null for a paired simulation contrast, and it makes no normality
    assumption -- the paired differences under CRN are not remotely normal.
    """
    d = np.asarray(diff, dtype=float)
    observed = abs(float(d.mean()))
    if observed == 0.0:
        return 1.0
    rng = np.random.default_rng(seed)
    signs = rng.choice((-1.0, 1.0), size=(reps, d.size))
    null = np.abs((signs * d).mean(axis=1))
    return float((np.sum(null >= observed) + 1) / (reps + 1))
