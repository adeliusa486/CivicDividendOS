"""Emit LaTeX blocks (results table, CI table, results figure) from results.json."""
import json, io
from cdos_sim import ARMS, ARM_LABEL
from cdos_sim import run

B = chr(92)          # backslash, kept out of literals for safe round-tripping
agg = json.load(open("results.json"))

NAME = {
    "B0": "Existing labour/capital tax system",
    "B1": "Fixed robot tax",
    "B2": "Broad capital-income tax increase",
    "B3": "UBI via general taxation",
    "B4": "Automation tax plus retraining",
    "B5": "Public wealth fund, no factor-origin tax",
    "B6": "CivicDividendOS, base as specified",
    "B6c": "CivicDividendOS, corrected base",
}

# ---------------- results table ----------------
rows = []
for a in ARMS:
    g = agg[a]; pr = g["_paired"]
    nm = NAME[a]
    if a == "B6c":
        nm = B + "textbf{" + nm + "}"
    rows.append(
        "%s & %s & $%+.2f$ & $%+.2f$ & $%.3f$ & $%.4f$ & $%.4f$ & $%.3f$ & $%.3f$ & $%.1f$ & $%.2f$ %s%s"
        % (a, nm, pr["Y"]["pct"], pr["hours"]["pct"], g["ws_end"]["mean"],
           g["gi"]["mean"], g["gw"]["mean"], g["pov"]["mean"], g["taul"]["mean"],
           100 * g["fund"]["mean"], 100 * g["divgdp"]["mean"], B, B))

tbl = [
    B + "begin{table*}[!t]", B + "centering",
    B + "caption{Simulation results: means over 50 seeds under common random numbers, "
    "averaged across the 200 reported quarters except the wage share (terminal value) "
    "and the fund (terminal value). Output and hours are paired percentage differences "
    "against arm B0. The labour tax rate clears the government budget in every arm and "
    "is therefore an outcome. Bootstrap 95\\% confidence intervals for the two key "
    "contrasts are given in Table~" + B + "ref{tab:ci}. These are outputs of the model of "
    "Section~" + B + "ref{sec:model}, not empirical estimates.}",
    B + "label{tab:results}", B + "footnotesize",
    B + "begin{tabular}{@{}l l c c c c c c c c c@{}}", B + "toprule",
    B + "textbf{Arm} & " + B + "textbf{Policy regime} & $" + B + "Delta$" + B + "textbf{GDP} & "
    + B + "textbf{Hours} & " + B + "textbf{Wage} & " + B + "textbf{Gini} & " + B + "textbf{Gini} & "
    + B + "textbf{Pov.} & $" + B + "tau_L$ & " + B + "textbf{Fund} & " + B + "textbf{Div.} " + B + B,
    " & & " + B + "textbf{(" + B + "%)} & " + B + "textbf{(" + B + "%)} & " + B + "textbf{share} & "
    + B + "textbf{(inc.)} & " + B + "textbf{(wealth)} & " + B + "textbf{rate} & "
    + B + "textbf{req.} & " + B + "textbf{(" + B + "% GDP)} & " + B + "textbf{(" + B + "% GDP)} " + B + B,
    B + "midrule",
] + rows + [B + "bottomrule", B + "end{tabular}", B + "end{table*}"]
io.open("results_table.tex", "w", newline="\n").write("\n".join(tbl) + "\n")

# ---------------- CI table ----------------
ci = []
for a in ARMS[1:]:
    pr = agg[a]["_paired"]
    ci.append("%s & $%+.4f$ & $[%+.4f, %+.4f]$ & $%+.4f$ & $[%+.4f, %+.4f]$ %s%s"
              % (a, pr["gi"]["diff"], pr["gi"]["lo"], pr["gi"]["hi"],
                 pr["taul"]["diff"], pr["taul"]["lo"], pr["taul"]["hi"], B, B))
cit = [
    B + "begin{table}[!t]", B + "centering",
    B + "caption{Paired differences against arm B0 with bootstrap 95" + B + "% confidence "
    "intervals over 50 seeds (2000 resamples). Negative Gini differences indicate lower "
    "inequality; negative labour-tax differences indicate that the arm finances the same "
    "public spending at a lower tax on work.}",
    B + "label{tab:ci}", B + "footnotesize",
    B + "begin{tabular}{@{}l c c c c@{}}", B + "toprule",
    B + "textbf{Arm} & $" + B + "Delta$" + B + "textbf{Gini} & " + B + "textbf{95" + B + "% CI} & $"
    + B + "Delta" + B + "tau_L$ & " + B + "textbf{95" + B + "% CI} " + B + B,
    B + "midrule",
] + ci + [B + "bottomrule", B + "end{tabular}", B + "end{table}"]
io.open("ci_table.tex", "w", newline="\n").write("\n".join(cit) + "\n")

# ---------------- results figure ----------------
sel = ["B0", "B1", "B3", "B6c"]
paths = {a: run(0, a, collect_path=True)["path"] for a in sel}
lines = []
for a in sel:
    pts = paths[a][::10]
    coords = " ".join("(%.2f,%.4f)" % (q[0] / 4.0, q[2]) for q in pts)
    lines.append((a, coords))

fig = [
    B + "begin{figure}[!t]", B + "centering", B + "begin{tikzpicture}",
    B + "begin{axis}[",
    "  width=0.94" + B + "columnwidth, height=5.6cm,",
    "  xlabel={Year}, ylabel={Labour share of value added},",
    "  xmin=0, xmax=50, ymin=0.25, ymax=0.80,",
    "  grid=major, grid style={black!12},",
    "  legend pos=south west, legend cell align=left,",
    "  legend style={font=" + B + "scriptsize, draw=black!30},",
    "  label style={font=" + B + "small}, tick label style={font=" + B + "scriptsize},",
    "  every axis plot/.append style={very thick, mark=none}",
    "]",
]
for a, coords in lines:
    fig.append(B + "addplot coordinates {" + coords + "};")
    fig.append(B + "addlegendentry{" + a + ": " + NAME[a].split(",")[0] + "}")
fig += [
    B + "end{axis}", B + "end{tikzpicture}",
    B + "caption{Labour share of value added over the 50-year horizon (seed 0). The "
    "machine price falls throughout, so the labour share declines in every arm. Arms that "
    "raise the effective cost of automation at the margin (B1, B6c) slow the decline; the "
    "UBI arm (B3) redistributes income but does not alter the factor allocation, so its "
    "path is indistinguishable from the baseline.}",
    B + "label{fig:results}", B + "end{figure}",
]
io.open("results_fig.tex", "w", newline="\n").write("\n".join(fig) + "\n")

print("wrote results_table.tex, ci_table.tex, results_fig.tex")
for f in ("results_table.tex", "ci_table.tex", "results_fig.tex"):
    print(" ", f, len(io.open(f, encoding="utf-8").read()), "chars")
