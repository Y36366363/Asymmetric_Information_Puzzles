# Composable regret-minimization trainer (2026-09-13)

## Result

AIP now has one tabular regret-minimization trainer assembled from five explicit
boundaries: an `ExtensiveFormGame` adapter, a `TraversalPolicy`, a
`RegretUpdatePolicy`, an `AverageStrategyPolicy`, and a versioned artifact
exporter. `CFRTrainer`, `CFRPlusTrainer`, `DCFRTrainer`, and
`ExternalSamplingCFRTrainer` are compatibility facades over those compositions;
they are not independent copies of the game traversal and node store.

The supported registry is:

| Algorithm ID | Traversal | Regret update | Average strategy | Seed |
| --- | --- | --- | --- | --- |
| `vanilla_cfr` | alternating batched full tree | cumulative regret | uniform iteration weighting | `null` (deterministic) |
| `cfr_plus` | alternating batched full tree | RM+, clip cumulative regret at zero after each player traversal | linear iteration weighting | `null` |
| `dcfr` | alternating batched full tree | sign-dependent discount, default alpha=1.5 and beta=0 | gamma-discounted, default gamma=2 | `null` |
| `external_sampling_mccfr` | sample chance and opponent actions | cumulative regret | standard external-sampling average | required integer |

The full-tree variants still commit only after a player's complete traversal.
Consequently CFR+ clipping and DCFR discounting cannot make a later chance
outcome observe a partially updated strategy.

## Independent evaluation and artifacts

Checkpoints require an evaluator supplied by the game module. For Kuhn this is
the existing exhaustive pure-strategy best-response traversal. A callback that
returns only training regret, omits one of the five common metrics, or returns a
non-finite/negative metric is rejected. Training regret remains a diagnostic and
is explicitly labelled `not_an_exploitability_measure` in exported artifacts.

Every generic artifact records the algorithm ID, all parameters, traversal,
update schedule, averaging rule, seed, convergence trace, independent final
evaluation, information-set visits, and policy. The one-die Liar's Dice writer
also records the new algorithm specification while retaining backward reading
compatibility with its frozen version-1 policy.

## Canonical Kuhn comparison

All values below use 10,000 iterations and exact best responses. The external
reference is a frozen numeric snapshot from PokerCapabilityLab commit
`07e293db214e7c56ffe299833269f21e806dfa33`; AIP neither imports its Python
implementation nor links its AGPL backend.

| Algorithm | AIP value to P0 | AIP exploitability | PokerCapabilityLab exploitability |
| --- | ---: | ---: | ---: |
| Vanilla CFR | -0.0555635183 | 0.0001133245 | 0.0001133245 |
| CFR+ | -0.0555555555 | 0.0000096232 | 0.0000096328 |
| DCFR (1.5, 0, 2) | -0.0555555549 | 0.0000123470 | 0.0000123471 |

The small CFR+ difference comes from AIP's existing Kuhn evaluator translating
probabilities to bounded-denominator exact fractions before exhaustive response
enumeration. It is below 1e-8 at the final checkpoint. At checkpoints 10, 100,
1,000, and 10,000, every exploitability differs from the frozen reference by
less than 5e-8. Concrete frequencies remain secondary because Kuhn has multiple
Nash equilibria.

PokerCapabilityLab's Leduc release values are recorded as transfer targets:
Vanilla at 2,000 iterations has exploitability 0.00659982, CFR+ at 1,000 has
0.000266938, and DCFR at 1,000 has 0.000176280, with 144 information sets per
player. These are not AIP results. AIP must first implement an independent Leduc
adapter, audit its full state tree and information sets, and build its own best
response before claiming parity.

## Solver routing

Later chance is no longer treated as proof that MCCFR is required. The router
now considers an estimated full-tree node count and an explicit node budget:

- if a later-chance full tree fits, full-tree DCFR is primary and external
  sampling is the cross-check;
- if the estimate exceeds the budget, external sampling is primary;
- if either estimate or budget is absent, the router stays conservative and
  reports that the resource case has not been established;
- exact matrix and small sequence-form routes continue to take precedence.

This is a routing decision, not certification. Runtime, memory, chance/action
invariants, independent best response, convergence, and game-specific promotion
gates still have to pass. The new trainer does not extend the two-player
zero/constant-sum, finite, perfect-recall certification scope.
