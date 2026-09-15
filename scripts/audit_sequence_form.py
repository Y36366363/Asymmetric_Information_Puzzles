"""Reproducible generic sequence-form compilation and independent audit."""
import json
from pathlib import Path

from aip.core import (
    CFRGameProperties, FullTreeBestResponseEvaluator, compile_sequence_form,
    solve_sequence_form, run_independent_evaluation,
)
from aip.puzzles.kuhn_poker import KuhnCFRGame
from aip.puzzles.e_card import ECardTimingCFRGame
from aip.puzzles.love_letter import LoveLetterCFRGame


def main():
    games = {}
    for name, game, expected in (
        ('kuhn', KuhnCFRGame(), -1/18),
        ('e_card_single_round', ECardTimingCFRGame(), -0.2),
        ('love_letter_four_card_subgame', LoveLetterCFRGame.late_round_subgame(), 1/6),
    ):
        form = compile_sequence_form(
            game, game_properties=CFRGameProperties(2, True, True, True))
        solution = solve_sequence_form(form)
        report = run_independent_evaluation(
            FullTreeBestResponseEvaluator(game, evaluator_id=name+'_independent_tree'),
            solution.policy, maximum_exploitability=1e-12)
        games[name] = {
            'representation': form.to_artifact(),
            'value': solution.value_to_player_0,
            'expected_reference_value': expected,
            'primal_dual_gap': solution.primal_dual_gap,
            'maximum_flow_residual': solution.maximum_flow_residual,
            'independent_report': report.to_artifact(),
            'passed': report.passed and abs(solution.value_to_player_0-expected) < 1e-12,
        }
    artifact = {
        'schema_version': 'generic_sequence_form_audit_v1',
        'date': '2026-09-15', 'new_dependencies': [],
        'games': games, 'passed': all(g['passed'] for g in games.values()),
        'scope': 'finite_two_player_zero_sum_perfect_recall_small_audited_trees',
        'runtime_changes': False,
    }
    if not artifact['passed']:
        raise SystemExit('sequence-form audit failed')
    path = Path(__file__).resolve().parents[1] / 'research/results/sequence_form_audit_2026-09-15.json'
    path.write_text(json.dumps(artifact, indent=2, sort_keys=True)+'\n')
    print(path)


if __name__ == '__main__':
    main()
