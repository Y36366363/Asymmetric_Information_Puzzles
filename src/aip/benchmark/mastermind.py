"""Held-out Mastermind adapter with exact beliefs and heuristic-only policy labels."""

from __future__ import annotations

import hashlib
import math
import re
from collections import Counter
from dataclasses import asdict, dataclass
from statistics import mean
from typing import Iterable, Mapping

from aip.benchmark.completion import GENERIC_STRATEGIC_PROMPT
from aip.benchmark.runner import EpisodeTrace, StepResult, run_episode
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
from aip.puzzles.mastermind import CodeFeedback, MastermindSolver


SUBMIT_GUESS = "submit_guess"
BELIEF_TARGET = "next_feedback"
LOG_LOSS_FLOOR = 1e-15

RULES = (
    "A hidden four-symbol sequence uses distinct decimal digits and may begin with "
    "zero. Submit one four-digit guess per turn. The public response reports how "
    "many digits are exact in both value and position and how many are present in "
    "a different position. Solve within ten guesses."
)

CROSS_GAME_MEMORY_V1 = """Reusable strategic principles learned before holdout:
- Maintain only hidden hypotheses consistent with every public observation.
- Prefer legal information-gathering actions that separate plausible hypotheses.
- Update beliefs after evidence rather than preserving an earlier narrative.
- Distinguish a proved optimum, an equilibrium, and an empirical heuristic.
- Report uncertainty honestly and never infer hidden state from identifiers.
"""


@dataclass(frozen=True, slots=True)
class FrozenTransferBundle:
    prompt: str
    memory: str
    source_environment_ids: tuple[str, ...]

    def manifest(self) -> dict[str, object]:
        return {
            "promptSha256": hashlib.sha256(self.prompt.encode()).hexdigest(),
            "memorySha256": hashlib.sha256(self.memory.encode()).hexdigest(),
            "sourceEnvironmentIds": list(self.source_environment_ids),
        }


FROZEN_TRANSFER_BUNDLE_V1 = FrozenTransferBundle(
    prompt=GENERIC_STRATEGIC_PROMPT,
    memory=CROSS_GAME_MEMORY_V1,
    source_environment_ids=(
        "guess-who",
        "worm",
        "kuhn-poker",
        "goofspiel",
        "liars-dice",
    ),
)
FROZEN_TRANSFER_MANIFEST_V1: Mapping[str, object] = {
    "promptSha256": "14a57d20cc29e6ed2ace8e2fea38d0a23beb9a9861738449613fd6eabd0d6320",
    "memorySha256": "4f3fcb87a8f4912a255d630c7dc4db140d3f15373567bec27222c20d30cffb7a",
    "sourceEnvironmentIds": [
        "guess-who",
        "worm",
        "kuhn-poker",
        "goofspiel",
        "liars-dice",
    ],
}

_TARGET_LEAK_PATTERNS = (
    r"\bmastermind\b",
    r"\bbulls?\s*(?:and|&)\s*cows?\b",
    r"\bsubmit_guess\b",
    r"\b5040\b|\b5,040\b",
    r"\b0123\b",
    r"four[- ]digit",
    r"distinct (?:decimal )?digits",
    r"exact (?:position|digit)",
    r"misplaced (?:digit|number)",
    r"worst[_ -]case[_ -]remaining",
)


@dataclass(frozen=True, slots=True)
class LeakageAudit:
    passed: bool
    findings: tuple[str, ...]
    manifest: Mapping[str, object]


def audit_mastermind_holdout(bundle: FrozenTransferBundle) -> LeakageAudit:
    """Reject target traces, examples, action recipes, and target-specific terms."""

    findings: list[str] = []
    manifest = bundle.manifest()
    for field, expected in FROZEN_TRANSFER_MANIFEST_V1.items():
        if manifest[field] != expected:
            findings.append(f"frozen transfer {field} drifted from v1 manifest")
    if "mastermind" in bundle.source_environment_ids:
        findings.append("held-out environment appears in source_environment_ids")
    material = f"{bundle.prompt}\n{bundle.memory}".casefold()
    for pattern in _TARGET_LEAK_PATTERNS:
        if re.search(pattern, material):
            findings.append(f"target-specific material matched /{pattern}/")
    return LeakageAudit(not findings, tuple(findings), manifest)


def _code_label(code: tuple[int, ...]) -> str:
    return "".join(str(value) for value in code)


def _feedback_label(feedback: CodeFeedback | tuple[int, int]) -> str:
    exact, misplaced = (
        feedback.as_tuple() if isinstance(feedback, CodeFeedback) else feedback
    )
    return f"exact={exact}|misplaced={misplaced}"


@dataclass(frozen=True, slots=True)
class MastermindSuiteSummary:
    episodes: int
    solved_rate: float
    mean_attempts: float
    worst_attempts: int
    heuristic_reference_agreement: float
    mean_worst_case_gap_to_heuristic: float
    belief_output_rate: float
    mean_belief_brier: float | None
    mean_belief_log_loss: float | None
    mean_predictive_tv_distance: float | None
    mean_information_efficiency_bits_per_guess: float


class MastermindBenchmarkAdapter:
    """Spoiler-safe held-out adapter.

    Candidate filtering and feedback probabilities are exact. The action reference
    is the existing bounded one-step minimax adviser, so disagreement is never
    reported as exact regret or exploitability.
    """

    environment_id = "mastermind"
    evidence_level = EvidenceLevel.STRONG_HEURISTIC

    def __init__(
        self,
        secret: tuple[int, ...] | str,
        *,
        episode_id: str = "mastermind:held-out:episode",
        include_rules: bool = True,
        solver: MastermindSolver | None = None,
    ) -> None:
        self.solver = solver or MastermindSolver()
        self.secret = self._parse_guess(secret)
        self.episode_id = episode_id
        self.include_rules = include_rules
        self._candidates = self.solver.all_codes
        self._history: list[ActionEvent] = []
        self._last_observation: Mapping[str, object] = {"kind": "start"}
        self._terminal = False
        self._solved = False
        self._information_gains: list[float] = []
        opening = self.solver.all_codes[0]
        self._feedback_labels = tuple(
            sorted(
                {
                    _feedback_label(self.solver.feedback(opening, candidate))
                    for candidate in self.solver.all_codes
                }
            )
        )

    def _parse_guess(self, raw: tuple[int, ...] | str | object) -> tuple[int, ...]:
        if isinstance(raw, str):
            if not re.fullmatch(r"\d+", raw):
                raise ValueError("guess must be a string of decimal digits")
            guess = tuple(int(value) for value in raw)
        elif isinstance(raw, (list, tuple)) and all(
            isinstance(value, int) and not isinstance(value, bool) for value in raw
        ):
            guess = tuple(raw)
        else:
            raise ValueError("guess must be a digit string or integer sequence")
        self.solver.rules.validate_guess(guess)
        return guess

    @property
    def terminal(self) -> bool:
        return self._terminal

    def decision_input(self) -> AgentInput:
        if self._terminal:
            raise RuntimeError("terminal episodes have no decision input")
        preview = [_code_label(code) for code in self._candidates[:12]]
        return AgentInput(
            environment_id=self.environment_id,
            episode_id=self.episode_id,
            step=len(self._history),
            observation=dict(self._last_observation),
            information_state={
                "candidateCount": len(self._candidates),
                "candidatePreview": preview,
                "candidatePreviewComplete": len(preview) == len(self._candidates),
                "attemptsRemaining": self.solver.rules.max_attempts - len(self._history),
                "beliefTarget": BELIEF_TARGET,
                "beliefStateLabels": list(self._feedback_labels),
                "referenceScope": "bounded_one_step_minimax_heuristic",
            },
            legal_actions=(
                ActionSpec(
                    SUBMIT_GUESS,
                    "Submit four distinct decimal digits as a string; leading zero is allowed.",
                    payload_schema={"guess": "four_distinct_digit_string"},
                ),
            ),
            action_history=tuple(self._history),
            natural_language_rules=RULES if self.include_rules else None,
        )

    def _partition(self, guess: tuple[int, ...]) -> Counter[tuple[int, int]]:
        return Counter(
            self.solver.feedback(guess, candidate).as_tuple()
            for candidate in self._candidates
        )

    def _belief_metrics(
        self,
        decision: AgentDecision,
        partition: Counter[tuple[int, int]],
        actual_feedback: CodeFeedback,
    ) -> dict[str, object]:
        if decision.belief is None:
            return {
                "beliefBrier": None,
                "beliefLogLoss": None,
                "trueFeedbackProbability": None,
                "beliefPredictiveTvDistance": None,
                "zeroProbabilityOnTruth": None,
            }
        if decision.belief.target != BELIEF_TARGET:
            raise ValueError(f"Mastermind belief target must be {BELIEF_TARGET}")
        unknown = set(decision.belief.probabilities).difference(self._feedback_labels)
        if unknown:
            raise ValueError(f"belief contains unknown feedback labels: {sorted(unknown)}")
        probabilities = decision.belief.probabilities
        truth = _feedback_label(actual_feedback)
        true_probability = probabilities.get(truth, 0.0)
        total = len(self._candidates)
        reference = {
            _feedback_label(feedback): count / total
            for feedback, count in partition.items()
        }
        return {
            "beliefBrier": sum(
                (probabilities.get(label, 0.0) - float(label == truth)) ** 2
                for label in self._feedback_labels
            ),
            "beliefLogLoss": -math.log(max(true_probability, LOG_LOSS_FLOOR)),
            "trueFeedbackProbability": true_probability,
            "beliefPredictiveTvDistance": 0.5
            * sum(
                abs(probabilities.get(label, 0.0) - reference.get(label, 0.0))
                for label in self._feedback_labels
            ),
            "zeroProbabilityOnTruth": true_probability == 0,
        }

    def apply_decision(self, decision: AgentDecision) -> StepResult:
        decision_input = self.decision_input()
        validate_decision(decision_input, decision)
        if set(decision.payload) != {"guess"}:
            raise ValueError("submit_guess payload must contain exactly guess")
        guess = self._parse_guess(decision.payload["guess"])
        before = len(self._candidates)
        reference = self.solver.suggest(self._candidates)
        if reference is None:
            raise RuntimeError("non-terminal information set cannot be empty")
        partition = self._partition(guess)
        selected_worst = max(partition.values())
        selected_expected = sum(value * value for value in partition.values()) / before
        actual_feedback = self.solver.feedback(guess, self.secret)
        evaluation = self._belief_metrics(
            decision, partition, actual_feedback
        )
        evaluation.update(
            {
                "decisionKind": "information_guess",
                "referenceEvidenceLevel": EvidenceLevel.STRONG_HEURISTIC.value,
                "heuristicReferenceGuess": _code_label(reference.guess),
                "heuristicReferenceAgreement": guess == reference.guess,
                "selectedWorstCaseRemaining": selected_worst,
                "selectedExpectedRemaining": selected_expected,
                "heuristicWorstCaseRemaining": reference.worst_case_remaining,
                "heuristicExpectedRemaining": reference.expected_remaining,
                "worstCaseGapToHeuristic": (
                    selected_worst - reference.worst_case_remaining
                ),
            }
        )
        self._candidates = self.solver.filter_candidates(
            self._candidates, guess, actual_feedback
        )
        if self.secret not in self._candidates:
            raise RuntimeError("exact feedback filtering removed the true secret")
        information_gain = math.log2(before / len(self._candidates))
        self._information_gains.append(information_gain)
        evaluation["informationGainBits"] = information_gain
        evaluation["trueSecretRetained"] = True
        self._solved = actual_feedback.exact == self.solver.rules.length
        exhausted = len(self._history) + 1 >= self.solver.rules.max_attempts
        self._terminal = self._solved or exhausted
        public_observation = {
            "kind": "feedback",
            "guess": _code_label(guess),
            "exact": actual_feedback.exact,
            "misplaced": actual_feedback.misplaced,
            "remainingCandidates": len(self._candidates),
            "solved": self._solved,
        }
        self._last_observation = public_observation
        self._history.append(
            ActionEvent(
                actor_id="agent",
                action_id=SUBMIT_GUESS,
                payload={"guess": _code_label(guess)},
                public_observation=public_observation,
            )
        )
        return StepResult(public_observation, evaluation)

    def result(self) -> Mapping[str, object]:
        if not self._terminal:
            raise RuntimeError("episode result is unavailable before termination")
        return {
            "solved": self._solved,
            "attempts": len(self._history),
            "maxAttempts": self.solver.rules.max_attempts,
            "secretAfterTerminal": _code_label(self.secret),
            "remainingCandidates": len(self._candidates),
            "informationEfficiencyBitsPerGuess": mean(self._information_gains),
            "referenceEvidenceLevel": EvidenceLevel.STRONG_HEURISTIC.value,
            "referenceScope": "bounded_one_step_minimax_heuristic",
        }


class MastermindHeuristicReferenceAgent:
    """Execute the declared bounded one-step reference and exact predictive belief."""

    def __init__(self, solver: MastermindSolver | None = None) -> None:
        self.solver = solver or MastermindSolver()

    def _candidates(self, decision: AgentInput) -> tuple[tuple[int, ...], ...]:
        candidates = self.solver.all_codes
        for event in decision.action_history:
            guess = tuple(int(value) for value in str(event.payload["guess"]))
            feedback = CodeFeedback(
                int(event.public_observation["exact"]),
                int(event.public_observation["misplaced"]),
            )
            candidates = self.solver.filter_candidates(candidates, guess, feedback)
        return candidates

    def choose_action(self, decision: AgentInput) -> AgentDecision:
        if decision.environment_id != "mastermind":
            raise ValueError("Mastermind reference agent supports only mastermind")
        candidates = self._candidates(decision)
        analysis = self.solver.suggest(candidates)
        if analysis is None:
            raise RuntimeError("candidate set cannot be empty")
        partition = Counter(
            self.solver.feedback(analysis.guess, candidate).as_tuple()
            for candidate in candidates
        )
        belief = BeliefOutput(
            BELIEF_TARGET,
            {
                _feedback_label(feedback): count / len(candidates)
                for feedback, count in partition.items()
            },
        )
        return AgentDecision(
            SUBMIT_GUESS,
            confidence=max(belief.probabilities.values()),
            payload={"guess": _code_label(analysis.guess)},
            belief=belief,
        )


def summarize_mastermind_traces(
    traces: Iterable[EpisodeTrace],
) -> MastermindSuiteSummary:
    episodes = tuple(traces)
    if not episodes:
        raise ValueError("at least one trace is required")
    if any(trace.environment_id != "mastermind" for trace in episodes):
        raise ValueError("summary accepts only Mastermind traces")
    steps = tuple(step for trace in episodes for step in trace.steps)
    belief_steps = tuple(
        step for step in steps if step.evaluation["beliefBrier"] is not None
    )
    return MastermindSuiteSummary(
        episodes=len(episodes),
        solved_rate=mean(bool(trace.result["solved"]) for trace in episodes),
        mean_attempts=mean(int(trace.result["attempts"]) for trace in episodes),
        worst_attempts=max(int(trace.result["attempts"]) for trace in episodes),
        heuristic_reference_agreement=mean(
            bool(step.evaluation["heuristicReferenceAgreement"]) for step in steps
        ),
        mean_worst_case_gap_to_heuristic=mean(
            float(step.evaluation["worstCaseGapToHeuristic"]) for step in steps
        ),
        belief_output_rate=len(belief_steps) / len(steps),
        mean_belief_brier=(
            mean(float(step.evaluation["beliefBrier"]) for step in belief_steps)
            if belief_steps
            else None
        ),
        mean_belief_log_loss=(
            mean(float(step.evaluation["beliefLogLoss"]) for step in belief_steps)
            if belief_steps
            else None
        ),
        mean_predictive_tv_distance=(
            mean(
                float(step.evaluation["beliefPredictiveTvDistance"])
                for step in belief_steps
            )
            if belief_steps
            else None
        ),
        mean_information_efficiency_bits_per_guess=mean(
            float(trace.result["informationEfficiencyBitsPerGuess"])
            for trace in episodes
        ),
    )


def run_mastermind_reference(
    secret: tuple[int, ...] | str,
    *,
    episode_id: str = "mastermind:held-out:reference",
) -> EpisodeTrace:
    agent: StrategicAgent = MastermindHeuristicReferenceAgent()
    return run_episode(
        MastermindBenchmarkAdapter(secret, episode_id=episode_id),
        agent,
        agent_id="mastermind:bounded-one-step-reference",
        agent_metadata={
            "condition": "heuristic_reference",
            "claimLevel": EvidenceLevel.STRONG_HEURISTIC.value,
            "usesGameSpecificKnowledge": True,
            "isLlm": False,
        },
        max_steps=10,
    )
