from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from itertools import permutations

from .models import CodeFeedback, CodeRules

Code = tuple[int, ...]


@dataclass(frozen=True, slots=True)
class GuessAnalysis:
    guess: Code
    worst_case_remaining: int
    expected_remaining: float
    evaluated_guesses: int
    exact_search: bool


class MastermindSolver:
    """Candidate filtering plus a responsive, bounded minimax adviser.

    The full dynamic-programming optimum is expensive because an information state
    is a subset of 5,040 possible codes. This adviser instead minimizes the next
    guess's largest feedback bucket, then its expected bucket size. It evaluates
    every possible guess once the state is small and uses a deterministic sample
    while the state is large.
    """

    def __init__(self, rules: CodeRules | None = None) -> None:
        self.rules = rules or CodeRules()
        self.all_codes: tuple[Code, ...] = tuple(
            permutations(self.rules.symbols, self.rules.length)
        )
        self._suggestion_cache: dict[tuple[Code, ...], GuessAnalysis] = {}

    @staticmethod
    def feedback(guess: Code, secret: Code) -> CodeFeedback:
        exact = sum(left == right for left, right in zip(guess, secret))
        shared = len(set(guess) & set(secret))
        return CodeFeedback(exact, shared - exact)

    def filter_candidates(
        self, candidates: tuple[Code, ...], guess: Code, feedback: CodeFeedback
    ) -> tuple[Code, ...]:
        target = feedback.as_tuple()
        return tuple(
            candidate
            for candidate in candidates
            if self.feedback(guess, candidate).as_tuple() == target
        )

    @staticmethod
    def _sample(values: tuple[Code, ...], limit: int) -> tuple[Code, ...]:
        if len(values) <= limit:
            return values
        return tuple(values[index * len(values) // limit] for index in range(limit))

    def _guess_pool(self, candidates: tuple[Code, ...]) -> tuple[Code, ...]:
        if len(candidates) <= 160:
            return self.all_codes
        if len(candidates) <= 800:
            extras = self._sample(self.all_codes, 360)
            return tuple(dict.fromkeys((*candidates, *extras)))
        candidate_sample = self._sample(candidates, 280)
        global_sample = self._sample(self.all_codes, 120)
        return tuple(dict.fromkeys((*candidate_sample, *global_sample)))

    def suggest(self, candidates: tuple[Code, ...]) -> GuessAnalysis | None:
        if not candidates:
            return None
        cached = self._suggestion_cache.get(candidates)
        if cached is not None:
            return cached
        if len(candidates) == 1:
            result = GuessAnalysis(candidates[0], 1, 1.0, 1, True)
            self._suggestion_cache[candidates] = result
            return result
        if len(candidates) == len(self.all_codes):
            opening = tuple(self.rules.symbols[: self.rules.length])
            buckets = Counter(
                self.feedback(opening, secret).as_tuple() for secret in candidates
            )
            result = GuessAnalysis(
                opening,
                max(buckets.values()),
                sum(size * size for size in buckets.values()) / len(candidates),
                1,
                False,
            )
            self._suggestion_cache[candidates] = result
            return result

        pool = self._guess_pool(candidates)
        candidate_set = set(candidates)
        best_key: tuple[float, ...] | None = None
        best: GuessAnalysis | None = None
        for guess in pool:
            buckets = Counter(
                self.feedback(guess, secret).as_tuple() for secret in candidates
            )
            worst = max(buckets.values())
            expected = sum(size * size for size in buckets.values()) / len(candidates)
            key = (worst, expected, 0 if guess in candidate_set else 1, *guess)
            if best_key is None or key < best_key:
                best_key = key
                best = GuessAnalysis(
                    guess,
                    worst,
                    expected,
                    len(pool),
                    len(pool) == len(self.all_codes),
                )
        if best is not None:
            self._suggestion_cache[candidates] = best
        return best

    def solve(self, secret: Code, max_attempts: int | None = None) -> tuple[Code, ...]:
        self.rules.validate_guess(secret)
        candidates = self.all_codes
        guesses: list[Code] = []
        for _ in range(max_attempts or self.rules.max_attempts):
            analysis = self.suggest(candidates)
            if analysis is None:
                break
            guess = analysis.guess
            guesses.append(guess)
            result = self.feedback(guess, secret)
            if result.exact == self.rules.length:
                return tuple(guesses)
            candidates = self.filter_candidates(candidates, guess, result)
        return tuple(guesses)
