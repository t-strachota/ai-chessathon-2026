# Benjamin

Benjamin is a saved copy of the main candidate agent at the point when it used
alpha-beta search, improved move ordering, and dynamic search depth. It is kept here so
future versions can be tested against it.

Benjamin is a traditional chess-search program, not a machine-learning model. It does
not learn while playing and it does not use a neural network.

## How Benjamin chooses a move

1. It gives each chess piece a value: pawn 100, knight 320, bishop 330, rook 500, and
   queen 900.
2. It also rewards mobility, meaning positions where its side has more legal moves.
3. It looks ahead using minimax. Benjamin assumes that it will choose the move that is
   best for itself and that its opponent will reply with the move that is worst for
   Benjamin.
4. It uses alpha-beta pruning to skip branches that cannot change the final decision.
   This produces the same answer as a full minimax search at that depth while usually
   examining fewer positions.
5. It searches captures first. Capturing a valuable piece with a cheaper piece is tried
   before less promising captures. This is often called MVV-LVA: Most Valuable Victim,
   Least Valuable Attacker. Good ordering helps alpha-beta pruning skip more work.
6. It uses iterative deepening. It completes depth 1, then depth 2, then depth 3, and so
   on until its time budget expires. It returns the move from the deepest search that
   finished completely.

## Time management

Benjamin keeps a 100 ms safety margin, divides its remaining usable time across an
estimated 40 moves, and never deliberately spends more than 1,000 ms on one move. Its
maximum search depth is 10, although the clock normally stops it earlier.

It selects a legal fallback move before searching. If time expires during a deeper
search, it abandons that incomplete result and safely returns the last fully completed
result. `try`/`finally` blocks ensure that every move placed on the analysis board is
removed again, even when a timeout happens.

## Current limitations

- It evaluates only material, mobility, checkmate, stalemate, and insufficient material.
- It has no opening book, piece-square tables, quiescence search, or transposition table.
- When several moves receive the same score, it chooses randomly between them.
- Its time allocation is deliberately simple and assumes roughly 40 moves remain.

## Benchmark results

These benchmarks were run on 4 September 2026 using the local harness on an arm64
computer with Python 3.14.2. Each row contains 50 games: Benjamin played 25 as White
and 25 as Black. Every game began from the standard starting position.

`Score` is the chess score percentage: a win is worth 1 point, a draw is worth half a
point, and a loss is worth 0 points. It is therefore different from the win percentage.

### Normal time: 10,000 ms + 100 ms per move

This is the arena harness's default fast time control.

| Opponent | Wins | Draws | Losses | Win % | Draw % | Loss % | Score | Checkmates | Repetitions |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `baselines/random` | 46 | 4 | 0 | 92% | 8% | 0% | 96% | 46 | 4 |
| `baselines/greedy` | 49 | 1 | 0 | 98% | 2% | 0% | 99% | 49 | 1 |
| `baselines/minimax` | 19 | 26 | 5 | 38% | 52% | 10% | 64% | 24 | 26 |
| `baselines/numba` | 22 | 25 | 3 | 44% | 50% | 6% | 69% | 25 | 25 |
| `past_models/Alfred` | 17 | 25 | 8 | 34% | 50% | 16% | 59% | 25 | 25 |
| **Total** | **153** | **81** | **16** | **61.2%** | **32.4%** | **6.4%** | **77.4%** | **169** | **81** |

### Longer time: 60,000 ms + 500 ms per move

At this time control Benjamin reaches its built-in maximum allowance of 1,000 ms per
move near the start of each game. A 120-second starting clock would not increase that
maximum because `MAX_THINK_MS` is 1,000.

| Opponent | Wins | Draws | Losses | Win % | Draw % | Loss % | Score | Checkmates | Repetitions |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `baselines/random` | 49 | 1 | 0 | 98% | 2% | 0% | 99% | 49 | 1 |
| `baselines/greedy` | 48 | 2 | 0 | 96% | 4% | 0% | 98% | 48 | 2 |
| `baselines/minimax` | 40 | 9 | 1 | 80% | 18% | 2% | 89% | 41 | 9 |
| `baselines/numba` | 38 | 12 | 0 | 76% | 24% | 0% | 88% | 38 | 12 |
| `past_models/Alfred` | 43 | 7 | 0 | 86% | 14% | 0% | 93% | 43 | 7 |
| **Total** | **218** | **31** | **1** | **87.2%** | **12.4%** | **0.4%** | **93.4%** | **219** | **31** |

### Combined result

Across all 500 games, Benjamin scored **85.4%** with **371 wins, 112 draws, and 17
losses**. That is a 74.2% win rate, 22.4% draw rate, and 3.4% loss rate. There were 388
checkmates and 112 threefold-repetition draws. Benjamin had **no crashes, illegal moves,
flag losses, or other technical failures**.

The extra thinking time produced a much stronger result against minimax, numba, and
Alfred. These numbers are useful local comparisons, but they are not an Elo estimate or
a prediction of competition performance. The local arena always starts from ordinary
chess's starting position, while competition games may use different openings. Random
tie-breaking also means another run will not produce exactly the same totals.

## Testing against Benjamin

From the repository root, with the virtual environment active, run 20 games with the
current agent as `.` and Benjamin as the opponent:

```bash
python -m harness.arena \
    --agent . \
    --opponent past_models/Benjamin \
    --games 20 \
    --base-ms 5000
```

For one game with a PGN file:

```bash
python -m harness.play \
    --white . \
    --black past_models/Benjamin \
    --base-ms 5000 \
    --increment-ms 100 \
    --pgn game.pgn
```

Do not update Benjamin when improving the main agent. Its purpose is to remain a fixed
historical opponent. The normal submission zip contains the root `agent.py`, not this
folder.
