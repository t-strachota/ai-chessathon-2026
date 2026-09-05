# Dylan

Dylan is the checkpoint that added repetition awareness, passed-pawn evaluation, and
king-safety evaluation to Charlie. The root `agent.py` and this saved `agent.py` were
byte-for-byte identical when Dylan was created.

Dylan remains a classical chess-search agent. It does not use a neural network or learn
during games.

## Difference from Charlie

### Repetition and draw awareness

Dylan records positions reached during the real game in module state. Position identity
includes piece placement, side to move, castling rights, and any legally relevant
en-passant square, while ignoring the move counters.

A root move that immediately creates a claimable third repetition or fifty-move draw is
scored as `0`. This makes Dylan avoid the draw when another move retains a positive
evaluation, while still accepting a draw instead of a losing continuation. When a draw
and a non-drawing move have equal scores, Dylan prefers the non-drawing move.

### Passed pawns

Dylan recognizes a passed pawn when no opposing pawn remains ahead of it on the same or
an adjacent file. Its bonus grows as it approaches promotion:

```text
Advancement:  0   1   2   3   4   5    6   7
Bonus:        0   0  10  20  40  80  160   0
```

The masks used to detect passed pawns are built once at import time.

### King safety

Dylan rewards friendly pawns shielding the three squares in front of the king and
penalizes squares around the king that are attacked by the opponent. King danger is
weighted most heavily while the opponent has a queen, less heavily with rooks only, and
disabled after both queens and rooks are gone so the king is not discouraged from
becoming active in a minor-piece ending.

Everything else remains Charlie's design: material and mobility evaluation, iterative
alpha-beta search, quiescence search through captures and promotions, capture-first
move ordering, random tie-breaking, and a maximum thinking-time allowance of 3,000 ms.

## Focused verification

- Repetition identity ignores only the irrelevant FEN move counters.
- A winning side avoided a manufactured third repetition.
- A losing side accepted the same repetition as a draw.
- `get_move` recorded the position before and after its selected move.
- Passed-pawn detection distinguished a true passer from a pawn blocked by an adjacent
  enemy pawn.
- A shielded king evaluated as safer than an exposed king.
- All four of Charlie's rated-position tactical regressions continued to pass.

On representative positions, Dylan completed the same normal search depths as Charlie
at the official three-second allowance. At the fast development clock it occasionally
lost one ply in a passed-pawn endgame because the richer evaluation costs more per leaf.

## Benchmark against Charlie

### Fast development clock: 10,000 ms plus 100 ms per move

Over 20 colour-alternating games, Dylan scored:

```text
4 wins, 13 draws, 3 losses
52.5% chess score
```

Twelve games ended by threefold repetition, one by the fifty-move rule, and seven by
checkmate.

### Official clock: 120,000 ms plus 500 ms per move

Over four colour-alternating games, Dylan scored:

```text
2 wins, 2 draws, 0 losses
75.0% chess score
```

Dylan won both games as Black and drew both games as White. Two games ended by
checkmate and two by threefold repetition. Neither benchmark contained a crash, illegal
move, or flag loss.

The official-clock sample is small, but it supports the expectation that Dylan's richer
evaluation benefits from enough time to complete the same search depths as Charlie.

## Testing against Dylan

After the root agent diverges from Dylan, use a fast arena for development:

```bash
v-env/bin/python -m harness.arena \
    --agent . \
    --opponent past_models/Dylan \
    --games 20 \
    --base-ms 10000 \
    --increment-ms 100
```

Follow promising results with two to four games at 120,000 ms plus 500 ms per move.
Keep Dylan fixed while developing the next improvement. The normal submission packager
does not include `past_models/`.

## Known limitations

- Repetition is recognized from the real game history at the root, not throughout every
  hypothetical branch of the search.
- A draw is neutral rather than receiving a separate contempt penalty.
- King safety is deliberately simple and does not explicitly remember whether a king
  has castled.
- Evaluation still lacks piece-square tables, pawn-structure terms, space, and a
  transposition table.
- Random tie-breaking increases benchmark variance.
