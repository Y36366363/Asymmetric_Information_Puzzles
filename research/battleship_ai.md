# Battleship AI research and implementation baseline

Battleship is the recommended next solo game for AIP. It is widely recognized,
has a clear click-per-turn loop, and turns every miss, hit, and sunk ship into a
public observation that shrinks the opponent-fleet information set.

## Proposed player loop

1. Place a standard fleet on a 10×10 board, manually or with one-click random placement.
2. Click one unknown enemy cell per turn and receive `miss`, `hit`, or `sunk` feedback.
3. The AI fires on the player's hidden board using the selected difficulty policy.
4. Win by sinking all five opposing ships before the AI sinks yours.
5. After the match, reveal both heat maps and explain which observations changed each decision.

The implemented deployment now offers three scales: standard 10×10 with five
ships, expanded 12×12 with six ships, and grand 15×15 with seven ships. Each ship
has a stable color and a collision-safe 90° rotation control. Because a straight,
undirected ship occupies identical cells after a 180° flip, horizontal/vertical
rotation is the meaningful transformation and both orientations are included in
the AI candidate enumeration.

This has more repeated decisions than Mastermind or the pirate vote, while remaining
easy to explain to a new player. It also offers visual tension without requiring a
multiplayer server.

## AI evolution plan

- **Level 0 — Random:** uniform shots over every untried cell. This is the sanity baseline.
- **Level 1 — Hunt/target:** checkerboard search until a hit, then inspect adjacent cells.
- **Level 2 — Probability density:** enumerate every still-legal placement of every
  unsunk ship and fire at a cell covered by the largest number of candidate worlds.
- **Later adaptive level:** learn a player's placement bias across local matches, but
  cap the learned component so the AI does not confuse exploitation with privileged information.

The local simulator uses paired board seeds for fair policy comparisons. The first
solo implementation is now registered in both the Python service and zero-backend
browser runtime. It uses probability-density targeting, while this document remains
the calibration baseline for later difficulty and multiplayer work.

## Initial 1,000-game benchmark

| AI policy | Mean shots | Median | 90th percentile | Best–worst |
| --- | ---: | ---: | ---: | ---: |
| Random | 95.355 | 97 | 100 | 71–100 |
| Hunt/target | 55.872 | 57 | 66 | 29–73 |
| Probability density | 46.119 | 45.5 | 59 | 24–71 |

All three policies played the same 1,000 seeded hidden fleets. Hunt/target used
41.4% fewer shots than random on average; probability density used another 17.5%
fewer shots than hunt/target. The remaining long-tail games show why the future
hard AI should keep explaining uncertainty instead of presenting itself as infallible.

## Next integration gates

- Use the 1,000-game baseline to calibrate easy, normal, and hard match pacing.
- Add manual drag/rotate placement on top of the current safe random-placement flow.
- Add easy and normal policies alongside the current probability-density opponent.
- Extract player identity and turn transport so a later two-player room can reuse the
  same board state without exposing either private fleet.

## Cluster-consistent targeting update (2026-08-14)

The density scorer now requires a candidate ship placement to explain an entire
connected straight cluster of unresolved hits on 10×10 and 12×12 boards. This
removes perpendicular false leads after consecutive hits. A paired 300-board
audit lowered 10×10 P90 from 58 to 56 and improved 12×12 mean shots from 65.51
to 63.64 with P90 improving from 85 to 84. The 15×15 board keeps the legacy
focus rule because the first unrestricted prototype worsened its tail; this
board-size gate makes the upgrade evidence-based rather than uniform by fiat.

The policy remains a one-step heuristic over individual ship placements. It is
not a complete-fleet Bayesian posterior or a proof of minimum expected shots.
See [the cross-game strategy audit](strategy_audit_2026-08-14.md) for the exact
benchmark and optimality terminology used throughout AIP.
