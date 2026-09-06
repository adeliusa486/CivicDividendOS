"""The Public Automation Wealth Fund, and the stability condition of Prop. 6.

The recursion is Eq. (19):

    F_{t+1} = F_t (1 + r_f) + omega * Rev_SAC,t + E_t - Dist_t,
    Dist_t  = rho * r_f * F_t

Writing ``f_t = F_t / Y_t`` and letting the combined inflow satisfy
``(omega*Rev + E)/Y = s``, the fund-to-output ratio converges iff

    (1 - rho) * r_f  <  g

and the steady state is ``f* = s (1 + g) / (g - (1 - rho) r_f)``, with a
convergence half-life set by ``a = (1 + (1-rho) r_f) / (1 + g)``.

**Audit finding F2.** The testbed sets ``rho = 0.60`` and ``r_f = 0.05``, giving
``(1-rho) r_f = 0.0200``, while the model's realised output growth is about
``g = 0.0166``. The condition therefore *fails*: the reported terminal fund of
17.0% of GDP is not a steady state but a point on a divergent path. Table VI's
71-year half-life assumes ``g = 0.03``, which the testbed does not deliver.

This module does not hide that. :func:`stability` returns the margin
``g - (1-rho) r_f`` explicitly, and the configured ``stability_mode`` decides
what happens when it is negative:

* ``"require"`` -- raise. Use when a run is supposed to be on a convergent path.
* ``"warn"``    -- record the margin and continue. The default, because the
                   audited calibration genuinely is divergent and suppressing
                   it would be the same error again.
* ``"stress"``  -- divergence is the object of study; stay silent.
"""

from __future__ import annotations

import math
import warnings
from dataclasses import dataclass

import numpy as np

__all__ = ["StabilityReport", "stability", "steady_state_ratio",
           "half_life_years", "required_inflow", "check_stability",
           "fund_step", "simulate_fund_ratio"]


@dataclass(frozen=True)
class StabilityReport:
    rho: float
    r_f: float
    g: float
    drift: float          # (1 - rho) * r_f
    margin: float         # g - drift; positive means convergent
    stable: bool
    steady_state: float | None
    half_life_years: float | None

    def as_dict(self) -> dict:
        return {
            "rho": self.rho, "r_f": self.r_f, "g": self.g, "drift": self.drift,
            "stability_margin": self.margin, "stable": self.stable,
            "steady_state_ratio": self.steady_state,
            "half_life_years": self.half_life_years,
        }


def stability(rho: float, r_f: float, g: float, inflow_share: float = 0.0065
              ) -> StabilityReport:
    """Evaluate Proposition 6 at an annual return, payout share and growth rate."""
    drift = (1.0 - rho) * r_f
    margin = g - drift
    stable = margin > 0.0
    f_star = steady_state_ratio(inflow_share, g, rho, r_f) if stable else None
    hl = half_life_years(rho, r_f, g) if stable else None
    return StabilityReport(rho=rho, r_f=r_f, g=g, drift=drift, margin=margin,
                           stable=stable, steady_state=f_star, half_life_years=hl)


def steady_state_ratio(s: float, g: float, rho: float, r_f: float) -> float:
    """``f* = s (1 + g) / (g - (1 - rho) r_f)``. Requires a positive margin."""
    denom = g - (1.0 - rho) * r_f
    if denom <= 0.0:
        raise ValueError(
            f"no finite steady state: (1-rho)*r_f = {(1.0 - rho) * r_f:.6f} exceeds g = {g:.6f} "
            "(Proposition 6 violated)")
    return s * (1.0 + g) / denom


def half_life_years(rho: float, r_f: float, g: float) -> float:
    """Half-life of convergence to ``f*``, in years."""
    a = (1.0 + (1.0 - rho) * r_f) / (1.0 + g)
    if a >= 1.0:
        raise ValueError(f"divergent: convergence factor a = {a:.6f} is not below one")
    return math.log(0.5) / math.log(a)


def required_inflow(kappa_d: float, r_f: float, rho: float, g: float) -> float:
    """Inflow ``s`` needed to sustain a dividend of ``kappa_d`` of output.

    ``s = kappa_d [g - (1-rho) r_f] / [rho r_f (1 + g)]`` -- the design rule
    inverted from Eq. (20). At kappa_d=0.02, r_f=0.05, rho=0.60, g=0.03 this is
    0.65% of output against a fund of 66.7% of output.
    """
    return kappa_d * (g - (1.0 - rho) * r_f) / (rho * r_f * (1.0 + g))


def check_stability(report: StabilityReport, mode: str = "warn",
                    context: str = "") -> StabilityReport:
    """Act on a stability report according to the configured mode."""
    if report.stable or mode == "stress":
        return report
    where = f" [{context}]" if context else ""
    message = (
        f"fund stability condition violated{where}: "
        f"(1-rho)*r_f = {report.drift:.5f} exceeds realised g = {report.g:.5f}, "
        f"margin {report.margin:.5f}. The fund-to-output ratio diverges; "
        "no finite steady state exists (audit F2).")
    if mode == "require":
        raise RuntimeError(message)
    if mode == "warn":
        warnings.warn(message, RuntimeWarning, stacklevel=2)
        return report
    raise ValueError(f"unknown stability_mode {mode!r}")


# ---------------------------------------------------------------------------
# Simulation-side recursion
# ---------------------------------------------------------------------------

def fund_step(fund: float, r_f_quarterly: float, inflow: float,
              rho: float) -> tuple[float, float]:
    """One quarter of Eq. (19). Returns ``(fund_next, payout)``."""
    payout = rho * r_f_quarterly * fund
    return fund * (1.0 + r_f_quarterly) + inflow - payout, payout


def simulate_fund_ratio(s: float, g: float, rho: float, r_f: float,
                        periods: int, f0: float = 0.0) -> np.ndarray:
    """Analytic path of ``f_t = F_t / Y_t`` under constant inflow share ``s``.

    The recursion is ``f_{t+1} = a f_t + s`` with
    ``a = (1 + (1-rho) r_f) / (1 + g)``, whose fixed point is
    ``s / (1 - a) = s (1 + g) / (g - (1-rho) r_f)`` -- the manuscript's
    :func:`steady_state_ratio`. The inflow share is therefore measured against
    contemporaneous output ``Y_{t+1}``, which is the convention Table VI uses.

    Used by E3 to compare the simulated fund against the closed-form dynamics
    the manuscript asserts. Deliberately does *not* require stability, so a
    divergent calibration produces a divergent path rather than an exception.
    """
    a = (1.0 + (1.0 - rho) * r_f) / (1.0 + g)
    out = np.empty(periods + 1, dtype=float)
    out[0] = f0
    for t in range(periods):
        out[t + 1] = a * out[t] + s
    return out
