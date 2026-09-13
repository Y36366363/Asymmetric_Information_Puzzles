# Independent sequence-form certification (2026-09-13)

## Outcome

AIP now has an independent certification layer for small finite two-player
zero-sum perfect-recall games. It is deliberately separate from trainer regrets.
The `EquilibriumEvaluator` contract exposes `expected_value`, `best_response`,
`nash_conv`, `exploitability`, and per-information-set `action_values`. Its common
output, `IndependentEvaluationReport`, validates finite metrics, the NashConv and
exploitability identities, action-value coverage, threshold status, and failures.
Each report hashes the normalized behavioral profile; exporters and promotion
gates reject a valid report attached to a different policy.

The action-value convention in this first version is the player's root expected
utility after forcing one action at the named information set while holding the
rest of the profile fixed. Best response remains a complete simultaneous choice
over all of that player's information sets; action values are diagnostics and do
not replace the best-response traversal.

## Kuhn sequence form

Canonical Kuhn is represented with 13 sequences and 7 realization-flow
constraints per player. Terminal utilities are multiplied by the six ordered
deal probabilities and stored in a 13 by 13 sparse sequence payoff matrix. The
zero-sum sequence-form primal and dual are solved separately:

- player 0 maximizes the guaranteed value subject to realization-flow equality,
  nonnegative realization weights, and the player-1 sequence inequalities;
- player 1 solves the transposed, negated game under its own flow constraints;
- realization plans are converted to behavioral policies by dividing each action
  sequence by its parent sequence reach.

The result is:

| Check | Result |
| --- | ---: |
| P0 game value | -0.0555555555555560 |
| primal-dual gap | 5.27e-16 |
| maximum flow residual | 3.33e-16 |
| exhaustive-BR NashConv | 0 |
| exhaustive-BR exploitability | 0 |

The analytic equilibrium, the existing exhaustive 64-response-per-seat oracle,
and the sequence-form LP therefore agree on value and zero exploitability. An
undertrained ten-iteration CFR policy still fails the independent epsilon gate.

## Second adapter: one-die Liar's Dice

The frozen one-die stepwise-bidding policy now implements the same evaluator
contract. Expected value traverses the complete chance/action tree; best response
conditions on the responding player's private die and recursively optimizes every
information set; action values cover all 348 required information sets. Its
independent exploitability remains `0.0023538636`, below the unchanged `0.01`
runtime threshold.

The live epsilon-GTO mode now recomputes an `IndependentEvaluationReport` when the
artifact is loaded and requires a promotion decision of at least
`independently_checked`. A trainer-owned regret number or the legacy certification
flag alone cannot activate the label.

## Promotion ladder

Promotion is contiguous and fail-closed:

1. `candidate`: incomplete or newly produced policy;
2. `labeled`: complete algorithm/game artifact, but no passed independent report;
3. `independently_checked`: independent evaluator passed; epsilon-GTO runtime is
   permitted within the exact declared game scope;
4. `verified`: a second method agrees within a declared tolerance;
5. `frozen`: verification is reproducible and the exact artifact is frozen.

For Kuhn, analytic, exhaustive BR, and sequence-form evidence can reach `frozen`.
The one-die runtime remains conservatively `independently_checked`: it has an
independent tree evaluator, but this milestone does not invent a second solver or
claim cross-method verification.

## LP dependency decision

No dependency was added. The project includes a small two-phase simplex solver
for certification-scale LPs, including infeasible, unbounded, dimension, and
non-finite input failures. This keeps the existing zero-runtime-dependency MIT
installation unchanged.

Alternatives considered:

- SciPy `optimize.linprog`/HiGHS: BSD-3-Clause and technically suitable, but adds
  a large compiled wheel and platform installation cost. It is the preferred
  optional backend if AIP later solves Leduc-scale sequence forms.
- CVXOPT: GPLv3 and compiled native dependencies. It was not selected because its
  distribution boundary is less compatible with AIP's MIT application goal.
- exact rational vertex enumeration: already useful for tiny normal-form matrices,
  but combinatorial active-set growth makes it a poor general sequence-form LP
  backend.

The local simplex is not advertised as a high-performance or numerically certified
large-game optimizer. Larger games must add residual, duality, scaling, and an
independent backend comparison before promotion.
