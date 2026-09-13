import json
import tempfile
import unittest
from pathlib import Path

from aip.core import (
    CFRArtifactExporter,
    CFRPlusTrainer,
    DCFRTrainer,
    ExternalSamplingCFRTrainer,
    RegretMatchingPlusUpdate,
    create_regret_minimization_trainer,
)
from aip.puzzles.kuhn_poker import (
    KuhnCFRGame,
    evaluate_kuhn_cfr,
    kuhn_policy_from_cfr,
    policy_value,
)


REFERENCE_10K = {
    "vanilla_cfr": {
        "value": -0.055563518262057715,
        "exploitability": 0.00011332445786397041,
        "trace": (
            0.06869879381715763,
            0.008225977315915806,
            0.000937616646994377,
            0.00011332445786397041,
        ),
    },
    "cfr_plus": {
        "value": -0.055555559111169994,
        "exploitability": 9.632756981008128e-06,
        "trace": (
            0.03268709066834479,
            0.0011944041011115875,
            8.73653225207903e-05,
            9.632756981008128e-06,
        ),
    },
    "dcfr": {
        "value": -0.055555554874280766,
        "exploitability": 1.2347051583747048e-05,
        "trace": (
            0.02188001426854977,
            0.0012821110231544877,
            0.00015782629441524892,
            1.2347051583747048e-05,
        ),
    },
}


def independent_metrics(result):
    return evaluate_kuhn_cfr(result).to_report()


class ReverseChanceKuhn(KuhnCFRGame):
    def chance_outcomes(self, state):
        return tuple(reversed(super().chance_outcomes(state)))


class RegretMinimizationCompositionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.results = {}
        for algorithm_id in REFERENCE_10K:
            cls.results[algorithm_id] = create_regret_minimization_trainer(
                KuhnCFRGame(), algorithm_id
            ).train(
                10_000,
                checkpoints={10, 100, 1_000, 10_000},
                independent_evaluator=independent_metrics,
            )

    def test_kuhn_algorithms_match_external_numeric_references(self) -> None:
        for algorithm_id, reference in REFERENCE_10K.items():
            with self.subTest(algorithm_id=algorithm_id):
                result = self.results[algorithm_id]
                policy = kuhn_policy_from_cfr(result)
                value = float(policy_value(policy, policy, hero_first=True))
                evaluation = evaluate_kuhn_cfr(result)
                self.assertAlmostEqual(value, reference["value"], delta=1e-8)
                self.assertAlmostEqual(
                    evaluation.exploitability,
                    reference["exploitability"],
                    delta=5e-8,
                )
                self.assertLess(evaluation.exploitability, 0.01)
                self.assertEqual(result.information_set_count, 12)

    def test_every_checkpoint_uses_exact_best_response_metrics(self) -> None:
        for algorithm_id, reference in REFERENCE_10K.items():
            with self.subTest(algorithm_id=algorithm_id):
                result = self.results[algorithm_id]
                self.assertEqual(
                    tuple(point.iteration for point in result.convergence_trace),
                    (10, 100, 1_000, 10_000),
                )
                actual = tuple(
                    point.independent_evaluation["exploitability"]
                    for point in result.convergence_trace
                )
                for observed, expected in zip(actual, reference["trace"]):
                    self.assertAlmostEqual(observed, expected, delta=5e-8)
                self.assertGreater(actual[0], actual[-1])

    def test_algorithm_composition_and_metadata_are_explicit(self) -> None:
        vanilla = self.results["vanilla_cfr"].algorithm
        plus = self.results["cfr_plus"].algorithm
        dcfr = self.results["dcfr"].algorithm
        self.assertEqual(vanilla.traversal, "full_tree")
        self.assertEqual(vanilla.update_schedule, "alternating_players")
        self.assertEqual(vanilla.averaging_rule, "uniform_iteration_weighting")
        self.assertIsNone(vanilla.seed)
        self.assertEqual(plus.averaging_rule, "linear_iteration_weighting")
        self.assertEqual(dcfr.parameters, {"alpha": 1.5, "beta": 0.0, "gamma": 2.0})
        self.assertIsInstance(
            CFRPlusTrainer(KuhnCFRGame()).regret_update_policy,
            RegretMatchingPlusUpdate,
        )
        self.assertIsInstance(
            DCFRTrainer(KuhnCFRGame()),
            type(create_regret_minimization_trainer(KuhnCFRGame(), "dcfr")),
        )

    def test_external_sampling_uses_the_same_composable_contract(self) -> None:
        direct = ExternalSamplingCFRTrainer(KuhnCFRGame(), seed=17).train(100)
        routed = create_regret_minimization_trainer(
            KuhnCFRGame(), "external_sampling_mccfr", seed=17
        ).train(100)
        self.assertEqual(direct.policy, routed.policy)
        self.assertEqual(
            routed.algorithm.to_artifact(),
            {
                "algorithm_id": "external_sampling_mccfr",
                "parameters": {},
                "traversal": "external_sampling",
                "update_schedule": "alternating_players",
                "averaging_rule": "uniform_iteration_weighting",
                "seed": 17,
            },
        )

    def test_all_full_tree_update_policies_remain_chance_order_invariant(self) -> None:
        for algorithm_id in REFERENCE_10K:
            with self.subTest(algorithm_id=algorithm_id):
                forward = create_regret_minimization_trainer(
                    KuhnCFRGame(), algorithm_id
                ).train(100)
                reversed_result = create_regret_minimization_trainer(
                    ReverseChanceKuhn(), algorithm_id
                ).train(100)
                self.assertEqual(forward.policy, reversed_result.policy)

    def test_artifact_separates_training_diagnostics_from_best_response(self) -> None:
        result = self.results["dcfr"]
        evaluation = evaluate_kuhn_cfr(result)
        artifact = CFRArtifactExporter().build(
            result, game_id="canonical_kuhn_poker", independent_evaluation=evaluation
        )
        self.assertEqual(artifact["algorithm"], result.algorithm.to_artifact())
        self.assertTrue(
            artifact["training_diagnostics"]["not_an_exploitability_measure"]
        )
        self.assertEqual(
            artifact["independent_evaluation"]["exploitability"],
            evaluation.exploitability,
        )
        self.assertEqual(len(artifact["convergence_trace"]), 4)
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "artifact.json"
            CFRArtifactExporter().write(
                result,
                destination,
                game_id="canonical_kuhn_poker",
                independent_evaluation=evaluation,
            )
            self.assertIn('"algorithm_id": "dcfr"', destination.read_text())

    def test_checkpoint_cannot_substitute_training_regret_for_best_response(self) -> None:
        trainer = create_regret_minimization_trainer(KuhnCFRGame(), "vanilla_cfr")
        with self.assertRaisesRegex(ValueError, "independent evaluator"):
            trainer.train(10, checkpoints={10})
        with self.assertRaisesRegex(ValueError, "five finite"):
            create_regret_minimization_trainer(
                KuhnCFRGame(), "vanilla_cfr"
            ).train(
                10,
                checkpoints={10},
                independent_evaluator=lambda result: {
                    "exploitability": result.average_positive_regret[0]
                },
            )

    def test_invalid_algorithm_ids_and_parameters_fail_closed(self) -> None:
        with self.assertRaisesRegex(ValueError, "unknown regret-minimization"):
            create_regret_minimization_trainer(KuhnCFRGame(), "magic_cfr")
        with self.assertRaisesRegex(ValueError, "does not accept"):
            create_regret_minimization_trainer(
                KuhnCFRGame(), "cfr_plus", parameters={"alpha": 1.5}
            )
        with self.assertRaisesRegex(ValueError, "unknown DCFR parameters"):
            create_regret_minimization_trainer(
                KuhnCFRGame(), "dcfr", parameters={"delta": 1.0}
            )
        for value in (float("nan"), float("inf"), float("-inf")):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "finite"):
                create_regret_minimization_trainer(
                    KuhnCFRGame(), "dcfr", parameters={"alpha": value}
                )
        with self.assertRaisesRegex(ValueError, "gamma"):
            create_regret_minimization_trainer(
                KuhnCFRGame(), "dcfr", parameters={"gamma": -1.0}
            )

    def test_frozen_leduc_reference_is_data_only_and_fail_closed(self) -> None:
        source = (
            Path(__file__).resolve().parents[1]
            / "configs/poker_capability_lab_regret_reference_v1.json"
        )
        reference = json.loads(source.read_text(encoding="utf-8"))
        self.assertEqual(
            reference["dependency_policy"],
            "frozen_numeric_reference_only_no_source_import",
        )
        self.assertEqual(
            reference["leduc_release"]["information_sets_per_player"], 144
        )
        self.assertGreater(
            reference["leduc_release"]["uniform_strategy_exploitability"], 2.0
        )
        self.assertLess(reference["leduc_release"]["dcfr"]["exploitability"], 0.001)


if __name__ == "__main__":
    unittest.main()
