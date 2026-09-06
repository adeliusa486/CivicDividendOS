"""Fund dynamics and Proposition 6, including the audit's F2 finding."""

from __future__ import annotations

import numpy as np
import pytest

from cdos.model.fund import (check_stability, fund_step, half_life_years,
                             required_inflow, simulate_fund_ratio,
                             stability, steady_state_ratio)


# ---------------------------------------------------------------------------
# Table VI arithmetic (the audit confirmed this part is correct)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("r_f", [0.04, 0.05, 0.06])
@pytest.mark.parametrize("rho", [0.55, 0.75, 0.95])
def test_table6_rows_reproduce(r_f, rho):
    s, g = 0.0065, 0.03
    f_star = steady_state_ratio(s, g, rho, r_f)
    d_star = rho * r_f * f_star
    assert f_star > 0 and d_star > 0
    # The closed form must satisfy its own fixed point.
    a = (1 + (1 - rho) * r_f) / (1 + g)
    assert f_star == pytest.approx(a * f_star + s, rel=1e-12)


def test_paper_half_life_is_about_71_years():
    assert half_life_years(0.60, 0.05, 0.03) == pytest.approx(71.0, abs=1.0)


def test_required_inflow_design_rule():
    """kappa_d=0.02, r_f=0.05, rho=0.60, g=0.03 -> s=0.65%, f*=66.7%."""
    s = required_inflow(0.02, 0.05, 0.60, 0.03)
    assert s == pytest.approx(0.0065, abs=1e-4)
    assert steady_state_ratio(s, 0.03, 0.60, 0.05) == pytest.approx(0.667, abs=0.01)


# ---------------------------------------------------------------------------
# F2: the condition fails at the testbed's realised growth
# ---------------------------------------------------------------------------

def test_f2_condition_fails_at_realised_growth():
    """(1-rho) r_f = 0.0200 exceeds the realised g = 0.0166 of arm B0, seed 0."""
    rep = stability(rho=0.60, r_f=0.05, g=0.01655)
    assert rep.drift == pytest.approx(0.0200)
    assert rep.stable is False
    assert rep.margin < 0
    assert rep.steady_state is None and rep.half_life_years is None


def test_f2_condition_holds_at_the_assumed_growth():
    """The same calibration is stable at the g = 0.03 that Table VI assumes."""
    rep = stability(rho=0.60, r_f=0.05, g=0.03)
    assert rep.stable is True
    assert rep.margin == pytest.approx(0.01)


def test_steady_state_refuses_to_exist_when_divergent():
    with pytest.raises(ValueError, match="Proposition 6"):
        steady_state_ratio(0.0065, 0.0166, 0.60, 0.05)


def test_half_life_refuses_when_divergent():
    with pytest.raises(ValueError, match="divergent"):
        half_life_years(0.60, 0.05, 0.0166)


def test_stability_mode_require_raises():
    rep = stability(0.60, 0.05, 0.0166)
    with pytest.raises(RuntimeError, match="audit F2"):
        check_stability(rep, "require", context="test")


def test_stability_mode_warn_warns_but_continues():
    rep = stability(0.60, 0.05, 0.0166)
    with pytest.warns(RuntimeWarning, match="audit F2"):
        out = check_stability(rep, "warn")
    assert out is rep


def test_stability_mode_stress_is_silent():
    import warnings
    rep = stability(0.60, 0.05, 0.0166)
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        check_stability(rep, "stress")


def test_unknown_stability_mode_raises():
    with pytest.raises(ValueError, match="unknown stability_mode"):
        check_stability(stability(0.60, 0.05, 0.0166), "whatever")


# ---------------------------------------------------------------------------
# Recursion
# ---------------------------------------------------------------------------

def test_fund_step_matches_equation_19():
    fund, payout = fund_step(100.0, 0.0125, 5.0, 0.60)
    assert payout == pytest.approx(0.60 * 0.0125 * 100.0)
    assert fund == pytest.approx(100.0 * 1.0125 + 5.0 - payout)


def test_divergent_path_keeps_growing():
    """A divergent calibration must not be silently rescued to a steady state."""
    path = simulate_fund_ratio(s=0.0065, g=0.0166, rho=0.60, r_f=0.05,
                               periods=400)
    assert path[-1] > path[-41] > path[-81]
    growth_last_decade = path[-1] / path[-41] - 1.0
    assert growth_last_decade > 0.0


def test_convergent_path_flattens_to_the_closed_form():
    f_star = steady_state_ratio(0.0065, 0.03, 0.60, 0.05)
    path = simulate_fund_ratio(0.0065, 0.03, 0.60, 0.05, periods=4000)
    assert path[-1] == pytest.approx(f_star, rel=1e-6)


def test_simulated_path_matches_analytic_fixed_point_relation():
    a = (1 + (1 - 0.60) * 0.05) / (1 + 0.03)
    path = simulate_fund_ratio(0.0065, 0.03, 0.60, 0.05, periods=10)
    for t in range(10):
        assert path[t + 1] == pytest.approx(a * path[t] + 0.0065)
