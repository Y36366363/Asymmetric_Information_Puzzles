import json
import tempfile
import unittest
from pathlib import Path

from aip.benchmark import (
    AgentDecision,
    BeliefOutput,
    GuessWhoBenchmarkAdapter,
    OptimalGuessWhoAgent,
    run_episode,
    summarize_guess_who_traces,
)
from aip.puzzles.guess_who import DEFAULT_ROSTER


class GuessWhoBenchmarkTests(unittest.TestCase):
    def test_oracle_trace_is_replayable_calibrated_and_spoiler_safe(self) -> None:
        trace = run_episode(
            GuessWhoBenchmarkAdapter("Ada", include_rules=True),
            OptimalGuessWhoAgent(),
            agent_id="algorithmic-oracle",
        )
        self.assertTrue(trace.result["solved"])
        self.assertEqual(trace.evidence_level.value, "proved_optimality")
        self.assertTrue(
            all(step.evaluation["optimalPolicyAgreement"] for step in trace.steps)
        )
        self.assertTrue(
            all(abs(float(step.evaluation["actionRegret"])) < 1e-12 for step in trace.steps)
        )
        for step in trace.steps[:-1]:
            self.assertNotIn("secret", step.decision_input.information_state)
            self.assertGreater(float(step.evaluation["trueStateProbability"]), 0)

        payload = json.loads(trace.to_json())
        self.assertEqual(payload["schemaVersion"], "aip-benchmark-trace-v0")
        self.assertEqual(len(payload["steps"]), len(trace.steps))
        with tempfile.TemporaryDirectory() as directory:
            path = trace.write_json(Path(directory) / "trace.json")
            self.assertEqual(json.loads(path.read_text()), payload)

    def test_exhaustive_oracle_suite_matches_exact_policy(self) -> None:
        oracle = OptimalGuessWhoAgent()
        traces = tuple(
            run_episode(
                GuessWhoBenchmarkAdapter(character.name),
                oracle,
                agent_id="algorithmic-oracle",
            )
            for character in DEFAULT_ROSTER
        )
        summary = summarize_guess_who_traces(traces)
        self.assertEqual(summary.episodes, 24)
        self.assertEqual(summary.solved_rate, 1.0)
        self.assertAlmostEqual(summary.mean_turns, 17 / 3)
        self.assertEqual(summary.worst_turns, 6)
        self.assertEqual(summary.optimal_policy_agreement, 1.0)
        self.assertAlmostEqual(summary.mean_action_regret, 0.0)
        self.assertEqual(summary.belief_output_rate, 1.0)
        self.assertGreater(summary.mean_information_efficiency_bits_per_question, 0)

    def test_adapter_rejects_illegal_action_before_mutating_state(self) -> None:
        adapter = GuessWhoBenchmarkAdapter("Ada")
        with self.assertRaisesRegex(ValueError, "illegal agent action"):
            adapter.apply_decision(AgentDecision("guess_character:Ada", confidence=1))
        self.assertEqual(adapter.decision_input().step, 0)

    def test_suboptimal_question_receives_exact_positive_regret(self) -> None:
        adapter = GuessWhoBenchmarkAdapter("Ada")
        transition = adapter.apply_decision(
            AgentDecision("ask_question:hair_black", confidence=0.5)
        )
        self.assertFalse(transition.evaluation["optimalPolicyAgreement"])
        self.assertAlmostEqual(float(transition.evaluation["actionRegret"]), 1 / 6)
        self.assertIsNone(transition.evaluation["beliefBrier"])

    def test_rules_are_optional_without_changing_the_state(self) -> None:
        hidden = GuessWhoBenchmarkAdapter("Ada").decision_input()
        included = GuessWhoBenchmarkAdapter("Ada", include_rules=True).decision_input()
        self.assertIsNone(hidden.natural_language_rules)
        self.assertIn("uniform prior", included.natural_language_rules or "")
        self.assertEqual(hidden.legal_actions, included.legal_actions)
        self.assertEqual(len(hidden.information_state["candidateProfiles"]), 24)

    def test_zero_probability_on_truth_is_finite_and_valid_json(self) -> None:
        adapter = GuessWhoBenchmarkAdapter("Ada")
        transition = adapter.apply_decision(
            AgentDecision(
                "ask_question:glasses",
                confidence=0.5,
                belief=BeliefOutput(
                    "secret_character",
                    {"Bruno": 1.0},
                ),
            )
        )
        self.assertTrue(transition.evaluation["zeroProbabilityOnTruth"])
        self.assertGreater(float(transition.evaluation["beliefLogLoss"]), 30)

    def test_missing_beliefs_are_reported_as_missing_not_zero(self) -> None:
        oracle = OptimalGuessWhoAgent()

        class NoBeliefAgent:
            def choose_action(self, decision):
                chosen = oracle.choose_action(decision)
                return AgentDecision(chosen.action_id, chosen.confidence)

        trace = run_episode(
            GuessWhoBenchmarkAdapter("Ada"),
            NoBeliefAgent(),
            agent_id="no-belief-oracle",
        )
        summary = summarize_guess_who_traces((trace,))
        self.assertEqual(summary.belief_output_rate, 0.0)
        self.assertIsNone(summary.mean_belief_brier)
        self.assertIsNone(summary.mean_belief_log_loss)


if __name__ == "__main__":
    unittest.main()
