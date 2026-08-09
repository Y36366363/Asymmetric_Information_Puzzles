# User-journey audit — 2026-08-09

## Method

The public GitHub Pages build was tested as a first-time player in English at
desktop size and at a 390 × 844 mobile viewport. For every playable game, the
audit opened all six rule sections, performed the first meaningful action,
read the resulting feedback, returned to the lobby, and checked browser error
logs. Complete session loops remain covered by the automated worker tests.

## Coverage

| Game | First action verified | New-player feedback |
| --- | --- | --- |
| Cases of Fate | Kept a case and opened another | Remaining opening count updated immediately |
| Blackjack | Let the strategy AI act | Decision log stated the action and whether it matched basic strategy |
| Restricted RPS | Played one limited card | Both moves, result, and consumed stock were revealed |
| Bulls & Cows | Filled and submitted the AI opening | Exact/misplaced feedback reduced 5,040 candidates to 720 |
| Hidden Pursuit | Moved detective A | Turn changed to B and the belief set fell from 16 to 15 |
| Battleship | Rotated a ship, locked the fleet, fired | Both shots and hit/miss outcomes appeared in the turn log |
| E-Card | Played a special card | Simultaneous reveal and round result appeared correctly |
| Pirate Council | Submitted a legal 100-coin proposal | Vote count and equilibrium allocation were explained |
| Kuhn Poker | Took the first legal action | Public action sequence and showdown state updated |
| Liar's Dice | Made the opening bid | AI response and confidence became public |
| Moving Worm | Followed the first guaranteed check | Live counter and next guaranteed hole updated |

All eleven rule dialogs contained role, goal, ordered steps, a concrete example,
ending conditions, and terminology. No application warnings or errors appeared
in the browser log.

## Confirmed issues and actions

1. Blackjack was three pixels wider than a 390px viewport because three action
   buttons could not wrap. The action row and long hands now wrap on mobile.
2. After an AI raise in Liar's Dice, the quantity field could retain a value
   below the new legal minimum. It now advances to at least the server-provided
   minimum before the player's next decision.
3. Pirate Council disabled Submit until exactly 100 coins were allocated but did
   not explain the lock. The instruction now states the remaining or excess
   amount and explicitly says when Submit unlocks.

## Remaining learning friction

E-Card, Kuhn Poker, and Liar's Dice still require more conceptual effort than
the first four games, but their difficulty labels, six-part rules, public logs,
and information-set explanations are consistent. A future optional guided first
round would reduce friction without weakening the games themselves.
