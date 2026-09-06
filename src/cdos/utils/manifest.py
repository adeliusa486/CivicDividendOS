"""Run manifests: what was run, with what, on what, and what came out.

Every experiment writes one of these next to its results. The audited project
recorded none, which is why the reproduction check had to reconstruct the
provenance of ``results.json`` from the source rather than read it.

A manifest records the experiment identity, the git SHA and dirty state, the
configuration hash and the full configuration, the interpreter and package
versions, the machine, the seeds, the wall-clock runtime, and a SHA-256 of every
input and output file. Nothing in it is typed by hand.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import subprocess
import sys
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

__all__ = ["Manifest", "file_digest", "git_state", "environment_state",
           "write_manifest"]

_TRACKED_PACKAGES = ("numpy", "scipy", "pandas", "matplotlib", "pyyaml", "pytest")


def file_digest(path: Path | str, chunk: int = 1 << 20) -> str:
    """SHA-256 of a file's bytes."""
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        while True:
            block = fh.read(chunk)
            if not block:
                break
            h.update(block)
    return h.hexdigest()


def git_state(root: Optional[Path] = None) -> Dict[str, Any]:
    """Current commit, branch and whether the tree is dirty."""
    root = Path(root or Path(__file__).resolve().parents[3])

    def _run(*args: str) -> Optional[str]:
        try:
            out = subprocess.run(("git", *args), cwd=root, capture_output=True,
                                 text=True, timeout=15)
        except (OSError, subprocess.SubprocessError):
            return None
        return out.stdout.strip() if out.returncode == 0 else None

    status = _run("status", "--porcelain")
    return {
        "sha": _run("rev-parse", "HEAD"),
        "short_sha": _run("rev-parse", "--short", "HEAD"),
        "branch": _run("rev-parse", "--abbrev-ref", "HEAD"),
        "describe": _run("describe", "--tags", "--always"),
        "dirty": bool(status) if status is not None else None,
        "dirty_files": status.splitlines() if status else [],
    }


def environment_state() -> Dict[str, Any]:
    """Interpreter, packages and machine."""
    packages: Dict[str, Optional[str]] = {}
    for name in _TRACKED_PACKAGES:
        try:
            from importlib.metadata import version
            packages[name] = version(name)
        except Exception:
            packages[name] = None
    return {
        "python": sys.version.split()[0],
        "python_full": sys.version,
        "implementation": platform.python_implementation(),
        "packages": packages,
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "cpu_count": os.cpu_count(),
    }


@dataclass
class Manifest:
    experiment_id: str
    description: str = ""
    started_at: str = ""
    finished_at: str = ""
    runtime_seconds: float = 0.0
    config_hash: str = ""
    config: Dict[str, Any] = field(default_factory=dict)
    seeds: List[int] = field(default_factory=list)
    arms: List[str] = field(default_factory=list)
    git: Dict[str, Any] = field(default_factory=dict)
    environment: Dict[str, Any] = field(default_factory=dict)
    inputs: Dict[str, str] = field(default_factory=dict)
    outputs: Dict[str, str] = field(default_factory=dict)
    notes: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def start(cls, experiment_id: str, description: str = "", **kwargs
              ) -> "Manifest":
        m = cls(experiment_id=experiment_id, description=description, **kwargs)
        m.started_at = time.strftime("%Y-%m-%dT%H:%M:%S%z")
        m._t0 = time.time()          # type: ignore[attr-defined]
        m.git = git_state()
        m.environment = environment_state()
        return m

    def add_input(self, path: Path | str) -> None:
        path = Path(path)
        self.inputs[str(path.as_posix())] = file_digest(path)

    def add_output(self, path: Path | str) -> None:
        path = Path(path)
        self.outputs[str(path.as_posix())] = file_digest(path)

    def finish(self) -> "Manifest":
        self.finished_at = time.strftime("%Y-%m-%dT%H:%M:%S%z")
        self.runtime_seconds = round(time.time() - getattr(self, "_t0", time.time()), 3)
        return self

    def as_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data.pop("_t0", None)
        return data

    def write(self, path: Path | str) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(self.as_dict(), fh, indent=1, sort_keys=True)
            fh.write("\n")
        return path


def write_manifest(experiment_id: str, path: Path | str, **kwargs) -> Path:
    return Manifest.start(experiment_id, **kwargs).finish().write(path)
