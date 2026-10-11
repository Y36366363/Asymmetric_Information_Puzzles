# Average-strategy estimator validation — 2026-10-11

## Decision

The new reach-weighted average-strategy estimator passed Kuhn Poker and passed
the one-die Liar's Dice independent exploitability threshold, but it failed the
preregistered one-die observation-coverage gate. Therefore the small-game
validation fails overall. No five-die experiment was preregistered or trained,
and the 2026-10-10 budget remains closed.

## Mechanism change

The shared CFR node now reports three separate quantities:

1. traversal visits, used for regret-update diagnostics;
2. average-strategy observation count;
3. cumulative average-strategy observation weight.

Existing full-tree and external-sampling algorithms retain their prior update
semantics. The new algorithm has its own ID,
`reach_weighted_external_sampling_mccfr_v1`. It observes the updating player's
strategy and weights the contribution by that player's own reach probability.
Its regret updates, sampling stream and visit trace are identical to the legacy
external-sampling run at the same seed.

## Frozen exact-game results

| Game | Iterations | Weighted observation coverage | New exploitability | Legacy exploitability | Gate |
|---|---:|---:|---:|---:|---|
| Canonical Kuhn | 50,000 | 12/12 = 100% | 0.002889 | 0.002816 | pass |
| One-die stepwise Liar's Dice | 100,000 | 189/348 = 54.31% | 0.001414 | 0.000690 | fail |

Both games reproduced exactly under the fixed seed. Both candidate policies
were complete and normalized, regret diagnostics and information-set visits
matched the legacy traversal, and both passed an independent exploitability
ceiling of 0.01. The candidate was also within the preregistered 0.002 allowed
difference from the legacy estimator.

The failure is specifically coverage, not exploitability. In one-die Liar's
Dice, 293 information sets were observed at least once, but only 189 received
positive own-reach weight. Thus 104 nodes were traversed after an earlier
action had already assigned zero behavioral reach, while 55 initialized nodes
were never observed at all. Treating all 293 visits as effective average-policy
evidence would hide this distinction.

## Interpretation

Own-reach weighting is mathematically coherent and produces a strong small-game
policy, but it does not by itself solve sparse off-path coverage. Explicit node
initialization prevents missing keys; it does not create average-strategy
evidence. The exact independent oracle can still pass because zero-reach actions
may make many downstream choices strategically irrelevant under the fixed
profile, but the separately frozen coverage endpoint must still be respected.

## Next valid step

Do not create the five-die preregistration yet. A separate small-game experiment
should define a coverage-aware fallback before seeing its results. A reasonable
candidate is to use the reach-weighted average whenever cumulative weight is
positive and use the node's current regret-matching strategy only when the
weight is zero. That rule needs:

- a separate algorithm and estimator ID;
- exact tests showing that initialization alone still counts as zero evidence;
- Kuhn and one-die independent best-response gates;
- explicit reporting of how many policy entries use the fallback;
- comparison with both legacy and reach-weighted policies;
- a frozen rule for when fallback use is acceptable.

Only if that new small-game protocol passes should it create a separate
five-die preregistration. It must not reopen or extend the prior five-die run.
