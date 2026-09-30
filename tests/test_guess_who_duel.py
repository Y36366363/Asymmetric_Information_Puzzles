import unittest
from itertools import permutations

from aip.puzzles.guess_who import DEFAULT_QUESTIONS, DEFAULT_ROSTER, GuessWhoDuel


class GuessWhoDuelTests(unittest.TestCase):
    def setUp(self) -> None:
        self.roster = (DEFAULT_ROSTER[0], DEFAULT_ROSTER[6], DEFAULT_ROSTER[12])
        self.questions = DEFAULT_QUESTIONS[:3]
        self.orders = tuple(permutations(question.id for question in self.questions))
        self.duel = GuessWhoDuel(self.roster, self.questions, self.orders)

    def test_truthful_discovery_and_simultaneous_race_payoff(self) -> None:
        for order in self.orders:
            self.assertEqual(sorted(self.duel.discovery_turns(person.name, order)
                                    for person in self.roster), [2, 3, 3])
        matrix = self.duel.payoff_matrix()
        self.assertTrue(all(matrix[i][j] == -matrix[j][i]
                            for i in range(len(matrix)) for j in range(len(matrix))))

    def test_lp_equilibrium_has_independent_best_response_certificate(self) -> None:
        result = self.duel.solve()
        self.assertAlmostEqual(result.value, 0.0, places=9)
        self.assertLess(result.exploitability, 1e-8)
        self.assertAlmostEqual(result.nash_conv, 2 * result.exploitability)
        self.assertAlmostEqual(result.maximum_unilateral_deviation_gain,
                               max(result.player_0_deviation_gain,
                                   result.player_1_deviation_gain))
        for strategy in (result.player_0_strategy, result.player_1_strategy):
            self.assertAlmostEqual(sum(strategy), 1.0)
            self.assertTrue(all(0 <= probability <= 1 for probability in strategy))
            for character in self.roster:
                marginal = sum(probability for action, probability in zip(result.actions, strategy)
                               if action.secret == character.name)
                self.assertAlmostEqual(marginal, 1 / 3, places=7)

    def test_no_pure_saddle_point_and_order_enumeration_invariance(self) -> None:
        matrix = self.duel.payoff_matrix()
        pure_maximin = max(min(row) for row in matrix)
        pure_minimax = min(max(matrix[row][column] for row in range(len(matrix)))
                           for column in range(len(matrix)))
        self.assertEqual((pure_maximin, pure_minimax), (-1.0, 1.0))
        reversed_duel = GuessWhoDuel(self.roster[::-1], self.questions, self.orders[::-1])
        reversed_result = reversed_duel.solve()
        self.assertAlmostEqual(reversed_result.value, self.duel.solve().value, places=9)
        self.assertLess(reversed_result.exploitability, 1e-8)

    def test_invalid_commitments_rejected(self) -> None:
        with self.assertRaises(ValueError):
            GuessWhoDuel(self.roster, self.questions, (self.orders[0], self.orders[0]))
        with self.assertRaises(ValueError):
            GuessWhoDuel(self.roster, self.questions, (self.orders[0][:-1],))
        with self.assertRaises(ValueError):
            self.duel.discovery_turns("unknown", self.orders[0])


if __name__ == "__main__":
    unittest.main()
