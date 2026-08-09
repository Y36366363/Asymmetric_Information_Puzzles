# Guess Who AI exploration

## Scope

This is a local pre-integration model for a future single-player web game. It
uses 24 distinct character cards and eight public yes/no questions covering
hair colour, glasses, hats, facial hair, and smiles. The hidden identity is
uniformly distributed, every question costs one turn, answers are truthful, and
the final identity guess costs one additional turn.

The exact results are optimal only inside that declared roster and question
bank. A commercial edition with different cards, free-form questions, weighted
characters, or a head-to-head turn race is a different game.

## Policies tested

- `random`: choose any question that still splits the candidates.
- `hair_first`: a readable fixed-order baseline that asks the first useful
  question in the displayed bank.
- `entropy`: minimize the expected size of the next candidate set.
- `minimax`: minimize the largest possible next candidate set.
- `optimal_expected`: dynamic programming over every reachable candidate set
  and unused-question set; globally minimizes expected remaining questions.
- `optimal_worst`: the corresponding dynamic program for worst-case depth.

## Results

With 500 random repetitions per secret, all policies identified every target.
Random splitting averaged 5.892 total turns with an eight-turn worst case, and
the simple hair-first order averaged 5.917 with a seven-turn worst case.
The exact expected-cost solver needs 4.667 information questions on average,
then one final guess: **5.667 total turns on average**. Its worst case is five
information questions plus the guess: **6 total turns**. The optimal opening is
“Does the person wear glasses?”, which creates a balanced 12/12 split.

For this deliberately balanced roster, one-step entropy and minimax select a
tree with the same 5.667 average and six-turn worst case as the exact dynamic
program. This is a useful result rather than a failed optimization: deeper
search proves that the cheaper greedy rule is already optimal from the initial
state. The exact solver should still remain the research oracle and regression
benchmark, because edited rosters or question banks can break that equivalence.

## Web-game direction

The eventual browser version can show all 24 cards, the current information
set, each question's yes/no split, and an AI recommendation. A learning mode can
compare the player's chosen question with the exact oracle. A later race mode
can give the player and AI separate hidden identities, but that requires a new
turn-value objective rather than reusing the identification-only proof above.
