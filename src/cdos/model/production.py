"""CES production with a span-of-control exponent, and market clearing.

The firm produces ``Y = A * X**gamma`` where ``X`` is a CES aggregate of labour
``L`` and machine services ``M``:

    X = (alpha * L**rho + (1-alpha) * M**rho) ** (1/rho),    rho = 1 - 1/sigma

``gamma < 1`` gives decreasing returns, which is what pins down firm size.

Two numerical points the audited baseline left open:

* ``sigma -> 1`` is a removable singularity (``rho -> 0``). Both the unit cost
  and the aggregator collapse to Cobb-Douglas. The baseline would have returned
  ``inf``/``nan`` there; :func:`ces_unit_cost` and :func:`ces_aggregate` take
  the limit explicitly.
* The wage bisection bracket was fixed at ``[1e-3, 1e3]`` with no check that the
  root was inside it. :func:`clear_wage` verifies the bracket and expands it
  rather than silently returning an endpoint.
"""

from __future__ import annotations

import numpy as np

__all__ = ["ces_unit_cost", "ces_aggregate", "firm_block", "clear_wage",
           "labour_supply", "is_cobb_douglas"]


def is_cobb_douglas(sigma: float, tol: float = 1e-8) -> bool:
    """True when sigma is close enough to 1 that the CD limit should be used."""
    return abs(sigma - 1.0) < tol


def ces_unit_cost(alpha, w, pm, sigma: float, tol: float = 1e-8):
    """Unit cost of the CES aggregate.

    For sigma != 1:
        c = (alpha**sigma * w**(1-sigma) + (1-alpha)**sigma * pm**(1-sigma))**(1/(1-sigma))
    For sigma -> 1 this tends to the Cobb-Douglas unit cost
        c = (w/alpha)**alpha * (pm/(1-alpha))**(1-alpha)
    """
    alpha = np.asarray(alpha, dtype=float)
    w = np.asarray(w, dtype=float)
    pm = np.asarray(pm, dtype=float)
    if is_cobb_douglas(sigma, tol):
        return (w / alpha) ** alpha * (pm / (1.0 - alpha)) ** (1.0 - alpha)
    return (alpha ** sigma * w ** (1.0 - sigma)
            + (1.0 - alpha) ** sigma * pm ** (1.0 - sigma)) ** (1.0 / (1.0 - sigma))


def ces_aggregate(alpha, L, M, sigma: float, tol: float = 1e-8):
    """The CES quantity aggregate X(L, M)."""
    alpha = np.asarray(alpha, dtype=float)
    L = np.maximum(np.asarray(L, dtype=float), 1e-12)
    M = np.maximum(np.asarray(M, dtype=float), 1e-12)
    if is_cobb_douglas(sigma, tol):
        return L ** alpha * M ** (1.0 - alpha)
    rho = 1.0 - 1.0 / sigma
    return (alpha * L ** rho + (1.0 - alpha) * M ** rho) ** (1.0 / rho)


def firm_block(alpha, A, w, pm, sigma: float, gamma: float, tol: float = 1e-8):
    """Cost-minimising factor demands and output for every firm.

    Returns ``(L, M, Y, c)``. ``w`` and ``pm`` may be scalars or per-firm arrays;
    ``pm`` is the *effective* price the firm faces when deciding, which under the
    SAC is not the same thing as the price it ultimately pays (see
    :mod:`cdos.model.accounting`).
    """
    c = ces_unit_cost(alpha, w, pm, sigma, tol)
    X = (gamma * A / c) ** (1.0 / (1.0 - gamma))
    if is_cobb_douglas(sigma, tol):
        # Shephard's lemma on the CD unit cost.
        L = alpha * c / w * X
        M = (1.0 - alpha) * c / pm * X
    else:
        L = alpha ** sigma * (w / c) ** (-sigma) * X
        M = (1.0 - alpha) ** sigma * (pm / c) ** (-sigma) * X
    Y = A * X ** gamma
    return L, M, Y, c


def labour_supply(sup_scale: float, w: float, tau_l: float, eps_l: float) -> float:
    """Aggregate labour supply in efficiency units.

    ``sup_scale`` is the sum of skill x efficiency across households, so the
    quantity returned is efficiency units and *not* a headcount. See
    :mod:`cdos.eval.metrics` for the distinction the audit's F6 turns on.
    """
    return sup_scale * max(w * (1.0 - tau_l), 1e-9) ** eps_l


def clear_wage(alpha, A, pm, sup_scale: float, tau_l: float, eps_l: float,
               sigma: float, gamma: float, lo: float = 1e-3, hi: float = 1e3,
               iters: int = 28, tol: float = 1e-8,
               verify_bracket: bool = True) -> float:
    """Bisect (in logs) on the wage until labour demand equals labour supply.

    Excess demand is decreasing in ``w``, so the root is unique. When
    ``verify_bracket`` is set the initial bracket is checked and widened up to
    forty times before giving up, rather than returning an endpoint that is not
    a root.
    """
    def excess(w: float) -> float:
        L, _, _, _ = firm_block(alpha, A, w, pm, sigma, gamma, tol)
        return float(np.sum(L)) - labour_supply(sup_scale, w, tau_l, eps_l)

    if verify_bracket:
        tries = 0
        while excess(lo) < 0.0 and tries < 40:
            lo /= 4.0
            tries += 1
        while excess(hi) > 0.0 and tries < 40:
            hi *= 4.0
            tries += 1
        if excess(lo) < 0.0 or excess(hi) > 0.0:
            raise RuntimeError(
                "wage bisection bracket does not contain a root "
                f"(excess demand {excess(lo):.3e} at w={lo:.3e}, "
                f"{excess(hi):.3e} at w={hi:.3e})")

    for _ in range(iters):
        w = np.sqrt(lo * hi)
        if excess(w) > 0.0:
            lo = w
        else:
            hi = w
    return float(np.sqrt(lo * hi))
