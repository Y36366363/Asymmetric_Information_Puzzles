import json
from pathlib import Path
import unittest

from aip.core import (
    GameSpecObservationSlice,
    ObservationStateRecord,
    audit_observation_invariance,
    audit_small_extensive_form,
    generate_observation_invariance_contract,
)
from aip.puzzles.goofspiel import (
    GoofspielCommitmentGame,
    generated_goofspiel_observation_contract,
    goofspiel_observation_records,
    goofspiel_observation_spec,
)
from aip.puzzles.liars_dice import (
    OneDieLiarDiceCFRGame,
    generated_one_die_observation_contract,
    one_die_observation_records,
    one_die_observation_spec,
    one_die_private_die_invariance_cases,
)


class OpponentDieLeakingGame(OneDieLiarDiceCFRGame):
    def information_set(self, state):
        if self.current_player(state) is None or state.dice is None:
            raise ValueError("decision states only")
        return state.dice, state.bids


class GameSpecObservationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.one_die = generated_one_die_observation_contract()
        cls.goofspiel = generated_goofspiel_observation_contract()

    def test_one_die_generator_exactly_reproduces_manual_reference_pairs(self):
        manual = one_die_private_die_invariance_cases()
        self.assertEqual(self.one_die.records, 2_088)
        self.assertEqual(self.one_die.observation_groups, 348)
        self.assertEqual(len(self.one_die.cases), 5_220)
        self.assertEqual(
            tuple((case.left_state, case.right_state) for case in self.one_die.cases),
            tuple((case.left_state, case.right_state) for case in manual),
        )

    def test_one_die_generated_contract_preserves_both_controls(self):
        correct = audit_observation_invariance(
            OneDieLiarDiceCFRGame(), self.one_die.cases
        )
        leak = audit_observation_invariance(
            OpponentDieLeakingGame(), self.one_die.cases
        )
        self.assertTrue(correct.passed)
        self.assertEqual(leak.violations, 5_220)
        self.assertEqual(
            dict(leak.violations_by_component), {"information_set": 5_220}
        )

    def test_goofspiel_generator_covers_frozen_four_card_slice(self):
        self.assertEqual(len(goofspiel_observation_records()), 1_456)
        self.assertEqual(self.goofspiel.records, 1_456)
        self.assertEqual(self.goofspiel.observation_groups, 628)
        self.assertEqual(len(self.goofspiel.cases), 1_032)

    def test_goofspiel_correct_adapter_is_invariant(self):
        report = audit_observation_invariance(
            GoofspielCommitmentGame(), self.goofspiel.cases
        )
        self.assertTrue(report.passed)
        self.assertEqual(report.violations, 0)

    def test_goofspiel_leak_passes_structure_but_fails_generated_contract(self):
        game = GoofspielCommitmentGame(leak_player_0_commitment=True)
        structure = audit_small_extensive_form(game)
        semantics = audit_observation_invariance(game, self.goofspiel.cases)
        self.assertTrue(structure.passed, structure.failures)
        self.assertEqual(structure.histories, 85)
        self.assertEqual(structure.information_sets, 20)
        self.assertEqual(semantics.violations, 1_032)
        self.assertEqual(
            dict(semantics.violations_by_component), {"information_set": 1_032}
        )

    def test_declaration_projects_public_and_own_private_fields(self):
        one_die = one_die_observation_spec()
        fields = {"bids": (), "die_0": 2, "die_1": 5}
        self.assertEqual(
            one_die.project(fields, 0), (("bids", ()), ("die_0", 2))
        )
        self.assertEqual(
            one_die.project(fields, 1), (("bids", ()), ("die_1", 5))
        )
        self.assertEqual(one_die.hidden_fields(0), ("die_1",))
        self.assertEqual(one_die.hidden_fields(1), ("die_0",))
        self.assertEqual(
            goofspiel_observation_spec().hidden_fields(1),
            ("pending_player_0_card",),
        )

    def test_invalid_declarations_and_records_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "cover every player"):
            GameSpecObservationSlice("bad", 2, ("public",), (("private",),))
        with self.assertRaisesRegex(ValueError, "disjoint"):
            GameSpecObservationSlice(
                "bad", 2, ("shared",), (("shared",), ())
            )
        spec = GameSpecObservationSlice("tiny", 2, ("public",), (("p0",), ()))
        missing = ObservationStateRecord.from_mapping(
            ("state", 0), 1, {"public": 1}
        )
        with self.assertRaisesRegex(ValueError, "missing"):
            generate_observation_invariance_contract(spec, (missing,))
        with self.assertRaisesRegex(ValueError, "nonempty"):
            generate_observation_invariance_contract(spec, ())
        self.assertEqual(len(one_die_observation_records()), 2_088)

    def test_saved_artifact_preserves_stop_rule_and_interpretation_boundary(self):
        root = Path(__file__).resolve().parents[1]
        artifact = json.loads((
            root
            / "research/results/game_spec_observation_slice_2026-10-17.json"
        ).read_text())
        self.assertTrue(artifact["primary_passed"])
        self.assertTrue(
            artifact["one_die_reference_reproduction"]
            ["exact_ordered_state_pair_match"]
        )
        self.assertIsNone(
            artifact["one_die_reference_reproduction"]["first_mismatch"]
        )
        self.assertEqual(
            artifact["goofspiel_transfer"]["mutant_adapter"]
            ["observation_invariance"]["violations"],
            1_032,
        )
        self.assertFalse(
            artifact["interpretation"]["llm_game_spec_generation_tested"]
        )
        self.assertFalse(
            artifact["interpretation"]["adaptive_opponent_learning_ready"]
        )


if __name__ == "__main__":
    unittest.main()
