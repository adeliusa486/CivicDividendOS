"""Cross-border Deployment Nexus apportionment, Eq. (23) and Proposition 8.

    Nexus_ij = w1 U_ij + w2 R_ij + w3 P_ij + w4 O_ij

with ``U`` usage, ``R`` revenue, ``P`` users and ``O`` physical operations, each
a share summing to one across jurisdictions ``j``. Proposition 8 then gives
``sum_j Nexus_ij = 1`` and ``sum_j SAC_ij = SAC_i`` exactly.

Server location is deliberately excluded from Eq. (23): it is the most cheaply
relocated of the candidate factors and therefore the most exposed to shifting.

The audited testbed had one jurisdiction and so, as the manuscript's own
limitations section concedes, could say nothing about leakage. This module adds
the multi-jurisdiction machinery and a strategic-shifting response so that E10
can measure it.

Nothing here asserts anything about current law. The nexus is a research
construct; adoption would require coordination with the OECD/G20 two-pillar
framework.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np

__all__ = ["NEXUS_COMPONENTS", "nexus_shares", "apportion", "validate_shares",
           "apply_shifting", "leakage"]

NEXUS_COMPONENTS = ("usage", "revenue", "users", "operations")


def validate_shares(shares, tol: float = 1e-9, name: str = "shares") -> np.ndarray:
    """Check that shares are non-negative and sum to one across jurisdictions.

    ``shares`` may be one dimensional (one row, applied to every firm) or two
    dimensional with firms on axis 0 and jurisdictions on axis 1.
    """
    arr = np.atleast_2d(np.asarray(shares, dtype=float))
    if np.any(arr < -tol):
        raise ValueError(f"{name} contains a negative share: min {arr.min():.6g}")
    totals = arr.sum(axis=1)
    bad = np.abs(totals - 1.0) > max(tol, 1e-9)
    if np.any(bad):
        idx = int(np.argmax(bad))
        raise ValueError(
            f"{name} must sum to one across jurisdictions (Proposition 8); "
            f"row {idx} sums to {totals[idx]:.12g}")
    return arr


def nexus_shares(components: dict[str, np.ndarray],
                 weights: Sequence[float] | None = None,
                 tol: float = 1e-9) -> np.ndarray:
    """Combine the four component share matrices into ``Nexus_ij``.

    Each component must itself be a valid share matrix. The component weights
    ``w1..w4`` must sum to one, which is what makes Proposition 8's conclusion
    follow from its premise.
    """
    missing = [c for c in NEXUS_COMPONENTS if c not in components]
    if missing:
        raise KeyError(f"missing nexus components {missing}")
    if weights is None:
        weights = [0.25] * 4
    w = np.asarray(weights, dtype=float)
    if w.size != 4:
        raise ValueError(f"nexus needs four component weights, got {w.size}")
    if np.any(w < -tol):
        raise ValueError("nexus component weights must be non-negative")
    if abs(float(w.sum()) - 1.0) > tol:
        raise ValueError(
            f"nexus component weights must sum to one, got {float(w.sum()):.12g}")
    acc = None
    for k, comp in zip(w, NEXUS_COMPONENTS, strict=False):
        mat = validate_shares(components[comp], tol, name=f"component {comp!r}")
        acc = k * mat if acc is None else acc + k * mat
    return validate_shares(acc, tol, name="nexus")


def apportion(sac, shares, tol: float = 1e-9) -> np.ndarray:
    """``SAC_ij = Nexus_ij * SAC_i``. Returns a firms-by-jurisdictions matrix.

    Exhaustive by construction: ``sum_j SAC_ij == SAC_i`` to floating point.
    """
    mat = validate_shares(shares, tol)
    sac = np.asarray(sac, dtype=float).reshape(-1, 1)
    if mat.shape[0] == 1 and sac.shape[0] != 1:
        mat = np.broadcast_to(mat, (sac.shape[0], mat.shape[1]))
    return sac * mat


def apply_shifting(shares, rate_multipliers, elasticity: float,
                   tol: float = 1e-9) -> np.ndarray:
    """Reallocate base towards jurisdictions with a lower effective rate.

    A firm moves ``elasticity`` of its share out of each jurisdiction in
    proportion to how far that jurisdiction's rate multiplier sits above the
    activity-weighted mean, redistributing it to those below. The result is
    renormalised, so Proposition 8 continues to hold exactly after shifting --
    which is the point: apportionment stays exhaustive even when the underlying
    activity has moved, and leakage shows up as revenue, not as a broken
    identity.
    """
    mat = validate_shares(shares, tol).astype(float).copy()
    mult = np.asarray(rate_multipliers, dtype=float)
    if mult.size != mat.shape[1]:
        raise ValueError(
            f"rate_multipliers has {mult.size} entries but there are "
            f"{mat.shape[1]} jurisdictions")
    if elasticity == 0.0:
        return mat
    mean_rate = (mat * mult).sum(axis=1, keepdims=True)
    adj = mat * (1.0 - elasticity * (mult[None, :] - mean_rate))
    adj = np.clip(adj, 0.0, None)
    totals = adj.sum(axis=1, keepdims=True)
    return adj / np.maximum(totals, 1e-12)


def leakage(sac_before, sac_after) -> float:
    """Fractional revenue lost to shifting, relative to the unshifted total."""
    before = float(np.sum(sac_before))
    after = float(np.sum(sac_after))
    return (before - after) / max(before, 1e-12)
