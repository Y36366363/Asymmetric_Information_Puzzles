"""Typed observation evidence; diagnostic agreement cannot authorize deployment.

These checks prevent accidental promotion in supported entry points. They are
not a security boundary against code that deliberately bypasses the API.
"""
from dataclasses import dataclass, field
from enum import Enum
from hashlib import sha256
import json


class ObservationValidationError(RuntimeError):
    pass


class ObservationStatus(str, Enum):
    REJECT_LOCAL = "reject_local"
    UNVERIFIED = "locally_consistent_unverified"
    VERIFIED = "verified"


_ISSUER = object()


def fingerprint(value):
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                             allow_nan=False).encode()).hexdigest()


@dataclass(frozen=True, slots=True)
class ObservationValidation:
    status: ObservationStatus
    subject_sha256: str
    reference_sha256: str | None = None
    semantic_result: str = "not_assessed"
    scope: str = "diagnostic_only"
    _issuer: object = field(default=None, repr=False, compare=False)

    def __post_init__(self):
        if self._issuer is not _ISSUER or not isinstance(self.status, ObservationStatus):
            raise ObservationValidationError("use the evaluator-owned observation checker")

    def __bool__(self):
        raise ObservationValidationError("select an explicit observation status; unverified is not passed")

    def to_artifact(self):
        return {"status": self.status.value, "subject_sha256": self.subject_sha256,
                "reference_sha256": self.reference_sha256, "semantic_result": self.semantic_result,
                "scope": self.scope, "runtime_or_strategy_authority": False}


def require_reference_verified(record, subject, reference):
    """Allow offline use only for the exact reference and subject checked."""
    if (not isinstance(record, ObservationValidation) or record._issuer is not _ISSUER
            or record.status is not ObservationStatus.VERIFIED
            or record.scope != "frozen_reference_output_only"
            or record.semantic_result != "matched"
            or record.subject_sha256 != fingerprint(subject)
            or record.reference_sha256 != fingerprint(reference)):
        raise ObservationValidationError("exact frozen-reference verification required")
    return record


def require_strategy_observation_authority(record):
    """No observation diagnostic in this version can authorize strategy promotion."""
    if not isinstance(record, ObservationValidation) or record.status is not ObservationStatus.VERIFIED:
        raise ObservationValidationError("unverified observation cannot authorize deployment or freezing")
    raise ObservationValidationError("diagnostic reference verification is not a strategy certificate")
