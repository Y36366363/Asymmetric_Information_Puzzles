# Single-round E-Card: exact matrix versus CFR — 2026-09-10

## Frozen game

Each player holds four Citizens and one role card. One seat is Emperor and the
other is Slave. Emperor beats Citizen, Citizen beats Slave, and Slave beats
Emperor. A duel with equal cards draws and play continues; the first non-draw
ends the round. An Emperor win is worth 1 point and a Slave win is worth 5.

For this audit both players choose, without observing the other choice, which of
five duels will contain their role card. This is strategically equivalent to the
sequential card interface: before a role card appears, the only public observation
is another Citizen/Citizen draw, so a behavioral hazard policy induces exactly a
distribution over the five possible timings.

## Exact sequence-form/matrix solution

The pure-strategy payoff matrix for the Emperor seat is

`A[i,j] = -5` when `i == j`, otherwise `A[i,j] = +1`.

Because each player has one hidden decision and no later private observation, the
sequence-form realization plans collapse to the mixed strategies of this 5×5
matrix. Exact rational-arithmetic vertex enumeration returns:

- Emperor timing: `(1/5, 1/5, 1/5, 1/5, 1/5)`;
- Slave timing: `(1/5, 1/5, 1/5, 1/5, 1/5)`;
- Emperor value: `-1/5` point per round;
- Slave value: `+1/5` point per round;
- exploitability: exactly `0`.

The value is asymmetric because matching timings gives the Slave a five-point
win, whereas every mismatch gives the Emperor only one point. Uniform timing
makes every pure deviation indifferent.

## CFR cross-check

The shared trainer models the Emperor's commitment first and hides it from the
Slave information set. There are exactly two information sets with five actions
each. At 10,000 vanilla alternating-CFR iterations:

- exploitability (half NashConv): `0.005256727`;
- Emperor profile value: `-0.199999871` versus the exact `-0.2`;
- maximum average-positive-regret diagnostic: `0.054623204`;
- Emperor distribution: approximately
  `(0.199991, 0.200002, 0.200002, 0.200002, 0.200002)`;
- Slave distribution: approximately
  `(0.201835, 0.200836, 0.199970, 0.199109, 0.198250)`.

The CFR profile passes a deliberately labelled cross-check gate of ε=`0.006`.
It does not replace the exact solution. A 100,000-iteration diagnostic reduced
exploitability only to about `0.001691`, illustrating why vanilla CFR is the wrong
primary solver when a tiny exact matrix is available. CFR+ or discounted CFR would
be useful performance comparisons, but cannot improve on the exact certificate.

## Relationship to the local game

The first fresh round already commits the AI timing uniformly, so its isolated
single-round policy agrees with the exact equilibrium. The existing local mode
then learns from the player's public timings across rounds and deliberately moves
away from uniform play. That repeated adaptive opponent remains correctly labelled
`strong_heuristic`; this single-round proof must not be presented as a proof of the
whole repeated match.

An exact mode can later disable cross-round adaptation and sample the uniform
distribution for both role assignments. No serialized policy artifact is needed:
the exact strategy is five rational probabilities and should be generated from the
matrix solver or asserted directly against it.

## Implications for related games

- **Hidden timing/inspection games:** first check whether all behavioral policies
  reduce to a distribution over stopping times. If so, a compact matrix or
  sequence-form LP may be exact and simpler than CFR.
- **Kuhn Poker and reduced Liar's Dice:** multiple information sets make CFR a
  meaningful implementation comparator, although exact sequence form remains a
  valuable oracle for small variants.
- **Love Letter:** new private cards can arrive after earlier actions, so timing
  reduction fails. It needs a complete extensive-form model and full traversal or
  correctly importance-weighted external-sampling MCCFR.
- **Repeated adaptive E-Card:** once utilities depend on learned history, the state
  must include that history and the problem is no longer the isolated 5×5 game.
  Equilibrium claims cannot be transferred between the two scopes.
