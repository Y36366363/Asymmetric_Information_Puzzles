# Completion ceiling and equilibrium metrics — 2026-09-04

## Smoke-test status

The original two-model/two-repeat Mastermind smoke is complete as an experiment:
all eight registered episode slots were attempted and preserved. It did not pass
its operational reliability gate because five responses consumed the exact
2,048-token ceiling without visible JSON and two episodes failed.

Today's preregistered diagnostic changed one model-call variable only:
`max_output_tokens` increased from 2,048 to 8,192. Models, secret, generic and
cross-game prompts, frozen memory, `low` reasoning, and the two-attempt rule did
not change. The official Responses API reference states that this limit includes
both visible and reasoning tokens, and exposes `incomplete_details.reason` when a
response is incomplete. AIP now records response status and that reason directly
instead of inferring every empty output from token counts.

Diagnostic result:

| Model | Condition | Episode | Provider calls | Retry / parse / validation |
| --- | --- | ---: | ---: | --- |
| GPT-5.6 Luna | Generic | Solved in 6 | 6 | 0 / 0 / 0 |
| GPT-5.6 Luna | Cross-game | Solved in 7 | 7 | 0 / 0 / 0 |
| GPT-5.6 Terra | Generic | Solved in 6 | 6 | 0 / 0 / 0 |
| GPT-5.6 Terra | Cross-game | Solved in 7 | 7 | 0 / 0 / 0 |

All four completed, with zero max-output incomplete responses. The diagnostic
used 26 calls and 39,676 API-reported tokens. This supports adopting 8,192 as the
next experiment's operational ceiling. It does not repair or overwrite the v1
smoke and does not add another repeat to its statistical sample.

Official references:

- [Responses `max_output_tokens` and incomplete details](https://developers.openai.com/api/reference/cli/resources/responses/methods/create)
- [GPT-5.6 Luna model capabilities](https://developers.openai.com/api/docs/models/gpt-5.6-luna)
- [GPT-5.6 Terra model capabilities](https://developers.openai.com/api/docs/models/gpt-5.6-terra)

## Kuhn Poker equilibrium metrics

The benchmark now accepts a complete Kuhn behavior policy and returns exact
model-scoped quantities:

- candidate regret in each seat against the declared equilibrium opponent;
- opponent best-response exploitability when the candidate occupies either seat;
- mean Bernoulli total-variation distance across the 12 information-set actions;
- actions assigned probability outside a reference pure-action support.

The equilibrium policy scores zero on every metric. The legacy policy is a useful
counterexample: it has zero value regret against this selected equilibrium member,
but exact exploitability `1/9` when used in the first seat and mean information-set
TV distance `1/36`. A policy can tie one equilibrium opponent yet remain vulnerable
to a best response; regret and exploitability are therefore reported separately.

## Goofspiel equilibrium metrics

For the declared four-card shuffled-prize game, exact recursion evaluates each
named row policy against both the equilibrium continuation and an adaptive best
response at every reachable state. It also reports mean root-action TV distance.

| Policy | Regret vs equilibrium | Exploitability | Root TV distance |
| --- | ---: | ---: | ---: |
| Equilibrium | 0 | 0 | 0 |
| Random | ≈1.6546 | 2.5 | ≈0.5367 |
| Match prize | 0 | 2 | ≈0.3375 |
| Always high | ≈2.0392 | ≈5.0417 | ≈0.6957 |

Again, match-prize demonstrates the distinction: its expected value against the
chosen equilibrium happens to equal the game value, but an exact best response
can exploit it by two points.

These are exact results inside AIP's small finite rulesets, not proofs about every
Kuhn or Goofspiel variant. No LLM policy was evaluated on these two environments
today.

## Next ordered milestone

The Mastermind completion boundary is now reliable enough for later repeated
experiments, and Kuhn/Goofspiel have the required equilibrium scoring primitives.
The next single slice is Liar's Dice opponent-shift robustness: define and freeze
reference, naive, adaptive, and adversarial opponent families, keep the evaluated
agent fixed across them, and score exact belief calibration separately from its
heuristic-backed action quality. The formal prompt × memory × cross-game ablation
remains after that slice.

Machine-readable artifacts:

- [`results/mastermind_ceiling_diagnostic_2026-09-04/`](results/mastermind_ceiling_diagnostic_2026-09-04/)
- [`results/equilibrium_metrics_2026-09-04.json`](results/equilibrium_metrics_2026-09-04.json)
