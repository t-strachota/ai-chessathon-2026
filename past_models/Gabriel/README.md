# Gabriel

Gabriel preserves the endgame-conversion and passed-pawn candidate developed after
Friedrich. Its agent.py is byte-for-byte identical to the root agent at checkpoint
creation. Friedrich remains unchanged as the earlier benchmark.

## Changes from Friedrich

- Fifty-move detection includes claimable draws at halfmove 99 when a qualifying
  legal move exists, matching the local referee's claim behavior.
- With a material imbalance of at least 500 centipawns, each halfmove beyond 40
  subtracts four centipawns from the leading side's evaluation and adds the same
  amount from the trailing side's perspective.
- Against a bare king, a side with a rook or queen receives bonuses for bringing
  its king closer, driving the enemy king toward the edge, and restricting its
  estimated escape squares. Checking moves are prioritized in these endings.
- Passed-pawn bonuses by side-relative rank index are now
  (0, 0, 10, 25, 60, 180, 500, 0), including 180 on the sixth rank and 500 on the seventh.
- Quiet passed-pawn advances onto the sixth or seventh rank enter bounded quiescence.
- One passed-pawn extension is available per normal search line in addition to the
  existing check-extension allowance. A move triggering both adds only one ply.
- Move ordering prioritizes promotions and captures of advanced enemy passers;
  ordinary positions retain a faster ordering path.

Repetition-aware search, iterative deepening, the existing time budget, and the
general material, mobility, piece-square, and king-safety evaluation remain in use.
No transposition table or adaptive time-allocation experiment is included.

## Benchmark against Friedrich

The final candidate produced the following results at the reported 120,000 ms base
plus 500 ms increment:

| Test | Wins | Draws | Losses | Score |
| --- | ---: | ---: | ---: | ---: |
| Test 1, user-provided arena output | 13 | 3 | 4 | 72.5% |
| Test 2, analyzed 25-game PGN | 16 | 1 | 8 | 66.0% |
| Combined | 29 | 4 | 12 | 68.9% |

Test 2 contained 24 checkmates and one fifty-move draw, with no technical failures
or adjudications. The draw came while Gabriel was six material points behind.
Gabriel promoted in 14 of its 16 wins; Friedrich promoted in four of Gabriel's
eight losses and in two Gabriel wins.

Test 2's color split was 12 wins from 12 games as Black, but four wins, one draw,
and eight losses as White (34.6%). Only 15 complete move sequences were unique.
These are encouraging local results, not an independent estimate of general
playing strength. Varied starting positions with reversed colors remain needed.

The earlier endgame-only candidate scored 51 wins, 25 draws, and 49 losses over
125 games (50.8%). Those games are not pooled with Gabriel's final 45-game sample.

## Verification and next investigation

The final candidate previously passed Ruff, strict mypy, a mating regression,
two safety wins over Random, and a six-game fast Friedrich smoke match
(three wins and three losses, every game won by Black).

Investigate whether large passer bonuses encourage unsound exchange sacrifices.
In Test 2 games 17 and 19, 29.R7xe6 fxe6 30.dxe6 created an advanced pawn after
trading a rook for a bishop; the pawn later fell and Gabriel lost. This is a
regression candidate, not proof that this sacrifice alone caused the loss.
Passed-pawn scoring does not yet account for protection, blockade, or safe
promotion time. King escape counting is a heuristic rather than an exact legal
king-move count.

## Testing against Gabriel

Keep this checkpoint frozen while developing the root agent:

```bash
v-env/bin/python -m harness.arena \
  --agent . \
  --opponent past_models/Gabriel \
  --games 20 \
  --base-ms 120000 \
  --increment-ms 500
```
