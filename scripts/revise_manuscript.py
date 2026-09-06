"""Apply the post-audit revisions to CivicDividendOS_v2.tex.

Idempotent: every replacement checks whether it has already been applied, so
the script can be re-run after further edits without corrupting the file. It
refuses to run if an expected passage is missing, rather than silently doing
nothing -- a revision that quietly fails is how the audited numbers survived in
the first place.

The revisions are those listed in HANDOFF.md section 5. They are not cosmetic:
the headline claim is withdrawn and replaced by a conditional one, and two
passages that the audit showed to be circular or false are removed.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import List, Tuple

ROOT = Path(__file__).resolve().parents[1]
TEX = ROOT / "CivicDividendOS_v2.tex"

# (label, old fragment, new fragment). Old must appear exactly once.
REPLACEMENTS: List[Tuple[str, str, str]] = [

# ---------------------------------------------------------------------------
# F1a: the circular robustness argument
# ---------------------------------------------------------------------------
("F1a circular incidence claim",
 r"In the testbed of Section~\ref{sec:model} this is not a knife-edge case: "
 r"$\partial v(\{M\})/\partial M < p_M$ holds for every firm in every quarter "
 r"of every run, and the implied effective wedge is between $-3.3\%$ and "
 r"$-4.1\%$ of the machine price.",
 r"The condition under which this bites is structural rather than empirical, "
 r"and it is worth stating precisely. Under the CES-with-span-of-control "
 r"technology of Section~\ref{sec:model} the ratio of the stand-alone to the "
 r"joint marginal product is exactly $s_M^{\gamma/\rho-1}$ with "
 r"$s_M\in(0,1)$ and $\rho = 1-1/\sigma$, so $\partial v(\{M\})/\partial M < "
 r"p_M$ holds \emph{identically} whenever $\gamma > 1-1/\sigma$. At the "
 r"calibration of Section~\ref{sec:model} ($\gamma=0.85$, $\sigma=1.5$) the "
 r"inequality therefore cannot fail, and its universal incidence across firms "
 r"and quarters is a property of the calibration rather than evidence about "
 r"the world. We report it as such. The implied effective wedge at that "
 r"calibration is between $-3.3\%$ and $-4.1\%$ of the machine price."),

# ---------------------------------------------------------------------------
# F4: the revenue-matching claim, stated twice
# ---------------------------------------------------------------------------
("F4 revenue matching (first statement)",
 r"Arms are revenue-matched by construction so that differences reflect "
 r"instrument design rather than fiscal stance.",
 r"Every arm finances the same baseline public spending, but the arms are "
 r"\emph{not} revenue-matched: each also finances its own programme spending, "
 r"so total spending differs across arms by up to two percentage points of "
 r"output. Contrasts therefore reflect fiscal stance as well as instrument "
 r"design, and the revenue-normalised comparison of "
 r"Section~\ref{sec:results} is the one to read when ranking instruments."),

("F4 revenue matching (second statement)",
 r"Arms are thus revenue-matched by construction, and differ only in the "
 r"instruments used and in what the proceeds buy.",
 r"Arms therefore differ both in the instruments used and in how much revenue "
 r"those instruments raise, which is why output effects alone do not rank "
 r"them."),

# ---------------------------------------------------------------------------
# F9: the worked-example unit error
# ---------------------------------------------------------------------------
("F9 worked-example units",
 r"a levy of $4{,}000$ MU on each of 60 robots yields $0.240$ MU in both "
 r"configurations.",
 r"a levy of $0.004$ MU on each of 60 robots yields $0.240$ MU in both "
 r"configurations. (Annual value added in this example is $V = 40.0$ MU, so "
 r"the monetary unit is not millions; an earlier version of this example "
 r"stated the per-robot levy in units inconsistent with $V$.)"),
]


def _check_unique(text: str, fragment: str, label: str) -> None:
    count = text.count(fragment)
    if count == 0:
        raise SystemExit(
            f"REVISION FAILED [{label}]: the passage to replace was not found.\n"
            f"Either it has already been revised, or the manuscript has moved on "
            f"and this script needs updating. Nothing was written.")
    if count > 1:
        raise SystemExit(
            f"REVISION FAILED [{label}]: the passage appears {count} times; "
            "the replacement would be ambiguous. Nothing was written.")


def main(argv=None) -> int:
    if not TEX.exists():
        raise SystemExit(f"manuscript not found at {TEX}")
    text = TEX.read_text(encoding="utf-8")
    original = text

    applied, already = [], []
    for label, old, new in REPLACEMENTS:
        if new in text:
            already.append(label)
            continue
        _check_unique(text, old, label)
        text = text.replace(old, new, 1)
        applied.append(label)

    if text != original:
        TEX.write_text(text, encoding="utf-8", newline="\n")

    for label in applied:
        print(f"  applied  {label}")
    for label in already:
        print(f"  already  {label}")
    print(f"\n{len(applied)} revision(s) applied, {len(already)} already present")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
