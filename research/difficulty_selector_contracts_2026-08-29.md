# Difficulty selector contracts — 2026-08-29

## Goal

Every difficulty or learning-mode selector should answer the same three player
questions before the player clicks it:

1. **What changes?** The opponent policy, available coaching, or both.
2. **When does it take effect?** Immediately in the current state or from a new
   match.
3. **What happens to the score?** Which totals reset and which preferences or
   learning records remain.

The review found three actual difficulty/mode selectors. Battleship board size
is a rules configuration rather than an AI-strength selector and is therefore
kept outside this contract.

## Implemented matrix

| Game | What changes | Takes effect | Score handling |
| --- | --- | --- | --- |
| Blackjack | Coaching visibility and Practice-only grading | Immediately in the current hand; no redeal | Bankroll, W/L/P, and existing Practice results remain |
| Kuhn Poker | Basic exploitable policy or exact GTO opponent | Immediately by starting a fresh match | Current hand, net chips, and action history reset |
| Goofspiel | Intuitive bidding heuristic or exact equilibrium opponent | Immediately by starting a fresh match | Prize scores, bid cards, and action history reset |

The selected Blackjack mode and both AI difficulty preferences remain in local
browser preferences after refresh. That persistence is now stated alongside the
reset behavior instead of being left implicit.

## UI contract

- All three surfaces use the same labels and row order in Chinese and English.
- Each selector group references its explanation with `aria-describedby`.
- Each explanation is an `aria-live="polite"` region, so a mode change announces
  the new contract without moving keyboard focus.
- Strategy evidence remains mode-specific. The unified format does not blur the
  distinction between an exploitable heuristic and an exact equilibrium.

## Verification boundary

The existing engine rules remain unchanged. This update standardizes and tests
the explanation layer and preserves the already-audited reset behavior. It does
not add a new game, claim a new optimum, or redefine any opponent policy.

