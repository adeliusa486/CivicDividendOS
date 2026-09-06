"""Configuration loading, manifests, metrics and the uncertainty machinery."""

from __future__ import annotations

import json

import numpy as np
import pytest

from cdos.config import Config, load_config, load_experiment
from cdos.eval.metrics import (
    atkinson,
    deadweight_loss,
    decile_shares,
    employment_metrics,
    equivalent_variation,
    gini,
    incidence_by_decile,
    poverty_rate,
    revenue_normalised,
)
from cdos.eval.uncertainty import (
    bootstrap_ci,
    combined_interval,
    effect_size,
    holm_bonferroni,
    paired_contrast,
    practical_significance,
    seed_adequacy,
)
from cdos.utils.manifest import Manifest, environment_state, file_digest, git_state

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

def test_defaults_are_the_paper_calibration():
    cfg = Config()
    assert cfg.technology.sigma == 1.5
    assert cfg.technology.gamma == 0.85
    assert cfg.fund.rho_payout == 0.60
    assert cfg.rate.r0 == 0.08 and cfg.rate.rmax == 0.25


def test_rho_sigma_and_proposition2_condition():
    cfg = Config()
    assert cfg.rho_sigma == pytest.approx(1.0 - 1.0 / 1.5)
    assert cfg.proposition2_condition is True
    steep = cfg.with_overrides({"technology.sigma": 8.0, "technology.gamma": 0.80})
    assert steep.proposition2_condition is False


def test_hash_is_stable_and_sensitive():
    a, b = Config(), Config()
    assert a.hash() == b.hash()
    assert a.with_overrides({"technology.sigma": 2.0}).hash() != a.hash()


def test_hash_is_sixteen_hex_characters():
    h = Config().hash()
    assert len(h) == 16 and all(c in "0123456789abcdef" for c in h)


def test_overrides_do_not_mutate_the_original():
    cfg = Config()
    cfg.with_overrides({"technology.sigma": 9.0})
    assert cfg.technology.sigma == 1.5


def test_unknown_override_key_is_rejected():
    with pytest.raises(KeyError, match="unknown configuration key"):
        Config().with_overrides({"technology.not_a_thing": 1.0})


def test_unknown_section_is_rejected():
    with pytest.raises(KeyError, match="unknown configuration section"):
        Config().with_overrides({"nope.sigma": 1.0})


def test_integers_are_coerced_to_float_where_expected():
    cfg = Config().with_overrides({"technology.sigma": 2})
    assert isinstance(cfg.technology.sigma, float)


def test_base_config_loads(root):
    cfg = load_config(root / "configs" / "base.yaml")
    assert cfg.legacy_mode is False
    assert cfg.fund.kappa == 0.25
    assert cfg.numerics.strict_accounting is True


def test_extends_chain_applies_parent_first(root):
    cfg = load_config(root / "configs" / "policies" / "audited_baseline.yaml")
    assert cfg.legacy_mode is True          # from the child
    assert cfg.technology.sigma == 1.5      # inherited from the parent
    assert cfg.fund.kappa == 0.0            # overridden by the child


@pytest.mark.parametrize("name", [
    "E01_sigma_gamma", "E02_budget", "E03_fund_stability",
    "E04_revenue_normalised", "E05_horizon", "E06_classifier_error",
    "E07_phi_sweep", "E08_rate_terms", "E09_payout_paradox",
    "E10_jurisdictions", "E11_avoidance", "E12_five_factor",
    "E13_calibration", "E14_decay", "E15_seed_adequacy", "E16_incidence",
    "E17_scalability", "A01_flat_rate", "A02_cost_share", "A03_fund_off",
    "A04_shield_off", "A05_transition_off", "A06_retraining_off",
    "A07_rent_term_off", "A08_augmentation_off", "A09_phi",
    "A10_displacement_off",
])
def test_every_experiment_file_loads(root, name):
    spec = load_experiment(root / "experiments" / f"{name}.yaml")
    assert spec["meta"]["experiment_id"]
    assert spec["meta"]["description"].strip()
    assert isinstance(spec["config"], Config)


def test_experiments_declare_distinct_ids(root):
    ids = [load_experiment(p)["meta"]["experiment_id"]
           for p in sorted((root / "experiments").glob("*.yaml"))]
    assert len(ids) == len(set(ids)), "two experiments share an experiment_id"
    assert len(ids) == 27


# ---------------------------------------------------------------------------
# Manifest
# ---------------------------------------------------------------------------

def test_manifest_records_provenance(tmp_path):
    m = Manifest.start("T01", description="test")
    probe = tmp_path / "probe.txt"
    probe.write_text("hello", encoding="utf-8")
    m.add_input(probe)
    out = m.finish().write(tmp_path / "manifest.json")
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["experiment_id"] == "T01"
    assert data["environment"]["packages"]["numpy"] == "1.26.4"
    assert data["environment"]["python"].startswith("3.11")
    assert data["started_at"] and data["finished_at"]
    assert len(next(iter(data["inputs"].values()))) == 64      # sha256 hex


def test_file_digest_is_sha256(tmp_path):
    p = tmp_path / "a.txt"
    p.write_bytes(b"abc")
    assert file_digest(p) == (
        "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad")


def test_git_state_reports_a_sha():
    state = git_state()
    assert state["sha"] is None or len(state["sha"]) == 40


def test_environment_state_lists_numpy():
    assert environment_state()["packages"]["numpy"] == "1.26.4"


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

def test_gini_bounds():
    assert gini(np.ones(100)) == pytest.approx(0.0, abs=1e-12)
    concentrated = np.zeros(1000)
    concentrated[0] = 1.0
    assert gini(concentrated) > 0.99


def test_gini_of_all_zeros_is_zero():
    assert gini(np.zeros(10)) == 0.0


def test_atkinson_zero_for_equal_incomes():
    assert atkinson(np.ones(100)) == pytest.approx(0.0, abs=1e-12)


def test_atkinson_rises_with_aversion():
    x = np.array([1.0, 2.0, 5.0, 10.0])
    assert atkinson(x, 0.2) < atkinson(x, 1.5)


def test_poverty_rate_relative_line():
    x = np.array([1.0] * 50 + [10.0] * 50)
    assert poverty_rate(x) == pytest.approx(0.50)


def test_employment_metrics_separate_the_three_quantities():
    """Audit F6: efficiency units are not headcount and not hours."""
    eff = np.array([1.0, 1.0, 0.25, 0.25, 0.8])
    m = employment_metrics(1234.5, eff, efficiency_floor=0.25)
    assert m["efficiency_units"] == 1234.5
    assert m["headcount"] == 3.0                 # two are at the floor
    assert np.isnan(m["hours"]), (
        "hours are not identified in this model and must not be invented")


def test_employment_metrics_report_hours_when_supplied():
    eff = np.ones(4)
    m = employment_metrics(100.0, eff, 0.25, hours_per_worker=35.0)
    assert m["hours"] == pytest.approx(140.0)


def test_deadweight_loss_is_zero_at_a_zero_tax():
    assert deadweight_loss(0.0, 1000.0, 0.3) == 0.0


def test_deadweight_loss_rises_convexly():
    a = deadweight_loss(0.10, 1000.0, 0.3)
    b = deadweight_loss(0.20, 1000.0, 0.3)
    assert b > 2 * a


def test_revenue_normalised_reports_both_directions():
    out = revenue_normalised(revenue=50.0, dwl=5.0, output=1000.0)
    assert out["revenue_per_dwl"] == pytest.approx(10.0)
    assert out["dwl_per_revenue"] == pytest.approx(0.1)
    assert out["revenue_share"] == pytest.approx(0.05)


def test_equivalent_variation_is_consumption_difference_without_leisure():
    ev = equivalent_variation(np.array([10.0]), np.array([8.0]))
    assert float(ev[0]) == pytest.approx(2.0)


def test_decile_shares_sum_to_one():
    shares = decile_shares(np.random.default_rng(0).lognormal(size=1000))
    assert shares.sum() == pytest.approx(1.0)
    assert shares[0] < shares[-1]


def test_incidence_by_decile_has_ten_entries():
    rng = np.random.default_rng(1)
    inc = incidence_by_decile(rng.random(500), rng.random(500))
    assert inc.shape == (10,)


# ---------------------------------------------------------------------------
# Uncertainty
# ---------------------------------------------------------------------------

def test_bootstrap_requires_a_declared_kind():
    with pytest.raises(ValueError, match="replication"):
        bootstrap_ci([1.0, 2.0], kind="whatever")


def test_bootstrap_interval_contains_the_mean():
    x = np.random.default_rng(0).normal(5.0, 1.0, 200)
    ci = bootstrap_ci(x, kind="replication")
    assert ci.lo < ci.point < ci.hi
    assert ci.kind == "replication"
    assert ci.n == 200


def test_bootstrap_rejects_an_empty_sample():
    with pytest.raises(ValueError, match="empty"):
        bootstrap_ci([])


def test_paired_contrast_requires_matched_samples():
    with pytest.raises(ValueError, match="common random numbers"):
        paired_contrast([1.0, 2.0, 3.0], [1.0, 2.0])


def test_paired_contrast_reports_replication_uncertainty():
    rng = np.random.default_rng(0)
    base = rng.normal(100, 10, 50)
    out = paired_contrast(base + 2.0, base)
    assert out["diff"]["kind"] == "replication"
    assert out["diff"]["point"] == pytest.approx(2.0, abs=1e-9)


def test_paired_contrast_handles_a_zero_control():
    out = paired_contrast([1.0, 2.0], [0.0, 0.0], relative=True)
    assert np.isnan(out["pct"]["point"])
    assert "undefined_reason" in out["pct"]


def test_effect_size_is_huge_under_crn():
    """Pairing removes the noise, so d is large almost by construction."""
    rng = np.random.default_rng(0)
    base = rng.normal(100, 10, 50)
    assert abs(effect_size(base + 2.0, base)) > 1e6


def test_combined_interval_refuses_to_merge_the_two_kinds():
    rng = np.random.default_rng(0)
    out = combined_interval(rng.normal(2.0, 0.01, 50), rng.normal(2.0, 3.0, 20))
    assert out["replication"]["kind"] == "replication"
    assert out["structural"]["kind"] == "structural"
    assert out["structural_over_replication"] > 1.0
    assert "not combined" in out["note"]
    assert "combined" not in {k for k in out if k.endswith("interval")}


def test_holm_is_step_down_and_monotone():
    out = holm_bonferroni({"a": 0.001, "b": 0.02, "c": 0.60})
    assert out["a"]["reject"] is True
    assert out["c"]["reject"] is False
    assert out["a"]["threshold"] < out["c"]["threshold"]


def test_holm_stops_at_the_first_failure():
    """Step-down: once a hypothesis is retained, every larger p is retained too."""
    out = holm_bonferroni({"a": 0.001, "b": 0.30, "c": 0.031})
    assert out["a"]["reject"] is True          # 0.001 <= 0.05/3
    assert out["c"]["reject"] is False         # 0.031 > 0.05/2, so it stops here
    assert out["b"]["reject"] is False, (
        "b has a larger p than c, so it cannot be rejected once c was retained")


def test_holm_adjusted_p_never_exceeds_one():
    out = holm_bonferroni({"a": 0.60, "b": 0.70, "c": 0.90})
    assert all(v["p_adjusted"] <= 1.0 for v in out.values())


def test_practical_significance_separates_detectable_from_meaningful():
    tiny = {"point": 0.0001, "lo": 0.00009, "hi": 0.00011}
    out = practical_significance(tiny, threshold=0.01)
    assert out["interval_excludes_zero"] is True
    assert out["practically_significant"] is False


def test_seed_adequacy_reports_a_required_count():
    rng = np.random.default_rng(0)
    out = seed_adequacy(rng.normal(0, 1.0, 50), target_halfwidth=0.1)
    assert out["n_required"] > 50
    assert out["adequate"] is False
