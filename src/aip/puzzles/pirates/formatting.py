from __future__ import annotations

from aip.puzzles.pirates.models import Solution


def format_solution(solution: Solution) -> str:
    lines = [
        f"Pirate puzzle: {len(solution.pirate_names)} pirates, {solution.total_gold} gold",
        "Order: " + " > ".join(solution.pirate_names) + " (most to least senior)",
    ]
    for round_ in solution.rounds:
        active_names = solution.pirate_names[-round_.pirate_count :]
        distribution = ", ".join(
            f"{name}={'dead' if not alive else gold}"
            for name, gold, alive in zip(active_names, round_.allocation, round_.alive)
        )
        lines.extend(
            [
                "",
                f"[{round_.pirate_count} pirate(s)] proposer {round_.proposer}",
                f"  Outcome: {distribution}",
                f"  Vote: {round_.yes_votes}/{round_.pirate_count} yes; needs {round_.votes_required} -> "
                + ("PASS" if round_.passed else "REJECT"),
            ]
        )
        for vote in round_.votes:
            lines.append(
                f"    {vote.pirate}: {'YES' if vote.supports else 'NO'} — {vote.reason}"
            )
        lines.append(f"  Logic: {round_.explanation}")
    return "\n".join(lines)

