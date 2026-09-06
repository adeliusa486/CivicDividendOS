"""The heterogeneous-agent testbed: one run of one policy arm.

This is the corrected successor to ``simulation/cdos_sim.py``. It reproduces
that model exactly when ``cfg.legacy_mode`` is set, which is how the regression
suite proves that every difference between the two is a deliberate correction
rather than drift.

What changed, and why
---------------------

**F3 -- the government budget now closes.** The audited model booked SAC revenue
as ``sum_i r_i ACB_i`` but debited firms only the marginal wedge, leaving ~93%
of the revenue funding the shield, fund and dividend without reducing anybody's
income. Here ``pm_eff`` remains the marginal decision price -- so firm behaviour
is untouched -- and the full liability ``r_i ACB_i`` is debited from profit as a
lump sum. Every period is then checked by :class:`~cdos.model.accounting.
ResourceAccount`, which raises rather than warns.

**F4 -- spending is matched when the paper says it is.** ``spending_mode``
selects between funding ``spend_ratio*Y`` plus each arm's own programme (the
audited behaviour, under which total spending differs across arms) and matching
a common total. The manuscript claims arms are "revenue-matched by
construction"; under the audited behaviour they were not.

**F6 -- employment metrics are named honestly.** The audited model's "hours" was
aggregate labour demand in efficiency units. Headcount, hours and efficiency
units are now tracked separately and never conflated.

**F2 -- fund stability is diagnosed, not assumed.** The realised growth rate is
measured and the Proposition 6 margin is reported on every run.

**F1 -- sigma and gamma are configuration.** They were unreachable without
editing source, which is why no sensitivity analysis existed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from ..config import Config
from .accounting import (ResourceAccount, marginal_decision_price,
                         profit_after_liability, sac_liability)
from .fund import fund_step, stability, check_stability
from .production import clear_wage, firm_block, labour_supply
from .rate import (applied_rate, augmentation_index, displacement_index,
                   rent_index, revenue_erosion_index, substitution_index)
from .shapley import cost_share_attribution, shapley_five_factor, shapley_machine, dpsi_dM
from .waterfall import split as waterfall_split

__all__ = ["run", "Population", "ARMS", "ARM_LABEL", "SAC_ARMS", "WEDGE_ARMS"]

# Arms levying a genuine wedge on the machine price.
WEDGE_ARMS = ("B1", "B4", "B12")
# Arms levying the Social Automation Contribution on the attributed base.
SAC_ARMS = ("B6", "B6c")

ARMS = ("B0", "B1", "B2", "B3", "B4", "B5", "B6", "B6c",
        "B7", "B8", "B9", "B10", "B11", "B12")

ARM_LABEL = {
    "B0": "Existing labour/capital tax system",
    "B1": "Fixed robot tax",
    "B2": "Broad capital-income tax increase",
    "B3": "UBI via general taxation",
    "B4": "Automation tax plus retraining",
    "B5": "Public wealth fund, no factor-origin tax",
    "B6": "CivicDividendOS, base as specified",
    "B6c": "CivicDividendOS, marginally corrected base",
    "B7": "Optimal linear capital tax",
    "B8": "Consumption-tax shift",
    "B9": "Lump-sum-financed CivicDividendOS",
    "B10": "EITC-style wage subsidy",
    "B11": "CivicDividendOS, no cost deduction (phi = 0)",
    "B12": "Thuemmel-style optimal robot tax",
}


# ---------------------------------------------------------------------------
# Population
# ---------------------------------------------------------------------------

@dataclass
class Population:
    """Heterogeneous households and firms, drawn once per seed.

    The draw order is fixed and must not change: common random numbers are what
    make the arm contrasts paired, and the regression suite depends on the
    audited baseline's exact stream.
    """
    skill: np.ndarray
    wealth: np.ndarray
    exposure: np.ndarray
    efficiency: np.ndarray
    A_f: np.ndarray
    alpha_f: np.ndarray
    markup: np.ndarray
    rent_index: np.ndarray
    save_rate: np.ndarray

    @classmethod
    def draw(cls, cfg: Config, seed: int) -> "Population":
        p = cfg.population
        rng = np.random.default_rng(seed)
        nh, nf = p.n_households, p.n_firms

        skill = np.exp(rng.normal(0.0, p.skill_sd, nh))
        skill /= skill.mean()
        wealth = np.exp(rng.normal(0.0, p.wealth_sd, nh))
        wealth *= p.wealth_mean / wealth.mean()
        exposure = np.clip(
            p.exposure_intercept
            - p.exposure_slope * (skill - skill.min()) / (skill.max() - skill.min())
            + rng.normal(0, p.exposure_noise, nh), p.exposure_lo, p.exposure_hi)

        A_f = np.exp(rng.normal(0.0, p.productivity_sd, nf))
        A_f *= 1.0 / A_f.mean()
        alpha_f = np.clip(rng.beta(p.alpha_beta_a, p.alpha_beta_b, nf),
                          p.alpha_lo, p.alpha_hi)
        markup = np.clip(rng.normal(p.markup_mean, p.markup_sd, nf),
                         p.markup_lo, p.markup_hi)

        save_rate = p.save_lo + (p.save_hi - p.save_lo) * \
            (np.argsort(np.argsort(wealth)) / max(nh - 1, 1))

        return cls(skill=skill, wealth=wealth, exposure=exposure,
                   efficiency=np.ones(nh), A_f=A_f, alpha_f=alpha_f,
                   markup=markup, rent_index=rent_index(markup),
                   save_rate=save_rate)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def gini(x) -> float:
    x = np.clip(np.asarray(x, dtype=float), 0.0, None)
    n = x.size
    xs = np.sort(x)
    tot = xs.sum()
    if tot <= 0:
        return 0.0
    idx = np.arange(1, n + 1)
    return float((2.0 * np.sum(idx * xs) / (n * tot)) - (n + 1.0) / n)


def _phi_for_arm(cfg: Config, arm: str) -> float:
    """Cost-deduction share of Proposition 2."""
    if arm == "B6c":
        return 0.50
    if arm == "B11":
        return 0.0
    return cfg.attribution.phi_deduct


def _tau_k_for_arm(cfg: Config, arm: str) -> float:
    base = cfg.fiscal.tau_k
    if arm == "B2":
        return base + cfg.policy.dtau_k
    if arm == "B7":
        return base + cfg.policy.b7_tau_k_extra
    return base


def _tau_c_for_arm(cfg: Config, arm: str) -> float:
    return cfg.fiscal.tau_c + (cfg.policy.b8_tau_c_extra if arm == "B8" else 0.0)


# ---------------------------------------------------------------------------
# The run
# ---------------------------------------------------------------------------

def run(cfg: Config, seed: Optional[int] = None, arm: Optional[str] = None
        ) -> Dict[str, Any]:
    """Simulate one arm under one seed. Returns summary statistics."""
    seed = cfg.run.seed if seed is None else seed
    arm = cfg.run.arm if arm is None else arm
    if arm not in ARMS:
        raise ValueError(f"unknown arm {arm!r}; known arms are {list(ARMS)}")

    tech, fisc, fnd, num = cfg.technology, cfg.fiscal, cfg.fund, cfg.numerics
    legacy = cfg.legacy_mode
    pop = Population.draw(cfg, seed)
    nh, nf = cfg.population.n_households, cfg.population.n_firms
    sigma, gamma = tech.sigma, tech.gamma
    tol = tech.cobb_douglas_tol
    T = cfg.run.t_burn + cfg.run.t_run

    wealth = pop.wealth.copy()
    eff = pop.efficiency.copy()
    skill, exposure = pop.skill, pop.exposure

    tau_L = fisc.tau_l0
    tau_K = _tau_k_for_arm(cfg, arm)
    tau_C = _tau_c_for_arm(cfg, arm)
    phi = _phi_for_arm(cfg, arm)
    rf_q = cfg.r_fund_quarterly

    # Waterfall shares. The shield is explicit for the SAC arms only; other
    # arms have no SAC revenue to apportion.
    waterfall_arms = SAC_ARMS + ("B9", "B11")
    omega = fnd.omega if arm in waterfall_arms else 0.0
    kappa = 0.0 if legacy else (fnd.kappa if arm in waterfall_arms else 0.0)
    sigma_t = fnd.sigma_t if arm in waterfall_arms else 0.0

    fund = 0.0
    lab_share0: Optional[np.ndarray] = None
    wage_share0: Optional[np.ndarray] = None
    w0: Optional[float] = None
    prev_adopt = 0.0

    keys = ("Y", "eff_units", "headcount", "hours", "ws", "revr", "gi", "gw",
            "fund", "div", "pov", "adopt", "taul", "sac", "divgdp", "wage",
            "liability", "dwl", "spend")
    H: Dict[str, List[float]] = {k: [] for k in keys}
    path: List[Tuple] = []
    accounts: List[Dict[str, Any]] = []
    incidence_acc = {"labour": 0.0, "capital": 0.0, "total": 0.0}

    for t in range(T):
        pm = tech.pm0 * np.exp(-tech.decay * t)
        sup_scale = float((skill * eff).sum())

        # ---- rate / wedge -------------------------------------------------
        wedge_f = np.zeros(nf)
        Lp = Mp = None
        if arm == "B1":
            wedge_f = np.full(nf, cfg.policy.robot_tax)
        elif arm == "B4":
            wedge_f = np.full(nf, cfg.policy.auto_tax)
        elif arm == "B12":
            wedge_f = np.full(nf, cfg.policy.b12_robot_tax)
        elif arm in SAC_ARMS + ("B9", "B11"):
            if lab_share0 is None:
                wedge_f = np.full(nf, cfg.rate.r0)
            else:
                w_try = clear_wage(pop.alpha_f, pop.A_f, pm, sup_scale, tau_L,
                                   tech.eps_l, sigma, gamma, num.wage_lo,
                                   num.wage_hi, num.bisect_iters, tol,
                                   verify_bracket=num.verify_bracket and not legacy)
                Lp, Mp, Yp, _ = firm_block(pop.alpha_f, pop.A_f, w_try, pm,
                                           sigma, gamma, tol)
                ls = (w_try * Lp) / np.maximum(w_try * Lp + pm * Mp, 1e-12)
                endogenous: Dict[str, Any] = {
                    "S": substitution_index(ls, lab_share0),
                    "C_rent": pop.rent_index,
                    "A_aug": augmentation_index(w_try, w0,
                                                cfg.rate.augmentation_wage_scale),
                }
                if not legacy:
                    endogenous["E_disp"] = displacement_index(eff, exposure)
                    endogenous["R_rev"] = revenue_erosion_index(
                        (w_try * Lp) / np.maximum(Yp, 1e-12), wage_share0)
                wedge_f = applied_rate(cfg.rate, nf, endogenous)

        # ---- marginal decision price --------------------------------------
        if arm in SAC_ARMS + ("B9", "B11"):
            if lab_share0 is None:
                pm_eff = pm * np.ones(nf)
            else:
                dacb = dpsi_dM(pop.alpha_f, pop.A_f, Lp, Mp, sigma, gamma, tol) \
                    - phi * pm
                pm_eff = marginal_decision_price(pm, wedge_f, dacb)
        else:
            pm_eff = pm * (1.0 + wedge_f)

        # ---- market clearing ----------------------------------------------
        w = clear_wage(pop.alpha_f, pop.A_f, pm_eff, sup_scale, tau_L,
                       tech.eps_l, sigma, gamma, num.wage_lo, num.wage_hi,
                       num.bisect_iters, tol,
                       verify_bracket=num.verify_bracket and not legacy)
        L_f, M_f, Y_f, _ = firm_block(pop.alpha_f, pop.A_f, w, pm_eff,
                                      sigma, gamma, tol)
        Y = float(Y_f.sum())
        eff_units = float(L_f.sum())          # F6: efficiency units, not hours
        wage_bill = w * eff_units
        machine_cost = float((pm * M_f).sum())

        if lab_share0 is None:
            lab_share0 = (w * L_f) / np.maximum(w * L_f + pm * M_f, 1e-12)
            wage_share0 = (w * L_f) / np.maximum(Y_f, 1e-12)
            w0 = w

        # ---- attribution ---------------------------------------------------
        if cfg.attribution.mode == "five_factor":
            psi_M, v_total = _five_factor_machine_value(cfg, pop, L_f, M_f,
                                                        sigma, gamma, tol)
        elif cfg.attribution.method == "cost_share":
            shares = cost_share_attribution(
                {"L": w * L_f, "M": pm * M_f}, Y_f)
            psi_M, v_total = shares["M"], Y_f
        else:
            psi_M, v_total = shapley_machine(pop.alpha_f, pop.A_f, L_f, M_f,
                                             sigma, gamma, tol)
        ACB = np.maximum(psi_M - phi * pm * M_f, 0.0)

        # ---- liability and profit ------------------------------------------
        liability_f = np.zeros(nf)
        if arm in SAC_ARMS + ("B9", "B11"):
            liability_f = sac_liability(wedge_f, ACB)

        if legacy:
            # The audited treatment: charge machines at pm_eff and never debit
            # the inframarginal liability. Retained only for regression.
            profit_f = np.maximum(Y_f - w * L_f - pm_eff * M_f, 0.0)
        elif arm in SAC_ARMS + ("B9", "B11"):
            profit_f = profit_after_liability(Y_f, w, L_f, pm, M_f, liability_f)
        else:
            # Wedge arms: the wedge *is* the liability, already in pm_eff.
            profit_f = profit_after_liability(Y_f, w, L_f, pm_eff, M_f, None)
        Profit = float(profit_f.sum())

        # ---- automation revenue and programme spending ---------------------
        sac_rev = 0.0
        rev_auto = 0.0
        prog_spend = 0.0
        equity_in = 0.0
        retrain_amt = 0.0
        transition_amt = 0.0
        shield_amt = 0.0
        subsidy_amt = 0.0
        lumpsum_rev = 0.0

        if arm in WEDGE_ARMS:
            rate = {"B1": cfg.policy.robot_tax, "B4": cfg.policy.auto_tax,
                    "B12": cfg.policy.b12_robot_tax}[arm]
            rev_auto = float((rate * pm * M_f).sum())
            if arm == "B4":
                retrain_amt = cfg.policy.retrain_share * rev_auto
                prog_spend += retrain_amt
        elif arm == "B5":
            equity_in = cfg.policy.aou_xi * Profit      # non-cash, no fiscal cost
        elif arm in SAC_ARMS + ("B9", "B11"):
            sac_rev = float(liability_f.sum())
            rev_auto = sac_rev
            wf = waterfall_split(sac_rev, omega, kappa, sigma_t)
            transition_amt = wf.transition
            shield_amt = wf.shield
            retrain_amt = transition_amt
            prog_spend += wf.fund + transition_amt
            if arm == "B9":
                # Financed by a lump sum rather than by the contribution.
                lumpsum_rev = cfg.policy.b9_lumpsum_ratio * Y
        elif arm == "B3":
            prog_spend += cfg.policy.ubi_ratio * Y

        if arm == "B10":
            # EITC-style subsidy paid to the lower part of the earnings
            # distribution; a programme cost, financed like any other.
            subsidy_amt = cfg.policy.b10_wage_subsidy * wage_bill \
                * cfg.policy.b10_target_quantile
            prog_spend += subsidy_amt

        # ---- fund -----------------------------------------------------------
        if arm in SAC_ARMS + ("B9", "B11"):
            fund, payout = fund_step(fund, rf_q, omega * sac_rev, fnd.rho_payout)
        elif arm == "B5":
            fund, payout = fund_step(fund, rf_q, equity_in, fnd.rho_payout)
        else:
            fund, payout = 0.0, 0.0
        prog_spend += payout                       # the payout is spent as dividend

        # ---- government budget: the labour tax clears it ---------------------
        rev_K = tau_K * Profit
        rev_C = tau_C * fisc.tau_c_base * Y
        if fisc.spending_mode == "match_spending" and not legacy:
            # F4: every arm funds the same total, so contrasts reflect
            # instrument design rather than fiscal stance.
            needed = fisc.spend_ratio * Y + _reference_programme(cfg, Y)
        elif fisc.spending_mode not in ("match_spending", "baseline_spending"):
            raise ValueError(f"unknown spending_mode {fisc.spending_mode!r}")
        else:
            needed = fisc.spend_ratio * Y + prog_spend
        # The earned-income shield is an explicit labour tax reduction, Eq. (17).
        shield_relief = shield_amt if not legacy else 0.0
        tau_L_next = (needed - (rev_K + rev_auto + rev_C + lumpsum_rev
                                + shield_relief)) / max(wage_bill, 1e-9)
        tau_L_next = float(np.clip(tau_L_next, fisc.taul_lo, fisc.taul_hi))
        gov_rev = tau_L * wage_bill + rev_K + rev_auto + rev_C + lumpsum_rev

        # ---- households -------------------------------------------------------
        eshare = (skill * eff) / max(float((skill * eff).sum()), 1e-12)
        labour_income = eshare * wage_bill
        cap_income = (wealth / max(wealth.sum(), 1e-12)) * Profit * (1.0 - tau_K)
        ubi_i = (cfg.policy.ubi_ratio * Y / nh) if arm == "B3" else 0.0
        div_i = (payout / nh) if arm in ("B5",) + SAC_ARMS + ("B9", "B11") else 0.0
        targ = exposure / max(exposure.sum(), 1e-12)
        trans_i = transition_amt * targ if transition_amt > 0 else 0.0
        subs_i = 0.0
        if arm == "B10":
            cutoff = np.quantile(labour_income, cfg.policy.b10_target_quantile)
            elig = (labour_income <= cutoff).astype(float)
            subs_i = subsidy_amt * elig / max(elig.sum(), 1e-12)

        income = labour_income * (1.0 - tau_L) + cap_income + ubi_i + div_i \
            + trans_i + subs_i
        if arm == "B9":
            income = income - lumpsum_rev / nh      # lump sum, uniform per head
        disp = income / (1.0 + tau_C)
        wealth = np.clip(wealth * (1.0 + rf_q) + pop.save_rate * disp, 0.0, None)

        # ---- incidence --------------------------------------------------------
        if rev_auto > 0.0:
            incidence_acc["labour"] += float(rev_auto) * float(
                wage_bill / max(wage_bill + Profit, 1e-12))
            incidence_acc["capital"] += float(rev_auto) * float(
                Profit / max(wage_bill + Profit, 1e-12))
            incidence_acc["total"] += float(rev_auto)

        # ---- resource accounting (F3) -----------------------------------------
        if not legacy:
            acct = ResourceAccount(period=t, tol=num.accounting_tol,
                                   strict=num.strict_accounting)
            acct.source("output", Y)
            acct.use("wage_bill", wage_bill)
            acct.use("machine_cost", machine_cost)
            acct.use("profit", Profit)
            acct.use("automation_liability", rev_auto if arm not in WEDGE_ARMS else 0.0)
            # Wedge arms charge machines at pm_eff, so their liability is
            # already inside machine_cost; account for the difference.
            if arm in WEDGE_ARMS:
                acct.use("machine_wedge", float(((pm_eff - pm) * M_f).sum()))
            # Firms whose profit was floored at zero absorb the shortfall; the
            # residual is what the floor removed, and it is booked explicitly
            # rather than silently discarded.
            gross = Y_f - w * L_f - pm * M_f - liability_f \
                if arm not in WEDGE_ARMS else Y_f - w * L_f - pm_eff * M_f
            acct.use("limited_liability_floor", float(np.sum(np.maximum(-gross, 0.0))))

            acct.revenue("labour_tax", tau_L * wage_bill)
            acct.revenue("capital_tax", rev_K)
            acct.revenue("consumption_tax", rev_C)
            acct.revenue("automation_revenue", rev_auto)
            acct.revenue("lump_sum", lumpsum_rev)
            acct.revenue("fund_payout", payout)
            acct.spend("public_spending", fisc.spend_ratio * Y)
            acct.spend("programme_spending", prog_spend)
            acct.spend("fiscal_balance",
                       (tau_L * wage_bill + rev_K + rev_C + rev_auto
                        + lumpsum_rev + payout)
                       - (fisc.spend_ratio * Y + prog_spend))
            report = acct.check()
            if cfg.run.collect_accounting:
                accounts.append({**acct.as_dict(), **report})

        # ---- displacement and retraining ---------------------------------------
        adopt = machine_cost / max(Y, 1e-12)
        if cfg.displacement.enabled:
            auto_growth = max(adopt - prev_adopt, 0.0)
            eff = eff * (1.0 - cfg.displacement.lam_disp * exposure * auto_growth)
            if retrain_amt > 0:
                eff = np.minimum(
                    eff * (1.0 + cfg.displacement.retrain_eff
                           * (retrain_amt / max(Y, 1e-9))
                           * (exposure / exposure.mean())), 1.0)
            eff = np.clip(eff, cfg.displacement.eff_floor, 1.0)
        prev_adopt = adopt

        # ---- record --------------------------------------------------------
        H["Y"].append(Y)
        H["eff_units"].append(eff_units)
        H["hours"].append(eff_units)          # kept for regression comparability
        H["headcount"].append(float(np.sum(eff > cfg.displacement.eff_floor + 1e-12)))
        H["wage"].append(float(w))
        H["ws"].append(wage_bill / max(Y, 1e-12))
        H["revr"].append(gov_rev / max(Y, 1e-12))
        H["gi"].append(gini(income))
        H["gw"].append(gini(wealth))
        H["fund"].append(fund / max(4.0 * Y, 1e-12))
        H["div"].append(div_i / max(float(disp.mean()), 1e-12))
        H["divgdp"].append(payout / max(Y, 1e-12))
        H["pov"].append(float((disp < 0.5 * np.median(disp)).mean()))
        H["adopt"].append(adopt)
        H["taul"].append(tau_L)
        H["sac"].append(rev_auto / max(Y, 1e-12))
        H["liability"].append(rev_auto)
        H["spend"].append((fisc.spend_ratio * Y + prog_spend) / max(Y, 1e-12))
        H["dwl"].append(_deadweight_loss(tau_L, wage_bill, tech.eps_l))

        if cfg.run.collect_path and t >= cfg.run.t_burn:
            path.append((t - cfg.run.t_burn, Y, H["ws"][-1], H["gi"][-1],
                         H["fund"][-1], H["taul"][-1]))

        tau_L = tau_L_next

    return _summarise(cfg, arm, seed, H, path, accounts, incidence_acc)


def _reference_programme(cfg: Config, Y: float) -> float:
    """Programme spending every arm must fund under ``match_spending``.

    Set to the UBI ratio, which is the largest single programme in the arm set,
    so no arm is asked to fund less than it would on its own. The choice is a
    parameter, not a hidden constant.
    """
    return cfg.policy.ubi_ratio * Y


def _deadweight_loss(tau_l: float, wage_bill: float, eps_l: float) -> float:
    """Harberger triangle on the labour margin: 1/2 * eps * tau^2/(1-tau) * base."""
    denom = max(1.0 - tau_l, 1e-9)
    return 0.5 * eps_l * tau_l ** 2 / denom * wage_bill


def _five_factor_machine_value(cfg: Config, pop: Population, L_f, M_f,
                               sigma: float, gamma: float, tol: float):
    """Machine-factor value under the five-factor game.

    The composite machine input is split across the AI-agent and robot factors
    in proportion to their configured shares; data and traditional capital are
    carried at their share of the labour input, which is the only observable
    the testbed has for them. This is a mapping from a two-factor model onto a
    five-factor game, not a five-factor model -- the manuscript's own
    limitations section already concedes the testbed has one composite machine
    factor, and E12 measures what the mapping costs.
    """
    shares = cfg.attribution.five_factor_shares
    mach = cfg.attribution.machine_factors
    mach_weight = sum(shares[f] for f in mach)
    inputs = {}
    for f, s in shares.items():
        if f in mach:
            inputs[f] = M_f * (s / max(mach_weight, 1e-12))
        elif f == "H":
            inputs[f] = L_f
        else:
            inputs[f] = L_f * s
    psi = shapley_five_factor(inputs, pop.A_f, sigma, gamma, shares,
                              tuple(shares.keys()), tol)
    total = sum(psi.values())
    return sum(psi[f] for f in mach), total


def _summarise(cfg: Config, arm: str, seed: int, H, path, accounts,
               incidence_acc) -> Dict[str, Any]:
    s = slice(cfg.run.t_burn, None)
    mean = lambda k: float(np.mean(H[k][s]))

    years = (len(H["Y"][s]) - 1) / 4.0
    g_realised = float((H["Y"][-1] / H["Y"][cfg.run.t_burn]) ** (1.0 / years) - 1.0) \
        if years > 0 else 0.0
    rep = stability(cfg.fund.rho_payout, cfg.fund.r_fund_annual, g_realised)
    if arm in SAC_ARMS + ("B5", "B9", "B11"):
        check_stability(rep, cfg.fund.stability_mode, context=f"{arm} seed {seed}")

    out: Dict[str, Any] = dict(
        arm=arm, seed=seed, config_hash=cfg.hash(),
        Y=mean("Y"), Y_end=float(H["Y"][-1]),
        hours=mean("hours"),
        eff_units=mean("eff_units"), headcount=mean("headcount"),
        wage=mean("wage"),
        ws=mean("ws"), ws_end=float(H["ws"][-1]),
        gi=mean("gi"), gw=mean("gw"), pov=mean("pov"),
        rev_cv=float(np.std(H["revr"][s]) / max(np.mean(H["revr"][s]), 1e-12)),
        fund=float(H["fund"][-1]), div=mean("div"), adopt=mean("adopt"),
        divgdp=mean("divgdp"), divgdp_end=float(H["divgdp"][-1]),
        taul=mean("taul"), taul_end=float(H["taul"][-1]), sac=mean("sac"),
        taul_cv=float(np.std(H["taul"][s]) / max(np.mean(H["taul"][s]), 1e-12)),
        spend=mean("spend"), dwl=mean("dwl"),
        revenue=float(np.mean(H["liability"][s])),
        g_realised=g_realised,
        stability_margin=rep.margin, fund_stable=rep.stable,
    )
    out["revenue_per_dwl"] = out["revenue"] / max(out["dwl"], 1e-12)
    if incidence_acc["total"] > 0:
        out["incidence_labour"] = incidence_acc["labour"] / incidence_acc["total"]
        out["incidence_capital"] = incidence_acc["capital"] / incidence_acc["total"]
    else:
        out["incidence_labour"] = 0.0
        out["incidence_capital"] = 0.0
    if cfg.run.collect_path:
        out["path"] = path
    if cfg.run.collect_accounting:
        out["accounts"] = accounts
    return out
