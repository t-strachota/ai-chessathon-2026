# Alfred

Alfred is a saved version of our chess agent. It is based on the two-ply agent that was on
`main` before the alpha-beta work began. Keeping it here lets us play newer agents against a
known older version and measure whether an idea actually helps.

Alfred is a **classical chess program**, not a trained machine-learning model. It follows rules
written in Python and does not contain neural-network weights or training data.

## How Alfred chooses a move

For every legal move Alfred can make, it:

1. Temporarily plays that move.
2. Tries every legal reply the opponent could make.
3. Assumes the opponent will choose the reply that gives Alfred the worst score.
4. Remembers the move whose worst possible reply still leaves Alfred with the best score.

This is a basic form of **minimax**. It searches two plies:

```text
Ply 1: Alfred's move
Ply 2: the opponent's reply
Then:  evaluate the resulting position
```

A ply is one move by one player. Two plies therefore means one Alfred move plus one opponent
move, not two complete turns by both players.

## How Alfred scores a position

Alfred primarily counts material using these values:

```text
Pawn    100
Knight  320
Bishop  330
Rook    500
Queen   900
```

It also adds four points for every legal move available. This is called **mobility**. Mobility
encourages positions where pieces have more options instead of being trapped.

Checkmate is worth 1,000,000 points so it is always preferred over winning material. Stalemate
is scored as zero because it is a draw.

When multiple moves receive the same best score, Alfred chooses randomly between them. This
helps prevent it from repeating the same equal-scoring move forever.

## What Alfred does not do

- It does not use alpha-beta pruning.
- It never searches beyond the opponent's first reply.
- It does not use the remaining clock to change its search.
- It does not understand concepts such as pawn structure or king safety except where those
  affect material, mobility, checkmate, or stalemate.
- It can miss any tactic that becomes clear only after three or more plies.

## Testing against Alfred

From the repository root, with the virtual environment active:

```bash
python -m harness.arena --opponent past_models/Alfred --games 20 --base-ms 5000
```

This uses the current root `agent.py` as one player and Alfred as the opponent, alternating
colours between games.

For one game with PGN output:

```bash
python -m harness.play --white . --black past_models/Alfred --base-ms 5000 --pgn game.pgn
```

Alfred is a historical benchmark. Improvements should be made in the root `agent.py`, not in
this saved copy.
