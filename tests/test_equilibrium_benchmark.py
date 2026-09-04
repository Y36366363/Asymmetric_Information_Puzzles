import unittest
from fractions import Fraction

from aip.benchmark import evaluate_goofspiel_policy, evaluate_kuhn_policy
from aip.puzzles.kuhn_poker import equilibrium_policy, legacy_policy
from scripts.audit_equilibrium_benchmark import report


class EquilibriumBenchmarkTests(unittest.TestCase):
    def test_kuhn_equilibrium_has_zero_regret_exploitability_and_distance(self) -> None:
        metrics = evaluate_kuhn_policy(equilibrium_policy())
        self.assertEqual(metrics.maximum_candidate_regret, 0)
        self.assertEqual(metrics.maximum_exploitability, 0)
        self.assertEqual(metrics.mean_information_set_tv_distance, 0)
        self.assertEqual(metrics.equilibrium_support_violations, 0)

    def test_kuhn_legacy_policy_separates_regret_from_exploitability(self) -> None:
        metrics = evaluate_kuhn_policy(legacy_policy())
        self.assertEqual(metrics.exploitability_when_candidate_first, Fraction(1, 9))
        self.assertGreaterEqual(metrics.maximum_candidate_regret, 0)
        self.assertGreater(metrics.mean_information_set_tv_distance, 0)

    def test_goofspiel_equilibrium_has_zero_exact_metrics(self) -> None:
        metrics = evaluate_goofspiel_policy("equilibrium")
        self.assertEqual(metrics.game_value, 0)
        self.assertEqual(metrics.candidate_regret, 0)
        self.assertEqual(metrics.exploitability, 0)
        self.assertEqual(metrics.mean_root_tv_distance, 0)

    def test_goofspiel_heuristics_are_exactly_exploitable(self) -> None:
        match = evaluate_goofspiel_policy("match_prize")
        high = evaluate_goofspiel_policy("high_card")
        self.assertGreater(match.exploitability, 0)
        self.assertGreater(high.exploitability, 0)
        self.assertGreater(match.mean_root_tv_distance, 0)
        self.assertGreaterEqual(match.candidate_regret, 0)

    def test_export_keeps_exact_values_and_future_work_explicit(self) -> None:
        payload = report()
        self.assertEqual(
            payload["kuhnPoker"]["legacy"]["exploitability_when_candidate_first"]["exact"],
            "1/9",
        )
        self.assertFalse(payload["claims"]["llmEvaluationExecuted"])
        self.assertFalse(payload["claims"]["formalAblationExecuted"])


if __name__ == "__main__":
    unittest.main()
