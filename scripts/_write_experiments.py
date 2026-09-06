"""Generate the experiment and ablation definition files.

Run once; the YAML it writes is the source of truth thereafter. Kept in the
repository so the experiment matrix is reproducible rather than hand-assembled.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXP = ROOT / "experiments"

EXPERIMENTS = {
"E01_sigma_gamma": """extends: ../configs/base.yaml
experiment_id: E01
name: sigma-gamma robustness
description: >
  Audit finding F1. The headline claim that B6c dominates was made at a single
  point, sigma=1.5 and gamma=0.85, with no sensitivity analysis, and the audit
  showed the output effect reverses sign by sigma of about 2. This maps the
  region of the parameter space in which the claim actually holds, and reports
  the Proposition 2 condition gamma > 1 - 1/sigma at every cell.
arms: [B0, B6, B6c, B1]
seeds: 20
sweep:
  technology.sigma: [1.2, 1.5, 2.0, 3.0, 5.0, 8.0]
  technology.gamma: [0.75, 0.85, 0.95]
""",

"E02_budget": """extends: ../configs/base.yaml
experiment_id: E02
name: corrected budget accounting
description: >
  Audit finding F3. Runs every arm with strict per-period resource closure
  enforced, so that any failure to close raises rather than passing silently.
  The audited comparison is produced by the regression suite, not by this file.
arms: [B0, B1, B4, B6, B6c, B11]
seeds: 50
numerics:
  strict_accounting: true
""",

"E03_fund_stability": """extends: ../configs/base.yaml
experiment_id: E03
name: fund stability
description: >
  Audit finding F2. Sweeps the payout share and the fund return so that the
  Proposition 6 margin g - (1-rho) r_f crosses zero, and compares the simulated
  fund path against the analytic recursion at each setting.
arms: [B0, B6c]
seeds: 20
fund:
  stability_mode: stress
sweep:
  fund.rho_payout: [0.40, 0.60, 0.75, 0.90]
  fund.r_fund_annual: [0.03, 0.04, 0.05, 0.06]
""",

"E04_revenue_normalised": """extends: ../configs/base.yaml
experiment_id: E04
name: revenue-normalised policy ranking
description: >
  Audit finding F5. Ranking instruments by output effect alone is not valid when
  they raise materially different revenue. Runs the full arm set and reports
  revenue per unit of deadweight loss alongside the output effect.
arms: [B0, B1, B2, B3, B4, B5, B6, B6c, B7, B8, B9, B10, B11, B12]
seeds: 50
""",

"E05_horizon": """extends: ../configs/base.yaml
experiment_id: E05
name: horizon sensitivity
description: >
  Whether the ranking of arms depends on the 200-quarter reporting window. A
  fund still accumulating at the horizon can flatter an arm that would look
  different over a longer or a shorter run.
arms: [B0, B1, B6, B6c]
seeds: 20
sweep:
  run.t_run: [80, 120, 200, 320, 400]
""",

"E06_classifier_error": """extends: ../configs/base.yaml
experiment_id: E06
name: classifier error
description: >
  Proposition 4. Injects classification error at 0, 5, 10 and 20 per cent and
  measures the induced rate and revenue error against the analytic bound
  epsilon times (alpha + theta).
arms: [B0, B6, B6c]
seeds: 20
sweep:
  classifier.error_rate: [0.0, 0.05, 0.10, 0.20]
""",

"E07_phi_sweep": """extends: ../configs/base.yaml
experiment_id: E07
name: cost-deduction share
description: >
  Proposition 2. Sweeps the deduction share phi across the unit interval. The
  proposition predicts marginal incidence turns non-negative at phi of one half
  or below, so the instrument should stop subsidising automation in that range.
arms: [B0, B6]
seeds: 20
sweep:
  attribution.phi_deduct: [0.0, 0.25, 0.50, 0.75, 1.0]
""",

"E08_rate_terms": """extends: ../configs/base.yaml
experiment_id: E08
name: rate-function terms
description: >
  What the three restored rate terms do. The audited code implemented seven of
  the ten terms of Eq. (11); this varies the weights on the displacement,
  externality and broad-ownership terms that were missing from it.
arms: [B0, B6c]
seeds: 20
sweep:
  rate.w_gamma_e: [0.0, 0.05, 0.10]
  rate.w_delta: [0.0, 0.04]
  rate.w_mu: [0.0, 0.05]
""",

"E09_payout_paradox": """extends: ../configs/base.yaml
experiment_id: E09
name: payout paradox
description: >
  Proposition 7. A higher payout share raises the dividend today but lowers the
  steady-state fund, so beyond some point raising rho reduces the long-run
  dividend. Sweeps rho to locate the turning point, if there is one.
arms: [B0, B6c]
seeds: 20
fund:
  stability_mode: stress
sweep:
  fund.rho_payout: [0.20, 0.40, 0.60, 0.80, 0.95]
""",

"E10_jurisdictions": """extends: ../configs/base.yaml
experiment_id: E10
name: multi-jurisdiction leakage
description: >
  The testbed had one jurisdiction and so, as the manuscript concedes, could say
  nothing about leakage. Enables the three-jurisdiction nexus and sweeps the
  shifting elasticity. Apportionment must stay exhaustive throughout.
arms: [B0, B6c]
seeds: 20
nexus:
  enabled: true
  jurisdictions: [J1, J2, J3]
  shares: [0.60, 0.25, 0.15]
  rate_multipliers: [1.0, 0.5, 1.5]
sweep:
  nexus.shifting_elasticity: [0.0, 0.2, 0.4, 0.8]
""",

"E11_avoidance": """extends: ../configs/base.yaml
experiment_id: E11
name: avoidance
description: >
  Cost inflation in the admitted cost base directly reduces the contribution
  base. Sweeps the deduction share upward as a proxy for inflated admitted
  costs, crossed with relabelling of substitution as augmentation through the
  classifier error channel.
arms: [B0, B6c]
seeds: 20
sweep:
  attribution.phi_deduct: [0.5, 0.7, 0.9]
  classifier.error_rate: [0.0, 0.2]
""",

"E12_five_factor": """extends: ../configs/base.yaml
experiment_id: E12
name: five-factor versus composite attribution
description: >
  The framework distinguishes five factors; the testbed has one composite
  machine factor. Runs the exact five-factor Shapley game over all 31 coalitions
  against the two-factor game to measure what the composite costs.
arms: [B0, B6c]
seeds: 20
sweep:
  attribution.mode: [two_factor, five_factor]
""",

"E13_calibration": """extends: ../configs/base.yaml
experiment_id: E13
name: calibration validity
description: >
  Compares model moments against the calibration targets in
  configs/calibration.yaml. Most targets are NOT_FETCHED because the underlying
  series are licensed and cannot be redistributed, so this experiment reports
  which targets could be checked and which could not. It does not invent data.
arms: [B0, B6c]
seeds: 20
""",

"E14_decay": """extends: ../configs/base.yaml
experiment_id: E14
name: machine-price decay sensitivity
description: >
  The machine price decline is assumed rather than calibrated, and it drives the
  entire automation transition, so the results should be read against it.
arms: [B0, B1, B6c]
seeds: 20
sweep:
  technology.decay: [0.002, 0.004, 0.006, 0.010, 0.015]
""",

"E15_seed_adequacy": """extends: ../configs/base.yaml
experiment_id: E15
name: Monte-Carlo seed adequacy
description: >
  How many seeds the paired contrasts actually need. Under common random numbers
  the replication intervals are very tight, which is a statement about
  reproducibility and not about policy certainty.
arms: [B0, B6c]
seeds: 100
""",

"E16_incidence": """extends: ../configs/base.yaml
experiment_id: E16
name: incidence
description: >
  The manuscript makes explicit incidence reporting a governance requirement,
  because a contribution levied on an operator may land on shareholders,
  workers, suppliers or consumers. Reports the factor split of the burden.
arms: [B0, B1, B4, B6, B6c, B12]
seeds: 50
""",

"E17_scalability": """extends: ../configs/base.yaml
experiment_id: E17
name: scalability
description: >
  Runtime and result stability as the agent population grows. Establishes
  whether the reported magnitudes are converged in population size or are an
  artefact of 10,000 households and 500 firms.
arms: [B0, B6c]
seeds: 10
sweep:
  population.n_households: [2500, 5000, 10000, 20000]
""",
}

ABLATIONS = {
"A01_flat_rate": ("A01", "adaptive rate to flat rate",
                  "Does the adaptive rate function do any work, or would a flat "
                  "rate at r0 achieve the same outcome? This is the ablation "
                  "that tests the framework's central design claim.",
                  {"rate.flat_rate": [False, True]}),
"A02_cost_share": ("A02", "Shapley to cost-share attribution",
                   "The manuscript argues that attribution by Shapley value is "
                   "not the same as attribution by factor cost share. This "
                   "measures the difference the choice makes.",
                   {"attribution.method": ["shapley", "cost_share"]}),
"A03_fund_off": ("A03", "wealth fund off",
                 "How much of the distributional result comes from the fund "
                 "rather than from the contribution itself.",
                 {"fund.omega": [0.40, 0.0]}),
"A04_shield_off": ("A04", "earned-income shield off",
                   "The shield is the mechanism the paper names for the lower "
                   "labour tax. Turning it off separates the earmarked shield "
                   "from the general-revenue residual.",
                   {"fund.kappa": [0.25, 0.0]}),
"A05_transition_off": ("A05", "transition transfers off",
                       "How much of the poverty and inequality effect is the "
                       "immediate transition transfer rather than the fund.",
                       {"fund.sigma_t": [0.15, 0.0]}),
"A06_retraining_off": ("A06", "retraining off",
                       "Retraining recovers worker efficiency after "
                       "displacement. Without it the displacement channel is "
                       "one-way.",
                       {"displacement.retrain_eff": [0.50, 0.0]}),
"A07_rent_term_off": ("A07", "rent term off",
                      "Whether taxing measured economic rent through the "
                      "C_rent term contributes anything beyond the "
                      "substitution term.",
                      {"rate.w_beta": [0.06, 0.0]}),
"A08_augmentation_off": ("A08", "augmentation credit off",
                         "The augmentation credit is what makes the instrument "
                         "discriminate between substituting and complementing "
                         "automation. Removing it should collapse that "
                         "discrimination.",
                         {"rate.w_theta": [0.09, 0.0]}),
"A09_phi": ("A09", "deduction share",
            "phi at 0, one half and 1, the three cases Proposition 2 "
            "distinguishes. Uses arm B6, which reads phi from configuration; "
            "arm B6c pins phi to one half by definition and so cannot vary it.",
            {"attribution.phi_deduct": [0.0, 0.5, 1.0]}, ["B0", "B6"]),
"A10_displacement_off": ("A10", "displacement channel off",
                         "Without displacement, automation has no effect on "
                         "worker efficiency and the case for the instrument "
                         "rests on distribution alone.",
                         {"displacement.enabled": [True, False]}),
}

ABLATION_TEMPLATE = """extends: ../configs/base.yaml
experiment_id: {eid}
name: {name}
description: >
  {desc}
arms: {arms}
seeds: 20
sweep:
{sweep}"""


def main() -> None:
    EXP.mkdir(parents=True, exist_ok=True)
    for stem, body in EXPERIMENTS.items():
        (EXP / f"{stem}.yaml").write_text(body, encoding="utf-8", newline="\n")
    for stem, spec in ABLATIONS.items():
        eid, name, desc, sweep = spec[:4]
        arms = spec[4] if len(spec) > 4 else ["B0", "B6c"]
        lines = "\n".join(f"  {k}: {v}".replace("'", "")
                          for k, v in sweep.items())
        (EXP / f"{stem}.yaml").write_text(
            ABLATION_TEMPLATE.format(eid=eid, name=name, desc=desc,
                                     sweep=lines, arms=arms)
            + "\n", encoding="utf-8", newline="\n")
    print(f"wrote {len(EXPERIMENTS)} experiments and {len(ABLATIONS)} ablations "
          f"into {EXP}")


if __name__ == "__main__":
    main()
