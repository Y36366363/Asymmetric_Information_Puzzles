# E-Card: from a one-shot reveal to a learnable timing match

## The design problem

E-Card is inherently a simultaneous hidden-choice game. A single isolated round
can therefore feel like a coin flip: there is little evidence from which a
player can form a model of the opponent. Pretending that every puzzle needs a
long-lived, human-like opponent would be misleading, but a repeated card match
can honestly make timing a strategic object.

## Implemented interaction contract

At the beginning of every round, the AI samples and commits to the duel in
which it will use its special card. It cannot react to the player's current
card. The committed slot is hidden until the round ends. Before each choice,
the interface shows the *conditional* probability of that slot being now,
derived from a public timing policy and the already revealed citizen duels.

After a round, both special-card timings are retained as public history. In
later rounds the AI uses only the player's timing history in the same role:

- as Slave it gives extra weight to the player's frequently used Emperor slot;
- as Emperor it gives extra weight to slots the player has used least often for
  Slave.

This creates a compact loop: establish a pattern, detect the adjustment, then
break or exploit it. The interface audits the commitment after settlement, so
the player can distinguish a precommitted loss from an apparently reactive AI.

## Evidence boundary

This policy is marked `strong_heuristic`, not `equilibrium_backed` or
`proved_optimality`. The five-card repeated timing game has not been solved
here, and the displayed probabilities are a transparent opponent model rather
than a claim of GTO. The initial round deliberately remains uncertain; the
skill comes from using the public record across later rounds.

## A platform rule for engagement

Use two honest product types instead of forcing every environment into the
same kind of entertainment:

| Type | Suitable environments | What makes the next action meaningful |
| --- | --- | --- |
| Repeated strategic match | E-Card, Kuhn Poker, Goofspiel, Liar's Dice, constrained RPS | Observable policy, counterplay, score history, and a post-round audit |
| Puzzle laboratory | Pirates, Worm, Hats-style logic | A verifiable invariant, parameter variation, and explanation—not invented AI psychology |

For future changes, an interactive game should pass four checks: a decision
changes a later state or model; the player sees feedback that explains that
change; a player can counter the opponent's adaptation; and the end screen
states what information was hidden and what was learned. If a one-shot puzzle
cannot satisfy those checks, it should remain clearly labelled as a puzzle lab.
