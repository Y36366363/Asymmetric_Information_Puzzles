# CFR framework and one-die Liar's Dice validation — 2026-09-08

## Outcome

The shared CFR boundary is suitable for small, finite, two-player zero-sum games
provided that every adapter declares complete information sets and supplies an
independent exploitability evaluator. The framework now supports both exhaustive
chance traversal and seeded root chance sampling. Policy activation remains a
separate fail-closed step; completing a training run alone never earns a GTO label.

The new Liar's Dice mode passed that boundary and is therefore exposed as
**ε-GTO**, not exact GTO. After the 2026-09-09 stability retest increased the
default budget, measured exploitability is `0.0023538636` under the
standard half-NashConv definition, below the declared `ε = 0.01` ceiling.

## Certified ruleset

This certificate applies only to the following finite variant:

- two players, one fair six-sided die each;
- ones are wild when the bid face is 2–6;
- the opening quantity is one;
- bids follow the ordered ladder `1×1 … 1×6, 2×1 … 2×6`;
- after an opening, the acting player may challenge or advance exactly one step;
- an information set contains the acting player's die and the complete public bid
  history.

The existing five-die mode and arbitrary jump raises are different games. They
remain under the `strong_heuristic` label and inherit none of this certificate.

## Promotion evidence

| Gate | Requirement | Frozen result |
| --- | ---: | ---: |
| Training | at least 20,000 iterations | 20,000 |
| Exact information-set coverage | all declared sets | 348 / 348 |
| Minimum visits per information set | at least 100 | 3,193 |
| Maximum average positive regret | at most 0.03 | 0.01144604 |
| Independent exploitability | at most 0.01 | 0.00235386 |
| Policy distributions | finite, nonnegative, normalized | passed |

Training uses chance-sampled CFR with a fixed seed. Certification does not reuse
the CFR recursion: it enumerates every possible private die of the opponent,
maximizes independently at every information set of the responding player, and
weights the fixed opponent's actions by the frozen policy. This produces exact
best-response values for the declared finite tree.

## Activation and failure behavior

The training script writes certification metadata into the policy artifact only
after `require_passed()` succeeds. The Python runtime reloads the artifact and
reruns the independent certificate before enabling ε-GTO. Missing certification,
duplicate information sets, invalid probabilities, insufficient coverage or
visits, non-finite/negative diagnostics, and excessive regret or exploitability
all prevent activation.

During play, the AI samples the certified second-seat distribution for its private
die and public history. That distribution is deliberately absent from live public
history and is revealed only after the round, so the audit does not leak private
information into the player's decision.

## Reuse boundary

Future finite imperfect-information adapters can reuse the trainer, seeded chance
sampling, policy diagnostics, and promotion report. Each game must still provide
its own rules, perfect-recall information-set representation, complete required-set
enumeration, and genuinely independent best-response traversal. For larger trees,
external-sampling MCCFR or abstraction may replace the trainer, but neither removes
the independent evidence requirement.
