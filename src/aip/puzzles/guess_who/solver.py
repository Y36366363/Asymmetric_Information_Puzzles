from __future__ import annotations

import math
import random
from dataclasses import dataclass
from functools import lru_cache
from statistics import mean

from aip.core.information import InformationSet, Observation

from .models import DEFAULT_QUESTIONS, DEFAULT_ROSTER, Character, Question


@dataclass(frozen=True, slots=True)
class QuestionScore:
    question: Question
    yes_count: int
    no_count: int
    worst_remaining: int
    expected_remaining: float
    entropy_bits: float


@dataclass(frozen=True, slots=True)
class GuessWhoRun:
    secret: str
    strategy: str
    questions: tuple[str, ...]
    candidate_counts: tuple[int, ...]
    turns_including_guess: int
    solved: bool


@dataclass(frozen=True, slots=True)
class PolicySummary:
    strategy: str
    games: int
    solved_rate: float
    mean_turns: float
    worst_turns: int


class GuessWhoSolver:
    """Solve a fixed Guess Who roster under a finite public question bank.

    The exact policies are globally optimal within this declared model: secrets
    are uniformly likely, questions have unit cost, answers are truthful, and a
    final identity guess costs one turn. They are not a proof for every physical
    Guess Who edition, whose roster and permitted natural-language questions vary.
    """

    STRATEGIES = (
        "random",
        "hair_first",
        "entropy",
        "minimax",
        "optimal_expected",
        "optimal_worst",
    )

    def __init__(
        self,
        roster: tuple[Character, ...] = DEFAULT_ROSTER,
        questions: tuple[Question, ...] = DEFAULT_QUESTIONS,
    ) -> None:
        if len(roster) < 2 or len({character.name for character in roster}) != len(roster):
            raise ValueError("roster needs at least two uniquely named characters")
        if not questions or len({question.id for question in questions}) != len(questions):
            raise ValueError("question ids must be unique")
        signatures = {
            tuple(question.matches(character) for question in questions)
            for character in roster
        }
        if len(signatures) != len(roster):
            raise ValueError("the question bank must distinguish every character")
        self.roster = roster
        self.questions = questions
        self._name_to_index = {character.name: index for index, character in enumerate(roster)}
        self._yes_masks = tuple(
            sum(1 << index for index, character in enumerate(roster) if question.matches(character))
            for question in questions
        )
        self.full_candidate_mask = (1 << len(roster)) - 1
        self.full_question_mask = (1 << len(questions)) - 1

    def initial_information_set(self, player_id: str = "detective") -> InformationSet[Character]:
        probability = 1 / len(self.roster)
        return InformationSet(
            key="guess-who:start",
            player_id=player_id,
            possible_states=self.roster,
            beliefs={character: probability for character in self.roster},
        )

    def candidate_mask(self, names: set[str] | tuple[str, ...] | list[str]) -> int:
        unknown = set(names).difference(self._name_to_index)
        if unknown:
            raise ValueError(f"unknown candidate characters: {sorted(unknown)}")
        return sum(1 << self._name_to_index[name] for name in names)

    def remaining_question_mask(self, used_question_ids: set[str]) -> int:
        known_ids = {question.id for question in self.questions}
        unknown = used_question_ids.difference(known_ids)
        if unknown:
            raise ValueError(f"unknown question ids: {sorted(unknown)}")
        return sum(
            1 << index
            for index, question in enumerate(self.questions)
            if question.id not in used_question_ids
        )

    def update_information(
        self,
        information: InformationSet[Character],
        question: Question,
        answer: bool,
    ) -> InformationSet[Character]:
        observation = Observation(question.id, answer, is_public=True)
        return information.update(
            observation,
            lambda character, fact: question.matches(character) is fact.value,
        )

    def score_questions(
        self,
        candidates_mask: int | None = None,
        remaining_questions: int | None = None,
    ) -> tuple[QuestionScore, ...]:
        candidates = self.full_candidate_mask if candidates_mask is None else candidates_mask
        remaining = self.full_question_mask if remaining_questions is None else remaining_questions
        total = candidates.bit_count()
        if total < 2:
            return ()
        scores = []
        for index, question in enumerate(self.questions):
            if not remaining & (1 << index):
                continue
            yes = (candidates & self._yes_masks[index]).bit_count()
            no = total - yes
            if not yes or not no:
                continue
            probabilities = (yes / total, no / total)
            scores.append(
                QuestionScore(
                    question,
                    yes,
                    no,
                    max(yes, no),
                    (yes * yes + no * no) / total,
                    -sum(probability * math.log2(probability) for probability in probabilities),
                )
            )
        return tuple(scores)

    def _split(self, candidates: int, question_index: int) -> tuple[int, int]:
        yes = candidates & self._yes_masks[question_index]
        return yes, candidates & ~self._yes_masks[question_index]

    @lru_cache(maxsize=None)
    def exact_expected_questions(self, candidates: int, remaining: int) -> float:
        total = candidates.bit_count()
        if total <= 1:
            return 0.0
        values = []
        for index in range(len(self.questions)):
            bit = 1 << index
            if not remaining & bit:
                continue
            yes, no = self._split(candidates, index)
            if not yes or not no:
                continue
            next_remaining = remaining & ~bit
            values.append(
                1
                + yes.bit_count() / total * self.exact_expected_questions(yes, next_remaining)
                + no.bit_count() / total * self.exact_expected_questions(no, next_remaining)
            )
        return min(values, default=math.inf)

    @lru_cache(maxsize=None)
    def exact_worst_questions(self, candidates: int, remaining: int) -> int | float:
        if candidates.bit_count() <= 1:
            return 0
        values: list[int | float] = []
        for index in range(len(self.questions)):
            bit = 1 << index
            if not remaining & bit:
                continue
            yes, no = self._split(candidates, index)
            if not yes or not no:
                continue
            next_remaining = remaining & ~bit
            values.append(
                1 + max(
                    self.exact_worst_questions(yes, next_remaining),
                    self.exact_worst_questions(no, next_remaining),
                )
            )
        return min(values, default=math.inf)

    def choose_question(
        self,
        strategy: str,
        candidates: int,
        remaining: int,
        rng: random.Random | None = None,
    ) -> int:
        if strategy not in self.STRATEGIES:
            raise ValueError(f"unknown Guess Who strategy: {strategy}")
        valid = []
        total = candidates.bit_count()
        for index in range(len(self.questions)):
            bit = 1 << index
            if not remaining & bit:
                continue
            yes, no = self._split(candidates, index)
            if yes and no:
                valid.append((index, yes, no))
        if not valid:
            raise ValueError("remaining question bank cannot distinguish the candidates")
        if strategy == "random":
            return (rng or random.Random()).choice(valid)[0]
        if strategy == "hair_first":
            return valid[0][0]

        def key(item: tuple[int, int, int]) -> tuple[float, ...]:
            index, yes, no = item
            counts = (yes.bit_count(), no.bit_count())
            worst = max(counts)
            expected_remaining = (counts[0] ** 2 + counts[1] ** 2) / total
            next_remaining = remaining & ~(1 << index)
            if strategy == "entropy":
                return expected_remaining, worst, index
            if strategy == "minimax":
                return worst, expected_remaining, index
            if strategy == "optimal_expected":
                future = (
                    counts[0] / total * self.exact_expected_questions(yes, next_remaining)
                    + counts[1] / total * self.exact_expected_questions(no, next_remaining)
                )
                return future, worst, index
            future_worst = max(
                self.exact_worst_questions(yes, next_remaining),
                self.exact_worst_questions(no, next_remaining),
            )
            return float(future_worst), expected_remaining, index

        return min(valid, key=key)[0]

    def play(self, secret: str, strategy: str, seed: int = 0) -> GuessWhoRun:
        if secret not in self._name_to_index:
            raise ValueError(f"unknown secret character: {secret}")
        secret_index = self._name_to_index[secret]
        candidates = self.full_candidate_mask
        remaining = self.full_question_mask
        rng = random.Random(seed)
        asked: list[str] = []
        counts = [candidates.bit_count()]
        while candidates.bit_count() > 1:
            question_index = self.choose_question(strategy, candidates, remaining, rng)
            question_bit = 1 << question_index
            answer = bool(self._yes_masks[question_index] & (1 << secret_index))
            yes, no = self._split(candidates, question_index)
            candidates = yes if answer else no
            remaining &= ~question_bit
            asked.append(self.questions[question_index].id)
            counts.append(candidates.bit_count())
        solved = candidates == 1 << secret_index
        return GuessWhoRun(secret, strategy, tuple(asked), tuple(counts), len(asked) + 1, solved)

    def compare(self, random_repeats: int = 100, seed: int = 20260809) -> tuple[PolicySummary, ...]:
        if random_repeats < 1:
            raise ValueError("random_repeats must be positive")
        summaries = []
        for strategy in self.STRATEGIES:
            repeats = random_repeats if strategy == "random" else 1
            runs = [
                self.play(character.name, strategy, seed + repeat * len(self.roster) + index)
                for repeat in range(repeats)
                for index, character in enumerate(self.roster)
            ]
            summaries.append(
                PolicySummary(
                    strategy,
                    len(runs),
                    sum(run.solved for run in runs) / len(runs),
                    round(mean(run.turns_including_guess for run in runs), 3),
                    max(run.turns_including_guess for run in runs),
                )
            )
        return tuple(summaries)
