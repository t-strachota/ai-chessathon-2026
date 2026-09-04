# Charlie

Charlie is the checkpoint that added quiescence search to Benjamin's three-second
iterative alpha-beta search. The root `agent.py` and this saved `agent.py` were
byte-for-byte identical when Charlie was created.

Charlie is a classical chess-search agent, not a neural network or trained
machine-learning model.

## Difference from Benjamin

Benjamin evaluates a position immediately when its normal search reaches depth zero.
That can stop the search halfway through an exchange, before the opponent captures
back. Charlie instead starts a limited quiescence search at those leaves.

The quiescence search:

- continues through captures and promotions;
- searches every legal escape when the side to move is in check;
- orders promotions and valuable captures first;
- uses alpha-beta pruning and a maximum extension of four plies;
- shares the normal search deadline; and
- restores the board with `try`/`finally` when a timeout interrupts recursion.

Standing pat allows the side to move to decline an optional capture when its current
position is better. Standing pat is not allowed while in check because a legal escape
must be played.

Everything else remains Benjamin's design: material and mobility evaluation,
capture-first normal move ordering, iterative deepening, random tie-breaking, and a
maximum thinking-time allowance of 3,000 ms.

## Rated-position regressions

Charlie was tested on four tactical mistakes preserved from Benjamin's rated games. At
the official starting clock, it rejected all four known losing moves:

- Round 1: rejected `e5e4`;
- Round 4: rejected `a3c4` (`Nc4`);
- Round 4: rejected `d1d2` (`Qd2`); and
- Round 4: rejected `e1c1` (`O-O-O`).

The three-second Benjamin still selected `Nc4` and `Qd2` in the same local regression
checks.

## Benchmark against Benjamin

Two 10-game, colour-alternating batches were played against the saved three-second
Benjamin at 120,000 ms plus 500 ms per move:

| Batch | Wins | Draws | Losses | Score |
| --- | ---: | ---: | ---: | ---: |
| 1 | 1 | 7 | 2 | 45% |
| 2 | 6 | 3 | 1 | 75% |
| **Combined** | **7** | **10** | **3** | **60%** |

Across the 20 games, 10 ended by checkmate, 9 by threefold repetition, and 1 by the
fifty-move rule. Charlie had no crashes, illegal moves, or flag losses. Twenty games
remain a modest sample and should not be treated as a precise Elo estimate.

## Testing against Charlie

After the root agent diverges from Charlie, compare it against this fixed checkpoint:

```bash
v-env/bin/python -m harness.arena \
    --agent . \
    --opponent past_models/Charlie \
    --games 20 \
    --base-ms 10000 \
    --increment-ms 100
```

Use two to four games at 120,000 ms plus 500 ms per move as a final clock-safety gate.
Keep Charlie fixed while developing the next improvement so comparisons remain
meaningful. The normal submission packager does not include `past_models/`.

## Known limitations

- Evaluation still knows only material, mobility, and terminal game states.
- There is no repetition history, transposition table, king-safety evaluation, or
  passed-pawn evaluation.
- Ordinary checking moves are not included in quiescence unless the position is already
  in check; this keeps the tactical search bounded.
- Random tie-breaking increases benchmark variance.
