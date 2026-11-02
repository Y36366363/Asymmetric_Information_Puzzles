"""New typed wrapper, leaving the hash-frozen v9 checker and scorers untouched."""
from collections import Counter
import json

from aip.benchmark.gamespec_attribution import evaluate
from aip.benchmark.gamespec_local_checks import MISSING, check_local
from aip.core.observation_validation import (
    ObservationStatus, ObservationValidation, _ISSUER, fingerprint,
)


def inspect_observation(fields, *, table=MISSING, proposal=MISSING):
    subject = {"fields": list(fields)}
    kwargs = {}
    for name, value in (("table", table), ("proposal", proposal)):
        if value is not MISSING:
            subject[name] = value
            kwargs[name] = value
    local = check_local(subject["fields"], **kwargs)
    record = ObservationValidation(ObservationStatus(local["status"]), fingerprint(subject), _issuer=_ISSUER)
    return record, local, subject


def verify_frozen_output(text, condition, item, transport_errors=()):
    # evaluate performs the unchanged semantic check + independent direct oracle.
    evaluation = evaluate(text, condition, item, transport_errors)
    try:
        payload = json.loads(text)
    except (ValueError, TypeError):
        payload = None
    kwargs = {}
    if condition != "A" and isinstance(payload, dict) and "stage_table" in payload:
        kwargs["table"] = payload["stage_table"]
    if evaluation["proposal"] is not None:
        kwargs["proposal"] = evaluation["proposal"]
    record, local, subject = inspect_observation(tuple(item["case"]["fields"]), **kwargs)
    if record.status is not ObservationStatus.REJECT_LOCAL:
        matched = evaluation["whole_response_correct"]
        record = ObservationValidation(
            ObservationStatus.VERIFIED if matched else ObservationStatus.UNVERIFIED,
            fingerprint(subject), fingerprint(item), "matched" if matched else "mismatched",
            "frozen_reference_output_only" if matched else "diagnostic_only", _ISSUER)
    return record, local, subject, evaluation


def state_counts(records):
    counts = Counter(r.status.value for r in records)
    return {"assigned": len(records), "states": {s.value: counts[s.value] for s in ObservationStatus},
            "combined_pass_rate": None,
            "reason": "local consistency and reference verification are separate endpoints"}
