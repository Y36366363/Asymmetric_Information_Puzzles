# AIP stability audit — 2026-08-06

## Scope

- Full Python and public-browser regression suites.
- Ten repeated public-engine runs covering complete single-player decision loops.
- Complete 15×15 Battleship match driven by the probability adviser.
- All ten playable games entered and returned to the lobby in one browser session.
- English/Chinese switching during an unfinished guess and 390×844 responsive checks.

## Risks found and fixed

1. **Unbounded temporary sessions** — Both the Python service and public worker now retain at most 256 sessions, refresh active games, and evict the least-recently-used. Shared Mastermind code worlds avoid rebuilding 5,040 arrays for every session. The site still stores no durable player data.
2. **Unavailable browser storage** — Language and first-play rule preferences now use guarded reads/writes, so privacy settings or storage failures cannot prevent the lobby from starting.
3. **Stale asynchronous navigation** — Returning to the lobby aborts an unfinished create/action request. A late response can no longer reopen or redraw a game the player already left.
4. **Overlapping notifications** — A newer toast cancels the older hide timer, preventing an earlier message from hiding the current one.
5. **Opaque connection failures** — Network, invalid-response, and expired-session errors now receive plain bilingual messages.
6. **Rules modal lifecycle** — Returning to the lobby also closes any open rules panel.

## Verification result

- Python: 107 tests passed.
- Web: 10 tests passed.
- Repeated public engine: 10 consecutive rounds passed.
- Browser: all ten game entry/return paths passed; active input survived two language switches; no 390px page overflow; no console warning/error.
