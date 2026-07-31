from __future__ import annotations

from aip.puzzles.worm.models import WormSolution


def format_solution(solution: WormSolution) -> str:
    sequence = " -> ".join(map(str, solution.checks))
    lines = [
        f"Moving worm: {solution.hole_count} adjacent holes",
        f"Shortest guaranteed sequence: {sequence}",
        f"Capture is guaranteed within {solution.maximum_checks} checks.",
    ]
    for step in solution.steps:
        before = ",".join(map(str, step.information_set.possible_states))
        after = ",".join(map(str, step.possible_after_miss_and_move)) or "none"
        suffix = "CAPTURE" if step.guarantees_capture else f"after a miss + move: {{{after}}}"
        lines.append(
            f"  Step {step.number}: possible {{{before}}}; check {step.checked_hole}; {suffix}"
        )
    lines.append(
        "Parity insight: each forced move flips odd/even parity; the repeated sweep "
        "covers both possible starting parities."
    )
    return "\n".join(lines)
