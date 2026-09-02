import json
import unittest
from dataclasses import replace

from aip.benchmark import (
    AgentDecision,
    BeliefOutput,
    FROZEN_TRANSFER_BUNDLE_V1,
    FROZEN_TRANSFER_MANIFEST_V1,
    FrozenTransferBundle,
    MASTERMIND_BELIEF_TARGET,
    MastermindBenchmarkAdapter,
    audit_mastermind_holdout,
    run_mastermind_reference,
    summarize_mastermind_traces,
)


class MastermindBenchmarkTests(unittest.TestCase):
    def test_frozen_prompt_and_memory_pass_target_leakage_audit(self) -> None:
        audit = audit_mastermind_holdout(FROZEN_TRANSFER_BUNDLE_V1)
        self.assertTrue(audit.passed)
        self.assertEqual(audit.findings, ())
        self.assertNotIn(
            "mastermind", audit.manifest["sourceEnvironmentIds"]
        )
        self.assertEqual(audit.manifest, FROZEN_TRANSFER_MANIFEST_V1)

    def test_leakage_audit_rejects_target_sources_examples_and_recipes(self) -> None:
        source_leak = replace(
            FROZEN_TRANSFER_BUNDLE_V1,
            source_environment_ids=("guess-who", "mastermind"),
        )
        self.assertFalse(audit_mastermind_holdout(source_leak).passed)
        content_leak = FrozenTransferBundle(
            prompt="Begin with 0123 and inspect misplaced digits.",
            memory="Use submit_guess.",
            source_environment_ids=("guess-who",),
        )
        audit = audit_mastermind_holdout(content_leak)
        self.assertFalse(audit.passed)
        self.assertGreaterEqual(len(audit.findings), 3)

    def test_initial_input_is_spoiler_safe_and_payload_contract_is_explicit(self) -> None:
        adapter = MastermindBenchmarkAdapter("9876")
        decision_input = adapter.decision_input()
        serialized = json.dumps(decision_input.information_state, sort_keys=True)
        self.assertNotIn("9876", serialized)
        self.assertNotIn("secret", serialized.casefold())
        self.assertEqual(decision_input.episode_id, "mastermind:held-out:episode")
        self.assertEqual(len(decision_input.legal_actions), 1)
        self.assertEqual(
            decision_input.legal_actions[0].payload_schema,
            {"guess": "four_distinct_digit_string"},
        )
        self.assertEqual(
            decision_input.information_state["referenceScope"],
            "bounded_one_step_minimax_heuristic",
        )

    def test_exact_feedback_updates_candidates_without_exposing_exact_regret(self) -> None:
        adapter = MastermindBenchmarkAdapter("9876")
        transition = adapter.apply_decision(
            AgentDecision(
                "submit_guess",
                confidence=0.5,
                payload={"guess": "0123"},
            )
        )
        self.assertTrue(transition.evaluation["trueSecretRetained"])
        self.assertGreater(transition.evaluation["informationGainBits"], 0)
        self.assertNotIn("actionRegret", transition.evaluation)
        self.assertNotIn("optimalPolicyAgreement", transition.evaluation)
        self.assertNotIn("exploitability", transition.evaluation)
        self.assertEqual(
            transition.evaluation["referenceEvidenceLevel"], "strong_heuristic"
        )
        self.assertLess(
            adapter.decision_input().information_state["candidateCount"], 5040
        )

    def test_invalid_guess_and_wrong_belief_do_not_mutate_state(self) -> None:
        adapter = MastermindBenchmarkAdapter("9876")
        with self.assertRaisesRegex(ValueError, "may not repeat"):
            adapter.apply_decision(
                AgentDecision(
                    "submit_guess", 0.5, payload={"guess": "0012"}
                )
            )
        self.assertEqual(adapter.decision_input().step, 0)
        with self.assertRaisesRegex(ValueError, "belief target"):
            adapter.apply_decision(
                AgentDecision(
                    "submit_guess",
                    0.5,
                    payload={"guess": "0123"},
                    belief=BeliefOutput("secret_code", {"0123": 1.0}),
                )
            )
        self.assertEqual(adapter.decision_input().step, 0)

    def test_heuristic_reference_trace_has_exact_predictive_belief(self) -> None:
        trace = run_mastermind_reference("9876")
        self.assertTrue(trace.result["solved"])
        self.assertEqual(trace.evidence_level.value, "strong_heuristic")
        self.assertLessEqual(trace.result["attempts"], 10)
        self.assertTrue(
            all(step.evaluation["trueSecretRetained"] for step in trace.steps)
        )
        self.assertTrue(
            all(
                step.evaluation["heuristicReferenceAgreement"]
                for step in trace.steps
            )
        )
        self.assertTrue(
            all(
                abs(step.evaluation["beliefPredictiveTvDistance"]) < 1e-12
                for step in trace.steps
            )
        )
        for step in trace.steps:
            serialized = json.dumps(step.decision_input.information_state)
            self.assertNotIn("secret", serialized.casefold())
            self.assertNotIn("9876", step.decision_input.episode_id)
            self.assertNotIn("actionRegret", step.evaluation)
        summary = summarize_mastermind_traces((trace,))
        self.assertEqual(summary.solved_rate, 1.0)
        self.assertEqual(summary.heuristic_reference_agreement, 1.0)
        self.assertEqual(summary.mean_predictive_tv_distance, 0.0)
        self.assertEqual(summary.belief_output_rate, 1.0)


if __name__ == "__main__":
    unittest.main()
