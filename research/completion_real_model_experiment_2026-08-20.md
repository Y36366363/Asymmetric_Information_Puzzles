# Real-model completion experiment — 2026-08-20

## Question and scope

This is the first paid, completion-backed check that the same real model can run
through AIP's generic and single-game prompt boundaries and produce traces that
separate strategic quality from operational reliability. It is a small contract
experiment, not evidence of cross-game transfer.

The requested and resolved model was `gpt-5.6-luna`, selected as the current
cost-sensitive GPT-5.6 option described in the official
[model catalogue](https://developers.openai.com/api/docs/models) and
[model page](https://developers.openai.com/api/docs/models/gpt-5.6-luna).
Both conditions used the same Responses backend with `reasoning.effort=low`,
`max_output_tokens=4096`, strict structured output, and `store=false`.

## Credential boundary

The local `.env` is ignored by Git. The runner loads only the literal
`OPENAI_API_KEY` value and never evaluates shell expansion. No key value, raw
completion text, or private reasoning is written to an experiment artifact.
Traces retain sanitized errors, response IDs, output hashes, token usage,
latency, model identity, decisions, beliefs, and confidence.

## Design

The paired conditions were run on four fixed secrets spanning the four hair
branches of the 24-character Guess Who roster: Ada, Hugo, Nico, and Talia.
Each condition received the same public state, legal actions, history, and model;
only the prompt condition changed.

An initial preflight exposed a belief vector whose probabilities did not sum
exactly to one. The boundary now normalizes deviations up to 0.02 and records
the original sum and normalization event. Larger deviations remain invalid.
The adapter also declares its belief target and complete allowed state labels,
so a belief about the wrong variable or an omitted/malformed distribution is
rejected before the environment scores it.

## Results

The table below uses complete traces. Hugo's generic row comes from a targeted
recovery run because its first run exhausted three validation attempts on one
decision. First-run completion is therefore reported separately and is not
silently folded into the strategy score.

| Metric | Generic prompt | Single-game prompt |
|---|---:|---:|
| First-run completion | 3/4 (75%) | 4/4 (100%) |
| Completion after targeted recovery | 4/4 | 4/4 |
| Mean turns including final guess | 5.75 | 5.75 |
| Exact optimal-question agreement | 89.47% | 84.21% |
| Mean question regret | 0.01754 | 0.02339 |
| Belief output coverage | 100% | 100% |
| Mean multiclass belief Brier | 0.63920 | 0.65700 |
| Mean belief log loss | 1.53232 | 1.60808 |
| Information efficiency, bits/question | 0.97430 | 0.97430 |
| Confidence Brier vs optimal-question indicator | 0.13627 | 0.20942 |
| Provider attempts / decisions | 24 / 23 | 24 / 23 |
| Successful-panel tokens | 27,974 | 28,229 |
| Successful-panel latency | 135.30 s | 106.54 s |

Both prompt variants solved all four completed episodes in the same mean number
of turns. In this very small panel, the single-game prompt did not improve the
exact strategy metrics: generic had higher optimal-question agreement, lower
regret, and better belief and confidence scores. The two conditions selected
the exact same action at only 45.83% of aligned decision positions, so the equal
turn count does not mean they followed the same policy.

The first generic Hugo run failed after two valid game decisions when the next
decision exhausted all three validation attempts. The targeted recovery
succeeded but required one correction retry: the rejected belief summed to
0.8888888888, well outside the rounding tolerance and consistent with a missing
candidate state. One single-game episode also needed a validation retry. Across
the successful panel, each condition made 23 strategic decisions and 24 provider
attempts. This demonstrates why those counts must remain separate.

The successful generic panel normalized three small belief rounding errors; the
single-game panel also normalized three. These are retained as telemetry rather
than hidden preprocessing.

## Interpretation boundary

This experiment supports four narrow claims:

1. the real-model adapter, strict parser, retry loop, trace writer, and scorer
   operate end to end;
2. traces expose prompt-condition differences that success rate alone hides;
3. strict belief validation catches realistic completion errors;
4. a game-specific prompt is not automatically better than a generic prompt.

It does **not** establish a stable ranking between prompts, model optimality, or
cross-game generalization. The panel contains only four secrets, one environment,
one requested model, and non-replicated stochastic calls. The next justified
experiment is repeated seeds/runs on this fixed environment before spending on
a held-out-game transfer comparison.

Machine-readable aggregates are in
[`panel-report.json`](results/completion_gpt-5.6-luna_2026-08-20/panel-report.json).
The same directory contains the sanitized episode traces and original runner
reports, including the failed first Hugo report and its targeted recovery.
