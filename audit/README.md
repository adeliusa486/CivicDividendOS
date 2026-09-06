# Audit harness

Independent verification of the CivicDividendOS manuscript against its own simulation,
performed 2026-09-06. Every finding in `AUDIT_REPORT.html` is reproduced by a script here,
so you can re-check any claim rather than take it on trust.

**Nothing in `CivicDividendOS_v2.tex`, `civicdividendos.bib` or `simulation/` was modified.**
These scripts import the project's own `simulation/cdos_sim.py` rather than a copy, so they
stay honest if you edit the model — and `check_budget.py` will tell you if the source has
drifted far enough that its patch no longer applies.

## Running

```bash
cd audit
python run_all.py            # everything, ~6 min (includes the 400-run campaign)
python run_all.py --quick    # ~2 min
```

Or run any check on its own; each prints a `VERDICT:` line and exits non-zero on a
confirmed defect.

Requires **Python 3.11.9 / NumPy 1.26.4** — the combination under which the campaign
reproduces bit-exactly. Other versions may reproduce, but this pair is verified.

## What each check establishes

| Script | Finding | Severity |
|---|---|---|
| `check_reproduction.py` | Bit-exact regeneration of `results.json`; citation hygiene; paper-to-results traceability | **passes** — keep green |
| `check_sigma.py` | **F1** The "not a knife-edge case" claim is circular, and B6c's advantage reverses at σ≈2 | P0 |
| `check_budget.py` | **F3** The budget does not close in B6/B6c; ~93% of SAC revenue is never debited | P0 |
| `check_fund.py` | **F2** Proposition 6's stability condition fails at the testbed's realised growth rate | P0 |
| `check_claims.py` | **F4** "revenue-matched" is false · **F5** the 0.65% comparison uses the wrong quantity · **F6** "Hours" is efficiency units · **F9** worked-example unit error | P1/P2 |

### The three P0 findings in one paragraph each

**F1 — the headline robustness claim is circular.** The paper offers "∂v({M})/∂M < p_M holds
for every firm in every quarter of every run" as evidence that Proposition 2 is not a
knife-edge case. Under the model's own CES-with-span-of-control technology the ratio of the
stand-alone to the joint marginal product is exactly `s_M^(γ/ρ−1)` with `s_M ∈ (0,1)`, so the
inequality holds *identically* whenever `γ > ρ = 1 − 1/σ`. At γ=0.85, σ=1.5 it cannot fail, so
100% incidence is not evidence. Worse, arm B6c's output effect runs +2.21% at σ=1.5, −4.30% at
σ=2.0, −14.8% at σ=3.0. The dominance claim holds only for σ ≲ 1.7, and no sensitivity analysis
is reported — although the paper's own Metrics subsection says one is required.

**F2 — the fund does not converge.** Proposition 6 requires `(1−ρ)·r_f < g`. The testbed gives
`0.0200` against a realised growth rate of `0.0166`, so the fund-to-output ratio is on a
divergent path — still growing 21.6% over the final decade — yet the terminal 17.0% of GDP is
reported as consistent with an analytic steady state, and Table VI's 71-year half-life assumes
g=0.03. Table VI's arithmetic itself is correct; `check_fund.py` re-verifies all nine rows.

**F3 — the budget does not close in the arms the paper advocates.** The state books
`Σ wedge·ACB`, but the firm's profit line is debited only `(pm_eff − pm)·M` — about 7% of it.
So roughly 93% of the automation revenue funds the shield, fund and dividend without reducing
anyone's income, and therefore without reducing capital income or the τ_K base. Arms B1 and B4
use `pm_eff = pm(1+wedge)` with matching revenue and are exactly consistent, so the error is
**asymmetric and inflates precisely the arms being recommended**. `check_budget.py` patches
profit to debit the true liability while leaving the marginal decision price untouched, and
confirms B1/B4 are unchanged to machine precision.

## Files

- `AUDIT_REPORT.html` — the full 19-section report (local copy of the published artifact).
  Also at <https://claude.ai/code/artifact/a250ef20-0c75-45e8-8097-209d3be5717b>
- `_common.py` — path bootstrap shared by the checks
- `run_all.py` — runs everything, prints a verdict summary

## Note on `simulation/generated/`

`driver.py` and `mklatex.py` write nine artifacts (`results_table.tex`, `ci_table.tex`,
`results_fig.tex`, `table_rows.tex`, `table_ci.tex`, `fig_paths.json`, `fig_ws_*.dat`,
`fig_taul_*.dat`) that were absent from the project. They have been regenerated into
`simulation/generated/` for reference. The manuscript currently **hand-pastes** these values
rather than `\input`-ing them; `check_reproduction.py` part 3 confirms they still agree, but
nothing enforces it.
