"""Every policy arm must be defined, distinct, and reduce to B0 when disabled."""

from __future__ import annotations

import numpy as np
import pytest

from cdos.model.economy import ARM_LABEL, ARMS, run

NEW_ARMS = ("B7", "B8", "B9", "B10", "B11", "B12")


def test_all_fourteen_arms_declared():
    assert len(ARMS) == 14
    assert set(ARMS) == set(ARM_LABEL)


def test_every_arm_has_a_descriptive_label():
    for arm in ARMS:
        assert len(ARM_LABEL[arm]) > 10, f"arm {arm} has no useful label"


def test_unknown_arm_is_rejected(fast_cfg):
    with pytest.raises(ValueError, match="unknown arm"):
        run(fast_cfg, seed=0, arm="B99")


@pytest.mark.parametrize("arm", ARMS)
def test_every_arm_runs_and_produces_finite_output(fast_cfg, arm):
    result = run(fast_cfg, seed=0, arm=arm)
    for key in ("Y", "taul", "gi", "gw", "ws", "pov", "eff_units"):
        assert np.isfinite(result[key]), f"{arm} produced non-finite {key}"
    assert result["Y"] > 0
    assert 0.0 <= result["gi"] <= 1.0


@pytest.mark.parametrize("arm", NEW_ARMS)
def test_new_arms_differ_from_the_baseline(fast_cfg, arm):
    b0 = run(fast_cfg, seed=0, arm="B0")
    other = run(fast_cfg, seed=0, arm=arm)
    assert other["Y"] != pytest.approx(b0["Y"], rel=1e-12), (
        f"arm {arm} is indistinguishable from B0; it is not a distinct policy")


# ---------------------------------------------------------------------------
# Reduction to B0 when the policy parameter is switched off
# ---------------------------------------------------------------------------

REDUCTIONS = {
    "B1": {"policy.robot_tax": 0.0},
    "B2": {"policy.dtau_k": 0.0},
    "B3": {"policy.ubi_ratio": 0.0},
    "B4": {"policy.auto_tax": 0.0},
    "B5": {"policy.aou_xi": 0.0},
    "B7": {"policy.b7_tau_k_extra": 0.0},
    "B8": {"policy.b8_tau_c_extra": 0.0},
    "B10": {"policy.b10_wage_subsidy": 0.0},
    "B12": {"policy.b12_robot_tax": 0.0},
}


@pytest.mark.parametrize("arm,override", sorted(REDUCTIONS.items()))
def test_arm_reduces_to_baseline_when_disabled(fast_cfg, arm, override):
    """With its policy parameter at zero, an arm must be B0 again."""
    disabled = fast_cfg.with_overrides(override)
    b0 = run(disabled, seed=0, arm="B0")
    off = run(disabled, seed=0, arm=arm)
    for key in ("Y", "taul", "gi", "ws"):
        assert off[key] == pytest.approx(b0[key], rel=1e-10), (
            f"arm {arm} with {override} still differs from B0 on {key}")


def test_sac_arms_reduce_to_baseline_at_a_zero_rate(fast_cfg):
    """B6 at r_min = r_max = 0 raises nothing and must collapse to B0."""
    off = fast_cfg.with_overrides({"rate.r0": 0.0, "rate.rmax": 0.0,
                                   "rate.flat_rate": True})
    b0 = run(off, seed=0, arm="B0")
    b6 = run(off, seed=0, arm="B6")
    for key in ("Y", "taul", "gi", "ws"):
        assert b6[key] == pytest.approx(b0[key], rel=1e-10)


# ---------------------------------------------------------------------------
# Arm-specific behaviour
# ---------------------------------------------------------------------------

def test_b7_raises_more_capital_revenue_than_b0(fast_cfg):
    b0 = run(fast_cfg, seed=0, arm="B0")
    b7 = run(fast_cfg, seed=0, arm="B7")
    assert b7["taul"] < b0["taul"], (
        "a higher capital tax should let the labour tax fall, since the labour "
        "tax is what clears the budget")


def test_b8_shifts_burden_off_labour(fast_cfg):
    b0 = run(fast_cfg, seed=0, arm="B0")
    b8 = run(fast_cfg, seed=0, arm="B8")
    assert b8["taul"] < b0["taul"]


def test_b11_uses_zero_deduction(fast_cfg):
    """B11 sets phi = 0, so the base is the full attributed value."""
    b11 = run(fast_cfg, seed=0, arm="B11")
    b6 = run(fast_cfg, seed=0, arm="B6")
    assert b11["sac"] > b6["sac"], (
        "with no cost deduction the base is larger, so revenue must be higher")


def test_b6c_raises_more_than_b6(fast_cfg):
    """phi = 1/2 gives a larger base than phi = 1 (Proposition 2)."""
    assert run(fast_cfg, seed=0, arm="B6c")["sac"] > \
        run(fast_cfg, seed=0, arm="B6")["sac"]


def test_b10_targets_the_lower_part_of_the_distribution(fast_cfg):
    b0 = run(fast_cfg, seed=0, arm="B0")
    b10 = run(fast_cfg, seed=0, arm="B10")
    assert b10["gi"] < b0["gi"], "an earnings subsidy should reduce income Gini"


def test_common_random_numbers_pair_the_arms(fast_cfg):
    """Two arms at the same seed must see the same population draw."""
    from cdos.model.economy import Population
    a = Population.draw(fast_cfg, 3)
    b = Population.draw(fast_cfg, 3)
    np.testing.assert_array_equal(a.skill, b.skill)
    np.testing.assert_array_equal(a.alpha_f, b.alpha_f)
    c = Population.draw(fast_cfg, 4)
    assert not np.array_equal(a.skill, c.skill)


@pytest.mark.parametrize("arm", ["B0", "B6c"])
def test_runs_are_deterministic(fast_cfg, arm):
    assert run(fast_cfg, seed=2, arm=arm)["Y"] == \
        run(fast_cfg, seed=2, arm=arm)["Y"]
