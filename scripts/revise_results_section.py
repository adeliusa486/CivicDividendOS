"""Replace the manuscript's Results section with the post-correction version.

This is the substantive revision. The old section reported that arm B6c
"improves on the baseline on every reported dimension simultaneously, which no
other arm does" at a single calibration, with numbers produced by a model whose
budget did not close. Both parts of that had to go.

The replacement:

* reports the corrected numbers;
* states the headline result **conditionally**, with the validity region from
  E01, and says plainly that B6c does not dominate;
* reports the revenue-normalised comparison, under which B6c is *worse* than
  the fixed robot tax;
* reports that the fund diverges on a substantial share of seeds;
* distinguishes replication from structural uncertainty;
* pulls every table in with \\input from paper/generated/, so no number in the
  results tables is typed by hand.

Idempotent, and refuses to run if the passage it expects is absent.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEX = ROOT / "CivicDividendOS_v2.tex"

MARKER = "% === RESULTS SECTION REVISED POST-AUDIT ==="

NEW_RESULTS = r"""% === RESULTS SECTION REVISED POST-AUDIT ===
\subsection{Results}
\label{sec:results}

Table~\ref{tab:results} reports the campaign and Table~\ref{tab:ci} the paired
contrasts. All numerical entries in these tables are generated directly from the
simulation output by \texttt{scripts/make\_tables.py} and included with
\verb|\input|; none is transcribed by hand.

Two framing points come first, because they govern how everything below should
be read.

\emph{The confidence intervals are replication intervals.} Arms share common
random numbers, so contrasts are paired and the bootstrap intervals over seeds
are extremely tight. That is a statement about the reproducibility of the
simulation at one parameter vector, and not about the certainty of any policy
conclusion. The sensitivity analysis of Section~\ref{sec:sensitivity} moves the
central estimate by tens of percentage points, which no replication interval
here can see.

\emph{The arms are not revenue-matched.} Each finances the same baseline public
spending plus its own programme, so total spending differs across arms. Ranking
instruments by output effect alone is therefore not valid, and
Table~\ref{tab:revnorm} gives the revenue-normalised comparison.

Six findings stand out, and they do not uniformly favour the proposed framework.

First, the fixed robot tax of arm B1 is by a wide margin the most costly
instrument in output terms, at $-6.12\%$ relative to baseline, while raising
$1.91\%$ of output in revenue. It does support the labour share, which ends at
$0.341$ against $0.298$ in the baseline, but it achieves this by taxing an input
at a uniform rate irrespective of whether the automation in question displaced
anyone. This is the quantitative counterpart of the attribution gap of
Section~\ref{sec:problem}.

Second, the framework as literally specified in \eqref{eq:acb} is close to
inert. Arm B6 raises only $0.24\%$ of output and reduces the income Gini by
$0.0022$, which is statistically clear and economically negligible. Its output
effect is positive, at $+2.45\%$, \emph{precisely because} the base is
marginally subsidising in the sense of Proposition~\ref{prop:margin}. A positive
output number here is evidence of the design defect, not of merit.

Third, the corrected base repairs the revenue problem but does not deliver
dominance. Arm B6c raises $0.88\%$ of output, lowers the required labour tax
from $0.381$ to $0.370$ $(\Delta\tau_L = -0.0111$, $\mathrm{CI}_{95\%} =
[-0.0118,-0.0103])$, reduces the income Gini by $0.0072$ $(\mathrm{CI}_{95\%} =
[-0.0077,-0.0068])$, and raises output by $3.18\%$ and labour demand in
efficiency units by $6.78\%$, holding the terminal labour share at $0.316$
against $0.298$. These figures are produced under corrected budget accounting,
in which the full contribution liability $r_i\ACB_i$ is debited from firm
profit while the marginal decision price remains $p_M + r_i\,\partial\ACB/
\partial M$ as Proposition~\ref{prop:margin} requires. Under the earlier
accounting, in which only the marginal wedge was debited, the same arm showed
$+3.30\%$; the difference is the mechanical effect of charging the
inframarginal liability to somebody.

Fourth, and decisively against the strong reading of the proposal, B6c is
\emph{not} the most efficient instrument once revenue is held constant.
Table~\ref{tab:revnorm} reports revenue raised per unit of deadweight loss on
the labour margin. B6c returns $0.45$, against $1.47$ for the fixed robot tax
of B1 and $0.89$ for the automation levy of B4. B6c looks good on output
largely because it raises little revenue. Furthermore, arm B9, which finances
the same programme with a lump-sum levy rather than with the attributed
contribution, attains $+3.03\%$ output against B6c's $+3.18\%$. Most of the
output advantage is therefore a fiscal-stance effect rather than a return to
the attribution machinery, which is the central claim the framework needs and
does not establish here.

Fifth, targeted transfers remain the better instrument for near-term
distributional objectives. Arm B3 attains the lowest income Gini at $0.3147$ and
much the lowest poverty rate at $9.95\%$, outcomes that B6c does not approach,
and it does so immediately rather than over decades. The cost is the highest
labour tax of any arm at $0.413$. A fund whose half-life is measured in decades
cannot substitute for transfers within a political cycle: the dividend in B6c
reaches only $0.26\%$ of output after fifty years.

Sixth, arm B4, a flat automation levy recycled into retraining, delivers the
largest gain in labour demand of any arm, at $+8.52\%$ in efficiency units, for
an output cost of only $-0.72\%$. Much of the benefit attributed to the
attribution machinery can be obtained by a simpler instrument coupled to an
active labour-market policy.

\emph{A note on the employment column.} The quantity reported here is aggregate
labour demand measured in \emph{efficiency units}, $\sum_f L_f$. It is not hours
and it is not employment. A worker whose efficiency has been reduced by
displacement contributes less to it while remaining fully employed, and
retraining expenditure raises it directly. The model has no extensive
employment margin --- labour supply is a smooth function of the net-of-tax wage
and no agent is ever unemployed --- so it cannot speak to employment in the
ordinary sense. Table~\ref{tab:employment} reports efficiency units, a headcount
above the displacement floor, and the wage separately.

\input{paper/generated/table_main}
\input{paper/generated/table_ci}
\input{paper/generated/table_revenue_normalised}
\input{paper/generated/table_employment}
\input{paper/generated/table_incidence}
"""

SENSITIVITY = r"""
\subsection{Sensitivity and the Region of Validity}
\label{sec:sensitivity}

The results of Section~\ref{sec:results} are computed at a single point,
$\sigma = 1.5$ and $\gamma = 0.85$. Neither parameter is calibrated, and the
Metrics discussion of Section~\ref{sec:eval} requires that sensitivity to them
be reported. We therefore sweep both.

Table~\ref{tab:sigmagamma} reports arm B6c's output effect across
$\sigma \in \{1.2, 1.5, 2.0, 3.0, 5.0, 8.0\}$ and
$\gamma \in \{0.75, 0.85, 0.95\}$, at ten seeds per cell under common random
numbers.

\textbf{The output advantage is positive in only four of the eighteen cells.}
At $\gamma = 0.85$ it is $+4.78\%$ at $\sigma = 1.2$ and $+3.01\%$ at
$\sigma = 1.5$, but $-2.23\%$ at $\sigma = 2.0$ and $-24.99\%$ at
$\sigma = 8.0$. The sign therefore reverses between $\sigma = 1.5$ and
$\sigma = 2.0$, and the region in which the advantage holds is approximately
$\sigma \lesssim 1.7$ at $\gamma = 0.85$. Since the empirical literature places
the labour--capital elasticity of substitution across a range that comfortably
spans this boundary, \textbf{the result must be read as conditional on a low
elasticity and not as a general property of the instrument}. At
$\gamma = 0.95$, close to constant returns, firm scale becomes explosive and the
model is better regarded as outside its domain of validity than as delivering a
policy result; that row is reported as a boundary diagnostic.

The same sweep clarifies Proposition~\ref{prop:margin}. Arm B6, with full
deduction, shows a small positive output effect almost everywhere in the grid,
which is exactly what a marginally subsidising base predicts. The proposition is
therefore supported by the sweep, while the proposal's headline advantage is
not.

\input{paper/generated/table_sigma_gamma}

\subsection{Fund Stability in the Testbed}
\label{sec:fundstability}

Proposition~\ref{prop:fund} requires $(1-\rho)r^{f} < g$ for the fund-to-output
ratio to converge. The testbed sets $\rho = 0.60$ and $r^{f} = 0.05$, giving
$(1-\rho)r^{f} = 0.0200$, while the model's own realised output growth across
fifty seeds ranges from $0.0147$ to $0.0336$ with a mean of $0.0231$.

\textbf{The condition therefore fails on a substantial minority of runs: 13 of
50 seeds are on a divergent path.} On those runs the fund-to-output ratio has no
finite limit, and the terminal level reported in Table~\ref{tab:results} is a
point on a trajectory rather than a steady state. It should not be compared
with the analytic $f^{*}$ of \eqref{eq:fstar}, and the $71$-year half-life of
Table~\ref{tab:fund} assumes $g = 0.03$, which this testbed does not deliver.
Table~\ref{tab:fund}'s arithmetic is itself correct; the difficulty is the
growth rate at which it is evaluated.

We report this rather than reparameterising to remove it. Selecting $\rho$ or
$r^{f}$ so that the condition holds would make the fund look convergent by
construction and would leave the reader no way to tell how close to the boundary
the design sits. The honest summary is that the fund as calibrated is on the
edge of stability, and that a design intended to run for a century should not
be.
"""

def main() -> int:
    if not TEX.exists():
        raise SystemExit(f"manuscript not found at {TEX}")

    gen = ROOT / "paper" / "generated"
    gen.mkdir(parents=True, exist_ok=True)
    for name, body in TABLE_WRAPPERS.items():
        (gen / name).write_text(body, encoding="utf-8", newline="\n")
        print(f"  wrote paper/generated/{name}")

    text = TEX.read_text(encoding="utf-8")
    if MARKER in text:
        print("\nresults section already revised; nothing to do")
        return 0

    start = text.find(r"\subsection{Results}")
    if start == -1:
        raise SystemExit("REVISION FAILED: could not find the Results subsection")
    end = text.find(r"\section{Discussion", start)
    if end == -1:
        end = text.find(r"\section{", start + 10)
    if end == -1:
        raise SystemExit("REVISION FAILED: could not find the end of the "
                         "Results section")

    replaced = NEW_RESULTS + SENSITIVITY + "\n"
    text = text[:start] + replaced + text[end:]
    TEX.write_text(text, encoding="utf-8", newline="\n")
    print(f"\nreplaced the Results section ({end - start} chars) with the "
          f"post-correction version ({len(replaced)} chars)")
    print("the old section, including its hand-pasted tables and figure "
          "coordinates, is preserved in git at tag v0-audit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
