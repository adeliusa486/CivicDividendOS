# MEMORY.md — project memory

**Purpose.** Everything a future researcher or agent needs in order to continue
this work without rediscovering its history. Read this before changing anything.

Last updated: 2026-09-06.

---

## 1. Project identity

| | |
|---|---|
| **Name** | CivicDividendOS |
| **Objective** | Determine whether the *attributed economic origin* of value — the Shapley value of a factor of production — can serve as a tax base as AI agents and robots displace human labour, and whether taxing that base behaves better than taxing robot counts or capital income. |
| **Status** | Post-remediation. All three P0 audit findings fixed. The central claim has been **narrowed**, not confirmed. |
| **Repository root** | `C:\Users\adeel\OneDrive\Desktop\4-agents-robots-taxation-financial` |
| **Manuscript** | `CivicDividendOS_v2.tex` (current). `CivicDividendOS_AI_Robot_Tax_Distribution_Framework.tex` is an older draft. |
| **Model** | `src/cdos/` (corrected). `simulation/cdos_sim.py` is the **frozen** audited baseline, kept only as a regression target. |
| **Audit** | `audit/` — preserved unmodified. |

---

## 2. Research contribution

The genuine contribution, as the audit itself identified, is **Shapley
attribution as a tax base** and what follows from taking it seriously:

- **Proposition 2 — marginal incidence.** Attributed value `psi_M` is
  inframarginal; the cost deduction `phi*p_M*M` is marginal. So
  `d(ACB)/dM = ½ dv({M})/dM + (½ − phi) p_M`. Under full deduction (`phi = 1`)
  this is negative whenever the machine's stand-alone marginal product falls
  below its price — the levy is then marginally a **subsidy** to automation.
  Any `phi ≤ ½` restores non-negative marginal incidence. This is the sharpest
  result in the paper and it is a *warning*, not a selling point.
- **The condition `gamma > 1 − 1/sigma`.** Under the CES-with-span-of-control
  technology, the ratio of the stand-alone to the joint marginal product is
  exactly `s_M^(gamma/rho − 1)`. So Proposition 2's inequality holds
  *identically* whenever `gamma > rho`. **Universal incidence across every firm
  and quarter is a property of the calibration, not evidence about the world.**
  The original paper reported it as the latter. That was finding F1.
- **Three separable layers:** measurement (what produced the value), liability
  (who owes it), distribution (where it goes). Each is independently
  evaluable and independently ablatable.
- **A bounded, monotone adaptive rate** (Proposition 3) that discriminates
  between substituting and complementing automation — which a fixed robot tax
  cannot express. The worked example shows a 12.2× liability difference on an
  identical base.

---

## 3. IMPORTANT CORRECTION — what this project is not

**This is NOT a multi-agent LLM system.** There are:

- no LLM agents
- no prompts
- no tool-using AI agents
- no inter-agent communication or messaging

The word "agents" means **economic** agents: heterogeneous households and firms,
and AI agents as a *factor of production* alongside robots, data and capital.

**This is NOT a robotics simulator.** There is no controller, no sensor model,
no physics engine, no sim-to-real component. Robots enter economically, as part
of a composite machine factor.

Do not redesign this project as an LLM multi-agent framework unless the research
specification is explicitly changed. Directory and module names deliberately
avoid `agents/` for this reason.

---

## 4. Audit history

- **Audit date:** 2026-09-06. Report: `audit/AUDIT_REPORT.html` (19 sections).
  Every finding is reproduced by a script in `audit/`.
- **Baseline reproduction:** verified before any change. The 400-run campaign
  regenerates `results.json` to md5 `788ce3e75b2417de34b445479a0bbdf1` —
  bit-exact under Python 3.11.9 / NumPy 1.26.4.

### Findings and status

| ID | Severity | Issue | Status |
|---|---|---|---|
| **F1** | P0 | Headline robustness claim is circular; result reverses with `sigma` | **FIXED** — `sigma`/`gamma` are configuration; E01 maps the validity region; the claim is now stated conditionally |
| **F2** | P0 | `(1−rho)r_f = 0.0200` exceeds realised `g ≈ 0.0166`; fund diverges | **FIXED** — margin computed on every run; E03 sweeps it; divergence reported, not hidden |
| **F3** | P0 | Budget does not close in B6/B6c; ~93% of SAC revenue never debited | **FIXED** — full liability debited from profit; per-period resource accounting raises on failure |
| **F4** | P1 | "Revenue-matched" was false | **FIXED** — `fiscal.spending_mode` is explicit |
| **F5** | P1 | A headline comparison used the wrong quantity | **FIXED** — revenue-normalised metrics reported alongside output effects |
| **F6** | P1 | "Hours" was labour demand in efficiency units | **FIXED** — `eff_units`, `headcount`, `hours` separated and never conflated |
| **F7/F8** | P2 | Repository and reproducibility defects | **FIXED** — package, configs, manifests, CI, Docker, automatic tables |
| **F9** | P2 | Worked-example unit error | **Manuscript revision pending** |

---

## 5. Implementation history

### C1 — F3, budget closure (2026-09-06)
- **Problem:** SAC revenue booked but not debited; error asymmetric, inflating
  exactly the recommended arms.
- **Original:** `profit = Y − wL − pm_eff·M`, where `pm_eff` carried only the
  marginal wedge.
- **New:** `pm_eff` stays the *marginal decision price* (so behaviour is
  unchanged); the full liability `r_i·ACB_i` is debited from profit as a lump
  sum. Per-period `ResourceAccount` asserts closure and raises.
- **Files:** `src/cdos/model/accounting.py`, `economy.py`.
- **Tests:** `tests/integration/test_budget_closure.py` (30).
- **Verification:** budget closes in all 14 arms, every period. B1/B4 unchanged
  to 1e-12, confirming the audit's asymmetry claim.
- **Effect:** B6c's output advantage at the paper's calibration falls from
  **+3.30%** (audited) to **+3.01%**.

### C2 — F2, fund stability (2026-09-06)
- **New:** `stability()` returns the margin `g − (1−rho)r_f` on every run;
  `stability_mode` ∈ {`require`, `warn`, `stress`}.
- **Finding beyond the audit:** realised `g` is **seed-dependent**, ranging
  ≈0.0166–0.0339. The condition therefore **holds for some seeds and fails for
  others** — roughly 40% of seeds are on a divergent path. The fund is not
  robustly stable, and reporting a terminal level as a steady state is wrong
  regardless of which seed is drawn.
- **Decision:** the parameter was **not** changed to make the result look
  better. The default calibration remains the paper's, `stability_mode: warn`,
  and the divergence is reported as a finding.

### C3 — F1, sigma/gamma robustness (2026-09-06)
- **New:** all technology parameters are configuration. E01 sweeps
  `sigma ∈ {1.2, 1.5, 2.0, 3.0, 5.0, 8.0}` × `gamma ∈ {0.75, 0.85, 0.95}`.
- **Result:** see §7. The dominance claim survives in only a small region.

### C4 — rate function completed to ten terms (2026-09-06)
- **Problem:** the code implemented 7 of the 10 terms of Eq. (11); it had no
  `E_disp`, `X_ext` or `B_broad`, and fed `S_i` into the `R_rev` slot.
- **New:** all ten terms, at the manuscript's own Table VII weights. `R_rev` now
  measures payroll-base erosion (`W/Y` falling), which is what Eq. (2) defines
  and is genuinely distinct from `S`. `X_ext` and `B_broad` have no observable
  counterpart in the testbed and are held at the paper's worked-example
  constants (0.10, 0.20) — **wired and tested, not derived**.
- **Verification:** the worked example reproduces exactly — `r̃ = 0.1160` and
  `0.0095`, liabilities 1.578 and 0.129 MU, ratio 12.2.

### C5 — framework completion (2026-09-06)
Five-factor Shapley over all 31 coalitions (exact, not sampled); AEAP schema and
registry with validation; rule-based classifier with controlled error injection;
three-jurisdiction nexus with strategic shifting; four-channel waterfall with an
explicit `kappa` shield; digital-twin screening interface.

### C6 — arms B7–B12 (2026-09-06)
Optimal linear capital tax, consumption-tax shift, lump-sum-financed variant,
EITC-style wage subsidy, `phi = 0` variant, Thuemmel-style robot tax. Each has
its own config, label, test, and reduces to B0 when disabled.

---

## 6. BLOCKED — requires author decision

These could not be implemented honestly and were **not** invented.

1. **Digital twin, Eq. (26).** The manuscript specifies the form of the
   screening problem but not: the search space bounds for any coordinate of
   `Theta`; the normalisation `U~_k`; numeric values for the revenue floor,
   innovation floor or leakage ceiling; or the scalarisation weights `omega_k`.
   `src/cdos/framework/twin.py` implements the full interface and **refuses to
   run** without all four. See `REQUIRES_AUTHOR_SPECIFICATION`.
2. **`X_ext` and `B_broad` indices.** No observable counterpart in the testbed.
   Held at the paper's worked-example constants and documented as such.
3. **Calibration.** No external data is bundled. Several sources (notably IFR
   World Robotics) prohibit redistribution. The pipeline exists; it has **not
   been run**. All results are synthetic.
4. **Author identity.** `CITATION.cff` and the manuscript author block carry
   explicit `REQUIRES AUTHOR INPUT` placeholders. No identity was invented.

---

## 7. Experiment history and headline results

See `results/summaries/experiment_status.json` for machine-readable status.

### E01 — sigma × gamma robustness (COMPLETE, 18 cells × 4 arms × 10 seeds)

**This is the most important result in the project.** B6c's output effect vs B0:

| sigma \ gamma | 0.75 | 0.85 | 0.95 |
|---|---|---|---|
| **1.2** | +3.35 | +4.78 | +0.37 |
| **1.5** | +2.35 | **+3.01** | −48.49 |
| **2.0** | +1.17 | −2.23 | −62.21 |
| **3.0** | −0.02 | −11.91 | −62.44 |
| **5.0** | −0.91 | −20.77 | −62.34 |
| **8.0** | −1.37 | −24.99 | −62.28 |

- Bold is the paper's calibration: **+3.01% [+2.47, +3.39]** (replication CI).
- **Positive in only 4 of 18 cells.** The sign reverses between `sigma` 1.5 and
  2.0 at `gamma = 0.85`, exactly as the audit predicted.
- At `gamma = 0.95` (near-constant returns) the model becomes extremely
  sensitive and firm scale explodes; treat that row as a boundary diagnostic
  rather than a policy result.
- **B6 (`phi = 1`) is positive almost everywhere but small.** That is not good
  news: by Proposition 2 full deduction makes the levy a marginal *subsidy*, so
  a positive output effect there is evidence of the defect, not of merit.

**Conclusion: B6c does NOT dominate. The claim holds only for `sigma ≲ 1.7` at
`gamma = 0.85`, and the paper must say so.**

---

## 8. Reproducibility

| | |
|---|---|
| Python | **3.11.9** |
| NumPy | **1.26.4** (this pair is the verified one) |
| OS used | Windows 11 Pro 10.0.26120 |
| Docker | `Dockerfile` (Python 3.11.9-slim + LaTeX) |
| Seeds | `seed` → `np.random.default_rng(seed)`; draw order fixed; CRN across arms |
| Config | `src/cdos/config.py`, nested dataclasses, YAML with `extends`, SHA-256 hash |
| Manifests | `results/manifests/*.json` — git SHA, dirty state, config, env, digests |

Reproduce: `make install && make test && make smoke && make reproduce`.

---

## 9. Git history

- `v0-audit` (`6f85763`) — the pre-remediation state, exactly as audited.
- `548ebd9` — corrected model package (F1–F4, F6).
- Subsequent commits — tests, experiments, pipeline, paper.

`simulation/` and `audit/` are **frozen**. Do not modify them: they are the
evidence of what the project looked like before remediation, and the regression
suite depends on `simulation/` being unchanged.

---

## 10. Warnings for whoever comes next

1. **Never loosen a tolerance to make a test pass.** F3 survived to publication
   because nothing checked whether the books closed.
2. **`legacy_mode` must stay bit-exact.** If `tests/regression/` breaks,
   something changed that nobody decided on, and this file no longer describes
   the code.
3. **Under CRN, a tight confidence interval means the simulation is
   reproducible — not that the policy conclusion is certain.** E01 is the
   proof: a result with a ±0.5pp replication interval moves by 50 percentage
   points across the parameter sweep.
4. **Do not report a fund level as a steady state** without checking the
   stability margin on the same run.
5. **Results are synthetic.** Nothing here is calibrated. Do not present any
   magnitude as an empirical estimate or as a real tax rate.
6. **Never fabricate a result, a dataset, or an experiment status.** If
   something cannot be done, write `BLOCKED — requires author decision` and say
   precisely why, as §6 does.
