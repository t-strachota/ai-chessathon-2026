# Friedrich

Friedrich is the checkpoint that extends Ethan's real-game draw awareness throughout
the hypothetical alpha-beta and quiescence search trees. The root `agent.py` and this
saved `agent.py` were byte-for-byte identical when Friedrich was created.

Friedrich remains a readable classical chess-search agent. It does not use a neural
network or learn during games.

## Difference from Ethan

### Search-tree repetition awareness

Ethan recognizes a claimable repetition only when evaluating an immediate root move.
Friedrich carries an exact position-count map down every hypothetical search line.
Position identity includes piece placement, side to move, castling rights, and any
legally relevant en-passant square, while excluding the halfmove and fullmove counters.

A third occurrence scores as a draw at any normal-search or quiescence node. A second
occurrence receives a modest 25-centipawn penalty only when Friedrich is ahead. Losing
or neutral positions remain unpenalized, allowing the agent to preserve repetition as
a defensive resource.

Hypothetical counts are undone in `finally` blocks after every searched move. They
therefore cannot leak between sibling variations or contaminate the real game history,
including when a search times out.

Everything else remains Ethan's design: root-alpha pruning, piece-square evaluation, a
single bounded check extension, material and mobility evaluation, passed-pawn and
king-safety scoring, quiescence search, capture-first ordering, and a maximum thinking
time of 3,000 ms.

## Focused verification

- Repetition identity ignores FEN move counters and legally irrelevant en-passant
  squares.
- Third occurrences score as draws in normal and quiescence search.
- A winning side avoids a manufactured third repetition.
- A losing side retains the same repetition as a defensive draw.
- Search restores both the board and hypothetical counts after a timeout.
- Fixed-depth scores match Ethan when no repetition occurs in the searched line.
- All four preserved tactical regression positions continue to pass.
- Ruff, strict mypy, and the repository safety games pass.

A replay of Ethan's four claimable draws from a 25-game Dylan match showed the intended
behavior. Friedrich preserved Ethan's draw while nine points behind, while avoiding
Ethan's three draws from positions where it was ahead by five, six, and thirteen points
of material.

## Benchmark against Ethan

### Fast development clock: 10,000 ms plus 100 ms per move

Over ten color-alternating games, Friedrich scored:

```text
5 wins, 0 draws, 5 losses
50.0% chess score
```

All ten games ended by checkmate, and White won every game, indicating a strong
color/opening bias in that sample.

### Official clock: 120,000 ms plus 500 ms per move

Over 20 color-alternating games, Friedrich scored:

```text
4 wins, 15 draws, 1 loss
57.5% chess score
```

Five games ended by checkmate, eight by threefold repetition, and seven by the
fifty-move rule. Friedrich scored 60% as White and 55% as Black.

## Benchmark against Dylan

At the official clock, Friedrich scored:

```text
11 wins, 9 draws, 5 losses
62.0% chess score over 25 games
```

The terminations were 15 checkmates, six threefold repetitions, two fifty-move draws,
one adjudication, and one insufficient-material draw. The final game exposed a known
endgame-conversion weakness: Friedrich reached queen, rook, and pawn against a bare king
but shuffled until the fifty-move rule instead of forcing mate.

## Testing against Friedrich

After the root agent diverges from Friedrich, use:

```bash
v-env/bin/python -u -m harness.arena \
    --agent . \
    --opponent past_models/Friedrich \
    --games 20 \
    --base-ms 10000 \
    --increment-ms 100
```

Follow a promising fast result with official-clock games. Keep Friedrich frozen while
developing the next improvement. The submission packager does not include
`past_models/`.

## Known limitations

- Endgame evaluation does not explicitly reward activating the friendly king or
  confining a bare enemy king.
- Fifty-move detection recognizes an established draw but does not model the referee's
  earlier claimable-draw boundary or reward resetting the halfmove clock while ahead.
- Repetition avoidance can turn an immediate repetition into a later fifty-move draw
  without improving endgame conversion.
- Quiescence excludes ordinary quiet checks, and only one normal-search check extension
  is available per line.
- There is no transposition table, killer-move heuristic, or history heuristic.
