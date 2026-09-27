# Structured value manipulation update — 2026-09-27

## Decision

The frozen Liar's Dice structured-output check completed, but its preregistered
gate failed. The identical Goofspiel run was therefore not started. The 17
positive-reach Love Letter subgame information sets remain available as a later
panel, but model calls on them are also deferred. The complete Love Letter tree
audit continued independently in bounded batches.

This preserves the requested order and retains a negative result rather than
weakening a threshold after seeing the data.

## Frozen protocol

- Target: the certified one-die, stepwise Liar's Dice variant.
- Panel: six exact, profile-invariant states: three challenge-optimal and three
  raise-optimal.
- Conditions: unaided structured calculation and an oracle-assisted structured
  positive control.
- Repeats: two per state and condition, for 24 total cells.
- Output: `posterior -> immediate value -> continuation value -> total value ->
  final action` under one strict JSON schema.
- Scoring: an independent exact oracle scores every intermediate field and the
  final action. Training regret is never used as an evaluator.
- Budget control: provider-reported input tokens are exactly equal across the
  two conditions within every state.
- Scope: the oracle-assisted arm measures instruction and schema following only;
  it is not evidence of independent solving, transfer, Nash equilibrium, or GTO.

The OpenAI Responses API structured-output mechanism was used with a strict JSON
schema and storage disabled. Strict schema adherence constrains the response
shape but does not guarantee that strategic numbers are correct, so the exact
external scorer remains necessary. See the official
[Structured Outputs guide](https://developers.openai.com/api/docs/guides/structured-outputs).

## Result

All 24 cells were valid and all provider token counts matched the frozen plan.
The oracle-assisted arm exactly reproduced every posterior, immediate value,
continuation value, total value, and optimal action. Its repeat action agreement
was 100%.

The unaided arm did not meet the 80% repeatability threshold:

| Metric | Unaided | Oracle-assisted |
|---|---:|---:|
| Valid cells | 12/12 | 12/12 |
| Repeat action agreement | 66.7% | 100% |
| Optimal action rate | 66.7% | 100% |
| Mean posterior Brier error | 0.3889 | 0 |
| Mean immediate-value MAE | 0.3611 | 0 |
| Mean continuation-value MAE | 0.3333 | 0 |
| Mean total-value MAE | 0.6944 | 0 |
| Mean final-action regret | 0.4167 | 0 |

Two challenge-optimal states changed from challenge on the first repeat to the
final raise on the second. One raise-optimal state selected challenge in both
repeats. The remaining three states were stable and optimal. The failure is not
a serialization problem: every response was schema-valid and internally chose
an action maximizing its own reported totals. It is a strategic inference and
repeatability problem.

## Consequences

1. Goofspiel remains mechanically ready, but its model experiment is blocked by
   the Liar gate. No Goofspiel provider calls were made.
2. The 17 positive-reach Love Letter nodes remain an exact later-stage panel;
   they were not promoted or run after the failed prerequisite.
3. Full Love Letter remains uncertified. Five independent 20,000-history chunks
   increased the persistent audit from 1,142,965 to 1,242,965 histories, with
   180,660 information sets, 81 frontier nodes, depth 26, and zero structural
   failures. Enumeration is still incomplete, so no runtime label changed.
4. No new CFR variant and no additional game were introduced.

## Next experiment

Do not rerun the same failed plan or relax its threshold. The next small Liar
study should freeze a better-defined unaided estimand before any calls. In
particular, the equilibrium-conditioned posterior should not be treated as if it
were obtainable from public rules alone: the protocol should either supply a
fixed opponent policy/reach table or separately score a rules-only prior and a
policy-conditioned posterior. After that redesign passes its own repeatability
gate, the exact same protocol can be applied to Goofspiel.
