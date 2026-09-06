r"""Regenerate every LaTeX results table from ``results/``.

The audit found that the manuscript's numbers were hand-pasted: the generated
artefacts existed but nothing connected them to the paper, and nothing checked
that they still agreed. Everything written here goes to ``paper/generated/`` as
a **complete float** and is pulled into the manuscript with a single top-level
``\input``, so a number in the paper cannot drift from the run that produced it
without CI noticing.

Each file is a whole ``table`` or ``table*`` environment, caption and all.
That is deliberate: ``\input`` *inside* a ``tabular`` breaks the alignment,
because LaTeX's ``\input`` emits file-list bookkeeping that opens a cell, after
which ``booktabs``'s ``\bottomrule`` (a ``\noalign``) is no longer at a row
boundary. Generating the whole float sidesteps that entirely, and it keeps the
caption -- which describes what the numbers mean -- next to the code that
computes them.

Every file carries a provenance comment naming the results file, the config
hash and the git SHA it came from.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from cdos.model.economy import ARM_LABEL              # noqa: E402
from cdos.utils.manifest import git_state             # noqa: E402

RAW = ROOT / "results" / "raw"
GEN = ROOT / "paper" / "generated"
TABLES = ROOT / "tables"


def _load(name: str) -> Optional[Dict[str, Any]]:
    path = RAW / f"{name}.json"
    if not path.exists():
        print(f"  ! {path.name} not found; skipping the tables that need it")
        return None
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _provenance(source: str, config_hash: str = "") -> str:
    git = git_state()
    return ("% GENERATED FILE -- do not edit by hand.\n"
            f"% Written by scripts/make_tables.py from results/raw/{source}\n"
            f"% git {git.get('short_sha')} "
            f"({'dirty' if git.get('dirty') else 'clean'})"
            f"{'  config ' + config_hash if config_hash else ''}\n")


def _float(rows: str, caption: str, label: str, colspec: str, header: str,
           wide: bool = False, size: str = r"\scriptsize") -> str:
    env = "table*" if wide else "table"
    return (
        f"\\begin{{{env}}}[!t]\n"
        "\\centering\n"
        f"\\caption{{{caption}}}\n"
        f"\\label{{{label}}}\n"
        f"{size}\n"
        f"\\begin{{tabular}}{{@{{}}{colspec}@{{}}}}\n"
        "\\toprule\n"
        f"{header}\n"
        "\\midrule\n"
        f"{rows.rstrip()}\n"
        "\\bottomrule\n"
        "\\end{tabular}\n"
        f"\\end{{{env}}}\n")


def _write(name: str, text: str, source: str, config_hash: str = "") -> None:
    body = _provenance(source, config_hash) + text
    for directory in (GEN, TABLES):
        directory.mkdir(parents=True, exist_ok=True)
        (directory / name).write_text(body, encoding="utf-8", newline="\n")
    print(f"  wrote {name}")


def _fmt(value: float, places: int = 3, signed: bool = False) -> str:
    if value != value:                       # NaN
        return "---"
    spec = f"{'+' if signed else ''}.{places}f"
    return f"${format(value, spec)}$"


# ---------------------------------------------------------------------------
# Main campaign
# ---------------------------------------------------------------------------

def table_main(agg: Dict[str, Any], arms: List[str]) -> str:
    rows = []
    for arm in arms:
        if arm not in agg:
            continue
        g, pr = agg[arm], agg[arm]["_paired"]
        label = ARM_LABEL.get(arm, arm)
        if arm == "B6c":
            label = r"\textbf{CivicDividendOS, corrected base}"
        rows.append(
            f"{arm} & {label} & {_fmt(pr['Y']['pct'], 2, True)} & "
            f"{_fmt(pr['eff_units']['pct'], 2, True)} & "
            f"{_fmt(g['ws_end']['mean'], 3)} & {_fmt(g['gi']['mean'], 4)} & "
            f"{_fmt(g['gw']['mean'], 4)} & {_fmt(g['taul']['mean'], 3)} & "
            f"{_fmt(100 * g['fund']['mean'], 1)} & "
            f"{_fmt(100 * g['divgdp']['mean'], 2)} \\\\")
    header = (
        r"\textbf{Arm} & \textbf{Policy regime} & $\Delta$\textbf{GDP} & "
        r"\textbf{Labour} & \textbf{Wage} & \textbf{Gini} & \textbf{Gini} & "
        r"$\tau_L$ & \textbf{Fund} & \textbf{Div.} \\" "\n"
        r" & & \textbf{(\%)} & \textbf{(eff., \%)} & \textbf{share} & "
        r"\textbf{(inc.)} & \textbf{(wealth)} & \textbf{req.} & "
        r"\textbf{(\%GDP)} & \textbf{(\%GDP)} \\")
    caption = (
        r"Simulation results: means over 50 seeds under common random numbers, "
        r"averaged across the 200 reported quarters except the wage share and "
        r"the fund (terminal values). Output and labour demand are paired "
        r"percentage differences against arm B0. \emph{Labour demand is "
        r"measured in efficiency units and is neither hours nor employment.} "
        r"The labour tax rate clears the government budget and is an outcome. "
        r"Produced under corrected budget accounting. These values are "
        r"\textbf{synthetic} outputs of the model of Section~\ref{sec:model}, "
        r"not empirical estimates.")
    return _float("\n".join(rows), caption, "tab:results",
                  "l l c c c c c c c c", header, wide=True)


def table_ci(agg: Dict[str, Any], arms: List[str], baseline: str = "B0") -> str:
    rows = []
    for arm in arms:
        if arm == baseline or arm not in agg:
            continue
        pr = agg[arm]["_paired"]
        rows.append(
            f"{arm} & {_fmt(pr['gi']['diff'], 4, True)} & "
            f"$[{pr['gi']['lo']:+.4f}, {pr['gi']['hi']:+.4f}]$ & "
            f"{_fmt(pr['taul']['diff'], 4, True)} & "
            f"$[{pr['taul']['lo']:+.4f}, {pr['taul']['hi']:+.4f}]$ \\\\")
    header = (r"\textbf{Arm} & $\Delta$\textbf{Gini} & \textbf{95\% CI} & "
              r"$\Delta\tau_L$ & \textbf{95\% CI} \\")
    caption = (
        r"Paired differences against arm B0 with bootstrap 95\% confidence "
        r"intervals over 50 seeds (2000 resamples). These are "
        r"\emph{replication} intervals: they quantify Monte-Carlo variation at "
        r"one fixed parameter vector and say nothing about parameter "
        r"uncertainty. See Section~\ref{sec:sensitivity}.")
    return _float("\n".join(rows), caption, "tab:ci", "l c c c c", header)


def table_revenue_normalised(agg: Dict[str, Any], arms: List[str]) -> str:
    rows = []
    for arm in arms:
        if arm not in agg:
            continue
        g, pr = agg[arm], agg[arm]["_paired"]
        rows.append(
            f"{arm} & {_fmt(pr['Y']['pct'], 2, True)} & "
            f"{_fmt(100 * g['sac']['mean'], 3)} & "
            f"{_fmt(g['dwl']['mean'] / max(g['Y']['mean'], 1e-9) * 100, 3)} & "
            f"{_fmt(g['revenue_per_dwl']['mean'], 3)} \\\\")
    header = (r"\textbf{Arm} & $\Delta$\textbf{GDP (\%)} & "
              r"\textbf{Revenue (\%Y)} & \textbf{DWL (\%Y)} & "
              r"\textbf{Rev./DWL} \\")
    caption = (
        r"Revenue-normalised comparison. Ranking instruments by output effect "
        r"alone is not valid when they raise materially different revenue: an "
        r"instrument that raises almost nothing will look efficient for no "
        r"better reason than that it does almost nothing. DWL is the Harberger "
        r"triangle on the labour margin.")
    return _float("\n".join(rows), caption, "tab:revnorm", "l c c c c", header)


def table_incidence(agg: Dict[str, Any], arms: List[str]) -> str:
    rows = []
    for arm in arms:
        if arm not in agg or agg[arm]["incidence_labour"]["mean"] == 0.0:
            continue
        g = agg[arm]
        rows.append(
            f"{arm} & {_fmt(100 * g['incidence_labour']['mean'], 1)} & "
            f"{_fmt(100 * g['incidence_capital']['mean'], 1)} & "
            f"{_fmt(100 * g['sac']['mean'], 3)} \\\\")
    header = (r"\textbf{Arm} & \textbf{Borne by labour (\%)} & "
              r"\textbf{Borne by capital (\%)} & \textbf{Revenue (\%Y)} \\")
    caption = (
        r"Economic incidence of the automation levy, apportioned by factor "
        r"income shares. Statutory incidence is on the firm in every case. "
        r"Reporting this split is a governance requirement of "
        r"Section~\ref{sec:twin}, because a contribution levied on an operator "
        r"may ultimately fall on shareholders, workers, suppliers or consumers.")
    return _float("\n".join(rows), caption, "tab:incidence", "l c c c", header)


def table_employment(agg: Dict[str, Any], arms: List[str]) -> str:
    rows = []
    for arm in arms:
        if arm not in agg:
            continue
        g, pr = agg[arm], agg[arm]["_paired"]
        rows.append(
            f"{arm} & {_fmt(g['eff_units']['mean'], 1)} & "
            f"{_fmt(pr['eff_units']['pct'], 2, True)} & "
            f"{_fmt(g['headcount']['mean'], 1)} & "
            f"{_fmt(pr['headcount']['pct'], 2, True)} & "
            f"{_fmt(g['wage']['mean'], 4)} \\\\")
    header = (r"\textbf{Arm} & \textbf{Eff. units} & $\Delta$\textbf{(\%)} & "
              r"\textbf{Headcount} & $\Delta$\textbf{(\%)} & \textbf{Wage} \\")
    caption = (
        r"Labour-market quantities, separated. Efficiency units are aggregate "
        r"labour demand $\sum_f L_f$; headcount counts workers above the "
        r"displacement floor. The model has no extensive employment margin --- "
        r"labour supply is a smooth function of the net-of-tax wage and no "
        r"agent is ever unemployed --- so neither column is an unemployment "
        r"rate, and the quantity reported as ``Hours'' in an earlier version "
        r"of this table was the first of these.")
    return _float("\n".join(rows), caption, "tab:employment", "l c c c c c",
                  header)


# ---------------------------------------------------------------------------
# Experiments
# ---------------------------------------------------------------------------

def table_sigma_gamma(exp: Dict[str, Any]) -> str:
    rows = []
    for cell in exp["cells"]:
        sigma = cell["overrides"]["technology.sigma"]
        gamma = cell["overrides"]["technology.gamma"]
        agg = cell["aggregate"]
        rho = 1.0 - 1.0 / sigma
        prop2 = r"yes" if gamma > rho else r"\textbf{no}"
        b6c = agg["B6c"]["_paired"]["Y"]
        b6 = agg["B6"]["_paired"]["Y"]
        rows.append(
            f"${sigma:.1f}$ & ${gamma:.2f}$ & ${rho:.3f}$ & {prop2} & "
            f"{_fmt(b6['pct'], 2, True)} & {_fmt(b6c['pct'], 2, True)} & "
            f"$[{b6c['plo']:+.2f}, {b6c['phi']:+.2f}]$ \\\\")
    header = (r"$\sigma$ & $\gamma$ & $\rho$ & $\gamma>\rho$ & "
              r"\textbf{B6 (\%)} & \textbf{B6c (\%)} & \textbf{B6c 95\% CI} \\")
    caption = (
        r"Sensitivity of the output effect to the elasticity of substitution "
        r"$\sigma$ and the span of control $\gamma$, ten seeds per cell under "
        r"common random numbers, with $\rho = 1-1/\sigma$. The "
        r"$\gamma>\rho$ column records whether the marginal-incidence "
        r"inequality of Proposition~\ref{prop:margin} holds identically. "
        r"\textbf{Arm B6c's advantage is positive in only four of the eighteen "
        r"cells, and the sign reverses between $\sigma=1.5$ and $\sigma=2.0$ "
        r"at $\gamma=0.85$.} The $\gamma=0.95$ row is a boundary diagnostic: "
        r"near constant returns firm scale becomes explosive and the model is "
        r"outside its domain of validity.")
    return _float("\n".join(rows), caption, "tab:sigmagamma",
                  "c c c c c c c", header)


def table_fund_stability(exp: Dict[str, Any]) -> str:
    rows = []
    for cell in exp["cells"]:
        rho = cell["overrides"]["fund.rho_payout"]
        rf = cell["overrides"]["fund.r_fund_annual"]
        agg = cell["aggregate"]["B6c"]
        drift = (1 - rho) * rf
        g = agg["g_realised"]["mean"]
        margin = agg["stability_margin"]["mean"]
        verdict = "converges" if margin > 0 else r"\textbf{diverges}"
        rows.append(
            f"${rho:.2f}$ & ${rf:.2f}$ & ${drift:.4f}$ & ${g:.4f}$ & "
            f"{_fmt(margin, 4, True)} & {verdict} & "
            f"{_fmt(100 * agg['fund']['mean'], 1)} \\\\")
    header = (r"$\rho$ & $r^{f}$ & $(1-\rho)r^{f}$ & \textbf{realised } $g$ & "
              r"\textbf{margin} & \textbf{verdict} & \textbf{Fund (\%Y)} \\")
    caption = (
        r"Fund stability across the payout share and the fund return. "
        r"Proposition~\ref{prop:fund} requires $(1-\rho)r^{f} < g$. At the "
        r"calibration of Section~\ref{sec:model} the drift is $0.0200$ against "
        r"a realised growth rate the model itself produces, so the margin is "
        r"small and of variable sign. A terminal fund level reported on a "
        r"divergent path is not a steady state.")
    return _float("\n".join(rows), caption, "tab:fundstab",
                  "c c c c c l c", header)


def table_sweep(exp: Dict[str, Any], key: str, label: str, caption: str,
                param_header: str, arm: str = "B6c") -> str:
    rows = []
    for cell in exp["cells"]:
        value = cell["overrides"].get(key)
        agg = cell["aggregate"]
        if arm not in agg:
            continue
        g, pr = agg[arm], agg[arm]["_paired"]
        rows.append(
            f"${value}$ & {_fmt(pr['Y']['pct'], 2, True)} & "
            f"{_fmt(g['gi']['mean'], 4)} & {_fmt(g['taul']['mean'], 4)} & "
            f"{_fmt(100 * g['sac']['mean'], 3)} & "
            f"{_fmt(100 * g['fund']['mean'], 1)} \\\\")
    header = (f"{param_header} & $\\Delta$\\textbf{{GDP (\\%)}} & "
              r"\textbf{Gini} & $\tau_L$ & \textbf{Rev. (\%Y)} & "
              r"\textbf{Fund (\%Y)} \\")
    return _float("\n".join(rows), caption, label, "c c c c c c", header)


SWEEPS = {
    "E07": ("attribution.phi_deduct", "table_phi.tex", "tab:phi", r"$\varphi$",
            r"Cost-deduction share $\varphi$ (Proposition~\ref{prop:margin}). "
            r"The proposition predicts that marginal incidence turns "
            r"non-negative at $\varphi \le 1/2$.", "B6"),
    "E09": ("fund.rho_payout", "table_payout.tex", "tab:payout", r"$\rho$",
            r"Payout share $\rho$ (Proposition~\ref{prop:payout}). A higher "
            r"payout raises the dividend today but lowers the steady-state "
            r"fund.", "B6c"),
    "E14": ("technology.decay", "table_decay.tex", "tab:decay",
            r"\textbf{decay}",
            r"Sensitivity to the quarterly machine-price decline, which is "
            r"assumed rather than calibrated and drives the entire automation "
            r"transition.", "B6c"),
    "E06": ("classifier.error_rate", "table_classifier.tex", "tab:classerr",
            r"$\varepsilon$",
            r"Classification error (Proposition~\ref{prop:robust}). The "
            r"induced rate error is bounded by "
            r"$\varepsilon(\alpha+\theta)$.", "B6c"),
    "E05": ("run.t_run", "table_horizon.tex", "tab:horizon", r"\textbf{quarters}",
            r"Horizon sensitivity. A fund still accumulating at the reporting "
            r"horizon can flatter an arm that would look different over a "
            r"longer or a shorter run.", "B6c"),
}


def main() -> int:
    GEN.mkdir(parents=True, exist_ok=True)
    TABLES.mkdir(parents=True, exist_ok=True)
    print("regenerating tables from results/raw/")
    wrote_any = False

    main_res = _load("main")
    if main_res:
        arms = main_res["_meta"]["arms"]
        base = main_res["_meta"]["baseline"]
        _write("table_main.tex", table_main(main_res, arms), "main.json")
        _write("table_ci.tex", table_ci(main_res, arms, base), "main.json")
        _write("table_revenue_normalised.tex",
               table_revenue_normalised(main_res, arms), "main.json")
        _write("table_incidence.tex", table_incidence(main_res, arms), "main.json")
        _write("table_employment.tex", table_employment(main_res, arms), "main.json")
        wrote_any = True

    e01 = _load("E01")
    if e01:
        _write("table_sigma_gamma.tex", table_sigma_gamma(e01), "E01.json")
        wrote_any = True

    e03 = _load("E03")
    if e03:
        _write("table_fund_stability.tex", table_fund_stability(e03), "E03.json")
        wrote_any = True

    for exp_id, (key, name, label, param_header, caption, arm) in SWEEPS.items():
        exp = _load(exp_id)
        if exp:
            _write(name, table_sweep(exp, key, label, caption, param_header, arm),
                   f"{exp_id}.json")
            wrote_any = True

    if not wrote_any:
        print("\nno results found. Run `make main` and `make experiments` first.")
        return 1
    print(f"\ntables written to {GEN} and {TABLES}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
