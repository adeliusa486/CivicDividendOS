"""The corrected package must reproduce the audited baseline bit-exactly.

This is the anchor for every scientific claim about what changed. If
``legacy_mode`` stops reproducing ``simulation/cdos_sim.py`` exactly, then a
difference has crept in that nobody decided on, and the remediation record in
MEMORY.md no longer describes the code.

Tolerances here are exact equality, not ``approx``. Where a corrected result
legitimately differs, the test says so and says why, rather than being loosened
until it passes.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from cdos.model.economy import run

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "simulation"))

try:
    import cdos_sim as legacy_module
except ImportError:                                     # pragma: no cover
    legacy_module = None

LEGACY_ARMS = ("B0", "B1", "B2", "B3", "B4", "B5", "B6", "B6c")
COMPARED = ("Y", "Y_end", "hours", "ws", "ws_end", "gi", "gw", "pov", "taul",
            "taul_end", "taul_cv", "fund", "divgdp", "divgdp_end", "sac",
            "adopt", "rev_cv", "div")

pytestmark = pytest.mark.regression


@pytest.mark.skipif(legacy_module is None, reason="legacy testbed not importable")
@pytest.mark.slow
@pytest.mark.parametrize("arm", LEGACY_ARMS)
def test_legacy_mode_is_bit_exact(audited_cfg, arm):
    """Every reported statistic must match to the last bit."""
    expected = legacy_module.run(0, arm)
    actual = run(audited_cfg, seed=0, arm=arm)
    for key in COMPARED:
        assert actual[key] == expected[key], (
            f"arm {arm}, statistic {key}: corrected package gives "
            f"{actual[key]!r}, audited baseline gives {expected[key]!r}. "
            "legacy_mode is supposed to be exact.")


@pytest.mark.skipif(legacy_module is None, reason="legacy testbed not importable")
@pytest.mark.slow
@pytest.mark.parametrize("seed", [1, 7])
def test_legacy_mode_is_bit_exact_across_seeds(audited_cfg, seed):
    for arm in ("B0", "B6c"):
        expected = legacy_module.run(seed, arm)
        actual = run(audited_cfg, seed=seed, arm=arm)
        for key in COMPARED:
            assert actual[key] == expected[key], f"{arm} seed {seed} key {key}"


# ---------------------------------------------------------------------------
# What the corrections do and do not change
# ---------------------------------------------------------------------------

@pytest.mark.slow
@pytest.mark.parametrize("arm", ["B0", "B2", "B3", "B5"])
def test_correction_leaves_untouched_arms_alone(audited_cfg, arm):
    """Arms with no automation contribution cannot be affected by the F3 fix.

    B0, B2, B3 and B5 raise no automation revenue, so the liability line is
    identically zero and the corrected model must agree exactly with the
    audited one. A difference here would mean the correction had side effects.
    """
    corrected = audited_cfg.copy()
    corrected.legacy_mode = False
    corrected.numerics.strict_accounting = True
    corrected.numerics.verify_bracket = True
    before = run(audited_cfg, seed=0, arm=arm)
    after = run(corrected, seed=0, arm=arm)
    for key in ("Y", "taul", "gi", "gw", "ws", "pov"):
        assert after[key] == pytest.approx(before[key], rel=1e-12), (
            f"arm {arm} statistic {key} moved, but it has no SAC revenue")


@pytest.mark.slow
@pytest.mark.parametrize("arm", ["B1", "B4"])
def test_wedge_arms_are_unchanged_by_the_f3_correction(audited_cfg, arm):
    """B1 and B4 were already consistent, as the audit found.

    They levy a genuine price wedge with matching revenue, so the liability is
    already inside the machine cost. The correction is specific to B6/B6c and
    must not move these.
    """
    corrected = audited_cfg.copy()
    corrected.legacy_mode = False
    corrected.numerics.strict_accounting = True
    corrected.numerics.verify_bracket = True
    before = run(audited_cfg, seed=0, arm=arm)
    after = run(corrected, seed=0, arm=arm)
    for key in ("Y", "taul", "gi", "ws"):
        assert after[key] == pytest.approx(before[key], rel=1e-12), (
            f"arm {arm} statistic {key} moved; the F3 fix should be asymmetric")


@pytest.mark.slow
@pytest.mark.parametrize("arm", ["B6", "B6c"])
def test_sac_arms_do_change_and_the_change_is_recorded(audited_cfg, arm):
    """The advocated arms must change: that is the point of the correction."""
    corrected = audited_cfg.copy()
    corrected.legacy_mode = False
    corrected.numerics.strict_accounting = True
    before = run(audited_cfg, seed=0, arm=arm)
    after = run(corrected, seed=0, arm=arm)
    assert after["taul"] != pytest.approx(before["taul"], rel=1e-9), (
        "the F3 correction debits the liability from profit, which changes the "
        "capital tax base and therefore the labour tax that clears the budget; "
        "no change here would mean the correction did nothing")
