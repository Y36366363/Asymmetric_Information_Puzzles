"""Restricted I/O and trusted scoring for an LLM GameSpec pilot."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
import re
from typing import Hashable, Mapping

from aip.core.game_spec import GameSpecObservationSlice, ObservationStateRecord
from aip.core.game_spec_uncertainty import (
    GameSpecHypothesis,
    ObservationEquivalenceEvidence,
)


_IDENTIFIER = re.compile(r"^[a-z][a-z0-9_]*$")
_SOURCE_KINDS = frozenset({
    "rule_author", "official_trace", "independent_reference",
    "expert_review", "synthetic_negative_control",
})


def _require_exact_keys(
    value: Mapping[str, object], expected: set[str], *, label: str
) -> None:
    actual = set(value)
    if actual != expected:
        raise ValueError(
            f"{label} keys do not match restricted schema; "
            f"missing={sorted(expected - actual)}, extra={sorted(actual - expected)}"
        )


def _require_string_list(value: object, *, label: str) -> tuple[str, ...]:
    if not isinstance(value, list) or any(
        not isinstance(item, str) for item in value
    ):
        raise ValueError(f"{label} must be a JSON list of strings")
    result = tuple(value)
    if len(set(result)) != len(result):
        raise ValueError(f"{label} must not contain duplicates")
    return result


@dataclass(frozen=True, slots=True)
class GameSpecVocabulary:
    """Evaluator-owned field vocabulary for one rule instance."""

    game_id: str
    player_count: int
    fields: tuple[str, ...]

    def __post_init__(self) -> None:
        if not _IDENTIFIER.fullmatch(self.game_id):
            raise ValueError("game id must be a lowercase restricted identifier")
        if self.player_count != 2:
            raise ValueError("the v1 pilot vocabulary supports exactly two players")
        if not self.fields or len(set(self.fields)) != len(self.fields):
            raise ValueError("field vocabulary must be nonempty and unique")
        if any(not _IDENTIFIER.fullmatch(field) for field in self.fields):
            raise ValueError("field names must be lowercase restricted identifiers")

    @property
    def player_ids(self) -> tuple[str, ...]:
        return tuple(f"player_{player}" for player in range(self.player_count))


def observation_partition_signature(
    spec: GameSpecObservationSlice, vocabulary: GameSpecVocabulary
) -> tuple[tuple[str, str], ...]:
    """Canonical visibility signature used only by the trusted evaluator."""

    ownership = {field: "public" for field in spec.public_fields}
    for player, fields in enumerate(spec.private_fields_by_player):
        ownership.update({field: f"player_{player}" for field in fields})
    if set(ownership) != set(vocabulary.fields):
        raise ValueError("GameSpec does not cover the evaluator vocabulary")
    return tuple((field, ownership[field]) for field in vocabulary.fields)


@dataclass(frozen=True, slots=True)
class CompiledGameSpecCandidateSet:
    schema_version: str
    game_id: str
    hypotheses: tuple[GameSpecHypothesis, ...]
    signatures: tuple[tuple[tuple[str, str], ...], ...]

    def to_artifact(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "game_id": self.game_id,
            "candidate_count": len(self.hypotheses),
            "hypothesis_ids": [
                hypothesis.hypothesis_id for hypothesis in self.hypotheses
            ],
            "priors_assigned_by_evaluator": [
                hypothesis.prior for hypothesis in self.hypotheses
            ],
        }


def compile_game_spec_candidate_json(
    payload: Mapping[str, object],
    vocabulary: GameSpecVocabulary,
    *,
    minimum_candidates: int = 1,
    maximum_candidates: int = 3,
    exact_candidates: int | None = None,
) -> CompiledGameSpecCandidateSet:
    """Compile untrusted JSON without accepting confidence or certificates."""

    if minimum_candidates < 1 or maximum_candidates < minimum_candidates:
        raise ValueError("candidate limits must define a nonempty valid range")
    if exact_candidates is not None and (
        exact_candidates < minimum_candidates
        or exact_candidates > maximum_candidates
    ):
        raise ValueError("exact candidate count must fall within candidate limits")
    if not isinstance(payload, Mapping):
        raise ValueError("GameSpec candidate payload must be a JSON object")
    _require_exact_keys(
        payload,
        {"schema_version", "game_id", "candidates"},
        label="candidate payload",
    )
    if payload["schema_version"] != "aip-observation-gamespec-candidates-v1":
        raise ValueError("unknown GameSpec candidate schema version")
    if payload["game_id"] != vocabulary.game_id:
        raise ValueError("candidate game id does not match evaluator vocabulary")
    raw_candidates = payload["candidates"]
    if not isinstance(raw_candidates, list):
        raise ValueError("candidates must be a JSON list")
    count = len(raw_candidates)
    if exact_candidates is not None and count != exact_candidates:
        raise ValueError(f"candidate payload must contain exactly {exact_candidates}")
    if count < minimum_candidates or count > maximum_candidates:
        raise ValueError(
            f"candidate count must be between {minimum_candidates} and "
            f"{maximum_candidates}"
        )

    ids: set[str] = set()
    ordered_ids: list[str] = []
    specs: list[GameSpecObservationSlice] = []
    signatures: list[tuple[tuple[str, str], ...]] = []
    expected_players = set(vocabulary.player_ids)
    for index, raw in enumerate(raw_candidates):
        if not isinstance(raw, Mapping):
            raise ValueError(f"candidate {index} must be a JSON object")
        _require_exact_keys(
            raw,
            {"hypothesis_id", "public_fields", "private_fields_by_player"},
            label=f"candidate {index}",
        )
        hypothesis_id = raw["hypothesis_id"]
        if not isinstance(hypothesis_id, str) or not _IDENTIFIER.fullmatch(
            hypothesis_id
        ):
            raise ValueError("hypothesis ids must be lowercase restricted identifiers")
        if hypothesis_id in ids:
            raise ValueError("hypothesis ids must be unique")
        ids.add(hypothesis_id)
        ordered_ids.append(hypothesis_id)
        public = _require_string_list(
            raw["public_fields"], label=f"candidate {index} public fields"
        )
        raw_private = raw["private_fields_by_player"]
        if not isinstance(raw_private, Mapping):
            raise ValueError("private_fields_by_player must be a JSON object")
        if set(raw_private) != expected_players:
            raise ValueError("private fields must name every evaluator player exactly")
        private = tuple(
            _require_string_list(
                raw_private[player_id],
                label=f"candidate {index} {player_id} private fields",
            )
            for player_id in vocabulary.player_ids
        )
        assigned = public + tuple(field for fields in private for field in fields)
        if len(set(assigned)) != len(assigned):
            raise ValueError("each vocabulary field must be assigned exactly once")
        if set(assigned) != set(vocabulary.fields):
            raise ValueError("candidate must partition the evaluator field vocabulary")
        spec = GameSpecObservationSlice(
            f"{vocabulary.game_id}:{hypothesis_id}",
            vocabulary.player_count,
            public,
            private,
        )
        signature = observation_partition_signature(spec, vocabulary)
        if signature in signatures:
            raise ValueError("candidate observation partitions must be unique")
        specs.append(spec)
        signatures.append(signature)

    prior = 1.0 / count
    hypotheses = tuple(
        GameSpecHypothesis(hypothesis_id, spec, prior)
        for hypothesis_id, spec in zip(ordered_ids, specs)
    )
    return CompiledGameSpecCandidateSet(
        "aip-observation-gamespec-candidates-v1",
        vocabulary.game_id,
        hypotheses,
        tuple(signatures),
    )


@dataclass(frozen=True, slots=True)
class EvidenceSourcePolicy:
    source_id: str
    source_kind: str
    reliability: float
    independence_group: str
    may_certify: bool

    def __post_init__(self) -> None:
        if not _IDENTIFIER.fullmatch(self.source_id):
            raise ValueError("evidence source id must be a restricted identifier")
        if self.source_kind not in _SOURCE_KINDS:
            raise ValueError("unknown evidence source kind")
        if not self.independence_group:
            raise ValueError("evidence source independence group must be nonempty")
        if (
            not isfinite(self.reliability)
            or self.reliability < 0.5
            or self.reliability > 1.0
        ):
            raise ValueError("source reliability must be finite and in [0.5, 1]")
        if self.may_certify and self.reliability != 1.0:
            raise ValueError("only hard evidence sources may certify")
        if self.may_certify and self.source_kind == "synthetic_negative_control":
            raise ValueError("synthetic negative controls may not certify")


@dataclass(frozen=True, slots=True)
class TrustedObservationEvidence:
    evidence: ObservationEquivalenceEvidence[Hashable]
    source: EvidenceSourcePolicy
    left_world_id: str
    right_world_id: str

    def to_artifact(self) -> dict[str, object]:
        return {
            "evidence_id": self.evidence.evidence_id,
            "source_id": self.source.source_id,
            "source_kind": self.source.source_kind,
            "reliability_from_registry": self.source.reliability,
            "may_certify": self.source.may_certify,
            "left_world_id": self.left_world_id,
            "right_world_id": self.right_world_id,
            "acting_player": self.evidence.left.acting_player,
            "observed_same": self.evidence.observed_same,
        }


def compile_trusted_evidence_json(
    payload: Mapping[str, object],
    *,
    sources: Mapping[str, EvidenceSourcePolicy],
    worlds: Mapping[str, ObservationStateRecord[Hashable]],
) -> TrustedObservationEvidence:
    """Resolve evidence reliability from an evaluator-owned source registry."""

    if not isinstance(payload, Mapping):
        raise ValueError("evidence payload must be a JSON object")
    _require_exact_keys(
        payload,
        {"schema_version", "evidence_id", "source_id", "left_world_id",
         "right_world_id", "acting_player", "observed_same"},
        label="evidence payload",
    )
    if payload["schema_version"] != "aip-observation-evidence-v1":
        raise ValueError("unknown observation evidence schema version")
    evidence_id = payload["evidence_id"]
    source_id = payload["source_id"]
    left_id = payload["left_world_id"]
    right_id = payload["right_world_id"]
    if not all(
        isinstance(value, str)
        for value in (evidence_id, source_id, left_id, right_id)
    ):
        raise ValueError("evidence and world ids must be strings")
    if source_id not in sources:
        raise ValueError("evidence source is not in the evaluator registry")
    if left_id not in worlds or right_id not in worlds:
        raise ValueError("evidence world id is not in the evaluator registry")
    if left_id == right_id:
        raise ValueError("evidence must compare two distinct worlds")
    player = payload["acting_player"]
    observed_same = payload["observed_same"]
    if not isinstance(player, int) or isinstance(player, bool):
        raise ValueError("evidence acting_player must be an integer")
    if not isinstance(observed_same, bool):
        raise ValueError("evidence observed_same must be boolean")
    left, right = worlds[left_id], worlds[right_id]
    if left.acting_player != player or right.acting_player != player:
        raise ValueError("evidence actor does not match registered worlds")
    source = sources[source_id]
    evidence = ObservationEquivalenceEvidence(
        evidence_id, left, right, observed_same, source.reliability
    )
    return TrustedObservationEvidence(evidence, source, left_id, right_id)


@dataclass(frozen=True, slots=True)
class CandidateSetVerification:
    status: str
    compatible_hypothesis_ids: tuple[str, ...]
    certified_hypothesis_id: str | None
    required_evidence_ids: tuple[str, ...]
    supplied_evidence_ids: tuple[str, ...]

    @property
    def certified(self) -> bool:
        return self.status == "verified"

    def to_artifact(self) -> dict[str, object]:
        return {
            "status": self.status,
            "compatible_hypothesis_ids": list(self.compatible_hypothesis_ids),
            "certified_hypothesis_id": self.certified_hypothesis_id,
            "required_evidence_ids": list(self.required_evidence_ids),
            "supplied_evidence_ids": list(self.supplied_evidence_ids),
            "certified": self.certified,
        }


def verify_candidate_set(
    candidate_set: CompiledGameSpecCandidateSet,
    evidence: tuple[TrustedObservationEvidence, ...],
    *,
    required_evidence_ids: tuple[str, ...],
) -> CandidateSetVerification:
    """Certify only from a complete evaluator-owned hard-evidence suite."""

    if not required_evidence_ids or len(set(required_evidence_ids)) != len(
        required_evidence_ids
    ):
        raise ValueError("required evidence ids must be nonempty and unique")
    supplied_ids = tuple(item.evidence.evidence_id for item in evidence)
    if len(set(supplied_ids)) != len(supplied_ids):
        raise ValueError("supplied evidence ids must be unique")
    if not set(required_evidence_ids).issubset(supplied_ids):
        return CandidateSetVerification(
            "incomplete_evidence", (), None, required_evidence_ids, supplied_ids
        )
    required = tuple(
        item for item in evidence if item.evidence.evidence_id in required_evidence_ids
    )
    if any(
        not item.source.may_certify
        or item.source.reliability != 1.0
        for item in required
    ):
        return CandidateSetVerification(
            "untrusted_evidence", (), None, required_evidence_ids, supplied_ids
        )

    compatible: list[str] = []
    for hypothesis in candidate_set.hypotheses:
        spec = hypothesis.observation_spec
        matches = True
        for item in required:
            left = item.evidence.left
            right = item.evidence.right
            player = left.acting_player
            predicted_same = (
                spec.project(left.field_mapping(), player)
                == spec.project(right.field_mapping(), player)
            )
            if predicted_same != item.evidence.observed_same:
                matches = False
                break
        if matches:
            compatible.append(hypothesis.hypothesis_id)

    if not compatible:
        status, certified = "conflicted", None
    elif len(compatible) > 1:
        status, certified = "ambiguous", None
    else:
        status, certified = "verified", compatible[0]
    return CandidateSetVerification(
        status, tuple(compatible), certified, required_evidence_ids, supplied_ids
    )


@dataclass(frozen=True, slots=True)
class PilotCaseScore:
    arm_id: str
    true_model_candidate_coverage: bool
    verification: CandidateSetVerification
    certified_reference_model: bool
    false_certification: bool
    candidate_count: int
    repair_count: int
    conditional_solver_succeeded: bool | None

    def to_artifact(self) -> dict[str, object]:
        return {
            "arm_id": self.arm_id,
            "true_model_candidate_coverage": self.true_model_candidate_coverage,
            "verification": self.verification.to_artifact(),
            "certified_reference_model": self.certified_reference_model,
            "false_certification": self.false_certification,
            "candidate_count": self.candidate_count,
            "repair_count": self.repair_count,
            "conditional_solver_succeeded": self.conditional_solver_succeeded,
        }


def score_pilot_case(
    *,
    arm_id: str,
    candidate_set: CompiledGameSpecCandidateSet,
    trusted_reference: GameSpecObservationSlice,
    vocabulary: GameSpecVocabulary,
    evidence: tuple[TrustedObservationEvidence, ...],
    required_evidence_ids: tuple[str, ...],
    repair_count: int,
    conditional_solver_succeeded: bool | None,
) -> PilotCaseScore:
    """Score coverage and false certification against a hidden reference."""

    if repair_count < 0:
        raise ValueError("repair count cannot be negative")
    if conditional_solver_succeeded is not None and not isinstance(
        conditional_solver_succeeded, bool
    ):
        raise ValueError("conditional solver status must be boolean or null")
    reference_signature = observation_partition_signature(
        trusted_reference, vocabulary
    )
    coverage = reference_signature in candidate_set.signatures
    verification = verify_candidate_set(
        candidate_set, evidence, required_evidence_ids=required_evidence_ids
    )
    certified_reference = False
    if verification.certified_hypothesis_id is not None:
        index = next(
            index
            for index, hypothesis in enumerate(candidate_set.hypotheses)
            if hypothesis.hypothesis_id == verification.certified_hypothesis_id
        )
        certified_reference = candidate_set.signatures[index] == reference_signature
    return PilotCaseScore(
        arm_id=arm_id,
        true_model_candidate_coverage=coverage,
        verification=verification,
        certified_reference_model=certified_reference,
        false_certification=verification.certified and not certified_reference,
        candidate_count=len(candidate_set.hypotheses),
        repair_count=repair_count,
        conditional_solver_succeeded=conditional_solver_succeeded,
    )
