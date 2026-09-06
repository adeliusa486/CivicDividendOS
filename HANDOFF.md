# HANDOFF

For whoever picks this up next — researcher or agent. Read `MEMORY.md` first;
this file says where things stand *today* and what to do next.

**Date:** 2026-09-06
**Baseline tag:** `v0-audit`
**Working branch:** `master`

---

## 1. Current state in one paragraph

The independent audit of 2026-09-06 found three P0 defects. All three are fixed
in `src/cdos/`, which reproduces the audited baseline **bit-exactly** under
`legacy_mode` and corrects it otherwise. The corrections changed the results:
the headline claim that arm B6c dominates is **not supported in general**. It
holds only in a small region of the `(sigma, gamma)` parameter space. The fund
is not robustly stable. The manuscript must be revised to say both.

---

## 2. What is done

- [x] Whole-directory inspection; audit read in full
- [x] Baseline reproduced bit-exactly (`results.json` md5 `788ce3e7…`) before any change
- [x] Git initialised; pre-remediation state committed and tagged `v0-audit`
- [x] Package structure, configuration system, manifests, seeding policy
- [x] **F3** budget closure — full liability debited; per-period accounting enforced
- [x] **F2** fund stability — margin computed on every run; divergence reported
- [x] **F1** `sigma`/`gamma` exposed; E01 sweep run and analysed
- [x] **F4** `spending_mode` explicit
- [x] **F6** efficiency units / headcount / hours separated
- [x] Ten-term rate function; worked example reproduces exactly
- [x] Five-factor Shapley over all 31 coalitions; AEAP; classifier; nexus; waterfall; twin interface
- [x] Arms B0–B6c plus B7–B12, each tested and each reducing to B0 when disabled
- [x] Evaluation layer: welfare, DWL, revenue-normalised metrics, incidence, Holm multiplicity
- [x] Test suite: 214 unit + integration + regression + numerical, all passing
- [x] E01 complete and analysed
- [x] Environment pins, Dockerfile, Makefile, CI, reproduction workflow
- [x] README, MEMORY.md, CONTRIBUTING, SECURITY, LICENSE, CITATION, traceability matrix

## 3. What remains

- [ ] Finish running the remaining experiments (E02–E17, A01–A10) — the runner
      works and E01 is done; the rest is wall-clock time
- [ ] Regenerate tables and figures from the completed results (`make tables figures`)
- [ ] **Revise the manuscript** against the corrected results — this is the
      largest remaining task; see §5
- [ ] Compile the PDF and check no `[RESULT TO BE GENERATED]` placeholder survives
      for an experiment that has now been run
- [ ] Fill the author block (`CITATION.cff`, manuscript) — **requires author input**
- [ ] Push to GitHub — **no remote is configured; requires the repository URL**

## 4. Known issues and blockers

| Item | Nature | What is needed |
|---|---|---|
| Digital twin, Eq. (26) | **BLOCKED** | Search space bounds, the normalisation `U~_k`, numeric floors/ceiling, and the weights `omega_k`. All unspecified in the manuscript. The interface is complete and refuses to run without them. |
| Calibration | **BLOCKED** | Licensed sources (IFR World Robotics) cannot be redistributed. Pipeline exists, has not been run. All results are synthetic. |
| `X_ext`, `B_broad` indices | Limitation | No observable counterpart in the testbed; held at the paper's own constants. |
| `gamma = 0.95` row of E01 | Numerical | Near-constant returns makes firm scale explosive (output ~1e11). Treat as a boundary diagnostic, not a policy result. |
| Author identity | **BLOCKED** | Placeholders only. Nothing was invented. |
| GitHub remote | **BLOCKED** | None configured. Repository is ready to push. |

## 5. The manuscript changes that are required

Do **not** preserve a claim merely because it was in the old paper.

1. **Restate the headline result conditionally.** B6c does not dominate. Report
   the E01 grid and the validity region (`sigma ≲ 1.7` at `gamma = 0.85`).
2. **Remove the "not a knife-edge case" argument.** `dv({M})/dM < p_M` holding
   for every firm in every quarter is a tautology whenever `gamma > 1 − 1/sigma`.
   Say that it is a property of the calibration.
3. **Correct the fund discussion.** The terminal 17% of GDP is not a steady
   state. `(1−rho)r_f = 0.0200` against realised `g ≈ 0.017–0.034` across seeds.
   Table VI's arithmetic is correct; its assumed `g = 0.03` is not delivered.
4. **State that the budget now closes**, and that it did not before.
5. **Relabel "Hours"** as labour demand in efficiency units, everywhere.
6. **Withdraw or qualify "revenue-matched by construction."**
7. **Fix the worked-example unit error (F9).**
8. **Separate replication from structural uncertainty.** The bootstrap CIs are
   CRN replication intervals; say so, and point at E01 for the structural
   spread.
9. **Label all results as synthetic**, and say the calibration has not been run.
10. **Replace hand-pasted numbers with `\input{paper/generated/…}`.**

## 6. Commands

```bash
make install        # pinned environment
make test           # everything
make test-fast      # skip the slow regression comparisons
make smoke          # two-seed campaign, ~1 minute
make main           # 50-seed headline campaign
make experiments    # E01–E17
make ablations      # A01–A10
make tables         # regenerate every LaTeX table
make figures        # regenerate every figure
make verify         # fail if a paper table drifted from its results
make paper          # compile the PDF
make audit          # re-run the original audit harness
```

One experiment: `python scripts/run_experiment.py experiments/E01_sigma_gamma.yaml`
One override: `python scripts/run_campaign.py --set technology.sigma=2.0`

## 7. Files that matter most

| Path | Why |
|---|---|
| `MEMORY.md` | The full history and the reasoning behind every change |
| `docs/traceability.md` | Every paper claim → implementation → test → experiment |
| `src/cdos/config.py` | Every parameter; nothing that affects a result lives elsewhere |
| `src/cdos/model/economy.py` | The run loop; the F3 and F4 corrections are here |
| `src/cdos/model/accounting.py` | Why the budget closes now |
| `src/cdos/model/fund.py` | The F2 stability diagnostics |
| `tests/regression/` | Proof that `legacy_mode` is still bit-exact |
| `audit/` | **Frozen.** The original findings and their reproduction scripts |
| `simulation/` | **Frozen.** The audited baseline; the regression target |

## 8. Last verified

| | |
|---|---|
| Baseline reproduction | Bit-exact, `results.json` md5 `788ce3e75b2417de34b445479a0bbdf1` |
| Test suite | 214 unit + integration + regression + numerical — all passing |
| Environment | Python 3.11.9, NumPy 1.26.4, Windows 11 |
| E01 | Complete, 18 cells × 4 arms × 10 seeds |
| Release status | **NOT PUSHED — no GitHub remote configured** |

## 9. Rules

1. Never loosen a numerical tolerance to make a test pass.
2. Never delete a failing test that reveals a scientific problem.
3. Never modify `simulation/` or `audit/`.
4. Never report a result that was not produced by a run recorded in
   `results/manifests/`.
5. If something cannot be done honestly, write **BLOCKED — requires author
   decision** and say precisely why.
