# Gameplay engagement and information-boundary audit — 2026-09-06

## Audit question

For each lobby entry, does the player's choice change a meaningful future,
does public feedback support learning, can the player counter a policy, and
does settlement explain hidden information without leaking it early?

The audit treats outcome variance as acceptable when decisions affect expected
value. Random outcomes alone are not evidence of strategic depth.

## Findings

| Environment | Current role | Agency and feedback | Main risk | Status / next action |
| --- | --- | --- | --- | --- |
| Fate Cases | risk-sensitive decision game | Offers, remaining values, and one counter-offer support a real stop/continue decision | choosing the first case is luck; offer quality lacks counterfactual review | retain; later compare Deal with No Deal value at each accepted offer |
| Blackjack | rule-scoped strategy trainer | actions alter bust and dealer-resolution probabilities; Practice mode audits choices | no Split/Surrender means the scope must stay explicit | healthy within stated rules |
| Restricted RPS | repeated mixed-strategy match | finite inventory and adaptive AI make current play affect later support | visible advice may reduce discovery for some players | healthy; consider optional advice concealment, not a new solver |
| Mastermind | exact information-acquisition puzzle | every guess contracts the candidate set with exact feedback | suggested guesses can turn play into automation | strong benchmark; keep suggestion optional in future UX work |
| Guess Who | exact information-acquisition puzzle | question partitions and remaining candidates are auditable | always showing the exact suggestion can remove challenge | strong benchmark; later add “independent” and “guided” views |
| Hidden Pursuit | adversarial belief search | public transport signals update a live belief set | density guidance can dominate novice choice | healthy; test guidance concealment separately |
| Battleship | adversarial search game | shots build a hit/miss state and ship geometry supports counterplay | result variance can obscure AI quality in one match | healthy; judge AI by paired multi-seed shot counts |
| E-Card | repeated timing match | precommitment, conditional timing forecast, and role-specific history create learnable counterplay | first round remains intentionally uncertain | repaired on 09/05; keep evidence at `strong_heuristic` |
| Pirates | backward-induction puzzle lab | proposals receive exact vote explanations | replay is mostly parameter variation, not opponent modelling | label and evaluate as a puzzle laboratory |
| Love Letter | belief-based card match | public discards and role effects update opponent-card belief | heuristic advice needs clearer counterfactual quality evidence | healthy; later score advice against bounded rollouts |
| Investment | risk-sensitive tournament | odds, Kelly stake, rank and elimination pressure create meaningful trade-offs | outcome luck dominates the final screen; no “what if” comparison | highest UX priority after Liar's Dice: add counterfactual bankroll review |
| Kuhn Poker | equilibrium-backed bluffing benchmark | private cards, mixed betting and exact exploitability support strategic learning | short-run winnings are noisy | healthy; retain long-run framing |
| Liar's Dice | hidden-state bluffing match | private dice and public bids should support inference and challenge timing | **live history leaked AI confidence derived from its private dice** | fixed today; next research slice is fixed opponent types and shift robustness |
| Goofspiel | equilibrium-backed simultaneous bidding | finite cards create opportunity cost and an exact post-match audit | four rounds are short but analytically clean | healthy benchmark; do not inflate it artificially |
| Worm | adversarial-search puzzle lab | belief set and forced movement make search order meaningful | solution disclosure can erase the puzzle | healthy after hint/answer concealment; keep as puzzle lab |

## Implemented repair: Liar's Dice

The AI still computes a confidence value from its private dice when choosing to
raise or challenge. During play, snapshots now remove that value from both the
visible history and `informationSet.publicHistory`. After settlement, a
separate `postRoundDecisionAudit` reports the AI's private estimate and action.
This preserves the bluff during the decision and provides learning evidence
after the hidden dice are legitimately revealed.

The AI remains a `strong_heuristic`: its 45% threshold is not a solved
equilibrium. The next rigorous extension should introduce declared, frozen
opponent policies and measure robustness when the policy changes, rather than
claiming that a more theatrical bot is optimal.

## Prioritized follow-up

1. Add Liar's Dice opponent-shift experiments outside the player UI, with fixed
   cautious, balanced, and aggressive policies and seeded repeats.
2. Add an investment post-round counterfactual showing the bankroll change for
   each available stake under the realized outcome, clearly separated from
   ex-ante expected value.
3. Test optional adviser concealment in Mastermind and Guess Who so assistance
   supports learning without replacing the player's decision.

These changes deepen strategic feedback and benchmark quality without growing
the project into a broad game collection.
