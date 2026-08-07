import unittest

from aip.puzzles.mastermind import CodeFeedback, CodeRules, MastermindSolver
from aip.puzzles.mastermind.solver import MAX_SUGGESTION_CACHE


class MastermindSolverTests(unittest.TestCase):
    def setUp(self) -> None:
        self.rules = CodeRules()
        self.solver = MastermindSolver(self.rules)

    def test_standard_decimal_rules_have_5040_hidden_worlds(self) -> None:
        self.assertEqual(self.rules.world_count, 5040)
        self.assertEqual(len(self.solver.all_codes), 5040)
        self.assertIn((0, 1, 2, 3), self.solver.all_codes)
        self.assertIs(self.solver.all_codes, MastermindSolver(self.rules).all_codes)

    def test_feedback_separates_exact_and_misplaced_digits(self) -> None:
        feedback = self.solver.feedback((0, 1, 2, 3), (0, 3, 5, 2))
        self.assertEqual(feedback, CodeFeedback(exact=1, misplaced=2))

    def test_feedback_filters_the_information_set_exactly(self) -> None:
        candidates = self.solver.filter_candidates(
            self.solver.all_codes,
            (0, 1, 2, 3),
            CodeFeedback(exact=4, misplaced=0),
        )
        self.assertEqual(candidates, ((0, 1, 2, 3),))

    def test_adviser_solves_a_deterministic_secret_within_limit(self) -> None:
        guesses = self.solver.solve((9, 8, 7, 6))
        self.assertEqual(guesses[-1], (9, 8, 7, 6))
        self.assertLessEqual(len(guesses), self.rules.max_attempts)

    def test_repeated_digits_are_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "may not repeat"):
            self.rules.validate_guess((1, 1, 2, 3))

    def test_adviser_cache_is_bounded_during_long_sessions(self) -> None:
        for code in self.solver.all_codes[: MAX_SUGGESTION_CACHE + 40]:
            self.solver.suggest((code,))

        self.assertEqual(self.solver.suggestion_cache_size, MAX_SUGGESTION_CACHE)
        self.assertNotIn((self.solver.all_codes[0],), self.solver._suggestion_cache)
        self.assertIn(
            (self.solver.all_codes[MAX_SUGGESTION_CACHE + 39],),
            self.solver._suggestion_cache,
        )


if __name__ == "__main__":
    unittest.main()
