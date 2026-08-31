# Novice onboarding audit — 2026-08-31

## Question

Can an otherwise capable player with no prior knowledge of these games complete a first meaningful action without asking another person or being shown a hidden solution?

## Minimum comprehension contract

Every playable environment now exposes the same four-part path:

1. **Goal** — what outcome the player is trying to produce.
2. **First action** — which visible control starts play.
3. **Feedback** — which public signal changes after the action and how to read it.
4. **Finish condition** — how the player knows the game has ended or the objective has been met.

The full rules modal provides role, goal, numbered play sequence, example, finish condition, and terminology. Its final button says explicitly that it closes the explanation and starts play. A compact first-turn guide then remains beside the live controls until the player takes a meaningful action.

## Coverage audit

| Environment | First action made explicit | Feedback named | Hidden answer protected |
| --- | --- | --- | --- |
| Cases of Fate | Keep a case | Removed prizes, offer vs expectation | Yes |
| Blackjack | Hit / Stand / Double | Total, dealer upcard, post-action Practice audit | Yes |
| Restricted RPS | Spend a gesture | Score and public inventories | Yes |
| Mastermind | Submit four distinct digits | Exact and misplaced counts | Yes |
| Guess Who | Ask a yes/no question | Candidate elimination | Yes |
| Hidden Pursuit | Move the highlighted detective | Transport, reveals, belief set | Yes |
| Battleship | Configure and lock fleet | Hit, miss, sunk, salvo count | Yes |
| E-Card | Play one card | Simultaneous reveal and remaining cards | Yes |
| Pirate Council | Allocate every coin | Rational vote threshold | The benchmark remains visible by design |
| Love Letter | Play one legal card | Public discard and belief panel | Yes |
| Kelly Tournament | Select offer and stake | Bankroll, rank, elimination round | Yes |
| Kuhn Poker | Respond to Check or Bet | Public action and payoff | Yes |
| Liar's Dice | Raise or challenge | Claim probability and reveal | Yes |
| Goofspiel | Secretly bid one card | Prize, bids, remaining cards | Yes |
| Moving Worm | Probe one hole | Adversarial belief-state update | Explicit solution remains opt-in |

## Interaction decisions

- Guidance is on by default and can be disabled globally from the header. The preference persists locally and does not change game state or scores.
- Guidance disappears after the first meaningful action, preventing permanent instructional clutter.
- Switching language updates the toggle, rules exit, and every first-turn guide without restarting the game.
- Battleship guidance adapts to the one-shot 10×10/12×12 rules and the two-shot 15×15 salvo rule.
- No opponent strategy, payoff, benchmark claim, or game engine was changed in this update.

## Verification target

Static tests require the guidance toggle, explicit rules exit, bilingual copy, and coverage of all 15 playable environments. Browser verification checks default-on behavior, persistence, language switching, modal exit, responsive fit, and empty warning/error logs.
