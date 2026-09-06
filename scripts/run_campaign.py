"""Run a policy-arm campaign and write results plus a manifest.

    python scripts/run_campaign.py --config configs/base.yaml --seeds 50 \
        --out results/raw/main.json

Every run records its git SHA, config hash, environment and output digests, so
a number in the paper can be traced back to the exact state that produced it.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from cdos.config import load_config                       # noqa: E402
from cdos.eval.campaign import aggregate, run_campaign    # noqa: E402
from cdos.model.economy import ARMS                       # noqa: E402
from cdos.utils.manifest import Manifest                  # noqa: E402

DEFAULT_ARMS = ("B0", "B1", "B2", "B3", "B4", "B5", "B6", "B6c",
                "B7", "B8", "B9", "B10", "B11", "B12")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config", default=str(ROOT / "configs" / "base.yaml"))
    ap.add_argument("--arms", nargs="*", default=list(DEFAULT_ARMS))
    ap.add_argument("--seeds", type=int, default=50)
    ap.add_argument("--baseline", default="B0")
    ap.add_argument("--processes", type=int, default=None)
    ap.add_argument("--out", default=str(ROOT / "results" / "raw" / "main.json"))
    ap.add_argument("--experiment-id", default="main")
    ap.add_argument("--set", nargs="*", default=[],
                    help="dotted overrides, e.g. technology.sigma=2.0")
    args = ap.parse_args(argv)

    overrides = {}
    for item in args.set:
        key, _, value = item.partition("=")
        overrides[key] = json.loads(value) if value[:1] in "0123456789-[{\"tfn" \
            else value
    cfg = load_config(args.config, overrides or None)

    seeds = list(range(args.seeds))
    manifest = Manifest.start(args.experiment_id,
                              description=f"campaign over {len(args.arms)} arms",
                              config_hash=cfg.hash(), config=cfg.to_dict(),
                              seeds=seeds, arms=list(args.arms))
    manifest.add_input(args.config)

    print(f"running {len(args.arms)} arms x {len(seeds)} seeds "
          f"(config {cfg.hash()})", flush=True)
    results = run_campaign(cfg, args.arms, seeds, args.processes)
    agg = aggregate(results, args.arms, seeds, args.baseline)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(agg, fh, indent=1, sort_keys=True, allow_nan=True)
        fh.write("\n")

    raw = out.with_name(out.stem + "_runs.json")
    with open(raw, "w", encoding="utf-8", newline="\n") as fh:
        json.dump([{k: v for k, v in r.items()
                    if k not in ("path", "accounts")} for r in results],
                  fh, indent=1, sort_keys=True)
        fh.write("\n")

    manifest.add_output(out)
    manifest.add_output(raw)
    manifest.finish().write(
        ROOT / "results" / "manifests" / f"{args.experiment_id}.json")

    _print_table(agg, args.arms, args.baseline)
    print(f"\nwrote {out}\n      {raw}")
    return 0


def _print_table(agg, arms, baseline) -> None:
    print(f"\n{'arm':<5} {'dGDP%':>8} {'dEffU%':>8} {'ws_end':>8} {'Gini_i':>8} "
          f"{'tau_L':>7} {'Fund/Y':>7} {'SAC%Y':>7} {'Rev/DWL':>8} {'stab':>7}")
    for a in arms:
        g, pr = agg[a], agg[a]["_paired"]
        print(f"{a:<5} {pr['Y']['pct']:>8.2f} {pr['eff_units']['pct']:>8.2f} "
              f"{g['ws_end']['mean']:>8.4f} {g['gi']['mean']:>8.4f} "
              f"{g['taul']['mean']:>7.4f} {g['fund']['mean']:>7.3f} "
              f"{100 * g['sac']['mean']:>7.3f} "
              f"{g['revenue_per_dwl']['mean']:>8.3f} "
              f"{g['stability_margin']['mean']:>7.4f}")


if __name__ == "__main__":
    raise SystemExit(main())
