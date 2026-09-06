"""Fiscal digital twin: constrained policy screening, Eq. (26).

The screening problem is

    Theta* = argmax_{Theta in T}  sum_k omega_k * U~_k(Theta)

subject to a revenue floor, an innovation floor, a leakage ceiling, and the
boundedness and feasibility constraints of Propositions 3 and 5.

What is specified, and what is not
----------------------------------
The manuscript specifies the *form* of the problem, the policy vector
``Theta = {r0, alpha, beta, gamma, delta, eta, theta, lambda, mu, nu, omega,
rho, kappa, xi}``, the constraint set, and the governance requirement that the
weights ``omega_k`` be published rather than inferred. It does **not** specify:

* the search space ``T`` -- no bounds are given for any coordinate;
* the normalisation ``U~_k`` -- "normalised outcome" is not defined;
* numeric values for the floors and the ceiling;
* numeric values for the weights ``omega_k``.

Those are author decisions, not implementation details, and inventing them would
manufacture a result. So this module implements the *interface* completely and
requires the caller to supply all four. :func:`screen` refuses to run with any
of them missing, and :data:`REQUIRES_AUTHOR_SPECIFICATION` records exactly what
must be supplied before a screening result can be reported as the paper's.

Governance constraints, both of which are properties of the institution rather
than the model, are enforced here as far as code can enforce them: the twin
reports incidence explicitly alongside every objective value, and it proposes
rather than sets -- :func:`screen` returns a candidate and never mutates a
configuration in place.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple

import numpy as np

from ..config import Config
from ..model.rate import rate_weights
from ..model.waterfall import feasible

__all__ = ["POLICY_VECTOR", "SearchSpace", "ScreeningResult", "screen",
           "REQUIRES_AUTHOR_SPECIFICATION", "default_normaliser"]

# Theta as listed in Section "Fiscal Digital Twin".
POLICY_VECTOR = ("rate.r0", "rate.w_alpha", "rate.w_beta", "rate.w_gamma_e",
                 "rate.w_delta", "rate.w_eta", "rate.w_theta", "rate.w_lambda",
                 "rate.w_mu", "rate.w_nu", "fund.omega", "fund.rho_payout",
                 "fund.kappa", "policy.aou_xi")

REQUIRES_AUTHOR_SPECIFICATION = (
    "search space bounds for each coordinate of Theta",
    "the normalisation map U~_k for each outcome k",
    "numeric values for the revenue floor, innovation floor and leakage ceiling",
    "numeric values for the scalarisation weights omega_k",
)


@dataclass
class SearchSpace:
    """Bounds on each coordinate of ``Theta``, supplied by the caller."""
    bounds: Dict[str, Tuple[float, float]]

    def validate(self) -> None:
        unknown = [k for k in self.bounds if k not in POLICY_VECTOR]
        if unknown:
            raise ValueError(
                f"search space names coordinates outside Theta: {unknown}. "
                f"Theta is {list(POLICY_VECTOR)}")
        for key, (lo, hi) in self.bounds.items():
            if not np.isfinite(lo) or not np.isfinite(hi):
                raise ValueError(f"bounds for {key} must be finite, got ({lo}, {hi})")
            if hi < lo:
                raise ValueError(f"bounds for {key} are inverted: ({lo}, {hi})")

    def sample(self, rng: np.random.Generator) -> Dict[str, float]:
        return {k: float(rng.uniform(lo, hi)) for k, (lo, hi) in self.bounds.items()}

    def latin_hypercube(self, n: int, rng: np.random.Generator
                        ) -> List[Dict[str, float]]:
        """Stratified sample: better coverage per evaluation than uniform draws."""
        keys = list(self.bounds)
        cuts = np.empty((n, len(keys)))
        for j, key in enumerate(keys):
            lo, hi = self.bounds[key]
            strata = (np.arange(n) + rng.random(n)) / n
            cuts[:, j] = lo + strata[rng.permutation(n)] * (hi - lo)
        return [{k: float(cuts[i, j]) for j, k in enumerate(keys)} for i in range(n)]


@dataclass
class ScreeningResult:
    theta: Dict[str, float]
    objective: float
    outcomes: Dict[str, float]
    incidence: Dict[str, float]
    feasible: bool
    n_evaluated: int
    n_feasible: int
    trace: List[Dict[str, Any]] = field(default_factory=list)

    def as_dict(self) -> Dict[str, Any]:
        return {"theta": self.theta, "objective": self.objective,
                "outcomes": self.outcomes, "incidence": self.incidence,
                "feasible": self.feasible, "n_evaluated": self.n_evaluated,
                "n_feasible": self.n_feasible}


def default_normaliser(reference: Mapping[str, float]
                       ) -> Callable[[str, float], float]:
    """A ratio-to-reference normalisation, offered only as a starting point.

    ``U~_k = value_k / reference_k``. This is *not* the manuscript's map, which
    is unspecified; it is here so the interface can be exercised end to end.
    Any result produced with it must say which normalisation it used.
    """
    def norm(key: str, value: float) -> float:
        base = float(reference.get(key, 0.0))
        if base == 0.0:
            return value
        return value / base
    return norm


def _constraints_hold(cfg: Config, outcomes: Mapping[str, float],
                      revenue_floor: float, innovation_floor: float,
                      leakage_ceiling: float) -> Tuple[bool, List[str]]:
    failures: List[str] = []
    if outcomes.get("revenue", 0.0) < revenue_floor:
        failures.append("revenue floor")
    if outcomes.get("innovation", 0.0) < innovation_floor:
        failures.append("innovation floor")
    if outcomes.get("leakage", 0.0) > leakage_ceiling:
        failures.append("leakage ceiling")
    # Proposition 3: weights must be non-negative and the rate bounded.
    try:
        rate_weights(cfg.rate)
    except ValueError as exc:
        failures.append(f"Proposition 3 ({exc})")
    if cfg.rate.rmax < cfg.rate.rmin:
        failures.append("Proposition 3 (rmax below rmin)")
    # Proposition 5: the waterfall must be feasible.
    if not feasible(cfg.fund.omega, cfg.fund.kappa, cfg.fund.sigma_t):
        failures.append("Proposition 5 (omega + kappa + sigma_T exceeds 1)")
    return (not failures), failures


def screen(base: Config,
           evaluate: Callable[[Config], Dict[str, float]],
           space: SearchSpace,
           weights: Mapping[str, float],
           normaliser: Callable[[str, float], float],
           revenue_floor: float,
           innovation_floor: float,
           leakage_ceiling: float,
           n_candidates: int = 64,
           seed: int = 0,
           holdout_seeds: Optional[Sequence[int]] = None,
           evaluate_holdout: Optional[Callable[[Config, int], Dict[str, float]]] = None
           ) -> ScreeningResult:
    """Search ``Theta`` for the best feasible scalarised outcome.

    Every argument after ``space`` is required precisely because the manuscript
    does not supply it; see :data:`REQUIRES_AUTHOR_SPECIFICATION`.

    ``holdout_seeds`` guards against seed overfitting. When supplied together
    with ``evaluate_holdout``, the top candidates are re-scored on seeds that
    took no part in the search, and the winner is chosen on the held-out score.
    A policy that only looks good on the seeds it was selected against is not a
    policy result, and the audit's warning about mistaking Monte-Carlo precision
    for policy certainty applies with full force here.
    """
    space.validate()
    if not weights:
        raise ValueError(
            "scalarisation weights omega_k must be supplied and published; the "
            "manuscript specifies that they are published rather than inferred, "
            "and it gives no numeric values")
    rng = np.random.default_rng(seed)
    candidates = space.latin_hypercube(n_candidates, rng)

    trace: List[Dict[str, Any]] = []
    scored: List[Tuple[float, Dict[str, float], Dict[str, float], Dict[str, float]]] = []
    n_feasible = 0

    for theta in candidates:
        cfg = base.with_overrides(theta)
        outcomes = evaluate(cfg)
        ok, failures = _constraints_hold(cfg, outcomes, revenue_floor,
                                         innovation_floor, leakage_ceiling)
        objective = sum(float(w) * normaliser(k, float(outcomes.get(k, 0.0)))
                        for k, w in weights.items())
        incidence = {k: float(v) for k, v in outcomes.items()
                     if k.startswith("incidence")}
        trace.append({"theta": theta, "objective": objective, "feasible": ok,
                      "failures": failures, "outcomes": dict(outcomes)})
        if ok:
            n_feasible += 1
            scored.append((objective, theta, dict(outcomes), incidence))

    if not scored:
        raise RuntimeError(
            f"no candidate satisfied the constraints across {n_candidates} draws; "
            "widen the search space or relax the floors")

    scored.sort(key=lambda row: row[0], reverse=True)

    if holdout_seeds and evaluate_holdout is not None:
        shortlist = scored[:max(1, len(scored) // 8)]
        rescored = []
        for objective, theta, outcomes, incidence in shortlist:
            cfg = base.with_overrides(theta)
            vals = [evaluate_holdout(cfg, s) for s in holdout_seeds]
            merged = {k: float(np.mean([v.get(k, 0.0) for v in vals]))
                      for k in outcomes}
            score = sum(float(w) * normaliser(k, merged.get(k, 0.0))
                        for k, w in weights.items())
            rescored.append((score, theta, merged,
                             {k: v for k, v in merged.items()
                              if k.startswith("incidence")}))
        rescored.sort(key=lambda row: row[0], reverse=True)
        scored = rescored

    objective, theta, outcomes, incidence = scored[0]
    return ScreeningResult(theta=theta, objective=objective, outcomes=outcomes,
                           incidence=incidence, feasible=True,
                           n_evaluated=len(candidates), n_feasible=n_feasible,
                           trace=trace)
