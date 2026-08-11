# AIP user-journey and stability audit — 2026-08-12

## Scope

This pass focused on the shared shell around all twelve playable games rather
than changing one game's strategy model. It covered local-server startup,
backend and browser-engine parity, lobby-to-game navigation, keyboard rule
help, static-public rebuilding, malformed inputs, bounded sessions, and full
single-player decision loops.

## User-facing findings and changes

1. The lobby behaved like a single-page app visually, but it had no addressable
   routes. Browser Back could leave AIP instead of returning to the lobby, and a
   game could not be represented by a stable URL. The shell now uses `#lobby`
   and `#game/<game-id>`, validates route targets against the registry, and
   restores the existing game view when possible.
2. The rules modal was readable with a pointer but did not take or contain
   keyboard focus. It now focuses Close on entry, traps Tab/Shift+Tab, supports
   Escape, and returns focus to a visible Rules control when the original opener
   has become hidden.
3. The duplicated local/public UI remains generated from one source: the
   zero-backend `docs/` mirror was rebuilt after the shared app change, including
   fresh cache-busting hashes.

## Verification

- Python: 126 tests passed, including API validation, every registered solver,
  complete game loops, session eviction, hidden-information boundaries, and the
  temporary local health server.
- Web: 10 tests passed under Node, including complete public-engine loops for all
  single-player games, 10×10/12×12/15×15 Battleship, static boot order, bounded
  sessions, malformed actions, and route/focus wiring.
- Browser: loaded the local lobby at `127.0.0.1:8765`, confirmed twelve playable
  cards in difficulty order, entered Pirate Council at `#game/pirates`, verified
  the complete English rulebook and active Close focus, and observed no warning
  or error output during the checked flow.

## Strategy-model status

No payoff, belief-update, or opponent-policy formula changed in this pass. That
is intentional: the engine tests still compare full decision loops across the
Python service and zero-backend browser runtime, so navigation improvements do
not silently alter AI behavior. A later research pass can therefore benchmark a
new game or policy against the same stable session boundary.
