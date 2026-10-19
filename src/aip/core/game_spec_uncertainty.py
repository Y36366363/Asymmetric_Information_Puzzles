"""Epistemic uncertainty over fixed GameSpec observation declarations."""

from __future__ import annotations

from dataclasses import dataclass
from math import exp, fsum, isclose, isfinite, log
from typing import Generic, Hashable, Iterable, TypeVar

from aip.core.game_spec import GameSpecObservationSlice, ObservationStateRecord


State = TypeVar("State", bound=Hashable)


@dataclass(frozen=True, slots=True)
class GameSpecHypothesis:
    """One candidate fixed information structure and its epistemic prior."""

    hypothesis_id: str
    observation_spec: GameSpecObservationSlice
    prior: float

    def __post_init__(self) -> None:
        if not self.hypothesis_id:
            raise ValueError("GameSpec hypothesis id must be nonempty")
        if not isfinite(self.prior) or self.prior <= 0:
            raise ValueError("GameSpec hypothesis priors must be finite and positive")


@dataclass(frozen=True, slots=True)
class ObservationEquivalenceEvidence(Generic[State]):
    """A report about whether two worlds look identical to one actor.

    Reliability is the declared probability that the report matches the true
    equivalence relation.  A value of one is hard evidence; lower values are
    meaningful only under an explicit evidence model.
    """

    evidence_id: str
    left: ObservationStateRecord[State]
    right: ObservationStateRecord[State]
    observed_same: bool
    reliability: float = 1.0

    def __post_init__(self) -> None:
        if not self.evidence_id:
            raise ValueError("observation evidence id must be nonempty")
        if self.left.acting_player != self.right.acting_player:
            raise ValueError("observation evidence must compare the same actor")
        if (
            not isfinite(self.reliability)
            or self.reliability < 0.5
            or self.reliability > 1.0
        ):
            raise ValueError("evidence reliability must be finite and in [0.5, 1]")


@dataclass(frozen=True, slots=True)
class GameSpecHypothesisResult:
    hypothesis_id: str
    prior: float
    posterior: float | None
    hard_compatible: bool
    predictions_matching_evidence: int
    evidence_count: int

    def to_artifact(self) -> dict[str, object]:
        return {
            "hypothesis_id": self.hypothesis_id,
            "prior": self.prior,
            "posterior": self.posterior,
            "hard_compatible": self.hard_compatible,
            "predictions_matching_evidence": self.predictions_matching_evidence,
            "evidence_count": self.evidence_count,
        }


@dataclass(frozen=True, slots=True)
class GameSpecHypothesisReport:
    status: str
    selected_hypothesis_id: str | None
    posterior_threshold: float
    hard_compatible_hypotheses: tuple[str, ...]
    conflicting_evidence_pairs: int
    results: tuple[GameSpecHypothesisResult, ...]

    @property
    def semantic_certification_allowed(self) -> bool:
        return len(self.hard_compatible_hypotheses) == 1

    def to_artifact(self) -> dict[str, object]:
        return {
            "status": self.status,
            "selected_hypothesis_id": self.selected_hypothesis_id,
            "posterior_threshold": self.posterior_threshold,
            "hard_compatible_hypotheses": list(
                self.hard_compatible_hypotheses
            ),
            "semantic_certification_allowed": (
                self.semantic_certification_allowed
            ),
            "conflicting_evidence_pairs": self.conflicting_evidence_pairs,
            "results": [result.to_artifact() for result in self.results],
        }


def evaluate_game_spec_hypotheses(
    hypotheses: Iterable[GameSpecHypothesis],
    evidence: Iterable[ObservationEquivalenceEvidence[State]],
    *,
    posterior_threshold: float = 0.95,
) -> GameSpecHypothesisReport:
    """Update candidate confidence without turning it into game chance.

    The likelihood model treats evidence reports as conditionally independent.
    Callers must justify that assumption; the result is epistemic bookkeeping,
    never a replacement for a rule-level semantic certificate.
    """

    candidates = tuple(hypotheses)
    reports = tuple(evidence)
    if len(candidates) < 2:
        raise ValueError("GameSpec uncertainty requires at least two hypotheses")
    identifiers = tuple(candidate.hypothesis_id for candidate in candidates)
    if len(set(identifiers)) != len(identifiers):
        raise ValueError("GameSpec hypothesis ids must be unique")
    if not isclose(sum(candidate.prior for candidate in candidates), 1.0):
        raise ValueError("GameSpec hypothesis priors must sum to one")
    if (
        not isfinite(posterior_threshold)
        or posterior_threshold <= 0.5
        or posterior_threshold > 1.0
    ):
        raise ValueError("posterior threshold must be finite and in (0.5, 1]")
    evidence_ids = tuple(item.evidence_id for item in reports)
    if len(set(evidence_ids)) != len(evidence_ids):
        raise ValueError("observation evidence ids must be unique")

    reference = candidates[0].observation_spec
    field_universe = set(reference.all_fields)
    for candidate in candidates[1:]:
        spec = candidate.observation_spec
        if spec.player_count != reference.player_count:
            raise ValueError("candidate GameSpecs must have the same players")
        if set(spec.all_fields) != field_universe:
            raise ValueError("candidate GameSpecs must share one field universe")

    pair_labels: dict[tuple[object, ...], set[bool]] = {}
    prepared: list[tuple[ObservationEquivalenceEvidence[State], dict, dict]] = []
    for item in reports:
        left_fields = item.left.field_mapping()
        right_fields = item.right.field_mapping()
        reference._validate_fields(left_fields)
        reference._validate_fields(right_fields)
        pair_key = (
            item.left.acting_player,
            item.left.state,
            item.right.state,
        )
        pair_labels.setdefault(pair_key, set()).add(item.observed_same)
        prepared.append((item, left_fields, right_fields))
    conflicting_pairs = sum(len(labels) > 1 for labels in pair_labels.values())

    log_weights: list[float] = []
    hard_compatible: list[bool] = []
    matches: list[int] = []
    for candidate in candidates:
        spec = candidate.observation_spec
        log_components = [log(candidate.prior)]
        compatible = True
        matching = 0
        for item, left_fields, right_fields in prepared:
            player = item.left.acting_player
            predicted_same = (
                spec.project(left_fields, player)
                == spec.project(right_fields, player)
            )
            prediction_matches = predicted_same == item.observed_same
            matching += int(prediction_matches)
            if item.reliability == 1.0 and not prediction_matches:
                compatible = False
                continue
            likelihood = (
                item.reliability
                if prediction_matches
                else 1.0 - item.reliability
            )
            if likelihood == 0:
                compatible = False
            else:
                log_components.append(log(likelihood))
        score = fsum(log_components) if compatible else float("-inf")
        log_weights.append(score)
        hard_compatible.append(compatible)
        matches.append(matching)

    compatible_ids = tuple(
        candidate.hypothesis_id
        for candidate, compatible in zip(candidates, hard_compatible)
        if compatible
    )
    finite_weights = [weight for weight in log_weights if isfinite(weight)]
    if not finite_weights:
        posteriors: tuple[float | None, ...] = tuple(None for _ in candidates)
        status = "conflicted"
        selected = None
    else:
        maximum = max(finite_weights)
        raw = tuple(
            exp(weight - maximum) if isfinite(weight) else 0.0
            for weight in log_weights
        )
        total = sum(raw)
        posteriors = tuple(value / total for value in raw)
        best = max(posteriors)
        winners = [
            candidate.hypothesis_id
            for candidate, posterior in zip(candidates, posteriors)
            if isclose(posterior, best, rel_tol=1e-12, abs_tol=1e-15)
        ]
        if best >= posterior_threshold and len(winners) == 1:
            status = "identified"
            selected = winners[0]
        else:
            status = "unresolved"
            selected = None

    results = tuple(
        GameSpecHypothesisResult(
            candidate.hypothesis_id,
            candidate.prior,
            posterior,
            compatible,
            matching,
            len(reports),
        )
        for candidate, posterior, compatible, matching in zip(
            candidates, posteriors, hard_compatible, matches
        )
    )
    return GameSpecHypothesisReport(
        status,
        selected,
        posterior_threshold,
        compatible_ids,
        conflicting_pairs,
        results,
    )
