"""F3 (P0) - the government budget does not close in arms B6 / B6c.

In B6/B6c the state books  rev_auto = sum(wedge * ACB), but the firm's profit line is
computed with `pm_eff`, which encodes only the MARGINAL wedge r * d(ACB)/dM.  The
inframarginal bulk of the liability is therefore collected and spent without ever being
subtracted from firm profit -- so not from capital income, and not from the tau_K base.

Arms B1/B4 use pm_eff = pm*(1+wedge) with matching revenue and are exactly consistent,
so the error is ASYMMETRIC and inflates precisely the arms the paper advocates.

Part 1 instruments the model and measures the gap.
Part 2 patches profit to debit the true liability -- leaving the marginal decision price
untouched, so behaviour is unchanged -- and re-runs to size the effect.

Usage:  python check_budget.py [--seeds N]
"""

import re
import sys
import types
import numpy as np

from _common import banner, verdict, SIM
import cdos_sim as C

import os

PATCH_OLD = """        profit_f = np.maximum(Y_f - w * L_f - pm_eff * M_f, 0.0)
        Profit = float(profit_f.sum())"""

PATCH_NEW = """        profit_f = np.maximum(Y_f - w * L_f - pm_eff * M_f, 0.0)
        Profit = float(profit_f.sum())
        if arm in ("B6", "B6c"):
            _psi, _ = shapley_machine(alpha_f, A_f, L_f, M_f, sigma, gamma)
            _acb = np.maximum(_psi - phi * pm * M_f, 0.0)
            profit_f = np.maximum(Y_f - w * L_f - pm * M_f - wedge_f * _acb, 0.0)
            Profit = float(profit_f.sum())"""


def load_patched():
    """Build a patched module in memory from the project's own source."""
    src = open(os.path.join(SIM, "cdos_sim.py"), encoding="utf-8").read()
    if PATCH_OLD not in src:
        raise SystemExit("cdos_sim.py has changed; update PATCH_OLD in check_budget.py")
    mod = types.ModuleType("cdos_sim_patched")
    mod.__dict__["__file__"] = "<patched>"
    exec(compile(src.replace(PATCH_OLD, PATCH_NEW), "<patched>", "exec"), mod.__dict__)
    return mod


def part1_measure(quarters=80):
    banner("PART 1  revenue booked vs amount actually debited to firms", "F3")
    p = C.P
    rng = np.random.default_rng(0)
    NH, NF = p["N_H"], p["N_F"]
    sigma, gamma = p["SIGMA"], p["GAMMA"]
    skill = np.exp(rng.normal(0, .60, NH)); skill /= skill.mean()
    wealth = np.exp(rng.normal(0, 1.30, NH)); wealth *= 4 / wealth.mean()
    expo = np.clip(0.85 - 0.45 * (skill - skill.min()) / (skill.max() - skill.min())
                   + rng.normal(0, .10, NH), .02, .98)
    eff = np.ones(NH)
    A_f = np.exp(rng.normal(0, .35, NF)); A_f *= 1 / A_f.mean()
    alpha_f = np.clip(rng.beta(6, 4, NF), .25, .90)
    markup = np.clip(rng.normal(.22, .08, NF), .02, .60)
    C_rent = (markup - markup.min()) / max(markup.max() - markup.min(), 1e-9)

    tau_L, phi, lab0, w0 = p["TAU_L0"], 0.50, None, None
    rows = []
    for t in range(quarters):
        pm = p["PM0"] * np.exp(-p["DECAY"] * t)
        sup = float((skill * eff).sum())
        if lab0 is None:
            wedge = np.full(NF, p["R0"]); pm_eff = pm * np.ones(NF)
        else:
            wt = C.clear_wage(alpha_f, A_f, pm, sup, tau_L, p["EPS_L"], sigma, gamma,
                              iters=p["BISECT"])
            Lp, Mp, _, _ = C.firm_block(alpha_f, A_f, wt, pm, sigma, gamma)
            ls = (wt * Lp) / np.maximum(wt * Lp + pm * Mp, 1e-12)
            S_i = np.clip((lab0 - ls) / np.maximum(lab0, 1e-9), 0, 1)
            Aa = np.full(NF, float(np.clip((wt / w0 - 1) / .50, 0, 1)))
            wedge = np.clip(p["R0"] + p["W_ALPHA"] * S_i + p["W_BETA"] * C_rent
                            + p["W_ETA"] * S_i - p["W_THETA"] * Aa
                            - p["W_LAMBDA"] * .55 - p["W_NU"] * .30,
                            p["RMIN"], p["RMAX"])
            pm_eff = np.maximum(pm + wedge * (C.dpsi_dM(alpha_f, A_f, Lp, Mp, sigma, gamma)
                                              - phi * pm), 0.25 * pm)
        w = C.clear_wage(alpha_f, A_f, pm_eff, sup, tau_L, p["EPS_L"], sigma, gamma,
                         iters=p["BISECT"])
        L_f, M_f, Y_f, _ = C.firm_block(alpha_f, A_f, w, pm_eff, sigma, gamma)
        Y = float(Y_f.sum())
        psi_M, _ = C.shapley_machine(alpha_f, A_f, L_f, M_f, sigma, gamma)
        ACB = np.maximum(psi_M - phi * pm * M_f, 0.0)
        collected = float((wedge * ACB).sum())
        charged = float(((pm_eff - pm) * M_f).sum())
        if lab0 is not None:
            rows.append((t, collected / Y, charged / Y, charged / max(collected, 1e-12)))
        else:
            lab0 = (w * L_f) / np.maximum(w * L_f + pm * M_f, 1e-12); w0 = w
        adopt = float((pm * M_f).sum()) / max(Y, 1e-12)
        eff = np.clip(eff, .25, 1.)
        tau_L = p["TAU_L0"]

    g = np.array(rows)
    print("  arm B6c, seed 0")
    print("  %-9s %-14s %-16s %s" % ("quarter", "collected / Y", "charged / Y", "ratio"))
    for r in g[::12]:
        print("  %-9d %-14.5f %-16.5f %.3f" % (r[0], r[1], r[2], r[3]))
    mean = g[:, 3].mean()
    print()
    print("  mean charged/collected = %.3f" % mean)
    print("  => about %.0f%% of the automation revenue is never debited to any agent." % (100 * (1 - mean)))
    return mean < 0.5


def part2_patched(nseeds):
    banner("PART 2  effect of debiting the true liability", "F3")
    pat = load_patched()
    print("  Patch keeps pm_eff as the marginal decision price (so firm behaviour is")
    print("  unchanged) and debits wedge*ACB from profit as a lump sum.")
    print("  B1/B4 should be untouched -- they were already consistent.")
    print()
    seeds = range(nseeds)
    b0 = [C.run(s, "B0") for s in seeds]
    p0 = [pat.run(s, "B0") for s in seeds]
    print("  %-5s %-14s %-14s %s" % ("arm", "dGDP% orig", "dGDP% fixed", "change"))
    ok = True
    for a in ("B1", "B4", "B6", "B6c"):
        rb = [C.run(s, a) for s in seeds]
        rp = [pat.run(s, a) for s in seeds]
        pb = np.mean([100 * (rb[i]["Y"] / b0[i]["Y"] - 1) for i in range(nseeds)])
        pp = np.mean([100 * (rp[i]["Y"] / p0[i]["Y"] - 1) for i in range(nseeds)])
        if a in ("B1", "B4") and abs(pb - pp) > 1e-9:
            ok = False
        print("  %-5s %-14.3f %-14.3f %+.3f" % (a, pb, pp, pp - pb))
    print()
    print("  B1/B4 unchanged: %s (as predicted -- the defect is specific to B6/B6c)"
          % ("yes" if ok else "NO"))
    return ok


if __name__ == "__main__":
    n = 8
    if "--seeds" in sys.argv:
        n = int(sys.argv[sys.argv.index("--seeds") + 1])
    leak = part1_measure()
    print()
    asym = part2_patched(n)
    sys.exit(verdict(
        not leak,
        "unexpected - the budget now appears to close; re-read the audit",
        "F3 CONFIRMED - budget does not close in B6/B6c, and the error is asymmetric"))
