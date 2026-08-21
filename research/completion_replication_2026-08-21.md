# Completion prompt replication — 2026-08-21

## Why this experiment

The 2026-08-20 panel suggested that a game-specific prompt did not outperform a
generic strategic prompt, but four secrets with one call per condition were too
small to distinguish a persistent effect from sampling variation. Today's only
paid experiment repeats the same four-secret, two-condition Guess Who panel with
the same requested model and request settings.

The official [Responses create reference](https://developers.openai.com/api/reference/cli/resources/responses/methods/create)
lists sampling temperature but no seed parameter. The repeat is therefore an
independent stochastic replication, not a deterministic replay. The requested
and resolved model remained `gpt-5.6-luna`, with `reasoning.effort=low`, strict
structured output, `max_output_tokens=4096`, and `store=false`.

## Replication result

All eight new episodes completed and solved their secret. The strategic metrics
still distinguished the prompt conditions:

| Metric | Generic, run 1 | Generic, run 2 | Single-game, run 1 | Single-game, run 2 |
|---|---:|---:|---:|---:|
| Mean turns | 5.75 | 5.75 | 5.75 | 6.00 |
| Exact optimal-question agreement | 89.47% | 89.47% | 84.21% | 75.00% |
| Mean question regret | 0.01754 | 0.01754 | 0.02339 | 0.03611 |
| Mean belief Brier | 0.63920 | 0.63925 | 0.65700 | 0.64931 |
| Confidence Brier | 0.13627 | 0.10760 | 0.20942 | 0.26884 |
| Information efficiency, bits/question | 0.97430 | 0.97430 | 0.97430 | 0.93610 |

Generic's aggregate strategic metrics repeated almost exactly even though its
aligned action sequence agreed only 75% across runs. Single-game action agreement
across runs was 45.24%; in run 2 it took an extra question on Talia and was worse
on turns, exact-policy agreement, regret, confidence calibration, and information
efficiency. This is evidence that the trace metrics are sensitive to real policy
variation rather than merely terminal success.

Pooling the two completed panels gives eight episodes per condition:

| Metric | Generic pooled | Single-game pooled | Single minus generic |
|---|---:|---:|---:|
| Mean turns | 5.750 | 5.875 | +0.125 |
| Exact optimal-question agreement | 89.47% | 79.49% | -9.98 pp |
| Mean question regret | 0.01754 | 0.02991 | +0.01237 |
| Mean belief Brier | 0.63922 | 0.65307 | +0.01385 |
| Confidence Brier | 0.12193 | 0.23989 | +0.11796 |
| Information efficiency, bits/question | 0.97430 | 0.95520 | -0.01910 |

The correct narrow interpretation is that this particular game-specific prompt
has not demonstrated an advantage for this model and environment. It should not
be treated as a stronger baseline merely because its text encodes the balanced-
split heuristic. This is not proof that generic prompting is generally better:
there are only two stochastic repetitions, one environment, four fixed secrets,
and no held-out transfer treatment.

## Reliability and usage

The new generic panel made 23 decisions and 23 provider attempts with no retry.
The new single-game panel made 24 decisions and 25 attempts; one malformed belief
was rejected and corrected. Both conditions again exercised audited rounding
normalization (three generic and four single-game events).

The fresh run used 42,583 input and 13,965 output tokens, 56,548 total. At the
official [GPT-5.6 Luna price observed on 2026-08-21](https://developers.openai.com/api/docs/models/gpt-5.6-luna)
of $0.20/M input and $1.20/M output tokens, its estimated token cost is $0.02527.
This is an estimate from trace usage, not an account billing record.

## Offline reproducibility improvement

`EpisodeTrace` can now reconstruct itself from a dictionary, JSON string, or
JSON file with strict schema and nested contract validation. Historical traces
can therefore be passed back through `summarize_guess_who_traces` without another
model call. Round-trip and rejection tests cover valid traces, unknown schema
versions, and unexpected fields.

The complete machine-readable comparison is
[`replication-report.json`](results/completion_gpt-5.6-luna_2026-08-21_replicate-2/replication-report.json).
The same directory contains all eight sanitized traces and four per-secret
runner reports. No raw completion text or credential is retained.
