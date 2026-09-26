# Game readiness and Love Letter continuation — 2026-09-26

## Outcome

The project now distinguishes “the declared variant is basically constructed”
from “a related larger game is solved.” The readiness audit recomputes exact
metrics rather than inferring completion from file presence or trainer output.

| Scope | Current status | Main remaining work |
|---|---|---|
| One-die stepwise Liar's Dice | Complete declared variant | Structured intermediate-output model check; any rule expansion needs a new certificate |
| Five-die Liar's Dice | Heuristic only, not GTO | Freeze scalable rules/action abstraction, candidate solver and independent response |
| Four-card Goofspiel | Complete exact solver and benchmark | Structured intermediate-output model check |
| Kuhn Poker | Complete exact reference | Optional second adversarial model target |
| Single-round E-Card | Complete solver control | Keep as control; multi-round adaptation is not ε-GTO |
| Love Letter four-card late subgame | Complete certified research subgame | Do not generalize to the full round |
| Full-round Love Letter | Incomplete | Close tree, solve candidate, complete independent response, promotion |

“Complete” here is scoped. It does not mean every ruleset, player count, deck
size, runtime mode, or model-evaluation protocol is complete.

## Liar's Dice assessment

The one-die stepwise game has all core layers:

- audited perfect-recall extensive-form adapter;
- exact sequence-form reference;
- independently evaluated frozen CFR runtime policy;
- normalized artifact metadata and promotion gate;
- undertrained/malformed negative controls;
- exact 30-state decision panel;
- independently scored posterior/immediate/continuation/action decomposition;
- runtime ε-GTO mode restricted to the declared one-step bid ladder.

It is therefore reasonable to treat this variant as basically constructed. The
2026-09-24 language-memory experiment did not show a reliable abstract-memory
benefit, but that is an agent-evaluation result rather than a solver deficiency.

The five-die playable mode remains a transparent probability heuristic. It must
not inherit the one-die certificate.

## Goofspiel and other exact controls

Four-card Goofspiel has exact backward induction, exact per-state zero-sum
matrices, an exact runtime equilibrium mode, policy-level exploitability tests,
a frozen 30-state decision panel and the same value-decomposition interface as
Liar's Dice. Its core solver/benchmark construction is complete. The next useful
question is whether a model can emit repeatable intermediate values, not whether
another CFR variant is needed.

Kuhn Poker remains a complete exact reference and the strongest small second
adversarial target. Single-round E-Card remains an exact timing-matrix control;
the playable multi-round adaptive session correctly remains a strong heuristic.

## Love Letter subgame decomposition

The exact four-card late-round subgame still has:

- 1,081 histories;
- 60 information sets;
- exact sequence-form value `1/6` to player 0;
- zero independently measured exploitability.

The shared decomposition interface now partitions its information sets by
counterfactual reach under the exact equilibrium:

- 17 information sets have positive reach and therefore a defined conditional
  hidden-world posterior;
- 43 information sets have zero reach and no mathematically defined conditional
  posterior under that profile.

All 17 reachable decompositions exactly reconstruct the independent action
values and include both terminal-effect value and nonterminal continuation
value. The zero-reach nodes remain explicitly listed instead of receiving a
fabricated uniform posterior. All 60 action-value tables remain covered by the
independent evaluator, but only the reachable 17 are eligible for conditional
posterior scoring under this exact profile.

Future model panels should either use the 17 positive-reach nodes or preregister
an explicit tremble policy. A tremble changes the reference distribution and
must not be silently introduced after seeing results.

## Full-round Love Letter progress

The saved checkpoint revision still matches the current game, rules and audit
implementation. Eight bounded chunks were run today: an initial 30,000 histories
followed by 100,000 additional histories. The latest cumulative state is:

- histories: **1,142,965**;
- terminal histories: **514,898**;
- chance histories: **303,496**;
- decision histories: **324,571**;
- information sets observed: **165,139**;
- maximum depth: **26**;
- frontier nodes: **75**;
- structural failures: **none**;
- complete: **false**.

The frontier count is not a denominator and cannot be converted into a percent
complete. Until it reaches zero, this is only prefix evidence. No candidate
full-round policy, full independent best response, or promotion evidence exists.
The runtime must continue to reject ε-GTO mode for full Love Letter.

## Next steps

1. Run a small preregistered structured-output manipulation check on Liar's Dice
   using posterior Brier, challenge/immediate MAE, raise-continuation MAE,
   additivity residual and final regret as separate endpoints.
2. If field validity and repeatability pass, reuse the identical schema on the
   frozen Goofspiel panel.
3. Use the 17 positive-reach Love Letter subgame information sets only after the
   two simpler games establish that the model can produce meaningful numerical
   intermediates.
4. Continue the full Love Letter structural traversal in bounded resumable
   chunks, independently of model experiments.
5. Do not add more CFR variants or more games until these mechanism checks are
   stable.
