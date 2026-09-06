"""The ten-term rate function: bounds, monotonicity, and the worked example."""

from __future__ import annotations

import numpy as np
import pytest

from cdos.config import RateConfig
from cdos.model.rate import (
    NEGATIVE_TERMS,
    POSITIVE_TERMS,
    RATE_TERMS,
    applied_rate,
    augmentation_index,
    classifier_error_bound,
    displacement_index,
    externality_index_from_aeap,
    lipschitz_constant,
    logistic_map,
    rate_terms,
    rate_weights,
    rent_index,
    revenue_erosion_index,
    substitution_index,
)


def paper_weights() -> RateConfig:
    """Table VII of the manuscript, verbatim."""
    return RateConfig(r0=0.08, rmin=0.0, rmax=0.25,
                      w_alpha=0.10, w_beta=0.06, w_gamma_e=0.05,
                      w_delta=0.04, w_eta=0.05,
                      w_theta=0.09, w_lambda=0.07, w_mu=0.05, w_nu=0.06)


def _fixed(cfg: RateConfig, **values) -> RateConfig:
    cfg = RateConfig(**{**cfg.__dict__})
    for term, value in values.items():
        setattr(cfg, f"source_{term}", "fixed")
        setattr(cfg, f"fixed_{term}", value)
    return cfg


# ---------------------------------------------------------------------------
# The worked example: Table VII must reproduce exactly
# ---------------------------------------------------------------------------

def test_worked_example_substitution_case():
    """Section 'Rate and Liability': r~ = 0.1160, SAC = 1.578 MU on ACB = 13.6."""
    cfg = _fixed(paper_weights(), S=0.62, C_rent=0.35, E_disp=0.48, X_ext=0.10,
                 R_rev=0.55, A_aug=0.40, T_train=0.55, B_broad=0.20, N_new=0.30)
    r = applied_rate(cfg, 1)
    assert float(r[0]) == pytest.approx(0.1160, abs=5e-5)
    assert float(r[0]) * 13.60 == pytest.approx(1.578, abs=1e-3)


def test_worked_example_augmentation_case():
    """The augmentation counterfactual: r~ = 0.0095, SAC = 0.129 MU."""
    cfg = _fixed(paper_weights(), S=0.15, C_rent=0.35, E_disp=0.10, X_ext=0.10,
                 R_rev=0.55, A_aug=0.85, T_train=0.55, B_broad=0.20, N_new=0.30)
    r = applied_rate(cfg, 1)
    assert float(r[0]) == pytest.approx(0.0095, abs=5e-5)
    assert float(r[0]) * 13.60 == pytest.approx(0.129, abs=1e-3)


def test_worked_example_liability_ratio():
    """The same base attracts a liability differing by a factor of ~12.2."""
    sub = _fixed(paper_weights(), S=0.62, C_rent=0.35, E_disp=0.48, X_ext=0.10,
                 R_rev=0.55, A_aug=0.40, T_train=0.55, B_broad=0.20, N_new=0.30)
    aug = _fixed(paper_weights(), S=0.15, C_rent=0.35, E_disp=0.10, X_ext=0.10,
                 R_rev=0.55, A_aug=0.85, T_train=0.55, B_broad=0.20, N_new=0.30)
    ratio = float(applied_rate(sub, 1)[0]) / float(applied_rate(aug, 1)[0])
    assert ratio == pytest.approx(12.2, abs=0.15)


def test_all_ten_terms_are_present():
    assert len(RATE_TERMS) == 9          # nine indices
    assert len(POSITIVE_TERMS) == 5 and len(NEGATIVE_TERMS) == 4
    # Ten terms in Eq. (11) counting the intercept r0.
    assert len(RATE_TERMS) + 1 == 10


# ---------------------------------------------------------------------------
# Proposition 3: boundedness and monotone comparative statics
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("seed", range(5))
def test_rate_is_bounded(seed):
    rng = np.random.default_rng(seed)
    cfg = paper_weights()
    for term in RATE_TERMS:
        setattr(cfg, f"source_{term}", "endogenous")
    endo = {t: rng.random(200) for t in RATE_TERMS}
    r = applied_rate(cfg, 200, endo)
    assert np.all(r >= cfg.rmin - 1e-15)
    assert np.all(r <= cfg.rmax + 1e-15)


@pytest.mark.parametrize("term", POSITIVE_TERMS)
def test_rate_non_decreasing_in_positive_terms(term):
    cfg = paper_weights()
    for t in RATE_TERMS:
        setattr(cfg, f"source_{t}", "endogenous")
    base = {t: np.full(1, 0.4) for t in RATE_TERMS}
    lo = applied_rate(cfg, 1, base)
    hi_idx = dict(base)
    hi_idx[term] = np.full(1, 0.9)
    hi = applied_rate(cfg, 1, hi_idx)
    assert float(hi[0]) >= float(lo[0])
    if getattr(cfg, {"S": "w_alpha", "C_rent": "w_beta", "E_disp": "w_gamma_e",
                     "X_ext": "w_delta", "R_rev": "w_eta"}[term]) > 0:
        assert float(hi[0]) > float(lo[0])   # strict inside the clip


@pytest.mark.parametrize("term", NEGATIVE_TERMS)
def test_rate_non_increasing_in_negative_terms(term):
    cfg = paper_weights()
    for t in RATE_TERMS:
        setattr(cfg, f"source_{t}", "endogenous")
    base = {t: np.full(1, 0.4) for t in RATE_TERMS}
    lo = applied_rate(cfg, 1, base)
    hi_idx = dict(base)
    hi_idx[term] = np.full(1, 0.9)
    hi = applied_rate(cfg, 1, hi_idx)
    assert float(hi[0]) <= float(lo[0])


def test_zero_index_gives_intercept_plus_nothing():
    cfg = paper_weights()
    for t in RATE_TERMS:
        setattr(cfg, f"source_{t}", "endogenous")
    r = applied_rate(cfg, 1, {t: np.zeros(1) for t in RATE_TERMS})
    assert float(r[0]) == pytest.approx(cfg.r0)


def test_extreme_indices_clip_at_bounds():
    cfg = paper_weights()
    for t in RATE_TERMS:
        setattr(cfg, f"source_{t}", "endogenous")
    high = {t: (np.ones(1) if t in POSITIVE_TERMS else np.zeros(1))
            for t in RATE_TERMS}
    low = {t: (np.zeros(1) if t in POSITIVE_TERMS else np.ones(1))
           for t in RATE_TERMS}
    assert float(applied_rate(cfg, 1, high)[0]) == pytest.approx(0.25)
    assert float(applied_rate(cfg, 1, low)[0]) == pytest.approx(0.0)


def test_augmentation_only_deployment_sits_at_the_floor():
    """The design condition on p. 9: S = 0 and A_aug = 1 should give r_min."""
    cfg = paper_weights()
    cfg.w_theta = 0.30      # theta >= r0 + beta*C + eta*R - r_min
    for t in RATE_TERMS:
        setattr(cfg, f"source_{t}", "endogenous")
    idx = {t: np.zeros(1) for t in RATE_TERMS}
    idx["A_aug"] = np.ones(1)
    idx["C_rent"] = np.full(1, 0.35)
    idx["R_rev"] = np.full(1, 0.55)
    assert float(applied_rate(cfg, 1, idx)[0]) == pytest.approx(cfg.rmin)


def test_negative_weight_is_rejected():
    cfg = paper_weights()
    cfg.w_alpha = -0.01
    with pytest.raises(ValueError, match="non-negative"):
        rate_weights(cfg)


def test_index_outside_unit_interval_is_rejected():
    cfg = paper_weights()
    cfg.source_S = "endogenous"
    with pytest.raises(ValueError, match=r"\[0, 1\]"):
        rate_terms(cfg, 1, {"S": np.array([1.5])})


def test_flat_rate_ablation_ignores_every_index():
    cfg = paper_weights()
    cfg.flat_rate = True
    for t in RATE_TERMS:
        setattr(cfg, f"source_{t}", "endogenous")
    r = applied_rate(cfg, 5, {t: np.ones(5) for t in RATE_TERMS})
    np.testing.assert_allclose(r, cfg.r0)


def test_logistic_map_is_bounded_and_monotone():
    lo = logistic_map(np.array([-50.0]), 0.0, 0.25)
    hi = logistic_map(np.array([50.0]), 0.0, 0.25)
    assert 0.0 <= float(lo[0]) < float(hi[0]) <= 0.25
    xs = np.linspace(-5, 5, 100)
    ys = logistic_map(xs, 0.0, 0.25)
    assert np.all(np.diff(ys) > 0)


def test_disabled_term_contributes_nothing():
    cfg = paper_weights()
    cfg.enabled_terms = [t for t in RATE_TERMS if t != "S"]
    cfg.source_S = "endogenous"
    for t in RATE_TERMS:
        setattr(cfg, f"source_{t}", "endogenous")
    idx = {t: np.zeros(1) for t in RATE_TERMS}
    a = applied_rate(cfg, 1, idx)
    idx["S"] = np.ones(1)
    b = applied_rate(cfg, 1, idx)
    assert float(a[0]) == pytest.approx(float(b[0]))


# ---------------------------------------------------------------------------
# Index constructors
# ---------------------------------------------------------------------------

def test_substitution_index_bounds():
    s = substitution_index(np.array([0.4, 0.6, 0.8]), np.array([0.6, 0.6, 0.6]))
    np.testing.assert_allclose(s, [1.0 / 3.0, 0.0, 0.0])


def test_revenue_erosion_is_distinct_from_substitution():
    """R_rev measures W/Y; S measures the labour share of factor cost."""
    s = substitution_index(np.array([0.50]), np.array([0.60]))
    r = revenue_erosion_index(np.array([0.30]), np.array([0.45]))
    assert float(s[0]) != pytest.approx(float(r[0]))


def test_rent_index_spans_unit_interval():
    idx = rent_index(np.array([0.02, 0.30, 0.60]))
    assert float(idx.min()) == 0.0 and float(idx.max()) == 1.0


def test_displacement_index_zero_when_nobody_displaced():
    assert displacement_index(np.ones(10), np.full(10, 0.5)) == pytest.approx(0.0)


def test_displacement_index_rises_with_efficiency_loss():
    a = displacement_index(np.full(10, 0.9), np.full(10, 0.5))
    b = displacement_index(np.full(10, 0.5), np.full(10, 0.5))
    assert b > a > 0


def test_augmentation_index_needs_wage_growth():
    assert augmentation_index(1.0, 1.0) == pytest.approx(0.0)
    assert augmentation_index(1.25, 1.0, 0.5) == pytest.approx(0.5)
    assert augmentation_index(2.0, 1.0, 0.5) == pytest.approx(1.0)


def test_externality_index_empty_registry_is_neutral():
    assert externality_index_from_aeap([]) == 0.0


def test_externality_index_from_aeap_bounded():
    records = [{"energy": 1.0, "output": 10.0}, {"energy": 5.0, "output": 10.0}]
    x = externality_index_from_aeap(records)
    assert 0.0 <= x <= 1.0


# ---------------------------------------------------------------------------
# Proposition 4
# ---------------------------------------------------------------------------

def test_lipschitz_constant_is_alpha_plus_theta():
    cfg = paper_weights()
    assert lipschitz_constant(cfg) == pytest.approx(0.10 + 0.09)


@pytest.mark.parametrize("eps", [0.0, 0.05, 0.10, 0.20])
def test_classifier_error_bound_scales_linearly(eps):
    cfg = paper_weights()
    assert classifier_error_bound(cfg, eps) == pytest.approx(eps * 0.19)


def test_classifier_revenue_bound_multiplies_the_base():
    cfg = paper_weights()
    rate_bound, rev_bound = classifier_error_bound(cfg, 0.10, np.array([13.6]))
    assert float(rev_bound[0]) == pytest.approx(rate_bound * 13.6)
