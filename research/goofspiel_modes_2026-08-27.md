# Goofspiel difficulty modes and cross-game UI audit — 2026-08-27

## Why Goofspiel was selected

The Kuhn Poker update established a useful rule for difficulty settings: a mode
must change an explicit policy, preserve the same rules and player role, and
carry evidence that quantifies the difference. Goofspiel is the strongest next
candidate because the existing four-card solver already gives an exact
zero-sum equilibrium for every public state.

Other current games were checked but not given artificial difficulty labels:

- Blackjack already separates normal play from coached practice; the mode
  changes feedback, not the dealer policy.
- Mastermind has a bounded one-step minimax adviser, but no opponent policy to
  weaken. Calling its search-budget variants “easy AI” and “GTO AI” would be
  misleading.
- Battleship and Love Letter have useful heuristics but no current exact
  exploitability calculation, so a “perfect” mode is not justified.
- Restricted RPS has an exact finite-horizon equilibrium and remains a good
  later candidate, but Goofspiel offers a clearer inventory-management lesson.

## Audited mode definitions

| Mode | AI policy | Evidence level | Initial game value | AI exploitability |
| --- | --- | --- | ---: | ---: |
| Basic | Spend the remaining card closest to the current prize; break ties downward | Strong heuristic | `0` equilibrium reference | `2` points/match |
| Advanced | Sample the exact public-state zero-sum equilibrium | Equilibrium-backed | `0` | `0` |

The Basic number is not a simulation estimate. Dynamic programming enumerates
every future prize reveal and every player response. A best response against
the deterministic heuristic earns exactly `+2` expected score-difference
points from the initial state. The Advanced value and zero exploitability are
backed by the exact rational matrix solver inside this four-card ruleset.

“Exact” does not extend to larger decks, alternative tie rules, multiplayer
Goofspiel, or objectives such as maximizing match-win probability instead of
expected score difference.

## Player-facing contract

- Difficulty is visible before the first decision and remains visible during
  play.
- Switching difficulty starts a fresh four-round match, preventing mixed-mode
  scores.
- The selected mode persists locally on the device.
- The probability panel is explicitly an equilibrium reference in both modes;
  it does not pretend that Basic AI uses those probabilities.
- Every completed trace records the actual AI policy and actual distribution.
- Score results remain noisy; the post-match review judges the player's bids
  against the exact equilibrium support as an additional learning signal.

## Comparable web-game patterns

The interaction changes borrow only general patterns from current public game
sites. Chess.com's official bot documentation exposes strength selection before
play and separates assistance such as hints, evaluation, and move feedback from
opponent strength. Its coach mode also gives move-by-move feedback and a clear
restart/undo toolset. CardGames.io prominently offers an immediate new-game
action and can run without user accounts. AIP therefore keeps difficulty,
assistance/reference information, and restart as separate controls while
retaining refresh-safe, account-free local sessions.

References:

- https://support.chess.com/en/articles/8614091-how-can-i-play-against-the-chess-com-bots
- https://support.chess.com/en/articles/10877257-how-do-i-play-against-the-coach
- https://cardgames.io/

