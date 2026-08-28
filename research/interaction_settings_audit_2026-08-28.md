# Interaction and settings audit — 2026-08-28

## Scope

This review treated a setting as a promise about what the player will see, what
state will reset, and what evidence will be recorded. It covered the language
switch, Blackjack Normal/Practice mode, Kuhn Poker Basic/Advanced mode,
Goofspiel Basic/Advanced mode, Battleship board size, and the Moving Worm's
optional hint/answer disclosure.

## Settings contract

| Setting | Takes effect | Resets play? | Persists on refresh? | Review result |
| --- | --- | --- | --- | --- |
| Language | Immediately | No | Yes | Clear; now exposes pressed state |
| Blackjack mode | Immediately | No | Yes | Repaired; modes now isolate feedback and scores |
| Kuhn Poker AI | Next fresh match | Yes | Yes | Appropriate because opponent policy changes |
| Goofspiel AI | Next fresh match | Yes | Yes | Appropriate because opponent policy changes |
| Battleship size | Placement phase | Rebuilds fleet | No | Appropriate; unavailable once battle starts |
| Worm help | Immediately | No | No | Appropriate; disclosure is local to the attempt |

## Repaired defect

Blackjack previously used one cumulative `strategyAccuracy` value for every
human action and AI demonstration. As a result, a decision made in Normal mode
could appear later as a Practice-mode grade, and the UI could expose the correct
action simply by switching modes. This violated the advertised learning flow.

The engine now keeps the research-facing all-decision metric and adds a separate
Practice-only metric. Each action records `practiceAssessed`; only a human action
submitted while Practice mode is active changes `practiceAccuracy`. Normal-mode
actions are never graded retrospectively, and AI demonstrations do not inflate
the player's score. The UI sends the mode with the action, reveals the correct
play only after an assessed decision, and hides per-action audit text otherwise.

## Accessibility and comprehension

- Language and Blackjack mode controls now expose `aria-pressed`, so the visible
  selection is also machine-readable.
- A bilingual sentence directly below the Blackjack selector explains whether
  answers and grading are hidden, whether the AI button is a demonstration, and
  whether switching redeals.
- The mode change intentionally keeps the current hand. Changing an opponent's
  actual policy in Kuhn Poker or Goofspiel still starts a fresh match, avoiding a
  mixed-policy score.

## Verification

- 209 Python tests pass, including separate Normal, Practice, and AI-action
  accounting.
- 12 public Worker/static-build tests pass against the regenerated zero-backend
  site.
- A real browser path confirmed: Normal action → no answer and `—`; switch to
  Practice → no retrospective grade; Practice action → correct-play review and
  a Practice-only 100% score. The language and mode pressed states were present,
  and the browser produced no warning or error logs.

## Next interaction priorities

These are deliberately not new-game work:

1. Standardize the explanatory sentence beneath every consequential difficulty
   selector: what changes, when it changes, and whether score/state resets.
2. Add a compact settings summary to each game's rules dialog, sourced from the
   same rule metadata as the engine to prevent copy drift.
3. Only introduce a cross-game global settings panel after at least three truly
   global preferences exist; today language is the only one, so a panel would add
   navigation cost without enough value.

