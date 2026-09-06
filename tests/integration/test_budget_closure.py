"""F3: the government budget must close in every arm, every period.

This is the test that would have caught the audit's most consequential finding.
The audited model booked SAC revenue the firms were never charged; nothing in it
ever asked whether the books balanced, so the error survived to publication.
"""

from __future__ import annotations

import numpy as np
import pytest

from cdos.model.accounting import (AccountingError, ResourceAccount,
                                   marginal_decision_price,
                                   profit_after_liability, sac_liability)
from cdos.model.economy import ARMS, run


# ---------------------------------------------------------------------------
# The accounting primitive
# ---------------------------------------------------------------------------

def test_resource_account_closes_when_balanced():
    a = ResourceAccount(period=0)
    a.source("output", 100.0)
    a.use("wages", 60.0)
    a.use("machines", 25.0)
    a.use("profit", 15.0)
    a.revenue("tax", 30.0)
    a.spend("public", 30.0)
    assert a.check()["closed"] is True


def test_resource_account_raises_when_unbalanced():
    a = ResourceAccount(period=3)
    a.source("output", 100.0)
    a.use("wages", 60.0)
    with pytest.raises(AccountingError, match="period 3"):
        a.check()


def test_resource_account_names_the_missing_amount():
    a = ResourceAccount(period=1, strict=False)
    a.source("output", 100.0)
    a.use("wages", 93.0)
    report = a.check()
    assert report["closed"] is False
    assert report["resource_residual"] == pytest.approx(7.0)
    assert "wages" in a.describe()


def test_liability_is_rate_times_base():
    rate = np.array([0.10, 0.20])
    acb = np.array([100.0, 50.0])
    np.testing.assert_allclose(sac_liability(rate, acb), [10.0, 10.0])


def test_negative_base_contributes_no_liability():
    np.testing.assert_allclose(sac_liability(np.array([0.1]), np.array([-5.0])),
                               [0.0])


def test_decision_price_and_liability_are_separate():
    """The audited defect in one assertion: the wedge on the decision price is
    not the liability, and charging only the former loses the difference."""
    pm = np.array([1.0])
    rate = np.array([0.10])
    dacb_dm = np.array([-0.3])          # phi = 1 makes this negative (Prop. 2)
    m = np.array([50.0])
    acb = np.array([80.0])
    pm_eff = marginal_decision_price(pm, rate, dacb_dm)
    charged_via_price = float(((pm_eff - pm) * m).sum())
    true_liability = float(sac_liability(rate, acb).sum())
    assert charged_via_price != pytest.approx(true_liability)
    assert true_liability == pytest.approx(8.0)


def test_profit_debits_the_full_liability():
    profit = profit_after_liability(np.array([100.0]), 1.0, np.array([40.0]),
                                    np.array([1.0]), np.array([30.0]),
                                    np.array([8.0]))
    assert float(profit[0]) == pytest.approx(100.0 - 40.0 - 30.0 - 8.0)


def test_profit_floors_at_zero():
    profit = profit_after_liability(np.array([10.0]), 1.0, np.array([40.0]),
                                    np.array([1.0]), np.array([30.0]))
    assert float(profit[0]) == 0.0


# ---------------------------------------------------------------------------
# The whole model
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("arm", ARMS)
def test_every_arm_closes_its_books(fast_cfg, arm):
    """Strict accounting is on; a failure raises rather than warns."""
    fast_cfg.numerics.strict_accounting = True
    fast_cfg.run.collect_accounting = True
    result = run(fast_cfg, seed=0, arm=arm)
    assert result["accounts"], "no accounting records were collected"
    for record in result["accounts"]:
        assert record["closed"] is True, (
            f"arm {arm} failed to close in period {record['period']}")


@pytest.mark.parametrize("arm", ["B6", "B6c", "B11"])
def test_sac_revenue_is_fully_debited(fast_cfg, arm):
    """Every unit of SAC revenue must have been taken from somebody."""
    fast_cfg.run.collect_accounting = True
    result = run(fast_cfg, seed=0, arm=arm)
    for record in result["accounts"]:
        booked = record["fiscal_in"]["automation_revenue"]
        debited = record["uses"]["automation_liability"]
        assert debited == pytest.approx(booked, rel=1e-12), (
            f"{arm} period {record['period']}: booked {booked} but debited "
            f"{debited} -- this is exactly audit finding F3")


def test_audited_baseline_would_fail_this_test(audited_cfg):
    """The defect is real: reproduce it, then show the correction removes it.

    Under ``legacy_mode`` no accounting is collected at all, which is the
    original condition. Running the same arm with the correction on produces a
    materially different SAC-to-output ratio, because the liability now reduces
    profit, capital income and the tau_K base.
    """
    audited_cfg.run.t_burn = 4
    audited_cfg.run.t_run = 16
    audited_cfg.population.n_households = 500
    audited_cfg.population.n_firms = 40
    legacy = run(audited_cfg, seed=0, arm="B6c")

    corrected = audited_cfg.copy()
    corrected.legacy_mode = False
    corrected.numerics.strict_accounting = True
    fixed = run(corrected, seed=0, arm="B6c")

    assert legacy["taul"] != pytest.approx(fixed["taul"], rel=1e-9)


@pytest.mark.parametrize("arm", ["B0", "B1", "B4"])
def test_arms_without_a_contribution_book_no_automation_liability(fast_cfg, arm):
    fast_cfg.run.collect_accounting = True
    result = run(fast_cfg, seed=0, arm=arm)
    for record in result["accounts"]:
        assert record["uses"]["automation_liability"] == 0.0


def test_wedge_arms_charge_through_the_price(fast_cfg):
    """B1's liability sits inside the machine cost, not in a separate line."""
    fast_cfg.run.collect_accounting = True
    result = run(fast_cfg, seed=0, arm="B1")
    for record in result["accounts"]:
        assert record["uses"]["machine_wedge"] > 0.0
        assert record["fiscal_in"]["automation_revenue"] == pytest.approx(
            record["uses"]["machine_wedge"], rel=1e-9)
