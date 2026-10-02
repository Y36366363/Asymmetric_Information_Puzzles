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
    DEFAULT_QUESTIONS,
    DEFAULT_ROSTER,
    StrategicGuessWhoGame,
)


class StrategicGuessWhoTests(unittest.TestCase):
    def setUp(self) -> None:
        self.game = StrategicGuessWhoGame(
            (DEFAULT_ROSTER[0], DEFAULT_ROSTER[6], DEFAULT_ROSTER[12]),
            DEFAULT_QUESTIONS[:3],
        )

    def _solve(self):
        form = compile_sequence_form(
            self.game,
            game_properties=CFRGameProperties(2, True, True, True),
            sparse=True,
        )
        return form, solve_sequence_form(form, backend="scipy_highs")

    def test_complete_tree_is_finite_consistent_and_perfect_recall(self) -> None:
        audit = audit_small_extensive_form(self.game)
        self.assertTrue(audit.passed, audit.failures)
        self.assertEqual(audit.histories, 1_651)
        self.assertEqual(audit.terminal_histories, 972)
        self.assertEqual(audit.information_sets, 404)
        self.assertEqual(audit.maximum_depth, 8)

    def test_sequence_form_passes_independent_best_response(self) -> None:
        form, solution = self._solve()
        report = run_independent_evaluation(
            FullTreeBestResponseEvaluator(
                self.game, evaluator_id="strategic_guess_who_v1"
            ),
            solution.policy,
            maximum_exploitability=1e-10,
        )
        self.assertTrue(report.passed, report.failures)
        self.assertAlmostEqual(solution.value_to_player_0, 0.0, places=10)
        self.assertLess(report.exploitability, 1e-10)
        self.assertEqual(tuple(map(len, form.player_sequences)), (301, 301))
        self.assertEqual(len(report.action_values), 404)

    def test_equilibrium_never_blind_guesses_but_does_guess_under_ambiguity(self) -> None:
        _, solution = self._solve()
        for player in (0, 1):
            root_distributions = []
            for secret in range(3):
                distribution = solution.policy[(player, ("act", secret, ()))]
                root_distributions.append(distribution)
                self.assertAlmostEqual(
                    sum(value for action, value in distribution.items()
                        if action[0] == "guess"),
                    0.0,
                )
            self.assertTrue(all(distribution == root_distributions[0]
                                for distribution in root_distributions[1:]))
        ambiguous_positive_reach = 0

        def traverse(state, reach):
            nonlocal ambiguous_positive_reach
            if self.game.is_terminal(state):
                return
            player = self.game.current_player(state)
            key = (player, self.game.information_set(state))
            distribution = solution.policy[key]
            if state.stage.endswith("action") and state.transcript:
                guess_mass = sum(
                    value for action, value in distribution.items()
                    if action[0] == "guess"
                )
                if state.candidates[player].bit_count() > 1 and reach * guess_mass > 1e-10:
                    ambiguous_positive_reach += 1
            for action, probability in distribution.items():
                if probability:
                    traverse(
                        self.game.next_state(state, action),
                        reach * probability,
                    )

        traverse(self.game.initial_state(), 1.0)
        self.assertGreater(ambiguous_positive_reach, 0)

    def test_wrong_unilateral_guess_loses_and_dual_correct_guess_draws(self) -> None:
        state = self.game.initial_state()
        state = self.game.next_state(state, 0)
        state = self.game.next_state(state, 1)
        pending = self.game.next_state(state, ("guess", 2))
        wrong = self.game.next_state(pending, ("ask", 0))
        self.assertEqual(self.game.utility_player_zero(wrong), -1.0)

        pending = self.game.next_state(state, ("guess", 1))
        both_correct = self.game.next_state(pending, ("guess", 0))
        self.assertEqual(self.game.utility_player_zero(both_correct), 0.0)

    def test_same_round_action_is_hidden_and_invalid_action_rejected(self) -> None:
        state = self.game.next_state(self.game.initial_state(), 0)
        state = self.game.next_state(state, 1)
        ask = self.game.next_state(state, ("ask", 0))
        guess = self.game.next_state(state, ("guess", 1))
        self.assertEqual(self.game.information_set(ask), self.game.information_set(guess))
        self.assertEqual(self.game.legal_actions(ask), self.game.legal_actions(guess))
        with self.assertRaises(ValueError):
            self.game.next_state(state, ("guess", 99))


if __name__ == "__main__":
    unittest.main()
