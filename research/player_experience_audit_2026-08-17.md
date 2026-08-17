# Player-experience and stability audit — 2026-08-17

## Scope

The audit traversed every one of the 15 playable lobby entries in the public
zero-backend build, checking route-to-view consistency, visible headings,
rules, restart and lobby controls, blank or permanently busy states, duplicate
DOM identifiers, unnamed controls, missing bilingual strings, runtime warnings,
and horizontal overflow at 390 px. Complete engine decision loops were also
rerun in Python and JavaScript.

## Fixed findings

### Protected Love Letter target

The Love Letter engine correctly forbids a Prince from targeting an opponent
who is protected by the Handmaid. The interface, however, left the protected AI
selected in the target menu. A player holding the Prince could therefore click
a visibly legal card and receive an illegal-action error.

The target menu now disables the protected AI and automatically selects the
player, the only legal Prince target. A deterministic seed test reproduces the
edge case and protects both the rule and the suggested action.

### Mixed-strategy wording

Goofspiel previously highlighted the largest component of a mixed equilibrium
as a generic “recommendation.” That wording could teach players to repeat one
card, which is not the equilibrium. It now labels that card as the
highest-frequency action and explicitly says to randomize using the displayed
distribution. The continuation value is described as the additional score
difference from the remaining rounds, rather than an ambiguous final score.

### Mobile and keyboard controls

At 390 px the detail-page lobby button was only 37 px high. The lobby button,
brand/home control, GitHub link, and language buttons now expose at least a
44 px touch target without creating horizontal overflow. Native select controls
also receive the same visible keyboard focus treatment as links, buttons, and
text inputs.

## Verification result

- All 15 playable routes resolve to the matching visible game view.
- Every detail page has visible rules, restart, and return-to-lobby controls.
- No missing Chinese or English translation keys were rendered.
- No duplicate IDs, unnamed controls, permanently busy pages, console warnings,
  or console errors were found.
- No tested game produced document-level horizontal overflow at 390 px.
- All 164 Python tests and 10 public-engine/build tests pass.

## Best next optimizations

1. **Hard-game guided first turn:** Liar's Dice, Love Letter, Goofspiel, and the
   worm puzzle would benefit from a dismissible first-turn callout pointing to
   the exact control to use, beyond the existing full rules modal.
2. **Post-match learning summary:** Goofspiel can compare the player's empirical
   bids with the equilibrium distribution, while Restricted RPS can show where
   repeated patterns became exploitable.
3. **Large-board Battleship pacing:** the 15×15 mode remains deliberately
   heavier. Its next improvement should be measured animation/pacing and cached
   probability presentation, not a weaker search policy.
4. **Manor Mystery product gate:** keep it local until accusation risk, opponent
   turns, and a readable notebook are implemented; its solver is ahead of its
   player experience.
