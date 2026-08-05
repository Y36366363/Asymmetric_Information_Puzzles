import random
import unittest

from aip.puzzles.battleship.models import FleetRules
from aip.puzzles.battleship.solver import (
    BattleshipSimulator,
    HiddenFleetBoard,
    ProbabilityDensityAI,
)


class BattleshipResearchTests(unittest.TestCase):
    def test_random_fleet_is_legal(self) -> None:
        rules = FleetRules()
        board = HiddenFleetBoard(rules, random.Random(11))
        occupied = set()
        self.assertEqual([ship.length for ship in board.ships], list(rules.ship_lengths))
        for ship in board.ships:
            self.assertEqual(len(ship.cells), ship.length)
            self.assertTrue(ship.cells.isdisjoint(occupied))
            occupied.update(ship.cells)

    def test_every_ai_finishes_without_repeated_shots(self) -> None:
        simulator = BattleshipSimulator()
        for strategy in ("random", "hunt-target", "probability-density"):
            shots = simulator.play(strategy, board_seed=17, policy_seed=23)
            self.assertGreaterEqual(shots, sum(simulator.rules.ship_lengths))
            self.assertLessEqual(shots, simulator.rules.board_size**2)

    def test_seeded_simulation_is_reproducible(self) -> None:
        simulator = BattleshipSimulator()
        first = simulator.compare(games=20, seed=99)
        second = simulator.compare(games=20, seed=99)
        self.assertEqual(first, second)

    def test_evolved_ai_outperforms_random_baseline(self) -> None:
        summaries = {
            result.strategy: result for result in BattleshipSimulator().compare(games=120)
        }
        random_mean = summaries["random"].mean_shots
        self.assertLess(summaries["hunt-target"].mean_shots, random_mean)
        self.assertLess(summaries["probability-density"].mean_shots, random_mean)

    def test_probability_ai_exposes_auditable_density_analysis(self) -> None:
        ai = ProbabilityDensityAI(FleetRules(), random.Random(9))
        choice = ai.choose()
        self.assertEqual(ai.last_analysis["chosenCell"], choice)
        self.assertGreater(ai.last_analysis["candidatePlacements"], 0)
        self.assertGreater(ai.last_analysis["peakDensity"], 0)


if __name__ == "__main__":
    unittest.main()
