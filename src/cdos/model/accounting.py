"""Per-period resource accounting, and the F3 correction.

**The defect.** In arms B6 and B6c the state books SAC revenue as
``sum_i r_i * ACB_i``, but the firm's profit line was computed against
``pm_eff``, which encodes only the *marginal* wedge ``r_i * d(ACB)/dM``. The
inframarginal bulk of the liability -- about 93% of it -- was therefore
collected and spent without ever being subtracted from anyone's income. It did
not reduce capital income and it did not reduce the ``tau_K`` base. Arms B1 and
B4 use ``pm_eff = pm (1 + wedge)`` with matching revenue and were exactly
consistent, so the error was **asymmetric and inflated precisely the arms the
paper recommends**.

**The correction.** The two prices are conceptually distinct and both are kept:

* ``pm_eff`` is the *marginal decision price*. It is what the firm optimises
  against, and by Proposition 2 its wedge is ``r_i * d(ACB)/dM``, not ``r_i``.
  Leaving it alone means firm behaviour is unchanged, which is what makes the
  correction a pure accounting fix rather than a change of model.
* ``SAC_i = r_i * ACB_i`` is the *liability*. The firm bears all of it. It is
  debited from profit as a lump sum, after the machine decision has been taken.

So profit becomes ``Y - w L - pm M - r * ACB`` rather than ``Y - w L - pm_eff M``.

**The check.** :func:`ResourceAccount` tracks every source and every use of
resources within a period and asserts that they balance. It fails loudly. The
audit's finding was invisible for as long as it was because nothing in the
model ever asked whether the books closed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np

__all__ = ["ResourceAccount", "AccountingError", "sac_liability",
           "marginal_decision_price", "profit_after_liability"]


class AccountingError(AssertionError):
    """Raised when a period's resource identity fails to close."""


def sac_liability(rate, acb):
    """``SAC_i = r_i * ACB_i`` -- the full liability, Eq. (12)."""
    return np.asarray(rate, dtype=float) * np.maximum(np.asarray(acb, dtype=float), 0.0)


def marginal_decision_price(pm, rate, dacb_dm, floor_ratio: float = 0.25):
    """The price the firm optimises against: ``pm + r * d(ACB)/dM``.

    ``d(ACB)/dM = d(psi_M)/dM - phi * pm`` by Proposition 2, so the caller
    passes that quantity directly. Floored at ``floor_ratio * pm`` to keep the
    firm's problem well posed when the marginal term is strongly negative --
    which, under ``phi = 1``, is exactly the subsidy Proposition 2 warns about.
    """
    pm = np.asarray(pm, dtype=float)
    return np.maximum(pm + np.asarray(rate, dtype=float)
                      * np.asarray(dacb_dm, dtype=float), floor_ratio * pm)


def profit_after_liability(Y_f, w, L_f, pm, M_f, liability=None):
    """Firm profit with the true liability debited.

    Machines are charged at the *actual* price ``pm``; the liability is a
    separate lump-sum line. Under arms that levy a genuine price wedge the
    caller passes the wedged price as ``pm`` and no liability, which reproduces
    the consistent B1/B4 treatment exactly.
    """
    profit = np.asarray(Y_f, dtype=float) - w * np.asarray(L_f, dtype=float) \
        - np.asarray(pm, dtype=float) * np.asarray(M_f, dtype=float)
    if liability is not None:
        profit = profit - np.asarray(liability, dtype=float)
    return np.maximum(profit, 0.0)


# ---------------------------------------------------------------------------
# Resource identity
# ---------------------------------------------------------------------------

@dataclass
class ResourceAccount:
    """Sources and uses of resources within one period.

    The identity checked is

        output + fund_return  ==  wage_bill + machine_cost + profit
                                  + unpaid_residual

    on the production side, and separately on the fiscal side

        tax_revenue + fund_drawdown  ==  public_spending + programme_spending
                                         + transfers + fund_inflow

    Both must hold. The second is the one that failed in the audited baseline:
    ``rev_auto`` appeared on the revenue side of the government budget while
    only a fraction of it had been removed from firm income.
    """
    period: int
    tol: float = 1e-8
    strict: bool = True
    sources: Dict[str, float] = field(default_factory=dict)
    uses: Dict[str, float] = field(default_factory=dict)
    fiscal_in: Dict[str, float] = field(default_factory=dict)
    fiscal_out: Dict[str, float] = field(default_factory=dict)

    def source(self, name: str, value: float) -> None:
        self.sources[name] = self.sources.get(name, 0.0) + float(value)

    def use(self, name: str, value: float) -> None:
        self.uses[name] = self.uses.get(name, 0.0) + float(value)

    def revenue(self, name: str, value: float) -> None:
        self.fiscal_in[name] = self.fiscal_in.get(name, 0.0) + float(value)

    def spend(self, name: str, value: float) -> None:
        self.fiscal_out[name] = self.fiscal_out.get(name, 0.0) + float(value)

    # -- totals -------------------------------------------------------------
    @property
    def total_sources(self) -> float:
        return sum(self.sources.values())

    @property
    def total_uses(self) -> float:
        return sum(self.uses.values())

    @property
    def total_revenue(self) -> float:
        return sum(self.fiscal_in.values())

    @property
    def total_spending(self) -> float:
        return sum(self.fiscal_out.values())

    def residual(self) -> float:
        return self.total_sources - self.total_uses

    def fiscal_residual(self) -> float:
        return self.total_revenue - self.total_spending

    # -- verification -------------------------------------------------------
    def _relative(self, residual: float, scale: float) -> float:
        return abs(residual) / max(abs(scale), 1e-12)

    def check(self) -> Dict[str, float]:
        """Verify both identities. Raises :class:`AccountingError` when strict."""
        rel = self._relative(self.residual(), self.total_sources)
        frel = self._relative(self.fiscal_residual(), self.total_revenue)
        report = {
            "period": self.period,
            "resource_residual": self.residual(),
            "resource_relative": rel,
            "fiscal_residual": self.fiscal_residual(),
            "fiscal_relative": frel,
            "total_sources": self.total_sources,
            "total_uses": self.total_uses,
            "total_revenue": self.total_revenue,
            "total_spending": self.total_spending,
            "closed": bool(rel <= self.tol and frel <= self.tol),
        }
        if self.strict and not report["closed"]:
            raise AccountingError(self.describe(report))
        return report

    def describe(self, report: Optional[Dict[str, float]] = None) -> str:
        report = report or {
            "resource_relative": self._relative(self.residual(), self.total_sources),
            "fiscal_relative": self._relative(self.fiscal_residual(), self.total_revenue),
        }
        lines: List[str] = [
            f"resource accounting failed to close in period {self.period}",
            f"  sources {self.total_sources:.10g} vs uses {self.total_uses:.10g} "
            f"(relative {report['resource_relative']:.3e}, tol {self.tol:.1e})",
        ]
        for k, v in sorted(self.sources.items()):
            lines.append(f"    + {k:<24s} {v:>18.10g}")
        for k, v in sorted(self.uses.items()):
            lines.append(f"    - {k:<24s} {v:>18.10g}")
        lines.append(
            f"  revenue {self.total_revenue:.10g} vs spending "
            f"{self.total_spending:.10g} (relative {report['fiscal_relative']:.3e})")
        for k, v in sorted(self.fiscal_in.items()):
            lines.append(f"    + {k:<24s} {v:>18.10g}")
        for k, v in sorted(self.fiscal_out.items()):
            lines.append(f"    - {k:<24s} {v:>18.10g}")
        return "\n".join(lines)

    def as_dict(self) -> Dict[str, object]:
        return {"period": self.period, "sources": dict(self.sources),
                "uses": dict(self.uses), "fiscal_in": dict(self.fiscal_in),
                "fiscal_out": dict(self.fiscal_out),
                "resource_residual": self.residual(),
                "fiscal_residual": self.fiscal_residual()}
