import json
import unittest
from dataclasses import replace

from aip.benchmark import (
    GENERIC_WEAK_METADATA,
    SINGLE_GAME_PROMPT_METADATA,
    GenericWeakRandomAgent,
    GuessWhoBenchmarkAdapter,
    GuessWhoSingleGamePromptBaseline,
    compare_guess_who_baselines,
    run_guess_who_baseline,
)


class BenchmarkBaselineTests(unittest.TestCase):
    def test_generic_weak_agent_is_stateless_reproducible_and_legal(self) -> None:
        decision_input = GuessWhoBenchmarkAdapter("Ada").decision_input()
        agent = GenericWeakRandomAgent(seed=19)
        first = agent.choose_action(decision_input)
        repeated = agent.choose_action(decision_input)
        changed_observation = replace(
            decision_input,
            observation={"ignoredByGenericWeakAgent": True},
        )
        changed_episode_id = replace(decision_input, episode_id="unrelated-episode")
        self.assertEqual(first, repeated)
        self.assertEqual(first, agent.choose_action(changed_observation))
        self.assertEqual(first, agent.choose_action(changed_episode_id))
        self.assertIn(
            first.action_id,
            {action.action_id for action in decision_input.legal_actions},
        )
        self.assertIsNone(first.belief)

    def test_single_game_prompt_baseline_uses_public_state_and_emits_belief(self) -> None:
        decision_input = GuessWhoBenchmarkAdapter("Ada").decision_input()
        self.assertNotIn("Ada", decision_input.episode_id)
        decision = GuessWhoSingleGamePromptBaseline().choose_action(decision_input)
        self.assertIn(
            decision.action_id,
            {action.action_id for action in decision_input.legal_actions},
        )
        belief = decision.belief
        self.assertIsNotNone(belief)
        assert belief is not None
        self.assertAlmostEqual(sum(belief.probabilities.values()), 1.0)

    def test_trace_preserves_agent_condition_without_mislabeling_it_as_llm(self) -> None:
        trace = run_guess_who_baseline(
            "Ada",
            GuessWhoSingleGamePromptBaseline(),
            agent_id="single-game-prompted-heuristic",
            metadata=SINGLE_GAME_PROMPT_METADATA,
        )
        payload = json.loads(trace.to_json())
        self.assertEqual(
            payload["agentMetadata"]["condition"],
            "single_game_prompted_heuristic_proxy",
        )
        self.assertFalse(payload["agentMetadata"]["isLlm"])
        self.assertEqual(
            payload["agentMetadata"]["claimLevel"], "strong_heuristic"
        )

    def test_paired_suite_separates_game_specific_prompt_from_generic_weak(self) -> None:
        report = compare_guess_who_baselines(weak_seeds=range(20))
        self.assertEqual(report.oracle.episodes, 24)
        self.assertEqual(report.single_game_prompted.episodes, 24)
        self.assertEqual(report.generic_weak.episodes, 480)
        self.assertEqual(report.single_game_prompted.solved_rate, 1.0)
        self.assertEqual(report.generic_weak.solved_rate, 1.0)
        self.assertEqual(report.single_game_prompted.optimal_policy_agreement, 1.0)
        self.assertAlmostEqual(report.single_game_prompted.mean_action_regret, 0.0)
        self.assertGreater(report.prompted_turn_gain, 0.1)
        self.assertGreater(report.prompted_agreement_gain, 0.25)
        self.assertGreater(report.prompted_regret_reduction, 0.04)
        self.assertEqual(report.single_game_prompted.belief_output_rate, 1.0)
        self.assertEqual(report.generic_weak.belief_output_rate, 0.0)

    def test_generic_metadata_declares_no_game_specific_knowledge(self) -> None:
        self.assertEqual(GENERIC_WEAK_METADATA["condition"], "generic_weak")
        self.assertFalse(GENERIC_WEAK_METADATA["usesGameSpecificKnowledge"])
        self.assertFalse(GENERIC_WEAK_METADATA["isLlm"])


if __name__ == "__main__":
    unittest.main()
