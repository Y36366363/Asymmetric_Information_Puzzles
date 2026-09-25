"""Game-independent, independently scorable strategic value decomposition."""

from __future__ import annotations

import json
from dataclasses import dataclass
from math import isfinite
from statistics import mean
from typing import Mapping, Protocol


TOLERANCE = 1e-9

VALUE_DECOMPOSITION_JSON_SCHEMA: Mapping[str, object] = {
    "type": "object",
    "properties": {
        "posterior": {
            "type": "object",
            "properties": {
                "target": {"type": "string"},
                "probabilities": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "state": {"type": "string"},
                            "probability": {"type": "number", "minimum": 0, "maximum": 1},
                        },
                        "required": ["state", "probability"],
                        "additionalProperties": False,
                    },
                },
            },
            "required": ["target", "probabilities"],
            "additionalProperties": False,
        },
        "action_values": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "action_id": {"type": "string"},
                    "immediate_value": {"type": "number"},
                    "continuation_value": {"type": "number"},
                    "total_value": {"type": "number"},
                },
                "required": [
                    "action_id",
                    "immediate_value",
                    "continuation_value",
                    "total_value",
                ],
                "additionalProperties": False,
            },
        },
        "chosen_action_id": {"type": "string"},
    },
    "required": ["posterior", "action_values", "chosen_action_id"],
    "additionalProperties": False,
}


@dataclass(frozen=True, slots=True)
class ValueDecomposition:
    """Auditable intermediate output from posterior through final action."""

    posterior_target: str
    posterior: Mapping[str, float]
    immediate_action_values: Mapping[str, float]
    continuation_action_values: Mapping[str, float]
    total_action_values: Mapping[str, float]
    chosen_action_id: str

    def __post_init__(self) -> None:
        if not self.posterior_target or not self.posterior:
            raise ValueError("value decomposition needs a nonempty posterior")
        if any(not label for label in self.posterior):
            raise ValueError("posterior labels cannot be empty")
        probabilities = tuple(self.posterior.values())
        if any(not isfinite(value) or value < 0 or value > 1 for value in probabilities):
            raise ValueError("posterior probabilities must be finite and between 0 and 1")
        if abs(sum(probabilities) - 1.0) > TOLERANCE:
            raise ValueError("posterior probabilities must sum to 1")
        action_sets = (
            set(self.immediate_action_values),
            set(self.continuation_action_values),
            set(self.total_action_values),
        )
        if not action_sets[0] or any(actions != action_sets[0] for actions in action_sets[1:]):
            raise ValueError("all value stages must contain the same nonempty action set")
        if self.chosen_action_id not in action_sets[0]:
            raise ValueError("chosen action must appear in every value stage")
        values = (
            tuple(self.immediate_action_values.values())
            + tuple(self.continuation_action_values.values())
            + tuple(self.total_action_values.values())
        )
        if any(not isfinite(value) for value in values):
            raise ValueError("action values must be finite")

    @property
    def optimal_action_ids(self) -> tuple[str, ...]:
        optimum = max(self.total_action_values.values())
        return tuple(sorted(
            action for action, value in self.total_action_values.items()
            if abs(value - optimum) <= TOLERANCE
        ))

    @property
    def maximum_additivity_residual(self) -> float:
        return max(
            abs(
                self.total_action_values[action]
                - self.immediate_action_values[action]
                - self.continuation_action_values[action]
            )
            for action in self.total_action_values
        )

    def to_artifact(self) -> dict[str, object]:
        return {
            "posteriorTarget": self.posterior_target,
            "posterior": dict(self.posterior),
            "immediateActionValues": dict(self.immediate_action_values),
            "continuationActionValues": dict(self.continuation_action_values),
            "totalActionValues": dict(self.total_action_values),
            "chosenActionId": self.chosen_action_id,
            "optimalActionIdsFromReportedTotals": list(self.optimal_action_ids),
            "maximumAdditivityResidual": self.maximum_additivity_residual,
        }


class ValueDecompositionOracle(Protocol):
    oracle_id: str

    def decompose(self, probe) -> ValueDecomposition: ...


@dataclass(frozen=True, slots=True)
class ValueDecompositionScore:
    posterior_brier: float
    immediate_value_mae: float
    continuation_value_mae: float
    total_value_mae: float
    maximum_additivity_residual: float
    final_action_regret: float
    optimal_action_agreement: bool
    decision_consistent_with_reported_values: bool
    per_action_errors: Mapping[str, Mapping[str, float]]

    def to_artifact(self) -> dict[str, object]:
        return {
            "posteriorBrier": self.posterior_brier,
            "immediateValueMae": self.immediate_value_mae,
            "continuationValueMae": self.continuation_value_mae,
            "totalValueMae": self.total_value_mae,
            "maximumAdditivityResidual": self.maximum_additivity_residual,
            "finalActionRegret": self.final_action_regret,
            "optimalActionAgreement": self.optimal_action_agreement,
            "decisionConsistentWithReportedValues": self.decision_consistent_with_reported_values,
            "perActionErrors": {
                action: dict(errors) for action, errors in self.per_action_errors.items()
            },
        }


def score_value_decomposition(
    candidate: ValueDecomposition,
    reference: ValueDecomposition,
) -> ValueDecompositionScore:
    """Score each intermediate field without trusting the candidate's final action."""

    if candidate.posterior_target != reference.posterior_target:
        raise ValueError("candidate posterior target differs from reference")
    if set(candidate.posterior) != set(reference.posterior):
        raise ValueError("candidate posterior labels differ from reference")
    actions = set(reference.total_action_values)
    if set(candidate.total_action_values) != actions:
        raise ValueError("candidate action set differs from reference")
    posterior_brier = sum(
        (candidate.posterior[label] - reference.posterior[label]) ** 2
        for label in reference.posterior
    )
    errors = {}
    for action in sorted(actions):
        errors[action] = {
            "immediateAbsoluteError": abs(
                candidate.immediate_action_values[action]
                - reference.immediate_action_values[action]
            ),
            "continuationAbsoluteError": abs(
                candidate.continuation_action_values[action]
                - reference.continuation_action_values[action]
            ),
            "totalAbsoluteError": abs(
                candidate.total_action_values[action]
                - reference.total_action_values[action]
            ),
        }
    optimum = max(reference.total_action_values.values())
    final_regret = optimum - reference.total_action_values[candidate.chosen_action_id]
    return ValueDecompositionScore(
        posterior_brier=posterior_brier,
        immediate_value_mae=mean(
            item["immediateAbsoluteError"] for item in errors.values()
        ),
        continuation_value_mae=mean(
            item["continuationAbsoluteError"] for item in errors.values()
        ),
        total_value_mae=mean(item["totalAbsoluteError"] for item in errors.values()),
        maximum_additivity_residual=candidate.maximum_additivity_residual,
        final_action_regret=final_regret,
        optimal_action_agreement=final_regret <= TOLERANCE,
        decision_consistent_with_reported_values=(
            candidate.chosen_action_id in candidate.optimal_action_ids
        ),
        per_action_errors=errors,
    )


def parse_value_decomposition(output_text: str) -> ValueDecomposition:
    """Parse the strict structured-output shape used by future model experiments."""

    payload = json.loads(output_text)
    if not isinstance(payload, dict) or set(payload) != {
        "posterior", "action_values", "chosen_action_id"
    }:
        raise ValueError("value decomposition has unknown or missing top-level fields")
    posterior = payload["posterior"]
    if not isinstance(posterior, dict) or set(posterior) != {"target", "probabilities"}:
        raise ValueError("posterior has unknown or missing fields")
    probability_rows = posterior["probabilities"]
    action_rows = payload["action_values"]
    if not isinstance(probability_rows, list) or not isinstance(action_rows, list):
        raise ValueError("posterior probabilities and action values must be arrays")

    def number(value, field: str) -> float:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"{field} must be numeric")
        return float(value)

    probabilities = {}
    for row in probability_rows:
        if not isinstance(row, dict) or set(row) != {"state", "probability"}:
            raise ValueError("posterior row has unknown or missing fields")
        label = row["state"]
        if not isinstance(label, str) or not label or label in probabilities:
            raise ValueError("posterior state labels must be unique nonempty strings")
        probabilities[label] = number(row["probability"], "posterior probability")
    immediate = {}
    continuation = {}
    total = {}
    required = {"action_id", "immediate_value", "continuation_value", "total_value"}
    for row in action_rows:
        if not isinstance(row, dict) or set(row) != required:
            raise ValueError("action-value row has unknown or missing fields")
        action = row["action_id"]
        if not isinstance(action, str) or not action or action in total:
            raise ValueError("action ids must be unique nonempty strings")
        immediate[action] = number(row["immediate_value"], "immediate value")
        continuation[action] = number(row["continuation_value"], "continuation value")
        total[action] = number(row["total_value"], "total value")
    chosen = payload["chosen_action_id"]
    if not isinstance(chosen, str):
        raise ValueError("chosen action id must be a string")
    target = posterior["target"]
    if not isinstance(target, str):
        raise ValueError("posterior target must be a string")
    return ValueDecomposition(
        posterior_target=target,
        posterior=probabilities,
        immediate_action_values=immediate,
        continuation_action_values=continuation,
        total_action_values=total,
        chosen_action_id=chosen,
    )
