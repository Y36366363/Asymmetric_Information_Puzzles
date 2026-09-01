"""Preregistered experiment grid and evidence-aware metric eligibility."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from itertools import product
from statistics import mean, stdev
from typing import Iterable

from aip.benchmark.catalog import BenchmarkEnvironmentSpec, V1_ENVIRONMENTS
from aip.benchmark.guess_who import (
    GuessWhoBaselineReport,
    GuessWhoSuiteSummary,
    compare_guess_who_baselines,
)
from aip.benchmark.types import EvidenceLevel, StrategicCapability


@dataclass(frozen=True, slots=True)
class MetricEligibility:
    """Metrics that may be named literally for one environment.

    False means unavailable under the current reference—not a zero score.
    """

    regret: bool
    exploitability: bool
    policy_agreement: str
    belief_calibration: bool
    information_efficiency: bool
    opponent_shift_robustness: bool


def metric_eligibility(spec: BenchmarkEnvironmentSpec) -> MetricEligibility:
    ground_truth = spec.ground_truth
    if spec.evidence_level is EvidenceLevel.PROVED_OPTIMAL:
        agreement = "exact_optimal_policy_agreement"
    elif spec.evidence_level is EvidenceLevel.EQUILIBRIUM_BACKED:
        agreement = "equilibrium_support_or_distribution_agreement"
    elif spec.evidence_level is EvidenceLevel.STRONG_HEURISTIC:
        agreement = "heuristic_reference_agreement"
    else:
        agreement = "none"
    return MetricEligibility(
        regret=ground_truth.computable_regret,
        exploitability=ground_truth.computable_exploitability,
        policy_agreement=agreement,
        belief_calibration=ground_truth.belief_ground_truth,
        information_efficiency=(
            StrategicCapability.INFORMATION_ACQUISITION in spec.capabilities
            or StrategicCapability.BELIEF_UPDATING in spec.capabilities
        ),
        opponent_shift_robustness=(
            StrategicCapability.OPPONENT_MODELLING in spec.capabilities
        ),
    )


@dataclass(frozen=True, slots=True)
class AblationCondition:
    condition_id: str
    game_specific_prompt: bool
    memory: bool
    cross_game_experience: bool

    def __post_init__(self) -> None:
        if not self.condition_id:
            raise ValueError("condition_id cannot be empty")

    @property
    def eligible_for_primary_transfer_comparison(self) -> bool:
        """Target-game prompting is a supervised ceiling, never transfer evidence."""

        return not self.game_specific_prompt


V1_ABLATIONS = tuple(
    AblationCondition(
        condition_id=(
            f"prompt-{'single-game' if prompt else 'generic'}"
            f"__memory-{'on' if memory else 'off'}"
            f"__cross-game-{'on' if experience else 'off'}"
        ),
        game_specific_prompt=prompt,
        memory=memory,
        cross_game_experience=experience,
    )
    for prompt, memory, experience in product((False, True), repeat=3)
)


@dataclass(frozen=True, slots=True)
class TrialSpec:
    trial_id: str
    environment_id: str
    model_id: str
    condition_id: str
    seed: int
    repeat: int
    opponent_shift: str
    held_out: bool
    eligible_for_primary_transfer_comparison: bool


@dataclass(frozen=True, slots=True)
class EvaluationProtocol:
    """Frozen axes for a comparable cross-game experiment."""

    protocol_id: str
    model_ids: tuple[str, ...]
    seeds: tuple[int, ...]
    repeats: int
    opponent_shifts: tuple[str, ...]
    conditions: tuple[AblationCondition, ...] = V1_ABLATIONS
    environments: tuple[BenchmarkEnvironmentSpec, ...] = V1_ENVIRONMENTS

    def __post_init__(self) -> None:
        if not self.protocol_id or not self.model_ids or not self.seeds:
            raise ValueError("protocol id, models, and seeds cannot be empty")
        if self.repeats < 1:
            raise ValueError("repeats must be positive")
        for name, values in (
            ("model ids", self.model_ids),
            ("seeds", self.seeds),
            ("opponent shifts", self.opponent_shifts),
            ("condition ids", tuple(item.condition_id for item in self.conditions)),
            ("environment ids", tuple(item.environment_id for item in self.environments)),
        ):
            if not values or len(values) != len(set(values)):
                raise ValueError(f"{name} must be nonempty and unique")
        held_out = tuple(spec for spec in self.environments if spec.held_out)
        if len(held_out) != 1:
            raise ValueError("protocol requires exactly one held-out environment")

    @property
    def held_out_environment_id(self) -> str:
        return next(spec.environment_id for spec in self.environments if spec.held_out)

    @property
    def training_environment_ids(self) -> tuple[str, ...]:
        return tuple(spec.environment_id for spec in self.environments if not spec.held_out)

    def trials(self) -> tuple[TrialSpec, ...]:
        trials: list[TrialSpec] = []
        for repeat, model_id, spec, condition, seed, shift in product(
            range(self.repeats),
            self.model_ids,
            self.environments,
            self.conditions,
            self.seeds,
            self.opponent_shifts,
        ):
            transfer_comparison = (
                spec.held_out
                and condition.eligible_for_primary_transfer_comparison
            )
            trial_id = ":".join(
                (
                    self.protocol_id,
                    f"repeat-{repeat}",
                    model_id,
                    spec.environment_id,
                    condition.condition_id,
                    f"seed-{seed}",
                    shift,
                )
            )
            trials.append(
                TrialSpec(
                    trial_id=trial_id,
                    environment_id=spec.environment_id,
                    model_id=model_id,
                    condition_id=condition.condition_id,
                    seed=seed,
                    repeat=repeat,
                    opponent_shift=shift,
                    held_out=spec.held_out,
                    eligible_for_primary_transfer_comparison=transfer_comparison,
                )
            )
        return tuple(trials)

    def as_dict(self) -> dict[str, object]:
        return {
            "protocolId": self.protocol_id,
            "models": list(self.model_ids),
            "seeds": list(self.seeds),
            "repeats": self.repeats,
            "opponentShifts": list(self.opponent_shifts),
            "trainingEnvironments": list(self.training_environment_ids),
            "heldOutEnvironment": self.held_out_environment_id,
            "conditions": [asdict(item) for item in self.conditions],
            "metricEligibility": {
                spec.environment_id: {
                    "evidenceLevel": spec.evidence_level.value,
                    **asdict(metric_eligibility(spec)),
                }
                for spec in self.environments
            },
            "trialCount": len(self.trials()),
        }


def _summary_dict(summary: GuessWhoSuiteSummary) -> dict[str, object]:
    return asdict(summary)


def _sample_spread(values: tuple[float, ...]) -> float:
    return stdev(values) if len(values) > 1 else 0.0


def run_repeated_guess_who_pilot(
    *, repeats: int = 4, seeds_per_repeat: int = 8, base_seed: int = 0
) -> dict[str, object]:
    """Offline exact-ground-truth pilot for repeated-run aggregation.

    Each repeat receives a disjoint seed block. The prompted proxy is deterministic;
    only the generic weak policy is randomized. This is a runner validation, not a
    held-out transfer or multi-model result.
    """

    if repeats < 2:
        raise ValueError("pilot requires at least two repeats")
    if seeds_per_repeat < 1:
        raise ValueError("seeds_per_repeat must be positive")
    reports: list[GuessWhoBaselineReport] = []
    seed_blocks: list[tuple[int, ...]] = []
    for repeat in range(repeats):
        start = base_seed + repeat * seeds_per_repeat
        seeds = tuple(range(start, start + seeds_per_repeat))
        seed_blocks.append(seeds)
        reports.append(compare_guess_who_baselines(weak_seeds=seeds))

    turn_gains = tuple(report.prompted_turn_gain for report in reports)
    agreement_gains = tuple(report.prompted_agreement_gain for report in reports)
    regret_reductions = tuple(report.prompted_regret_reduction for report in reports)
    prompted_brier = tuple(
        float(report.single_game_prompted.mean_belief_brier)
        for report in reports
        if report.single_game_prompted.mean_belief_brier is not None
    )
    return {
        "reportSchemaVersion": "aip-repeated-pilot-v1",
        "environmentId": "guess-who",
        "evidenceLevel": EvidenceLevel.PROVED_OPTIMAL.value,
        "purpose": "runner_and_metric_discrimination_only",
        "notEvidenceFor": ["held_out_transfer", "multi_model_comparison"],
        "repeats": repeats,
        "seedsPerRepeat": seeds_per_repeat,
        "seedBlocks": [list(block) for block in seed_blocks],
        "replicates": [
            {
                "repeat": index,
                "seeds": list(seed_blocks[index]),
                "oracle": _summary_dict(report.oracle),
                "singleGamePromptedProxy": _summary_dict(
                    report.single_game_prompted
                ),
                "genericWeak": _summary_dict(report.generic_weak),
                "pairedDifferences": {
                    "turnGain": report.prompted_turn_gain,
                    "policyAgreementGain": report.prompted_agreement_gain,
                    "regretReduction": report.prompted_regret_reduction,
                },
            }
            for index, report in enumerate(reports)
        ],
        "aggregate": {
            "turnGainMean": mean(turn_gains),
            "turnGainSampleSd": _sample_spread(turn_gains),
            "policyAgreementGainMean": mean(agreement_gains),
            "policyAgreementGainSampleSd": _sample_spread(agreement_gains),
            "regretReductionMean": mean(regret_reductions),
            "regretReductionSampleSd": _sample_spread(regret_reductions),
            "singleGamePromptedBeliefBrierMean": mean(prompted_brier),
            "genericWeakBeliefBrier": None,
        },
    }


def default_protocol(model_ids: Iterable[str]) -> EvaluationProtocol:
    return EvaluationProtocol(
        protocol_id="aip-cross-game-v1",
        model_ids=tuple(model_ids),
        seeds=(101, 211, 307, 401),
        repeats=3,
        opponent_shifts=("reference", "naive", "adaptive", "adversarial"),
    )
