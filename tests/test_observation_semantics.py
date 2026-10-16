import json
from pathlib import Path
import unittest

from aip.core import (
    ObservationInvarianceCase,
    audit_observation_invariance,
    audit_small_extensive_form,
)
from aip.puzzles.liars_dice import (
    OneDieLiarDiceCFRGame,
    one_die_private_die_invariance_cases,
)


class OpponentDieLeakingGame(OneDieLiarDiceCFRGame):
    def information_set(self, state):
        if self.current_player(state) is None or state.dice is None:
            raise ValueError("decision states only")
        return state.dice, state.bids


class ObservationSemanticAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases = one_die_private_die_invariance_cases()

    def test_contract_exhausts_one_die_private_counterfactual_pairs(self):
        self.assertEqual(len(self.cases), 5_220)
        self.assertEqual(len({case.case_id for case in self.cases}), 5_220)

    def test_correct_adapter_is_observation_invariant(self):
        report = audit_observation_invariance(
            OneDieLiarDiceCFRGame(), self.cases
        )
        self.assertTrue(report.passed)
        self.assertEqual(report.violations, 0)
        self.assertEqual(report.violations_by_component, ())

    def test_leaking_adapter_is_structurally_valid_but_semantically_rejected(self):
        game = OpponentDieLeakingGame()
        structure = audit_small_extensive_form(game, maximum_histories=10_000)
        semantics = audit_observation_invariance(game, self.cases)
        self.assertTrue(structure.passed, structure.failures)
        self.assertEqual(structure.information_sets, 2_088)
        self.assertFalse(semantics.passed)
        self.assertEqual(semantics.violations, 5_220)
        self.assertEqual(
            dict(semantics.violations_by_component), {"information_set": 5_220}
        )
        self.assertEqual(
            semantics.counterexamples[0].changed_observables,
            ("information_set",),
        )

    def test_contract_rejects_empty_duplicate_and_invalid_limits(self):
        game = OneDieLiarDiceCFRGame()
        with self.assertRaisesRegex(ValueError, "contain cases"):
            audit_observation_invariance(game, ())
        duplicate = ObservationInvarianceCase(
            self.cases[0].case_id,
            self.cases[1].left_state,
            self.cases[1].right_state,
        )
        with self.assertRaisesRegex(ValueError, "unique"):
            audit_observation_invariance(game, (self.cases[0], duplicate))
        with self.assertRaisesRegex(OverflowError, "exceeds"):
            audit_observation_invariance(game, self.cases, maximum_cases=10)
        with self.assertRaisesRegex(ValueError, "counterexamples"):
            audit_observation_invariance(
                game, self.cases[:1], maximum_counterexamples=-1
            )

    def test_frozen_experiment_artifact_preserves_the_negative_control(self):
        root = Path(__file__).resolve().parents[1]
        artifact = json.loads((
            root
            / "research/results/one_die_private_information_semantic_audit_2026-10-16.json"
        ).read_text())
        self.assertTrue(artifact["primary_passed"])
        self.assertTrue(
            artifact["correct_adapter"]["structural_audit"]["passed"]
        )
        self.assertTrue(
            artifact["mutant_adapter"]["structural_audit"]["passed"]
        )
        self.assertEqual(
            artifact["correct_adapter"]["observation_invariance"]["violations"],
            0,
        )
        self.assertEqual(
            artifact["mutant_adapter"]["observation_invariance"]["violations"],
            5_220,
        )
        self.assertEqual(
            artifact["mutant_adapter"]["internal_solution"]
            ["independent_evaluation"]["exploitability"],
            0.0,
        )
        self.assertFalse(
            artifact["interpretation"]
            ["mutant_internal_equilibrium_is_real_game_certificate"]
        )


if __name__ == "__main__":
    unittest.main()
