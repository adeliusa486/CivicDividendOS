"""Run the full 7-arm x 50-seed campaign and emit LaTeX table + figure data."""

import json, time, itertools
import numpy as np
from multiprocessing import Pool
from cdos_sim import run, ARMS, ARM_LABEL, P

N_SEEDS = 50


def job(a):
    return run(a[0], a[1])


def boot_ci(x, reps=2000, seed=12345):
    rng = np.random.default_rng(seed)
    x = np.asarray(x, dtype=float)
    idx = rng.integers(0, x.size, size=(reps, x.size))
    means = x[idx].mean(axis=1)
    return float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


if __name__ == "__main__":
    t0 = time.time()
    tasks = list(itertools.product(range(N_SEEDS), ARMS))
    with Pool(processes=16) as pool:
        res = pool.map(job, tasks, chunksize=4)
    print("campaign: %d runs in %.1fs" % (len(res), time.time() - t0))

    by = {a: [r for r in res if r["arm"] == a] for a in ARMS}
    keys = ["Y", "hours", "ws", "ws_end", "gi", "gw", "pov", "taul", "taul_cv",
            "fund", "divgdp", "adopt", "sac"]

    agg = {}
    for a in ARMS:
        agg[a] = {}
        for k in keys:
            v = np.array([r[k] for r in by[a]])
            lo, hi = boot_ci(v)
            agg[a][k] = dict(mean=float(v.mean()), sd=float(v.std(ddof=1)),
                             lo=lo, hi=hi)

    # paired differences vs B0 (common random numbers -> paired by seed)
    for a in ARMS:
        agg[a]["_paired"] = {}
        for k in ["Y", "hours", "gi", "gw", "pov", "taul", "ws_end"]:
            d = np.array([by[a][i][k] - by["B0"][i][k] for i in range(N_SEEDS)])
            lo, hi = boot_ci(d)
            rel = np.array([100.0 * (by[a][i][k] / by["B0"][i][k] - 1.0)
                            for i in range(N_SEEDS)])
            rlo, rhi = boot_ci(rel)
            agg[a]["_paired"][k] = dict(diff=float(d.mean()), lo=lo, hi=hi,
                                        pct=float(rel.mean()), plo=rlo, phi=rhi)

    json.dump(agg, open("results.json", "w"), indent=1)

    # ---- console summary ----
    print("\narm  dGDP%%   dHours%%  wageshare_end  Gini_i           Gini_w    "
          "tau_L    CV(tau_L)  Fund/Y  Div%%GDP  SAC%%GDP  Pov")
    for a in ARMS:
        g = agg[a]; pr = g["_paired"]
        print(f"{a}  {pr['Y']['pct']:6.2f}  {pr['hours']['pct']:6.2f}   "
              f"{g['ws_end']['mean']:.4f}      "
              f"{g['gi']['mean']:.4f} [{g['gi']['lo']:.4f},{g['gi']['hi']:.4f}]  "
              f"{g['gw']['mean']:.4f}  {g['taul']['mean']:.4f}  "
              f"{g['taul_cv']['mean']:.4f}   {g['fund']['mean']:.3f}  "
              f"{100*g['divgdp']['mean']:.3f}   {100*g['sac']['mean']:.3f}   "
              f"{g['pov']['mean']:.4f}")

    # ---- LaTeX table rows ----
    rows = []
    for a in ARMS:
        g = agg[a]; pr = g["_paired"]
        nm = ARM_LABEL[a]
        if a == "B6":
            nm = r"\textbf{CivicDividendOS (integrated)}"
        rows.append(
            f"{a} & {nm} & ${pr['Y']['pct']:+.2f}$ & ${pr['hours']['pct']:+.2f}$ & "
            f"${g['ws_end']['mean']:.3f}$ & ${g['gi']['mean']:.4f}$ & "
            f"${g['gw']['mean']:.4f}$ & ${g['taul']['mean']:.3f}$ & "
            f"${g['fund']['mean']:.2f}$ & ${100*g['divgdp']['mean']:.2f}$ \\\\")
    open("table_rows.tex", "w", newline="\n").write("\n".join(rows) + "\n")

    # ---- CI table for key contrasts ----
    ci = []
    for a in ARMS[1:]:
        pr = agg[a]["_paired"]
        ci.append(f"{a} & ${pr['gi']['diff']:+.4f}$ & $[{pr['gi']['lo']:+.4f}, "
                  f"{pr['gi']['hi']:+.4f}]$ & ${pr['taul']['diff']:+.4f}$ & "
                  f"$[{pr['taul']['lo']:+.4f}, {pr['taul']['hi']:+.4f}]$ \\\\")
    open("table_ci.tex", "w", newline="\n").write("\n".join(ci) + "\n")

    # ---- figure paths (seed 0) ----
    paths = {a: run(0, a, collect_path=True)["path"] for a in ARMS}
    with open("fig_paths.json", "w") as f:
        json.dump(paths, f)

    for a in ("B0", "B1", "B3", "B6"):
        pts = paths[a][::8]
        coords = " ".join(f"({q[0]/4.0:.2f},{q[2]:.4f})" for q in pts)
        open(f"fig_ws_{a}.dat", "w", newline="\n").write(coords + "\n")
        coords2 = " ".join(f"({q[0]/4.0:.2f},{q[5]:.4f})" for q in pts)
        open(f"fig_taul_{a}.dat", "w", newline="\n").write(coords2 + "\n")

    print("\nwrote results.json, table_rows.tex, table_ci.tex, fig_*.dat")
