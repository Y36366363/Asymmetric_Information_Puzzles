# Independently scored value decomposition — 2026-09-25

## Decision

AIP now has a game-independent intermediate evaluation contract:

`posterior → immediate action value → continuation action value → total value → final action`

The interface is implemented and independently verified on the frozen 30-state
one-die Liar's Dice panel and the frozen 30-state four-card Goofspiel panel. It
does not change any runtime policy or certification label, and no model was
evaluated in this update.

The earlier shorthand `challenge value → raise continuation value` remains the
Liar-specific interpretation. The generalized names are necessary for
Goofspiel, where every legal action is a simultaneous secret bid rather than a
challenge or raise.

## Shared contract

Every candidate decomposition contains:

1. a named posterior target and a normalized distribution;
2. an immediate utility estimate for every legal action;
3. a continuation utility estimate for every legal action;
4. a reported total for every action;
5. one final chosen action.

The scorer does not trust the final action or the reported totals. Against an
independent exact reference, it reports:

- posterior Brier score;
- immediate-value mean absolute error;
- continuation-value mean absolute error;
- total-value mean absolute error;
- maximum internal residual in `total = immediate + continuation`;
- final action regret under reference values;
- exact optimal-action agreement;
- whether the chosen action is consistent with the candidate's own totals;
- per-action errors for localization.

A strict structured-output schema and parser reject missing or extra fields,
duplicate state labels, duplicate actions, mismatched action sets, non-finite
values, unnormalized probabilities, and illegal final actions. Incorrect but
well-formed numerical estimates remain scoreable rather than being discarded.

## One-die Liar's Dice mapping

The posterior target is the opponent's private die, conditional on public bids
and equilibrium opponent reach. For each legal action:

- `challenge` immediate value is the posterior expectation of the terminal
  challenge payoff;
- `challenge` continuation value is zero;
- a legal raise has zero immediate payoff;
- raise continuation value is its independently traversed expected future
  utility against the exact equilibrium opponent;
- total action value is the sum, and the final action maximizes that total.

Across all 30 profile-invariant states:

- maximum additivity residual: **0**;
- maximum reconstruction error against the independent action-value oracle:
  **0**;
- all reference self-scores passed within the declared numerical tolerance.

This decomposition directly exposes the failure seen on 2026-09-24. A future
candidate can now be diagnosed as having the wrong die posterior, wrong
challenge payoff, wrong raise continuation, an arithmetic inconsistency, or a
final comparison error.

## Four-card Goofspiel mapping

The posterior target is the opponent's current hidden bid under the exact
zero-sum matrix equilibrium for the public state. For each player bid:

- immediate value is expected current-prize score difference across the
  opponent-bid distribution;
- continuation value is expected exact backward-induction value after both bid
  cards and the current prize are removed;
- total value is their sum;
- the final action maximizes total conditional value.

This uses the same generic fields as Liar's Dice while preserving Goofspiel's
different simultaneous-move structure.

Across the frozen 30-state Goofspiel panel:

- maximum additivity residual: **4.44e-16**;
- maximum reconstruction error against the exact probe action values:
  **8.88e-16**;
- all reference self-scores passed within `1e-12`.

The residuals are ordinary binary floating-point conversion from exact rational
matrix/backward-induction values. The raw residuals remain in the artifact; they
were not rounded to manufacture an exact zero.

## Negative controls

Permanent tests verify that the scorer distinguishes:

- a shifted posterior with otherwise correct immediate values;
- an incorrect continuation value with correct reported totals;
- a violated addition identity;
- a final action inconsistent with both the reference and the candidate's own
  reported values;
- malformed, duplicate, non-finite, or label-mismatched outputs.

Thus training regret, a candidate's self-reported best action, or a correct final
action cannot substitute for independent intermediate scoring.

## Admission and research scope

Passing this audit proves that the decomposition machinery reconstructs two
existing exact small-game oracles. It does **not** prove that:

- an LLM can reliably generate the intermediate fields;
- the intermediate representation improves cross-game transfer;
- the selected action constitutes a complete equilibrium policy;
- full Love Letter is certified;
- any runtime AI should receive a new ε-GTO label.

The next clean experiment should first run a small structured-output manipulation
check on held-out Liar states. Its primary diagnostic endpoints should be
posterior Brier and raise-continuation MAE, with final regret secondary. Only if
field-level validity and repeatability pass should the identical output schema be
used on the frozen Goofspiel panel. Kuhn Poker can then test whether the same
decomposition works when private cards and betting responses interact.
