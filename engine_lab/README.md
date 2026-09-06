# Compiled engine development

The tools now live in `match_maker/lab/` and can be run from the **Chess Lab**
desktop app: `v-env/bin/python -m match_maker`. The commands below remain working
compatibility shortcuts. Existing results in this folder are preserved. See
[`match_maker/README.md`](../match_maker/README.md) for the integrated GUI.

The candidate lives in the root `agent.py`; Gabriel remains unchanged in
`past_models/Gabriel`. No harness files were changed. This folder contains local
verification tools, not submission dependencies.

## What changed

The engine now uses an original 0x88 board and Numba-compiled legal move generation,
make/unmake, evaluation, and recursive search. Python-chess parses the incoming
FEN and validates the final reply; it is no longer in the recursive search loop.
All compilation happens during import, with disk caching disabled. Only readable
Python source ships, not a compiled engine binary.

Gabriel's nonterminal evaluation was preserved: material, piece-square tables,
legal mobility, passed pawns, king safety, mating conversion, and fifty-move
urgency. This makes the main experiment search speed rather than new evaluation
weights. The verification suite compares these evaluations directly.

Search uses iterative deepening and alpha-beta, capture/promotion ordering,
killer moves, history ordering, and transposition-table moves. Check and advanced
passed-pawn extensions have separate per-line budgets. Quiescence searches up to
six extra plies, with check evasions and advanced passed-pawn pushes included.
Mate-distance scores prefer faster mates. Normal iterative depth can reach 32;
the previous engine capped at 10. Thinking-time allocation is unchanged.

A transposition table remembers previous search results so the engine can avoid
searching the same situation again. Entries contain depth, score, move, and the
score's bound type. This implementation also checks the reversible repetition
history, halfmove clock, and extension budget before reusing a score. Mate scores
are adjusted for the new search ply. A separate position-only table can suggest
a move without assuming its old score is still valid. Tables occupy about 9 MiB.

Draw detection includes prospective threefold and fifty-move claims. Checkmate
takes precedence. Gabriel's small twofold-repetition penalty is not retained;
actual draw conditions are evaluated directly. With FEN-only input, positions
before the initial supplied FEN cannot be reconstructed.

There is deliberately no null-move pruning or late-move reduction in this
version. Those should be separate experiments after establishing this baseline.

## Run the checks

Run from the repository root:

```sh
v-env/bin/python -m engine_lab.verify
v-env/bin/python -m engine_lab.benchmark --seconds 1 --out engine_lab/results/benchmark-new.json
v-env/bin/ruff check agent.py engine_lab
v-env/bin/mypy agent.py engine_lab
```

Verification covers randomized legal moves, all legal make/unmake transitions,
castling, promotions, en passant and pins, reference perft counts, evaluation
equivalence, draw claims, TT score/bound/history/clock/extension handling,
mate-distance normalization, and interrupted searches.

The initial run passed 2,955 positions and 92,581 make/unmake comparisons.
Perft totals: start depth 4 = 197,281; castling position depth 3 = 97,862;
en-passant position depth 3 = 2,812; promotion position depth 3 = 9,467.
Import compilation took approximately two seconds locally.

## Initial speed results

One second per position on this development machine, with cleared tables:

| Position | Gabriel completed depth | Compiled completed depth |
| --- | ---: | ---: |
| Start | 4 | 6 |
| Castling/tactics | 3 | 4 |
| Rook/pawn ending | 4 | 7 |
| Promotions | 3 | 5 |
| Middlegame knight position | 3 | 5 |

On these positions the compiled engine processed roughly 150,000–330,000 nodes
per second. Gabriel's instrumented search processed roughly 10,000–22,000
function entries per second. These are approximate comparisons, not a precise
speed multiplier: Gabriel's counters add overhead and count the transition into
quiescence differently. Completed depth and match results are more useful.
The two additional mating positions were solved early, so lower reported depth
there is not a regression. Full numbers and ordering/table ablations are in
`results/benchmark.json`.

## Color-paired matches and PGN export

Eight fast games (four different openings, both colors per opening):

```sh
v-env/bin/python -u -m engine_lab.series \
  --base-ms 10000 --increment-ms 100 --openings 4 \
  --out engine_lab/results/fast-new
```

Four full-clock games (two openings, both colors):

```sh
v-env/bin/python -u -m engine_lab.series \
  --base-ms 120000 --increment-ms 500 --openings 2 \
  --out engine_lab/results/full-new
```

The default opponent is Gabriel. Override `--agent` and `--opponent` to compare
other folders. Both `.pgn` and `.json` are saved after each finished game.
Choose a new output name for each run; existing results are never overwritten.
PGNs are ignored by the repository's existing ignore rules but remain on disk.
Run matches and speed benchmarks sequentially to avoid CPU contention.

The first fast series scored **8 wins, 0 draws, 0 losses**, all by checkmate.
The full-clock series scored **4 wins, 0 draws, 0 losses**, also all by
checkmate, from two openings with colors reversed. Neither series had a
technical failure. Results are in `results/fast.json` and `results/full.json`;
the corresponding PGNs are available locally alongside them.
This is encouraging evidence, not a rating estimate or proof of leaderboard
strength. More openings and independent opponents are still needed.

## Platform and harness differences

The [live contract](https://aichessathon.com/docs/agent-contract.md) and
[rules](https://aichessathon.com/docs/rules.md), checked September 6, 2026,
allow Numba and specify a 90-second initialization budget, 120+0.5 clocks,
and a draw after 600 total plies. Processes are suspended during the opponent's
turn. Some repository quick-reference information is older.

The series tool uses the unmodified harness's process isolation and clocks. It
keeps its stricter 60-second initialization limit, passes a cap accounting for
the starting FEN's ply number, and reports reaching that cap as a draw instead
of the old harness's material adjudication. Other harness commands retain their
existing behavior. These tests are local, not platform validation: the local
Python version and CPU differ from the competition container. Check the upload
validation log before relying on a submission.
