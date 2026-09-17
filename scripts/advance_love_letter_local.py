"""Advance persistent full-round audit and export independently checked local policy."""
import argparse
from dataclasses import asdict
from hashlib import sha256
import json
from pathlib import Path

from aip.core import (
    CFRGameProperties, compile_sequence_form, solve_sequence_form,
    run_independent_evaluation, strategy_profile_fingerprint,
)
from aip.core.resumable_audit import ResumableTreeAudit
from aip.puzzles.love_letter import LoveLetterCFRGame, LoveLetterIndependentEvaluator

ROOT = Path(__file__).resolve().parents[1]


def revision():
    digest = sha256()
    for name in ('src/aip/puzzles/love_letter/extensive.py',
                 'src/aip/puzzles/love_letter/solver.py',
                 'src/aip/core/resumable_audit.py'):
        digest.update(name.encode())
        digest.update((ROOT/name).read_bytes())
    return digest.hexdigest()


def portable_policy(profile, report):
    """Browser-ready data only; a subgame certificate cannot target the full round."""
    if not report.passed or report.profile_fingerprint != strategy_profile_fingerprint(profile):
        raise ValueError('portable policy requires a passed, profile-bound independent report')
    # Recheck shape/probabilities and independent BR, never trust caller's pass flag.
    checked = run_independent_evaluation(
        LoveLetterIndependentEvaluator(LoveLetterCFRGame.late_round_subgame()),
        profile, maximum_exploitability=1e-12)
    if not checked.passed:
        raise ValueError('portable policy failed independent recheck')
    records = [dict(player=p, information_set=info,
                    distribution=[dict(action=asdict(a), probability=v)
                                  for a, v in sorted(dist.items(), key=lambda x: repr(x[0]))])
               for (p, info), dist in sorted(profile.items(), key=lambda x: repr(x[0]))]
    return dict(schema_version='love_letter_portable_policy_v1',
                scope='four_card_late_round_subgame_only',
                rules_revision=revision(), profile_fingerprint=checked.profile_fingerprint,
                promotion='independently_checked', maximum_exploitability=1e-12,
                policy=records, independent_evaluation=checked.to_artifact(),
                full_round_runtime_allowed=False)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--chunks', type=int, default=3)
    parser.add_argument('--histories-per-chunk', type=int, default=10_000)
    args = parser.parse_args()
    if args.chunks <= 0 or args.histories_per_chunk <= 0:
        parser.error('budgets must be positive')
    folder = ROOT/'research/local_checkpoints'
    folder.mkdir(exist_ok=True)
    checkpoint = folder/'love_letter_full_round.sqlite'
    progress = []
    for _ in range(args.chunks):
        auditor = ResumableTreeAudit(LoveLetterCFRGame(), checkpoint, revision=revision())
        try:
            progress.append(auditor.advance(maximum_histories=args.histories_per_chunk,
                                            maximum_seconds=15))
        finally:
            auditor.close()
        print(json.dumps(progress[-1]), flush=True)
        if progress[-1]['status'] != 'paused':
            break
    game = LoveLetterCFRGame.late_round_subgame()
    form = compile_sequence_form(game, game_properties=CFRGameProperties(2, True, True, True), sparse=True)
    solution = solve_sequence_form(form, backend='scipy_highs')
    report = run_independent_evaluation(LoveLetterIndependentEvaluator(game),
                                        solution.policy, maximum_exploitability=1e-12)
    results = ROOT/'research/results'
    (results/'love_letter_portable_subgame_2026-09-17.json').write_text(
        json.dumps(portable_policy(solution.policy, report), indent=2, sort_keys=True)+'\n')
    (results/'love_letter_local_progress_2026-09-17.json').write_text(json.dumps(dict(
        checkpoint_path='research/local_checkpoints/love_letter_full_round.sqlite',
        chunks=progress, full_round_certified=False,
        subgame_value=solution.value_to_player_0, subgame_exploitability=report.exploitability,
    ), indent=2, sort_keys=True)+'\n')


if __name__ == '__main__':
    main()
