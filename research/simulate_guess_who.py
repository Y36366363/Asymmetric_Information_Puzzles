"""Compare local Guess Who question-selection policies before web integration."""

from aip.puzzles.guess_who import GuessWhoSolver


def main() -> None:
    solver = GuessWhoSolver()
    print("strategy             games  solved   mean turns  worst")
    print("-------------------  -----  -------  ----------  -----")
    for summary in solver.compare(random_repeats=500):
        print(
            f"{summary.strategy:19}  {summary.games:5d}  "
            f"{summary.solved_rate:7.1%}  {summary.mean_turns:10.3f}  {summary.worst_turns:5d}"
        )
    print()
    print("Exact optimum within the fixed 24-character roster and eight-question bank:")
    print(f"  expected information questions: {solver.exact_expected_questions(solver.full_candidate_mask, solver.full_question_mask):.3f}")
    print(f"  worst-case information questions: {solver.exact_worst_questions(solver.full_candidate_mask, solver.full_question_mask):.0f}")
    opening = solver.choose_question(
        "optimal_expected", solver.full_candidate_mask, solver.full_question_mask
    )
    print(f"  optimal expected-cost opening: {solver.questions[opening].label}")


if __name__ == "__main__":
    main()
