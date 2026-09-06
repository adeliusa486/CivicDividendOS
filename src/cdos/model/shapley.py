"""Shapley attribution of firm value to factors of production.

Two games are implemented.

**Two-factor** ``{L, M}`` -- the audited baseline. With the CES-with-span-of-
control technology the coalition values are available in closed form, so the
Shapley value is exact rather than sampled:

    v({L})  = A * (alpha * L**rho) ** (gamma/rho)
    v({M})  = A * ((1-alpha) * M**rho) ** (gamma/rho)
    v({L,M}) = A * (alpha*L**rho + (1-alpha)*M**rho) ** (gamma/rho)
    psi_M   = 1/2 * v({M}) + 1/2 * (v({L,M}) - v({L}))

**Five-factor** ``{H, A, R, D, K}`` -- the specification in the manuscript.
Human labour ``H``, AI agents ``A``, robots ``R``, data ``D`` and traditional
capital ``K``. All ``2**5 - 1 = 31`` non-empty coalitions are evaluated exactly
and the Shapley value is computed from the full permutation-weighted sum, not by
Monte-Carlo sampling. Efficiency (``sum_i psi_i == v(N)``) therefore holds to
floating-point precision and is asserted in the test suite.

The five-factor value function keeps the same functional family: each factor
carries a share weight ``theta_i``, the coalition aggregate is the CES
combination of the members' inputs, and the span-of-control exponent is applied
to the aggregate. A coalition missing every factor produces nothing.

The audit's F1 finding is a property of this game and is exposed here as
:func:`marginal_below_price_condition`: the ratio of the stand-alone to the
joint marginal product is exactly ``s_M ** (gamma/rho - 1)``, so Proposition 2's
inequality holds *identically* whenever ``gamma > rho``. That is a fact about
the calibration, not evidence about the world.
"""

from __future__ import annotations

from itertools import combinations
from math import factorial
from typing import Dict, Iterable, List, Sequence, Tuple

import numpy as np

from .production import is_cobb_douglas

__all__ = ["shapley_machine", "dpsi_dM", "shapley_five_factor",
           "cost_share_attribution", "marginal_below_price_condition",
           "FIVE_FACTORS", "coalition_value"]

FIVE_FACTORS: Tuple[str, ...] = ("H", "A", "R", "D", "K")


# ---------------------------------------------------------------------------
# Two-factor game
# ---------------------------------------------------------------------------

def shapley_machine(alpha, A, L, M, sigma: float, gamma: float,
                    tol: float = 1e-8):
    """Shapley value of the machine factor. ``psi_L + psi_M == Y`` exactly.

    Returns ``(psi_M, v_LM)``.
    """
    Ls = np.maximum(np.asarray(L, dtype=float), 1e-12)
    Ms = np.maximum(np.asarray(M, dtype=float), 1e-12)
    alpha = np.asarray(alpha, dtype=float)
    if is_cobb_douglas(sigma, tol):
        # rho -> 0: the CES aggregate becomes L**alpha * M**(1-alpha) and each
        # singleton coalition produces nothing, so the Shapley split is the
        # symmetric half of total output.
        vLM = A * (Ls ** alpha * Ms ** (1.0 - alpha)) ** gamma
        return 0.5 * vLM, vLM
    rho = 1.0 - 1.0 / sigma
    vL = A * (alpha * Ls ** rho) ** (gamma / rho)
    vM = A * ((1.0 - alpha) * Ms ** rho) ** (gamma / rho)
    vLM = A * (alpha * Ls ** rho + (1.0 - alpha) * Ms ** rho) ** (gamma / rho)
    psi_M = 0.5 * vM + 0.5 * (vLM - vL)
    return np.clip(psi_M, 0.0, vLM), vLM


def dpsi_dM(alpha, A, L, M, sigma: float, gamma: float, tol: float = 1e-8):
    """``d(psi_M)/dM`` in closed form; verified against central differences."""
    Ls = np.maximum(np.asarray(L, dtype=float), 1e-12)
    Ms = np.maximum(np.asarray(M, dtype=float), 1e-12)
    alpha = np.asarray(alpha, dtype=float)
    if is_cobb_douglas(sigma, tol):
        vLM = A * (Ls ** alpha * Ms ** (1.0 - alpha)) ** gamma
        return 0.5 * gamma * (1.0 - alpha) * vLM / Ms
    rho = 1.0 - 1.0 / sigma
    S = alpha * Ls ** rho + (1.0 - alpha) * Ms ** rho
    dvM = A * (1.0 - alpha) ** (gamma / rho) * gamma * Ms ** (gamma - 1.0)
    dvLM = A * gamma * S ** (gamma / rho - 1.0) * (1.0 - alpha) * Ms ** (rho - 1.0)
    return 0.5 * dvM + 0.5 * dvLM


def marginal_below_price_condition(sigma: float, gamma: float) -> Dict[str, float | bool]:
    """Report whether Proposition 2's inequality can fail at this calibration.

    The ratio ``dv({M})/dM  /  dY/dM`` equals ``s_M ** (gamma/rho - 1)`` with
    ``s_M in (0,1)``, so it is below one for every firm and every quarter
    whenever ``gamma > rho``. Universal incidence is then a tautology and is not
    evidence for the proposition (audit F1).
    """
    rho = 1.0 - 1.0 / sigma
    return {
        "sigma": sigma,
        "gamma": gamma,
        "rho": rho,
        "gamma_over_rho": (gamma / rho) if rho != 0 else float("inf"),
        "holds_identically": bool(gamma > rho),
        "is_informative": bool(gamma <= rho),
    }


# ---------------------------------------------------------------------------
# Five-factor game
# ---------------------------------------------------------------------------

def coalition_value(inputs: Dict[str, np.ndarray], members: Sequence[str],
                    shares: Dict[str, float], A, sigma: float, gamma: float,
                    tol: float = 1e-8):
    """Value produced by a coalition of factors.

    The coalition combines its members' inputs through the same CES aggregator
    used by the two-factor game, weighted by each factor's share ``theta_i``,
    and then applies the span-of-control exponent. Factors outside the coalition
    contribute nothing -- that is what makes this a cooperative game rather than
    a production function evaluated at zero.
    """
    if not members:
        return np.zeros_like(np.asarray(A, dtype=float))
    if is_cobb_douglas(sigma, tol):
        weight = sum(shares[m] for m in members)
        agg = np.ones_like(np.asarray(A, dtype=float))
        for m in members:
            agg = agg * np.maximum(inputs[m], 1e-12) ** (shares[m] / max(weight, 1e-12))
        return A * agg ** gamma
    rho = 1.0 - 1.0 / sigma
    acc = np.zeros_like(np.asarray(A, dtype=float))
    for m in members:
        acc = acc + shares[m] * np.maximum(inputs[m], 1e-12) ** rho
    return A * acc ** (gamma / rho)


def shapley_five_factor(inputs: Dict[str, np.ndarray], A, sigma: float,
                        gamma: float, shares: Dict[str, float] | None = None,
                        factors: Sequence[str] = FIVE_FACTORS,
                        tol: float = 1e-8) -> Dict[str, np.ndarray]:
    """Exact Shapley values over the ``2**n - 1`` non-empty coalitions.

    ``inputs`` maps every factor name to a per-firm input array. Returns a dict
    of per-firm Shapley values, one array per factor, satisfying
    ``sum_i psi_i == v(N)`` to floating-point precision.
    """
    factors = tuple(factors)
    n = len(factors)
    if shares is None:
        shares = {f: 1.0 / n for f in factors}
    missing = [f for f in factors if f not in inputs]
    if missing:
        raise KeyError(f"missing inputs for factors {missing}")

    # Cache every coalition value once: 2**n evaluations, not n * 2**n.
    values: Dict[frozenset, np.ndarray] = {frozenset(): np.zeros_like(
        np.asarray(A, dtype=float))}
    for size in range(1, n + 1):
        for members in combinations(factors, size):
            values[frozenset(members)] = coalition_value(
                inputs, members, shares, A, sigma, gamma, tol)

    weights = {s: factorial(s) * factorial(n - s - 1) / factorial(n)
               for s in range(n)}
    out: Dict[str, np.ndarray] = {}
    for f in factors:
        others = [g for g in factors if g != f]
        acc = np.zeros_like(np.asarray(A, dtype=float))
        for size in range(n):
            for members in combinations(others, size):
                s = frozenset(members)
                acc = acc + weights[size] * (values[s | {f}] - values[s])
        out[f] = acc
    return out


def cost_share_attribution(costs: Dict[str, np.ndarray], total_value):
    """Ablation A2: attribute value in proportion to factor cost.

    This is the conventional alternative to Shapley and is what the manuscript
    argues against. Keeping it implemented is what makes that argument testable.
    """
    denom = np.zeros_like(np.asarray(total_value, dtype=float))
    for c in costs.values():
        denom = denom + np.asarray(c, dtype=float)
    denom = np.maximum(denom, 1e-12)
    return {k: np.asarray(v, dtype=float) / denom * total_value
            for k, v in costs.items()}
