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
