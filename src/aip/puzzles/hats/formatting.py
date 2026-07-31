from __future__ import annotations

from aip.puzzles.hats.models import HatSolution


def format_solution(solution: HatSolution) -> str:
    lines = [
        "Hat puzzle: " + " ".join(solution.actual_world),
        f"Public fact: at least one hat is {solution.target_color}",
    ]
    for round_ in solution.rounds:
        lines.append("")
        lines.append(
            f"Round {round_.number}: {round_.possible_world_count} public world(s) remain; "
            f"{round_.public_event}."
        )
        for player, info in enumerate(round_.information_sets, start=1):
            own_colors = sorted({world[player - 1] for world in info.possible_states})
            rendered = "/".join(own_colors)
            status = "KNOWS" if len(own_colors) == 1 else "does not know"
            lines.append(f"  Player {player}: own hat could be {rendered} -> {status}")
    if solution.discovery_round is None:
        lines.append("\nNo discovery occurred within the configured round limit.")
    else:
        lines.append(f"\nFirst discovery occurs in round {solution.discovery_round}.")
    return "\n".join(lines)
