# Kuhn Poker AI audit — 2026-08-15

The playable game uses the standard two-player, three-card Kuhn model: both
players ante one chip, one bet of one chip is allowed, and cards rank
`K > Q > J`. First position alternates between hands.

## Finding and correction

The previous AI used the familiar `1/3` frequency for every queen call. That
merged two different information sets. When the AI is second and faces an
opening bet, Q calls with probability `1/3`. When the AI is first, checks, and
then faces a bet, Q must call with probability `2/3` for the selected
`alpha = 1/3` equilibrium.

An exhaustive evaluator enumerates all 64 deterministic responses available
to a player in each seat and computes their exact rational expected payoff.

| Opponent policy | Best response as first | Best response as second | Maximum exploitability |
| --- | ---: | ---: | ---: |
| Previous shared-`1/3` policy | `-1/18` | `+1/6` | `1/9` per hand |
| Corrected position-aware policy | `-1/18` | `+1/18` | `0` |

The equilibrium game value is `-1/18` chips for first position and `+1/18`
for second position. The corrected policy reaches those values against every
best response, so it is non-exploitable within the implemented rules.

## Exact policy used

- First player opens with J at `1/3`, Q at `0`, and K at `1`.
- First player, after checking and facing a bet, calls with J at `0`, Q at
  `2/3`, and K at `1`.
- Second player, after a check, bets J at `1/3`, Q at `0`, and K at `1`.
- Second player facing an opening bet calls J at `0`, Q at `1/3`, and K at `1`.

This is exact only for the declared three-card, one-bet, risk-neutral zero-sum
model. Stack constraints, larger decks, rake, alternate bet sizes, or human
utility preferences require a different strategy.
