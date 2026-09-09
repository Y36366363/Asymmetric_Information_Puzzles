# Shared CFR framework and promotion gate — 2026-09-07

## Architecture

The common engine lives in `aip.core.cfr`. A game adapter supplies only:

1. initial and terminal state handling;
2. the current player or a chance node;
3. normalized chance outcomes;
4. legal actions and transitions;
5. a stable information-set key;
6. terminal utility for player zero in a two-player zero-sum game.

The shared trainer owns regret matching, counterfactual reach weighting,
reach-weighted average-policy accumulation, action consistency checks, and
diagnostic collection. This boundary keeps card dealing, bidding rules, and
payoffs inside each game while preventing each adapter from reimplementing the
error-prone CFR update equations.

## Uniform promotion gate

A trained policy is not allowed to become a GTO opponent merely because CFR ran.
The default gate requires all of the following:

| Check | Default threshold | Failure reason |
| --- | ---: | --- |
| Training iterations | at least 10,000 | `insufficient_iterations` |
| Information-set coverage | game-specific minimum | `insufficient_information_sets` |
| Required information-set identities | every declared set present | `missing_required_information_sets` |
| Visits per information set | game-specific minimum | `insufficient_information_set_visits` |
| Average positive regret diagnostic | at most 0.01 | `average_positive_regret_above_threshold` |
| Independent best-response exploitability | at most 0.01 | `exploitability_above_threshold` |
| Independent evaluator supplied | required | `independent_exploitability_required` |
| Every action distribution | finite, nonnegative, sums to one | `invalid_policy_distribution` |

Certification now also requires the adapter to explicitly declare a finite,
two-player, zero/constant-sum game with perfect recall. This is an auditable
eligibility assertion, not an automatic proof: tests and review must still confirm
that information-set keys retain every private observation and remembered action.
Exact game adapters additionally reject unexpected information sets and any
mismatch between policy and visit tables.

`CFRGateReport.require_passed()` is the activation boundary. It raises with the
complete failure list, allowing a runtime or artifact builder to fail closed and
making convergence problems reproducible instead of silently falling back.

## Kuhn Poker calibration

`aip.puzzles.kuhn_poker.cfr` is the first adapter. It models all six private-card
deals, four public decision histories, and 12 information sets. Its learned
average strategy is translated into the existing `KuhnPolicy` contract and then
evaluated by the pre-existing exhaustive pure best-response oracle; the CFR
trainer is therefore not grading its own output.

The frozen calibration profile uses 50,000 iterations, requires all 12 information
sets and at least 50,000 visits per information set, and caps both the regret
diagnostic and exploitability at `0.01`. In the deterministic regression run, the
maximum exploitability is approximately `0.00111`. A 100-iteration run fails the
gate and identifies undertraining explicitly.

The live Kuhn AI remains on its exact closed-form policy because replacing an
exact zero-exploitability policy with a numerical approximation would be a
regression. The adapter proves that the shared machinery can rediscover a policy
well inside its configured gate before it is used for games without a formula.

## Adapter sequence

1. One-die Liar's Dice: implemented on 2026-09-08 for the explicitly reduced,
   stepwise-bidding tree. Its frozen policy is promoted as ε-GTO only after an
   independently traversed best response passes the gate.
2. Single-round E-Card: isolate the frozen extensive-form rules from the current
   cross-round adaptive heuristic, then add its own information-set and utility
   adapter.
3. Love Letter: first exhaustively validate legal transitions and hidden-card
   information sets; use external-sampling MCCFR if full traversal is too large.
4. Restricted RPS and Goofspiel should keep dynamic-programming matrix solvers as
   their primary exact method. They can implement the same gate/report interface,
   but forcing CFR onto a smaller exact public-state game would add approximation
   without benefit.
