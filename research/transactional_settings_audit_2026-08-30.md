# Transactional settings audit — 2026-08-30

## Finding

Kuhn Poker and Goofspiel previously changed their in-memory mode and persistent
browser preference before the replacement session had been created. If the
request failed, the visible match stayed on the old opponent while a later page
refresh silently loaded the requested opponent. The selector, current match,
and saved preference could therefore describe three different states.

## Updated contract

Opponent difficulty is now committed transactionally:

1. The click requests a new session using the proposed mode.
2. All difficulty controls are disabled while that request is pending.
3. Only a successful response updates the selected mode and saved preference.
4. A failed request keeps the current opponent and saved preference, restores
   the controls, and displays the existing connection error message.

Blackjack Normal/Practice switching remains immediate because it does not create
a remote session or reset the hand. Its selected preference can therefore be
committed synchronously.

## Accessibility and responsive behavior

- The three mode groups now have localized Chinese and English accessible names.
- Mode buttons share one `difficulty-control` state and visibly indicate that a
  session transition is pending.
- The existing three-row contract remains linked through `aria-describedby`.
- At a 390 × 844 viewport the page width and document scroll width were both
  390 pixels; the Blackjack contract measured 304 pixels and did not overflow.

## Verification

- Successful Kuhn mode change reset a non-zero match score to zero, returned to
  hand one, and selected Advanced GTO.
- Successful Goofspiel mode change returned to a fresh four-card match and
  selected Advanced equilibrium.
- Blackjack Practice switching preserved the round, cards, and bankroll.
- With the local service deliberately stopped, a Kuhn Advanced → Basic attempt
  retained Advanced on screen, re-enabled the controls, and reported the
  connection failure. After restart and refresh, Advanced remained selected.
- The browser warning/error log remained empty after the recovered reload.

No game policy, payoff, optimality claim, or benchmark environment changed.

