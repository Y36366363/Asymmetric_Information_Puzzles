# Contract consistency audit — 2026-08-22

## Scope

This update applies earlier player-testing lessons across the project without
adding a game or spending on another model run. The audit asks whether the
actions displayed to a player are exactly the actions accepted by the game
engine, and whether a stored benchmark trace can be trusted as a semantically
consistent replay record rather than merely well-shaped JSON.

## Public-game action contract

Every public state includes `legalActions`, but the action API previously passed
requests directly to each session's `act()` implementation. Most sessions
rejected undeclared actions locally, while a few lifecycle methods accepted
restart actions even when the current snapshot did not advertise them. That made
the visible contract advisory rather than authoritative.

The shared boundary now validates the current snapshot and rejects any action
not present in `legalActions` before calling the game session. The same helper is
used by the server worker and the zero-backend browser adapter, preventing the
public deployment and worker build from drifting apart.

A table-driven regression test creates all 15 playable games and confirms that
an undeclared action receives a 400 response. A targeted investment test also
checks the previously accepted hidden `new_game` shortcut during the decision
phase. Existing full decision-loop tests still verify that declared actions
remain usable through terminal states.

## Benchmark transition contract

`run_episode` now calls the common `validate_decision` function before an
adapter can mutate its state. This makes legality enforcement a runner property,
not an optional convention that every environment adapter must remember.

Loaded `EpisodeTrace` objects now additionally require:

- nonempty environment, episode, and agent identifiers;
- every step to use the trace's environment and episode identifiers;
- contiguous step numbers beginning at zero; and
- every recorded decision to be legal for its recorded input and payload schema.

Corruption tests cover mismatched environments and undeclared recorded actions.
Another test proves an illegal live agent action is rejected while the adapter
remains at step zero.

## Test-discovered loader defect

The new direct round-trip test found that `read_json()` worked but
`EpisodeTrace.from_dict(trace.as_dict())` did not: dataclass tuples remain tuples
in an in-memory dictionary, while a JSON round trip converts them to arrays.
The loader now accepts list and tuple representations for schema sequences while
continuing to reject unrelated types. This was a genuine defect exposed by the
new test, not a speculative refactor.

All 16 stored completion traces were loaded, semantically validated, converted
back through `as_dict()`, and reconstructed again without another API call.

## Verification

- 196 Python tests pass, including the localhost health check.
- 12 worker/static-browser tests pass.
- All 15 playable games reject actions outside their declared legal set.
- All 16 historical completion traces pass semantic validation and round-trip.
- Both deployable web builds were regenerated from the shared engine.

No performance, equilibrium, optimality, or cross-game transfer claim changes in
this update. It is a contract-hardening result only.
