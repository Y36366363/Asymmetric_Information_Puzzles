import unittest

from aip.core import (
    CFRGameProperties,
    CFRResult,
    create_regret_minimization_trainer,
    compile_sequence_form,
    run_independent_evaluation,
    solve_sequence_form,
)
from aip.puzzles.liars_dice import (
    OneDieLiarDiceCFRGame,
    OneDieLiarIndependentEvaluator,
    one_die_liar_evaluation,
    solve_one_die_liar_exact,
)
from aip.puzzles.love_letter import (
    LoveLetterCFRGame,
    LoveLetterIndependentEvaluator,
    complete_information_set_actions,
    love_letter_subgame_evaluation,
)


PROPERTIES = CFRGameProperties(2, True, True, True)


def result_for(policy):
    return CFRResult(
        iterations=0,
        policy=policy,
        information_set_visits={key: 0 for key in policy},
        average_positive_regret=(0.0, 0.0),
    )


def uniform_love_letter_policy(game):
    return {
        key: {action: 1 / len(actions) for action in actions}
        for key, actions in complete_information_set_actions(game).items()
    }


class ReorderedGame:
    def __init__(self, game, *, chance=False, actions=False):
        self.game = game
        self.reverse_chance = chance
        self.reverse_actions = actions

    def __getattr__(self, name):
        return getattr(self.game, name)

    def chance_outcomes(self, state):
        values = self.game.chance_outcomes(state)
        return tuple(reversed(values)) if self.reverse_chance else values

    def legal_actions(self, state):
        values = self.game.legal_actions(state)
        return tuple(reversed(values)) if self.reverse_actions else values


def assert_profiles_close(case, first, second, places=14):
    case.assertEqual(set(first), set(second))
    for key, distribution in first.items():
        case.assertEqual(set(distribution), set(second[key]))
        for action, probability in distribution.items():
            case.assertAlmostEqual(probability, second[key][action], places=places)


class LoveLetterLiarAlgorithmAuditTests(unittest.TestCase):
    def test_exact_profiles_agree_with_two_independent_oracle_paths(self):
        love = LoveLetterCFRGame.late_round_subgame()
        love_form = compile_sequence_form(love, game_properties=PROPERTIES)
        love_solution = solve_sequence_form(love_form)
        love_report = run_independent_evaluation(
            LoveLetterIndependentEvaluator(love), love_solution.policy,
            maximum_exploitability=1e-12,
        )
        love_legacy = love_letter_subgame_evaluation(
            love, result_for(love_solution.policy)
        )
        self.assertTrue(love_report.passed)
        self.assertAlmostEqual(love_report.exploitability,
                               love_legacy.exploitability, places=14)

        _, liar_solution = solve_one_die_liar_exact()
        liar_report = run_independent_evaluation(
            OneDieLiarIndependentEvaluator(), liar_solution.policy,
            maximum_exploitability=1e-12,
        )
        liar_legacy = one_die_liar_evaluation(result_for(liar_solution.policy))
        self.assertTrue(liar_report.passed)
        self.assertAlmostEqual(liar_report.exploitability,
                               liar_legacy.exploitability, places=14)

    def test_love_letter_uniform_negative_control_stays_exploitable(self):
        game = LoveLetterCFRGame.late_round_subgame()
        report = run_independent_evaluation(
            LoveLetterIndependentEvaluator(game),
            uniform_love_letter_policy(game),
            maximum_exploitability=0.001,
        )
        self.assertFalse(report.passed)
        self.assertAlmostEqual(report.exploitability, 0.375)

    def test_one_die_independent_evaluator_rejects_incomplete_sampled_profile(self):
        result = create_regret_minimization_trainer(
            OneDieLiarDiceCFRGame(), "external_sampling_mccfr", seed=19
        ).train(100)
        with self.assertRaisesRegex(ValueError, "cover exactly"):
            run_independent_evaluation(
                OneDieLiarIndependentEvaluator(), result.policy,
                maximum_exploitability=0.01,
            )

    def test_one_die_independent_evaluator_rejects_bad_actions_and_probabilities(self):
        _, solution = solve_one_die_liar_exact()
        key = next(iter(solution.policy))
        bad_actions = {item: dict(distribution)
                       for item, distribution in solution.policy.items()}
        bad_actions[key]["not-legal"] = 0.0
        with self.assertRaisesRegex(ValueError, "actions do not match"):
            run_independent_evaluation(
                OneDieLiarIndependentEvaluator(), bad_actions,
                maximum_exploitability=0.01,
            )

        bad_probability = {item: dict(distribution)
                           for item, distribution in solution.policy.items()}
        action = next(iter(bad_probability[key]))
        bad_probability[key][action] = float("nan")
        with self.assertRaisesRegex(ValueError, "probabilities must be finite"):
            run_independent_evaluation(
                OneDieLiarIndependentEvaluator(), bad_probability,
                maximum_exploitability=0.01,
            )

    def test_full_tree_algorithms_are_order_invariant_on_both_games(self):
        for game_factory in (
            LoveLetterCFRGame.late_round_subgame,
            OneDieLiarDiceCFRGame,
        ):
            for algorithm in ("vanilla_cfr", "cfr_plus", "dcfr"):
                with self.subTest(game=game_factory.__name__, algorithm=algorithm):
                    baseline = create_regret_minimization_trainer(
                        game_factory(), algorithm
                    ).train(10).policy
                    chance = create_regret_minimization_trainer(
                        ReorderedGame(game_factory(), chance=True), algorithm
                    ).train(10).policy
                    actions = create_regret_minimization_trainer(
                        ReorderedGame(game_factory(), actions=True), algorithm
                    ).train(10).policy
                    assert_profiles_close(self, baseline, chance)
                    assert_profiles_close(self, baseline, actions)


if __name__ == "__main__":
    unittest.main()
