# Benchmark experiment protocol — 2026-09-01

## What changed

Today adds the experiment layer needed to move from isolated game scores to a
cross-game strategic-intelligence benchmark. It does not claim held-out transfer
or model superiority yet.

The protocol freezes six independent axes for every trial:

- model identity;
- environment, with Mastermind held out from the five training environments;
- random seed;
- independent repeat;
- reference, naive, adaptive, or adversarial opponent shift;
- the full 2×2×2 ablation of game-specific prompt, memory, and cross-game
  experience.

This produces stable trial IDs and prevents a later result from silently changing
seeds, opponent type, prompt condition, or holdout status. A single-game prompt on
Mastermind is explicitly marked as a supervised ceiling and excluded from the
primary transfer comparison.

## Ground-truth gating

Metric eligibility now comes from each environment's declared evidence profile:

| Stratum | Environments | Permitted policy-quality language |
| --- | --- | --- |
| Proved optimal | Guess Who, Worm | exact optimal agreement and computable regret |
| Equilibrium-backed | Kuhn Poker, Goofspiel | equilibrium distribution/support agreement, regret, exploitability |
| Strong heuristic | Liar's Dice, Mastermind | heuristic-reference agreement only; no action regret or exploitability |

Belief calibration remains available wherever hidden-state ground truth is exact,
including Liar's Dice and Mastermind. An unavailable metric is serialized as
`null` or omitted by the environment evaluator, never changed to zero.

## Offline repeated pilot

To validate aggregation without making paid model calls, the exact Guess Who
slice ran four disjoint repeats. Each repeat evaluated all 24 secrets under eight
new weak-baseline seeds (768 randomized episodes total), alongside the exact
oracle and deterministic single-game prompted proxy.

| Paired metric: prompted proxy minus generic weak | Mean | Sample SD across repeats |
| --- | ---: | ---: |
| Turns saved | 0.24479 | 0.01533 |
| Exact-policy agreement gain | 0.30280 | 0.02314 |
| Exact regret reduction | 0.04983 | 0.00296 |

The prompted proxy emitted a belief on every decision and its mean belief Brier
score was `0.65441`. The generic weak control emitted no belief, so its Brier score
is `null`, not zero. Both the exact oracle and prompted proxy happened to achieve
zero regret in this implemented Guess Who ruleset; the proxy retains its
`strong_heuristic` method label because its balanced-split procedure is not itself
the dynamic-programming proof.

This pilot demonstrates seed separation, repeat dispersion, belief missingness,
and exact regret discrimination. It is explicitly **not evidence for held-out
transfer or multi-model comparison**.

## Next single milestone

Implement the Mastermind benchmark adapter with spoiler-safe candidate-set belief
truth and heuristic-reference agreement. Before any cross-game agent is run, add
a leakage test showing that its prompt and memory contain no Mastermind examples,
rules-specific action recipe, or target traces. Only then run a small two-model,
two-repeat held-out smoke panel.

Machine-readable protocol and pilot:
[`results/benchmark_protocol_2026-09-01.json`](results/benchmark_protocol_2026-09-01.json).
