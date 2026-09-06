"""Configuration for the CivicDividendOS testbed.

Every quantity that the model reads at run time lives here. Nothing that
affects a result is hard-coded inside a model function: the audit's F1 finding
was in large part a consequence of ``SIGMA`` and ``GAMMA`` being reachable only
by editing source, which is why no sensitivity analysis was ever run.

A :class:`Config` is a plain nested dataclass tree. It can be built from
defaults, loaded from YAML, overridden with dotted keys, and hashed. The hash is
what experiment manifests record, so a result can always be traced back to the
exact parameter vector that produced it.
"""

from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import asdict, dataclass, field, is_dataclass
from pathlib import Path
from typing import Any

import yaml

# ---------------------------------------------------------------------------
# Sections
# ---------------------------------------------------------------------------

@dataclass
class PopulationConfig:
    n_households: int = 10_000
    n_firms: int = 500
    skill_sd: float = 0.60
    wealth_sd: float = 1.30
    wealth_mean: float = 4.0
    productivity_sd: float = 0.35
    alpha_beta_a: float = 6.0
    alpha_beta_b: float = 4.0
    alpha_lo: float = 0.25
    alpha_hi: float = 0.90
    markup_mean: float = 0.22
    markup_sd: float = 0.08
    markup_lo: float = 0.02
    markup_hi: float = 0.60
    exposure_intercept: float = 0.85
    exposure_slope: float = 0.45
    exposure_noise: float = 0.10
    exposure_lo: float = 0.02
    exposure_hi: float = 0.98
    save_lo: float = 0.02
    save_hi: float = 0.35


@dataclass
class TechnologyConfig:
    sigma: float = 1.5           # elasticity of substitution, labour vs machines
    gamma: float = 0.85          # span of control (decreasing returns)
    pm0: float = 1.00            # initial machine price
    decay: float = 0.0060        # quarterly decline in the machine price
    eps_l: float = 0.30          # labour supply elasticity wrt net-of-tax wage
    cobb_douglas_tol: float = 1e-8   # |sigma - 1| below this uses the CD limit


@dataclass
class FiscalConfig:
    spend_ratio: float = 0.35    # baseline public spending as a share of output
    tau_l0: float = 0.30         # initial labour tax (endogenous thereafter)
    tau_k: float = 0.25          # capital/profit tax
    tau_c: float = 0.18          # consumption tax
    tau_c_base: float = 0.60     # share of output in the consumption tax base
    taul_lo: float = 0.05
    taul_hi: float = 0.60
    # F4: how programme spending is treated across arms.
    #   "baseline_spending" - each arm funds spend_ratio*Y plus its own programme
    #   "match_spending"    - every arm funds the same total spending path
    spending_mode: str = "baseline_spending"
    spending_reference_arm: str = "B0"


@dataclass
class FundConfig:
    r_fund_annual: float = 0.05
    rho_payout: float = 0.60
    omega: float = 0.40          # SAC share to the fund
    sigma_t: float = 0.15        # SAC share to immediate transition support
    kappa: float = 0.25          # SAC share earmarked to the earned-income shield
    # F2: stability. (1 - rho) * r_f must sit below realised growth g.
    #   "require" - assert a positive margin, fail loudly otherwise
    #   "warn"    - record the margin, keep going
    #   "stress"  - divergence is the object of study; never warn
    stability_mode: str = "warn"
    stability_g_assumed: float = 0.03   # g used in the analytic steady state


@dataclass
class RateConfig:
    """The adaptive SAC rate function, Eq. (11) of the manuscript.

    ``r~_i = r0 + alpha*S + beta*C_rent + gamma_e*E_disp + delta*X_ext + eta*R_rev``
    ``     - theta*A_aug - lam*T_train - mu*B_broad - nu*N_new``
    ``r_i  = clip(r~_i, rmin, rmax)``

    Ten terms in total. The audited baseline implemented seven of them (it
    omitted ``E_disp``, ``X_ext`` and ``B_broad``, and used ``S`` in place of
    ``R_rev``). Every weight and every index source is switchable so that the
    ablations can disable one channel without disturbing the others.

    Note on naming: the manuscript writes the ``E_disp`` weight as ``gamma``,
    which collides with the span-of-control ``gamma``. It is ``w_gamma_e`` here.
    """
    r0: float = 0.08
    rmin: float = 0.0
    rmax: float = 0.25
    # Non-negative coefficients (raise the rate)
    w_alpha: float = 0.10        # S_disp   labour substitution intensity
    w_beta: float = 0.06         # C_rent   economic rent / concentration
    w_gamma_e: float = 0.05      # E_disp   measured displacement burden
    w_delta: float = 0.04        # X_ext    environmental / social externality
    w_eta: float = 0.05          # R_rev    payroll and contribution base erosion
    # Non-positive coefficients (lower the rate)
    w_theta: float = 0.09        # A_aug    human augmentation benefit
    w_lambda: float = 0.07       # T_train  verified training and transition
    w_mu: float = 0.05           # B_broad  broad ownership and benefit
    w_nu: float = 0.06           # N_new    creation of new human tasks

    # Index sources. "endogenous" derives the index from the simulated state;
    # "fixed" uses the constant below. Two indices have no observable
    # counterpart in this testbed: X_ext needs the AEAP energy field and
    # B_broad needs per-firm ownership dispersion, and the model has neither.
    # Their constants are the manuscript's own worked-example values (Table VII,
    # 0.10 and 0.20), so the main specification is the paper's calibration
    # rather than an invented one, and the limitation is recorded in the README.
    source_S: str = "endogenous"
    source_C_rent: str = "endogenous"
    source_E_disp: str = "endogenous"
    source_X_ext: str = "fixed"
    source_R_rev: str = "endogenous"
    source_A_aug: str = "endogenous"
    source_T_train: str = "fixed"
    source_B_broad: str = "fixed"
    source_N_new: str = "fixed"

    fixed_S: float = 0.0
    fixed_C_rent: float = 0.0
    fixed_E_disp: float = 0.0
    fixed_X_ext: float = 0.10
    fixed_R_rev: float = 0.0
    fixed_A_aug: float = 0.0
    fixed_T_train: float = 0.55
    fixed_B_broad: float = 0.20
    fixed_N_new: float = 0.30

    augmentation_wage_scale: float = 0.50
    # Terms allowed to contribute at all; dropping a name here zeroes it.
    enabled_terms: list[str] = field(default_factory=lambda: [
        "S", "C_rent", "E_disp", "X_ext", "R_rev",
        "A_aug", "T_train", "B_broad", "N_new"])
    flat_rate: bool = False      # ablation A1: collapse the rate to r0
    # "clip" (Eq. 12) or "logistic" (the differentiable alternative on p. 9).
    map_kind: str = "clip"
    # Legacy quirk: the audited baseline fed S_i into the R_rev slot.
    legacy_rrev_uses_S: bool = False


@dataclass
class AttributionConfig:
    """Shapley attribution of firm value to factors of production."""
    # "two_factor"  - {L, M}, the audited baseline
    # "five_factor" - {H, A, R, D, K} as specified in the manuscript
    mode: str = "two_factor"
    method: str = "shapley"      # or "cost_share" (ablation A2)
    phi_deduct: float = 1.00     # share of machine cost deductible from the base
    five_factor_shares: dict[str, float] = field(default_factory=lambda: {
        "H": 0.55,   # human labour
        "A": 0.15,   # AI agents (software)
        "R": 0.10,   # robots (embodied)
        "D": 0.10,   # data
        "K": 0.10,   # traditional capital
    })
    machine_factors: list[str] = field(default_factory=lambda: ["A", "R"])


@dataclass
class ClassifierConfig:
    """Substitution / augmentation / new-task / safety classification."""
    enabled: bool = True
    error_rate: float = 0.0      # epsilon: probability a task class is misread
    kind: str = "rule_based"     # this testbed's classifier is rule-based, not learned


@dataclass
class NexusConfig:
    enabled: bool = False
    jurisdictions: list[str] = field(default_factory=lambda: ["J1", "J2", "J3"])
    shares: list[float] = field(default_factory=lambda: [0.60, 0.25, 0.15])
    shifting_elasticity: float = 0.0
    rate_multipliers: list[float] = field(default_factory=lambda: [1.0, 1.0, 1.0])


@dataclass
class DisplacementConfig:
    lam_disp: float = 0.35       # efficiency loss per unit exposure x automation growth
    retrain_eff: float = 0.50    # efficiency recovery per unit retraining spend
    eff_floor: float = 0.25
    enabled: bool = True


@dataclass
class PolicyConfig:
    """Arm-specific policy parameters."""
    robot_tax: float = 0.080     # B1 fixed wedge on the machine price
    auto_tax: float = 0.060      # B4 wedge
    retrain_share: float = 0.60  # B4 share of revenue spent on retraining
    dtau_k: float = 0.10         # B2 capital tax increase
    ubi_ratio: float = 0.020     # B3 UBI as a share of output
    aou_xi: float = 0.010        # B5 equity contribution rate on profit
    b7_tau_k_extra: float = 0.05     # B7 optimal linear capital tax increment
    b8_tau_c_extra: float = 0.03     # B8 consumption tax shift
    b9_lumpsum_ratio: float = 0.010  # B9 lump-sum financing as a share of output
    b10_wage_subsidy: float = 0.020  # B10 EITC-style subsidy rate
    b10_target_quantile: float = 0.40
    b12_robot_tax: float = 0.030     # B12 Thuemmel-style optimal robot tax


@dataclass
class NumericsConfig:
    bisect_iters: int = 28
    wage_lo: float = 1e-3
    wage_hi: float = 1e3
    accounting_tol: float = 1e-8     # relative tolerance for resource closure
    verify_bracket: bool = True      # check the wage bisection bracket contains a root
    strict_accounting: bool = True   # raise when the resource identity fails


@dataclass
class RunConfig:
    t_burn: int = 40
    t_run: int = 200
    seed: int = 0
    arm: str = "B0"
    collect_path: bool = False
    collect_accounting: bool = False


@dataclass
class Config:
    population: PopulationConfig = field(default_factory=PopulationConfig)
    technology: TechnologyConfig = field(default_factory=TechnologyConfig)
    fiscal: FiscalConfig = field(default_factory=FiscalConfig)
    fund: FundConfig = field(default_factory=FundConfig)
    rate: RateConfig = field(default_factory=RateConfig)
    attribution: AttributionConfig = field(default_factory=AttributionConfig)
    classifier: ClassifierConfig = field(default_factory=ClassifierConfig)
    nexus: NexusConfig = field(default_factory=NexusConfig)
    displacement: DisplacementConfig = field(default_factory=DisplacementConfig)
    policy: PolicyConfig = field(default_factory=PolicyConfig)
    numerics: NumericsConfig = field(default_factory=NumericsConfig)
    run: RunConfig = field(default_factory=RunConfig)

    # When true the model reproduces ``simulation/cdos_sim.py`` exactly,
    # including the three P0 defects. It exists so the regression suite can
    # prove the corrected code differs from the audited baseline only where
    # a correction was intended.
    legacy_mode: bool = False

    # -- derived ------------------------------------------------------------
    @property
    def r_fund_quarterly(self) -> float:
        return self.fund.r_fund_annual / 4.0

    @property
    def rho_sigma(self) -> float:
        """rho = 1 - 1/sigma, the CES exponent."""
        return 1.0 - 1.0 / self.technology.sigma

    @property
    def proposition2_condition(self) -> bool:
        """Proposition 2 holds identically when gamma > 1 - 1/sigma (audit F1)."""
        return self.technology.gamma > self.rho_sigma

    # -- serialisation ------------------------------------------------------
    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def hash(self) -> str:
        blob = json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]

    def copy(self) -> Config:
        return copy.deepcopy(self)

    def with_overrides(self, overrides: dict[str, Any]) -> Config:
        """Return a copy with dotted keys applied, e.g. ``{"technology.sigma": 2.0}``."""
        out = self.copy()
        for key, value in overrides.items():
            _set_dotted(out, key, value)
        return out


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------

_META_KEYS = ("name", "description", "experiment_id", "sweep", "arms", "seeds",
              "outputs", "notes", "grid", "ablation_of")


def _set_dotted(obj: Any, dotted: str, value: Any) -> None:
    parts = dotted.split(".")
    for part in parts[:-1]:
        if not hasattr(obj, part):
            raise KeyError(f"unknown configuration section {part!r} in {dotted!r}")
        obj = getattr(obj, part)
    leaf = parts[-1]
    if not hasattr(obj, leaf):
        raise KeyError(f"unknown configuration key {leaf!r} in {dotted!r}")
    current = getattr(obj, leaf)
    if isinstance(current, float) and isinstance(value, int) and not isinstance(value, bool):
        value = float(value)
    setattr(obj, leaf, value)


def _apply_nested(obj: Any, data: dict[str, Any], prefix: str = "") -> None:
    for key, value in data.items():
        if not hasattr(obj, key):
            raise KeyError(f"unknown configuration key {prefix + key!r}")
        current = getattr(obj, key)
        if is_dataclass(current) and isinstance(value, dict):
            _apply_nested(current, value, prefix=f"{prefix}{key}.")
        else:
            if isinstance(current, float) and isinstance(value, int) \
                    and not isinstance(value, bool):
                value = float(value)
            setattr(obj, key, value)


def _load_yaml_into(cfg: Config, path: Path, _seen: set | None = None) -> Config:
    path = Path(path).resolve()
    _seen = set() if _seen is None else _seen
    if path in _seen:
        raise ValueError(f"circular extends chain at {path}")
    _seen.add(path)
    with open(path, encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    data = dict(data)
    parent = data.pop("extends", None)
    for meta in _META_KEYS:
        data.pop(meta, None)
    if parent:
        cfg = _load_yaml_into(cfg, (path.parent / parent), _seen)
    _apply_nested(cfg, data)
    return cfg


def load_config(path: Path | str | None = None,
                overrides: dict[str, Any] | None = None) -> Config:
    """Build a Config from an optional YAML file plus optional dotted overrides.

    A YAML file may carry an ``extends:`` key naming another file relative to
    itself, so experiment files need only state what differs from the base.
    """
    cfg = Config() if path is None else _load_yaml_into(Config(), Path(path))
    if overrides:
        cfg = cfg.with_overrides(overrides)
    return cfg


def load_experiment(path: Path | str) -> dict[str, Any]:
    """Load an experiment file, returning its metadata alongside its Config."""
    path = Path(path)
    with open(path, encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}
    meta = {k: raw[k] for k in _META_KEYS if k in raw}
    return {"meta": meta, "config": _load_yaml_into(Config(), path), "path": str(path)}


__all__ = ["Config", "load_config", "load_experiment", "PopulationConfig",
           "TechnologyConfig", "FiscalConfig", "FundConfig", "RateConfig",
           "AttributionConfig", "ClassifierConfig", "NexusConfig",
           "DisplacementConfig", "PolicyConfig", "NumericsConfig", "RunConfig"]
