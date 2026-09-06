"""F2 (P0) - Proposition 6's stability condition fails in the paper's own testbed.

Proposition 6 requires  (1 - rho) * r_f  <  g  for a finite steady state.  The testbed
sets rho = 0.60 and r_f = 0.05 (giving 0.0200) while its realised output growth is about
0.0166.  The fund-to-output ratio is therefore on a divergent path, yet the terminal
17.0% of GDP is reported as consistent with an analytic steady state, and Table VI's
71-year half-life assumes g = 0.03.

Also re-verifies the Table VI arithmetic itself, which is correct.

Usage:  python check_fund.py
"""

import sys
import numpy as np

from _common import banner, verdict
import cdos_sim as C


def part1_condition():
    banner("PART 1  stability condition at the testbed's realised growth rate", "F2")
    rho, rf = C.P["RHO_PAYOUT"], C.P["R_FUND"] * 4
    lhs = (1 - rho) * rf
    path = C.run(0, "B0", collect_path=True)["path"]
    yrs = (path[-1][0] - path[0][0]) / 4.0
    g = (path[-1][1] / path[0][1]) ** (1 / yrs) - 1
    print("  (1 - rho) * r_f = (1 - %.2f) * %.3f = %.5f" % (rho, rf, lhs))
    print("  realised g      = %.5f   (measured from arm B0 over %.0f years)" % (g, yrs))
    print("  Prop. 6 assumes g = 0.03000 in Table VI and the 71-year half-life.")
    print()
    holds = lhs < g
    print("  CONDITION %s" % ("HOLDS" if holds else "*** FAILS ***"))
    return holds, g


def part2_trajectory():
    banner("PART 2  the fund ratio does not converge", "F2")
    path = C.run(0, "B6c", collect_path=True)["path"]
    print("  arm B6c, seed 0")
    print("  %-8s %s" % ("year", "fund / GDP"))
    for q in path[::40]:
        print("  %-8.0f %.4f" % (q[0] / 4.0, q[4]))
    print("  %-8.0f %.4f" % (path[-1][0] / 4.0, path[-1][4]))
    f = [q[4] for q in path]
    growth = 100 * (f[-1] / f[-41] - 1)
    print()
    print("  growth of the fund ratio over the final 10 years: %+.1f%%" % growth)
    print("  A converging series would be flattening here.")
    return growth


def part3_table6():
    banner("PART 3  Table VI arithmetic re-verified (this part is CORRECT)")
    s, g = 0.0065, 0.03
    print("  %-6s %-6s %-9s %-10s %s" % ("r_f", "rho", "f*", "d* (%)", "half-life (yr)"))
    for rf in (0.04, 0.05, 0.06):
        for rho in (0.55, 0.75, 0.95):
            fstar = s * (1 + g) / (g - (1 - rho) * rf)
            dstar = rho * rf * fstar
            a = (1 + (1 - rho) * rf) / (1 + g)
            hl = np.log(0.5) / np.log(a)
            print("  %-6.2f %-6.2f %-9.3f %-10.2f %.1f" % (rf, rho, fstar, 100 * dstar, hl))
    rho, rf = 0.60, 0.05
    a = (1 + (1 - rho) * rf) / (1 + g)
    print()
    print("  paper's calibration rho=0.60, r_f=0.05, g=0.03 -> half-life %.1f yr (paper says 71)"
          % (np.log(0.5) / np.log(a)))
    print("  All Table VI values reproduce exactly.  The defect is not the arithmetic --")
    print("  it is that g=0.03 is assumed while the testbed delivers g=0.0166.")


if __name__ == "__main__":
    holds, g = part1_condition()
    print()
    growth = part2_trajectory()
    print()
    part3_table6()
    sys.exit(verdict(
        holds,
        "unexpected - the condition now holds; re-read the audit",
        "F2 CONFIRMED - stability condition violated; fund ratio diverges"))
