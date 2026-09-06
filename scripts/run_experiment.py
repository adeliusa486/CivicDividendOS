"""Run one experiment from ``experiments/*.yaml`` and write results + manifest.

    python scripts/run_experiment.py experiments/E01_sigma_gamma.yaml

An experiment file carries an ``experiment_id``, a ``sweep`` (a mapping of
dotted config keys to lists of values), the ``arms`` and ``seeds`` to use, and
any configuration overrides. Every cell of the sweep is run under common random
numbers, and the manifest records the git SHA, config hash, environment and
output digests.
"""

from __future__ import annotations

import argparse
import itertools
import json
import sys
import warnings
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from cdos.config import load_experiment  # noqa: E402
from cdos.eval.campaign import aggregate, run_campaign  # noqa: E402
from cdos.utils.manifest import Manifest  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("experiment", help="path to an experiments/*.yaml file")
    ap.add_argument("--out-dir", default=str(ROOT / "results" / "raw"))
    ap.add_argument("--processes", type=int, default=None)
    ap.add_argument("--seeds", type=int, default=None,
                    help="override the seed count in the experiment file")
    args = ap.parse_args(argv)

    spec = load_experiment(args.experiment)
    meta, cfg = spec["meta"], spec["config"]
    exp_id = meta.get("experiment_id") or Path(args.experiment).stem
    arms = meta.get("arms") or ["B0", "B6", "B6c"]
    n_seeds = args.seeds if args.seeds is not None else int(meta.get("seeds", 20))
    seeds = list(range(n_seeds))
    sweep: dict[str, list[Any]] = meta.get("sweep") or {}

    manifest = Manifest.start(
        exp_id, description=meta.get("description", ""),
        config_hash=cfg.hash(), config=cfg.to_dict(), seeds=seeds, arms=arms,
        notes={"sweep": sweep, "source": str(Path(args.experiment).as_posix())})
    manifest.add_input(args.experiment)

    keys = list(sweep)
    combos = list(itertools.product(*(sweep[k] for k in keys))) if keys else [()]
    print(f"[{exp_id}] {len(combos)} cell(s) x {len(arms)} arm(s) x "
          f"{len(seeds)} seed(s) = {len(combos) * len(arms) * len(seeds)} runs",
          flush=True)

    cells: list[dict[str, Any]] = []
    for values in combos:
        overrides = dict(zip(keys, values, strict=False))
        cell_cfg = cfg.with_overrides(overrides) if overrides else cfg
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            results = run_campaign(cell_cfg, arms, seeds, args.processes)
        agg = aggregate(results, arms, seeds, baseline=arms[0])
        cells.append({
            "overrides": overrides,
            "config_hash": cell_cfg.hash(),
            "aggregate": agg,
            "runs": [{k: v for k, v in r.items()
                      if k not in ("path", "accounts")} for r in results],
        })
        label = ", ".join(f"{k}={v}" for k, v in overrides.items()) or "base"
        print(f"  {label:<44s} " + "  ".join(
            f"{a}:{agg[a]['_paired']['Y']['pct']:+6.2f}%" for a in arms[1:]),
            flush=True)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{exp_id}.json"
    with open(out, "w", encoding="utf-8", newline="\n") as fh:
        json.dump({"experiment_id": exp_id, "meta": meta,
                   "config": cfg.to_dict(), "cells": cells},
                  fh, indent=1, sort_keys=True, allow_nan=True)
        fh.write("\n")
    manifest.add_output(out)
    manifest.finish().write(ROOT / "results" / "manifests" / f"{exp_id}.json")
    print(f"[{exp_id}] wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
