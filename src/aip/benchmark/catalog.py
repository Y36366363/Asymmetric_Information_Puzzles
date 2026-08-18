"""Versioned environment catalog for the first AIP generalization benchmark."""

from __future__ import annotations

from dataclasses import dataclass

from aip.benchmark.types import EvidenceLevel, StrategicCapability


@dataclass(frozen=True, slots=True)
class GroundTruthProfile:
    exact_optimal_policy: bool = False
    equilibrium_policy: bool = False
    computable_regret: bool = False
    computable_exploitability: bool = False
    belief_ground_truth: bool = False
    heuristic_ground_truth: bool = False


@dataclass(frozen=True, slots=True)
class BenchmarkEnvironmentSpec:
    environment_id: str
    capabilities: frozenset[StrategicCapability]
    evidence_level: EvidenceLevel
    ground_truth: GroundTruthProfile
    role: str
    held_out: bool = False
    evidence_note: str = ""

    def __post_init__(self) -> None:
        if not self.environment_id or not self.role or not self.capabilities:
            raise ValueError("benchmark specs need id, role, and capabilities")
        if self.evidence_level is EvidenceLevel.PROVED_OPTIMAL:
            if not self.ground_truth.exact_optimal_policy:
                raise ValueError("proved-optimal specs need an exact optimal policy")
        if self.evidence_level is EvidenceLevel.EQUILIBRIUM_BACKED:
            if not self.ground_truth.equilibrium_policy:
                raise ValueError("equilibrium-backed specs need an equilibrium policy")
        if self.evidence_level is EvidenceLevel.STRONG_HEURISTIC:
            if not self.ground_truth.heuristic_ground_truth:
                raise ValueError("heuristic specs need a heuristic reference")


CAP = StrategicCapability

V1_ENVIRONMENTS = (
    BenchmarkEnvironmentSpec(
        environment_id="kuhn-poker",
        capabilities=frozenset(
            {
                CAP.HIDDEN_STATE_REASONING,
                CAP.BELIEF_UPDATING,
                CAP.MIXED_STRATEGY,
                CAP.OPPONENT_MODELLING,
                CAP.DECEPTION_BLUFFING,
                CAP.RISK_SENSITIVE_DECISION_MAKING,
            }
        ),
        evidence_level=EvidenceLevel.EQUILIBRIUM_BACKED,
        ground_truth=GroundTruthProfile(
            equilibrium_policy=True,
            computable_regret=True,
            computable_exploitability=True,
            belief_ground_truth=True,
        ),
        role="equilibrium anchor",
        evidence_note="Exact three-card zero-sum equilibrium with exhaustive best responses.",
    ),
    BenchmarkEnvironmentSpec(
        environment_id="goofspiel",
        capabilities=frozenset(
            {
                CAP.MIXED_STRATEGY,
                CAP.OPPONENT_MODELLING,
                CAP.ADVERSARIAL_SEARCH,
            }
        ),
        evidence_level=EvidenceLevel.EQUILIBRIUM_BACKED,
        ground_truth=GroundTruthProfile(
            equilibrium_policy=True,
            computable_regret=True,
            computable_exploitability=True,
        ),
        role="finite-horizon mixed-strategy anchor",
        evidence_note="Every public four-card state has an exact zero-sum policy.",
    ),
    BenchmarkEnvironmentSpec(
        environment_id="guess-who",
        capabilities=frozenset(
            {
                CAP.HIDDEN_STATE_REASONING,
                CAP.BELIEF_UPDATING,
                CAP.INFORMATION_ACQUISITION,
            }
        ),
        evidence_level=EvidenceLevel.PROVED_OPTIMAL,
        ground_truth=GroundTruthProfile(
            exact_optimal_policy=True,
            computable_regret=True,
            belief_ground_truth=True,
        ),
        role="exact information-acquisition anchor",
        evidence_note="Dynamic programming proves the minimum expected question policy.",
    ),
    BenchmarkEnvironmentSpec(
        environment_id="worm",
        capabilities=frozenset(
            {
                CAP.HIDDEN_STATE_REASONING,
                CAP.BELIEF_UPDATING,
                CAP.ADVERSARIAL_SEARCH,
            }
        ),
        evidence_level=EvidenceLevel.PROVED_OPTIMAL,
        ground_truth=GroundTruthProfile(
            exact_optimal_policy=True,
            computable_regret=True,
            belief_ground_truth=True,
        ),
        role="worst-case hidden-state anchor",
        evidence_note="Breadth-first belief search proves a shortest guaranteed sequence.",
    ),
    BenchmarkEnvironmentSpec(
        environment_id="liars-dice",
        capabilities=frozenset(
            {
                CAP.HIDDEN_STATE_REASONING,
                CAP.BELIEF_UPDATING,
                CAP.OPPONENT_MODELLING,
                CAP.DECEPTION_BLUFFING,
                CAP.RISK_SENSITIVE_DECISION_MAKING,
            }
        ),
        evidence_level=EvidenceLevel.STRONG_HEURISTIC,
        ground_truth=GroundTruthProfile(
            belief_ground_truth=True,
            heuristic_ground_truth=True,
        ),
        role="calibration and opponent-shift probe",
        evidence_note="Claim probabilities are exact; bidding and challenge policy is heuristic.",
    ),
    BenchmarkEnvironmentSpec(
        environment_id="mastermind",
        capabilities=frozenset(
            {
                CAP.HIDDEN_STATE_REASONING,
                CAP.BELIEF_UPDATING,
                CAP.INFORMATION_ACQUISITION,
            }
        ),
        evidence_level=EvidenceLevel.STRONG_HEURISTIC,
        ground_truth=GroundTruthProfile(
            belief_ground_truth=True,
            heuristic_ground_truth=True,
        ),
        role="held-out transfer environment",
        held_out=True,
        evidence_note="Candidate filtering is exact; the bounded one-step minimax policy is heuristic.",
    ),
)


def environment_spec(environment_id: str) -> BenchmarkEnvironmentSpec:
    try:
        return next(
            spec for spec in V1_ENVIRONMENTS if spec.environment_id == environment_id
        )
    except StopIteration as error:
        raise KeyError(environment_id) from error

