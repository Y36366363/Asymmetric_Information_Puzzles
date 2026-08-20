# Completion-backed agent boundary

Date: 2026-08-19  
Status: implementation and deterministic fault tests complete; real-model run
not executed because this environment has no `OPENAI_API_KEY`

## Scope

This milestone adds the smallest boundary needed to compare the same completion
model under two prompt conditions without adding a game or a general-purpose
agent framework:

- **Generic:** receives the normalized public `AgentInput` and a game-independent
  strategic instruction.
- **Single-game prompted:** receives the identical input plus a versioned Guess
  Who balanced-split instruction.

`CompletionAgentPair` requires both conditions to share the same backend object
and requested model. The live runner also collects every API-returned resolved
model and exits nonzero if the two conditions do not resolve to one model. A
snapshot ID should be used when exact model reproducibility matters.

## Boundary contract

The provider-neutral layer consists of:

- `CompletionRequest`: model, condition, instructions, public input, and JSON
  schema;
- `CompletionResponse`: output text, response ID, resolved model, and token use;
- `CompletionBackend`: one `complete()` method;
- `CompletionBackedAgent`: strict parse, legal-action validation, bounded retry,
  and telemetry;
- `OpenAIResponsesBackend`: an optional real provider adapter;
- `CompletionAgentPair`: enforces shared backend and model across conditions.

The first environment uses concrete action IDs, so completion output does not
need an arbitrary action payload. The schema can be extended when a selected
benchmark environment genuinely requires payload-bearing actions.

## Output and retry policy

The model returns only:

```json
{
  "action_id": "one supplied legal action ID",
  "confidence": 0.0,
  "belief": {
    "target": "adapter state label family",
    "probabilities": [
      {"state": "state label", "probability": 1.0}
    ]
  }
}
```

`belief` may be `null`. Parsing rejects extra root fields, duplicate belief
states, unnormalized probabilities, invalid confidence, and illegal actions.
Failures are classified separately as:

- `parse_error` — not valid JSON;
- `validation_error` — wrong shape, invalid probability/confidence, or illegal
  benchmark action;
- `transport_error` — provider/client exception.

Every failure consumes one bounded attempt. The correction prompt reveals only
the failure class, not evaluator truth or the correct action.

## Recorded telemetry

Every trace step now includes `agentTelemetry` containing:

- condition, provider, and requested model;
- attempt outcome and retry count;
- parse, validation, and transport failure counts;
- per-attempt and total latency in milliseconds;
- input, output, and total tokens across all attempts;
- provider response ID and resolved model;
- final self-reported confidence;
- output character count and SHA-256 fingerprint.

Raw model text is not copied into telemetry. The validated action, belief, and
confidence are already present in the normal trace, while failed text receives
only a size and fingerprint. This records operational failures without storing
free-form private reasoning.

## OpenAI Responses adapter

The optional adapter follows the current official Responses API structure:
`model`, `instructions`, `input`, and strict `text.format` JSON schema. It reads
`usage.input_tokens`, `usage.output_tokens`, and `usage.total_tokens`, records the
returned model and response ID, and sets `store=false`. See the official
[Responses API reference](https://developers.openai.com/api/reference/responses/create)
and [Structured Outputs guide](https://developers.openai.com/api/docs/guides/structured-outputs).

The OpenAI SDK remains optional through `pip install -e '.[llm]'`; core puzzle
and benchmark tests do not require it.

## Guarded real run

The live script refuses to start without `OPENAI_API_KEY` and never accepts a
key as a command-line argument:

```bash
python -m pip install -e '.[llm]'
export OPENAI_API_KEY='...'
PYTHONPATH=src python scripts/run_completion_baseline.py \
  --model YOUR_EXACT_MODEL_OR_SNAPSHOT \
  --secret Ada \
  --output-dir completion-traces
```

It runs both conditions against the same secret and shared backend, then writes
`generic.json`, `single-game.json`, and `report.json`. The report contains
decision invocations, provider attempts, failures, retries, token use, latency,
confidence sequences, terminal result, and resolved-model consistency. Report
v1 distinguishes strategic
`decisionInvocations` from `providerAttempts`, so an internal retry is never
misreported as a new game decision.

For paid failure diagnosis, `--condition generic` or
`--condition single-game` reruns only the failed arm. Exhausted conditions retain
their full per-attempt telemetry in `failureTelemetry` even though no terminal
episode trace exists.

## Verification and current status

Deterministic tests cover:

1. same backend/model with distinct prompt conditions;
2. malformed JSON followed by a successful retry;
3. transport and illegal-action failures as separate classes;
4. exhausted retries retaining telemetry;
5. per-decision telemetry inside a complete episode trace;
6. strict OpenAI request shape and usage extraction with a test client;
7. literal dotenv loading without shell evaluation;
8. audited normalization of small probability rounding errors;
9. rejection and retry for the wrong adapter belief target.

The first authorized real-model experiment is reported in
[`completion_real_model_experiment_2026-08-20.md`](completion_real_model_experiment_2026-08-20.md).
