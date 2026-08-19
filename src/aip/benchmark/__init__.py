"""Lightweight cross-game strategic-intelligence benchmark contracts."""

from aip.benchmark.catalog import (
    V1_ENVIRONMENTS,
    BenchmarkEnvironmentSpec,
    GroundTruthProfile,
    environment_spec,
)
from aip.benchmark.baselines import GENERIC_WEAK_METADATA, GenericWeakRandomAgent
from aip.benchmark.guess_who import (
    ORACLE_METADATA,
    SINGLE_GAME_PROMPT,
    SINGLE_GAME_PROMPT_METADATA,
    GuessWhoBenchmarkAdapter,
    GuessWhoBaselineReport,
    GuessWhoSingleGamePromptBaseline,
    GuessWhoSuiteSummary,
    OptimalGuessWhoAgent,
    compare_guess_who_baselines,
    run_guess_who_baseline,
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
    "GENERIC_WEAK_METADATA",
    "GenericWeakRandomAgent",
    "GroundTruthProfile",
    "GuessWhoBenchmarkAdapter",
    "GuessWhoBaselineReport",
    "GuessWhoSingleGamePromptBaseline",
    "GuessWhoSuiteSummary",
    "OptimalGuessWhoAgent",
    "ORACLE_METADATA",
    "SINGLE_GAME_PROMPT",
    "SINGLE_GAME_PROMPT_METADATA",
    "StrategicAgent",
    "StrategicCapability",
    "StepResult",
    "TraceStep",
    "V1_ENVIRONMENTS",
    "environment_spec",
    "compare_guess_who_baselines",
    "run_guess_who_baseline",
    "run_episode",
    "summarize_guess_who_traces",
    "validate_decision",
]
