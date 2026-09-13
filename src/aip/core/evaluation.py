"""Independent equilibrium evaluation and evidence promotion contracts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from hashlib import sha256
import json
from math import isfinite
from typing import Hashable, Mapping, Protocol


Action = Hashable
InformationSetKey = tuple[int, Hashable]
StrategyProfile = Mapping[InformationSetKey, Mapping[Action, float]]
ActionValueReport = Mapping[InformationSetKey, Mapping[Action, float]]


class EquilibriumEvaluator(Protocol):
    """Independent oracle boundary; implementations must not inspect trainer regret."""

    evaluator_id: str

    def expected_value(self, profile: StrategyProfile) -> float: ...

    def best_response(self, profile: StrategyProfile, player: int) -> float: ...

    def nash_conv(self, profile: StrategyProfile) -> float: ...

    def exploitability(self, profile: StrategyProfile) -> float: ...

    def action_values(self, profile: StrategyProfile) -> ActionValueReport: ...


@dataclass(frozen=True, slots=True)
class IndependentEvaluationReport:
    evaluator_id: str
    evaluator_method: str
    profile_fingerprint: str
    expected_value_to_player_0: float
    best_response_player_0: float
    best_response_player_1: float
    player_0_deviation_gain: float
    player_1_deviation_gain: float
    nash_conv: float
    exploitability: float
    maximum_unilateral_deviation_gain: float
    action_values: ActionValueReport
    passed: bool
    failures: tuple[str, ...]

    def __post_init__(self) -> None:
        numeric = (
            self.expected_value_to_player_0,
            self.best_response_player_0,
            self.best_response_player_1,
            self.player_0_deviation_gain,
            self.player_1_deviation_gain,
            self.nash_conv,
            self.exploitability,
            self.maximum_unilateral_deviation_gain,
        )
        if any(not isfinite(value) for value in numeric):
            raise ValueError("independent evaluation metrics must be finite")
        if not self.action_values or any(
            value < -1e-12
            for value in (
                self.player_0_deviation_gain,
                self.player_1_deviation_gain,
                self.nash_conv,
                self.exploitability,
                self.maximum_unilateral_deviation_gain,
            )
        ):
            raise ValueError("independent deviation metrics cannot be negative")
        if abs(self.nash_conv - (
            self.player_0_deviation_gain + self.player_1_deviation_gain
        )) > 1e-10:
            raise ValueError("independent NashConv is inconsistent")
        if abs(self.exploitability - self.nash_conv / 2.0) > 1e-10:
            raise ValueError("independent exploitability is inconsistent")
        if any(
            not distribution
            or any(not isfinite(value) for value in distribution.values())
            for distribution in self.action_values.values()
        ):
            raise ValueError("independent action values must be nonempty and finite")
        if self.passed == bool(self.failures):
            raise ValueError("independent evaluation pass state is inconsistent")

    def to_artifact(self) -> dict[str, object]:
        return {
            "evaluator_id": self.evaluator_id,
            "evaluator_method": self.evaluator_method,
            "profile_fingerprint": self.profile_fingerprint,
            "expected_value_to_player_0": self.expected_value_to_player_0,
            "best_response_player_0": self.best_response_player_0,
            "best_response_player_1": self.best_response_player_1,
            "nash_conv": self.nash_conv,
            "exploitability": self.exploitability,
            "player_0_deviation_gain": self.player_0_deviation_gain,
            "player_1_deviation_gain": self.player_1_deviation_gain,
            "maximum_unilateral_deviation_gain": (
                self.maximum_unilateral_deviation_gain
            ),
            "action_values": [
                {
                    "player": key[0],
                    "information_set": repr(key[1]),
                    "values": [
                        {"action": repr(action), "value": value}
                        for action, value in distribution.items()
                    ],
                }
                for key, distribution in sorted(
                    self.action_values.items(), key=lambda item: repr(item[0])
                )
            ],
            "passed": self.passed,
            "failures": list(self.failures),
        }


class PromotionLevel(IntEnum):
    CANDIDATE = 0
    LABELED = 1
    INDEPENDENTLY_CHECKED = 2
    VERIFIED = 3
    FROZEN = 4

    @property
    def artifact_name(self) -> str:
        return self.name.lower()


def strategy_profile_fingerprint(profile: StrategyProfile) -> str:
    """Hash a normalized behavioral profile so reports cannot attach elsewhere."""

    normalized = [
        {
            "player": key[0],
            "information_set": repr(key[1]),
            "distribution": [
                [repr(action), format(float(probability), ".17g")]
                for action, probability in sorted(
                    distribution.items(), key=lambda item: repr(item[0])
                )
            ],
        }
        for key, distribution in sorted(profile.items(), key=lambda item: repr(item[0]))
    ]
    payload = json.dumps(normalized, sort_keys=True, separators=(",", ":"))
    return sha256(payload.encode("utf-8")).hexdigest()


def run_independent_evaluation(
    evaluator: EquilibriumEvaluator,
    profile: StrategyProfile,
    *,
    maximum_exploitability: float,
) -> IndependentEvaluationReport:
    """Evaluate a profile without accepting any trainer-owned diagnostics."""

    if not isfinite(maximum_exploitability) or maximum_exploitability < 0:
        raise ValueError("maximum exploitability must be finite and nonnegative")
    value = evaluator.expected_value(profile)
    response_zero = evaluator.best_response(profile, 0)
    response_one = evaluator.best_response(profile, 1)
    gain_zero = max(0.0, response_zero - value)
    gain_one = max(0.0, response_one + value)
    nash_conv = gain_zero + gain_one
    exploitability = nash_conv / 2.0
    if (
        abs(evaluator.nash_conv(profile) - nash_conv) > 1e-10
        or abs(evaluator.exploitability(profile) - exploitability) > 1e-10
    ):
        raise ValueError("independent evaluator methods returned inconsistent metrics")
    failures = (
        ("exploitability_above_threshold",)
        if exploitability > maximum_exploitability
        else ()
    )
    return IndependentEvaluationReport(
        evaluator_id=evaluator.evaluator_id,
        evaluator_method="independent_game_tree_best_response",
        profile_fingerprint=strategy_profile_fingerprint(profile),
        expected_value_to_player_0=value,
        best_response_player_0=response_zero,
        best_response_player_1=response_one,
        player_0_deviation_gain=gain_zero,
        player_1_deviation_gain=gain_one,
        nash_conv=nash_conv,
        exploitability=exploitability,
        maximum_unilateral_deviation_gain=max(gain_zero, gain_one),
        action_values=evaluator.action_values(profile),
        passed=not failures,
        failures=failures,
    )


@dataclass(frozen=True, slots=True)
class PromotionEvidence:
    artifact_complete: bool = False
    artifact_profile_fingerprint: str | None = None
    independent_report: IndependentEvaluationReport | None = None
    cross_method_agreement: bool = False
    reproducible: bool = False
    artifact_frozen: bool = False


@dataclass(frozen=True, slots=True)
class PromotionDecision:
    level: PromotionLevel
    failures: tuple[str, ...]

    @property
    def epsilon_gto_runtime_allowed(self) -> bool:
        return self.level >= PromotionLevel.INDEPENDENTLY_CHECKED

    def to_artifact(self) -> dict[str, object]:
        return {
            "level": self.level.artifact_name,
            "epsilon_gto_runtime_allowed": self.epsilon_gto_runtime_allowed,
            "failures": list(self.failures),
        }


def decide_promotion(evidence: PromotionEvidence) -> PromotionDecision:
    """Return the highest contiguous evidence level; promotion never skips a gate."""

    if not evidence.artifact_complete:
        return PromotionDecision(PromotionLevel.CANDIDATE, ("artifact_incomplete",))
    if not evidence.artifact_profile_fingerprint:
        return PromotionDecision(
            PromotionLevel.CANDIDATE, ("artifact_profile_fingerprint_missing",)
        )
    if evidence.independent_report is None or not evidence.independent_report.passed:
        return PromotionDecision(
            PromotionLevel.LABELED, ("independent_evaluation_not_passed",)
        )
    if (
        evidence.independent_report.profile_fingerprint
        != evidence.artifact_profile_fingerprint
    ):
        return PromotionDecision(
            PromotionLevel.LABELED, ("independent_report_profile_mismatch",)
        )
    if not evidence.cross_method_agreement:
        return PromotionDecision(
            PromotionLevel.INDEPENDENTLY_CHECKED,
            ("cross_method_agreement_required",),
        )
    if not evidence.reproducible or not evidence.artifact_frozen:
        failures = []
        if not evidence.reproducible:
            failures.append("reproducibility_required")
        if not evidence.artifact_frozen:
            failures.append("artifact_freeze_required")
        return PromotionDecision(PromotionLevel.VERIFIED, tuple(failures))
    return PromotionDecision(PromotionLevel.FROZEN, ())
