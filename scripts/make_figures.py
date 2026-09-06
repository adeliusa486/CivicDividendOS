"""Regenerate every figure from ``results/``.

Writes PDF (for the manuscript) and PGF-style ``.dat`` coordinate files (for the
pgfplots figures already in the manuscript), so that both figure paths are fed
from the same results rather than from anything typed by hand.

Matplotlib is optional: without it the ``.dat`` files are still produced, which
is what the manuscript's pgfplots figures actually consume.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from cdos.config import load_config                   # noqa: E402
from cdos.model.economy import run                    # noqa: E402

RAW = ROOT / "results" / "raw"
FIG = ROOT / "figures"
GEN = ROOT / "paper" / "generated"

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    HAVE_MPL = True
except ImportError:                                    # pragma: no cover
    HAVE_MPL = False


def _load(name: str) -> Optional[Dict[str, Any]]:
    path = RAW / f"{name}.json"
    if not path.exists():
        print(f"  ! {path.name} not found; skipping its figures")
        return None
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _write_dat(name: str, points) -> None:
    coords = " ".join(f"({x:.4f},{y:.4f})" for x, y in points)
    for directory in (FIG, GEN):
        directory.mkdir(parents=True, exist_ok=True)
        (directory / name).write_text(coords + "\n", encoding="utf-8", newline="\n")


def _save(fig, name: str) -> None:
    FIG.mkdir(parents=True, exist_ok=True)
    GEN.mkdir(parents=True, exist_ok=True)
    for directory in (FIG, GEN):
        fig.savefig(directory / name, bbox_inches="tight")
    plt.close(fig)
    print(f"  wrote {name}")


# ---------------------------------------------------------------------------
# Time paths
# ---------------------------------------------------------------------------

def figure_paths(arms=("B0", "B1", "B3", "B6c")) -> None:
    """Wage-share and labour-tax paths, seed 0, from the corrected model."""
    cfg = load_config(ROOT / "configs" / "base.yaml")
    cfg.run.collect_path = True
    cfg.numerics.strict_accounting = True
    paths = {}
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        for arm in arms:
            paths[arm] = run(cfg, seed=0, arm=arm)["path"]

    for arm in arms:
        pts = paths[arm][::8]
        _write_dat(f"fig_ws_{arm}.dat", [(q[0] / 4.0, q[2]) for q in pts])
        _write_dat(f"fig_taul_{arm}.dat", [(q[0] / 4.0, q[5]) for q in pts])
        _write_dat(f"fig_fund_{arm}.dat", [(q[0] / 4.0, q[4]) for q in pts])
    with open(GEN / "fig_paths.json", "w", encoding="utf-8", newline="\n") as fh:
        json.dump(paths, fh)
    print("  wrote fig_ws_*.dat, fig_taul_*.dat, fig_fund_*.dat, fig_paths.json")

    if not HAVE_MPL:
        return
    fig, axes = plt.subplots(1, 3, figsize=(13, 3.6))
    for arm in arms:
        p = np.array(paths[arm], dtype=float)
        axes[0].plot(p[:, 0] / 4.0, p[:, 2], label=arm)
        axes[1].plot(p[:, 0] / 4.0, p[:, 5], label=arm)
        axes[2].plot(p[:, 0] / 4.0, p[:, 4], label=arm)
    for ax, title, ylabel in zip(
            axes, ("Wage share", "Labour tax rate", "Fund / annual output"),
            ("$wL/Y$", r"$\tau_L$", "$F/4Y$")):
        ax.set_title(title)
        ax.set_xlabel("year")
        ax.set_ylabel(ylabel)
        ax.grid(alpha=0.3)
    axes[0].legend(frameon=False, fontsize=8)
    _save(fig, "fig_paths.pdf")


# ---------------------------------------------------------------------------
# E01: the sigma-gamma validity region (audit F1)
# ---------------------------------------------------------------------------

def figure_sigma_gamma() -> None:
    exp = _load("E01")
    if exp is None:
        return
    sigmas = sorted({c["overrides"]["technology.sigma"] for c in exp["cells"]})
    gammas = sorted({c["overrides"]["technology.gamma"] for c in exp["cells"]})
    grid = np.full((len(gammas), len(sigmas)), np.nan)
    for cell in exp["cells"]:
        i = gammas.index(cell["overrides"]["technology.gamma"])
        j = sigmas.index(cell["overrides"]["technology.sigma"])
        grid[i, j] = cell["aggregate"]["B6c"]["_paired"]["Y"]["pct"]

    _write_dat("fig_sigma_boundary.dat",
               [(s, 1.0 / (1.0 - g) if (g := 0.0) else 0.0) for s in sigmas])
    rows = []
    for i, g in enumerate(gammas):
        for j, s in enumerate(sigmas):
            rows.append(f"{s} {g} {grid[i, j]:.4f}")
    (GEN / "fig_sigma_gamma.dat").write_text("\n".join(rows) + "\n",
                                             encoding="utf-8", newline="\n")
    print("  wrote fig_sigma_gamma.dat")

    if not HAVE_MPL:
        return
    fig, ax = plt.subplots(figsize=(7.0, 3.6))
    vmax = float(np.nanmax(np.abs(grid)))
    im = ax.imshow(grid, cmap="RdBu_r", vmin=-vmax, vmax=vmax,
                   aspect="auto", origin="lower")
    ax.set_xticks(range(len(sigmas)), [f"{s:g}" for s in sigmas])
    ax.set_yticks(range(len(gammas)), [f"{g:g}" for g in gammas])
    ax.set_xlabel(r"elasticity of substitution $\sigma$")
    ax.set_ylabel(r"span of control $\gamma$")
    ax.set_title("B6c output effect vs B0 (%), by calibration")
    for i in range(len(gammas)):
        for j in range(len(sigmas)):
            if np.isfinite(grid[i, j]):
                ax.text(j, i, f"{grid[i, j]:+.1f}", ha="center", va="center",
                        fontsize=8,
                        color="white" if abs(grid[i, j]) > 0.6 * vmax else "black")
    fig.colorbar(im, ax=ax, label=r"$\Delta$GDP (\%)")
    _save(fig, "fig_sigma_gamma.pdf")


# ---------------------------------------------------------------------------
# E03: fund stability (audit F2)
# ---------------------------------------------------------------------------

def figure_fund_stability() -> None:
    exp = _load("E03")
    if exp is None or not HAVE_MPL:
        return
    rhos = sorted({c["overrides"]["fund.rho_payout"] for c in exp["cells"]})
    rfs = sorted({c["overrides"]["fund.r_fund_annual"] for c in exp["cells"]})
    grid = np.full((len(rhos), len(rfs)), np.nan)
    for cell in exp["cells"]:
        i = rhos.index(cell["overrides"]["fund.rho_payout"])
        j = rfs.index(cell["overrides"]["fund.r_fund_annual"])
        grid[i, j] = cell["aggregate"]["B6c"]["stability_margin"]["mean"]

    fig, ax = plt.subplots(figsize=(6.4, 3.4))
    vmax = float(np.nanmax(np.abs(grid)))
    im = ax.imshow(grid, cmap="RdBu", vmin=-vmax, vmax=vmax, aspect="auto",
                   origin="lower")
    ax.set_xticks(range(len(rfs)), [f"{v:g}" for v in rfs])
    ax.set_yticks(range(len(rhos)), [f"{v:g}" for v in rhos])
    ax.set_xlabel("fund return $r^f$")
    ax.set_ylabel(r"payout share $\rho$")
    ax.set_title(r"Proposition 6 margin $g-(1-\rho)r^f$; blue diverges")
    for i in range(len(rhos)):
        for j in range(len(rfs)):
            ax.text(j, i, f"{grid[i, j]:+.4f}", ha="center", va="center",
                    fontsize=7)
    fig.colorbar(im, ax=ax)
    _save(fig, "fig_fund_stability.pdf")


# ---------------------------------------------------------------------------
# Rate function (Proposition 3)
# ---------------------------------------------------------------------------

def figure_rate() -> None:
    from cdos.config import RateConfig
    from cdos.model.rate import RATE_TERMS, applied_rate

    cfg = RateConfig()
    for term in RATE_TERMS:
        setattr(cfg, f"source_{term}", "endogenous")
    s_grid = np.linspace(0.0, 1.0, 51)
    series = {}
    for a_aug in (0.0, 0.4, 0.85):
        idx = {"S": s_grid, "C_rent": np.full(51, 0.35),
               "E_disp": np.full(51, 0.48), "X_ext": np.full(51, 0.10),
               "R_rev": np.full(51, 0.55), "A_aug": np.full(51, a_aug),
               "T_train": np.full(51, 0.55), "B_broad": np.full(51, 0.20),
               "N_new": np.full(51, 0.30)}
        series[a_aug] = applied_rate(cfg, 51, idx)
        _write_dat(f"fig_rate_aug{int(a_aug * 100):02d}.dat",
                   list(zip(s_grid, series[a_aug])))

    if not HAVE_MPL:
        return
    fig, ax = plt.subplots(figsize=(6.0, 3.2))
    for a_aug, values in series.items():
        ax.plot(s_grid, values, label=rf"$A^{{\mathrm{{aug}}}}={a_aug}$")
    ax.axhline(cfg.rmin, ls=":", c="grey", lw=0.8)
    ax.axhline(cfg.rmax, ls=":", c="grey", lw=0.8)
    ax.set_xlabel("substitution intensity $S_i$")
    ax.set_ylabel("applied rate $r_i$")
    ax.set_title("Rate function: bounded and monotone (Proposition 3)")
    ax.legend(frameon=False, fontsize=8)
    ax.grid(alpha=0.3)
    _save(fig, "fig_rate.pdf")


def main() -> int:
    print("regenerating figures")
    if not HAVE_MPL:
        print("  (matplotlib not installed: writing .dat files only)")
    figure_rate()
    figure_paths()
    figure_sigma_gamma()
    figure_fund_stability()
    print(f"\nfigures written to {FIG} and {GEN}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
