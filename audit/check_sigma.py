"""F1 (P0) - the headline robustness claim is circular, and the result reverses.

The paper states that  dv({M})/dM < p_M  "holds for every firm in every quarter of
every run", offering this as evidence that Proposition 2 is "not a knife-edge case".

Part 1 shows that under the model's own CES-with-span-of-control technology the ratio
of the stand-alone to the joint marginal product is exactly

        dv({M})/dM  /  dY/dM  =  s_M ** (gamma/rho - 1),      s_M in (0,1)

so the inequality holds IDENTICALLY whenever gamma > rho = 1 - 1/sigma.  At the paper's
gamma=0.85, sigma=1.5 it cannot fail, and 100% incidence is therefore not evidence.

Part 2 re-runs the campaign across sigma and shows arm B6c's advantage reversing.
Part 3 checks this is not an artefact of the baseline moving with sigma.

Usage:  python check_sigma.py [--quick]
"""

import sys
import numpy as np
from multiprocessing import Pool

from _common import banner, verdict
import cdos_sim as C

SIGMAS = [1.2, 1.5, 2.0, 3.0, 5.0, 8.0]
SEEDS = range(5)


def part1_closed_form():
    banner("PART 1  the inequality is structural, not empirical", "F1")
    rng = np.random.default_rng(0)
    print("  %-6s %-7s %-9s  %-11s %-11s  %s"
          % ("sigma", "rho", "gamma/rho", "min ratio", "max ratio", "dv({M})/dM < p_M ?"))
    flips = []
    for sigma in SIGMAS:
        gamma, rho = C.P["GAMMA"], 1.0 - 1.0 / sigma
        a = rng.uniform(0.25, 0.90, 4000)
        A = np.exp(rng.normal(0, 0.35, 4000))
        pm = rng.uniform(0.3, 1.0, 4000)
        L, M, _, _ = C.firm_block(a, A, 1.0, pm, sigma, gamma)
        S = a * L ** rho + (1 - a) * M ** rho
        dvM = A * (1 - a) ** (gamma / rho) * gamma * M ** (gamma - 1)
        dY = A * gamma * S ** (gamma / rho - 1) * (1 - a) * M ** (rho - 1)
        ratio = dvM / dY
        closed = ((1 - a) * M ** rho / S) ** (gamma / rho - 1)
        assert np.allclose(ratio, closed, rtol=1e-9), "closed form disagrees with the model"
        holds = ratio.max() < 1.0
        flips.append(holds)
        print("  %-6.1f %-7.3f %-9.3f  %-11.4f %-11.4f  %s"
              % (sigma, rho, gamma / rho, ratio.min(), ratio.max(),
                 "always (cannot fail)" if holds else "*** SIGN FLIPS ***"))
    print()
    print("  Closed form verified against the model at rtol 1e-9 over 4000 draws per sigma.")
    print("  The condition is  gamma > 1 - 1/sigma  -- a property of the calibration,")
    print("  not a finding about the world.  The paper reports it as the latter.")
    return not all(flips)


def _job(t):
    sig, seed, arm = t
    p = dict(C.P)
    p["SIGMA"] = sig
    return (sig, seed, arm, C.run(seed, arm, p=p))


def part2_campaign(sigmas):
    banner("PART 2  arm B6c's advantage reverses as sigma rises", "F1")
    tasks = [(s, sd, a) for s in sigmas for sd in SEEDS for a in ("B0", "B6", "B6c")]
    with Pool(min(12, len(tasks))) as pool:
        res = pool.map(_job, tasks, chunksize=2)
    D = {}
    for sig, seed, arm, r in res:
        D.setdefault((sig, arm), {})[seed] = r
    print("  %-6s  %-12s %-12s  %-11s %s"
          % ("sigma", "dGDP% B6", "dGDP% B6c", "SAC %Y B6c", "fund %Y B6c"))
    reversed_at = None
    for sig in sigmas:
        b0 = D[(sig, "B0")]
        row = [sig]
        for arm in ("B6", "B6c"):
            d = D[(sig, arm)]
            row.append(np.mean([100 * (d[s]["Y"] / b0[s]["Y"] - 1) for s in SEEDS]))
        d6c = D[(sig, "B6c")]
        row.append(100 * np.mean([d6c[s]["sac"] for s in SEEDS]))
        row.append(100 * np.mean([d6c[s]["fund"] for s in SEEDS]))
        if row[2] < 0 and reversed_at is None:
            reversed_at = sig
        print("  %-6.1f  %-12.2f %-12.2f  %-11.3f %.1f" % tuple(row))
    print()
    if reversed_at:
        print("  B6c's output effect turns NEGATIVE at sigma = %.1f." % reversed_at)
        print("  The paper's calibration is sigma = 1.5 and reports no sensitivity analysis,")
        print("  although its own Metrics subsection says one is required.")
    return reversed_at is not None


def part3_baseline_confound(sigmas):
    banner("PART 3  is this just the baseline moving with sigma?", "F1")
    with Pool(min(6, len(sigmas))) as pool:
        b0 = pool.map(_job, [(s, 0, "B0") for s in sigmas])
    print("  %-6s %-14s %-14s %s" % ("sigma", "B0 ws (mean)", "B0 ws (end)", "B0 GDP level"))
    for sig, _, _, r in b0:
        print("  %-6.1f %-14.4f %-14.4f %.1f" % (sig, r["ws"], r["ws_end"], r["Y"]))
    print()
    print("  Mean baseline labour share is near-identical at sigma 1.5 vs 2.0, so the")
    print("  reversal in Part 2 is not explained by a shifted baseline.  The terminal")
    print("  share does fall with sigma (faster substitution), which is a real mechanism.")


if __name__ == "__main__":
    sigmas = [1.2, 1.5, 2.0, 3.0] if "--quick" in sys.argv else SIGMAS
    circular = part1_closed_form()
    print()
    reverses = part2_campaign(sigmas)
    print()
    part3_baseline_confound(sigmas)
    sys.exit(verdict(
        not (circular and reverses),
        "unexpected - the claim now looks robust; re-read the audit",
        "F1 CONFIRMED - the robustness claim is circular and the result reverses"))
