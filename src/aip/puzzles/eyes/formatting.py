from __future__ import annotations

from aip.puzzles.eyes.models import EyeSolution


def format_solution(solution: EyeSolution) -> str:
    rules = solution.rules
    lines = [
        "Village eye-colour puzzle",
        f"Population: {solution.target_count} {rules.target_color}-eyed, "
        f"{solution.other_count} {rules.other_color}-eyed",
        "Public announcement: "
        + (
            f"at least one person has {rules.target_color} eyes"
            if rules.public_announcement
            else "none"
        ),
    ]
    for day in solution.days:
        possibilities = "/".join(day.possible_own_colors)
        status = "KNOWS" if day.target_group_knows else "does not yet know"
        lines.append(
            f"  Day {day.day}: own colour could be {possibilities} -> {status}; "
            f"{day.public_event}."
        )
    lines.append("Conclusion: " + solution.conclusion)
    return "\n".join(lines)
