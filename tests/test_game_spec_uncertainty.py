import json
import math
from pathlib import Path
import unittest

from aip.core import (
    GameSpecHypothesis,
    GameSpecObservationSlice,
    ObservationEquivalenceEvidence,
    evaluate_game_spec_hypotheses,
    generate_observation_invariance_contract,
)
from aip.puzzles.liars_dice import (
    one_die_observation_records,
    one_die_observation_spec,
    one_die_private_die_invariance_cases,
)


def visible_dice_spec():
    return GameSpecObservationSlice(
        "one_die_both_dice_visible_v1",
        2,
        ("bids", "die_0", "die_1"),
        ((), ()),
    )


def hypotheses():
    return (
        GameSpecHypothesis("opponent_die_hidden", one_die_observation_spec(), 0.5),
        GameSpecHypothesis("both_dice_visible", visible_dice_spec(), 0.5),
    )


def evidence_for_manual_case(index, *, observed_same=True, reliability=1.0, suffix=""):
    records = {record.state: record for record in one_die_observation_records()}
    case = one_die_private_die_invariance_cases()[index]
    return ObservationEquivalenceEvidence(
        f"manual-{index}{suffix}",
        records[case.left_state],
        records[case.right_state],
        observed_same,
        reliability,
    )


class GameSpecUncertaintyTests(unittest.TestCase):
    def test_no_evidence_keeps_equal_prior_unresolved(self):
        report = evaluate_game_spec_hypotheses(hypotheses(), ())
        self.assertEqual(report.status, "unresolved")
        self.assertIsNone(report.selected_hypothesis_id)
        self.assertEqual(
            tuple(result.posterior for result in report.results), (0.5, 0.5)
        )
        self.assertEqual(
            report.hard_compatible_hypotheses,
            ("opponent_die_hidden", "both_dice_visible"),
        )
        self.assertFalse(report.semantic_certification_allowed)

    def test_hard_manual_reference_eliminates_visible_dice_hypothesis(self):
        report = evaluate_game_spec_hypotheses(
            hypotheses(), (evidence_for_manual_case(0),)
        )
        self.assertEqual(report.status, "identified")
        self.assertEqual(report.selected_hypothesis_id, "opponent_die_hidden")
        self.assertEqual(
            tuple(result.posterior for result in report.results), (1.0, 0.0)
        )
        self.assertEqual(
            report.hard_compatible_hypotheses, ("opponent_die_hidden",)
        )
        self.assertTrue(report.semantic_certification_allowed)

    def test_probabilistic_evidence_matches_frozen_sensitivity_curve(self):
        expected = {
            0: 0.5,
            1: 0.75,
            2: 0.9,
            4: 0.9878048780487805,
            8: 0.999847607436757,
        }
        available = tuple(
            evidence_for_manual_case(
                index, reliability=0.75, suffix="-probabilistic"
            )
            for index in range(8)
        )
        for count, posterior in expected.items():
            with self.subTest(count=count):
                report = evaluate_game_spec_hypotheses(
                    hypotheses(), available[:count]
                )
                self.assertTrue(
                    math.isclose(
                        report.results[0].posterior,
                        posterior,
                        rel_tol=1e-12,
                    )
                )
                self.assertFalse(report.semantic_certification_allowed)

    def test_balanced_soft_contradiction_remains_unresolved(self):
        same = evidence_for_manual_case(
            0, reliability=0.9, suffix="-same-source"
        )
        different = evidence_for_manual_case(
            0,
            observed_same=False,
            reliability=0.9,
            suffix="-different-source",
        )
        report = evaluate_game_spec_hypotheses(hypotheses(), (same, different))
        self.assertEqual(report.status, "unresolved")
        self.assertEqual(report.conflicting_evidence_pairs, 1)
        self.assertEqual(
            tuple(result.posterior for result in report.results), (0.5, 0.5)
        )
        self.assertFalse(report.semantic_certification_allowed)

    def test_contradictory_hard_evidence_fails_closed(self):
        same = evidence_for_manual_case(0, suffix="-same-hard")
        different = evidence_for_manual_case(
            0, observed_same=False, suffix="-different-hard"
        )
        report = evaluate_game_spec_hypotheses(hypotheses(), (same, different))
        self.assertEqual(report.status, "conflicted")
        self.assertIsNone(report.selected_hypothesis_id)
        self.assertEqual(report.hard_compatible_hypotheses, ())
        self.assertTrue(all(result.posterior is None for result in report.results))
        self.assertFalse(report.semantic_certification_allowed)

    def test_each_candidate_generates_its_own_contract(self):
        records = one_die_observation_records()
        hidden = generate_observation_invariance_contract(
            one_die_observation_spec(), records
        )
        visible = generate_observation_invariance_contract(
            visible_dice_spec(), records, require_cases=False
        )
        self.assertEqual(len(hidden.cases), 5_220)
        self.assertEqual(len(visible.cases), 0)
        self.assertEqual(visible.observation_groups, 2_088)

    def test_invalid_priors_evidence_and_candidate_universes_are_rejected(self):
        hidden = one_die_observation_spec()
        with self.assertRaisesRegex(ValueError, "sum to one"):
            evaluate_game_spec_hypotheses(
                (
                    GameSpecHypothesis("a", hidden, 0.4),
                    GameSpecHypothesis("b", visible_dice_spec(), 0.4),
                ),
                (),
            )
        with self.assertRaisesRegex(ValueError, "reliability"):
            evidence_for_manual_case(0, reliability=0.49)
        incompatible = GameSpecObservationSlice(
            "incompatible", 2, ("bids",), (("die_0",), ("other",))
        )
        with self.assertRaisesRegex(ValueError, "field universe"):
            evaluate_game_spec_hypotheses(
                (
                    GameSpecHypothesis("a", hidden, 0.5),
                    GameSpecHypothesis("b", incompatible, 0.5),
                ),
                (),
            )

    def test_saved_artifact_keeps_probability_and_certification_separate(self):
        root = Path(__file__).resolve().parents[1]
        artifact = json.loads((
            root
            / "research/results/game_spec_hypothesis_uncertainty_2026-10-19.json"
        ).read_text())
        self.assertTrue(artifact["primary_passed"])
        self.assertEqual(artifact["no_evidence"]["status"], "unresolved")
        self.assertEqual(
            artifact["hard_reference_evidence"]["selected_hypothesis_id"],
            "opponent_die_hidden",
        )
        self.assertEqual(artifact["hard_contradiction"]["status"], "conflicted")
        self.assertTrue(all(
            not point["semantic_certification_allowed"]
            for point in artifact["probabilistic_sensitivity"]["curve"]
        ))
        self.assertFalse(artifact["interpretation"]["prior_is_nature_probability"])
        self.assertFalse(
            artifact["promotion"]["runtime_epsilon_gto_allowed"]
        )
        self.assertFalse(artifact["promotion"]["llm_pilot_executed"])


if __name__ == "__main__":
    unittest.main()
