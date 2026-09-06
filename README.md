# CivicDividendOS

**Attribution-based taxation of autonomous economic activity: a framework and a
computational testbed.**

---

## Research question

As AI agents and robots take over a growing share of production, tax systems
built on human wage income lose their base. Existing proposals tax the *count*
of robots or the *cost* of machines. This project asks a different question:

> Can the economic **origin** of value — how much of a firm's output is
> attributable to human labour, to AI agents, to robots, to data and to capital —
> be measured well enough to serve as a tax base, and does taxing that base
> behave better than taxing robot counts or capital income?

## Contribution

The genuine contribution is the **Shapley value of a factor as a tax base**, and
the results that follow from taking that seriously:

- **Proposition 2 (marginal incidence).** Attributed value is inframarginal
  while the cost deduction is marginal. Deducting machine costs in full
  (`phi = 1`) makes an extra machine *reduce* the taxable base, so a levy on
  that base is marginally a **subsidy** to automation, not a corrective. Any
  `phi <= 1/2` restores non-negative marginal incidence.
- The separation of **measurement** (what produced the value), **liability**
  (who owes) and **distribution** (where the money goes) into three independent
  layers, so that each can be evaluated on its own terms.
- A **bounded, monotone adaptive rate** (Proposition 3) that discriminates
  between automation which substitutes for workers and automation which
  complements them — something a fixed robot tax cannot express.

## Current status

This repository is the **post-remediation** state. An independent audit
(`audit/`, performed 2026-09-06) found three P0 defects in the original work.
All three have been fixed, and the fixes changed the results. See
[CHANGELOG.md](CHANGELOG.md) and [MEMORY.md](MEMORY.md) for the full record.

| Finding | Issue | Status |
|---|---|---|
| **F1** | The headline robustness claim is circular; the result reverses with `sigma` | Fixed — `sigma`/`gamma` are configuration; E01 maps the validity region |
| **F2** | The fund stability condition fails at the model's realised growth rate | Fixed — diagnosed on every run; E03 sweeps it |
| **F3** | The government budget does not close in B6/B6c (~93% of revenue never debited) | Fixed — full liability debited; per-period accounting enforced |
| **F4** | "Revenue-matched" arms were not actually matched | Fixed — `spending_mode` is explicit |
| **F5** | A headline comparison used the wrong quantity | Fixed — revenue-normalised metrics reported alongside |
| **F6** | "Hours" was labour demand in efficiency units | Fixed — efficiency units, headcount and hours reported separately |
| **F9** | Worked-example unit error | Addressed in the manuscript revision |

## Important scientific caveats

Read these before using any number in this repository.

1. **These are model outputs, not empirical estimates.** No result here has been
   calibrated against national accounts, robot-stock series or labour
   microdata. `configs/calibration.yaml` records which targets remain
   `NOT_FETCHED` and why (several sources are licensed and cannot be
   redistributed). Every reported magnitude is **synthetic**.
2. **The central result is conditional, not general.** B6c's output advantage
   holds only in a limited region of the `(sigma, gamma)` space. Outside it the
   sign reverses. The region is mapped in E01 and reported honestly in the
   paper; it is not a universal dominance result.
3. **The fund is not robustly stable.** At the paper's calibration
   `(1-rho) r_f = 0.0200` while realised growth ranges roughly 0.017–0.034
   across seeds, so a substantial fraction of runs are on a **divergent** path.
   A terminal fund level on a divergent path is not a steady state.
4. **This is not a multi-agent LLM system.** There are no LLM agents, no
   prompts, no tool use and no inter-agent messaging. "Agents" here means
   *economic* agents: heterogeneous households and firms, and AI agents as a
   factor of production.
5. **This is not a robotics simulator.** There is no controller, no sensor
   model, no physics and no sim-to-real component. Robots enter economically,
   as part of a machine factor.
6. **Two rate indices are exogenous.** `X_ext` (externality) and `B_broad`
   (broad ownership) have no observable counterpart in this testbed; they are
   held at the manuscript's own worked-example values. They are wired, bounded
   and tested — not derived.

## Not advice

This is research software. Its outputs are **not legal, tax, financial or
investment advice**. Simulated rates are not real tax rates. The Deployment
Nexus is a research construct, not a statement about any jurisdiction's law;
adoption would require coordination with the OECD/G20 two-pillar framework. The
AEAP does **not** create legal personality for any AI agent or robot — the
statutory taxpayer is always the human or corporate owner. Task-level metering
of the kind the framework assumes raises real privacy questions that the
framework as specified does not resolve.

## Repository structure

```
├── src/cdos/              the model
│   ├── config.py          every run-time parameter, hashable, YAML-loadable
│   ├── model/             production, Shapley, rate, fund, waterfall, nexus,
│   │                      accounting, economy (the run loop)
│   ├── framework/         AEAP, classifier, digital twin
│   ├── eval/              metrics, uncertainty, campaign
│   └── utils/             manifests
├── configs/               base specification, policies, calibration targets
├── experiments/           E01–E17 and A01–A10, one YAML each
├── scripts/               campaign and experiment runners, tables, figures
├── tests/                 unit, integration, regression, numerical
├── results/               raw, processed, manifests, summaries
├── paper/generated/       LaTeX tables and figure data — never edited by hand
├── audit/                 the independent audit, preserved unmodified
└── simulation/            the audited baseline, frozen as a regression target
```

`simulation/` is **frozen**. It is the audited baseline and exists so that
`legacy_mode` can be proved bit-exact against it. Do not use it for results.

## Installation

Requires **Python 3.11.9** and **NumPy 1.26.4** — the pair under which the
campaign reproduces bit-exactly.

```bash
python -m pip install -r requirements-dev.txt
python -m pip install -e . --no-deps
```

Or with conda:

```bash
conda env create -f environment.yml && conda activate cdos
```

Or in Docker (includes LaTeX):

```bash
docker build -t cdos .
docker run --rm -v "$PWD:/work" cdos make reproduce
```

## Quick start

```bash
make test          # the whole suite
make smoke         # a two-seed campaign, about a minute
make main          # the 50-seed headline campaign
make experiments   # E01–E17
make ablations     # A01–A10
make tables        # regenerate every LaTeX table from results/
make figures       # regenerate every figure from results/
make paper         # compile the manuscript
```

To run one experiment:

```bash
python scripts/run_experiment.py experiments/E01_sigma_gamma.yaml
```

To change a parameter without editing any source:

```bash
python scripts/run_campaign.py --set technology.sigma=2.0 attribution.phi_deduct=0.5
```

## Configuration

Every quantity the model reads lives in `src/cdos/config.py` and can be set from
YAML or with a dotted override. Nothing that affects a result is hard-coded in a
model function — that was the proximate cause of finding F1, since `sigma` and
`gamma` were reachable only by editing source, so no sensitivity analysis was
ever run.

`configs/base.yaml` is the corrected main specification.
`configs/policies/audited_baseline.yaml` reproduces the audited code exactly,
defects and all, and exists **only** so the regression suite can prove what
changed.

## Reproducibility

Every run writes a manifest to `results/manifests/` recording the git SHA and
dirty state, the config hash and full configuration, the interpreter and package
versions, the machine, the seeds, the runtime, and a SHA-256 of every input and
output file.

The audited baseline reproduces **bit-exactly**: `results.json` regenerates to
md5 `788ce3e75b2417de34b445479a0bbdf1` under Python 3.11.9 / NumPy 1.26.4, and
`tests/regression/` asserts that `legacy_mode` matches
`simulation/cdos_sim.py` to the last bit on every reported statistic.

All numerical tables in the paper are generated by `make tables` and pulled in
with `\input`. `scripts/verify_generated.py` fails if any of them has drifted
from the results that produced it, and CI runs it.

## Data

No external data is bundled. `configs/calibration.yaml` lists each intended
calibration target, its source and its status. Several sources (notably IFR
World Robotics) are licensed and prohibit redistribution, so this repository
ships fetch scripts, checksums and transformation code rather than the data.
**The calibration has not been run.** Results are synthetic and labelled so.

## Limitations

Beyond the caveats above: the model has one composite machine factor rather than
the five the framework distinguishes (E12 measures what that costs); no explicit
data or intangible input; a single good; no entry or exit; an exogenous machine
price rather than endogenous innovation; and no extensive employment margin, so
"headcount" is a displacement measure and not an unemployment rate. Coalition
values are counterfactual and not directly observed, so attribution inherits the
error of the estimator — the manuscript's own limitations section identifies
this as the single largest obstacle to implementation, and this repository does
not solve it.

## Citation

See [CITATION.cff](CITATION.cff).

## Author

**Author details are not recorded in this repository and require author input.**
The manuscript's author block, ORCID, affiliation and contact address must be
supplied before publication; placeholders are not filled in with invented
identities. See `HANDOFF.md`.

## Licence

Code: MIT (see [LICENSE](LICENSE)). The manuscript and figures are the author's
and are not covered by the code licence.
