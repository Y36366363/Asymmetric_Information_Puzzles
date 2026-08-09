import unittest

from aip.puzzles.guess_who import DEFAULT_QUESTIONS, DEFAULT_ROSTER, GuessWhoSolver


class GuessWhoTests(unittest.TestCase):
    def setUp(self) -> None:
        self.solver = GuessWhoSolver()

    def test_roster_is_unique_and_question_bank_separates_every_character(self) -> None:
        self.assertEqual(len(DEFAULT_ROSTER), 24)
        self.assertEqual(len({character.name for character in DEFAULT_ROSTER}), 24)
        signatures = {
            tuple(question.matches(character) for question in DEFAULT_QUESTIONS)
            for character in DEFAULT_ROSTER
        }
        self.assertEqual(len(signatures), 24)

    def test_information_set_updates_from_public_yes_no_answer(self) -> None:
        information = self.solver.initial_information_set()
        question = next(question for question in DEFAULT_QUESTIONS if question.id == "glasses")
        updated = self.solver.update_information(information, question, True)
        self.assertTrue(all(character.glasses for character in updated.possible_states))
        self.assertLess(len(updated.possible_states), len(information.possible_states))
        self.assertTrue(updated.public_history[-1].is_public)

    def test_root_question_scores_are_well_formed(self) -> None:
        scores = self.solver.score_questions()
        self.assertEqual(len(scores), len(DEFAULT_QUESTIONS))
        self.assertTrue(all(score.yes_count + score.no_count == 24 for score in scores))
        self.assertTrue(all(score.worst_remaining < 24 for score in scores))

    def test_exact_policies_solve_every_character(self) -> None:
        for strategy in ("optimal_expected", "optimal_worst"):
            runs = [self.solver.play(character.name, strategy) for character in DEFAULT_ROSTER]
            self.assertTrue(all(run.solved for run in runs))
            self.assertLessEqual(max(run.turns_including_guess for run in runs), 9)

    def test_exact_expected_policy_is_not_worse_than_one_step_entropy(self) -> None:
        summaries = {item.strategy: item for item in self.solver.compare(random_repeats=5)}
        self.assertLessEqual(
            summaries["optimal_expected"].mean_turns,
            summaries["entropy"].mean_turns,
        )

    def test_seeded_random_policy_is_reproducible(self) -> None:
        self.assertEqual(self.solver.compare(5, 77), self.solver.compare(5, 77))


if __name__ == "__main__":
    unittest.main()
