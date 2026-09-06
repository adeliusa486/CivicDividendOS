"""Shared setup for the audit checks.

Every check imports the project's own simulation module rather than a copy, so
these scripts stay honest if `simulation/cdos_sim.py` is edited.
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SIM = os.path.join(ROOT, "simulation")
PAPER_TEX = os.path.join(ROOT, "CivicDividendOS_v2.tex")
PAPER_BIB = os.path.join(ROOT, "civicdividendos.bib")
RESULTS = os.path.join(SIM, "results.json")

if SIM not in sys.path:
    sys.path.insert(0, SIM)


def banner(title, finding=""):
    line = "=" * 74
    print(line)
    print(title if not finding else "%s   [%s]" % (title, finding))
    print(line)


def verdict(ok, msg_ok, msg_bad):
    print()
    print("VERDICT: " + (msg_ok if ok else msg_bad))
    return 0 if ok else 1
