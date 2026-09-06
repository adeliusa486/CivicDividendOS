"""Outcome metrics, with the audit's F5/F6 corrections.

Three groups.

**Kept as they were:** output, Gini of income and wealth, wage share, poverty
headcount.

**Corrected:**

* *Employment.* The audited model reported a quantity labelled "Hours" that was
  aggregate labour demand ``sum_f L_f`` in *efficiency units*. It is not hours
  and it is not employment: a worker whose efficiency has been halved by
  displacement contributes half as much to it while still being employed full
  time. :func:`employment_metrics` reports ``efficiency_units``, ``headcount``
  and ``hours`` separately and never conflates them. This model has no
  extensive employment margin at all -- labour supply is a smooth function of
  the net-of-tax wage and nobody is ever unemployed -- so ``headcount`` here
  counts workers above the efficiency floor, which is a displacement measure
  rather than an unemployment measure. That limitation is real and is recorded
  rather than dressed up.
* *Fund-to-output.* Reported as a ratio to annualised output, and always
  alongside the stability margin, because a level means nothing on a divergent
  path.
* *Comparisons of policy effectiveness.* The audit's F5 finding was that a
  headline comparison used the wrong quantity. Ranking tax instruments by
  output effect alone is invalid when the arms raise materially different
  revenue, so :func:`revenue_normalised` supplies revenue per unit of deadweight
  loss and revenue as a share of output alongside it.

**Added:** equivalent variation, deadweight loss, revenue per unit DWL,
incidence by factor and by income decile, revenue volatility, stability margin.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np

__all__ = ["gini", "poverty_rate", "employment_metrics", "equivalent_variation",
           "deadweight_loss", "revenue_normalised", "incidence_by_decile",
           "decile_shares", "atkinson", "summarise_run", "METRIC_DIRECTION"]

# Whether a higher value is better, for reporting only. "context" means the
# metric cannot be ranked without knowing what else changed.
METRIC_DIRECTION: dict[str, str] = {
    "Y": "higher", "ws": "higher", "gi": "lower", "gw": "lower",
    "pov": "lower", "taul": "lower", "dwl": "lower",
    "revenue_per_dwl": "higher", "eff_units": "context", "headcount": "higher",
    "fund": "context", "sac": "context", "rev_cv": "lower",
    "stability_margin": "higher",
}


def gini(x) -> float:
    x = np.clip(np.asarray(x, dtype=float), 0.0, None)
    n = x.size
    xs = np.sort(x)
    tot = xs.sum()
    if tot <= 0:
        return 0.0
    idx = np.arange(1, n + 1)
    return float((2.0 * np.sum(idx * xs) / (n * tot)) - (n + 1.0) / n)


def atkinson(x, epsilon: float = 0.5) -> float:
    """Atkinson index: inequality with an explicit aversion parameter.

    Reported alongside the Gini because the Gini is insensitive to where in the
    distribution a change happens, and the arms differ mostly at the bottom.
    """
    x = np.clip(np.asarray(x, dtype=float), 1e-12, None)
    mu = x.mean()
    if epsilon == 1.0:
        return float(1.0 - np.exp(np.mean(np.log(x))) / mu)
    ede = (np.mean(x ** (1.0 - epsilon))) ** (1.0 / (1.0 - epsilon))
    return float(1.0 - ede / mu)


def poverty_rate(disposable, fraction: float = 0.5) -> float:
    """Headcount below ``fraction`` of the median, the standard relative line."""
    d = np.asarray(disposable, dtype=float)
    return float((d < fraction * np.median(d)).mean())


def employment_metrics(labour_demand_efficiency_units: float,
                       efficiency: np.ndarray,
                       efficiency_floor: float,
                       hours_per_worker: float | None = None
                       ) -> dict[str, float]:
    """Separate the three quantities the audited code conflated (F6)."""
    eff = np.asarray(efficiency, dtype=float)
    headcount = float(np.sum(eff > efficiency_floor + 1e-12))
    out = {
        "efficiency_units": float(labour_demand_efficiency_units),
        "headcount": headcount,
        "mean_efficiency": float(eff.mean()),
    }
    if hours_per_worker is not None:
        out["hours"] = headcount * float(hours_per_worker)
    else:
        # No extensive margin exists in this model, so hours are not identified.
        out["hours"] = float("nan")
    return out


def equivalent_variation(consumption_new, consumption_base,
                         leisure_new=None, leisure_base=None,
                         eps_l: float = 0.30) -> np.ndarray:
    """Money-metric welfare change per household.

    Consumption difference plus the labour-supply term implied by the
    iso-elastic disutility that generates the model's supply function. Reported
    per household so that welfare can be aggregated *and* decomposed by decile,
    which a single scalar cannot support.
    """
    c_new = np.asarray(consumption_new, dtype=float)
    c_base = np.asarray(consumption_base, dtype=float)
    ev = c_new - c_base
    if leisure_new is not None and leisure_base is not None:
        ln = np.asarray(leisure_new, dtype=float)
        lb = np.asarray(leisure_base, dtype=float)
        power = 1.0 + 1.0 / max(eps_l, 1e-9)
        ev = ev - (ln ** power - lb ** power) / power
    return ev


def deadweight_loss(tau_l: float, wage_bill: float, eps_l: float) -> float:
    """Harberger triangle on the labour margin."""
    return 0.5 * eps_l * tau_l ** 2 / max(1.0 - tau_l, 1e-9) * wage_bill


def revenue_normalised(revenue: float, dwl: float, output: float) -> dict[str, float]:
    """Efficiency of an instrument per unit of revenue actually raised (F5).

    Comparing arms on output effect alone is not valid when they raise
    materially different revenue -- an arm that raises almost nothing will look
    efficient for no better reason than that it does almost nothing.
    """
    return {
        "revenue": float(revenue),
        "revenue_share": float(revenue) / max(float(output), 1e-12),
        "dwl": float(dwl),
        "dwl_share": float(dwl) / max(float(output), 1e-12),
        "revenue_per_dwl": float(revenue) / max(float(dwl), 1e-12),
        "dwl_per_revenue": float(dwl) / max(float(revenue), 1e-12),
    }


def decile_shares(income) -> np.ndarray:
    """Share of total income held by each decile, poorest first."""
    x = np.sort(np.asarray(income, dtype=float))
    parts = np.array_split(x, 10)
    total = max(x.sum(), 1e-12)
    return np.array([p.sum() / total for p in parts])


def incidence_by_decile(burden, income) -> np.ndarray:
    """Mean burden within each income decile, poorest first.

    The manuscript's governance requirement is that the twin report incidence
    explicitly, because a contribution levied on an operator may land on
    shareholders, workers, suppliers or consumers. Statutory incidence is not
    economic incidence and this is what separates them.
    """
    inc = np.asarray(income, dtype=float)
    bur = np.asarray(burden, dtype=float)
    order = np.argsort(inc)
    parts = np.array_split(order, 10)
    return np.array([bur[p].mean() if p.size else 0.0 for p in parts])


def summarise_run(result: Mapping[str, Any]) -> dict[str, float]:
    """Pull the reportable metrics out of a run, with the corrections applied."""
    out: dict[str, float] = {}
    for key in ("Y", "Y_end", "ws", "ws_end", "gi", "gw", "pov", "taul",
                "taul_cv", "fund", "divgdp", "adopt", "sac", "rev_cv",
                "eff_units", "headcount", "wage", "dwl", "revenue",
                "revenue_per_dwl", "g_realised", "stability_margin", "spend",
                "incidence_labour", "incidence_capital"):
        if key in result:
            out[key] = float(result[key])
    out["fund_stable"] = float(bool(result.get("fund_stable", False)))
    return out
