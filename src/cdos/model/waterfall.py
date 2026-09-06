"""The four-channel distribution waterfall, Fig. 5 and Proposition 5.

SAC revenue splits into four channels:

    omega    -> Public Automation Wealth Fund
    kappa    -> Earned-income shield (a labour tax reduction)
    sigma_T  -> Immediate transition support
    residual -> General public revenue,  residual = 1 - omega - kappa - sigma_T

Proposition 5 gives the feasibility constraint ``omega + kappa + sigma_T <= 1``,
which is an accounting identity: allocated shares cannot exceed collected
revenue. :func:`split` enforces it.

The audited baseline implemented only ``omega`` and ``sigma_T``; ``kappa`` was
absent from the code even though it appears in the worked example at 0.25 and
carries the shield, which the paper names as the mechanism behind the lower
labour tax. The shield still operated in the baseline, but implicitly: SAC
revenue entered the government budget constraint and the labour tax cleared it,
so the whole residual acted as a shield. Making ``kappa`` explicit separates the
earmarked shield from the residual, which is what the ablations need.

Proposition 5's Laffer correction is Eq. (18): to first order in the labour
supply elasticity the net cost of the shield is

    kappa * Rev_SAC * [1 - eps_L * tau_L / (1 - tau_L)]
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

__all__ = ["WaterfallSplit", "split", "feasible", "shield_net_cost",
           "CHANNELS"]

CHANNELS = ("fund", "shield", "transition", "general")


@dataclass(frozen=True)
class WaterfallSplit:
    revenue: float
    fund: float
    shield: float
    transition: float
    general: float

    @property
    def total(self) -> float:
        return self.fund + self.shield + self.transition + self.general

    def as_dict(self) -> Dict[str, float]:
        return {"revenue": self.revenue, "fund": self.fund,
                "shield": self.shield, "transition": self.transition,
                "general": self.general}


def feasible(omega: float, kappa: float, sigma_t: float, tol: float = 1e-12) -> bool:
    """Proposition 5: the three earmarked shares must not exceed one."""
    return (omega >= -tol and kappa >= -tol and sigma_t >= -tol
            and omega + kappa + sigma_t <= 1.0 + tol)


def split(revenue: float, omega: float, kappa: float, sigma_t: float,
          strict: bool = True) -> WaterfallSplit:
    """Apportion SAC revenue across the four channels.

    Raises when the shares are infeasible, because an infeasible split would
    distribute money that was never collected -- exactly the class of error the
    audit's F3 finding is about.
    """
    if not feasible(omega, kappa, sigma_t):
        message = ("waterfall shares infeasible (Proposition 5): "
                   f"omega={omega} + kappa={kappa} + sigma_T={sigma_t} "
                   f"= {omega + kappa + sigma_t} exceeds 1")
        if strict:
            raise ValueError(message)
    residual = max(1.0 - omega - kappa - sigma_t, 0.0)
    return WaterfallSplit(revenue=revenue,
                          fund=omega * revenue,
                          shield=kappa * revenue,
                          transition=sigma_t * revenue,
                          general=residual * revenue)


def shield_net_cost(kappa: float, revenue: float, eps_l: float,
                    tau_l: float) -> float:
    """Eq. (18): the shield's mechanical cost net of its base expansion."""
    denom = max(1.0 - tau_l, 1e-9)
    return kappa * revenue * (1.0 - eps_l * tau_l / denom)
