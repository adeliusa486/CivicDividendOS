# Paper-to-code traceability matrix

Every substantive claim in the manuscript, and where its evidence lives. A claim
with no implementation, no test and no experiment is marked so explicitly rather
than left to look supported.

Legend: **T** = automated test, **E** = experiment, **—** = not evidenced.

---

## Theoretical results

| Claim | Where | Implementation | Test | Experiment | Status |
|---|---|---|---|---|---|
| Shapley efficiency: `psi_L + psi_M = Y` | Eq. (5) | `model/shapley.py::shapley_machine` | `test_two_factor_efficiency` | — | **verified to 1e-12** |
| Five-factor exactness over `2^5−1 = 31` coalitions | Remark, §III | `shapley_five_factor` | `test_five_factor_efficiency`, `test_five_factor_evaluates_all_31_coalitions` | E12 | **verified to 1e-11** |
| Symmetry, null player, monotonicity of Shapley | Shapley axioms | `shapley_five_factor` | `test_five_factor_symmetry`, `..._null_player...`, `..._monotone...` | — | **verified** |
| **Prop. 2** marginal incidence `d(ACB)/dM = ½ dv({M})/dM + (½−phi) p_M` | Eq. (10) | `shapley.py::dpsi_dM`, `accounting.py::marginal_decision_price` | `test_dpsi_dm_matches_central_difference` | E07, A09 | **verified against finite differences** |
| Prop. 2's inequality holds identically when `gamma > 1 − 1/sigma` | audit F1 | `marginal_below_price_condition` | `test_proposition2_holds_identically_at_paper_calibration`, `test_marginal_ratio_equals_closed_form` | E01 | **verified; the paper's claim was circular** |
| **Prop. 3** rate bounded in `[r_min, r_max]` | Eq. (12) | `model/rate.py::applied_rate` | `test_rate_is_bounded` | E08 | **verified** |
| **Prop. 3** monotone in each index, correct sign | Prop. 3 | `rate.py::rate_weights` | `test_rate_non_decreasing_in_positive_terms`, `..._non_increasing_...` (9 cases) | E08 | **verified** |
| Augmentation-only deployments sit at the floor | §IV design condition | `rate.py` | `test_augmentation_only_deployment_sits_at_the_floor` | A08 | **verified** |
| **Prop. 4** classifier error bound `eps(alpha+theta)` | Prop. 4 | `rate.py::classifier_error_bound`, `framework/classifier.py` | `test_classifier_error_bound_scales_linearly`, `test_proposition4_bound_holds_empirically` | E06 | **verified analytically and empirically** |
| **Prop. 5** waterfall feasibility `omega+kappa+sigma_T ≤ 1` | Prop. 5 | `model/waterfall.py::feasible` | `test_feasibility_boundary`, `test_infeasible_split_raises` | A03–A05 | **verified** |
| **Prop. 5** shield Laffer correction, Eq. (18) | Eq. (18) | `waterfall.py::shield_net_cost` | `test_shield_net_cost_below_mechanical_cost` | A04 | **verified** |
| **Prop. 6** fund converges iff `(1−rho)r_f < g` | Eq. (20) | `model/fund.py::stability` | `test_f2_condition_fails_at_realised_growth`, `test_convergent_path_flattens_to_the_closed_form` | E03 | **verified — and it FAILS at the testbed's `g`** |
| Table VI arithmetic (9 rows) and the 71-year half-life | Table VI | `fund.py::steady_state_ratio`, `half_life_years` | `test_table6_rows_reproduce`, `test_paper_half_life_is_about_71_years` | E03 | **verified — the arithmetic is correct; the assumed `g` is not** |
| **Prop. 7** payout paradox | Prop. 7 | `fund.py` | — | E09 | **experiment only** |
| **Prop. 8** nexus exhaustive, `sum_j SAC_ij = SAC_i` | Eq. (23) | `model/nexus.py::apportion` | `test_proposition8_apportionment_is_exhaustive`, `..._shares_sum_to_one` | E10 | **verified to 1e-12** |
| Nexus survives strategic shifting | §VI | `nexus.py::apply_shifting` | `test_shifting_preserves_exhaustiveness` | E10 | **verified** |
| Worked example: `r̃ = 0.1160` / `0.0095`, ratio 12.2× | Table VII | `rate.py` | `test_worked_example_substitution_case`, `..._augmentation_case`, `..._liability_ratio` | — | **reproduces exactly** |
| Worked-example allocation (0.631/0.394/0.237/0.316 MU) | §VIII | `waterfall.py::split` | `test_worked_example_allocation` | — | **reproduces exactly** |

## Empirical claims

| Claim | Where | Implementation | Test | Experiment | Status |
|---|---|---|---|---|---|
| B6c improves output vs B0 | Table VIII | `model/economy.py` | regression suite | **E01, E04** | **CONDITIONAL — holds only for `sigma ≲ 1.7` at `gamma = 0.85`; positive in 4 of 18 cells** |
| Budget closes in every arm | implicit | `accounting.py` | `test_every_arm_closes_its_books` (14 arms) | E02 | **now verified; it did not before** |
| Fund reaches ~17% of GDP as a steady state | §V | `fund.py` | `test_f2_condition_fails_at_realised_growth` | E03 | **REFUTED — that is a point on a divergent path** |
| Arms are "revenue-matched by construction" | §IX | `fiscal.spending_mode` | — | E04 | **was FALSE; now explicit and reported** |
| "Hours" rise under B6c | Table VIII | `economy.py` | `test_employment_metrics_separate_the_three_quantities` | E04 | **relabelled — that quantity is efficiency units** |
| 100% incidence of `dv({M})/dM < p_M` is evidence | §IV | `marginal_below_price_condition` | `test_proposition2_holds_identically...` | E01 | **REFUTED — tautological at this calibration** |
| Cross-border leakage | §VI | `nexus.py` | nexus tests | E10 | **now addressable; the old testbed had one jurisdiction** |
| Classifier confusion matrix at each error rate | §XII checklist | `classifier.py::confusion_matrix` | `test_confusion_matrix_shape_and_total` | E06 | **induced-error matrix only; no ground-truth matrix exists** |
| Calibration against robot stocks and national accounts | §XII | `configs/calibration.yaml` | — | E13 | **NOT DONE — sources licensed; results are synthetic** |
| Digital-twin optimal policy `Theta*` | Eq. (26) | `framework/twin.py` | twin tests | — | **BLOCKED — search space, normalisation, floors and weights are unspecified** |

## Research questions

| RQ | Question | Experiment | Status |
|---|---|---|---|
| RQ1 | Can factor-origin value be attributed exactly? | — | **Answered theoretically** (Shapley efficiency, tested); not empirically — coalition values are counterfactual |
| RQ2 | Does an adaptive rate outperform a fixed robot tax? | E04, A01 | **Answered conditionally** — depends on `sigma`; A01 isolates the adaptive rate's contribution |
| RQ3 | Does the instrument discourage automation? | E07, A09 | **Answered** — Prop. 2 says it *subsidises* at `phi = 1`; E01's B6 row is consistent |
| RQ4 | Is the fund a viable long-run dividend source? | E03, E09 | **Answered negatively at this calibration** — divergent for a substantial share of seeds |
| RQ5 | Is the rate robust to classification error? | E06 | **Answered** — Prop. 4 bound holds empirically |
| RQ6 | Does the nexus prevent leakage? | E10 | **Partially** — apportionment stays exhaustive; leakage magnitude measured, not eliminated |
| RQ7 | Does five-factor attribution differ from a composite? | E12 | **Measured** |
| RQ8 | Does the framework survive calibration? | E13 | **UNANSWERED — moved to future work.** No calibration has been run. |

---

## How to keep this matrix honest

`scripts/verify_generated.py` checks that the paper's tables still match their
results. It cannot check this matrix. When a claim is added to the manuscript,
add a row here and either point at the evidence or write **—** and say so. A
claim that appears in the paper and not here is a claim nobody has checked.
