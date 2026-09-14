# Full-tree independent evaluator compatibility audit — 2026-09-14

## Question

The previous milestone proved that a Kuhn-specific sequence-form LP and two
game-specific best-response implementations could certify policies. Today's
test asks a stricter engineering question: can one independent evaluator accept
materially different `ExtensiveFormGame` adapters without importing trainer
state or weakening any gate?

The tested structures are deliberately different:

1. single-round E-Card: two hidden simultaneous timing commitments, represented
   sequentially but with no chance node;
2. canonical Kuhn Poker: an initial private chance deal followed by public
   betting actions;
3. the four-card Love Letter late-round subgame: chance occurs after play begins
   and new private cards arrive during the game.

## Shared full-tree oracle

`FullTreeBestResponseEvaluator` implements the common evaluator contract:

- `expected_value` traverses the complete profile tree;
- `best_response(player)` chooses one deterministic action per information set
  while integrating over chance and the fixed opponent strategy;
- `nash_conv` is the sum of the two independently calculated deviation gains;
- `exploitability` is `nash_conv / 2`;
- `action_values` reports conditional counterfactual action values under optimal
  continuation for the acting player.

The oracle consumes only the game adapter and behavioral policy. It does not
accept regrets, visit counts, checkpoints, or a trainer object.

Before evaluation, the complete-tree audit checks:

- the tree fits the declared history budget and has no ancestor cycle;
- every non-terminal actor is player 0, player 1, or chance;
- terminal utilities are finite;
- chance outcomes are unique, finite, nonnegative, nonempty, and sum to one;
- legal actions are nonempty and unique;
- all members of an information set expose the same ordered actions;
- every information-set member has the same sequence of that player's earlier
  information sets and own actions, which is an executable perfect-recall test;
- the submitted profile covers exactly the audited information sets and actions,
  with normalized finite probabilities.

Negative controls show that an adapter in which a player forgets its first
action is rejected as `imperfect_recall`, an invalid chance distribution is
rejected, malformed policies fail closed, and a tree exceeding its history
budget cannot receive a partial certificate.

## Cross-game results

| Game | Histories | Chance histories | Information sets | Value to player 0 | Exploitability |
|---|---:|---:|---:|---:|---:|
| E-Card | 31 | 0 | 2 | -0.2 | 0 |
| Kuhn Poker | 55 | 1 | 12 | -0.055555555556 | 1.42e-16 |
| Love Letter four-card subgame | 1,081 | 217 | 60 | 0.166666695583 | 0.000484423 |

### E-Card

The shared tree oracle exactly matches the existing 5×5 matrix solution and its
pure best-response enumeration. The exact single-round policy therefore reaches
`frozen`. This does not relabel the playable repeated session: its deliberate
cross-round adaptation can depart from the equilibrium distribution, so runtime
continues to report `strong_heuristic`, not ε-GTO.

### Kuhn Poker

The shared oracle matches both the Kuhn-specific exhaustive oracle and the
sequence-form LP value. Its tiny nonzero exploitability (`1.42e-16`) is floating-
point residue and is below the unchanged `1e-12` test tolerance. This comparison
is useful because the LP construction and tree traversal have different failure
modes.

### Love Letter

The same evaluator accepts later private chance without treating it as a reason
to skip full-tree validation. For the enumerable four-card subgame it reproduces
the older specialized best-response result: the seeded 20,000-iteration external-
sampling policy has exploitability `0.000484423`, below the existing `0.001`
threshold. Cross-method agreement promotes this scoped artifact to `verified`;
it is not `frozen` because reproducibility and immutable-artifact evidence were
not supplied to that promotion decision.

The complete 16-card round still exceeds the 10,000-history audit budget and is
explicitly uncertified. Passing the subgame cannot promote the full game.

## Compatibility conclusion

The reusable boundary is now stronger than “CFR can call this adapter.” A small
game must pass a structural tree audit, exact policy validation, independent
best responses, and profile-bound promotion. The common evaluator has been
exercised on no-chance, root-chance, and later-private-chance games, including
both exact and sampled candidate policies.

This still does not establish a universal solver. Large trees require sequence-
form sparsity, sampling, abstraction, or a faster backend; multiplayer and
general-sum games remain outside the certification contract. The next useful
scaling milestone is a generic sequence-form compiler from an audited adapter,
with sparse LP export and realization-plan consistency checks, rather than
another regret-minimization variant.

Machine-readable evidence is stored in
`research/results/game_compatibility_audit_2026-09-14.json`.
