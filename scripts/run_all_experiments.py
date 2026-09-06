"""Run every experiment matching a pattern, in order, with a status summary.

    python scripts/run_all_experiments.py                # everything
    python scripts/run_all_experiments.py --pattern 'E0*'
    python scripts/run_all_experiments.py --skip E15 E17 --seeds 10

An experiment that fails does not stop the rest; its failure is recorded and
reported at the end, so a long matrix does not have to be restarted from the
beginning. Nothing is marked complete unless it actually wrote its results.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--pattern", default="*")
    ap.add_argument("--skip", nargs="*", default=[])
    ap.add_argument("--seeds", type=int, default=None)
    ap.add_argument("--processes", type=int, default=None)
    ap.add_argument("--continue-on-error", action="store_true", default=True)
    args = ap.parse_args(argv)

    files = sorted((ROOT / "experiments").glob(f"{args.pattern}.yaml"))
    files = [f for f in files
             if not any(f.name.startswith(s) for s in args.skip)]
    if not files:
        print(f"no experiments match {args.pattern!r}")
        return 1

    print(f"running {len(files)} experiment(s)\n")
    status: list[tuple[str, str, float]] = []

    for path in files:
        t0 = time.time()
        cmd = [sys.executable, str(ROOT / "scripts" / "run_experiment.py"), str(path)]
        if args.seeds is not None:
            cmd += ["--seeds", str(args.seeds)]
        if args.processes is not None:
            cmd += ["--processes", str(args.processes)]
        print(f"=== {path.stem} " + "=" * max(0, 60 - len(path.stem)))
        proc = subprocess.run(cmd, cwd=ROOT)
        elapsed = time.time() - t0
        outcome = "ok" if proc.returncode == 0 else f"FAILED (exit {proc.returncode})"
        status.append((path.stem, outcome, elapsed))
        print(f"    {outcome} in {elapsed:.1f}s\n")
        if proc.returncode != 0 and not args.continue_on_error:
            break

    print("=" * 68)
    print(f"{'experiment':<28} {'status':<24} {'seconds':>10}")
    for name, outcome, elapsed in status:
        print(f"{name:<28} {outcome:<24} {elapsed:>10.1f}")
    failed = [s for s in status if s[1] != "ok"]
    total = sum(s[2] for s in status)
    print(f"\n{len(status) - len(failed)}/{len(status)} succeeded "
          f"in {total / 60:.1f} minutes")

    summary = ROOT / "results" / "summaries" / "experiment_status.json"
    summary.parent.mkdir(parents=True, exist_ok=True)
    with open(summary, "w", encoding="utf-8", newline="\n") as fh:
        json.dump([{"experiment": n, "status": o, "seconds": round(e, 1)}
                   for n, o, e in status], fh, indent=1)
        fh.write("\n")
    print(f"wrote {summary}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
