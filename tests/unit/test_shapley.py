"""Shapley attribution: efficiency, symmetry, degeneracy, and Proposition 2."""

from __future__ import annotations

import numpy as np
import pytest

from cdos.model.production import firm_block
from cdos.model.shapley import (
    FIVE_FACTORS,
    coalition_value,
    cost_share_attribution,
    dpsi_dM,
    marginal_below_price_condition,
    shapley_five_factor,
    shapley_machine,
)

SIGMA, GAMMA = 1.5, 0.85


def _draw(n=200, seed=0):
    rng = np.random.default_rng(seed)
    alpha = rng.uniform(0.25, 0.90, n)
    A = np.exp(rng.normal(0, 0.35, n))
    L = rng.uniform(0.5, 5.0, n)
    M = rng.uniform(0.5, 5.0, n)
    return alpha, A, L, M


# ---------------------------------------------------------------------------
# Two-factor game
# ---------------------------------------------------------------------------

def test_two_factor_efficiency():
    """psi_L + psi_M == v({L, M}) exactly."""
    alpha, A, L, M = _draw()
    psi_M, v = shapley_machine(alpha, A, L, M, SIGMA, GAMMA)
    rho = 1.0 - 1.0 / SIGMA
    vL = A * (alpha * L ** rho) ** (GAMMA / rho)
    vM = A * ((1 - alpha) * M ** rho) ** (GAMMA / rho)
    psi_L = 0.5 * vL + 0.5 * (v - vM)
    np.testing.assert_allclose(psi_L + psi_M, v, rtol=1e-12)


def test_two_factor_bounded_by_total():
    alpha, A, L, M = _draw()
    psi_M, v = shapley_machine(alpha, A, L, M, SIGMA, GAMMA)
    assert np.all(psi_M >= 0.0)
    assert np.all(psi_M <= v + 1e-12)


def test_dpsi_dm_matches_central_difference():
    alpha, A, L, M = _draw(50, seed=3)
    analytic = dpsi_dM(alpha, A, L, M, SIGMA, GAMMA)
    h = 1e-6
    up, _ = shapley_machine(alpha, A, L, M + h, SIGMA, GAMMA)
    dn, _ = shapley_machine(alpha, A, L, M - h, SIGMA, GAMMA)
    np.testing.assert_allclose(analytic, (up - dn) / (2 * h), rtol=1e-5)


def test_cobb_douglas_limit_is_finite():
    """sigma -> 1 is a removable singularity, not a NaN."""
    alpha, A, L, M = _draw(50, seed=4)
    psi_M, v = shapley_machine(alpha, A, L, M, 1.0, GAMMA)
    assert np.all(np.isfinite(psi_M)) and np.all(np.isfinite(v))
    np.testing.assert_allclose(psi_M, 0.5 * v, rtol=1e-12)


# ---------------------------------------------------------------------------
# Proposition 2 / audit F1
# ---------------------------------------------------------------------------

def test_proposition2_holds_identically_at_paper_calibration():
    """At gamma=0.85, sigma=1.5 the inequality cannot fail (audit F1).

    Universal incidence across every firm and quarter is therefore a property
    of the calibration, not evidence about the world.
    """
    rep = marginal_below_price_condition(1.5, 0.85)
    assert rep["holds_identically"] is True
    assert rep["is_informative"] is False


def test_proposition2_becomes_informative_when_gamma_below_rho():
    rep = marginal_below_price_condition(sigma=8.0, gamma=0.80)
    assert rep["rho"] == pytest.approx(0.875)
    assert rep["holds_identically"] is False
    assert rep["is_informative"] is True


@pytest.mark.parametrize("sigma", [1.2, 1.5, 2.0, 3.0, 5.0, 8.0])
def test_marginal_ratio_equals_closed_form(sigma):
    """dv({M})/dM / dY/dM == s_M ** (gamma/rho - 1), exactly."""
    rng = np.random.default_rng(0)
    n = 2000
    alpha = rng.uniform(0.25, 0.90, n)
    A = np.exp(rng.normal(0, 0.35, n))
    pm = rng.uniform(0.3, 1.0, n)
    rho = 1.0 - 1.0 / sigma
    L, M, _, _ = firm_block(alpha, A, 1.0, pm, sigma, GAMMA)
    S = alpha * L ** rho + (1 - alpha) * M ** rho
    dvM = A * (1 - alpha) ** (GAMMA / rho) * GAMMA * M ** (GAMMA - 1)
    dY = A * GAMMA * S ** (GAMMA / rho - 1) * (1 - alpha) * M ** (rho - 1)
    closed = ((1 - alpha) * M ** rho / S) ** (GAMMA / rho - 1)
    np.testing.assert_allclose(dvM / dY, closed, rtol=1e-9)
    # And the inequality holds precisely when gamma > rho.
    assert (float((dvM / dY).max()) < 1.0) == (GAMMA > rho)


# ---------------------------------------------------------------------------
# Five-factor game
# ---------------------------------------------------------------------------

def _five_inputs(n=40, seed=1):
    rng = np.random.default_rng(seed)
    return {f: rng.uniform(0.5, 4.0, n) for f in FIVE_FACTORS}, \
        np.exp(rng.normal(0, 0.3, n))


def test_five_factor_efficiency():
    """sum_i psi_i == v(N) over all 31 coalitions, to floating point."""
    inputs, A = _five_inputs()
    psi = shapley_five_factor(inputs, A, SIGMA, GAMMA)
    total = sum(psi.values())
    grand = coalition_value(inputs, FIVE_FACTORS,
                            {f: 0.2 for f in FIVE_FACTORS}, A, SIGMA, GAMMA)
    np.testing.assert_allclose(total, grand, rtol=1e-11)


def test_five_factor_evaluates_all_31_coalitions():
    assert 2 ** len(FIVE_FACTORS) - 1 == 31


def test_five_factor_symmetry():
    """Identical inputs and shares give identical Shapley values."""
    n = 20
    inputs = {f: np.full(n, 2.0) for f in FIVE_FACTORS}
    A = np.ones(n)
    psi = shapley_five_factor(inputs, A, SIGMA, GAMMA,
                              {f: 0.2 for f in FIVE_FACTORS})
    values = list(psi.values())
    for v in values[1:]:
        np.testing.assert_allclose(v, values[0], rtol=1e-12)


def test_five_factor_null_player_gets_nothing_extra():
    """A factor with a zero share contributes nothing and receives ~nothing."""
    n = 20
    inputs = {f: np.full(n, 2.0) for f in FIVE_FACTORS}
    A = np.ones(n)
    shares = {"H": 0.4, "A": 0.3, "R": 0.3, "D": 0.0, "K": 0.0}
    psi = shapley_five_factor(inputs, A, SIGMA, GAMMA, shares)
    assert abs(float(psi["D"].mean())) < 1e-9
    assert abs(float(psi["K"].mean())) < 1e-9


def test_five_factor_monotone_in_own_input():
    inputs, A = _five_inputs(30, seed=5)
    base = shapley_five_factor(inputs, A, SIGMA, GAMMA)
    more = dict(inputs)
    more["R"] = inputs["R"] * 1.5
    up = shapley_five_factor(more, A, SIGMA, GAMMA)
    assert float(up["R"].mean()) > float(base["R"].mean())


def test_five_factor_zero_input_is_finite():
    inputs, A = _five_inputs(10, seed=6)
    inputs["D"] = np.zeros(10)
    psi = shapley_five_factor(inputs, A, SIGMA, GAMMA)
    for v in psi.values():
        assert np.all(np.isfinite(v))


def test_five_factor_cobb_douglas_efficiency():
    inputs, A = _five_inputs(15, seed=7)
    psi = shapley_five_factor(inputs, A, 1.0, GAMMA)
    grand = coalition_value(inputs, FIVE_FACTORS,
                            {f: 0.2 for f in FIVE_FACTORS}, A, 1.0, GAMMA)
    np.testing.assert_allclose(sum(psi.values()), grand, rtol=1e-10)


def test_missing_factor_input_raises():
    inputs, A = _five_inputs(5)
    del inputs["K"]
    with pytest.raises(KeyError):
        shapley_five_factor(inputs, A, SIGMA, GAMMA)


# ---------------------------------------------------------------------------
# Cost-share alternative (ablation A2)
# ---------------------------------------------------------------------------

def test_cost_share_is_exhaustive():
    rng = np.random.default_rng(2)
    costs = {"L": rng.uniform(1, 5, 50), "M": rng.uniform(1, 5, 50)}
    total = rng.uniform(10, 20, 50)
    shares = cost_share_attribution(costs, total)
    np.testing.assert_allclose(shares["L"] + shares["M"], total, rtol=1e-12)


def test_cost_share_differs_from_shapley():
    """The manuscript's central claim is that these are not the same thing."""
    alpha, A, L, M = _draw(100, seed=8)
    psi_M, Y = shapley_machine(alpha, A, L, M, SIGMA, GAMMA)
    cs = cost_share_attribution({"L": 1.0 * L, "M": 1.0 * M}, Y)["M"]
    assert not np.allclose(psi_M, cs, rtol=1e-3)
