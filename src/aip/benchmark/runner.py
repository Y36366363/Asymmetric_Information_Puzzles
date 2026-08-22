"""Minimal episode runner and auditable JSON trace for benchmark adapters."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Mapping, Protocol

from aip.benchmark.types import (
    ActionEvent,
    ActionSpec,
    AgentDecision,
    AgentInput,
    BeliefOutput,
    EvidenceLevel,
    StrategicAgent,
    validate_decision,
)


TRACE_SCHEMA_VERSION = "aip-benchmark-trace-v0"


def _mapping(value: object, field_name: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} must be an object")
    return value


def _sequence(value: object, field_name: str) -> list[object]:
    if not isinstance(value, (list, tuple)):
        raise ValueError(f"{field_name} must be an array")
    return list(value)


def _string(value: object, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string")
    return value


def _integer(value: object, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field_name} must be an integer")
    return value


def _number(value: object, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field_name} must be numeric")
    return float(value)


def _exact_keys(
    payload: Mapping[str, object], expected: set[str], field_name: str
) -> None:
    if set(payload) != expected:
        raise ValueError(f"{field_name} has unexpected or missing fields")


def _action_spec_from_dict(value: object) -> ActionSpec:
    payload = _mapping(value, "action spec")
    _exact_keys(
        payload, {"action_id", "description", "payload_schema"}, "action spec"
    )
    return ActionSpec(
        action_id=_string(payload["action_id"], "action id"),
        description=(
            None
            if payload["description"] is None
            else _string(payload["description"], "action description")
        ),
        payload_schema=dict(_mapping(payload["payload_schema"], "payload schema")),
    )


def _action_event_from_dict(value: object) -> ActionEvent:
    payload = _mapping(value, "action event")
    _exact_keys(
        payload,
        {"actor_id", "action_id", "payload", "public_observation"},
        "action event",
    )
    return ActionEvent(
        actor_id=_string(payload["actor_id"], "actor id"),
        action_id=_string(payload["action_id"], "event action id"),
        payload=dict(_mapping(payload["payload"], "action event payload")),
        public_observation=dict(
            _mapping(payload["public_observation"], "public observation")
        ),
    )


def _agent_input_from_dict(value: object) -> AgentInput:
    payload = _mapping(value, "agent input")
    _exact_keys(
        payload,
        {
            "environment_id",
            "episode_id",
            "step",
            "observation",
            "information_state",
            "legal_actions",
            "action_history",
            "natural_language_rules",
        },
        "agent input",
    )
    return AgentInput(
        environment_id=_string(payload["environment_id"], "environment id"),
        episode_id=_string(payload["episode_id"], "episode id"),
        step=_integer(payload["step"], "step"),
        observation=dict(_mapping(payload["observation"], "observation")),
        information_state=dict(
            _mapping(payload["information_state"], "information state")
        ),
        legal_actions=tuple(
            _action_spec_from_dict(item)
            for item in _sequence(payload["legal_actions"], "legal actions")
        ),
        action_history=tuple(
            _action_event_from_dict(item)
            for item in _sequence(payload["action_history"], "action history")
        ),
        natural_language_rules=(
            None
            if payload["natural_language_rules"] is None
            else _string(payload["natural_language_rules"], "natural-language rules")
        ),
    )


def _agent_decision_from_dict(value: object) -> AgentDecision:
    payload = _mapping(value, "agent decision")
    _exact_keys(
        payload,
        {"action_id", "confidence", "payload", "belief"},
        "agent decision",
    )
    belief_payload = payload["belief"]
    belief = None
    if belief_payload is not None:
        belief_object = _mapping(belief_payload, "belief")
        _exact_keys(belief_object, {"target", "probabilities"}, "belief")
        belief = BeliefOutput(
            target=_string(belief_object["target"], "belief target"),
            probabilities={
                _string(label, "belief state label"): _number(
                    probability, "belief probability"
                )
                for label, probability in _mapping(
                    belief_object["probabilities"], "belief probabilities"
                ).items()
            },
        )
    return AgentDecision(
        action_id=_string(payload["action_id"], "decision action id"),
        confidence=_number(payload["confidence"], "decision confidence"),
        payload=dict(_mapping(payload["payload"], "decision payload")),
        belief=belief,
    )


@dataclass(frozen=True, slots=True)
class StepResult:
    """Public transition plus evaluator-only metrics for one decision."""

    outcome: Mapping[str, object]
    evaluation: Mapping[str, object]


class BenchmarkAdapter(Protocol):
    """Small environment boundary required by :func:`run_episode`."""

    environment_id: str
    episode_id: str
    evidence_level: EvidenceLevel

    @property
    def terminal(self) -> bool: ...

    def decision_input(self) -> AgentInput: ...

    def apply_decision(self, decision: AgentDecision) -> StepResult: ...

    def result(self) -> Mapping[str, object]: ...


@dataclass(frozen=True, slots=True)
class TraceStep:
    decision_input: AgentInput
    decision: AgentDecision
    agent_telemetry: Mapping[str, object]
    outcome: Mapping[str, object]
    evaluation: Mapping[str, object]


@dataclass(frozen=True, slots=True)
class EpisodeTrace:
    """Replayable record without private reasoning text or hidden-state leakage."""

    environment_id: str
    episode_id: str
    agent_id: str
    agent_metadata: Mapping[str, object]
    evidence_level: EvidenceLevel
    steps: tuple[TraceStep, ...]
    result: Mapping[str, object]

    def __post_init__(self) -> None:
        if not self.environment_id or not self.episode_id or not self.agent_id:
            raise ValueError("trace environment, episode, and agent ids cannot be empty")
        for index, step in enumerate(self.steps):
            decision_input = step.decision_input
            if decision_input.environment_id != self.environment_id:
                raise ValueError(f"trace step {index} environment id does not match")
            if decision_input.episode_id != self.episode_id:
                raise ValueError(f"trace step {index} episode id does not match")
            if decision_input.step != index:
                raise ValueError(f"trace step {index} has a non-contiguous step number")
            validate_decision(decision_input, step.decision)

    def as_dict(self) -> dict[str, object]:
        return {
            "schemaVersion": TRACE_SCHEMA_VERSION,
            "environmentId": self.environment_id,
            "episodeId": self.episode_id,
            "agentId": self.agent_id,
            "agentMetadata": dict(self.agent_metadata),
            "evidenceLevel": self.evidence_level.value,
            "steps": [
                {
                    "input": asdict(step.decision_input),
                    "decision": asdict(step.decision),
                    "agentTelemetry": dict(step.agent_telemetry),
                    "outcome": dict(step.outcome),
                    "evaluation": dict(step.evaluation),
                }
                for step in self.steps
            ],
            "result": dict(self.result),
        }

    @classmethod
    def from_dict(cls, value: object) -> EpisodeTrace:
        """Validate and reconstruct a trace previously emitted by :meth:`as_dict`."""

        payload = _mapping(value, "episode trace")
        _exact_keys(
            payload,
            {
                "schemaVersion",
                "environmentId",
                "episodeId",
                "agentId",
                "agentMetadata",
                "evidenceLevel",
                "steps",
                "result",
            },
            "episode trace",
        )
        if payload["schemaVersion"] != TRACE_SCHEMA_VERSION:
            raise ValueError(f"unsupported trace schema: {payload['schemaVersion']}")
        steps: list[TraceStep] = []
        for index, raw_step in enumerate(_sequence(payload["steps"], "trace steps")):
            step = _mapping(raw_step, f"trace step {index}")
            _exact_keys(
                step,
                {"input", "decision", "agentTelemetry", "outcome", "evaluation"},
                f"trace step {index}",
            )
            steps.append(
                TraceStep(
                    decision_input=_agent_input_from_dict(step["input"]),
                    decision=_agent_decision_from_dict(step["decision"]),
                    agent_telemetry=dict(
                        _mapping(step["agentTelemetry"], "agent telemetry")
                    ),
                    outcome=dict(_mapping(step["outcome"], "step outcome")),
                    evaluation=dict(
                        _mapping(step["evaluation"], "step evaluation")
                    ),
                )
            )
        return cls(
            environment_id=_string(payload["environmentId"], "environment id"),
            episode_id=_string(payload["episodeId"], "episode id"),
            agent_id=_string(payload["agentId"], "agent id"),
            agent_metadata=dict(
                _mapping(payload["agentMetadata"], "agent metadata")
            ),
            evidence_level=EvidenceLevel(
                _string(payload["evidenceLevel"], "evidence level")
            ),
            steps=tuple(steps),
            result=dict(_mapping(payload["result"], "episode result")),
        )

    @classmethod
    def from_json(cls, source: str) -> EpisodeTrace:
        return cls.from_dict(json.loads(source))

    @classmethod
    def read_json(cls, path: str | Path) -> EpisodeTrace:
        return cls.from_json(Path(path).read_text(encoding="utf-8"))

    def to_json(self, *, indent: int | None = 2) -> str:
        return json.dumps(
            self.as_dict(), indent=indent, sort_keys=True, allow_nan=False
        )

    def write_json(self, path: str | Path) -> Path:
        destination = Path(path)
        destination.write_text(self.to_json() + "\n", encoding="utf-8")
        return destination


def run_episode(
    adapter: BenchmarkAdapter,
    agent: StrategicAgent,
    *,
    agent_id: str,
    agent_metadata: Mapping[str, object] | None = None,
    max_steps: int = 100,
) -> EpisodeTrace:
    """Run one adapter-agent episode and retain every observable decision."""

    if not agent_id:
        raise ValueError("agent_id cannot be empty")
    if max_steps < 1:
        raise ValueError("max_steps must be positive")
    steps: list[TraceStep] = []
    while not adapter.terminal:
        if len(steps) >= max_steps:
            raise RuntimeError(f"episode exceeded max_steps={max_steps}")
        decision_input = adapter.decision_input()
        decision = agent.choose_action(decision_input)
        validate_decision(decision_input, decision)
        telemetry_provider = getattr(agent, "decision_telemetry", None)
        agent_telemetry = (
            dict(telemetry_provider()) if callable(telemetry_provider) else {}
        )
        transition = adapter.apply_decision(decision)
        steps.append(
            TraceStep(
                decision_input,
                decision,
                agent_telemetry,
                transition.outcome,
                transition.evaluation,
            )
        )
    return EpisodeTrace(
        adapter.environment_id,
        adapter.episode_id,
        agent_id,
        dict(agent_metadata or {}),
        adapter.evidence_level,
        tuple(steps),
        adapter.result(),
    )
