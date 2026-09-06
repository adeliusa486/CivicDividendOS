"""Reproduction, citation hygiene, and paper-to-results traceability.

These are the checks the project PASSES, and they are worth keeping green.

Part 1  re-runs the full 8-arm x 50-seed campaign and diffs every stored statistic
        against simulation/results.json.  Expected: max deviation exactly 0.
Part 2  bibliography and cross-reference hygiene.
Part 3  regenerates the LaTeX tables and figure from results.json and compares them,
        number by number, with the values pasted into the manuscript.  Nothing in the
        repository currently enforces this, so drift is one careless edit away.

Usage:  python check_reproduction.py [--skip-campaign]
"""

import io
import itertools
import json
import os
import re
import sys
import tempfile
import numpy as np
from multiprocessing import Pool, cpu_count

from _common import banner, verdict, SIM, RESULTS, PAPER_TEX, PAPER_BIB
import cdos_sim as C

sys.path.insert(0, SIM)


def _job(a):
    return C.run(a[0], a[1])


def part1_campaign(nseeds=50):
    banner("PART 1  bit-exact reproduction of results.json")
    import driver
    tasks = list(itertools.product(range(nseeds), C.ARMS))
    with Pool(min(16, cpu_count())) as pool:
        res = pool.map(_job, tasks, chunksize=4)
    by = {a: [r for r in res if r["arm"] == a] for a in C.ARMS}
    keys = ["Y", "hours", "ws", "ws_end", "gi", "gw", "pov", "taul", "taul_cv",
            "fund", "divgdp", "adopt", "sac"]
    agg = {}
    for a in C.ARMS:
        agg[a] = {}
        for k in keys:
            v = np.array([r[k] for r in by[a]])
            lo, hi = driver.boot_ci(v)
            agg[a][k] = dict(mean=float(v.mean()), sd=float(v.std(ddof=1)), lo=lo, hi=hi)
        agg[a]["_paired"] = {}
        for k in ["Y", "hours", "gi", "gw", "pov", "taul", "ws_end"]:
            d = np.array([by[a][i][k] - by["B0"][i][k] for i in range(nseeds)])
            lo, hi = driver.boot_ci(d)
            rel = np.array([100.0 * (by[a][i][k] / by["B0"][i][k] - 1.0) for i in range(nseeds)])
            rlo, rhi = driver.boot_ci(rel)
            agg[a]["_paired"][k] = dict(diff=float(d.mean()), lo=lo, hi=hi,
                                        pct=float(rel.mean()), plo=rlo, phi=rhi)

    old = json.load(open(RESULTS))
    mx, worst, n = 0.0, None, 0
    for a in agg:
        for k, v in agg[a].items():
            if k == "_paired":
                for kk, vv in v.items():
                    for f, x in vv.items():
                        n += 1
                        d = abs(x - old[a]["_paired"][kk][f])
                        if d > mx:
                            mx, worst = d, (a, kk, f)
            else:
                for f, x in v.items():
                    n += 1
                    d = abs(x - old[a][k][f])
                    if d > mx:
                        mx, worst = d, (a, k, f)
    print("  compared %d stored statistics over %d runs" % (n, len(res)))
    print("  max absolute deviation: %g   %s" % (mx, "" if worst is None else str(worst)))
    print()
    print("  %s" % ("BIT-EXACT" if mx == 0 else "*** NOT EXACT ***"))
    print("  environment: python %s, numpy %s" % (sys.version.split()[0], np.__version__))
    return mx == 0


def part2_citations():
    banner("PART 2  bibliography and cross-reference hygiene")
    tex = open(PAPER_TEX, encoding="utf-8").read()
    bib = open(PAPER_BIB, encoding="utf-8").read()
    keys = set(re.findall(r"^@\w+\{([^,]+),", bib, re.M))
    cited = set()
    for m in re.findall(r"\\cite\{([^}]+)\}", tex):
        cited |= {k.strip() for k in m.split(",")}
    labels = set(re.findall(r"\\label\{([^}]+)\}", tex))
    refs = set(re.findall(r"\\(?:eq)?ref\{([^}]+)\}", tex))
    print("  bib entries %d   cited %d   labels %d   refs %d"
          % (len(keys), len(cited), len(labels), len(refs)))
    print("  cited but not in bib : %s" % (sorted(cited - keys) or "none"))
    print("  in bib but uncited   : %s" % (sorted(keys - cited) or "none"))
    print("  dangling refs        : %s" % (sorted(refs - labels) or "none"))
    print("  unreferenced labels  : %s" % (sorted(labels - refs) or "none"))
    ents = re.findall(r"@(\w+)\{([^,]+),(.*?)\n\}", bib, re.S)
    noyear = [k for _, k, b in ents if not re.search(r"\byear\s*=", b, re.I)]
    nodoi = [k for _, k, b in ents if not re.search(r"\bdoi\s*=", b, re.I)]
    print("  entries missing year : %s" % (noyear or "none"))
    print("  entries missing doi  : %d of %d" % (len(nodoi), len(ents)))
    return not (cited - keys) and not (keys - cited) and not (refs - labels)


def part3_traceability():
    banner("PART 3  do the manuscript's pasted numbers still match results.json?")
    cwd = os.getcwd()
    tmp = tempfile.mkdtemp(prefix="cdos_trace_")
    try:
        os.chdir(tmp)
        import shutil
        shutil.copy(RESULTS, os.path.join(tmp, "results.json"))
        sys.argv = ["mklatex"]
        import runpy
        runpy.run_path(os.path.join(SIM, "mklatex.py"), run_name="__main__")
        tex = open(PAPER_TEX, encoding="utf-8").read()

        def nums(s):
            return re.findall(r"[-+]?\d+\.\d+", s)

        def body(src, label):
            m = re.search(r"\\label\{" + label + r"\}(.*?)\\bottomrule", src, re.S)
            return m.group(1) if m else ""

        ok = True
        for label, gen in (("tab:results", "results_table.tex"), ("tab:ci", "ci_table.tex")):
            paper = nums(body(tex, label))
            fresh = nums(body(open(gen, encoding="utf-8").read(), label))
            match = paper == fresh
            ok &= match
            print("  %-12s paper %3d numbers   generated %3d   %s"
                  % (label, len(paper), len(fresh), "MATCH" if match else "MISMATCH"))
        pf = re.search(r"\\label\{fig:results\}", tex)
        blk = tex[tex.rfind(r"\begin{figure}", 0, pf.start()):pf.start()]
        pc = re.findall(r"\(([\d.]+),([\d.]+)\)", blk)
        fc = re.findall(r"\(([\d.]+),([\d.]+)\)", open("results_fig.tex", encoding="utf-8").read())
        ok &= pc == fc
        print("  %-12s paper %3d points    generated %3d   %s"
              % ("fig:results", len(pc), len(fc), "MATCH" if pc == fc else "MISMATCH"))
        print()
        print("  NOTE: the manuscript hand-pastes these values.  There is no \\input{} and")
        print("  no CI check, so this agreement is not enforced by anything.")
        return ok
    finally:
        os.chdir(cwd)


if __name__ == "__main__":
    ok = True
    if "--skip-campaign" not in sys.argv:
        ok &= part1_campaign()
        print()
    ok &= part2_citations()
    print()
    ok &= part3_traceability()
    sys.exit(verdict(ok,
                     "all reproduction checks PASS - keep these green",
                     "*** a reproduction check FAILED - investigate before trusting output"))
