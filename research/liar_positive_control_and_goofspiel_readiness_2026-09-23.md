# Liar positive-control gate and Goofspiel readiness — 2026-09-23

## Decision

The redesigned same-game manipulation check improved decisions, but it did not
pass every preregistered gate. The four-condition 30-state experiment therefore
did **not** run. This is a planned negative result, not an infrastructure failure.

The exact four-card Goofspiel decision layer was implemented and tested locally
without starting a Goofspiel model experiment. Kuhn Poker remains the second
adversarial target, E-Card remains an exact-solver control, and full Love Letter
remains uncertified. No runtime strategy or ε-GTO label changed.

## Frozen design

The target panel comes from the previously audited 30-state one-die Liar's Dice
panel. Every state has the same unique best action under the exact sequence-form
solution, the frozen runtime CFR policy, and a separately trained DCFR policy.
The small check used a mechanically selected 12-state subset:

- 6 challenge-optimal states;
- 3 player-0 raise-optimal states;
- 3 player-1 raise-optimal states;
- 2 independent repeats per state and condition;
- no-memory and same-game positive-control conditions only.

The positive control uses 16 mechanically selected and test-disjoint worked
states, balanced 8 challenge / 8 raise. The earlier intended 10 / 10 split was
rejected before preregistration because only nine stable challenge examples
remain after excluding the full 30-state test panel.

The preregistration SHA-256 is
`dff66beb8bf03d7cdddde39e5bee327a3134a7420656fd4db7b98a82249d507a`.
Its rule required all of the following:

1. all 48 cells valid;
2. zero provider-token mismatches;
3. at least 80% repeat action agreement in each arm;
4. at least 85% exact-best-action rate in the positive control;
5. at least 15 percentage points improvement over no memory;
6. lower mean exact action regret than no memory.

Full request sizes were balanced with the provider's input-token counting
endpoint. This endpoint accepts the same input shape as the Responses API and
accounts for request formatting and structured-output schemas; see the
[official token-counting guide](https://developers.openai.com/api/docs/guides/token-counting).

## Result

| Metric | No memory | Same-game positive control |
|---|---:|---:|
| Valid decisions | 24 / 24 | 24 / 24 |
| Repeat action agreement | 10 / 12 (83.3%) | 10 / 12 (83.3%) |
| Exact-best-action rate | 16 / 24 (66.7%) | 20 / 24 (83.3%) |
| Mean exact conditional regret | 0.4861 | 0.2708 |

The positive control produced a +16.7 percentage-point accuracy lift and reduced
mean regret by 0.2153. Those effect gates passed. Both repeatability gates also
passed. The positive-control accuracy gate failed narrowly: 20 / 24 is 83.3%,
below the frozen 85% requirement (at least 21 / 24).

Consequently, `gatePassed` is false and `nextStep` is
`stop_before_main_experiment`. Lowering the threshold after observing this result
would invalidate the manipulation check, so the four-arm study remains blocked.

## Four-card Goofspiel horizontal layer

`GoofspielProbe` now maps a public simultaneous-bid state into the common
`AgentInput` / `AgentDecision` contract. Its oracle is deliberately different
from the Liar's Dice oracle:

1. exact backward induction supplies continuation values;
2. an exact zero-sum matrix solution supplies both players' current mixed
   strategies;
3. each candidate bid is evaluated against the equilibrium opponent's hidden
   simultaneous bid;
4. optional opponent-bid beliefs are scored against that exact mixed strategy.

All 628 multi-action public states in rounds one through three are enumerable.
A deterministic 30-state v1 panel is frozen for later work: 4 opening states,
13 second-round states, and 13 third-round states. Every selected state has at
least one strictly inferior action, so the panel can detect decision errors.

This layer supports a future horizontal experiment without implying that a
single chosen best response is itself a complete Goofspiel equilibrium policy.
The score is conditional action regret against an equilibrium opponent; full
policy exploitability remains a separate exact metric.

## Next decision point

Do not rerun the four-arm Liar experiment unchanged. First redesign the positive
control *before* collecting more test outcomes—for example, turn the worked
examples into an explicit reusable decision procedure, then freeze a fresh
manipulation check. The existing failed run must remain as negative evidence.

Once a new manipulation check passes, the intended order is:

1. run the four-condition Liar experiment on all 30 invariant states;
2. run a separately preregistered four-card Goofspiel comparison;
3. use Kuhn Poker as the second adversarial target;
4. keep E-Card as an exact-solver comparison rather than a primary agent task;
5. keep full Love Letter explicitly uncertified until its independent evaluator
   and admission gates pass.
