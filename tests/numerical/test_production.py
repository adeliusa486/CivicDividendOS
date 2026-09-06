"""Numerical robustness of production, market clearing and the CD singularity."""

from __future__ import annotations

import numpy as np
import pytest

from cdos.model.production import (
    ces_aggregate,
    ces_unit_cost,
    clear_wage,
    firm_block,
    is_cobb_douglas,
    labour_supply,
)

GAMMA = 0.85


def _firms(n=100, seed=0):
    rng = np.random.default_rng(seed)
    alpha = np.clip(rng.beta(6, 4, n), 0.25, 0.90)
    A = np.exp(rng.normal(0, 0.35, n))
    return alpha, A / A.mean()


@pytest.mark.parametrize("sigma", [0.5, 0.8, 1.2, 1.5, 2.0, 3.0, 5.0, 8.0])
def test_no_nans_across_sigma(sigma):
    alpha, A = _firms()
    L, M, Y, c = firm_block(alpha, A, 1.0, 0.7, sigma, GAMMA)
    for arr in (L, M, Y, c):
        assert np.all(np.isfinite(arr)), f"non-finite output at sigma={sigma}"
        assert np.all(arr > 0)


def test_cobb_douglas_singularity_is_handled():
    """sigma = 1 exactly must not produce a division by zero."""
    alpha, A = _firms()
    assert is_cobb_douglas(1.0)
    L, M, Y, c = firm_block(alpha, A, 1.0, 0.7, 1.0, GAMMA)
    for arr in (L, M, Y, c):
        assert np.all(np.isfinite(arr))


def test_cobb_douglas_limit_is_continuous():
    """Approaching sigma -> 1 must converge to the CD branch."""
    alpha, A = _firms(50, seed=2)
    target = ces_unit_cost(alpha, 1.0, 0.7, 1.0)
    for eps in (1e-3, 1e-4, 1e-5):
        near = ces_unit_cost(alpha, 1.0, 0.7, 1.0 + eps)
        np.testing.assert_allclose(near, target, rtol=50 * eps)


def test_cobb_douglas_aggregate_limit():
    alpha, _ = _firms(30, seed=3)
    L = np.full(30, 2.0)
    M = np.full(30, 3.0)
    target = ces_aggregate(alpha, L, M, 1.0)
    near = ces_aggregate(alpha, L, M, 1.0 + 1e-5)
    np.testing.assert_allclose(near, target, rtol=1e-3)


def test_shephard_lemma_holds_in_cd_branch():
    """Factor demands must be the derivatives of the cost function."""
    alpha, A = _firms(20, seed=4)
    w, pm, h = 1.0, 0.7, 1e-6
    L, M, Y, c = firm_block(alpha, A, w, pm, 1.0, GAMMA)
    X = (GAMMA * A / c) ** (1.0 / (1.0 - GAMMA))
    dc_dw = (ces_unit_cost(alpha, w + h, pm, 1.0)
             - ces_unit_cost(alpha, w - h, pm, 1.0)) / (2 * h)
    np.testing.assert_allclose(L / X, dc_dw, rtol=1e-5)


@pytest.mark.parametrize("sigma", [1.2, 1.5, 2.0, 3.0])
def test_wage_clears_the_market(sigma):
    alpha, A = _firms(200, seed=5)
    sup_scale, tau_l, eps_l = 900.0, 0.35, 0.30
    w = clear_wage(alpha, A, 0.7, sup_scale, tau_l, eps_l, sigma, GAMMA)
    L, _, _, _ = firm_block(alpha, A, w, 0.7, sigma, GAMMA)
    demand = float(L.sum())
    supply = labour_supply(sup_scale, w, tau_l, eps_l)
    assert abs(demand - supply) / supply < 1e-6


def test_bisection_expands_a_bracket_that_misses_the_root():
    """A root outside [lo, hi] must widen the bracket, not return an endpoint."""
    alpha, A = _firms(50, seed=6)
    w = clear_wage(alpha, A, 0.7, 900.0, 0.35, 0.30, 1.5, GAMMA,
                   lo=1e4, hi=1e5, verify_bracket=True)
    L, _, _, _ = firm_block(alpha, A, w, 0.7, 1.5, GAMMA)
    assert abs(float(L.sum()) - labour_supply(900.0, w, 0.35, 0.30)) \
        / labour_supply(900.0, w, 0.35, 0.30) < 1e-6
    assert w < 1e4


def test_more_iterations_converge_monotonically():
    alpha, A = _firms(50, seed=7)
    ws = [clear_wage(alpha, A, 0.7, 900.0, 0.35, 0.30, 1.5, GAMMA, iters=n)
          for n in (10, 20, 28, 40, 60)]
    errs = []
    for w in ws:
        L, _, _, _ = firm_block(alpha, A, w, 0.7, 1.5, GAMMA)
        errs.append(abs(float(L.sum()) - labour_supply(900.0, w, 0.35, 0.30)))
    assert errs[-1] <= errs[0]
    assert errs[-1] < 1e-3


def test_labour_demand_falls_as_the_wage_rises():
    alpha, A = _firms(50, seed=8)
    prev = np.inf
    for w in (0.5, 1.0, 2.0, 4.0):
        L, _, _, _ = firm_block(alpha, A, w, 0.7, 1.5, GAMMA)
        cur = float(L.sum())
        assert cur < prev
        prev = cur


def test_machine_demand_rises_as_the_machine_price_falls():
    alpha, A = _firms(50, seed=9)
    prev = 0.0
    for pm in (1.0, 0.8, 0.6, 0.4):
        _, M, _, _ = firm_block(alpha, A, 1.0, pm, 1.5, GAMMA)
        cur = float(M.sum())
        assert cur > prev
        prev = cur


def test_higher_sigma_gives_more_substitution():
    """A larger elasticity must move the factor mix further for the same prices."""
    alpha, A = _firms(200, seed=10)
    shares = []
    for sigma in (1.2, 2.0, 5.0):
        L, M, _, _ = firm_block(alpha, A, 1.0, 0.5, sigma, GAMMA)
        shares.append(float((0.5 * M).sum() / (1.0 * L + 0.5 * M).sum()))
    assert shares[0] < shares[1] < shares[2]


def test_extreme_prices_stay_finite():
    alpha, A = _firms(20, seed=11)
    for pm in (1e-4, 1e4):
        L, M, Y, c = firm_block(alpha, A, 1.0, pm, 1.5, GAMMA)
        assert np.all(np.isfinite(L)) and np.all(np.isfinite(M))
        assert np.all(np.isfinite(Y)) and np.all(np.isfinite(c))
