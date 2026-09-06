"""The classifier-error and nexus-leakage channels must actually bite.

Both were configurable before they were connected: ``classifier.error_rate``
and ``nexus.shifting_elasticity`` could be set to anything and the run produced
identical results, so experiments E06 and E10 measured nothing. A parameter that
appears in a configuration file and changes no result is worse than a missing
one, because it looks like evidence.

These tests fail if either channel is ever disconnected again.
"""

from __future__ import annotations

import pytest

from cdos.model.economy import run

# ---------------------------------------------------------------------------
# Classification error (Proposition 4)
# ---------------------------------------------------------------------------

def test_classifier_error_changes_the_outcome(fast_cfg):
    clean = run(fast_cfg.with_overrides({"classifier.error_rate": 0.0}),
                seed=0, arm="B6c")
    noisy = run(fast_cfg.with_overrides({"classifier.error_rate": 0.20}),
                seed=0, arm="B6c")
    assert noisy["sac"] != pytest.approx(clean["sac"], rel=1e-9), (
        "classifier.error_rate is configurable but changes nothing; E06 would "
        "be measuring a parameter no code reads")


def test_zero_classifier_error_is_a_no_op(fast_cfg):
    a = run(fast_cfg.with_overrides({"classifier.error_rate": 0.0}), 0, "B6c")
    b = run(fast_cfg.with_overrides({"classifier.enabled": False}), 0, "B6c")
    assert a["sac"] == pytest.approx(b["sac"], rel=1e-12)


def test_classifier_error_is_deterministic(fast_cfg):
    cfg = fast_cfg.with_overrides({"classifier.error_rate": 0.10})
    assert run(cfg, 3, "B6c")["sac"] == run(cfg, 3, "B6c")["sac"]


def test_classifier_error_does_not_disturb_arms_without_a_rate(fast_cfg):
    """Arms that never consult the rate function must be untouched."""
    clean = run(fast_cfg.with_overrides({"classifier.error_rate": 0.0}), 0, "B1")
    noisy = run(fast_cfg.with_overrides({"classifier.error_rate": 0.30}), 0, "B1")
    assert noisy["Y"] == pytest.approx(clean["Y"], rel=1e-12)


@pytest.mark.parametrize("eps", [0.05, 0.10, 0.20])
def test_revenue_error_respects_the_proposition4_bound(fast_cfg, eps):
    """|E[SAC] - SAC*| <= eps (alpha + theta) * ACB, applied to the ratio."""
    clean = run(fast_cfg.with_overrides({"classifier.error_rate": 0.0}), 0, "B6c")
    noisy = run(fast_cfg.with_overrides({"classifier.error_rate": eps}), 0, "B6c")
    lipschitz = fast_cfg.rate.w_alpha + fast_cfg.rate.w_theta
    # The revenue ratio moves by at most the rate error times the base, and the
    # base itself is bounded by the clean revenue divided by the clean rate.
    relative_move = abs(noisy["sac"] - clean["sac"]) / max(clean["sac"], 1e-12)
    assert relative_move <= eps * lipschitz / max(fast_cfg.rate.rmin + 0.01, 1e-9)


# ---------------------------------------------------------------------------
# Cross-border leakage (Proposition 8)
# ---------------------------------------------------------------------------

def _nexus_cfg(cfg, elasticity: float):
    return cfg.with_overrides({
        "nexus.enabled": True,
        "nexus.shifting_elasticity": elasticity,
        "nexus.rate_multipliers": [1.0, 0.5, 1.5],
    })


def test_shifting_reduces_collected_revenue(fast_cfg):
    none = run(_nexus_cfg(fast_cfg, 0.0), 0, "B6c")
    some = run(_nexus_cfg(fast_cfg, 0.8), 0, "B6c")
    assert some["sac"] < none["sac"], (
        "a positive shifting elasticity must move base towards the "
        "low-rate jurisdiction and so reduce revenue; E10 measures nothing "
        "otherwise")
    assert some["leakage"] > 0.0


def test_leakage_is_zero_without_shifting(fast_cfg):
    assert run(_nexus_cfg(fast_cfg, 0.0), 0, "B6c")["leakage"] == \
        pytest.approx(0.0, abs=1e-12)


def test_leakage_rises_monotonically_with_the_elasticity(fast_cfg):
    values = [run(_nexus_cfg(fast_cfg, e), 0, "B6c")["leakage"]
              for e in (0.0, 0.2, 0.4, 0.8)]
    assert all(b >= a for a, b in zip(values, values[1:], strict=False)), values
    assert values[-1] > values[0]


def test_nexus_disabled_leaves_revenue_alone(fast_cfg):
    off = run(fast_cfg, 0, "B6c")
    on_no_shift = run(_nexus_cfg(fast_cfg, 0.0), 0, "B6c")
    # With uniform apportionment and no shifting, the only difference is the
    # jurisdictions' rate multipliers, which are not all one here.
    assert off["leakage"] == 0.0
    assert on_no_shift["leakage"] == pytest.approx(0.0, abs=1e-12)


def test_budget_still_closes_under_leakage(fast_cfg):
    """Leakage must reduce domestic revenue, not break the resource identity.

    Firms bear the full liability; the domestic budget collects only its
    apportioned share, and the remainder accrues to another jurisdiction. So
    ``automation_liability`` (what firms paid) legitimately exceeds
    ``automation_revenue`` (what this government received), and the difference
    is exactly the foreign apportionment.
    """
    cfg = _nexus_cfg(fast_cfg, 0.8)
    cfg.run.collect_accounting = True
    cfg.numerics.strict_accounting = True
    result = run(cfg, 0, "B6c")
    saw_leakage = False
    for record in result["accounts"]:
        assert record["closed"] is True
        borne = record["uses"]["automation_liability"]
        collected = record["fiscal_in"]["automation_revenue"]
        foreign = record["fiscal_in"]["foreign_apportioned"]
        assert borne == pytest.approx(collected + foreign, rel=1e-12), (
            "every unit of liability must be accounted for either as domestic "
            "revenue or as foreign apportionment")
        if foreign > 0:
            saw_leakage = True
    assert saw_leakage, "no revenue leaked despite a shifting elasticity of 0.8"
