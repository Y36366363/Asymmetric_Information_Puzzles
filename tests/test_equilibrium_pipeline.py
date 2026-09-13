import random
import unittest

from aip.core import (
    EquilibriumGameStructure,
    EquilibriumMethod,
    audit_stopping_time_compression,
    recommend_equilibrium_solver,
)
from aip.puzzles.e_card import e_card_equilibrium_structure
from aip.puzzles.love_letter import (
    LoveLetterGame,
    love_letter_equilibrium_structure,
)


class EquilibriumPipelineTests(unittest.TestCase):
    def test_e_card_passes_complete_stopping_time_matrix_gate(self) -> None:
        structure = e_card_equilibrium_structure()
        audit = audit_stopping_time_compression(structure.stopping_time)
        recommendation = recommend_equilibrium_solver(structure)
        self.assertTrue(audit.compressible)
        self.assertEqual(audit.matrix_shape, (5, 5))
        self.assertEqual(recommendation.primary, EquilibriumMethod.EXACT_MATRIX)
        self.assertEqual(recommendation.cross_check, EquilibriumMethod.VANILLA_CFR)

    def test_love_letter_fails_timing_compression_for_specific_reasons(self) -> None:
        structure = love_letter_equilibrium_structure()
        audit = audit_stopping_time_compression(structure.stopping_time)
        self.assertFalse(audit.compressible)
        self.assertEqual(
            set(audit.failures),
            {
                "private_information_not_fixed_at_start",
                "new_private_information_arrives",
                "strategic_actions_exist_before_stopping",
                "payoff_requires_more_than_stopping_times",
            },
        )
        recommendation = recommend_equilibrium_solver(structure)
        self.assertEqual(
            recommendation.primary, EquilibriumMethod.EXTERNAL_SAMPLING_MCCFR
        )
        self.assertEqual(recommendation.cross_check, EquilibriumMethod.SEQUENCE_FORM)

    def test_live_love_letter_really_draws_new_private_information(self) -> None:
        game = LoveLetterGame(random.Random(7))
        game.deck = [6]
        game.hands["ai"] = [2]
        game._begin_turn("ai")
        self.assertEqual(game.hands["ai"], [2, 6])
        self.assertEqual(game.deck, [])

    def test_later_chance_uses_full_tree_when_it_fits_the_budget(self) -> None:
        recommendation = recommend_equilibrium_solver(
            EquilibriumGameStructure(
                players=2,
                finite=True,
                zero_sum_or_constant_sum=True,
                perfect_recall=True,
                chance_after_initial_state=True,
                estimated_full_tree_nodes=80_000,
                full_tree_node_budget=100_000,
            )
        )
        self.assertEqual(recommendation.primary, EquilibriumMethod.DCFR)
        self.assertEqual(
            recommendation.cross_check, EquilibriumMethod.EXTERNAL_SAMPLING_MCCFR
        )
        self.assertIn(
            "estimated_full_tree_cost_within_resource_budget",
            recommendation.reasons,
        )

    def test_tree_over_budget_routes_to_sampling_even_without_later_chance(self) -> None:
        recommendation = recommend_equilibrium_solver(
            EquilibriumGameStructure(
                players=2,
                finite=True,
                zero_sum_or_constant_sum=True,
                perfect_recall=True,
                chance_after_initial_state=False,
                estimated_full_tree_nodes=100_001,
                full_tree_node_budget=100_000,
            )
        )
        self.assertEqual(
            recommendation.primary, EquilibriumMethod.EXTERNAL_SAMPLING_MCCFR
        )
        self.assertEqual(recommendation.cross_check, EquilibriumMethod.DCFR)

    def test_invalid_tree_cost_or_budget_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "nodes must be positive"):
            EquilibriumGameStructure(
                2, True, True, True, True, estimated_full_tree_nodes=0
            )
        with self.assertRaisesRegex(ValueError, "budget must be positive"):
            EquilibriumGameStructure(
                2, True, True, True, True, full_tree_node_budget=0
            )

    def test_multiplayer_general_sum_game_is_not_gto_gate_eligible(self) -> None:
        recommendation = recommend_equilibrium_solver(
            EquilibriumGameStructure(
                players=6,
                finite=True,
                zero_sum_or_constant_sum=False,
                perfect_recall=True,
                chance_after_initial_state=True,
            )
        )
        self.assertFalse(recommendation.eligible_for_gto_pipeline)
        self.assertEqual(recommendation.primary, EquilibriumMethod.UNSUPPORTED)
        self.assertEqual(
            set(recommendation.reasons),
            {"requires_two_players", "requires_zero_or_constant_sum"},
        )


if __name__ == "__main__":
    unittest.main()
