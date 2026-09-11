import unittest
from pathlib import Path

from aip.core import (
    CFRCertificationGate,
    CFRGateFailure,
    CFRGameProperties,
    CFRResult,
    CFRThresholds,
    CFRTrainer,
    ChanceSamplingCFRTrainer,
    ExternalSamplingCFRTrainer,
)
from aip.puzzles.kuhn_poker import (
    audit_policy,
    certify_kuhn_cfr,
    kuhn_policy_from_cfr,
    train_kuhn_cfr,
)
from aip.puzzles.liars_dice import (
    certify_one_die_liar_cfr,
    load_one_die_liar_policy,
    one_die_liar_exploitability,
    required_one_die_information_sets,
    train_one_die_liar_cfr,
)


class CFRFrameworkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.result = train_kuhn_cfr(50_000)

    def test_kuhn_adapter_discovers_a_low_exploitability_policy(self) -> None:
        policy = kuhn_policy_from_cfr(self.result)
        audit = audit_policy(policy)
        self.assertEqual(self.result.information_set_count, 12)
        self.assertLess(float(audit.maximum_exploitability), 0.01)

    def test_default_gate_promotes_the_converged_kuhn_policy(self) -> None:
        report = certify_kuhn_cfr(self.result)
        self.assertTrue(report.passed)
        self.assertEqual(report.failures, ())
        self.assertLessEqual(report.exploitability, 0.01)
        report.require_passed()

    def test_gate_rejects_missing_independent_exploitability(self) -> None:
        report = CFRCertificationGate(
            CFRThresholds(
                min_iterations=1,
                min_information_sets=1,
                min_visits_per_information_set=1,
                max_average_positive_regret=1,
                max_exploitability=1,
            )
        ).evaluate(
            self.result,
            exploitability=None,
            game_properties=CFRGameProperties(2, True, True, True),
        )
        self.assertFalse(report.passed)
        self.assertIn("independent_exploitability_required", report.failures)
        with self.assertRaises(CFRGateFailure):
            report.require_passed()

    def test_gate_checks_game_specific_information_set_identities(self) -> None:
        report = CFRCertificationGate(
            CFRThresholds(
                min_iterations=1,
                min_information_sets=1,
                min_visits_per_information_set=1,
                max_average_positive_regret=1,
                max_exploitability=1,
            )
        ).evaluate(
            self.result,
            exploitability=0,
            required_information_sets=frozenset({(0, ("missing", "history"))}),
            game_properties=CFRGameProperties(2, True, True, True),
        )
        self.assertFalse(report.passed)
        self.assertIn("missing_required_information_sets", report.failures)

    def test_gate_diagnostics_identify_undertraining(self) -> None:
        short_result = train_kuhn_cfr(100)
        report = certify_kuhn_cfr(short_result)
        self.assertFalse(report.passed)
        self.assertIn("insufficient_iterations", report.failures)
        self.assertIn("insufficient_information_set_visits", report.failures)
        self.assertTrue(
            {
                "average_positive_regret_above_threshold",
                "exploitability_above_threshold",
            }
            & set(report.failures)
        )

    def test_gate_rejects_nonfinite_diagnostics_and_negative_exploitability(self) -> None:
        malformed = CFRResult(
            iterations=10,
            policy={(0, "only"): {"act": 1.0}},
            information_set_visits={(0, "only"): 10},
            average_positive_regret=(float("nan"), 0.0),
        )
        gate = CFRCertificationGate(
            CFRThresholds(
                min_iterations=1,
                min_information_sets=1,
                min_visits_per_information_set=1,
                max_average_positive_regret=1,
                max_exploitability=1,
            )
        )
        report = gate.evaluate(
            malformed,
            exploitability=-0.1,
            game_properties=CFRGameProperties(2, True, True, True),
        )
        self.assertFalse(report.passed)
        self.assertIn("invalid_regret_diagnostic", report.failures)
        self.assertIn("invalid_exploitability", report.failures)

    def test_gate_rejects_negative_regret_hidden_by_a_positive_player(self) -> None:
        malformed = CFRResult(
            iterations=10,
            policy={(0, "only"): {"act": 1.0}},
            information_set_visits={(0, "only"): 10},
            average_positive_regret=(-0.1, 0.2),
        )
        gate = CFRCertificationGate(
            CFRThresholds(
                min_iterations=1,
                min_information_sets=1,
                min_visits_per_information_set=1,
                max_average_positive_regret=1,
                max_exploitability=1,
            )
        )
        report = gate.evaluate(
            malformed,
            exploitability=0,
            game_properties=CFRGameProperties(2, True, True, True),
        )
        self.assertIn("invalid_regret_diagnostic", report.failures)

    def test_exact_gate_rejects_extra_sets_and_mismatched_visit_keys(self) -> None:
        malformed = CFRResult(
            iterations=10,
            policy={
                (0, "expected"): {"act": 1.0},
                (0, "extra"): {"act": 1.0},
            },
            information_set_visits={(0, "expected"): 10},
            average_positive_regret=(0.0, 0.0),
        )
        gate = CFRCertificationGate(
            CFRThresholds(
                min_iterations=1,
                min_information_sets=1,
                min_visits_per_information_set=1,
                max_average_positive_regret=1,
                max_exploitability=1,
            )
        )
        report = gate.evaluate(
            malformed,
            exploitability=0,
            required_information_sets=frozenset({(0, "expected")}),
            exact_information_sets=True,
            game_properties=CFRGameProperties(2, True, True, True),
        )
        self.assertIn("unexpected_information_sets", report.failures)
        self.assertIn("invalid_information_set_visits", report.failures)

    def test_gate_requires_supported_game_properties(self) -> None:
        gate = CFRCertificationGate(
            CFRThresholds(
                min_iterations=1,
                min_information_sets=1,
                min_visits_per_information_set=1,
                max_average_positive_regret=1,
                max_exploitability=1,
            )
        )
        missing = gate.evaluate(self.result, exploitability=0)
        unsupported = gate.evaluate(
            self.result,
            exploitability=0,
            game_properties=CFRGameProperties(3, True, False, True),
        )
        self.assertIn("game_properties_required", missing.failures)
        self.assertIn("unsupported_game_properties", unsupported.failures)

    def test_trainer_rejects_nonfinite_terminal_utility(self) -> None:
        class NonfiniteTerminalGame:
            def initial_state(self): return "terminal"
            def is_terminal(self, state): return True
            def utility_player_zero(self, state): return float("inf")
            def current_player(self, state): return None
            def chance_outcomes(self, state): return ()
            def legal_actions(self, state): return ()
            def information_set(self, state): return "unused"
            def next_state(self, state, action): return state

        with self.assertRaisesRegex(ValueError, "utility must be finite"):
            CFRTrainer(NonfiniteTerminalGame()).train(1)

    def test_trainers_reject_duplicate_player_and_chance_actions(self) -> None:
        class DuplicatePlayerActionGame:
            def initial_state(self): return "play"
            def is_terminal(self, state): return state == "terminal"
            def utility_player_zero(self, state): return 0.0
            def current_player(self, state): return 0
            def chance_outcomes(self, state): return ()
            def legal_actions(self, state): return ("same", "same")
            def information_set(self, state): return "duplicate"
            def next_state(self, state, action): return "terminal"

        class DuplicateChanceActionGame(DuplicatePlayerActionGame):
            def initial_state(self): return "chance"
            def current_player(self, state): return None if state == "chance" else 0
            def chance_outcomes(self, state):
                return (("same", 0.5), ("same", 0.5)) if state == "chance" else ()

        with self.assertRaisesRegex(ValueError, "duplicate legal actions"):
            CFRTrainer(DuplicatePlayerActionGame()).train(1)
        with self.assertRaisesRegex(ValueError, "valid chance node"):
            ChanceSamplingCFRTrainer(DuplicateChanceActionGame()).train(1)

    def test_chance_sampling_is_seeded_and_reproducible(self) -> None:
        first = train_one_die_liar_cfr(50, seed=7)
        second = train_one_die_liar_cfr(50, seed=7)
        self.assertEqual(first.policy, second.policy)
        self.assertEqual(first.information_set_visits, second.information_set_visits)

    def test_external_sampling_handles_later_private_chance_nodes(self) -> None:
        class LaterChanceMatchingGame:
            def initial_state(self):
                return ("first", None, None, None)

            def is_terminal(self, state):
                return state[0] == "terminal"

            def utility_player_zero(self, state):
                _, first, signal, second = state
                matches = first == second
                return 1.0 if matches == (signal == 0) else -1.0

            def current_player(self, state):
                return {"first": 0, "chance": None, "second": 1}.get(state[0])

            def chance_outcomes(self, state):
                return ((0, 0.5), (1, 0.5)) if state[0] == "chance" else ()

            def legal_actions(self, state):
                return ("heads", "tails") if state[0] in {"first", "second"} else ()

            def information_set(self, state):
                return "root" if state[0] == "first" else ("signal", state[2])

            def next_state(self, state, action):
                stage, first, signal, _ = state
                if stage == "first":
                    return ("chance", action, None, None)
                if stage == "chance":
                    return ("second", first, action, None)
                return ("terminal", first, signal, action)

        first = ExternalSamplingCFRTrainer(
            LaterChanceMatchingGame(), seed=11
        ).train(50_000)
        second = ExternalSamplingCFRTrainer(
            LaterChanceMatchingGame(), seed=11
        ).train(50_000)
        self.assertEqual(first.policy, second.policy)
        self.assertEqual(first.information_set_count, 3)
        self.assertAlmostEqual(
            first.policy[(0, "root")]["heads"], 0.5, delta=0.03
        )
        # The equilibrium is not unique: player one may use any mixture as long
        # as it is the same after either signal, keeping player zero indifferent.
        self.assertAlmostEqual(
            first.policy[(1, ("signal", 0))]["heads"],
            first.policy[(1, ("signal", 1))]["heads"],
            delta=0.03,
        )
        first_heads = first.policy[(0, "root")]["heads"]
        signal_zero_heads = first.policy[(1, ("signal", 0))]["heads"]
        signal_one_heads = first.policy[(1, ("signal", 1))]["heads"]
        exploitability = (
            abs(signal_zero_heads - signal_one_heads)
            + abs(2 * first_heads - 1)
        ) / 2
        self.assertLess(exploitability, 0.03)

    def test_external_sampling_recovers_kuhn_against_exact_best_response(self) -> None:
        from aip.puzzles.kuhn_poker.cfr import KuhnCFRGame

        result = ExternalSamplingCFRTrainer(KuhnCFRGame(), seed=7).train(50_000)
        exploitability = float(
            audit_policy(kuhn_policy_from_cfr(result)).maximum_exploitability
        )
        self.assertEqual(result.information_set_count, 12)
        self.assertLess(exploitability, 0.01)

    def test_certified_one_die_liar_artifact_passes_independent_best_response(self) -> None:
        source = (
            Path(__file__).resolve().parents[1]
            / "src/aip/puzzles/liars_dice/one_die_cfr_policy.json"
        )
        result = load_one_die_liar_policy(source)
        report = certify_one_die_liar_cfr(result)
        self.assertTrue(report.passed, report.failures)
        self.assertEqual(result.information_set_count, 348)
        self.assertEqual(set(result.policy), set(required_one_die_information_sets()))
        self.assertAlmostEqual(
            report.exploitability, one_die_liar_exploitability(result)
        )
        self.assertLess(report.exploitability, 0.01)


if __name__ == "__main__":
    unittest.main()
