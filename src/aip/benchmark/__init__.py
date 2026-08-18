"""Lightweight cross-game strategic-intelligence benchmark contracts."""

from aip.benchmark.catalog import (
    V1_ENVIRONMENTS,
    BenchmarkEnvironmentSpec,
    GroundTruthProfile,
    environment_spec,
)
from aip.benchmark.guess_who import (
    GuessWhoBenchmarkAdapter,
    GuessWhoSuiteSummary,
    OptimalGuessWhoAgent,
    summarize_guess_who_traces,
)
from aip.benchmark.runner import (
    BenchmarkAdapter,
    EpisodeTrace,
    StepResult,
    TraceStep,
    run_episode,
)
from aip.benchmark.types import (
    ActionEvent,
    ActionSpec,
    AgentDecision,
    AgentInput,
    BeliefOutput,
    EvidenceLevel,
    StrategicAgent,
    StrategicCapability,
    validate_decision,
)

__all__ = [
    "ActionEvent",
    "ActionSpec",
    "AgentDecision",
    "AgentInput",
    "BeliefOutput",
    "BenchmarkAdapter",
    "BenchmarkEnvironmentSpec",
    "EpisodeTrace",
    "EvidenceLevel",
    "GroundTruthProfile",
    "GuessWhoBenchmarkAdapter",
    "GuessWhoSuiteSummary",
    "OptimalGuessWhoAgent",
    "StrategicAgent",
    "StrategicCapability",
    "StepResult",
    "TraceStep",
    "V1_ENVIRONMENTS",
    "environment_spec",
    "run_episode",
    "summarize_guess_who_traces",
    "validate_decision",
]
