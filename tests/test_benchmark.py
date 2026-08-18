import unittest

from aip.benchmark import (
    V1_ENVIRONMENTS,
    ActionEvent,
    ActionSpec,
    AgentDecision,
    AgentInput,
    BeliefOutput,
    EvidenceLevel,
    StrategicCapability,
    environment_spec,
    validate_decision,
)


class BenchmarkContractTests(unittest.TestCase):
    def sample_input(self) -> AgentInput:
        return AgentInput(
            environment_id="guess-who",
            episode_id="episode-1",
            step=2,
            observation={"lastAnswer": True},
            information_state={"candidates": ["Ada", "Cleo"]},
            legal_actions=(
                ActionSpec("ask", payload_schema={"questionId": "string"}),
                ActionSpec("guess", payload_schema={"name": "string"}),
            ),
            action_history=(
                ActionEvent(
                    actor_id="agent",
                    action_id="ask",
                    payload={"questionId": "glasses"},
                    public_observation={"answer": True},
                ),
            ),
            natural_language_rules="Ask questions or name the hidden character.",
        )

    def test_contract_accepts_a_legal_decision_with_calibrated_belief(self) -> None:
        decision_input = self.sample_input()
        output = AgentDecision(
            action_id="guess",
            payload={"name": "Ada"},
            belief=BeliefOutput(
                target="secret_character",
                probabilities={"Ada": 0.6, "Cleo": 0.4},
            ),
            confidence=0.6,
        )
        validate_decision(decision_input, output)

    def test_contract_rejects_illegal_actions_and_undeclared_payloads(self) -> None:
        decision_input = self.sample_input()
        with self.assertRaisesRegex(ValueError, "illegal agent action"):
            validate_decision(
                decision_input,
                AgentDecision(action_id="peek", confidence=1.0),
            )
        with self.assertRaisesRegex(ValueError, "undeclared fields"):
            validate_decision(
                decision_input,
                AgentDecision(
                    action_id="guess",
                    payload={"name": "Ada", "hiddenState": "Cleo"},
                    confidence=0.5,
                ),
            )

    def test_beliefs_and_confidence_must_be_probabilities(self) -> None:
        with self.assertRaisesRegex(ValueError, "sum to 1"):
            BeliefOutput(
                target="secret",
                probabilities={"left": 0.7, "right": 0.4},
            )
        with self.assertRaisesRegex(ValueError, "confidence"):
            AgentDecision(action_id="ask", confidence=1.1)
        with self.assertRaisesRegex(ValueError, "between 0 and 1"):
            BeliefOutput(target="secret", probabilities={"state": float("nan")})

    def test_input_rejects_duplicate_legal_action_ids(self) -> None:
        with self.assertRaisesRegex(ValueError, "unique"):
            AgentInput(
                environment_id="worm",
                episode_id="duplicate-actions",
                step=0,
                observation={},
                information_state={"possible": [1, 2, 3, 4, 5]},
                legal_actions=(ActionSpec("check"), ActionSpec("check")),
            )

    def test_v1_catalog_is_small_complementary_and_has_one_holdout(self) -> None:
        self.assertEqual(len(V1_ENVIRONMENTS), 6)
        self.assertEqual(
            [spec.environment_id for spec in V1_ENVIRONMENTS if spec.held_out],
            ["mastermind"],
        )
        covered = set().union(*(spec.capabilities for spec in V1_ENVIRONMENTS))
        self.assertEqual(covered, set(StrategicCapability))

    def test_catalog_keeps_proofs_equilibria_and_heuristics_distinct(self) -> None:
        self.assertEqual(
            environment_spec("guess-who").evidence_level,
            EvidenceLevel.PROVED_OPTIMAL,
        )
        self.assertEqual(
            environment_spec("kuhn-poker").evidence_level,
            EvidenceLevel.EQUILIBRIUM_BACKED,
        )
        self.assertEqual(
            environment_spec("liars-dice").evidence_level,
            EvidenceLevel.STRONG_HEURISTIC,
        )
        self.assertTrue(
            environment_spec("goofspiel").ground_truth.computable_exploitability
        )
        self.assertTrue(
            environment_spec("mastermind").ground_truth.belief_ground_truth
        )
        self.assertFalse(
            environment_spec("mastermind").ground_truth.exact_optimal_policy
        )


if __name__ == "__main__":
    unittest.main()
