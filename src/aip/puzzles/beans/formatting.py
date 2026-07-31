from __future__ import annotations

from aip.puzzles.beans.models import BeanSolution


def format_solution(solution: BeanSolution) -> str:
    rules = solution.rules
    lines = [
        f"Bean puzzle: {rules.player_count} players, pile in "
        f"[{solution.minimum_beans}, {solution.maximum_beans}]",
        f"Each turn takes {rules.min_take}..{rules.max_take}; the last taker loses.",
        "Risk model: all other players may coordinate against player 1.",
        "",
        "Exact-count safe actions:",
    ]
    for analysis in solution.analyses:
        actions = ", ".join(map(str, analysis.safe_actions)) or "none"
        lines.append(f"  {analysis.beans} beans: {actions}")
    lines.append("\nInterval action coverage:")
    for risk in solution.action_risks:
        unsafe = ", ".join(map(str, risk.unsafe_counts)) or "none"
        lines.append(f"  take {risk.action}: unsafe at [{unsafe}]")
    if solution.robust_actions:
        lines.append(
            "\nZero-worst-case-risk actions: " + ", ".join(map(str, solution.robust_actions))
        )
    else:
        lines.append("\nNo action is safe for every pile size in this interval.")
    lines.append(f"Recommended extreme-risk action: take {solution.recommended_action}.")
    return "\n".join(lines)
