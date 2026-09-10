import unittest
from fractions import Fraction

from aip.puzzles.e_card import (
    DUELS,
    certify_e_card_cfr,
    e_card_cfr_exploitability,
    e_card_cfr_value,
    e_card_exploitability,
    e_card_payoff_matrix,
    solve_e_card_timing_game,
    train_e_card_cfr,
)
from aip.ui.registry import ECardSession


class ECardEquilibriumTests(unittest.TestCase):
    def test_timing_matrix_matches_the_declared_role_cycle_and_scores(self) -> None:
        matrix = e_card_payoff_matrix()
        for emperor_index, emperor_timing in enumerate(DUELS):
            for slave_index, slave_timing in enumerate(DUELS):
                expected = -5 if emperor_timing == slave_timing else 1
                self.assertEqual(matrix[emperor_index][slave_index], expected)

                runtime_payoff = None
                for duel in DUELS:
                    emperor_card = "emperor" if duel == emperor_timing else "citizen"
                    slave_card = "slave" if duel == slave_timing else "citizen"
                    outcome = ECardSession._outcome(emperor_card, slave_card)
                    if outcome != "draw":
                        runtime_payoff = 1 if outcome == "player" else -5
                        break
                self.assertEqual(matrix[emperor_index][slave_index], runtime_payoff)

    def test_exact_matrix_sequence_form_solution_is_uniform(self) -> None:
        solution = solve_e_card_timing_game()
        uniform = (Fraction(1, 5),) * 5
        self.assertEqual(solution.emperor_value, Fraction(-1, 5))
        self.assertEqual(solution.emperor_strategy, uniform)
        self.assertEqual(solution.slave_strategy, uniform)
        self.assertEqual(
            e_card_exploitability(
                dict(zip(DUELS, map(float, uniform))),
                dict(zip(DUELS, map(float, uniform))),
            ),
            0.0,
        )

    def test_shared_cfr_recovers_the_exact_solution(self) -> None:
        result = train_e_card_cfr()
        report = certify_e_card_cfr(result)
        self.assertTrue(report.passed, report.failures)
        self.assertLessEqual(e_card_cfr_exploitability(result), 0.006)
        self.assertAlmostEqual(e_card_cfr_value(result), -0.2, delta=0.001)
        for distribution in result.policy.values():
            for probability in distribution.values():
                self.assertAlmostEqual(probability, 0.2, delta=0.002)

    def test_pure_timing_is_highly_exploitable(self) -> None:
        pure = {duel: float(duel == 1) for duel in DUELS}
        self.assertEqual(e_card_exploitability(pure, pure), 3.0)

    def test_fresh_local_round_already_uses_the_exact_uniform_ai_timing(self) -> None:
        session = ECardSession({"seed": 7})
        exact = solve_e_card_timing_game()
        self.assertEqual(
            session.ai_timing_distribution,
            tuple(map(float, exact.slave_strategy)),
        )


if __name__ == "__main__":
    unittest.main()
