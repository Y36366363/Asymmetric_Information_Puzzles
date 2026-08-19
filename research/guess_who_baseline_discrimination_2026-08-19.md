# Guess Who baseline discrimination study

Date: 2026-08-19  
Status: executable local controls; no external LLM calls

## Research purpose

The first benchmark slice could show that an exact oracle scores perfectly, but
that alone did not establish that its traces and metrics distinguish meaningfully
different policies. This update adds two controls before adding another game:

1. **Generic weak baseline** — chooses one legal action by a stable seeded hash.
   It reads no rules, observation, history, beliefs, or game-specific state.
2. **Single-game prompted heuristic proxy** — follows an explicit Guess Who
   instruction: maintain a uniform posterior over consistent candidates and ask
   the public question with the most even immediate split.

The second control is intentionally named a proxy. It executes a transparent
prompt-derived policy locally and is not evidence about any LLM. Its exact prompt
is versioned in `aip.benchmark.guess_who.SINGLE_GAME_PROMPT`, so a completion-
backed agent can later use the same instruction without changing the condition.

## Honest policy labels

| Condition | Game-specific knowledge | Belief output | Claim |
| --- | --- | --- | --- |
| Algorithmic oracle | Yes | Exact posterior | Proved optimal in the declared model |
| Single-game prompted proxy | Yes | Uniform consistent posterior | Strong one-step heuristic |
| Generic weak | No | None | Unreferenced exploratory control |

Every trace now serializes this distinction in `agentMetadata`, separately from
the environment's evidence level. In particular, both local baselines record
`isLlm=false`.

## Evaluation design

- Oracle: one episode for each of the 24 secrets.
- Prompted proxy: the same 24 secrets.
- Generic weak: 100 stable seeds × the same 24 secrets = 2,400 episodes.
- Date/seed range: `range(100)`, evaluated on 2026-08-19.
- All policies receive identical public legal actions and hidden secrets.
- Episode identifiers are state-independent, and the generic weak hash excludes
  them, preventing identifiers from becoming an accidental hidden-state channel.
- Final identity guesses are excluded from agreement and regret averages because
  they are forced once one candidate remains. Including them would artificially
  inflate every policy's score.

## Results

| Metric | Oracle | Prompted proxy | Generic weak |
| --- | ---: | ---: | ---: |
| Episodes | 24 | 24 | 2,400 |
| Solved rate | 100% | 100% | 100% |
| Mean turns, including final guess | 5.6667 | 5.6667 | 5.9033 |
| Worst turns | 6 | 6 | 8 |
| Exact-policy agreement on questions | 100% | 100% | 70.29% |
| Mean exact action regret | 0.0000 | 0.0000 | 0.0483 |
| Belief-output rate | 100% | 100% | 0% |
| Mean information efficiency, bits/question | 0.9934 | 0.9934 | 0.9755 |

Relative to the generic weak control, the prompted proxy saves 0.2367 turns,
adds 29.71 percentage points of exact-policy agreement, and removes 0.0483
expected-question regret per information decision.

## Interpretation

The trace and scoring layer now separates the controls along four independent
axes:

- **Outcome efficiency:** both solve every episode, but the weak policy takes
  longer and has a worse tail. Solved rate alone would have missed the gap.
- **Decision quality:** exact agreement and regret identify locally inferior
  questions even when the final answer is correct.
- **Information efficiency:** the weak control resolves fewer prior bits per
  question.
- **Belief observability:** belief coverage distinguishes “no reported belief”
  from a calibrated posterior instead of silently assigning a zero error.

The prompted proxy happens to match the exact oracle on every reachable state in
this fixed roster. This is an exhaustive empirical result for this question bank,
not a proof that balanced one-step splitting is generally optimal. Different
rosters, nonuniform priors, question costs, or noisy answers can separate it from
the dynamic-programming oracle.

## Remaining limitations

- No actual generic or single-game-prompted LLM has been called yet.
- Belief calibration cannot be compared against the generic weak agent because
  it honestly abstains from game-specific belief labels; coverage is reported
  instead.
- This is still a within-game test, so it says nothing about transfer gain.
- The deterministic proxy removes language variance and should remain a control,
  not replace the future LLM condition.

The next narrow milestone should be a completion-backed agent boundary that runs
the same model under a generic prompt and this single-game prompt, with strict
JSON parsing, retry accounting, latency/token metadata, and no change to the
environment or scorer.
