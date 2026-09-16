"""Sparse certification evidence and honest full-round resource boundary."""
import json
from pathlib import Path
from time import monotonic

import scipy
from aip.core import (
    CFRGameProperties, FullTreeBestResponseEvaluator, compile_sequence_form,
    solve_sequence_form, run_independent_evaluation,
)
from aip.core.tree_evaluation import audit_small_extensive_form
from aip.puzzles.love_letter import LoveLetterCFRGame


def main():
    game = LoveLetterCFRGame.late_round_subgame()
    form = compile_sequence_form(
        game, game_properties=CFRGameProperties(2, True, True, True), sparse=True)
    sparse = solve_sequence_form(form, backend='scipy_highs')
    dense = solve_sequence_form(compile_sequence_form(
        game, game_properties=CFRGameProperties(2, True, True, True)))
    report = run_independent_evaluation(
        FullTreeBestResponseEvaluator(game, evaluator_id='love_letter_sparse_tree_v1'),
        sparse.policy, maximum_exploitability=1e-12)
    started = monotonic()
    print('Auditing full 16-card round with 1,000,000-history budget', flush=True)
    try:
        audit = audit_small_extensive_form(
            LoveLetterCFRGame(), maximum_histories=1_000_000)
    except OverflowError as error:
        full = {'certified': False, 'status': 'resource_budget_exceeded',
                'reason': str(error), 'history_budget': 1_000_000}
    else:
        full = {'certified': False, 'status': 'structural_audit_only',
                'tree_audit': audit.to_artifact()}
    full['elapsed_seconds'] = monotonic()-started
    artifact = {
        'date': '2026-09-16', 'backend': sparse.backend,
        'scipy_version': scipy.__version__,
        'representation': form.to_artifact(),
        'value': sparse.value_to_player_0,
        'dense_reference_value': dense.value_to_player_0,
        'primal_dual_gap': sparse.primal_dual_gap,
        'maximum_flow_residual': sparse.maximum_flow_residual,
        'independent_report': report.to_artifact(),
        'full_round': full,
        'runtime_epsilon_gto_enabled_for_full_round': False,
        'passed': report.passed and abs(sparse.value_to_player_0-dense.value_to_player_0) < 1e-12,
    }
    path = Path(__file__).resolve().parents[1] / 'research/results/sparse_love_letter_2026-09-16.json'
    path.write_text(json.dumps(artifact, indent=2, sort_keys=True)+'\n')
    print(path, flush=True)
    if not artifact['passed']:
        raise SystemExit('sparse verification failed')


if __name__ == '__main__':
    main()
