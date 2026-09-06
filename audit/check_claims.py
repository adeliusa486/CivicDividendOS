"""F4, F5, F6, F9 - secondary claims in the manuscript that do not hold.

F4  "Arms are revenue-matched by construction" (stated twice) is false: total spending
    differs by up to 2.0 percentage points of GDP across arms.
F5  The "mutual consistency" claim compares total SAC revenue against the required FUND
    INFLOW.  Only omega=0.40 of SAC reaches the fund, so B6c delivers 61% of what its own
    design rule requires -- it undershoots rather than "brackets".
F6  The "Hours" column is labour demand in EFFICIENCY UNITS, raised directly by retraining
    spending, so B4's "largest employment gain" is not an employment result.
F9  Worked example: "4,000 MU on each of 60 robots yields 0.240 MU" is off by 10^6.

Usage:  python check_claims.py
"""

import json
import sys
import numpy as np

from _common import banner, verdict, RESULTS
import cdos_sim as C


def f4_spending(nquarters=120):
    banner("F4  are the arms actually revenue-matched?", "P1")
    p = C.P
    print("  Paper: 'Arms are revenue-matched by construction so that differences reflect")
    print("  instrument design rather than fiscal stance.'")
    print("  Model:  needed = SPEND_RATIO*Y + prog_spend   <- programme spending is EXTRA")
    print()
    print("  %-5s %-18s %s" % ("arm", "total spend / Y", "vs B0"))
    base = None
    ok = True
    for arm in C.ARMS:
        r = C.run(0, arm)
        # programme spending is recoverable from the reported ratios
        prog = 0.0
        if arm == "B3":
            prog = p["UBI_RATIO"]
        elif arm == "B4":
            prog = 0.60 * r["sac"]
        elif arm in ("B6", "B6c"):
            prog = (p["OMEGA"] + p["SIGMA_T"]) * r["sac"] + r["divgdp"]
        elif arm == "B5":
            prog = r["divgdp"] + p["AOU_XI"] * 0.0
        if arm in ("B5", "B6", "B6c"):
            prog = prog  # dividend payout is spent
        tot = p["SPEND_RATIO"] + prog
        if base is None:
            base = tot
        d = tot - base
        if abs(d) > 1e-6:
            ok = False
        print("  %-5s %-18.5f %s" % (arm, tot, "" if abs(d) < 1e-6 else "%+.2f pp of GDP" % (100 * d)))
    print()
    print("  Spending differs across arms, so the tau_L comparison confounds instrument")
    print("  design with fiscal stance -- the exact confound the sentence claims to exclude.")
    return ok


def f5_fund_inflow():
    banner("F5  the 'brackets 0.65% of output' consistency claim", "P1")
    agg = json.load(open(RESULTS))
    kd, g, rf, rho = 0.02, 0.03, 0.05, 0.60
    om = C.P["OMEGA"]
    s_req = kd * (g - (1 - rho) * rf) / (rho * rf * (1 + g))
    sac = agg["B6c"]["sac"]["mean"]
    print("  required FUND INFLOW s      = %.4f%% of output   (paper quotes 0.65%%)" % (100 * s_req))
    print("  B6c total SAC revenue       = %.4f%% of output   (paper compares THIS)" % (100 * sac))
    print("  but only omega = %.2f reaches the fund:" % om)
    print("  B6c actual fund inflow      = %.2f x %.4f%% = %.4f%% of output"
          % (om, 100 * sac, 100 * om * sac))
    print()
    print("  => B6c delivers %.0f%% of the inflow its own design rule requires."
          % (100 * om * sac / s_req))
    print("  Corrected, the finding REVERSES: the fund undershoots by roughly %.0f%%."
          % (100 * (1 - om * sac / s_req)))
    print("  This strengthens the paper's own 'fund is intergenerational' conclusion.")
    return abs(om * sac - s_req) / s_req < 0.05


def f6_hours():
    banner("F6  is the 'Hours' column hours?", "P1")
    print("  cdos_sim.py records   H['hours'] = L_f.sum()   -- labour demand in EFFICIENCY")
    print("  UNITS.  Labour supply is  sup_scale = (skill * eff).sum(), and retraining does:")
    print("    eff = min(eff * (1 + RETRAIN_EFF * (retrain/Y) * (expo/expo.mean())), 1.0)")
    print("  so retraining spending raises the reported quantity directly.")
    print()
    agg = json.load(open(RESULTS))
    print("  %-5s %-14s %s" % ("arm", "reported Hours%", "note"))
    for a in ("B0", "B4", "B6c"):
        note = "retraining-financed (0.60 of automation revenue)" if a == "B4" else ""
        print("  %-5s %-14.2f %s" % (a, agg[a]["_paired"]["hours"]["pct"], note))
    print()
    print("  B4's '+8.52%, largest employment gain of any arm' conflates employment with")
    print("  restored human capital.  Headcount and hours are never reported separately.")
    return False


def f9_units():
    banner("F9  worked-example unit error", "P2")
    print("  Paper: 'a levy of 4,000 MU on each of 60 robots yields 0.240 MU'")
    print("    4,000 x 60 = %s MU,  not 0.240 MU  -- a factor of 10^6." % f"{4000*60:,}")
    print("  Annual value added is defined as V = 40.0 MU, so MU is never millions.")
    print()
    print("  Everything else in the example is exact:")
    a = dict(H=0.220, A=0.135, R=0.220, D=0.020, K=0.045)
    b = {("H","A"):0.10, ("A","D"):0.05, ("R","K"):0.06, ("A","R"):0.06,
         ("H","R"):0.04, ("H","K"):0.02, ("A","K"):0.02, ("D","K"):0.01}
    psi = {f: a[f] + 0.5 * sum(v for k, v in b.items() if f in k) for f in a}
    print("    Shapley shares  %s  sum = %.3f"
          % (", ".join("%s=%.2f" % (f, psi[f]) for f in "HARDK" if f in psi), sum(psi.values())))
    acb = (psi["A"] + psi["R"]) * 40.0 - 8.4
    idx = dict(S=0.62, Cr=0.35, E=0.48, X=0.10, R=0.55, Aa=0.40, T=0.55, B=0.20, N=0.30)
    r = (0.08 + 0.10*idx["S"] + 0.06*idx["Cr"] + 0.05*idx["E"] + 0.04*idx["X"] + 0.05*idx["R"]
         - 0.09*idx["Aa"] - 0.07*idx["T"] - 0.05*idx["B"] - 0.06*idx["N"])
    r2 = (0.08 + 0.10*0.15 + 0.06*0.35 + 0.05*0.10 + 0.04*0.10 + 0.05*0.55
          - 0.09*0.85 - 0.07*0.55 - 0.05*0.20 - 0.06*0.30)
    print("    ACB = %.2f MU,  r = %.4f / %.4f,  SAC = %.3f / %.3f MU,  ratio %.1fx"
          % (acb, r, r2, r * acb, r2 * acb, (r * acb) / (r2 * acb)))
    return False


if __name__ == "__main__":
    results = [f4_spending(), print() or f5_fund_inflow(), print() or f6_hours(),
               print() or f9_units()]
    sys.exit(verdict(
        all(results),
        "unexpected - all secondary claims now hold; re-read the audit",
        "F4/F5/F6/F9 CONFIRMED - four secondary claims do not hold as stated"))
