"""Uncertainty, paired contrasts, and multiplicity control.

The distinction this module exists to enforce
---------------------------------------------
Common random numbers make arm contrasts paired, which removes almost all the
Monte-Carlo noise from a difference. The audited campaign reported the resulting
bootstrap intervals -- some of them a few parts in ten thousand wide -- without
saying what they were intervals *about*. They are intervals about the
**replication** uncertainty of the model's own output at one parameter vector.
They say nothing whatever about whether the parameter vector is right.

Under CRN a tight interval is a statement that the simulation is reproducible,
not that the policy conclusion is certain. The audit's F1 finding is the proof:
B6c's output effect sits at +2.21% with a CRN interval barely wider than the
line thickness, and it goes to -14.8% when sigma moves from 1.5 to 3.0 -- a
change entirely outside what any replication interval can see.

So every reported quantity carries a labelled uncertainty *kind*:

* ``"replication"`` -- bootstrap over seeds at a fixed parameter vector.
* ``"structural"``  -- spread across a parameter sweep or ensemble.

:func:`combined_interval` reports both and refuses to merge them into one
number, because they answer different questions.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

import numpy as np

__all__ = ["Interval", "bootstrap_ci", "paired_contrast", "effect_size",
           "holm_bonferroni", "combined_interval", "practical_significance",
           "seed_adequacy"]


@dataclass(frozen=True)
class Interval:
    point: float
    lo: float
    hi: float
    kind: str            # "replication" or "structural"
    n: int

    def as_dict(self) -> Dict[str, Any]:
        return {"point": self.point, "lo": self.lo, "hi": self.hi,
                "kind": self.kind, "n": self.n}

    def __str__(self) -> str:
        return f"{self.point:+.4f} [{self.lo:+.4f}, {self.hi:+.4f}] ({self.kind})"


def bootstrap_ci(x: Sequence[float], reps: int = 2000, seed: int = 12345,
                 alpha: float = 0.05, kind: str = "replication") -> Interval:
    """Percentile bootstrap of the mean.

    ``kind`` must be stated by the caller and is carried into the result, so
    that a replication interval can never be silently reported as if it
    quantified parameter uncertainty.
    """
    if kind not in ("replication", "structural"):
        raise ValueError(f"uncertainty kind must be 'replication' or "
                         f"'structural', got {kind!r}")
    arr = np.asarray(x, dtype=float)
    if arr.size == 0:
        raise ValueError("cannot bootstrap an empty sample")
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, arr.size, size=(reps, arr.size))
    means = arr[idx].mean(axis=1)
    return Interval(point=float(arr.mean()),
                    lo=float(np.percentile(means, 100 * alpha / 2)),
                    hi=float(np.percentile(means, 100 * (1 - alpha / 2))),
                    kind=kind, n=arr.size)


def paired_contrast(treatment: Sequence[float], control: Sequence[float],
                    reps: int = 2000, seed: int = 12345,
                    relative: bool = False) -> Dict[str, Any]:
    """Paired difference under common random numbers.

    Pairing is what makes the contrast precise; it is also what makes the
    resulting interval a statement about replication only.
    """
    t = np.asarray(treatment, dtype=float)
    c = np.asarray(control, dtype=float)
    if t.shape != c.shape:
        raise ValueError(
            f"paired contrast needs matched samples; got {t.shape} and {c.shape}. "
            "Under common random numbers the i-th entry of each arm must come "
            "from the same seed.")
    diff = t - c
    out: Dict[str, Any] = {
        "diff": bootstrap_ci(diff, reps, seed, kind="replication").as_dict(),
        "effect_size": effect_size(t, c),
        "n_pairs": int(t.size),
    }
    if relative:
        rel = 100.0 * (t / np.where(c == 0, np.nan, c) - 1.0)
        rel = rel[np.isfinite(rel)]
        if rel.size:
            out["pct"] = bootstrap_ci(rel, reps, seed, kind="replication").as_dict()
        else:
            # The control is zero for every seed, so a percentage change is not
            # defined. Reporting zero here would be a claim of no effect; the
            # absolute contrast above is the one to read.
            out["pct"] = {"point": float("nan"), "lo": float("nan"),
                          "hi": float("nan"), "kind": "replication", "n": 0,
                          "undefined_reason": "control is zero for every seed"}
    return out


def effect_size(treatment: Sequence[float], control: Sequence[float]) -> float:
    """Cohen's d on the paired differences.

    Under CRN the paired standard deviation is tiny, so this number is large
    almost by construction. It is reported because its size relative to the raw
    difference is itself diagnostic of how much the pairing is doing.
    """
    d = np.asarray(treatment, dtype=float) - np.asarray(control, dtype=float)
    sd = float(np.std(d, ddof=1))
    if sd < 1e-15:
        return float("inf") if abs(float(d.mean())) > 1e-15 else 0.0
    return float(d.mean() / sd)


def holm_bonferroni(pvalues: Mapping[str, float], alpha: float = 0.05
                    ) -> Dict[str, Dict[str, Any]]:
    """Holm's step-down correction. Uniformly more powerful than Bonferroni.

    Holm is chosen over Benjamini-Hochberg because the comparisons here are
    confirmatory contrasts against a single baseline arm, where controlling the
    family-wise error rate is the right target; BH controls a false-discovery
    rate, which suits screening rather than confirmation.
    """
    items = sorted(pvalues.items(), key=lambda kv: kv[1])
    m = len(items)
    out: Dict[str, Dict[str, Any]] = {}
    rejected_so_far = True
    for rank, (name, p) in enumerate(items):
        threshold = alpha / (m - rank)
        reject = bool(rejected_so_far and p <= threshold)
        rejected_so_far = reject
        out[name] = {"p": float(p), "threshold": float(threshold),
                     "reject": reject, "rank": rank + 1,
                     "p_adjusted": float(min(1.0, p * (m - rank)))}
    return out


def combined_interval(replication: Sequence[float],
                      structural: Sequence[float],
                      reps: int = 2000, seed: int = 12345
                      ) -> Dict[str, Any]:
    """Report replication and structural uncertainty side by side.

    Deliberately does not return a single merged interval. They quantify
    different things and adding them would imply a joint distribution over
    parameters that nothing here has estimated.
    """
    rep = bootstrap_ci(replication, reps, seed, kind="replication")
    struct = bootstrap_ci(structural, reps, seed, kind="structural")
    return {
        "replication": rep.as_dict(),
        "structural": struct.as_dict(),
        "structural_over_replication":
            (struct.hi - struct.lo) / max(rep.hi - rep.lo, 1e-12),
        "note": ("Replication uncertainty is bootstrap over seeds at a fixed "
                 "parameter vector. Structural uncertainty is the spread across "
                 "the parameter sweep. They are not commensurable and are not "
                 "combined."),
    }


def practical_significance(interval: Mapping[str, float], threshold: float
                           ) -> Dict[str, Any]:
    """Is an effect large enough to matter, not merely large enough to detect?"""
    point = float(interval["point"])
    return {
        "point": point,
        "threshold": float(threshold),
        "practically_significant": bool(abs(point) >= threshold),
        "interval_excludes_zero": bool(
            float(interval["lo"]) * float(interval["hi"]) > 0),
        "interval_excludes_threshold": bool(
            min(abs(float(interval["lo"])), abs(float(interval["hi"]))) >= threshold),
    }


def seed_adequacy(values: Sequence[float], target_halfwidth: float,
                  alpha: float = 0.05) -> Dict[str, Any]:
    """How many seeds are needed for a given interval half-width (E15).

    Uses the normal approximation ``n = (z * sd / halfwidth)**2``. Answers the
    replication question only.
    """
    arr = np.asarray(values, dtype=float)
    sd = float(np.std(arr, ddof=1)) if arr.size > 1 else 0.0
    z = 1.959963984540054 if abs(alpha - 0.05) < 1e-12 else float(
        abs(np.sqrt(2) * _erfinv(1 - alpha)))
    needed = (z * sd / max(target_halfwidth, 1e-12)) ** 2
    return {"n_current": int(arr.size), "sd": sd,
            "n_required": int(np.ceil(needed)),
            "adequate": bool(arr.size >= np.ceil(needed)),
            "target_halfwidth": float(target_halfwidth)}


def _erfinv(y: float) -> float:
    """Inverse error function by Newton refinement on a rational start."""
    a = 0.147
    ln = np.log(1 - y * y)
    t1 = 2 / (np.pi * a) + ln / 2
    x = np.sign(y) * np.sqrt(np.sqrt(t1 * t1 - ln / a) - t1)
    for _ in range(3):
        err = _erf(x) - y
        x -= err / (2 / np.sqrt(np.pi) * np.exp(-x * x))
    return float(x)


def _erf(x: float) -> float:
    t = 1.0 / (1.0 + 0.3275911 * abs(x))
    y = 1.0 - (((((1.061405429 * t - 1.453152027) * t) + 1.421413741) * t
                - 0.284496736) * t + 0.254829592) * t * np.exp(-x * x)
    return float(np.sign(x) * y)
