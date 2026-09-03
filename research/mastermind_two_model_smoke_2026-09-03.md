# Mastermind two-model, two-repeat smoke test — 2026-09-03

## Outcome

The frozen held-out smoke panel ran all eight planned episode slots. Six completed
and solved the hidden code; two failed after their bounded retries. The reliability
gate therefore **did not pass**. These results are exploratory completion-behavior
evidence, not a transfer-gain estimate and not a model ranking.

## Frozen before the first API call

The machine-readable plan was written before execution with SHA-256
`0c989df2e45d2f21c156d35d36997de18b225763f47acea5a50ebab9b619fa6f`.

| Field | Frozen value |
| --- | --- |
| Models | `gpt-5.6-luna`, `gpt-5.6-terra` |
| Conditions | generic, frozen cross-game experience |
| Repeats | 2 independent completions per model/condition |
| Held-out secret | one shared hidden code across all cells |
| Reasoning effort | `low` |
| Retries | at most 2 provider attempts per decision |
| Per-request output ceiling | 2,048 tokens |
| Experiment call ceiling | 96 provider requests |
| Reported-token stop threshold | 250,000 tokens |

Both conditions received the same rules, observations, legal actions, history,
secret, and model identity. The cross-game condition added only the previously
frozen generic principles; the leakage audit found no Mastermind names, examples,
target action recipes, or target traces. The official model pages document
Responses API and structured-output support for both
[`gpt-5.6-luna`](https://developers.openai.com/api/docs/models/gpt-5.6-luna)
and [`gpt-5.6-terra`](https://developers.openai.com/api/docs/models/gpt-5.6-terra).
The provider currently exposes these names as aliases rather than dated snapshot
IDs, so every trial records both requested and resolved model; all completed
trials resolved to the requested name.

## Results

| Trial | Status | Attempts to solve | Provider attempts | Retry/parse/validation failures |
| --- | --- | ---: | ---: | --- |
| Luna, repeat 0, generic | Failed | — | 6 | 1 / 0 / 2 |
| Luna, repeat 0, cross-game | Solved | 7 | 8 | 1 / 1 / 0 |
| Terra, repeat 0, generic | Solved | 6 | 6 | 0 / 0 / 0 |
| Terra, repeat 0, cross-game | Solved | 6 | 6 | 0 / 0 / 0 |
| Luna, repeat 1, generic | Solved | 7 | 7 | 0 / 0 / 0 |
| Luna, repeat 1, cross-game | Solved | 6 | 7 | 1 / 1 / 0 |
| Terra, repeat 1, generic | Failed | — | 5 | 1 / 2 / 0 |
| Terra, repeat 1, cross-game | Solved | 6 | 7 | 1 / 1 / 0 |

Condition-level diagnostics, computed only over completed episodes where noted:

| Diagnostic | Generic | Cross-game |
| --- | ---: | ---: |
| Episode completion | 2/4 (50%) | 4/4 (100%) |
| Solved among completed | 100% | 100% |
| Mean guesses among completed | 6.50 | 6.25 |
| Mean heuristic-reference agreement | 0.4643 | 0.4405 |
| Mean belief-output rate | 0.4524 | 0.4405 |
| Mean of episode belief Brier scores | 0.5797 | 0.5704 |

The cross-game completion-rate difference is directionally interesting but cannot
be called transfer gain: there are only two repeats, failed episodes create
selection bias in the action/calibration averages, and one operational interruption
occurred. Among successful episodes, cross-game advice did not improve the mean
bounded-heuristic agreement. The action reference remains `strong_heuristic`, not
proved optimality.

## Reliability finding and recovery

Five parse failures had zero output characters while consuming exactly the full
2,048 output-token allowance. This strongly suggests the reasoning process reached
the output ceiling before emitting the structured JSON. It is an inference from
the trace, not a provider error classification. The next diagnostic should keep
models, prompts, memory, secret, and retries fixed while testing a separately
registered larger output ceiling.

The first execution was stopped after its first failed trial because the initial
summary retained failure counts but not individual error messages. Six successful
responses (7,987 reported tokens) had been recorded, and one in-flight request was
conservatively reserved against the call budget with unknown token usage. The
runner was then hardened before resuming:

- each provider request consumes the call budget before network dispatch;
- usage is atomically journaled after dispatch and after each response;
- resume skips every already-recorded trial rather than silently rerunning it;
- subsequent attempt-level outcome, token, latency, hash, and error fields persist.

The final budget ledger contains 53 calls: 52 represented in trial telemetry plus
the one reserved interrupted request. API-reported usage was 80,834 tokens,
excluding the interrupted request whose usage was unavailable locally. The
uncached-price estimate is `$0.3478114`, also excluding that unknown request and
subject to cache/account billing differences.

## Decision

The smoke test successfully exposed a real completion-boundary weakness, so it
served its intended purpose. It did not satisfy the all-episodes-complete gate.
Before Kuhn/Goofspiel model evaluation or the formal ablation, run one small,
separately hashed output-ceiling diagnostic. Do not reuse the failed episodes as
if they were successful observations and do not change the frozen v1 report.

Artifacts are in
[`results/mastermind_model_smoke_2026-09-03/`](results/mastermind_model_smoke_2026-09-03/).
