"""
CivicDividendOS evaluation testbed.

Stylized heterogeneous-agent model of an economy in which firms substitute
machine services (AI agents + robots) for labour as the machine price falls.
Seven policy arms are compared under common random numbers.

Two design points matter for interpretation:

1. The model implements the paper's own attribution mechanism. The automation
   contribution base is the Shapley value of the machine factor in the firm's
   two-factor production game, not a cost share and not an asset count.

2. All arms finance an identical path of baseline public spending
   (SPEND_RATIO of output) plus their own programme spending. The labour tax
   rate therefore clears the government budget and is an OUTCOME, not a
   parameter. The Human Earned-Income Shield is exactly this: arms that raise
   automation revenue need a lower labour tax to fund the same public services.

Outputs are outputs of this model. They are not empirical estimates.
"""

import json
import numpy as np

# ----------------------------------------------------------------------------
# Parameters
# ----------------------------------------------------------------------------

P = dict(
    N_H=10000,            # households
    N_F=500,              # firms
    T_BURN=40,            # burn-in quarters
    T_RUN=200,            # reported quarters
    SIGMA=1.5,            # elasticity of substitution, labour vs machines
    GAMMA=0.85,           # span of control (decreasing returns)
    PM0=1.00,             # initial machine price
    DECAY=0.0060,         # quarterly decline in machine price
    EPS_L=0.30,           # labour supply elasticity wrt net-of-tax wage
    SPEND_RATIO=0.35,     # baseline public spending as a share of output
    TAU_L0=0.30,          # initial labour tax (endogenous thereafter)
    TAU_K=0.25,           # capital/profit tax
    TAU_C=0.18,           # consumption tax
    TAUL_LO=0.05, TAUL_HI=0.60,
    R_FUND=0.05 / 4.0,    # quarterly real fund return
    RHO_PAYOUT=0.60,      # fund payout ratio
    OMEGA=0.40,           # SAC share to fund
    SIGMA_T=0.15,         # SAC share to immediate transition support
    R0=0.08, RMIN=0.0, RMAX=0.25,
    W_ALPHA=0.10, W_BETA=0.06, W_ETA=0.05,      # rate: +S, +rent, +base erosion
    W_THETA=0.09, W_LAMBDA=0.07, W_NU=0.06,     # rate: -aug, -training, -newtask
    ROBOT_TAX=0.080,      # B1 fixed wedge on machine price
    AUTO_TAX=0.060,       # B4 wedge
    DTAU_K=0.10,          # B2 capital tax increase
    UBI_RATIO=0.020,      # B3 UBI as share of output
    AOU_XI=0.010,         # B5 equity contribution rate on profit
    LAM_DISP=0.35,        # efficiency loss per unit exposure x automation growth
    RETRAIN_EFF=0.50,     # efficiency recovery per unit retraining spend
    SAVE_LO=0.02, SAVE_HI=0.35,
    BISECT=28,
    PHI_DEDUCT=1.00,     # share of machine cost deductible (B6c uses 0.5)
)

ARMS = ["B0", "B1", "B2", "B3", "B4", "B5", "B6", "B6c"]
ARM_LABEL = {
    "B0": "Existing labour/capital tax system",
    "B1": "Fixed robot tax",
    "B2": "Broad capital-income tax increase",
    "B3": "UBI via general taxation",
    "B4": "Automation tax plus retraining",
    "B5": "Public wealth fund, no factor-origin tax",
    "B6": "CivicDividendOS, base as specified",
    "B6c": "CivicDividendOS, marginally corrected base",
}


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------

def gini(x):
    x = np.clip(np.asarray(x, dtype=float), 0.0, None)
    n = x.size
    xs = np.sort(x)
    tot = xs.sum()
    if tot <= 0:
        return 0.0
    idx = np.arange(1, n + 1)
    return float((2.0 * np.sum(idx * xs) / (n * tot)) - (n + 1.0) / n)


def ces_unit_cost(alpha, w, pm, sigma):
    return (alpha ** sigma * w ** (1.0 - sigma)
            + (1.0 - alpha) ** sigma * pm ** (1.0 - sigma)) ** (1.0 / (1.0 - sigma))


def firm_block(alpha, A, w, pm, sigma, gamma):
    c = ces_unit_cost(alpha, w, pm, sigma)
    X = (gamma * A / c) ** (1.0 / (1.0 - gamma))
    L = alpha ** sigma * (w / c) ** (-sigma) * X
    M = (1.0 - alpha) ** sigma * (pm / c) ** (-sigma) * X
    Y = A * X ** gamma
    return L, M, Y, c


def shapley_machine(alpha, A, L, M, sigma, gamma):
    """Shapley value of the machine factor; psi_L + psi_M = Y exactly."""
    rho = 1.0 - 1.0 / sigma
    Ls, Ms = np.maximum(L, 1e-12), np.maximum(M, 1e-12)
    vL = A * (alpha * Ls ** rho) ** (gamma / rho)
    vM = A * ((1.0 - alpha) * Ms ** rho) ** (gamma / rho)
    vLM = A * (alpha * Ls ** rho + (1.0 - alpha) * Ms ** rho) ** (gamma / rho)
    psi_M = 0.5 * vM + 0.5 * (vLM - vL)
    return np.clip(psi_M, 0.0, vLM), vLM


def dpsi_dM(alpha, A, L, M, sigma, gamma):
    """d(psi_M)/dM in closed form; verified against central differences."""
    rho = 1.0 - 1.0 / sigma
    Ls, Ms = np.maximum(L, 1e-12), np.maximum(M, 1e-12)
    S = alpha * Ls ** rho + (1.0 - alpha) * Ms ** rho
    dvM = A * (1.0 - alpha) ** (gamma / rho) * gamma * Ms ** (gamma - 1.0)
    dvLM = A * gamma * S ** (gamma / rho - 1.0) * (1.0 - alpha) * Ms ** (rho - 1.0)
    return 0.5 * dvM + 0.5 * dvLM


def clear_wage(alpha, A, pm, sup_scale, tau_l, eps_l, sigma, gamma,
               lo=1e-3, hi=1e3, iters=28):
    """Bisection on the wage so aggregate labour demand equals supply."""
    for _ in range(iters):
        w = np.sqrt(lo * hi)
        L, _, _, _ = firm_block(alpha, A, w, pm, sigma, gamma)
        sup = sup_scale * max(w * (1.0 - tau_l), 1e-9) ** eps_l
        if L.sum() - sup > 0:
            lo = w
        else:
            hi = w
    return np.sqrt(lo * hi)


# ----------------------------------------------------------------------------
# Single run
# ----------------------------------------------------------------------------

def run(seed, arm, p=P, collect_path=False):
    rng = np.random.default_rng(seed)
    NH, NF = p["N_H"], p["N_F"]
    sigma, gamma = p["SIGMA"], p["GAMMA"]
    T = p["T_BURN"] + p["T_RUN"]

    # heterogeneous agents (common random numbers across arms via seed)
    skill = np.exp(rng.normal(0.0, 0.60, NH)); skill /= skill.mean()
    wealth = np.exp(rng.normal(0.0, 1.30, NH)); wealth *= 4.0 / wealth.mean()
    expo = np.clip(0.85 - 0.45 * (skill - skill.min()) / (skill.max() - skill.min())
                   + rng.normal(0, 0.10, NH), 0.02, 0.98)
    eff = np.ones(NH)

    A_f = np.exp(rng.normal(0.0, 0.35, NF)); A_f *= 1.0 / A_f.mean()
    alpha_f = np.clip(rng.beta(6.0, 4.0, NF), 0.25, 0.90)
    markup = np.clip(rng.normal(0.22, 0.08, NF), 0.02, 0.60)
    C_rent = (markup - markup.min()) / max(markup.max() - markup.min(), 1e-9)

    srate = p["SAVE_LO"] + (p["SAVE_HI"] - p["SAVE_LO"]) * \
        (np.argsort(np.argsort(wealth)) / max(NH - 1, 1))

    tau_L = p["TAU_L0"]          # endogenous from period 1 onward
    tau_K = p["TAU_K"] + (p["DTAU_K"] if arm == "B2" else 0.0)
    phi = 0.50 if arm == "B6c" else p["PHI_DEDUCT"]
    fund = 0.0
    lab_share0 = None
    L_f0 = None
    w0 = None
    prev_adopt = 0.0

    H = {k: [] for k in ("Y", "hours", "ws", "revr", "gi", "gw", "fund",
                         "div", "pov", "adopt", "taul", "sac", "divgdp")}
    path = []

    for t in range(T):
        pm = p["PM0"] * np.exp(-p["DECAY"] * t)
        sup_scale = float((skill * eff).sum())

        # ---- machine price wedge -------------------------------------------
        if arm == "B1":
            wedge_f = np.full(NF, p["ROBOT_TAX"])
        elif arm == "B4":
            wedge_f = np.full(NF, p["AUTO_TAX"])
        elif arm in ("B6", "B6c"):
            if lab_share0 is None:
                wedge_f = np.full(NF, p["R0"])
            else:
                w_try = clear_wage(alpha_f, A_f, pm, sup_scale, tau_L,
                                   p["EPS_L"], sigma, gamma, iters=p["BISECT"])
                Lp, Mp, _, _ = firm_block(alpha_f, A_f, w_try, pm, sigma, gamma)
                ls = (w_try * Lp) / np.maximum(w_try * Lp + pm * Mp, 1e-12)
                S_i = np.clip((lab_share0 - ls) / np.maximum(lab_share0, 1e-9), 0, 1)
                # Augmentation is credited only where labour is actually better
                # off: real wage growth relative to the pre-diffusion wage.
                # Employment retention alone is not evidence of augmentation,
                # since wages clear the market in this model.
                A_aug = np.full(NF, float(np.clip((w_try / w0 - 1.0) / 0.50, 0.0, 1.0)))
                wedge_f = np.clip(
                    p["R0"] + p["W_ALPHA"] * S_i + p["W_BETA"] * C_rent
                    + p["W_ETA"] * S_i - p["W_THETA"] * A_aug
                    - p["W_LAMBDA"] * 0.55 - p["W_NU"] * 0.30,
                    p["RMIN"], p["RMAX"])
        else:
            wedge_f = np.zeros(NF)

        if arm in ("B6", "B6c"):
            # SAC is levied on ACB = psi_M - pm*M, a rent-like base. Its marginal
            # effect on the machine decision is r*d(ACB)/dM, not a price wedge.
            if lab_share0 is None:
                pm_eff = pm * np.ones(NF)
            else:
                dps = dpsi_dM(alpha_f, A_f, Lp, Mp, sigma, gamma)
                pm_eff = np.maximum(pm + wedge_f * (dps - phi * pm), 0.25 * pm)
        else:
            pm_eff = pm * (1.0 + wedge_f)

        # ---- market clearing -------------------------------------------------
        w = clear_wage(alpha_f, A_f, pm_eff, sup_scale, tau_L, p["EPS_L"],
                       sigma, gamma, iters=p["BISECT"])
        L_f, M_f, Y_f, _ = firm_block(alpha_f, A_f, w, pm_eff, sigma, gamma)
        Y = float(Y_f.sum())
        hours = float(L_f.sum())
        wage_bill = w * hours
        profit_f = np.maximum(Y_f - w * L_f - pm_eff * M_f, 0.0)
        Profit = float(profit_f.sum())

        if lab_share0 is None:
            lab_share0 = (w * L_f) / np.maximum(w * L_f + pm * M_f, 1e-12)
            L_f0 = L_f.copy()
            w0 = w

        # ---- factor-origin attribution (Shapley) -----------------------------
        psi_M, _ = shapley_machine(alpha_f, A_f, L_f, M_f, sigma, gamma)
        ACB = np.maximum(psi_M - phi * pm * M_f, 0.0)

        # ---- automation revenue and programme spending ----------------------
        sac_rev = 0.0
        rev_auto = 0.0
        prog_spend = 0.0
        equity_in = 0.0
        retrain_amt = 0.0
        transition_amt = 0.0

        if arm == "B1":
            rev_auto = float((p["ROBOT_TAX"] * pm * M_f).sum())
        elif arm == "B4":
            rev_auto = float((p["AUTO_TAX"] * pm * M_f).sum())
            retrain_amt = 0.60 * rev_auto
            prog_spend += retrain_amt
        elif arm == "B5":
            equity_in = p["AOU_XI"] * Profit          # non-cash, no fiscal cost
        elif arm in ("B6", "B6c"):
            sac_rev = float((wedge_f * ACB).sum())
            rev_auto = sac_rev
            transition_amt = p["SIGMA_T"] * sac_rev
            retrain_amt = transition_amt
            prog_spend += p["OMEGA"] * sac_rev + transition_amt
        elif arm == "B3":
            prog_spend += p["UBI_RATIO"] * Y

        # ---- fund ------------------------------------------------------------
        payout = p["RHO_PAYOUT"] * p["R_FUND"] * fund
        if arm in ("B6", "B6c"):
            fund = fund * (1.0 + p["R_FUND"]) + p["OMEGA"] * sac_rev - payout
        elif arm == "B5":
            fund = fund * (1.0 + p["R_FUND"]) + equity_in - payout
        else:
            fund, payout = 0.0, 0.0
        prog_spend += payout                       # payout is spent as dividend

        # ---- government budget: labour tax clears it -------------------------
        rev_K = tau_K * Profit
        rev_C = p["TAU_C"] * 0.60 * Y
        needed = p["SPEND_RATIO"] * Y + prog_spend
        tau_L_next = (needed - (rev_K + rev_auto + rev_C)) / max(wage_bill, 1e-9)
        tau_L_next = float(np.clip(tau_L_next, p["TAUL_LO"], p["TAUL_HI"]))
        gov_rev = tau_L * wage_bill + rev_K + rev_auto + rev_C

        # ---- households ------------------------------------------------------
        eshare = (skill * eff) / max(float((skill * eff).sum()), 1e-12)
        labour_income = eshare * wage_bill
        cap_income = (wealth / max(wealth.sum(), 1e-12)) * Profit * (1.0 - tau_K)
        ubi_i = (p["UBI_RATIO"] * Y / NH) if arm == "B3" else 0.0
        div_i = (payout / NH) if arm in ("B5", "B6", "B6c") else 0.0
        targ = expo / max(expo.sum(), 1e-12)
        trans_i = transition_amt * targ if arm in ("B6", "B6c") else 0.0

        income = labour_income * (1.0 - tau_L) + cap_income + ubi_i + div_i + trans_i
        disp = income / (1.0 + p["TAU_C"])
        wealth = np.clip(wealth * (1.0 + p["R_FUND"]) + srate * disp, 0.0, None)

        # ---- displacement and retraining -------------------------------------
        adopt = float((pm * M_f).sum()) / max(Y, 1e-12)
        auto_growth = max(adopt - prev_adopt, 0.0)
        eff = eff * (1.0 - p["LAM_DISP"] * expo * auto_growth)
        if retrain_amt > 0:
            eff = np.minimum(eff * (1.0 + p["RETRAIN_EFF"]
                                    * (retrain_amt / max(Y, 1e-9))
                                    * (expo / expo.mean())), 1.0)
        eff = np.clip(eff, 0.25, 1.0)
        prev_adopt = adopt

        # ---- record ----------------------------------------------------------
        H["Y"].append(Y); H["hours"].append(hours)
        H["ws"].append(wage_bill / max(Y, 1e-12))
        H["revr"].append(gov_rev / max(Y, 1e-12))
        H["gi"].append(gini(income)); H["gw"].append(gini(wealth))
        H["fund"].append(fund / max(4.0 * Y, 1e-12))
        H["div"].append(div_i / max(float(disp.mean()), 1e-12))
        H["divgdp"].append(payout / max(Y, 1e-12))
        H["pov"].append(float((disp < 0.5 * np.median(disp)).mean()))
        H["adopt"].append(adopt); H["taul"].append(tau_L)
        H["sac"].append(rev_auto / max(Y, 1e-12))

        if collect_path and t >= p["T_BURN"]:
            path.append((t - p["T_BURN"], Y, H["ws"][-1], H["gi"][-1],
                         H["fund"][-1], H["taul"][-1]))

        tau_L = tau_L_next

    s = slice(p["T_BURN"], None)
    m = lambda k: float(np.mean(H[k][s]))
    out = dict(
        arm=arm, seed=seed,
        Y=m("Y"), Y_end=float(H["Y"][-1]),
        hours=m("hours"), ws=m("ws"), ws_end=float(H["ws"][-1]),
        gi=m("gi"), gw=m("gw"), pov=m("pov"),
        rev_cv=float(np.std(H["revr"][s]) / max(np.mean(H["revr"][s]), 1e-12)),
        fund=float(H["fund"][-1]), div=m("div"), adopt=m("adopt"),
        divgdp=m("divgdp"), divgdp_end=float(H["divgdp"][-1]),
        taul=m("taul"), taul_end=float(H["taul"][-1]), sac=m("sac"),
        taul_cv=float(np.std(H["taul"][s]) / max(np.mean(H["taul"][s]), 1e-12)),
    )
    if collect_path:
        out["path"] = path
    return out


def _job(a):
    return run(a[0], a[1])


if __name__ == "__main__":
    import time, sys
    t0 = time.time()
    r = run(0, "B6")
    print("single B6 run %.2fs" % (time.time() - t0))
    print(json.dumps({k: v for k, v in r.items() if k != "path"}, indent=2))
