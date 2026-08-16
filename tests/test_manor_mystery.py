import unittest

from aip.puzzles.manor_mystery import MysterySolver


class ManorMysteryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.solver = MysterySolver()

    def test_deal_has_one_secret_per_category_and_disjoint_hands(self) -> None:
        world = self.solver.deal(17)
        self.assertEqual(len(world.secret), 3)
        self.assertTrue(all(len(hand) == 3 for hand in world.hands))
        zones = [set(world.secret), *(set(hand) for hand in world.hands)]
        self.assertEqual(sum(len(zone) for zone in zones), len(set().union(*zones)))
        self.assertEqual(set().union(*zones), set(self.solver.all_cards))

    def test_initial_information_set_contains_the_true_world(self) -> None:
        world = self.solver.deal(23)
        information = self.solver.initial_information_set(world.hands[0])
        self.assertIn(world, information.possible_states)
        self.assertGreater(len(information.possible_states), 100)
        self.assertNotIn(world.secret[0], world.hands[0])

    def test_suggestion_response_shrinks_belief_without_losing_truth(self) -> None:
        world = self.solver.deal(31)
        information = self.solver.initial_information_set(world.hands[0])
        score = self.solver.recommend(information)
        response = self.solver.response(world, score.suggestion)
        updated = self.solver.observe(information, score.suggestion, response)
        self.assertIn(world, updated.possible_states)
        self.assertLess(len(updated.possible_states), len(information.possible_states))
        self.assertLessEqual(
            len(self.solver.remaining_secrets(updated)),
            len(self.solver.remaining_secrets(information)),
        )
        self.assertEqual(len(updated.public_history), len(response.passed_players))
        self.assertEqual(len(updated.observations), int(response.shown_card is not None))
        self.assertTrue(all(item.is_public for item in updated.public_history))
        self.assertTrue(all(not item.is_public for item in updated.observations))

    def test_first_opponent_with_a_matching_card_controls_the_response(self) -> None:
        world = self.solver.deal(41)
        suggestion = next(
            item
            for item in self.solver.suggestions
            if world.hands[1].intersection(item.cards)
        )
        response = self.solver.response(world, suggestion)
        self.assertEqual(response.responder, 1)
        self.assertEqual(response.passed_players, ())
        self.assertIn(response.shown_card, world.hands[1].intersection(suggestion.cards))

    def test_information_strategy_solves_seeded_cases(self) -> None:
        runs = [self.solver.play(seed, "information") for seed in range(12)]
        self.assertTrue(all(run.solved for run in runs))
        self.assertLessEqual(max(run.suggestions for run in runs), 8)
        self.assertTrue(all(run.candidate_trace[-1] == 1 for run in runs))

    def test_robust_strategy_survives_information_denying_reveals(self) -> None:
        runs = [
            self.solver.play(seed, "information", reveal_policy="information_denying")
            for seed in range(12)
        ]
        self.assertTrue(all(run.solved for run in runs))
        self.assertLessEqual(max(run.suggestions for run in runs), 8)

    def test_information_strategy_beats_random_suggestions(self) -> None:
        summaries = {item.strategy: item for item in self.solver.compare(20, seed=100)}
        self.assertEqual(summaries["information"].solved_rate, 1)
        self.assertLess(
            summaries["information"].mean_suggestions,
            summaries["random"].mean_suggestions,
        )


if __name__ == "__main__":
    unittest.main()
