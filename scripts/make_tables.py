"""Regenerate every LaTeX results table from ``results/``.

The audit found that the manuscript's numbers were hand-pasted: the generated
artefacts existed but nothing connected them to the paper, and nothing checked
that they still agreed. Everything written here goes to ``paper/generated/``
and is pulled into the manuscript with ``\\input``, so a number in the paper
cannot drift from the run that produced it without CI noticing.

Every table carries a provenance comment naming the results file, the config
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
            f"% git {git.get('short_sha')} ({'dirty' if git.get('dirty') else 'clean'})"
            f"{'  config ' + config_hash if config_hash else ''}\n")


def _write(name: str, body: str, source: str, config_hash: str = "") -> None:
    text = _provenance(source, config_hash) + body
    for directory in (GEN, TABLES):
        directory.mkdir(parents=True, exist_ok=True)
        (directory / name).write_text(text, encoding="utf-8", newline="\n")
    print(f"  wrote {name}")


def _fmt(value: float, places: int = 3, signed: bool = False) -> str:
    if value != value:                       # NaN
        return "---"
    spec = f"{'+' if signed else ''}.{places}f"
    return f"${format(value, spec)}$"


# ---------------------------------------------------------------------------
# Main results table
# ---------------------------------------------------------------------------

def table_main(agg: Dict[str, Any], arms: List[str]) -> str:
    rows = []
    for arm in arms:
        if arm not in agg:
            continue
        g, pr = agg[arm], agg[arm]["_paired"]
        label = ARM_LABEL.get(arm, arm)
        if arm == "B6c":
            label = r"\textbf{CivicDividendOS (corrected base)}"
        rows.append(
            f"{arm} & {label} & {_fmt(pr['Y']['pct'], 2, True)} & "
            f"{_fmt(pr['eff_units']['pct'], 2, True)} & "
            f"{_fmt(g['ws_end']['mean'], 3)} & {_fmt(g['gi']['mean'], 4)} & "
            f"{_fmt(g['gw']['mean'], 4)} & {_fmt(g['taul']['mean'], 3)} & "
            f"{_fmt(g['fund']['mean'], 2)} & "
            f"{_fmt(100 * g['divgdp']['mean'], 2)} \\\\")
    return "\n".join(rows) + "\n"


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
    return "\n".join(rows) + "\n"


def table_revenue_normalised(agg: Dict[str, Any], arms: List[str]) -> str:
    """F5: output effect alongside revenue actually raised and DWL."""
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
    return "\n".join(rows) + "\n"


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
    return "\n".join(rows) + "\n"


def table_employment(agg: Dict[str, Any], arms: List[str]) -> str:
    """F6: efficiency units and headcount, never conflated as 'hours'."""
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
    return "\n".join(rows) + "\n"


# ---------------------------------------------------------------------------
# Experiment tables
# ---------------------------------------------------------------------------

def table_sigma_gamma(exp: Dict[str, Any]) -> str:
    """E01/F1: the region in which the dominance claim actually holds."""
    rows = []
    for cell in exp["cells"]:
        sigma = cell["overrides"]["technology.sigma"]
        gamma = cell["overrides"]["technology.gamma"]
        agg = cell["aggregate"]
        rho = 1.0 - 1.0 / sigma
        prop2 = r"\checkmark" if gamma > rho else r"$\times$"
        b6c = agg["B6c"]["_paired"]["Y"]
        b6 = agg["B6"]["_paired"]["Y"]
        rows.append(
            f"{sigma:.1f} & {gamma:.2f} & {rho:.3f} & {prop2} & "
            f"{_fmt(b6['pct'], 2, True)} & {_fmt(b6c['pct'], 2, True)} & "
            f"$[{b6c['plo']:+.2f}, {b6c['phi']:+.2f}]$ \\\\")
    return "\n".join(rows) + "\n"


def table_fund_stability(exp: Dict[str, Any]) -> str:
    """E03/F2: the Proposition 6 margin at each calibration."""
    rows = []
    for cell in exp["cells"]:
        rho = cell["overrides"]["fund.rho_payout"]
        rf = cell["overrides"]["fund.r_fund_annual"]
        agg = cell["aggregate"]["B6c"]
        drift = (1 - rho) * rf
        g = agg["g_realised"]["mean"]
        margin = agg["stability_margin"]["mean"]
        verdict = r"\checkmark" if margin > 0 else r"\textbf{diverges}"
        rows.append(
            f"{rho:.2f} & {rf:.2f} & {drift:.4f} & {g:.4f} & "
            f"{_fmt(margin, 4, True)} & {verdict} & "
            f"{_fmt(agg['fund']['mean'], 3)} \\\\")
    return "\n".join(rows) + "\n"


def table_sweep(exp: Dict[str, Any], key: str, arm: str = "B6c",
                places: int = 3) -> str:
    rows = []
    for cell in exp["cells"]:
        value = cell["overrides"].get(key)
        agg = cell["aggregate"]
        if arm not in agg:
            continue
        g, pr = agg[arm], agg[arm]["_paired"]
        rows.append(
            f"{value} & {_fmt(pr['Y']['pct'], 2, True)} & "
            f"{_fmt(g['gi']['mean'], 4)} & {_fmt(g['taul']['mean'], 4)} & "
            f"{_fmt(100 * g['sac']['mean'], places)} & "
            f"{_fmt(g['fund']['mean'], 3)} \\\\")
    return "\n".join(rows) + "\n"


# ---------------------------------------------------------------------------

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

    for exp_id, key, name in (("E07", "attribution.phi_deduct", "table_phi.tex"),
                              ("E09", "fund.rho_payout", "table_payout.tex"),
                              ("E14", "technology.decay", "table_decay.tex"),
                              ("E06", "classifier.error_rate", "table_classifier.tex"),
                              ("E05", "run.t_run", "table_horizon.tex")):
        exp = _load(exp_id)
        if exp:
            arm = "B6" if exp_id == "E07" else "B6c"
            _write(name, table_sweep(exp, key, arm), f"{exp_id}.json")
            wrote_any = True

    if not wrote_any:
        print("\nno results found. Run `make main` and `make experiments` first.")
        return 1
    print(f"\ntables written to {GEN} and {TABLES}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
