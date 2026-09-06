"""Four-channel waterfall (Prop. 5) and cross-border nexus (Prop. 8)."""

from __future__ import annotations

import numpy as np
import pytest

from cdos.model.nexus import (NEXUS_COMPONENTS, apply_shifting, apportion,
                              leakage, nexus_shares, validate_shares)
from cdos.model.waterfall import CHANNELS, feasible, shield_net_cost, split


# ---------------------------------------------------------------------------
# Waterfall
# ---------------------------------------------------------------------------

def test_worked_example_allocation():
    """SAC of 1.578 MU at omega=.40, kappa=.25, sigma_T=.15, residual .20."""
    w = split(1.578, 0.40, 0.25, 0.15)
    assert w.fund == pytest.approx(0.631, abs=1e-3)
    assert w.shield == pytest.approx(0.394, abs=1e-3)
    assert w.transition == pytest.approx(0.237, abs=1e-3)
    assert w.general == pytest.approx(0.316, abs=1e-3)


def test_split_is_exhaustive():
    w = split(100.0, 0.40, 0.25, 0.15)
    assert w.total == pytest.approx(100.0, rel=1e-12)


def test_all_four_channels_present():
    assert set(CHANNELS) == {"fund", "shield", "transition", "general"}


def test_feasibility_boundary():
    assert feasible(0.40, 0.25, 0.15) is True
    assert feasible(0.50, 0.30, 0.20) is True      # exactly one
    assert feasible(0.50, 0.30, 0.25) is False


def test_infeasible_split_raises():
    with pytest.raises(ValueError, match="Proposition 5"):
        split(100.0, 0.6, 0.3, 0.2)


def test_negative_share_is_infeasible():
    assert feasible(-0.01, 0.25, 0.15) is False


def test_channels_are_independently_ablatable():
    full = split(100.0, 0.40, 0.25, 0.15)
    no_fund = split(100.0, 0.0, 0.25, 0.15)
    assert no_fund.fund == 0.0
    assert no_fund.general == pytest.approx(full.general + full.fund)
    assert no_fund.shield == pytest.approx(full.shield)


def test_shield_net_cost_below_mechanical_cost():
    """Eq. (18): the base expansion offsets part of the mechanical cost."""
    mechanical = 0.25 * 100.0
    net = shield_net_cost(0.25, 100.0, eps_l=0.30, tau_l=0.38)
    assert 0 < net < mechanical


def test_shield_net_cost_equals_mechanical_when_supply_is_inelastic():
    assert shield_net_cost(0.25, 100.0, eps_l=0.0, tau_l=0.38) == pytest.approx(25.0)


# ---------------------------------------------------------------------------
# Nexus
# ---------------------------------------------------------------------------

def _components(n=10, j=3, seed=0):
    rng = np.random.default_rng(seed)
    out = {}
    for c in NEXUS_COMPONENTS:
        m = rng.random((n, j))
        out[c] = m / m.sum(axis=1, keepdims=True)
    return out


def test_proposition8_shares_sum_to_one():
    nx = nexus_shares(_components())
    np.testing.assert_allclose(nx.sum(axis=1), 1.0, rtol=1e-12)


def test_proposition8_apportionment_is_exhaustive():
    """sum_j SAC_ij == SAC_i exactly."""
    nx = nexus_shares(_components(n=25))
    sac = np.linspace(1.0, 50.0, 25)
    allocated = apportion(sac, nx)
    np.testing.assert_allclose(allocated.sum(axis=1), sac, rtol=1e-12)


def test_three_jurisdictions_supported():
    nx = nexus_shares(_components(n=5, j=3))
    assert nx.shape == (5, 3)


def test_shares_not_summing_to_one_are_rejected():
    with pytest.raises(ValueError, match="sum to one"):
        validate_shares(np.array([[0.5, 0.3, 0.1]]))


def test_negative_share_rejected():
    with pytest.raises(ValueError, match="negative"):
        validate_shares(np.array([[1.2, -0.2]]))


def test_missing_component_rejected():
    comps = _components()
    del comps["operations"]
    with pytest.raises(KeyError, match="operations"):
        nexus_shares(comps)


def test_component_weights_must_sum_to_one():
    with pytest.raises(ValueError, match="sum to one"):
        nexus_shares(_components(), weights=[0.5, 0.5, 0.5, 0.5])


def test_wrong_number_of_component_weights_rejected():
    with pytest.raises(ValueError, match="four component weights"):
        nexus_shares(_components(), weights=[0.5, 0.5])


def test_shifting_preserves_exhaustiveness():
    """Proposition 8 must still hold exactly after strategic relocation."""
    nx = nexus_shares(_components(n=20))
    shifted = apply_shifting(nx, [1.0, 0.5, 1.5], elasticity=0.4)
    np.testing.assert_allclose(shifted.sum(axis=1), 1.0, rtol=1e-12)


def test_shifting_moves_base_towards_the_cheaper_jurisdiction():
    nx = np.array([[1 / 3, 1 / 3, 1 / 3]])
    shifted = apply_shifting(nx, [1.0, 0.5, 1.5], elasticity=0.5)
    assert shifted[0, 1] > nx[0, 1]      # cheapest gains
    assert shifted[0, 2] < nx[0, 2]      # dearest loses


def test_zero_elasticity_is_a_no_op():
    nx = nexus_shares(_components(n=8))
    np.testing.assert_allclose(apply_shifting(nx, [1.0, 0.8, 1.2], 0.0), nx)


def test_wrong_multiplier_length_rejected():
    nx = nexus_shares(_components(n=4, j=3))
    with pytest.raises(ValueError, match="jurisdictions"):
        apply_shifting(nx, [1.0, 1.0], 0.1)


def test_leakage_is_zero_without_rate_differentials():
    nx = nexus_shares(_components(n=10))
    sac = np.full(10, 5.0)
    before = apportion(sac, nx)
    after = apportion(sac, apply_shifting(nx, [1.0, 1.0, 1.0], 0.5))
    assert leakage(before, after) == pytest.approx(0.0, abs=1e-12)


def test_leakage_is_positive_when_rates_differ_and_base_moves():
    """Revenue falls when the base relocates to a lower-rate jurisdiction."""
    nx = np.tile(np.array([[1 / 3, 1 / 3, 1 / 3]]), (10, 1))
    rates = np.array([1.0, 0.5, 1.5])
    sac = np.full(10, 6.0)
    before = (apportion(sac, nx) * rates).sum()
    shifted = apply_shifting(nx, rates, elasticity=0.6)
    after = (apportion(sac, shifted) * rates).sum()
    assert after < before
