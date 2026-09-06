# CivicDividendOS — Project Handoff

**Last updated:** 2026-09-06
**Folder:** `C:\Users\adeel\OneDrive\Desktop\4-agents-robots-taxation-financial\`
**Status:** Manuscript complete with real simulation results. Compiles clean. Not yet submitted.

---

## 1. What this is

A Q1-target paper proposing **CivicDividendOS** — a factor-origin fiscal ledger and public
automation dividend framework for economies where humans, AI agents, and robots produce jointly.

Core idea: separate three questions that are usually conflated.
1. *Who created the value?* → Factor-Origin Ledger (Shapley attribution over 5 factors)
2. *Who is legally liable?* → Autonomous Economic Activity Passport (owner of record; **no machine legal personality**)
3. *Who shares the returns?* → bounded adaptive Social Automation Contribution → Earned-Income Shield + Public Automation Wealth Fund → 4 distribution channels

---

## 2. File inventory

| File | What it is |
|---|---|
| `CivicDividendOS_v2.tex` | **The manuscript.** 97 KB, IEEEtran `[journal]`, 15 pp. |
| `civicdividendos.bib` | 42 entries, all cited, none uncited |
| `CivicDividendOS_v2.pdf` | Compiled output |
| `simulation/cdos_sim.py` | The evaluation testbed (heterogeneous-agent model) |
| `simulation/driver.py` | Runs the 8-arm × 50-seed campaign, emits tables |
| `simulation/mklatex.py` | Turns `results.json` into the LaTeX table/figure blocks |
| `simulation/results.json` | Full campaign output with bootstrap CIs |
| `CivicDividendOS_AI_Robot_Tax_Distribution_Framework.*` | **ORIGINAL v1** — untouched, 8 pp., conference format |

The v1 files are the author's original. Everything with `_v2` or in `simulation/` was produced
in the upgrade. v1 was never modified.

---

## 3. How to build

```bash
pdflatex CivicDividendOS_v2.tex && bibtex CivicDividendOS_v2 && pdflatex CivicDividendOS_v2.tex && pdflatex CivicDividendOS_v2.tex
```

Toolchain on this machine: **MiKTeX** at `C:\Users\adeel\AppData\Local\Programs\MiKTeX\`
(not TeX Live — v1's log shows TeX Live 2022, but MiKTeX is what's on PATH now).
Requires: IEEEtran.cls + IEEEtran.bst, tikz, pgfplots, algorithmicx, booktabs, microtype. All present.

To re-run the simulation (~207 s on 16 workers, 20 cores available):
```bash
cd simulation && python driver.py && python mklatex.py
```

**Current build state:** 0 errors, 0 overfull boxes, 0 LaTeX warnings, 0 dangling refs,
0 unreferenced labels, 1 BibTeX warning (see §7). 2 minor underfull hboxes (badness <3200,
cosmetic, normal for two-column with inline math — v1 had badness 10000).

---

## 4. What was done (v1 → v2)

v1 was a well-argued proposal with **no figures, no tables, no formal results, no evaluation**.
Diagnosis was Case A: strong framing, weak rigor. The upgrade added analysis, not volume.

**Structure:** 16 loose sections → 14. Added Related Work positioning, formal Problem
Formulation, Governance Safeguards, Discussion, Limitations. Folded the redundant "Expected
Contributions" section into the Introduction. Abstract cut ~600 → ~260 words.
Class changed `[conference]` → `[journal]` (revert instructions are in the .tex header comment).

**Now contains:** 5 figures, 8 tables, 1 algorithm, 8 propositions (all proved), 6 numbered
assumptions.

**Eight propositions:**
1. Budget balance (Shapley efficiency ⇒ Σφ=1, no double counting)
2. **Marginal incidence of the contribution base** — see §5, this is the important one
3. Rate boundedness + monotone comparative statics
4. Lipschitz bound on misclassification cost: `|E[r]−r*| ≤ ε(α+θ)`
5. Shield feasibility (`ω+κ≤1`) + first-order Laffer correction
6. Fund stability: `(1−ρ)r_f < g`, `f* = s(1+g)/(g−(1−ρ)r_f)`
7. Payout paradox: `∂d*/∂ρ` has the sign of `(g−r_f)`
8. Exhaustive nexus apportionment

Every proposition was **verified numerically before being written into the paper**
(Lipschitz bound checked over 2×10⁵ draws, max violation 1.7e-16; the marginal-Shapley
derivative checked against central differences to 1.6e-9).

---

## 5. The most important finding — read this first

Implementing the paper's own base definition `ACB = ψ_M − p_M·M` revealed it is
**marginally subsidising the automation it is meant to price.** The derivation is exact:

```
∂ACB/∂M = ½(∂v({M})/∂M − p_M) < 0
```

The Shapley term ψ_M is *inframarginal* (it credits the machine with half the complementarity
surplus it shares with labour); the cost deduction is *marginal*. So an extra machine shrinks
the taxable base, and a levy on that base lowers the effective machine price.

This is **not a knife-edge case** — it held for 100% of firms in every quarter of every run,
with an effective wedge of −3.3% to −4.1% of the machine price.

**Fix:** deduct at most half of machine costs (φ ≤ ½), which restores `∂ACB/∂M ≥ 0`.
This is now Proposition 2 plus a corrected-base variant (arm B6c), and it is the paper's
strongest original contribution. It was discovered *by* building the simulation — it is not
visible from the algebra alone.

---

## 6. Simulation results (Table VII in the paper)

Model: 500 firms, 10,000 households, CES production in (labour, composite machine factor),
σ=1.5, span of control γ=0.85, machine price falling 0.6%/quarter, 240 quarters,
8 arms × 50 seeds, common random numbers, paired bootstrap CIs.

Two design points that matter: the model computes the **actual Shapley attribution**
(ψ_L + ψ_M = Y identically, not a proxy), and **all arms finance identical public spending**
with the labour tax clearing the budget — so τ_L is an *outcome*, and the Earned-Income Shield
shows up directly as the tax cut automation revenue buys.

| Arm | Regime | ΔGDP% | Hours% | Wage share | Gini(inc) | τ_L | Fund %GDP | Div %GDP |
|---|---|---|---|---|---|---|---|---|
| B0 | Baseline | +0.00 | +0.00 | 0.298 | 0.3296 | 0.381 | 0.0 | 0.00 |
| B1 | Fixed robot tax | **−6.12** | +3.34 | 0.341 | 0.3245 | 0.325 | 0.0 | 0.00 |
| B2 | Capital-income tax ↑ | +0.84 | +1.20 | 0.298 | 0.3255 | 0.356 | 0.0 | 0.00 |
| B3 | UBI via general tax | −1.05 | −1.55 | 0.297 | **0.3147** | 0.413 | 0.0 | 0.00 |
| B4 | Auto tax + retraining | −0.72 | **+8.52** | 0.338 | 0.3247 | 0.352 | 0.0 | 0.00 |
| B5 | Wealth fund only | −0.10 | −0.14 | 0.298 | 0.3283 | 0.384 | 7.4 | 0.17 |
| B6 | CDOS, base as specified | +2.66 | +1.77 | 0.298 | 0.3283 | 0.383 | 4.5 | 0.09 |
| B6c | **CDOS, corrected base** | +3.30 | +7.24 | 0.317 | 0.3229 | 0.371 | 17.0 | 0.29 |

**The results deliberately do not flatter the proposal.** Key honest findings:
- **B1 (fixed robot tax) is the costliest arm** (−6.12% output) — vindicates the attribution-gap argument.
- **B6 as literally specified is near-inert** — raises 0.25% of GDP, ΔGini −0.0013 (negligible).
- **B6c is the only arm improving on baseline in output, hours, labour share, inequality AND τ_L simultaneously.**
- **B3 (UBI) beats B6c** on inequality and poverty (9.95% vs 11.4%). Transfers win near-term.
- **B4 beats B6c** on employment (+8.52 vs +7.24) at lower output cost.
- No arm dominates. This nuance is written *into* the paper, not around it.

**Three cross-validations between the analytics and the simulation:**
- B6c's yield (0.98% of GDP) brackets the 0.65% the inverse design of Prop. 6 predicted.
- The 71-year fund half-life shows up as B6c's dividend reaching only 0.29% of GDP after 50 yr.
- Fund at 17% of GDP after 50 yr is consistent with the analytic steady state given ramping inflow.

---

## 7. Outstanding items

**Only the author can settle these:**
1. **Author block** — still `Author Name / Affiliation / Email`. Deliberately not invented.
2. **Journal class** — currently IEEEtran `[journal]`. Many Q1 venues here (TFSC, Government
   Information Quarterly) are Elsevier. Revert to `[conference]` per the .tex header if needed.
3. **Three bib entries still flagged:**
   - `IMF2026GlobalAI` — confirm series/report number
   - `APF` (Alaska Permanent Fund) — access date + URL
   - `DimitropoulouAIIncome` — **chapter authorship could not be confirmed.** Search suggests
     the intended source may be her monograph *Robot Taxation: A Normative Tax Policy Analysis*,
     IBFD Doctoral Series 70, 2024, rather than an Edward Elgar chapter. This is the 1 remaining
     BibTeX warning (empty year).
4. **Verify remaining DOIs.** Only high-confidence ones were added. Note: Guerreiro's real DOI is
   `10.1093/restud/rdab019` — I would have guessed `rdab033` wrong, which is why unverified DOIs
   were left blank rather than guessed.

**Genuine research gaps (stated in the paper's Limitations):**
- Model is stylised: **one composite machine factor, not the five the framework distinguishes**;
  single good; single jurisdiction (so the nexus rule of §VII is never exercised); exogenous
  machine price; no entry/exit. Sign and ordering of effects are more credible than magnitudes.
- No calibration against national accounts / robot-stock data. This is the main empirical gap.
- Coalition-value estimator never validated against observed counterfactuals.

---

## 8. Bibliography entries verified by web lookup (2026-09-06)

Resolved from `[INCOMPLETE]`: Beraja & Zorzi (the entry had **no author** in v1),
Korinek & Lockwood NBER 34873, Corneo (*J. Gov. Econ.* 5:100033), Faivre's first name
(Juliette, not Julien), Zhang (59:500–509), Acemoglu–Manera–Restrepo NBER 27052,
Le Grand (LSE PPR 1(2), doi 10.31389/lseppr.8), ILO (Ortiz et al., ESS WP 62, 2018),
Guerreiro DOI. BibTeX warnings went 4 → 1.

~15 well-established references were added to v1's original 27 (Shapley 1953, Mirrlees 1971,
Diamond–Mirrlees 1971, Atkinson–Stiglitz 1976, Autor–Levy–Murnane 2003, Frey–Osborne 2017,
SHAP, Data Shapley, AI Economist, OECD two-pillar, Piketty, Van Parijs). All real; metadata
kept minimal where uncertain rather than guessed.

---

## 9. Operational gotchas (save yourself the debugging)

- **The Bash tool's heredocs strip one backslash level.** `\\addplot` in a `<< 'EOF'` heredoc
  arrives as `\a` (BEL byte); `\n`, `\r`, `\b`, `\t` are all silently corrupted. This
  **injected control characters into the .tex twice** before it was caught.
  → For any LaTeX content, use the Write/Edit tools, or build strings with `chr(92)` / `chr(10)`
    and no literal escapes at all.
- **pgfplots `width=` sizes the axis box, not the labels.** `width=\columnwidth` overflows;
  use `0.94\columnwidth`.
- Wide tables need `\scriptsize`, not `\footnotesize`, in IEEEtran two-column.
- Paragraph rule enforced throughout: **one paragraph = one continuous line, no internal
  line breaks.** A checker script confirms 0 violations; longest prose line is 2184 chars.
  Keep this if editing.
- IEEEtran + amsthm needs `\let\proof\relax` before loading amsthm (already in the preamble).

---

## 10. Quick verification commands

```bash
grep -c "Overfull" CivicDividendOS_v2.log
grep -c "LaTeX Warning" CivicDividendOS_v2.log
```
Both should be 0. If a rebuild produces control-character errors, see §9.
