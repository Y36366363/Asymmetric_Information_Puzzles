# Standard-sampling fallback confirmation — 2026-10-13

## Decision

The new `coverage_aware_external_sampling_mccfr_v1` estimator passed the frozen
five-seed confirmation on canonical Kuhn Poker and one-die stepwise Liar's Dice.
This resolves the small-game preregistered experiment, but it does not certify
five-die Liar's Dice and does not enable runtime ε-GTO.

The 2026-10-12 negative result remains valid. Its primary estimator was
own-reach weighted; today's candidate instead preserves the standard
external-sampling average at every observed information set and uses current
regret matching only where cumulative observation weight is zero.

## Experiment design

An exploratory pilot used seeds `2026101301`–`2026101303`; those seeds were
permanently excluded from confirmation. Before running confirmation, five new
seeds, budgets and gates were frozen. The numerical margins were anchored to
the existing `0.01` absolute small-game gate rather than fitted to pilot effect
sizes:

- every seed independently required exploitability ≤ `0.01`;
- paired mean degradation versus legacy could not exceed `0.0005`;
- no individual paired degradation could exceed `0.001`;
- one-die fallback use could not exceed 50%; Kuhn allowed none;
- all policies had to be complete, normalized and independently evaluated;
- regret, visit and observation traces had to equal the paired legacy run.

## Confirmatory results

| Game | Seeds | Candidate mean | Legacy mean | Worst candidate | Mean paired difference | Result |
|---|---:|---:|---:|---:|---:|---|
| Canonical Kuhn | 5 | 0.003060 | 0.003060 | 0.003748 | 0.000000 | pass |
| One-die Liar's Dice | 5 | 0.000652 | 0.000657 | 0.000795 | -0.00000450 | pass |

Kuhn used no fallback, so candidate and legacy policies were identical. In
one-die Liar's Dice, fallback fractions ranged from 33.91% to 39.37%. Candidate
exploitability was slightly lower than its paired legacy value in all five
runs. This is evidence of noninferiority, not a preregistered superiority claim.

Every structural gate passed, including exact fixed-seed reproduction and the
identity of the fallback set with the zero-observation-weight set. Resolved
policy coverage was 100%, while raw observation coverage remains separately
reported and is not inflated by fallback.

## Next boundary

A separate five-die protocol is now frozen at
`configs/five_die_coverage_aware_joint_preregistration_2026-10-13.json`. It
combines the confirmed fallback with the already audited joint-marginal chance
schedule. It is a new run, not an extension of any failed budget. Training has
not started. Even if its candidate gates later pass, runtime promotion still
requires completion of the independent resumable full-tree audit.
