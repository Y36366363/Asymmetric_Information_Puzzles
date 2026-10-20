import json
from pathlib import Path
import unittest

from aip.core import (
    EvidenceSourcePolicy,
    GameSpecVocabulary,
    compile_game_spec_candidate_json,
    compile_trusted_evidence_json,
    score_pilot_case,
    verify_candidate_set,
)
from aip.puzzles.liars_dice import (
    one_die_observation_records,
    one_die_observation_spec,
    one_die_private_die_invariance_cases,
)


SCHEMA = "aip-observation-gamespec-candidates-v1"


def candidate(hypothesis_id, public, player_0, player_1):
    return {
        "hypothesis_id": hypothesis_id,
        "public_fields": list(public),
        "private_fields_by_player": {
            "player_0": list(player_0),
            "player_1": list(player_1),
        },
    }


HIDDEN = candidate("hidden", ("bids",), ("die_0",), ("die_1",))
VISIBLE = candidate("visible", ("bids", "die_0", "die_1"), (), ())
SWAPPED = candidate("swapped", ("bids",), ("die_1",), ("die_0",))


def payload(*candidates):
    return {
        "schema_version": SCHEMA,
        "game_id": "one_die_liar",
        "candidates": list(candidates),
    }


class GameSpecPilotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.vocabulary = GameSpecVocabulary(
            "one_die_liar", 2, ("bids", "die_0", "die_1")
        )
        records = {record.state: record for record in one_die_observation_records()}
        reference_case = one_die_private_die_invariance_cases()[0]
        cls.worlds = {
            "left": records[reference_case.left_state],
            "right": records[reference_case.right_state],
        }
        cls.sources = {
            "manual_reference": EvidenceSourcePolicy(
                "manual_reference",
                "independent_reference",
                1.0,
                "manual_contract_v1",
                True,
            ),
            "expert_soft": EvidenceSourcePolicy(
                "expert_soft", "expert_review", 0.8, "expert_a", False
            ),
        }
        cls.evidence_payload = {
            "schema_version": "aip-observation-evidence-v1",
            "evidence_id": "hidden_die_pair_0000",
            "source_id": "manual_reference",
            "left_world_id": "left",
            "right_world_id": "right",
            "acting_player": 0,
            "observed_same": True,
        }
        cls.evidence = compile_trusted_evidence_json(
            cls.evidence_payload,
            sources=cls.sources,
            worlds=cls.worlds,
        )

    def compile(self, *candidates, exact=None):
        return compile_game_spec_candidate_json(
            payload(*candidates),
            self.vocabulary,
            exact_candidates=exact,
        )

    def score(self, arm_id, candidates, repairs=0):
        return score_pilot_case(
            arm_id=arm_id,
            candidate_set=candidates,
            trusted_reference=one_die_observation_spec(),
            vocabulary=self.vocabulary,
            evidence=(self.evidence,),
            required_evidence_ids=("hidden_die_pair_0000",),
            repair_count=repairs,
            conditional_solver_succeeded=None,
        )

    def test_single_wrong_candidate_is_valid_but_not_covered_or_certified(self):
        compiled = self.compile(VISIBLE, exact=1)
        score = self.score("single_no_feedback", compiled)
        self.assertFalse(score.true_model_candidate_coverage)
        self.assertEqual(score.verification.status, "conflicted")
        self.assertFalse(score.false_certification)

    def test_multi_candidate_set_covers_and_verifies_reference(self):
        compiled = self.compile(VISIBLE, HIDDEN, SWAPPED, exact=3)
        score = self.score("multi_structural_feedback", compiled, repairs=1)
        self.assertTrue(score.true_model_candidate_coverage)
        self.assertEqual(score.verification.status, "verified")
        self.assertEqual(score.verification.certified_hypothesis_id, "hidden")
        self.assertTrue(score.certified_reference_model)
        self.assertFalse(score.false_certification)
        self.assertEqual(compiled.to_artifact()["priors_assigned_by_evaluator"], [
            1 / 3, 1 / 3, 1 / 3
        ])

    def test_human_reference_ceiling_verifies_without_candidate_alternatives(self):
        compiled = self.compile(HIDDEN, exact=1)
        score = self.score("human_reference_ceiling", compiled)
        self.assertTrue(score.true_model_candidate_coverage)
        self.assertTrue(score.verification.certified)
        self.assertTrue(score.certified_reference_model)

    def test_closed_set_negative_control_refuses_overconfidence(self):
        compiled = self.compile(VISIBLE, SWAPPED, exact=2)
        score = self.score("true_model_absent_negative_control", compiled)
        self.assertFalse(score.true_model_candidate_coverage)
        self.assertEqual(score.verification.status, "conflicted")
        self.assertFalse(score.verification.certified)
        self.assertFalse(score.false_certification)

    def test_missing_or_soft_evidence_cannot_certify(self):
        compiled = self.compile(HIDDEN, exact=1)
        missing = verify_candidate_set(
            compiled, (), required_evidence_ids=("hidden_die_pair_0000",)
        )
        self.assertEqual(missing.status, "incomplete_evidence")

        soft_payload = dict(self.evidence_payload)
        soft_payload["source_id"] = "expert_soft"
        soft_payload["evidence_id"] = "soft_hidden_die_pair"
        soft = compile_trusted_evidence_json(
            soft_payload, sources=self.sources, worlds=self.worlds
        )
        untrusted = verify_candidate_set(
            compiled,
            (soft,),
            required_evidence_ids=("soft_hidden_die_pair",),
        )
        self.assertEqual(untrusted.status, "untrusted_evidence")
        self.assertFalse(untrusted.certified)

    def test_candidate_json_rejects_self_confidence_and_certification(self):
        for forbidden_key, value in (
            ("prior", 0.99),
            ("posterior", 0.99),
            ("certified", True),
            ("evidence_reliability", 1.0),
        ):
            with self.subTest(forbidden_key=forbidden_key):
                invalid = dict(HIDDEN)
                invalid[forbidden_key] = value
                with self.assertRaisesRegex(ValueError, "restricted schema"):
                    self.compile(invalid, exact=1)

    def test_candidate_json_rejects_unknown_missing_and_duplicate_fields(self):
        unknown = candidate("unknown", ("bids", "secret"), ("die_0",), ("die_1",))
        with self.assertRaisesRegex(ValueError, "partition"):
            self.compile(unknown, exact=1)
        missing = candidate("missing", ("bids",), ("die_0",), ())
        with self.assertRaisesRegex(ValueError, "partition"):
            self.compile(missing, exact=1)
        duplicate = candidate("duplicate", ("bids", "die_0"), ("die_0",), ("die_1",))
        with self.assertRaisesRegex(ValueError, "exactly once"):
            self.compile(duplicate, exact=1)
        with self.assertRaisesRegex(ValueError, "partitions must be unique"):
            self.compile(HIDDEN, dict(HIDDEN, hypothesis_id="hidden_copy"), exact=2)

    def test_evidence_json_cannot_self_assign_reliability_or_source(self):
        self.assertEqual(self.evidence.source.reliability, 1.0)
        invalid = dict(self.evidence_payload)
        invalid["reliability"] = 1.0
        with self.assertRaisesRegex(ValueError, "restricted schema"):
            compile_trusted_evidence_json(
                invalid, sources=self.sources, worlds=self.worlds
            )
        unknown = dict(self.evidence_payload)
        unknown["source_id"] = "model_claim"
        with self.assertRaisesRegex(ValueError, "not in the evaluator registry"):
            compile_trusted_evidence_json(
                unknown, sources=self.sources, worlds=self.worlds
            )

    def test_invalid_source_and_candidate_limits_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "hard evidence"):
            EvidenceSourcePolicy(
                "soft_certifier", "expert_review", 0.9, "expert", True
            )
        with self.assertRaisesRegex(ValueError, "may not certify"):
            EvidenceSourcePolicy(
                "synthetic", "synthetic_negative_control", 1.0, "test", True
            )
        with self.assertRaisesRegex(ValueError, "valid range"):
            compile_game_spec_candidate_json(
                payload(HIDDEN), self.vocabulary, minimum_candidates=0
            )

    def test_saved_dry_run_does_not_claim_llm_effect_or_enable_calls(self):
        root = Path(__file__).resolve().parents[1]
        artifact = json.loads((
            root
            / "research/results/llm_gamespec_pilot_protocol_dry_run_2026-10-20.json"
        ).read_text())
        self.assertTrue(artifact["primary_passed"])
        self.assertFalse(artifact["paid_model_calls"])
        self.assertFalse(
            artifact["execution_readiness"]["provider_calls_allowed"]
        )
        self.assertFalse(artifact["promotion"]["llm_effect_established"])
        self.assertFalse(
            artifact["promotion"]["runtime_epsilon_gto_allowed"]
        )
        negative = artifact["true_model_absent_negative_control"]
        self.assertFalse(negative["true_model_candidate_coverage"])
        self.assertEqual(negative["verification"]["status"], "conflicted")
        self.assertFalse(negative["false_certification"])


if __name__ == "__main__":
    unittest.main()
