"""Semantic contracts that are independent of an adapter's information sets."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Generic, Hashable, Iterable, TypeVar

from aip.core.cfr import ExtensiveFormGame


State = TypeVar("State", bound=Hashable)


@dataclass(frozen=True, slots=True)
class ObservationInvarianceCase(Generic[State]):
    """Two decision states that differ only in state hidden from the actor."""

    case_id: str
    left_state: State
    right_state: State


@dataclass(frozen=True, slots=True)
class ObservationInvarianceViolation:
    case_id: str
    player: int | None
    changed_observables: tuple[str, ...]
    left_state: str
    right_state: str

    def to_artifact(self) -> dict[str, object]:
        return {
            "case_id": self.case_id,
            "player": self.player,
            "changed_observables": list(self.changed_observables),
            "left_state": self.left_state,
            "right_state": self.right_state,
        }


@dataclass(frozen=True, slots=True)
class ObservationInvarianceAudit:
    cases: int
    violations: int
    violations_by_component: tuple[tuple[str, int], ...]
    counterexamples: tuple[ObservationInvarianceViolation, ...]

    @property
    def passed(self) -> bool:
        return self.violations == 0

    def to_artifact(self) -> dict[str, object]:
        return {
            "cases": self.cases,
            "violations": self.violations,
            "violations_by_component": dict(self.violations_by_component),
            "passed": self.passed,
            "counterexamples": [
                violation.to_artifact() for violation in self.counterexamples
            ],
        }


def audit_observation_invariance(
    game: ExtensiveFormGame[State],
    cases: Iterable[ObservationInvarianceCase[State]],
    *,
    maximum_cases: int = 100_000,
    maximum_counterexamples: int = 5,
) -> ObservationInvarianceAudit:
    """Check externally declared state pairs against an adapter's observations.

    The pairs are part of a trusted rule contract. They must not be inferred
    from the candidate adapter's own information-set partition, because that
    would reproduce the same hidden-information error being audited.
    """

    if maximum_cases <= 0:
        raise ValueError("maximum cases must be positive")
    if maximum_counterexamples < 0:
        raise ValueError("maximum counterexamples cannot be negative")

    materialized = tuple(cases)
    if not materialized:
        raise ValueError("observation-invariance contract must contain cases")
    if len(materialized) > maximum_cases:
        raise OverflowError(f"semantic audit exceeds {maximum_cases} cases")
    identifiers = tuple(case.case_id for case in materialized)
    if any(not identifier for identifier in identifiers):
        raise ValueError("observation-invariance case ids must be nonempty")
    if len(set(identifiers)) != len(identifiers):
        raise ValueError("observation-invariance case ids must be unique")

    examples: list[ObservationInvarianceViolation] = []
    component_counts: Counter[str] = Counter()
    violation_count = 0
    for case in materialized:
        left, right = case.left_state, case.right_state
        changed: list[str] = []
        left_terminal = game.is_terminal(left)
        right_terminal = game.is_terminal(right)
        if left_terminal != right_terminal:
            changed.append("terminal_status")

        left_player = game.current_player(left)
        right_player = game.current_player(right)
        if left_player != right_player:
            changed.append("current_player")
        player = left_player if left_player == right_player else None

        if left_terminal or right_terminal or player not in (0, 1):
            changed.append("decision_state_required")
        else:
            if game.legal_actions(left) != game.legal_actions(right):
                changed.append("legal_actions")
            if game.information_set(left) != game.information_set(right):
                changed.append("information_set")

        if changed:
            violation_count += 1
            component_counts.update(changed)
            if len(examples) < maximum_counterexamples:
                examples.append(
                    ObservationInvarianceViolation(
                        case.case_id,
                        player,
                        tuple(changed),
                        repr(left),
                        repr(right),
                    )
                )

    return ObservationInvarianceAudit(
        cases=len(materialized),
        violations=violation_count,
        violations_by_component=tuple(sorted(component_counts.items())),
        counterexamples=tuple(examples),
    )
