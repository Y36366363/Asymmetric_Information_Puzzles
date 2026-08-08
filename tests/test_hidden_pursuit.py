import random
import unittest

from aip.puzzles.hidden_pursuit import HiddenPursuitRules, HiddenPursuitSimulator, PursuitState


class HiddenPursuitTests(unittest.TestCase):
    def test_initial_information_set_excludes_detectives(self) -> None:
        state = PursuitState(HiddenPursuitRules(), random.Random(7))
        self.assertEqual(len(state.belief), 16)
        self.assertTrue(set(state.detectives).isdisjoint(state.belief))

    def test_illegal_detective_move_is_rejected(self) -> None:
        state = PursuitState(HiddenPursuitRules(), random.Random(7))
        with self.assertRaisesRegex(ValueError, "legal detective move"):
            state.move_detective(18)

    def test_public_transport_updates_belief_and_reveal_collapses_it(self) -> None:
        state = PursuitState(HiddenPursuitRules(), random.Random(4), "random")
        while state.phase != "finished" and state.round_number <= 3:
            state.move_detective(state.legal_detective_moves()[0])
        if state.phase != "finished":
            self.assertEqual(state.round_number, 4)
            self.assertEqual(state.belief, {state.fugitive})
            self.assertEqual(state.last_reveal, state.fugitive)

    def test_seeded_simulation_is_reproducible(self) -> None:
        simulator = HiddenPursuitSimulator()
        self.assertEqual(simulator.compare(30, 99), simulator.compare(30, 99))

    def test_final_reveal_collapses_post_game_information_set(self) -> None:
        rules = HiddenPursuitRules(max_rounds=1, reveal_rounds=())
        state = PursuitState(rules, random.Random(7), "random")
        while state.phase != "finished":
            state.move_detective(state.legal_detective_moves()[0])
        self.assertEqual(state.belief, {state.fugitive})

    def test_belief_policy_beats_random_detectives_against_evasive_ai(self) -> None:
        summaries = {
            (item.detective_policy, item.fugitive_policy): item
            for item in HiddenPursuitSimulator().compare(200)
        }
        self.assertGreater(
            summaries[("belief-pursuit", "evasive-information")].capture_rate,
            summaries[("random", "evasive-information")].capture_rate,
        )


if __name__ == "__main__":
    unittest.main()
