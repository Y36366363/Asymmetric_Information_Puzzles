"""Minimal episode runner and auditable JSON trace for benchmark adapters."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Mapping, Protocol

from aip.benchmark.types import (
    AgentDecision,
    AgentInput,
    EvidenceLevel,
    StrategicAgent,
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

    def as_dict(self) -> dict[str, object]:
        return {
            "schemaVersion": "aip-benchmark-trace-v0",
            "environmentId": self.environment_id,
            "episodeId": self.episode_id,
            "agentId": self.agent_id,
            "agentMetadata": dict(self.agent_metadata),
            "evidenceLevel": self.evidence_level.value,
            "steps": [
                {
                    "input": asdict(step.decision_input),
                    "decision": asdict(step.decision),
                    "outcome": dict(step.outcome),
                    "evaluation": dict(step.evaluation),
                }
                for step in self.steps
            ],
            "result": dict(self.result),
        }

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
        transition = adapter.apply_decision(decision)
        steps.append(
            TraceStep(
                decision_input,
                decision,
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
