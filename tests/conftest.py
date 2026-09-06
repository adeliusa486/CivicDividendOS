"""Shared fixtures. Tests import ``cdos`` from ``src`` without installation."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from cdos.config import Config, load_config      # noqa: E402


@pytest.fixture(scope="session")
def root() -> Path:
    return ROOT


@pytest.fixture
def base_cfg() -> Config:
    """The corrected main specification."""
    return load_config(ROOT / "configs" / "base.yaml")


@pytest.fixture
def audited_cfg() -> Config:
    """The audited baseline, defects included, for regression only."""
    return load_config(ROOT / "configs" / "policies" / "audited_baseline.yaml")


@pytest.fixture
def fast_cfg(base_cfg: Config) -> Config:
    """A short-horizon configuration for tests that only need the mechanics."""
    cfg = base_cfg.copy()
    cfg.run.t_burn = 4
    cfg.run.t_run = 16
    cfg.population.n_households = 500
    cfg.population.n_firms = 40
    return cfg
