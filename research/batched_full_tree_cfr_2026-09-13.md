# Batched full-tree vanilla CFR audit — 2026-09-13

## Scope and result

This milestone changes only AIP's deterministic full-tree vanilla CFR semantics.
It does not import PokerCapabilityLab implementation classes, copy poker-specific
NLHE code, or link its AGPL Rust backend. Cross-project comparison uses a subprocess
and versioned JSON evidence, preserving AIP's MIT boundary. The external-sampling
MCCFR traversal was not changed.

The first cross-project blocking gate now passes: full-tree CFR is invariant to
Kuhn chance-outcome and action enumeration order.

## Original defect

The old `CFRTrainer._traverse` updated a node's regrets immediately when recursion
returned from one history. At a root chance node, deals were visited sequentially.
Several deals share the same information set, so a later deal computed regret
matching from regrets already changed by an earlier deal in the *same player update*.
The declared full-tree iteration therefore did not use one fixed strategy profile.

This made an implementation detail—the order of `chance_outcomes()`—part of the
learning dynamics. At 10,000 canonical Kuhn iterations, reversing the six ordered
deals changed one normalized action probability by as much as `0.0114574490772`.

## Batched alternating update

For each iteration, the trainer now performs:

1. create an empty player-0 delta batch;
2. traverse the complete tree using the current fixed regret-matching policy;
3. accumulate all information-set regret, average-strategy, and visit deltas;
4. commit the batch once traversal is complete;
5. repeat the same sequence for player 1, who sees the newly committed player-0
   regrets, preserving the declared alternating update schedule.

Chance and node expectation sums use `math.fsum`. Node strategy arrays are still
stored in adapter action order, while exported policy comparisons normalize by
action identity. No update occurs during the full-tree recursion.

`ChanceSamplingCFRTrainer` reuses the same batch mechanism after selecting its one
root outcome. `ExternalSamplingCFRTrainer` remains a separate sampling algorithm
and retains its prior update semantics.

## Permanent Kuhn regressions

The new tests lock all requested properties:

- forward and reversed chance enumeration produce exactly equal canonical policy;
- forward and reversed action enumeration produce exactly equal canonical policy;
- all 12 expected information sets are present and action distributions normalize;
- the learned value remains within `0.0001` of the exact `-1/18` value;
- the independent best-response gate passes the existing `0.01` ceiling;
- a 100-iteration negative control remains rejected;
- inconsistent action order inside one information set is rejected; and
- invalid chance probabilities are rejected.

## Before and after at 10,000 iterations

| AIP full-tree CFR | Before batching | After batching |
| --- | ---: | ---: |
| Player-0 profile value | -0.055570843053 | -0.055563518262 |
| Exploitability (NashConv / 2) | 0.002136119400 | 0.000113324461 |
| Maximum unilateral deviation gain | 0.002498150141 | 0.000117657682 |
| Forward/reverse-chance maximum policy difference | 0.011457449077 | 0.0 |
| Forward/reverse-action maximum policy difference | not previously gated | 0.0 |

The improvement is a semantic correction, not a relaxed acceptance threshold.

## PokerCapabilityLab comparison

Both projects were run for 10,000 alternating full-tree vanilla CFR iterations on
canonical three-card Kuhn Poker:

| Metric | AIP | PokerCapabilityLab | Absolute difference |
| --- | ---: | ---: | ---: |
| Player-0 profile value | -0.055563518261907 | -0.055563518262058 | 1.51e-13 |
| NashConv | 0.000226648921695 | 0.000226648915728 | 5.97e-12 |
| Exploitability | 0.000113324460847 | 0.000113324457864 | 2.98e-12 |
| Information sets | 12 | 12 | 0 |
| Maximum normalized policy difference | — | — | 6.78e-14 |

Kuhn Poker has multiple Nash equilibria, so frequency equality is not a general
cross-solver requirement. Value and exploitability remain the primary gates. The
near-identical strategies here are useful evidence that the two implementations now
share the same update semantics, not a new universal policy-frequency requirement.

The machine-readable comparison is in
`research/results/cross_project_kuhn_batched_2026-09-13.json`; it can be reproduced
without a production dependency using:

```bash
PYTHONPATH=src python scripts/audit_cross_project_kuhn.py \
  --poker-root /path/to/PokerCapabilityLab
```

## Unified metric vocabulary

Independent CFR reports now expose:

- `player_0_deviation_gain`;
- `player_1_deviation_gain`;
- `nash_conv`, their sum;
- `exploitability`, exactly `nash_conv / 2` for this two-player constant-sum route;
- `maximum_unilateral_deviation_gain`, reported separately.

The maximum unilateral gain is no longer aliased as exploitability. Kuhn, E-Card,
one-die Liar's Dice, and the Love Letter research subgame all feed two seat-specific
gains into this common report. Existing artifact failure evidence remains readable;
newly written evidence uses the unified nested evaluation schema.

## What this does not prove

Passing canonical Kuhn proves the corrected reference trainer and its Kuhn adapter
agree with an exact independent evaluator. It does not prove that every AIP adapter
has correct rules, perfect-recall information sets, tractable coverage, or low
exploitability. Each game still needs its own tree/information audit and independent
best response. Reduced Liar's Dice and Love Letter certificates remain scoped to
their declared reductions, and multiplayer general-sum games remain rejected by the
two-player zero-sum promotion gate.
