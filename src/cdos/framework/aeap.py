"""Autonomous Economic Activity Passport (AEAP).

A registration record for a deployed autonomous system. It is a **measurement
and accountability artefact**, nothing more.

What an AEAP is not
-------------------
It does not create legal personality for an AI agent or a robot. By the
manuscript's ownership assumption the statutory taxpayer is always
``Owner(AEAP_i)`` -- a natural or legal person -- and never the deployment
itself. A passport identifies activity for attribution and audit; it does not
confer rights, duties or standing on the thing it describes. Nothing in this
module should be read as a claim about what any jurisdiction's law currently
provides.

The record
----------
Required: ``deployment_id``, ``owner``, ``jurisdiction``, ``task_class``,
``model_class``, ``risk_class``, ``energy``, ``output``.

Validation covers the cases the audit asked for: a missing owner, an
unrecognised jurisdiction or task class, duplicate deployment identifiers,
activity below the de minimis threshold, non-finite or negative output, and
malformed records generally. Validation is strict by default: a passport that
cannot be validated must not enter the contribution base.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence
from dataclasses import asdict, dataclass, field
from typing import Any

__all__ = ["AEAP", "AEAPError", "TASK_CLASSES", "RISK_CLASSES", "MODEL_CLASSES",
           "AEAPRegistry", "validate_record"]

TASK_CLASSES = ("substitution", "augmentation", "new_task", "safety_replacement")
RISK_CLASSES = ("minimal", "limited", "high", "unacceptable")
MODEL_CLASSES = ("rule_based", "classical_ml", "foundation_model",
                 "embodied_robot", "hybrid")


class AEAPError(ValueError):
    """Raised when a passport record is malformed or fails validation."""


@dataclass
class AEAP:
    """One registered deployment."""
    deployment_id: str
    owner: str
    jurisdiction: str
    task_class: str
    model_class: str = "rule_based"
    risk_class: str = "minimal"
    energy: float = 0.0          # energy consumed over the reporting period
    output: float = 0.0          # attributed output over the reporting period
    nexus_shares: dict[str, float] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def energy_intensity(self) -> float:
        return self.energy / max(self.output, 1e-12)


def _require_str(record: dict[str, Any], key: str) -> str:
    value = record.get(key)
    if value is None or (isinstance(value, str) and not value.strip()):
        raise AEAPError(f"AEAP record is missing a {key}")
    if not isinstance(value, str):
        raise AEAPError(f"AEAP {key} must be a string, got {type(value).__name__}")
    return value


def _require_number(record: dict[str, Any], key: str, minimum: float = 0.0) -> float:
    value = record.get(key, 0.0)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise AEAPError(f"AEAP {key} must be a number, got {type(value).__name__}")
    value = float(value)
    if not math.isfinite(value):
        raise AEAPError(f"AEAP {key} must be finite, got {value}")
    if value < minimum:
        raise AEAPError(f"AEAP {key} must be at least {minimum}, got {value}")
    return value


def validate_record(record: dict[str, Any],
                    jurisdictions: Sequence[str] | None = None,
                    de_minimis: float = 0.0) -> AEAP:
    """Validate one record and return the passport.

    ``de_minimis`` is the administrability threshold: activity below it is out
    of scope. The manuscript's regulatory assumption leans on this threshold,
    and its calibration determines whether the system is administrable at all,
    so a sub-threshold record is rejected explicitly rather than silently
    contributing zero.
    """
    if not isinstance(record, dict):
        raise AEAPError(f"AEAP record must be a mapping, got {type(record).__name__}")

    deployment_id = _require_str(record, "deployment_id")
    owner = _require_str(record, "owner")
    jurisdiction = _require_str(record, "jurisdiction")
    task_class = _require_str(record, "task_class")

    if task_class not in TASK_CLASSES:
        raise AEAPError(
            f"AEAP {deployment_id}: task_class {task_class!r} is not one of "
            f"{list(TASK_CLASSES)}")
    model_class = record.get("model_class", "rule_based")
    if model_class not in MODEL_CLASSES:
        raise AEAPError(
            f"AEAP {deployment_id}: model_class {model_class!r} is not one of "
            f"{list(MODEL_CLASSES)}")
    risk_class = record.get("risk_class", "minimal")
    if risk_class not in RISK_CLASSES:
        raise AEAPError(
            f"AEAP {deployment_id}: risk_class {risk_class!r} is not one of "
            f"{list(RISK_CLASSES)}")
    if jurisdictions is not None and jurisdiction not in jurisdictions:
        raise AEAPError(
            f"AEAP {deployment_id}: jurisdiction {jurisdiction!r} is not "
            f"registered; known jurisdictions are {list(jurisdictions)}")

    energy = _require_number(record, "energy")
    output = _require_number(record, "output")
    if output < de_minimis:
        raise AEAPError(
            f"AEAP {deployment_id}: output {output} is below the de minimis "
            f"threshold {de_minimis}; the deployment is out of scope")

    shares = record.get("nexus_shares")
    if shares is not None:
        if not isinstance(shares, dict) or not shares:
            raise AEAPError(f"AEAP {deployment_id}: nexus_shares must be a "
                            "non-empty mapping of jurisdiction to share")
        total = 0.0
        for key, value in shares.items():
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                raise AEAPError(f"AEAP {deployment_id}: nexus share for {key!r} "
                                "is not a number")
            if value < 0:
                raise AEAPError(f"AEAP {deployment_id}: nexus share for {key!r} "
                                f"is negative ({value})")
            total += float(value)
        if abs(total - 1.0) > 1e-9:
            raise AEAPError(
                f"AEAP {deployment_id}: nexus shares sum to {total:.12g}, not 1 "
                "(Proposition 8)")

    return AEAP(deployment_id=deployment_id, owner=owner,
                jurisdiction=jurisdiction, task_class=task_class,
                model_class=model_class, risk_class=risk_class,
                energy=energy, output=output,
                nexus_shares=dict(shares) if shares else None,
                metadata=dict(record.get("metadata", {})))


class AEAPRegistry:
    """A set of passports with unique deployment identifiers."""

    def __init__(self, jurisdictions: Sequence[str] | None = None,
                 de_minimis: float = 0.0):
        self.jurisdictions = tuple(jurisdictions) if jurisdictions else None
        self.de_minimis = float(de_minimis)
        self._records: dict[str, AEAP] = {}

    def __len__(self) -> int:
        return len(self._records)

    def __contains__(self, deployment_id: object) -> bool:
        return deployment_id in self._records

    def __iter__(self):
        return iter(self._records.values())

    def add(self, record: dict[str, Any] | AEAP) -> AEAP:
        passport = record if isinstance(record, AEAP) else validate_record(
            record, self.jurisdictions, self.de_minimis)
        if passport.deployment_id in self._records:
            raise AEAPError(
                f"duplicate deployment_id {passport.deployment_id!r}; a "
                "deployment may be registered only once")
        self._records[passport.deployment_id] = passport
        return passport

    def add_many(self, records: Iterable[dict[str, Any]]) -> list[AEAP]:
        return [self.add(r) for r in records]

    def get(self, deployment_id: str) -> AEAP:
        try:
            return self._records[deployment_id]
        except KeyError:
            raise AEAPError(f"no AEAP registered under {deployment_id!r}") from None

    def owners(self) -> set[str]:
        return {r.owner for r in self._records.values()}

    def by_task_class(self, task_class: str) -> list[AEAP]:
        if task_class not in TASK_CLASSES:
            raise AEAPError(f"unknown task_class {task_class!r}")
        return [r for r in self._records.values() if r.task_class == task_class]

    def total_output(self) -> float:
        return sum(r.output for r in self._records.values())

    def total_energy(self) -> float:
        return sum(r.energy for r in self._records.values())

    def records(self) -> list[dict[str, Any]]:
        return [r.as_dict() for r in self._records.values()]
