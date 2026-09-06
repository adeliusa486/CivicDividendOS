"""The adaptive Social Automation Contribution rate, Eq. (11)-(12).

    r~_i = r0 + alpha*S_i + beta*C_rent_i + gamma_e*E_disp_i + delta*X_ext_i
              + eta*R_rev_i
              - theta*A_aug_i - lambda*T_train_i - mu*B_broad_i - nu*N_new_i

    r_i  = clip(r~_i, r_min, r_max),   SAC_i = r_i * ACB_i

Ten terms. The audited baseline implemented seven: it had no ``E_disp``,
``X_ext`` or ``B_broad`` term, and it fed the substitution index ``S_i`` into
the slot the paper reserves for payroll-base erosion ``R_rev_i``. Both are
restored here, and ``legacy_rrev_uses_S`` reproduces the old behaviour for the
regression suite.

Two indices are supplied as configured constants rather than derived from the
simulated state, because the testbed contains nothing that could identify them:

* ``X_ext`` (environmental / social externality) needs an energy or risk
  measure per deployment. That lives in the AEAP record, and the testbed's
  representative firms carry no AEAP. When AEAP records *are* supplied,
  :func:`externality_index_from_aeap` derives it.
* ``B_broad`` (broad ownership and benefit) needs per-firm ownership
  dispersion. In the testbed every household holds the market portfolio in
  proportion to wealth, so there is no cross-firm variation to measure.

Both default to zero, which is the neutral value: with a zero index the term
contributes nothing and the rate reduces to the eight remaining terms. They are
wired, bounded, tested and documented rather than invented.

Proposition 3 (boundedness and monotone comparative statics) is a property of
this module and is asserted directly in ``tests/unit/test_rate.py``.
"""

from __future__ import annotations

from typing import Dict, Iterable, Mapping, Optional, Sequence

import numpy as np

from ..config import RateConfig

__all__ = ["RATE_TERMS", "POSITIVE_TERMS", "NEGATIVE_TERMS", "rate_terms",
           "raw_rate", "applied_rate", "rate_weights", "clip_map",
           "logistic_map", "substitution_index", "rent_index",
           "displacement_index", "revenue_erosion_index", "augmentation_index",
           "externality_index_from_aeap", "lipschitz_constant",
           "classifier_error_bound"]

# Order matters only for reporting; the sum is order-independent.
POSITIVE_TERMS = ("S", "C_rent", "E_disp", "X_ext", "R_rev")
NEGATIVE_TERMS = ("A_aug", "T_train", "B_broad", "N_new")
RATE_TERMS = POSITIVE_TERMS + NEGATIVE_TERMS

_WEIGHT_ATTR = {
    "S": "w_alpha",
    "C_rent": "w_beta",
    "E_disp": "w_gamma_e",
    "X_ext": "w_delta",
    "R_rev": "w_eta",
    "A_aug": "w_theta",
    "T_train": "w_lambda",
    "B_broad": "w_mu",
    "N_new": "w_nu",
}


def rate_weights(cfg: RateConfig) -> Dict[str, float]:
    """Signed coefficient on each index: positive group ``+w``, negative ``-w``."""
    out: Dict[str, float] = {}
    for term in RATE_TERMS:
        w = float(getattr(cfg, _WEIGHT_ATTR[term]))
        if w < 0.0:
            raise ValueError(
                f"rate weight {_WEIGHT_ATTR[term]} must be non-negative "
                f"(Proposition 3 assumes it); got {w}")
        if term not in cfg.enabled_terms:
            w = 0.0
        out[term] = w if term in POSITIVE_TERMS else -w
    return out


# ---------------------------------------------------------------------------
# Index constructors
# ---------------------------------------------------------------------------

def substitution_index(labour_cost_share, labour_cost_share_0):
    """S_i: fall in the firm's labour cost share against its pre-diffusion level."""
    base = np.maximum(np.asarray(labour_cost_share_0, dtype=float), 1e-9)
    return np.clip((base - np.asarray(labour_cost_share, dtype=float)) / base, 0.0, 1.0)


def rent_index(markup):
    """C_rent_i: markup rescaled to [0, 1] across the firm population."""
    m = np.asarray(markup, dtype=float)
    lo, hi = m.min(), m.max()
    return (m - lo) / max(hi - lo, 1e-9)


def displacement_index(efficiency, exposure):
    """E_disp: realised, exposure-weighted loss of worker efficiency.

    Economy-wide rather than per-firm: the testbed's displacement channel acts
    on households through aggregate automation growth and cannot be traced to
    an individual firm. Recorded as a limitation rather than papered over.
    """
    e = np.asarray(exposure, dtype=float)
    eff = np.asarray(efficiency, dtype=float)
    weighted = float((e * eff).sum() / max(e.sum(), 1e-12))
    return float(np.clip(1.0 - weighted, 0.0, 1.0))


def revenue_erosion_index(wage_bill_share, wage_bill_share_0):
    """R_rev_i: erosion of the payroll base, Eq. (2)'s ``W_H / Y`` falling.

    Distinct from ``S_i``: ``S`` compares labour against machines within the
    firm's cost mix, whereas ``R_rev`` compares the wage bill against output,
    which is the quantity the payroll tax base actually depends on.
    """
    base = np.maximum(np.asarray(wage_bill_share_0, dtype=float), 1e-9)
    return np.clip((base - np.asarray(wage_bill_share, dtype=float)) / base, 0.0, 1.0)


def augmentation_index(wage, wage_0, scale: float = 0.50):
    """A_aug: real wage growth against the pre-diffusion wage, capped at one.

    Employment retention on its own is not evidence of augmentation in this
    model, because the wage clears the market; only a higher wage is.
    """
    return float(np.clip((wage / max(wage_0, 1e-12) - 1.0) / max(scale, 1e-12), 0.0, 1.0))


def externality_index_from_aeap(records: Sequence[Mapping],
                                output_key: str = "output",
                                energy_key: str = "energy") -> float:
    """X_ext from AEAP energy intensity, normalised across the supplied records.

    Returns 0.0 for an empty record set, which is the neutral value.
    """
    if not records:
        return 0.0
    intensity = np.array([
        float(r.get(energy_key, 0.0)) / max(float(r.get(output_key, 0.0)), 1e-12)
        for r in records], dtype=float)
    lo, hi = intensity.min(), intensity.max()
    if hi - lo < 1e-12:
        return float(np.clip(intensity.mean(), 0.0, 1.0))
    return float(np.clip(((intensity - lo) / (hi - lo)).mean(), 0.0, 1.0))


# ---------------------------------------------------------------------------
# Assembly
# ---------------------------------------------------------------------------

def rate_terms(cfg: RateConfig, n_firms: int,
               endogenous: Optional[Mapping[str, object]] = None
               ) -> Dict[str, np.ndarray]:
    """Resolve every index to a per-firm array in [0, 1].

    ``endogenous`` supplies the indices the caller has derived from the current
    state. A term whose ``source_*`` is ``"fixed"``, or for which no endogenous
    value was supplied, falls back to its configured constant.
    """
    endogenous = endogenous or {}
    out: Dict[str, np.ndarray] = {}
    for term in RATE_TERMS:
        source = getattr(cfg, f"source_{term}")
        if source not in ("endogenous", "fixed"):
            raise ValueError(f"source_{term} must be 'endogenous' or 'fixed', "
                             f"got {source!r}")
        if source == "endogenous" and term in endogenous:
            value = endogenous[term]
        else:
            value = getattr(cfg, f"fixed_{term}")
        arr = np.broadcast_to(np.asarray(value, dtype=float), (n_firms,)).astype(float)
        if np.any(arr < -1e-12) or np.any(arr > 1.0 + 1e-12):
            raise ValueError(
                f"rate index {term} must lie in [0, 1] (Eq. 11); "
                f"got range [{arr.min():.6g}, {arr.max():.6g}]")
        out[term] = np.clip(arr, 0.0, 1.0)
    return out


def raw_rate(cfg: RateConfig, indices: Mapping[str, np.ndarray]) -> np.ndarray:
    """The raw score ``r~_i`` of Eq. (11), before the bounding map."""
    weights = rate_weights(cfg)
    first = next(iter(indices.values()))
    acc = np.full(np.shape(first), float(cfg.r0), dtype=float)
    for term, w in weights.items():
        if w == 0.0:
            continue
        acc = acc + w * np.asarray(indices[term], dtype=float)
    return acc


def clip_map(raw, rmin: float, rmax: float):
    return np.clip(raw, rmin, rmax)


def logistic_map(raw, rmin: float, rmax: float):
    """The differentiable alternative: ``rmin + (rmax-rmin) * sigmoid(raw)``."""
    return rmin + (rmax - rmin) / (1.0 + np.exp(-np.asarray(raw, dtype=float)))


def applied_rate(cfg: RateConfig, n_firms: int,
                 endogenous: Optional[Mapping[str, object]] = None,
                 return_components: bool = False):
    """The applied rate ``r_i`` of Eq. (12).

    With ``flat_rate`` set (ablation A1) every firm receives ``r0``, bounded,
    and no index is consulted.
    """
    if cfg.flat_rate:
        r = np.full((n_firms,), float(np.clip(cfg.r0, cfg.rmin, cfg.rmax)))
        if return_components:
            return r, {"raw": r.copy(), "indices": {}, "weights": {}}
        return r

    endogenous = dict(endogenous or {})
    if cfg.legacy_rrev_uses_S and "S" in endogenous:
        endogenous["R_rev"] = endogenous["S"]

    indices = rate_terms(cfg, n_firms, endogenous)
    raw = raw_rate(cfg, indices)
    mapper = clip_map if cfg.map_kind == "clip" else logistic_map
    if cfg.map_kind not in ("clip", "logistic"):
        raise ValueError(f"rate map_kind must be 'clip' or 'logistic', got {cfg.map_kind!r}")
    r = mapper(raw, cfg.rmin, cfg.rmax)
    if return_components:
        return r, {"raw": raw, "indices": indices, "weights": rate_weights(cfg)}
    return r


# ---------------------------------------------------------------------------
# Proposition 4 support
# ---------------------------------------------------------------------------

def lipschitz_constant(cfg: RateConfig) -> float:
    """``alpha + theta``: the bound on rate error from a misclassified episode.

    Proposition 4 states ``|E[r_i] - r_i*| <= epsilon * (alpha + theta)`` when
    classification errs at rate ``epsilon``, because misclassification moves
    only the substitution and augmentation coordinates and each index lies in
    [0, 1].
    """
    return float(cfg.w_alpha + cfg.w_theta)


def classifier_error_bound(cfg: RateConfig, epsilon: float, acb=None):
    """The Proposition 4 rate bound, and the revenue bound when ``acb`` is given."""
    bound = float(epsilon) * lipschitz_constant(cfg)
    if acb is None:
        return bound
    return bound, bound * np.asarray(acb, dtype=float)
