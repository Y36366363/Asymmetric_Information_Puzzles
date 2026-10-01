# Adaptive Guess Who and GTO update — 2026-10-01

## Result

The adversarial Guess Who idea now has a genuine small extensive-form model,
not only a matrix of precommitted question orders. Both players privately choose
a character. In each round they choose a question without seeing the other
player's same-round choice; the two questions and truthful answers then become
public. A player wins when their remaining identity set first becomes a
singleton, with simultaneous identification scored as a draw.
Identification in this version is deliberately mechanical: a player cannot end
the game early merely because the opponent's equilibrium question choice makes
one secret more likely. Adding explicit belief-based guesses would be a new
action model and needs its own information-set and best-response audit.

This representation makes the strategic boundary explicit. Sequential nodes
are used internally to encode simultaneous decisions, but player 1's information
set omits player 0's pending choice. Each information set includes the player's
own secret, the complete public transcript, and that player's remembered action
history. The independent structural audit therefore checks both action
consistency and perfect recall rather than assuming them.

## Three-character exact certificate

The audited instance uses Ada, Hugo and Nico with the three corresponding hair
questions. Its complete tree contains 337 histories, 189 terminal histories,
44 information sets and maximum depth six. Automatic sequence-form compilation
produces 49 realization sequences per player. The dependency-free LP reports a
value within `6.1e-17` of zero, a primal-dual gap below `1.3e-16`, and an
independent full-tree best-response exploitability below `1.7e-16`.

The exact policy selects each secret with probability 1/3. This symmetry is not
the main certificate: the gate is the independent best response over all 44
information sets. A ten-iteration Vanilla CFR negative control has
exploitability about 0.08263 and is rejected.

Vanilla CFR, CFR+ and default DCFR were retained only as cross-method checks.
Their independently measured exploitability at 10,000 iterations is:

| Algorithm | Exploitability at 100 | at 1,000 | at 10,000 |
|---|---:|---:|---:|
| Vanilla CFR | 0.0103459 | 0.00155130 | 0.000180587 |
| CFR+ | 0.00986063 | 0.00106791 | 0.000115612 |
| DCFR (1.5, 0, 2) | 0.00646867 | 0.00127624 | 0.000147785 |

All three converge toward the exact solution and pass the preregistered
cross-check threshold of 0.001 at 10,000 iterations. This particular trace puts
CFR+ ahead at the final budget and DCFR ahead at 100 iterations; it is not
evidence for a universal algorithm ranking. Exact sequence form remains the
router's primary method for this small game.

## Four-character scaling probe

Adding a fourth one-hot hair identity increases the complete tree to 5,525
histories and 682 information sets. The sparse sequence form has 741 sequences
per player and a 741×741 payoff matrix with only 672 nonzero entries. The
optional SciPy/HiGHS backend solves it with value zero, and the separate
full-tree best response again finds exploitability below `1.5e-16`.

This is encouraging for the adapter/compiler/evaluator stack, but it also shows
the scaling boundary: one extra character increases histories by roughly 16×
and information sets by roughly 15×. A direct 24-character expansion is not a
reasonable next experiment. Before scaling, the rules should specify whether
public questions are intentionally allowed to signal one's protected identity,
and whether defensive play remains secret selection only or gains a costed
shield/obscure action. Those choices change the game rather than merely its
size. Neither the three- nor four-character research policy is exposed as a
runtime ε-GTO mode.

## Other game validation

The focused regressions for exact one-die Liar's Dice, its transfer/value
decomposition, four-card Goofspiel, Kuhn regret minimization and the readiness
classifier remain green. Their existing certifications stay scoped to the
declared variants; five-die Liar's Dice remains heuristic.

The full-round Love Letter resumable audit advanced to 1,391,622 histories,
625,463 terminal histories and 200,936 observed information sets, with no
structural failures. Seventy-seven frontier nodes remain and `complete=false`.
The frontier count is not a completion percentage. Full-round Love Letter still
has no candidate equilibrium or independent best-response certificate, so its
runtime ε-GTO label remains forbidden; the certified four-card late-round
subgame remains separate.

The reproducible numerical artifact is
`research/results/adaptive_guess_who_audit_2026-10-01.json`. Run it with the
project's optional sparse-LP environment using `PYTHONPATH=src python3
scripts/audit_adaptive_guess_who.py`.
