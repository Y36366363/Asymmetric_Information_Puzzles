# Goofspiel exact-AI audit — 2026-08-16

## Published ruleset

The browser game uses bid cards 1–4 and prize cards 1–4. Prize order is shuffled;
the current prize is public while later prizes remain hidden. Both players spend
one unused bid simultaneously. The higher bid wins the current prize value and a
tie discards it. Scores are compared after four rounds.

This is a finite two-player zero-sum imperfect-information game. Its public state
is `(player inventory, AI inventory, remaining prizes, current prize)`. There is
no hidden persistent hand: the uncertainty is the opponent's current action and
the order of future prize reveals.

## Exact solution

For every public state, the solver builds the simultaneous-action payoff matrix.
Each cell contains the immediate score difference plus the exact continuation
value averaged over every possible next prize. A rational-arithmetic LP vertex
enumerator then solves both the row player's primal and the column player's dual;
the matching values are an internal optimality check.

The four-card game contains **692 reachable-shaped public policy entries** in the
exported table. The initial value is exactly zero by symmetry. The browser never
re-solves a matrix: it looks up the current state and samples the AI's equilibrium
distribution, so all play remains local and works after a refresh without saved
data.

## Reproducible simulation

Two thousand fixed-seed games against the exact equilibrium AI produced:

| Player policy | Mean score difference | Win rate | Draw rate |
| --- | ---: | ---: | ---: |
| Exact equilibrium | -0.046 | 13.2% | 70.8% |
| Uniform random | -1.644 | 14.0% | 18.7% |
| Match the prize when possible | +0.029 | 20.5% | 63.4% |
| Always spend the highest card | -2.093 | 10.2% | 16.1% |

The small positive finite-sample result for “match prize” is sampling noise, not
evidence that it beats the AI. The AI's exact minimax policy guarantees that no
player policy has a positive expected score difference; more samples converge
toward a non-positive mean. Draw rate is not the optimized objective—the solver
optimizes expected score difference.

Run the audit with:

```bash
PYTHONPATH=src python research/simulate_goofspiel.py
PYTHONPATH=src python research/export_goofspiel_policy.py
```

## Scope and next experiments

“Exact” applies to this four-card shuffled-prize zero-sum ruleset. It does not
claim optimality for larger Goofspiel decks, alternative tie carry-over rules,
multiplayer play, or opponents whose objective is win probability instead of
expected score. Useful later modes include a five-card precomputed policy,
opponent-pattern exploitation with a safe minimax floor, and post-match
exploitability feedback for the player's empirical bidding habits.
