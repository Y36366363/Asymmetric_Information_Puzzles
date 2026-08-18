"""Small, game-agnostic contracts for strategic-agent evaluation.

The benchmark layer deliberately describes decisions instead of simulating games.
Environment adapters remain thin and puzzle-specific; agents only depend on the
types in this module.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from math import isfinite
from typing import Mapping, Protocol


class StrategicCapability(str, Enum):
    HIDDEN_STATE_REASONING = "hidden_state_reasoning"
    BELIEF_UPDATING = "belief_updating"
    MIXED_STRATEGY = "mixed_strategy"
    OPPONENT_MODELLING = "opponent_modelling"
    INFORMATION_ACQUISITION = "information_acquisition"
    DECEPTION_BLUFFING = "deception_bluffing"
    ADVERSARIAL_SEARCH = "adversarial_search"
    RISK_SENSITIVE_DECISION_MAKING = "risk_sensitive_decision_making"


class EvidenceLevel(str, Enum):
    """Strength of the policy reference available to an evaluator."""

    PROVED_OPTIMAL = "proved_optimality"
    EQUILIBRIUM_BACKED = "equilibrium_backed_behavior"
    STRONG_HEURISTIC = "strong_heuristic"
    EXPLORATORY = "exploratory_llm_behavior"


@dataclass(frozen=True, slots=True)
class ActionSpec:
    """One legal action exposed to an agent at a decision point."""

    action_id: str
    description: str | None = None
    payload_schema: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.action_id:
            raise ValueError("action_id cannot be empty")


@dataclass(frozen=True, slots=True)
class ActionEvent:
    """A public or private action-history item supplied by an adapter."""

    actor_id: str
    action_id: str
    payload: Mapping[str, object] = field(default_factory=dict)
    public_observation: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.actor_id or not self.action_id:
            raise ValueError("history events need actor_id and action_id")


@dataclass(frozen=True, slots=True)
class AgentInput:
    """The complete game-independent input for one strategic decision."""

    environment_id: str
    episode_id: str
    step: int
    observation: Mapping[str, object]
    information_state: Mapping[str, object]
    legal_actions: tuple[ActionSpec, ...]
    action_history: tuple[ActionEvent, ...] = ()
    natural_language_rules: str | None = None

    def __post_init__(self) -> None:
        if not self.environment_id or not self.episode_id:
            raise ValueError("environment_id and episode_id cannot be empty")
        if self.step < 0:
            raise ValueError("step cannot be negative")
        if not self.legal_actions:
            raise ValueError("a non-terminal agent input needs at least one legal action")
        action_ids = tuple(action.action_id for action in self.legal_actions)
        if len(action_ids) != len(set(action_ids)):
            raise ValueError("legal action ids must be unique")


@dataclass(frozen=True, slots=True)
class BeliefOutput:
    """Optional agent belief over adapter-defined, stable state labels."""

    target: str
    probabilities: Mapping[str, float]

    def __post_init__(self) -> None:
        if not self.target or not self.probabilities:
            raise ValueError("belief output needs a target and nonempty probabilities")
        if any(not isinstance(label, str) or not label for label in self.probabilities):
            raise ValueError("belief state labels cannot be empty")
        values = tuple(self.probabilities.values())
        if any(
            not isfinite(probability) or probability < 0 or probability > 1
            for probability in values
        ):
            raise ValueError("belief probabilities must be between 0 and 1")
        if abs(sum(values) - 1.0) > 1e-9:
            raise ValueError("belief probabilities must sum to 1")


@dataclass(frozen=True, slots=True)
class AgentDecision:
    """The minimum auditable output required from every benchmark agent."""

    action_id: str
    confidence: float
    payload: Mapping[str, object] = field(default_factory=dict)
    belief: BeliefOutput | None = None

    def __post_init__(self) -> None:
        if not self.action_id:
            raise ValueError("chosen action_id cannot be empty")
        if not isfinite(self.confidence) or not 0 <= self.confidence <= 1:
            raise ValueError("confidence must be between 0 and 1")


class StrategicAgent(Protocol):
    """One method is enough for algorithms, LLMs, and memory agents alike."""

    def choose_action(self, decision: AgentInput) -> AgentDecision: ...


def validate_decision(decision_input: AgentInput, output: AgentDecision) -> None:
    """Reject invalid outputs before an environment adapter mutates state."""

    legal = {action.action_id: action for action in decision_input.legal_actions}
    if output.action_id not in legal:
        raise ValueError(f"illegal agent action: {output.action_id}")
    schema = legal[output.action_id].payload_schema
    unknown_fields = set(output.payload).difference(schema)
    if unknown_fields:
        raise ValueError(
            f"action payload contains undeclared fields: {sorted(unknown_fields)}"
        )
