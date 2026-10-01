import unittest

from aip.core import (
    CFRGameProperties,
    compile_sequence_form,
    run_independent_evaluation,
    solve_sequence_form,
)
from aip.core.tree_evaluation import (
    FullTreeBestResponseEvaluator,
    audit_small_extensive_form,
)
from aip.puzzles.guess_who import (
    AdaptiveGuessWhoGame,
    DEFAULT_QUESTIONS,
    DEFAULT_ROSTER,
)


class AdaptiveGuessWhoTests(unittest.TestCase):
    def setUp(self) -> None:
        self.roster = (DEFAULT_ROSTER[0], DEFAULT_ROSTER[6], DEFAULT_ROSTER[12])
        self.questions = DEFAULT_QUESTIONS[:3]
        self.game = AdaptiveGuessWhoGame(self.roster, self.questions)

    def test_complete_tree_has_consistent_actions_and_perfect_recall(self) -> None:
        audit = audit_small_extensive_form(self.game)
        self.assertTrue(audit.passed, audit.failures)
        self.assertEqual(audit.histories, 337)
        self.assertEqual(audit.terminal_histories, 189)
        self.assertEqual(audit.information_sets, 44)
        self.assertEqual(audit.maximum_depth, 6)

    def test_secret_and_same_round_question_choices_are_hidden(self) -> None:
        root = self.game.initial_state()
        after_secret_zero = self.game.next_state(root, 0)
        after_other_secret_zero = self.game.next_state(root, 1)
        self.assertEqual(
            self.game.information_set(after_secret_zero),
            self.game.information_set(after_other_secret_zero),
        )
        selected = self.game.next_state(after_secret_zero, 1)
        pending_zero = self.game.next_state(selected, 0)
        pending_one = self.game.next_state(selected, 1)
        self.assertEqual(
            self.game.information_set(pending_zero),
            self.game.information_set(pending_one),
        )
        self.assertEqual(
            self.game.legal_actions(pending_zero),
            self.game.legal_actions(pending_one),
        )

    def test_sequence_form_and_independent_tree_oracle_agree(self) -> None:
        form = compile_sequence_form(
            self.game,
            game_properties=CFRGameProperties(2, True, True, True),
        )
        solution = solve_sequence_form(form)
        evaluator = FullTreeBestResponseEvaluator(
            self.game, evaluator_id="adaptive_guess_who_v1"
        )
        report = run_independent_evaluation(
            evaluator, solution.policy, maximum_exploitability=1e-10
        )
        self.assertTrue(report.passed, report.failures)
        self.assertAlmostEqual(solution.value_to_player_0, 0.0, places=10)
        self.assertAlmostEqual(report.expected_value_to_player_0, 0.0, places=10)
        self.assertLess(report.exploitability, 1e-10)
        self.assertEqual(len(report.action_values), 44)

    def test_relabeling_characters_and_questions_preserves_certificate(self) -> None:
        reversed_game = AdaptiveGuessWhoGame(
            self.roster[::-1], self.questions[::-1]
        )
        form = compile_sequence_form(
            reversed_game,
            game_properties=CFRGameProperties(2, True, True, True),
        )
        solution = solve_sequence_form(form)
        report = run_independent_evaluation(
            FullTreeBestResponseEvaluator(
                reversed_game, evaluator_id="adaptive_guess_who_relabel_v1"
            ),
            solution.policy,
            maximum_exploitability=1e-10,
        )
        self.assertTrue(report.passed, report.failures)
        self.assertAlmostEqual(solution.value_to_player_0, 0.0, places=10)

    def test_four_character_probe_uses_sparse_sequence_form(self) -> None:
        roster = tuple(DEFAULT_ROSTER[index * 6] for index in range(4))
        game = AdaptiveGuessWhoGame(roster, DEFAULT_QUESTIONS[:4])
        form = compile_sequence_form(
            game,
            game_properties=CFRGameProperties(2, True, True, True),
            maximum_histories=10_000,
            sparse=True,
        )
        self.assertEqual(form.audit.histories, 5_525)
        self.assertEqual(form.audit.information_sets, 682)
        self.assertEqual(tuple(map(len, form.player_sequences)), (741, 741))
        self.assertEqual(form.payoff_matrix.shape, (741, 741))
        self.assertEqual(len(form.payoff_matrix.entries), 672)

    def test_illegal_or_incomplete_question_bank_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            AdaptiveGuessWhoGame(self.roster, self.questions[:1])
        with self.assertRaises(ValueError):
            self.game.next_state(self.game.initial_state(), 99)


if __name__ == "__main__":
    unittest.main()
