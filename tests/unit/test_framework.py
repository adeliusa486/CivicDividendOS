"""AEAP registry, the classifier, and the digital-twin interface."""

from __future__ import annotations

import numpy as np
import pytest

from cdos.config import Config, RateConfig
from cdos.framework.aeap import (
    AEAP,
    TASK_CLASSES,
    AEAPError,
    AEAPRegistry,
    validate_record,
)
from cdos.framework.classifier import MODES, classify, confusion_matrix, inject_error
from cdos.framework.twin import (
    POLICY_VECTOR,
    REQUIRES_AUTHOR_SPECIFICATION,
    SearchSpace,
    default_normaliser,
    screen,
)
from cdos.model.rate import applied_rate, lipschitz_constant


def good_record(**over):
    rec = {"deployment_id": "D-001", "owner": "Acme Ltd",
           "jurisdiction": "J1", "task_class": "substitution",
           "model_class": "foundation_model", "risk_class": "limited",
           "energy": 12.0, "output": 100.0}
    rec.update(over)
    return rec


# ---------------------------------------------------------------------------
# AEAP
# ---------------------------------------------------------------------------

def test_valid_record_accepted():
    p = validate_record(good_record())
    assert isinstance(p, AEAP)
    assert p.owner == "Acme Ltd"
    assert p.energy_intensity == pytest.approx(0.12)


def test_missing_owner_rejected():
    rec = good_record()
    del rec["owner"]
    with pytest.raises(AEAPError, match="missing a owner"):
        validate_record(rec)


def test_blank_owner_rejected():
    with pytest.raises(AEAPError, match="missing a owner"):
        validate_record(good_record(owner="   "))


def test_invalid_jurisdiction_rejected():
    with pytest.raises(AEAPError, match="not registered"):
        validate_record(good_record(jurisdiction="ZZ"), jurisdictions=("J1", "J2"))


def test_invalid_task_class_rejected():
    with pytest.raises(AEAPError, match="task_class"):
        validate_record(good_record(task_class="automation"))


def test_invalid_model_and_risk_class_rejected():
    with pytest.raises(AEAPError, match="model_class"):
        validate_record(good_record(model_class="magic"))
    with pytest.raises(AEAPError, match="risk_class"):
        validate_record(good_record(risk_class="extreme"))


def test_duplicate_deployment_id_rejected():
    reg = AEAPRegistry()
    reg.add(good_record())
    with pytest.raises(AEAPError, match="duplicate deployment_id"):
        reg.add(good_record())


def test_below_de_minimis_rejected():
    with pytest.raises(AEAPError, match="de minimis"):
        validate_record(good_record(output=0.5), de_minimis=10.0)


def test_negative_output_rejected():
    with pytest.raises(AEAPError, match="at least"):
        validate_record(good_record(output=-1.0))


def test_non_finite_energy_rejected():
    with pytest.raises(AEAPError, match="finite"):
        validate_record(good_record(energy=float("inf")))


def test_malformed_record_rejected():
    with pytest.raises(AEAPError, match="must be a mapping"):
        validate_record(["not", "a", "record"])          # type: ignore[arg-type]


def test_nexus_shares_must_sum_to_one():
    with pytest.raises(AEAPError, match="Proposition 8"):
        validate_record(good_record(nexus_shares={"J1": 0.5, "J2": 0.2}))


def test_nexus_shares_accepted_when_valid():
    p = validate_record(good_record(nexus_shares={"J1": 0.6, "J2": 0.4}))
    assert p.nexus_shares == {"J1": 0.6, "J2": 0.4}


def test_registry_aggregates():
    reg = AEAPRegistry(jurisdictions=("J1", "J2"))
    reg.add_many([good_record(deployment_id=f"D-{i}") for i in range(5)])
    assert len(reg) == 5
    assert reg.total_output() == pytest.approx(500.0)
    assert reg.total_energy() == pytest.approx(60.0)
    assert reg.owners() == {"Acme Ltd"}
    assert len(reg.by_task_class("substitution")) == 5


def test_registry_unknown_id_raises():
    with pytest.raises(AEAPError, match="no AEAP registered"):
        AEAPRegistry().get("nope")


def test_aeap_does_not_confer_personality():
    """The statutory taxpayer is the owner, never the deployment."""
    p = validate_record(good_record())
    assert p.owner and p.owner != p.deployment_id
    assert not hasattr(p, "legal_person")


# ---------------------------------------------------------------------------
# Classifier
# ---------------------------------------------------------------------------

def test_classifier_modes_match_the_paper():
    assert set(MODES) == set(TASK_CLASSES)
    assert len(MODES) == 4


def test_substitution_detected_when_labour_falls():
    r = classify(np.array([-0.4]), np.array([0.0]))
    assert r.modes[0] == "substitution"


def test_augmentation_detected_when_wages_rise():
    r = classify(np.array([0.0]), np.array([0.3]))
    assert r.modes[0] == "augmentation"


def test_new_task_and_safety_take_precedence():
    r = classify(np.array([-0.9]), np.array([0.0]),
                 is_new_task=np.array([True]))
    assert r.modes[0] == "new_task"
    r = classify(np.array([-0.9]), np.array([0.0]),
                 is_hazardous=np.array([True]))
    assert r.modes[0] == "safety_replacement"


def test_zero_error_leaves_classification_untouched():
    base = classify(np.random.default_rng(0).normal(0, 0.3, 200),
                    np.random.default_rng(1).normal(0, 0.3, 200))
    out = inject_error(base, 0.0)
    assert out.error_rate == 0.0
    np.testing.assert_array_equal(out.modes, base.modes)


@pytest.mark.parametrize("eps", [0.05, 0.10, 0.20])
def test_injected_error_rate_is_approximately_epsilon(eps):
    rng = np.random.default_rng(0)
    base = classify(rng.normal(0, 0.3, 20000), rng.normal(0, 0.3, 20000))
    out = inject_error(base, eps, rng=7)
    # A flip may land on the same mode only if it were the sole alternative,
    # which cannot happen with four modes, so the observed rate tracks epsilon.
    assert out.error_rate == pytest.approx(eps, abs=0.02)


def test_error_rate_outside_unit_interval_rejected():
    base = classify(np.zeros(5), np.zeros(5))
    with pytest.raises(ValueError, match=r"\[0, 1\]"):
        inject_error(base, 1.5)


def test_confusion_matrix_shape_and_total():
    rng = np.random.default_rng(2)
    base = classify(rng.normal(0, 0.3, 500), rng.normal(0, 0.3, 500))
    cm = confusion_matrix(inject_error(base, 0.10, rng=3))
    assert cm.shape == (4, 4)
    assert cm.sum() == 500


def test_confusion_matrix_is_diagonal_at_zero_error():
    rng = np.random.default_rng(4)
    base = classify(rng.normal(0, 0.3, 300), rng.normal(0, 0.3, 300))
    cm = confusion_matrix(inject_error(base, 0.0))
    assert np.all(cm - np.diag(np.diag(cm)) == 0)


def test_confusion_matrix_needs_ground_truth():
    from cdos.framework.classifier import ClassificationResult
    r = ClassificationResult(modes=np.array(["substitution"], dtype=object),
                             substitution_score=np.zeros(1),
                             augmentation_score=np.zeros(1))
    with pytest.raises(ValueError, match="ground truth"):
        confusion_matrix(r)


def test_proposition4_bound_holds_empirically():
    """|E[r] - r*| <= epsilon (alpha + theta), the Proposition 4 bound."""
    cfg = RateConfig()
    for term in ("S", "A_aug"):
        setattr(cfg, f"source_{term}", "endogenous")
    rng = np.random.default_rng(11)
    n = 4000
    base = classify(rng.normal(-0.2, 0.3, n), rng.normal(0.1, 0.3, n))
    for eps in (0.0, 0.05, 0.10, 0.20):
        noisy = inject_error(base, eps, rng=5)
        r_true = applied_rate(cfg, n, {"S": base.substitution_score,
                                       "A_aug": base.augmentation_score})
        r_obs = applied_rate(cfg, n, {"S": noisy.substitution_score,
                                      "A_aug": noisy.augmentation_score})
        observed = abs(float(np.mean(r_obs - r_true)))
        assert observed <= eps * lipschitz_constant(cfg) + 1e-12


# ---------------------------------------------------------------------------
# Digital twin
# ---------------------------------------------------------------------------

def test_policy_vector_matches_the_manuscript():
    assert len(POLICY_VECTOR) == 14


def test_unspecified_inputs_are_documented():
    assert len(REQUIRES_AUTHOR_SPECIFICATION) == 4
    assert any("weights" in s for s in REQUIRES_AUTHOR_SPECIFICATION)


def test_search_space_rejects_coordinates_outside_theta():
    with pytest.raises(ValueError, match="outside Theta"):
        SearchSpace({"technology.sigma": (1.0, 2.0)}).validate()


def test_search_space_rejects_inverted_bounds():
    with pytest.raises(ValueError, match="inverted"):
        SearchSpace({"rate.r0": (0.2, 0.1)}).validate()


def test_latin_hypercube_covers_the_range():
    space = SearchSpace({"rate.r0": (0.0, 0.2)})
    draws = space.latin_hypercube(50, np.random.default_rng(0))
    values = np.array([d["rate.r0"] for d in draws])
    assert values.min() < 0.02 and values.max() > 0.18
    assert np.all((values >= 0.0) & (values <= 0.2))


def test_screen_refuses_without_published_weights():
    space = SearchSpace({"rate.r0": (0.05, 0.12)})
    with pytest.raises(ValueError, match="published"):
        screen(Config(), lambda c: {"revenue": 1.0}, space, {},
               default_normaliser({}), 0.0, 0.0, 1.0)


def test_screen_returns_a_feasible_candidate():
    space = SearchSpace({"rate.r0": (0.05, 0.12), "fund.omega": (0.1, 0.5)})

    def evaluate(cfg):
        return {"revenue": cfg.rate.r0 * 10, "innovation": 1.0,
                "leakage": 0.0, "welfare": -abs(cfg.fund.omega - 0.4)}

    res = screen(Config(), evaluate, space,
                 weights={"revenue": 1.0, "welfare": 2.0},
                 normaliser=default_normaliser({}),
                 revenue_floor=0.6, innovation_floor=0.5, leakage_ceiling=0.1,
                 n_candidates=40, seed=0)
    assert res.feasible and res.n_feasible > 0
    assert res.outcomes["revenue"] >= 0.6
    assert set(res.theta) <= set(POLICY_VECTOR)


def test_screen_reports_no_feasible_candidate_rather_than_inventing_one():
    space = SearchSpace({"rate.r0": (0.05, 0.12)})
    with pytest.raises(RuntimeError, match="no candidate satisfied"):
        screen(Config(), lambda c: {"revenue": 0.0, "innovation": 0.0,
                                    "leakage": 1.0}, space,
               weights={"revenue": 1.0}, normaliser=default_normaliser({}),
               revenue_floor=99.0, innovation_floor=0.0, leakage_ceiling=0.0,
               n_candidates=8)


def test_screen_enforces_proposition5():
    space = SearchSpace({"fund.omega": (0.9, 0.95)})   # omega + kappa + sigma_T > 1
    with pytest.raises(RuntimeError, match="no candidate satisfied"):
        screen(Config(), lambda c: {"revenue": 1.0, "innovation": 1.0,
                                    "leakage": 0.0}, space,
               weights={"revenue": 1.0}, normaliser=default_normaliser({}),
               revenue_floor=0.0, innovation_floor=0.0, leakage_ceiling=1.0,
               n_candidates=8)
