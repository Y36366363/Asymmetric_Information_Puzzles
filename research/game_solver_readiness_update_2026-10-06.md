# Game solver readiness update — 2026-10-06

## What “solved” means here

For the unified GTO track, a game is counted as solved only for its explicitly
declared finite rules and scope when it has an exact or thresholded candidate,
an independent evaluator, consistent information sets and an exploitability
certificate. A solved subgame is not counted as a solved larger game, and an
exact single-agent optimization is not relabeled as a two-player GTO result.

## Unified GTO/equilibrium pipeline

| Declared game scope | Current status | Independent result | Runtime scope |
|---|---|---:|---|
| One-die stepwise Liar's Dice | Complete declared variant | exploitability 0 | certified ε-GTO mode allowed |
| Four-card Goofspiel | Complete exact game | exploitability 0 | exact-equilibrium mode allowed |
| Kuhn Poker | Complete exact reference | maximum unilateral deviation gain 0 | reference/benchmark |
| Single-round E-Card timing game | Complete exact solver control | exploitability 0 | repeated adaptive game remains heuristic |
| Three-character strategic Guess Who | Complete certified research subgame | exploitability about 1.11e-16 | no transfer to 24-character game |
| Four-card Love Letter late-round subgame | Complete certified research subgame | exploitability 0 | no transfer to full round |

Thus six precisely scoped games or subgames have completed the project's exact
or independently certified equilibrium method. Only one-die Liar's Dice and
four-card Goofspiel currently expose the corresponding certified runtime mode.
Kuhn and E-Card are controls; Guess Who and Love Letter remain research-only
subgame certificates.

## Not complete in the unified GTO track

| Game | Current boundary | Required next work |
|---|---|---|
| Five-die Liar's Dice | transparent probability heuristic only | freeze action abstraction and rules, build scalable candidate and independent best response |
| Full 16-card Love Letter round | extensive-form model exists, structural traversal incomplete | close the tree audit, solve a candidate, run complete independent best response, bind promotion evidence |
| Full 24-character strategic Guess Who | no certificate transfer from three-character model | freeze a scalable strategic rule and obtain a new independent certificate |

The full Love Letter audit now covers 1,491,622 histories and 214,487 observed
information sets with no recorded structural failure, but 77 frontier nodes
remain. It is therefore still uncertified.

## Other exact components are not the same claim

The project also contains exact-in-model or rule-scoped methods for Pirate
Council, Moving Worm, the original single-agent Guess Who decision tree,
Restricted RPS and restricted-action Blackjack. These remain useful exact
solvers, but they have not all gone through the newer extensive-form
candidate → independent best response → promotion pipeline and should not be
combined with the six-item GTO count above.

## Today's Love Letter mechanism result

The preregistered current-private-hand full-support policy made all 60 four-card
information sets reachable but produced zero posterior shift. This is a valid
negative result: the hidden-world pairs differ by private card acquisition
order, whereas the fixed policy depends only on the current hand. The fixed
policy is strongly exploitable (`0.358319`) and correctly fails the GTO gate.
Future belief-manipulation work must separately preregister either a
history-sensitive policy or a posterior target that collapses
acquisition-order-equivalent worlds.
