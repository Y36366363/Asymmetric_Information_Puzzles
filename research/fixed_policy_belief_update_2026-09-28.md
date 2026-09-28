# Fixed-policy belief update — 2026-09-28

## Outcome

The ambiguous Liar's Dice target was replaced with an explicit calculation
contract:

`base prior -> supplied policy reach -> conditioned posterior -> immediate value
-> supplied continuation anchor -> total value -> action`

The corrected Liar's Dice v2 experiment passed every frozen gate. The identical
v2 contract was then applied to four-card Goofspiel and also passed. These are
calculation-manipulation results, not evidence that the model independently
discovered an equilibrium.

## Why the old target was invalid

The previous unaided prompt supplied public rules and history but scored the
model against a posterior conditioned on one exact equilibrium policy. Public
rules determine the die prior, but do not uniquely identify the opponent's
behavioral strategy or its reach probabilities. Therefore the scored posterior
contained information absent from the task input.

The new contract separates:

- **base prior**: uniform chance prior over the opponent die in Liar's Dice;
- **policy reach weights**: explicitly supplied relative likelihoods under a
  frozen opponent policy;
- **conditioned posterior**: normalized prior times reach;
- **immediate payoff table**: explicit per-action, per-hidden-state utilities;
- **continuation anchors**: independently computed continuation values.

For Goofspiel, the base prior is explicitly an experimental uniform action
baseline, not a probability implied by the rules. Fixed equilibrium bid weights
then produce the predictive opponent-bid distribution.

The Responses API uses strict `text.format` JSON schema output. The response
schema name is now part of the request object so token counting and execution
use exactly the same request shape. Strict schema adherence controls structure;
the independent numerical scorer remains necessary. See the official
[Structured Outputs guide](https://developers.openai.com/api/docs/guides/structured-outputs).

## Preserved failed evidence

The first fixed-policy preregistration was not overwritten. All 12 model outputs
were valid, Bayes conditioning and optimal actions were correct, but its gate
failed for two reasons:

1. token counting used schema name `aip_conditioned_value_decomposition` while
   execution used the backend default `aip_agent_decision`, creating a consistent
   two-token mismatch in every cell;
2. two repeated responses omitted a challenge payoff of `+1`, producing mean
   immediate and total-value MAE of `1/12`.

V2 fixed the request identity and supplied the per-hidden-state immediate payoff
table. No threshold was relaxed.

## Liar's Dice v2

- six states, two repeats, 12/12 valid;
- zero input-token mismatches;
- repeat action agreement: 100%;
- optimal action rate: 100%;
- conditioned-posterior, policy-weight, immediate-value, continuation-value and
  total-value errors: zero;
- base-prior Brier: approximately `1.67e-21`, only decimal rounding;
- maximum additivity residual and final regret: zero.

## Goofspiel v2

- the same schema, instructions, gates, six-state/two-repeat design and supplied
  component semantics were used;
- 12/12 valid with zero token mismatches;
- optimal action rate: 100%;
- repeat action agreement: `5/6 = 83.3%`, above the frozen 80% threshold;
- the only changed action occurred at a state with three exactly tied optimal
  bids (`bid:1`, `bid:2`, and `bid:3`, all value zero), so both observed actions
  had zero regret;
- all scored errors were zero apart from floating-point noise below `7e-18`.

## Love Letter boundary

The two prerequisite games now permit design work on the 17 positive-reach
four-card Love Letter information sets. They should not yet be sent to the model.
Unlike one-die Liar's Dice, the correct base distribution over hidden worlds
must reflect card multiplicities, deal/removal history and the public trajectory.
The next implementation step is an independent combinatorial-prior oracle,
followed by fixed-policy reach conditioning. Zero-reach nodes remain excluded
unless an explicit tremble policy is preregistered.

The complete Love Letter tree remains separate and uncertified. Three additional
20,000-history chunks advanced the persistent audit to 1,302,965 histories,
188,348 information sets, depth 26 and 80 frontier nodes, with zero structural
failures. The traversal is incomplete; no runtime or ε-GTO label changed.
