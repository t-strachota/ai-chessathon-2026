# Ethan

Ethan is the checkpoint that added root-alpha pruning, piece-square evaluation, and a
bounded check extension to Dylan. The root `agent.py` and this saved `agent.py` were
byte-for-byte identical when Ethan was created.

Ethan remains a readable classical chess-search agent. It does not use a neural network
or learn during games.

## Difference from Dylan

### Root-alpha pruning

Dylan searched every root candidate with a fresh full alpha-beta window. Ethan carries
the best proven root score forward as alpha while searching later candidates. Inferior
moves can therefore be rejected earlier.

Ethan retains the first proven best move because a value returned after a narrow-window
cutoff may be a bound rather than an exact equal score. Its emergency legal fallback is
still randomized.

Principal-variation carry was tested separately and rejected. Ethan does **not** move
the previous iterative-deepening pass's best move to the front of the next pass.

### Piece-square tables

Ethan adds side-relative tables for pawns, knights, bishops, rooks, and queens. They
encourage useful placement such as central knights, developed bishops, active rooks,
and advanced pawns. Their centipawn values are deliberately modest so placement cannot
outweigh a pawn of material.

Black's table lookup mirrors ranks relative to Black's side. The king remains governed
by Dylan's king-safety evaluation rather than a fixed table that would discourage king
activity in endgames.

### Bounded check extension

When a normal-search move gives check, Ethan may search that line one ply deeper. Only
one check extension is permitted per line, preventing repeated checks from expanding
the tree without bound. The extension shares the existing deadline, and quiescence
remains capped at four plies.

Everything else remains Dylan's design: material and mobility evaluation, passed-pawn
and king-safety scoring, real-game repetition awareness, iterative alpha-beta search,
quiescence through captures and promotions, capture-first ordering, and a maximum
thinking-time allowance of 3,000 ms.

## Focused verification

- Every piece-square table contains eight ranks of eight files.
- The initial position has a symmetric piece-square score.
- A central knight scores above a knight on the edge.
- Mirrored White and Black placements cancel correctly.
- Checking moves receive at most one additional normal-search ply.
- Search restores the board after completion and timeout.
- All four preserved rated-position tactical blunders remain rejected.
- Ruff, strict mypy, and the repository safety gate pass.

## Benchmark against Dylan

### Fast development clock: 10,000 ms plus 100 ms per move

Over six color-alternating games, Ethan scored:

```text
6 wins, 0 draws, 0 losses
100.0% chess score
```

All six games ended by checkmate.

### Official clock: 120,000 ms plus 500 ms per move

The first two games split one win and one loss. An eight-game follow-up scored three
wins, four draws, and one loss. Combined:

```text
4 wins, 4 draws, 2 losses
60.0% chess score over 10 games
6 checkmates, 4 threefold repetitions
```

Neither benchmark contained a crash, illegal move, or flag loss.

## Testing against Ethan

After the root agent diverges from Ethan, use:

```bash
v-env/bin/python -u -m harness.arena \
    --agent . \
    --opponent past_models/Ethan \
    --games 20 \
    --base-ms 10000 \
    --increment-ms 100
```

Follow a promising fast result with official-clock games. Keep Ethan frozen while
developing the next improvement. The submission packager does not include
`past_models/`.

## Known limitations

- Piece-square values are hand-tuned and not game-phase aware.
- Repetition is recognized from real game history at the root, not throughout every
  hypothetical search line.
- Quiescence excludes ordinary quiet checks; normal search allows only one check
  extension per line.
- There is no transposition table, killer-move heuristic, or history heuristic.
- Broader pawn structure, bishop-pair value, open-file rooks, and space are not scored.
