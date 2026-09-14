import unittest
from dataclasses import dataclass

from aip.core import (
    FullTreeBestResponseEvaluator,
    PromotionLevel,
    audit_small_extensive_form,
    run_independent_evaluation,
)
from aip.puzzles.e_card import (
    DUELS,
    ECardIndependentEvaluator,
    e_card_evaluation,
    e_card_profile,
    exact_e_card_promotion,
    solve_e_card_timing_game,
)
from aip.puzzles.kuhn_poker import (
    KuhnCFRGame,
    KuhnIndependentEvaluator,
    solve_kuhn_sequence_form,
)
from aip.puzzles.love_letter import LoveLetterCFRGame, LoveLetterIndependentEvaluator


@dataclass(frozen=True)
class ForgetfulState:
    history: tuple[str, ...] = ()


class ForgetfulGame:
    """Deliberately invalid adapter: player zero forgets its first action."""

    def initial_state(self):
        return ForgetfulState()

    def is_terminal(self, state):
        return len(state.history) == 2

    def utility_player_zero(self, state):
        return float(state.history[0] == state.history[1])

    def current_player(self, state):
        return None if self.is_terminal(state) else 0

    def chance_outcomes(self, state):
        return ()

    def legal_actions(self, state):
        return ("left", "right") if not self.is_terminal(state) else ()

    def information_set(self, state):
        return "first" if not state.history else "forgot_first_action"

    def next_state(self, state, action):
        return ForgetfulState(state.history + (action,))


@dataclass(frozen=True)
class BadChanceState:
    terminal: bool = False


class BadChanceGame:
    def initial_state(self):
        return BadChanceState()

    def is_terminal(self, state):
        return state.terminal

    def utility_player_zero(self, state):
        return 0.0

    def current_player(self, state):
        return None

    def chance_outcomes(self, state):
        return (("a", 0.4), ("b", 0.4))

    def legal_actions(self, state):
        return ()

    def information_set(self, state):
        raise AssertionError("chance has no information set")

    def next_state(self, state, action):
        return BadChanceState(True)


class ExtensiveFormCompatibilityTests(unittest.TestCase):
    def test_exact_e_card_matrix_and_shared_tree_oracle_agree(self) -> None:
        solution = solve_e_card_timing_game()
        emperor = dict(zip(DUELS, map(float, solution.emperor_strategy)))
        slave = dict(zip(DUELS, map(float, solution.slave_strategy)))
        profile = e_card_profile(emperor, slave)
        evaluator = ECardIndependentEvaluator()
        report = run_independent_evaluation(
            evaluator, profile, maximum_exploitability=1e-12
        )
        matrix = e_card_evaluation(emperor, slave)

        self.assertEqual(evaluator.audit.histories, 31)
        self.assertEqual(evaluator.audit.information_sets, 2)
        self.assertTrue(report.passed)
        self.assertAlmostEqual(
            report.expected_value_to_player_0, float(solution.emperor_value)
        )
        self.assertAlmostEqual(report.nash_conv, matrix.nash_conv)
        self.assertEqual(len(report.action_values), 2)
        self.assertEqual(exact_e_card_promotion().level, PromotionLevel.FROZEN)

    def test_kuhn_specialized_and_shared_tree_oracles_agree(self) -> None:
        profile = solve_kuhn_sequence_form().policy
        specialized = KuhnIndependentEvaluator()
        shared = FullTreeBestResponseEvaluator(
            KuhnCFRGame(), evaluator_id="kuhn_shared_full_tree_test_v1"
        )
        specialized_report = run_independent_evaluation(
            specialized, profile, maximum_exploitability=1e-12
        )
        shared_report = run_independent_evaluation(
            shared, profile, maximum_exploitability=1e-12
        )

        self.assertEqual(shared.audit.histories, 55)
        self.assertEqual(shared.audit.information_sets, 12)
        self.assertTrue(shared_report.passed)
        self.assertAlmostEqual(
            shared_report.expected_value_to_player_0,
            specialized_report.expected_value_to_player_0,
        )
        self.assertAlmostEqual(
            shared_report.nash_conv, specialized_report.nash_conv, delta=2e-15
        )
        self.assertEqual(len(shared_report.action_values), 12)

    def test_later_private_chance_game_passes_the_same_structural_audit(self) -> None:
        evaluator = LoveLetterIndependentEvaluator(
            LoveLetterCFRGame.late_round_subgame()
        )
        self.assertTrue(evaluator.audit.passed)
        self.assertEqual(evaluator.audit.histories, 1_081)
        self.assertEqual(evaluator.audit.chance_histories, 217)
        self.assertEqual(evaluator.audit.information_sets, 60)
        self.assertEqual(evaluator.audit.maximum_depth, 5)

    def test_audit_rejects_imperfect_recall_and_invalid_chance(self) -> None:
        recall = audit_small_extensive_form(ForgetfulGame())
        chance = audit_small_extensive_form(BadChanceGame())
        self.assertIn("imperfect_recall", recall.failures)
        self.assertIn("invalid_chance_distribution", chance.failures)
        with self.assertRaisesRegex(ValueError, "imperfect_recall"):
            FullTreeBestResponseEvaluator(
                ForgetfulGame(), evaluator_id="must_not_certify"
            )

    def test_profile_validation_fails_closed(self) -> None:
        evaluator = ECardIndependentEvaluator()
        uniform = {duel: 0.2 for duel in DUELS}
        valid = e_card_profile(uniform, uniform)
        values = evaluator.action_values(valid)
        key = (0, ("emperor", "choose_special_duel"))
        values[key][1] = 999.0
        self.assertNotEqual(evaluator.action_values(valid)[key][1], 999.0)
        malformed = dict(valid)
        malformed.pop((1, ("slave", "choose_special_duel")))
        with self.assertRaisesRegex(ValueError, "cover exactly"):
            evaluator.expected_value(malformed)

        nonfinite = {key: dict(value) for key, value in valid.items()}
        nonfinite[(0, ("emperor", "choose_special_duel"))][1] = float("nan")
        with self.assertRaisesRegex(ValueError, "finite"):
            evaluator.expected_value(nonfinite)

    def test_full_tree_resource_limit_fails_before_partial_certification(self) -> None:
        with self.assertRaisesRegex(OverflowError, "exceeds 10 histories"):
            audit_small_extensive_form(KuhnCFRGame(), maximum_histories=10)


if __name__ == "__main__":
    unittest.main()
