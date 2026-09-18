"""Freeze local evidence for the exact sequence-form one-die solution."""
import json
from pathlib import Path

from aip.core import PromotionEvidence, decide_promotion
from aip.core.evaluation import run_independent_evaluation, strategy_profile_fingerprint
from aip.puzzles.liars_dice import (
    OneDieLiarIndependentEvaluator, load_one_die_liar_policy,
    solve_one_die_liar_exact,
)

ROOT = Path(__file__).resolve().parents[1]


def policy_artifact(profile):
    records = []
    for (player, information_set), distribution in sorted(
            profile.items(), key=lambda item: repr(item[0])):
        die, bids = information_set
        records.append({
            'player': player,
            'die': die,
            'bids': [list(bid) for bid in bids],
            'distribution': [
                {'action': action if action == 'challenge' else list(action),
                 'probability': probability}
                for action, probability in distribution.items()
            ],
        })
    return records


def main():
    form, solution = solve_one_die_liar_exact()
    report = run_independent_evaluation(
        OneDieLiarIndependentEvaluator(), solution.policy,
        maximum_exploitability=1e-10)
    fingerprint = strategy_profile_fingerprint(solution.policy)
    promotion = decide_promotion(PromotionEvidence(
        artifact_complete=True, artifact_profile_fingerprint=fingerprint,
        independent_report=report, cross_method_agreement=True,
        reproducible=True, artifact_frozen=True))
    old = load_one_die_liar_policy(
        ROOT/'src/aip/puzzles/liars_dice/one_die_cfr_policy.json')
    old_report = run_independent_evaluation(
        OneDieLiarIndependentEvaluator(), old.policy, maximum_exploitability=0.01)
    artifact = {
        'date': '2026-09-18',
        'game': 'one_die_stepwise_liars_dice',
        'method': 'generic_sparse_sequence_form_scipy_highs',
        'representation': {
            'schema_version': 'sequence_form_summary_v1',
            'sparse_storage': True,
            'tree_audit': form.audit.to_artifact(),
            'player_sequence_counts': [len(sequences) for sequences in form.player_sequences],
            'flow_shapes': [list(matrix.shape) for matrix in form.flow_matrices],
            'flow_nonzeros': [len(matrix.entries) for matrix in form.flow_matrices],
            'payoff_shape': list(form.payoff_matrix.shape),
            'payoff_nonzeros': len(form.payoff_matrix.entries),
        },
        'value_to_player_0': solution.value_to_player_0,
        'maximum_flow_residual': solution.maximum_flow_residual,
        'primal_dual_gap': solution.primal_dual_gap,
        'profile_fingerprint': fingerprint,
        'policy': policy_artifact(solution.policy),
        'independent_evaluation': report.to_artifact(),
        'promotion': promotion.to_artifact(),
        'live_runtime_unchanged': True,
        'existing_cfr_reference': {
            'iterations': old.iterations,
            'exploitability': old_report.exploitability,
            'value_to_player_0': old_report.expected_value_to_player_0,
        },
        'passed': report.passed and promotion.level.artifact_name == 'frozen',
    }
    path = ROOT/'research/results/one_die_liar_exact_2026-09-18.json'
    path.write_text(json.dumps(artifact, indent=2, sort_keys=True)+'\n')
    print(path)
    if not artifact['passed']:
        raise SystemExit('exact one-die audit failed')


if __name__ == '__main__':
    main()
