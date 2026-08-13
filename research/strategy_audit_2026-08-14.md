# AIP strategy audit — 2026-08-14

This audit distinguishes mathematical optimality from a policy that merely
performs well in simulation. A strategy is called **optimal** only when the
implemented rules, objective, information boundary, and proof all match.

## Current strategy status

| Game | Current policy | Status | What the claim actually means |
| --- | --- | --- | --- |
| Pirate Council | Backward induction | Exact in model | Optimal under the declared vote threshold and strict survival/coin preferences. Different tie preferences change the answer. |
| Moving Worm | Breadth-first belief search | Exact in model | Produces a shortest guaranteed open-loop capture sequence under forced adjacent movement. |
| Guess Who | Dynamic programming | Exact in model | Globally minimizes expected or worst-case questions for the fixed 24-person roster, uniform prior, and eight-question bank. |
| Restricted RPS | Exact finite-game minimax plus bounded exploitation | Safe core, adaptive overlay | The exposed equilibrium is exact. The deployed exploit mixture may score better against a biased player but gives up a strict minimax guarantee. |
| Blackjack | Six-deck S17 basic strategy | Rule-scoped optimum | Optimal for the available hit/stand/double actions without splits, surrender, insurance, or card counting. It is not universally optimal Blackjack. |
| Kuhn Poker | Equilibrium-inspired mixed frequencies | Strong benchmark | The tiny game is solvable, but the current repeated-match implementation has not yet been exhaustively checked for exploitability at every information set. |
| E-Card | Timing randomization with bounded adaptation | Heuristic | Uses legal public timing history, but no equilibrium proof exists for the repeated asymmetric scoring model. |
| Battleship | Placement-density targeting | Improved heuristic | Strong one-step search, not an exact posterior over complete non-overlapping fleets and not a lookahead optimum. |
| Mastermind | Bounded one-step minimax | Strong heuristic | Exact candidate filtering; the opening search is budgeted, so global minimum expected attempts is not proved. |
| Hidden Pursuit | Belief pursuit / evasive-information scoring | Strong heuristic | Belief pursuit captures the current evader in every audited seed, but neither side is a full 12-round minimax policy. |
| Love Letter | Remaining-card belief scoring | Strong heuristic | Respects hidden information and dominates random play; fixed player-first rounds create a measurable first-move advantage. |
| Liar's Dice | Exact claim probability plus fixed challenge threshold | Heuristic | Probability calculation is exact for the local wild-one rules; bidding and challenge utility are not solved as a sequential equilibrium. |
| Investment Tournament | Kelly-family policies | Objective-dependent | Kelly optimizes long-run log growth. Tournament title rate, survival rate, and final wealth are different objectives with different preferred risk. |
| Cases of Fate | Expected value, certainty equivalent, banker posterior | Decision aid | Auditable risk metrics, not a strategic optimum against every possible banker process or utility function. |

## Repeated comparisons

All experiments use fixed seeds and live in `research/`.

### Battleship policy evolution

The old density policy counted a ship placement whenever it touched *any*
unresolved hit. With two adjacent hits, this could score perpendicular cells
that could not extend the observed straight hit line. The new 10×10 and 12×12
policy requires one candidate placement to explain the full connected straight
cluster. The 15×15 board deliberately retains the legacy rule because an early
prototype worsened its P90 tail.

| Board | Random mean | Hunt mean | Legacy density mean | Enhanced mean | Legacy P90 | Enhanced P90 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 10×10 | 95.267 | 55.770 | 45.927 | **45.477** | 58 | **56** |
| 12×12 | 139.183 | 78.710 | 65.510 | **63.640** | 85 | **84** |
| 15×15 | 218.723 | 118.660 | 96.883 | 95.933* | 125 | 123* |

`*` The named enhanced policy intentionally uses the unchanged legacy rule on
15×15. The small difference in the four-policy summary comes from independent
policy random seeds; a strict paired same-seed comparison is exactly tied in
all 300 games, as expected.

On paired 10×10 boards the enhanced policy beat the exact legacy baseline 141
times, tied 20, and lost 139. Its mean improvement was small (`0.067` shots),
but P90 improved from 58 to 56. On 12×12 it improved by `1.48` shots on average
and lowered P90 from 85 to 84. This is a conservative, evidence-gated upgrade,
not a claim of global optimality.

### Guess Who exact oracle

The complete fixed roster still gives the same answer: entropy, one-step
minimax, exact expected-cost DP, and exact worst-case DP all average **5.667**
total turns and have a six-turn worst case. The deeper solver therefore proves
that the cheaper greedy opening is already optimal for this roster.

### Hidden Pursuit

Across 1,000 seeds, belief-pursuit detectives captured random, distance, and
evasive-information fugitives in **100%** of games, with mean capture rounds
3.33, 4.02, and 4.24. This validates strength against the implemented opponent
set, not optimal play against every possible evasion policy.

### Love Letter

Across 2,000 matches, belief play beat a random AI in **91.45%** of matches;
random play beat the belief AI in only **17.40%**. Belief versus belief still
favored the player at **63.15%**, confirming that fixed player-first rounds are
a material structural advantage. A future hard mode should alternate the first
actor before using deeper expectiminimax.

### Investment Tournament

Across 3,000 seeds, double Kelly produced the highest title rate (**28.73%**)
and mean bankroll, while standard Kelly retained a higher survival rate
(**54.03%** versus **46.70%**). Half Kelly survived even more often
(**58.40%**) but won fewer titles. There is no honest single “best” strategy
until the player chooses an objective.

## Next optimization priorities

1. Audit Kuhn Poker exploitability at every information set and replace its
   hand-written frequencies with an exact equilibrium table if any gap exists.
2. Alternate Love Letter first action, then compare the current belief scorer
   with shallow determinized expectiminimax on identical deals.
3. Upgrade Battleship from independent ship placements to sampled legal
   complete fleets only if both mean and P90 improve within the interaction
   time budget.
4. Treat the RPS exploit overlay as an optional opponent profile; retain the
   exact minimax distribution as the clearly labeled non-exploitable mode.
