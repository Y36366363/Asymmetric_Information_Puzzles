"""Advance the resumable structural audit for five-die stepwise Liar's Dice."""

from __future__ import annotations

import argparse
from datetime import date
from hashlib import sha256
import json
from pathlib import Path

from aip.core.resumable_audit import ResumableTreeAudit
from aip.puzzles.liars_dice import FiveDieStepwiseLiarGame


ROOT = Path(__file__).resolve().parents[1]
RULES = ROOT / "configs/five_die_liar_stepwise_rules_v1.json"
ADAPTER = ROOT / "src/aip/puzzles/liars_dice/five_die_stepwise.py"
CHECKPOINT = ROOT / "research/local_checkpoints/five_die_stepwise_v1.sqlite"
OUTPUT = ROOT / "research/results/five_die_stepwise_progress_2026-10-08.json"
ORIGINAL_CANDIDATE = (
    ROOT / "research/results/five_die_stepwise_candidate_2026-10-08.json"
)
JOINT_STRATIFIED_CANDIDATE = (
    ROOT
    / "research/results/five_die_stepwise_joint_stratification_2026-10-10.json"
)


def revision() -> str:
    digest = sha256()
    for path in (RULES, ADAPTER):
        digest.update(str(path.relative_to(ROOT)).encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--chunks", type=int, default=3)
    parser.add_argument("--histories-per-chunk", type=int, default=10_000)
    args = parser.parse_args()
    if args.chunks <= 0 or args.histories_per_chunk <= 0:
        parser.error("chunk budgets must be positive")
    CHECKPOINT.parent.mkdir(parents=True, exist_ok=True)
    chunks = []
    for _ in range(args.chunks):
        auditor = ResumableTreeAudit(
            FiveDieStepwiseLiarGame(), CHECKPOINT, revision=revision()
        )
        try:
            chunks.append(
                auditor.advance(
                    maximum_histories=args.histories_per_chunk,
                    maximum_seconds=30,
                )
            )
        finally:
            auditor.close()
        print(json.dumps(chunks[-1]), flush=True)
        if chunks[-1]["status"] != "paused":
            break
    candidate_path = (
        JOINT_STRATIFIED_CANDIDATE
        if JOINT_STRATIFIED_CANDIDATE.exists()
        else ORIGINAL_CANDIDATE
    )
    candidate = (
        json.loads(candidate_path.read_text(encoding="utf-8"))
        if candidate_path.exists()
        else None
    )
    if candidate is None:
        candidate_evaluation = None
    elif "checkpoints" in candidate:
        candidate_evaluation = candidate["checkpoints"][-1][
            "independent_evaluation"
        ]
    else:
        candidate_evaluation = candidate["independent_evaluation"]
    artifact = {
        "updated_date": date.today().isoformat(),
        "rules_id": FiveDieStepwiseLiarGame.RULES_ID,
        "revision": revision(),
        "checkpoint_path": str(CHECKPOINT.relative_to(ROOT)),
        "chunks": chunks,
        "candidate_trained": candidate is not None,
        "candidate_path": (
            None if candidate is None else str(candidate_path.relative_to(ROOT))
        ),
        "candidate_exploitability": (
            None if candidate_evaluation is None else candidate_evaluation["exploitability"]
        ),
        "candidate_independent_gate_passed": (
            False
            if candidate_evaluation is None
            else candidate_evaluation["passed"]
        ),
        "independent_evaluation_complete": candidate_evaluation is not None,
        "runtime_epsilon_gto_allowed": False,
    }
    OUTPUT.write_text(
        json.dumps(artifact, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
