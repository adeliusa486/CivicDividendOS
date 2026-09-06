"""Run every audit check and print a summary.

  python run_all.py            full run   (~6 min: includes the 400-run campaign)
  python run_all.py --quick    fast run   (~2 min: fewer seeds, fewer sigma values)
"""

import subprocess
import sys
import time
import os

HERE = os.path.dirname(os.path.abspath(__file__))
QUICK = "--quick" in sys.argv

CHECKS = [
    ("check_reproduction.py", ["--skip-campaign"] if QUICK else [],
     "reproduction, citations, traceability", "PASS expected"),
    ("check_sigma.py", ["--quick"] if QUICK else [],
     "F1  circular robustness claim; result reverses", "P0"),
    ("check_budget.py", ["--seeds", "4"] if QUICK else ["--seeds", "8"],
     "F3  budget does not close in B6/B6c", "P0"),
    ("check_fund.py", [], "F2  fund stability condition fails", "P0"),
    ("check_claims.py", [], "F4/F5/F6/F9  secondary claims", "P1/P2"),
]

if __name__ == "__main__":
    print("CivicDividendOS audit harness%s\n" % ("  (quick mode)" if QUICK else ""))
    out = []
    for script, args, desc, sev in CHECKS:
        t0 = time.time()
        r = subprocess.run([sys.executable, os.path.join(HERE, script)] + args,
                           capture_output=True, text=True, cwd=HERE)
        tail = [l for l in r.stdout.splitlines() if l.startswith("VERDICT:")]
        out.append((script, sev, desc, tail[0][9:] if tail else "(no verdict)",
                    time.time() - t0))
        print("  %-26s %-6s %5.1fs  %s" % (script, sev, out[-1][4], out[-1][3]))
    print()
    print("=" * 74)
    print("Findings stand as recorded in AUDIT_REPORT.html.")
    print("Nothing in the paper or simulation has been modified by these checks.")
