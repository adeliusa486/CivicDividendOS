# Changelog

All notable changes to this project. Format loosely follows Keep a Changelog.
Scientific changes are listed separately from software changes, because they
change what the paper may claim.

---

## [1.0.0] — 2026-09-06 — post-audit remediation

Remediation of the independent audit of 2026-09-06
(`audit/AUDIT_REPORT.html`). The pre-remediation state is preserved at tag
`v0-audit` and reproduces bit-exactly.

### Scientific Changes

These change results and therefore change what may be claimed.

- **F3 — the government budget now closes.** The audited model booked SAC
  revenue as `sum_i r_i·ACB_i` but debited firms only the marginal wedge
  `(pm_eff − pm)·M`, about 7% of it. Roughly 93% of automation revenue funded
  the shield, fund and dividend without reducing anybody's income, and so
  without reducing capital income or the `tau_K` base. The error was
  **asymmetric**: arms B1 and B4 were already consistent, so it inflated
  precisely the arms the paper recommends.
  The marginal decision price `pm_eff` is unchanged (firm behaviour is
  identical); the full liability is now debited from profit as a lump sum.
  *Effect:* B6c's output advantage at the paper's calibration falls from
  **+3.30%** to **+3.01%**.

- **F1 — the headline claim is now conditional.** `sigma` and `gamma` were
  reachable only by editing source, so no sensitivity analysis was ever run.
  E01 sweeps `sigma ∈ {1.2 … 8.0}` × `gamma ∈ {0.75, 0.85, 0.95}`. B6c's output
  effect is **positive in only 4 of 18 cells** and reverses between `sigma` 1.5
  and 2.0 at `gamma = 0.85`. **The dominance claim is withdrawn** and replaced
  by a stated validity region.

- **F1 (second part) — the "not a knife-edge case" argument is withdrawn.**
  Under the model's own technology, `dv({M})/dM / dY/dM = s_M^(gamma/rho − 1)`
  exactly, so the inequality holds *identically* whenever `gamma > 1 − 1/sigma`.
  100% incidence is a tautology at this calibration and is not evidence.

- **F2 — the fund is not robustly stable.** `(1−rho)r_f = 0.0200` while realised
  growth ranges ≈0.0166–0.0339 across seeds, so a substantial share of runs are
  on a **divergent** path. The reported terminal 17% of GDP is not a steady
  state. Parameters were **not** changed to make this go away; divergence is
  reported as a finding.

- **F4 — spending matching is explicit.** Arms were claimed to be
  "revenue-matched by construction" and were not. `fiscal.spending_mode`
  selects between the audited behaviour and genuine matching.

- **F6 — employment metrics relabelled.** The quantity reported as "Hours" was
  aggregate labour demand in efficiency units. Efficiency units, headcount and
  hours are now separate and never conflated. This model has no extensive
  employment margin, so headcount is a displacement measure, not unemployment.

- **Rate function completed to ten terms.** The code implemented seven of the
  ten terms of Eq. (11): it had no `E_disp`, `X_ext` or `B_broad`, and fed `S_i`
  into the slot reserved for payroll-base erosion `R_rev`. All ten are now
  implemented at the manuscript's own Table VII weights, and `R_rev` measures
  what Eq. (2) defines. The worked example reproduces exactly.

### Implemented

- Configuration-driven package `src/cdos/` — nothing that affects a result is
  hard-coded in a model function
- Exact five-factor Shapley game `{H, A, R, D, K}` over all `2^5−1 = 31`
  coalitions, with a cost-share alternative for ablation
- Autonomous Economic Activity Passport: schema, registry, validation
- Substitution/augmentation classifier with controlled error injection and an
  induced confusion matrix
- Three-jurisdiction Deployment Nexus with strategic shifting and leakage
- Four-channel waterfall with an explicit `kappa` earned-income shield
- Fiscal digital-twin screening interface, with seed-overfitting protection
- Six new comparison arms: B7 optimal linear capital tax, B8 consumption-tax
  shift, B9 lump-sum-financed variant, B10 EITC-style wage subsidy, B11
  `phi = 0`, B12 Thuemmel-style robot tax
- Evaluation layer: equivalent variation, deadweight loss, revenue per unit
  DWL, incidence by factor and decile, Atkinson index, revenue volatility
- Statistical layer: paired contrasts, sign-flip permutation tests, Holm
  multiplicity control, seed-adequacy analysis, practical-significance
  thresholds
- 27 configuration-driven experiments (E01–E17, A01–A10)
- Test suite: 214 unit tests plus integration, regression and numerical suites

### Fixed

- Cobb-Douglas singularity at `sigma = 1` — was a division by zero, now the
  explicit limit in both the unit cost and the aggregator
- Wage bisection bracket was never checked; it now verifies and expands rather
  than returning an endpoint that is not a root
- `paired_contrast` no longer reports a percentage change of zero when the
  control is identically zero; it reports the quantity as undefined
- Arm B11 raised contribution revenue but was excluded from the distribution
  waterfall, so none of it reached the fund
- `classifier.error_rate` and `nexus.shifting_elasticity` were configurable but
  never read by the run loop, so experiments E06 and E10 measured nothing at
  any setting. Both are now wired and covered by regression tests

### Reproducibility Changes

- Pinned `requirements.txt`, `requirements-dev.txt`, `environment.yml`,
  `.python-version` (Python 3.11.9 / NumPy 1.26.4 — the verified pair)
- `Dockerfile` including LaTeX; the build fails if the tests do not pass
- `Makefile` pipeline: `test`, `smoke`, `main`, `experiments`, `ablations`,
  `tables`, `figures`, `verify`, `paper`, `reproduce`
- Machine-readable manifests for every run: git SHA and dirty state, config
  hash and full config, interpreter and package versions, machine, seeds,
  runtime, SHA-256 of every input and output
- `scripts/verify_generated.py` fails CI when a paper table has drifted from
  the results that produced it
- GitHub Actions: `ci.yml` (lint, four test suites, smoke campaign, artefact
  validation) and `reproduction.yml` (the heavy matrix, on demand)

### Paper Changes

The Results section is rewritten and a Sensitivity section added. Specifically:

- the headline result is stated **conditionally**, with the validity region
  from E01, and the dominance claim is withdrawn;
- the circular "not a knife-edge case" argument is removed and replaced with
  the structural condition `gamma > 1 - 1/sigma`;
- the revenue-matching claim is withdrawn (it appeared twice);
- three further reversals are reported: horizon, automation speed, and
  attribution granularity;
- cross-border leakage and classification error are reported for the first
  time, the testbed previously having had one jurisdiction;
- the employment column is relabelled as efficiency units;
- confidence intervals are labelled as replication intervals, with the sweep
  identified as where structural uncertainty lives;
- the F9 unit error is corrected;
- all results are labelled synthetic;
- every numerical table is generated and included with `\input`.

The manuscript builds clean at 17 pages with no undefined references or
citations.

### Breaking Changes

- `simulation/cdos_sim.py` is **frozen** and must not be used for results. It
  is retained solely as the regression target.
- Results produced before this release are not comparable: the budget did not
  close, so the SAC arms' magnitudes were inflated.
- `RateConfig` weight names changed to match Eq. (11)
  (`w_eta` now weights `R_rev`, `w_gamma_e` weights `E_disp`).

### Known Blockers

- **Digital twin (Eq. 26)** — the manuscript specifies neither the search
  space, the normalisation `U~_k`, the numeric floors and ceiling, nor the
  weights `omega_k`. The interface is complete and refuses to run without them.
- **Calibration** — licensed sources cannot be redistributed; the pipeline
  exists but has not been run. **All results are synthetic.**
- **Author identity** — placeholders only; nothing invented.

---

## [v0-audit] — 2026-09-06 — the audited baseline

The pre-remediation state, preserved unmodified. Contains the three P0 defects
F1, F2 and F3 plus F4–F9. Reproduces `results.json` bit-exactly to md5
`788ce3e75b2417de34b445479a0bbdf1` under Python 3.11.9 / NumPy 1.26.4.

Do not build on this tag. It exists as evidence.
