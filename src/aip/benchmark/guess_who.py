"""First executable benchmark slice: exact information acquisition in Guess Who."""

from __future__ import annotations

import math
from dataclasses import dataclass
from statistics import mean
from typing import Iterable, Mapping

from aip.benchmark.runner import EpisodeTrace, StepResult
from aip.benchmark.types import (
    ActionEvent,
    ActionSpec,
    AgentDecision,
    AgentInput,
    BeliefOutput,
    EvidenceLevel,
    validate_decision,
)
from aip.puzzles.guess_who import GuessWhoSolver


ASK_PREFIX = "ask_question:"
GUESS_PREFIX = "guess_character:"
LOG_LOSS_FLOOR = 1e-15

RULES = (
    "One of 24 characters is hidden under a uniform prior. Ask one unused public "
    "yes/no question per turn. Answers are truthful. When exactly one candidate "
    "remains, name that character. Every question and the final guess cost one turn."
)


@dataclass(frozen=True, slots=True)
class GuessWhoSuiteSummary:
    episodes: int
    solved_rate: float
    mean_turns: float
    worst_turns: int
    optimal_policy_agreement: float
    mean_action_regret: float
    belief_output_rate: float
    mean_belief_brier: float | None
    mean_belief_log_loss: float | None
    mean_information_efficiency_bits_per_question: float


class GuessWhoBenchmarkAdapter:
    """Truthful fixed-roster environment with an exact dynamic-programming oracle.

    Identity guesses are legal only when one candidate remains. This declared
    action space matches the solver's proof model and prevents a different
    early-guessing game from being mislabeled as proved optimal.
    """

    environment_id = "guess-who"
    evidence_level = EvidenceLevel.PROVED_OPTIMAL

    def __init__(
        self,
        secret: str,
        *,
        episode_id: str | None = None,
        include_rules: bool = False,
        solver: GuessWhoSolver | None = None,
    ) -> None:
        self.solver = solver or GuessWhoSolver()
        names = {character.name for character in self.solver.roster}
        if secret not in names:
            raise ValueError(f"unknown secret character: {secret}")
        self.secret = secret
        self.episode_id = episode_id or f"guess-who:{secret}"
        self.include_rules = include_rules
        self._candidates = tuple(character.name for character in self.solver.roster)
        self._used_question_ids: set[str] = set()
        self._history: list[ActionEvent] = []
        self._last_observation: Mapping[str, object] = {"kind": "start"}
        self._terminal = False
        self._solved = False
        self._question_count = 0

    @property
    def terminal(self) -> bool:
        return self._terminal

    def _masks(self) -> tuple[int, int]:
        return (
            self.solver.candidate_mask(self._candidates),
            self.solver.remaining_question_mask(self._used_question_ids),
        )

    def _question_cost(self, question_id: str) -> float:
        _, remaining = self._masks()
        index = next(
            index
            for index, question in enumerate(self.solver.questions)
            if question.id == question_id
        )
        bit = 1 << index
        if not remaining & bit:
            return math.inf
        question = self.solver.questions[index]
        yes_names = tuple(
            name
            for name in self._candidates
            if question.matches(next(c for c in self.solver.roster if c.name == name))
        )
        no_names = tuple(name for name in self._candidates if name not in yes_names)
        if not yes_names or not no_names:
            return math.inf
        next_remaining = remaining & ~bit
        total = len(self._candidates)
        yes_mask = self.solver.candidate_mask(yes_names)
        no_mask = self.solver.candidate_mask(no_names)
        return (
            1
            + len(yes_names) / total
            * self.solver.exact_expected_questions(yes_mask, next_remaining)
            + len(no_names) / total
            * self.solver.exact_expected_questions(no_mask, next_remaining)
        )

    def _optimal_action_ids(self) -> tuple[str, ...]:
        if len(self._candidates) == 1:
            return (GUESS_PREFIX + self._candidates[0],)
        candidates, remaining = self._masks()
        optimum = self.solver.exact_expected_questions(candidates, remaining)
        return tuple(
            ASK_PREFIX + question.id
            for question in self.solver.questions
            if math.isclose(self._question_cost(question.id), optimum, abs_tol=1e-12)
        )

    def decision_input(self) -> AgentInput:
        if self._terminal:
            raise RuntimeError("terminal episodes have no decision input")
        if len(self._candidates) == 1:
            legal_actions = (
                ActionSpec(
                    GUESS_PREFIX + self._candidates[0],
                    f"Name {self._candidates[0]} as the hidden character.",
                ),
            )
        else:
            scores = {
                score.question.id: score
                for score in self.solver.score_questions(*self._masks())
            }
            legal_actions = tuple(
                ActionSpec(ASK_PREFIX + question.id, question.label)
                for question in self.solver.questions
                if question.id in scores
            )
        return AgentInput(
            environment_id=self.environment_id,
            episode_id=self.episode_id,
            step=len(self._history),
            observation=dict(self._last_observation),
            information_state={
                "candidateNames": list(self._candidates),
                "candidateCount": len(self._candidates),
                "candidateProfiles": [
                    {
                        "name": character.name,
                        "hair": character.hair,
                        "glasses": character.glasses,
                        "hat": character.hat,
                        "facialHair": character.facial_hair,
                        "smiling": character.smiling,
                    }
                    for character in self.solver.roster
                    if character.name in self._candidates
                ],
                "usedQuestionIds": sorted(self._used_question_ids),
            },
            legal_actions=legal_actions,
            action_history=tuple(self._history),
            natural_language_rules=RULES if self.include_rules else None,
        )

    def _belief_metrics(self, decision: AgentDecision) -> dict[str, float | None]:
        if decision.belief is None:
            return {
                "beliefBrier": None,
                "beliefLogLoss": None,
                "trueStateProbability": None,
                "candidateSupportMass": None,
                "zeroProbabilityOnTruth": None,
            }
        if decision.belief.target != "secret_character":
            raise ValueError("Guess Who belief target must be secret_character")
        names = {character.name for character in self.solver.roster}
        unknown = set(decision.belief.probabilities).difference(names)
        if unknown:
            raise ValueError(f"belief contains unknown characters: {sorted(unknown)}")
        probabilities = decision.belief.probabilities
        true_probability = probabilities.get(self.secret, 0.0)
        brier = sum(
            (probabilities.get(name, 0.0) - float(name == self.secret)) ** 2
            for name in names
        )
        return {
            "beliefBrier": brier,
            "beliefLogLoss": -math.log(max(true_probability, LOG_LOSS_FLOOR)),
            "trueStateProbability": true_probability,
            "candidateSupportMass": sum(
                probabilities.get(name, 0.0) for name in self._candidates
            ),
            "zeroProbabilityOnTruth": true_probability == 0,
        }

    def apply_decision(self, decision: AgentDecision) -> StepResult:
        decision_input = self.decision_input()
        validate_decision(decision_input, decision)
        optimal_action_ids = self._optimal_action_ids()
        evaluation: dict[str, object] = self._belief_metrics(decision)
        evaluation["optimalActionIds"] = list(optimal_action_ids)
        evaluation["optimalPolicyAgreement"] = decision.action_id in optimal_action_ids
        before_count = len(self._candidates)

        if decision.action_id.startswith(ASK_PREFIX):
            question_id = decision.action_id.removeprefix(ASK_PREFIX)
            candidates_mask, remaining = self._masks()
            optimum = self.solver.exact_expected_questions(candidates_mask, remaining)
            selected_cost = self._question_cost(question_id)
            evaluation["actionRegret"] = selected_cost - optimum
            question = next(q for q in self.solver.questions if q.id == question_id)
            secret_character = next(
                character for character in self.solver.roster if character.name == self.secret
            )
            answer = question.matches(secret_character)
            self._candidates = tuple(
                character.name
                for character in self.solver.roster
                if character.name in self._candidates
                and question.matches(character) is answer
            )
            self._used_question_ids.add(question_id)
            self._question_count += 1
            public_observation = {
                "kind": "answer",
                "questionId": question_id,
                "answer": answer,
                "remainingCandidates": len(self._candidates),
            }
            evaluation["informationGainBits"] = math.log2(
                before_count / len(self._candidates)
            )
        else:
            guessed_name = decision.action_id.removeprefix(GUESS_PREFIX)
            self._solved = guessed_name == self.secret
            self._terminal = True
            public_observation = {
                "kind": "final_guess",
                "name": guessed_name,
                "correct": self._solved,
            }
            evaluation["actionRegret"] = 0.0
            evaluation["informationGainBits"] = 0.0

        self._last_observation = public_observation
        self._history.append(
            ActionEvent(
                actor_id="agent",
                action_id=decision.action_id,
                public_observation=public_observation,
            )
        )
        return StepResult(public_observation, evaluation)

    def result(self) -> Mapping[str, object]:
        if not self._terminal:
            raise RuntimeError("episode result is unavailable before termination")
        return {
            "solved": self._solved,
            "secret": self.secret,
            "turnsIncludingGuess": len(self._history),
            "questionsAsked": self._question_count,
            "informationEfficiencyBitsPerQuestion": (
                math.log2(len(self.solver.roster)) / self._question_count
            ),
        }


class OptimalGuessWhoAgent:
    """Algorithmic oracle using the exact expected-question recurrence."""

    def __init__(self, solver: GuessWhoSolver | None = None) -> None:
        self.solver = solver or GuessWhoSolver()

    def choose_action(self, decision: AgentInput) -> AgentDecision:
        candidates = tuple(str(name) for name in decision.information_state["candidateNames"])
        probability = 1 / len(candidates)
        belief = BeliefOutput(
            target="secret_character",
            probabilities={name: probability for name in candidates},
        )
        if len(candidates) == 1:
            action_id = GUESS_PREFIX + candidates[0]
        else:
            used = set(str(q) for q in decision.information_state["usedQuestionIds"])
            question_index = self.solver.choose_question(
                "optimal_expected",
                self.solver.candidate_mask(candidates),
                self.solver.remaining_question_mask(used),
            )
            action_id = ASK_PREFIX + self.solver.questions[question_index].id
        return AgentDecision(action_id=action_id, confidence=1.0, belief=belief)


def summarize_guess_who_traces(
    traces: Iterable[EpisodeTrace],
) -> GuessWhoSuiteSummary:
    episodes = tuple(traces)
    if not episodes:
        raise ValueError("at least one trace is required")
    if any(trace.environment_id != "guess-who" for trace in episodes):
        raise ValueError("summary accepts only Guess Who traces")
    steps = tuple(step for trace in episodes for step in trace.steps)
    belief_steps = tuple(
        step for step in steps if step.evaluation["beliefBrier"] is not None
    )
    return GuessWhoSuiteSummary(
        episodes=len(episodes),
        solved_rate=mean(bool(trace.result["solved"]) for trace in episodes),
        mean_turns=mean(int(trace.result["turnsIncludingGuess"]) for trace in episodes),
        worst_turns=max(int(trace.result["turnsIncludingGuess"]) for trace in episodes),
        optimal_policy_agreement=mean(
            bool(step.evaluation["optimalPolicyAgreement"]) for step in steps
        ),
        mean_action_regret=mean(float(step.evaluation["actionRegret"]) for step in steps),
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
        mean_information_efficiency_bits_per_question=mean(
            float(trace.result["informationEfficiencyBitsPerQuestion"])
            for trace in episodes
        ),
    )
