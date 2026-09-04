# Day 2 Development Log

Date: 4 September 2026

Status: **in progress**. The combined root-alpha/principal-variation candidate was
neutral at the official clock. Isolated follow-ups rejected PV carry and identified
root-alpha-only as promising: 75.0% fast and 62.5% official, both without a loss. The
current root adds piece-square tables and one bounded check extension; it scored 100.0%
over six fast games and 60.0% over 10 official-clock games. It has been saved as
**Ethan** and is ready to commit and promote.

This document is a handoff for the next developer or AI agent. Read `AGENTS.md`, the
live competition documentation, `Day1Log.md`, this file, and the current root `agent.py`
before changing the engine.

## Executive summary

Day 2 moved the active engine through three completed checkpoints and several isolated
experiments:

1. **Benjamin** was allowed to use up to three seconds per move instead of one.
2. **Charlie** added deadline-aware quiescence search for captures, promotions, and
   check evasions.
3. **Dylan** added real-game repetition awareness, passed-pawn evaluation, and a simple
   king-safety evaluation.
4. Root-search isolation rejected principal-variation carry and retained root-alpha
   pruning as the promising component.
5. The current uncommitted candidate adds piece-square evaluation and a single bounded
   check extension on top of root-alpha-only.

The user's ladder rank was approximately 170 at the start of this work, with the goal
of reaching the 150s by the end of the day. Reliability remained non-negotiable: every
accepted candidate retained a legal fallback, deadline checks inside recursive search,
and `try`/`finally` restoration around pushed moves.

The current stable submission checkpoint is **Dylan**, committed on `main` at `8e6f887`.
The current working branch is `feature/root-alpha-pv-ordering`, created from Dylan,
although its name no longer describes the root exactly. PV carry was removed; the root
now contains root-alpha pruning, piece-square tables, and one bounded check extension.
Dylan remains the committed checkpoint, while the validated root candidate is now
preserved under `past_models/Ethan` for promotion.

## Current repository state

At the time this log was started:

- Current branch: `feature/root-alpha-pv-ordering`
- Stable branch: `main`
- `main` and `origin/main`: `8e6f887`
- Stable commit: `8e6f887` (`Add position awareness and save Dylan checkpoint`)
- Root `agent.py`: root-alpha-only plus experimental piece-square tables and check extension
- `past_models/Dylan/agent.py`: frozen stable control
- `past_models/Ethan/agent.py`: byte-identical snapshot of the validated root candidate
- `Day2Log.md`: new and uncommitted
- `.DS_Store`: untracked macOS metadata; do not commit it
- There is no remote feature branch unless the user explicitly creates one later

Useful checks:

```bash
git status --short --branch
git log --oneline --decorate --graph -14
git diff --no-index agent.py past_models/Dylan/agent.py
git branch --all --verbose
```

The root and Dylan are expected to differ while the current experiment is active.

## Day 2 model lineage

| Model | Main addition | Saved location | Commit |
| --- | --- | --- | --- |
| Alfred | Fixed two-ply material/mobility minimax | `past_models/Alfred` | historical |
| Benjamin | Iterative alpha-beta; later raised to a 3-second cap | `past_models/Benjamin` | `efadf6e` update |
| Victor | ONNX evaluation plus fixed-depth negamax | `past_models/Victor` | `7a131c4` |
| Charlie | Four-ply bounded quiescence search | `past_models/Charlie` | `ea16c4e` |
| Dylan | Repetition, passed pawns, and king safety | `past_models/Dylan` | `8e6f887` |
| Ethan | Root alpha, piece-square tables, and check extension | `past_models/Ethan` | pending |

Each saved model is a complete runnable opponent. Ethan must remain frozen after its
promotion so it can serve as the next control.

## Live competition contract checked on Day 2

The canonical sources remain:

- <https://aichessathon.com/docs/agent-contract.md>
- <https://aichessathon.com/docs/rules.md>
- <https://aichessathon.com/docs>

Values reconfirmed on 4 September 2026 include:

- 120 seconds per side plus 500 ms per move;
- one dedicated CPU core, 2 GB RAM, no GPU, and no network;
- a 60-second initialization budget;
- a maximum unzipped submission size of 50 MB;
- Python 3.12 with fixed versions of python-chess, NumPy, Numba, PyTorch, and
  ONNX Runtime;
- one process per game, with module state surviving between moves;
- automatic threefold- and fifty-move claims by the referee;
- curated near-equal rated opening positions; and
- readable source, with third-party engines prohibited at runtime.

The current site illustrates the upload as `agent.zip` containing `agent.py` at its
root. The local packager still defaults to `submission.zip`, so build the desired name
explicitly:

```bash
v-env/bin/python -m harness.package --out agent.zip
unzip -t agent.zip
unzip -p agent.zip agent.py | cmp - agent.py
```

Always fetch the live pages again before relying on competition limits, schedules,
submission rules, or allowed components.

## Stage 1: Benjamin uses more of the clock

### Motivation

Day 1 rated games showed Benjamin losing or drawing while retaining approximately
88–115 seconds. Its normal allocation formula wanted to spend about three seconds near
the start of a 120-second game, but `MAX_THINK_MS = 1_000` overrode the formula.

### Change

The maximum was increased from:

```python
MAX_THINK_MS = 1_000
```

to:

```python
MAX_THINK_MS = 3_000
```

The remaining-clock division and 100 ms overall margin were left unchanged. At a
120,000 ms clock, the actual initial budget is approximately 2,997 ms.

### Focused evidence

At the three-second allowance, Benjamin rejected two of the four preserved rated
blunders:

- rejected Round 1's `e5e4`;
- still selected Round 4's `a3c4` (`Nc4`);
- still selected Round 4's `d1d2` (`Qd2`); and
- rejected Round 4's `e1c1` (`O-O-O`).

Local depth-4 timing on the decisive Round 4 castling position was approximately 2.08
seconds. This depth had been categorically unreachable under the old one-second cap.

### Benchmark

The updated root agent played the original one-second Benjamin over 10 games at
120,000 ms plus 500 ms per move:

```text
5 wins, 5 draws, 0 losses
75.0% chess score
```

There were five checkmates and five threefold repetitions, with no technical failures.
After acceptance, the saved Benjamin checkpoint was deliberately updated to match the
three-second version and its README was revised without relabelling the original Day 1
500-game tables.

Commit:

```text
efadf6e Increase Benjamin thinking time to three seconds
```

## Victor neural-network preservation

The remote branch `update_viktor` contained a separate neural-network agent under
`bots/stockfish_net`, while its root `agent.py` was an older Benjamin. All unique bot
artifacts were preserved before the branch was deleted:

```text
past_models/Victor/
├── README.md
├── agent.py
├── transform_data.py
├── train.py
├── eval_net.onnx
├── eval_net.onnx.data
├── eval_net.pt
└── data/
    ├── .gitignore
    ├── generate_dataset_cores.py
    └── generate_stockfish_dataset.py
```

The original generated training dataset was ignored by Git and was not present on the
branch. The trained ONNX model, ONNX external-data sidecar, PyTorch checkpoint,
preprocessing, training code, and both offline data-generation scripts were preserved.

Victor's original agent loaded `eval_net.onnx` relative to the shell's working
directory. The preserved copy resolves it relative to `__file__`, allowing the normal
harness command to run from the repository root.

The local `v-env` initially lacked ONNX Runtime, causing two invalid startup-crash smoke
games. `onnxruntime==1.29.0`, the project-pinned platform version, was installed into the
existing virtual environment. The rerun was valid:

```text
Benjamin vs Victor, 2 official-clock games
1 win, 1 draw, 0 losses
75.0% chess score
```

The invalid crash games were discarded. PyTorch remains unnecessary for inference;
training requires it.

Commit:

```text
7a131c4 Added Victor's model to Past_Models
```

## Stage 2: Charlie adds quiescence search

### Motivation

Benjamin evaluated immediately at ordinary depth zero, even when the leaf was halfway
through an exchange. This horizon effect directly contributed to the Round 4 sequence:

```text
Nc4 dxc4 Bxc4 Bxc4
```

Three seconds alone still failed the `Nc4` and `Qd2` regression positions.

### Implementation

Charlie added a maximum of four quiescence plies. At an ordinary depth-zero leaf it:

- evaluates immediately when no tactical continuation exists;
- continues captures and promotions;
- searches every legal escape when the side to move is in check;
- orders promotions and MVV-LVA captures first;
- uses stand-pat alpha-beta bounds outside check;
- shares the main search deadline; and
- restores every pushed move with `try`/`finally`.

Ordinary non-capturing checks are not extended unless they leave the next side in check.
This keeps the extension bounded.

### Focused results

Charlie rejected all four preserved losing moves:

```text
Round 1: e5e4
Round 4: a3c4
Round 4: d1d2
Round 4: e1c1
```

A forced timeout test also confirmed that the analysis board's FEN was unchanged after
`SearchTimeoutError` propagated through quiescence.

### Benchmark against three-second Benjamin

Two separate 10-game official-clock batches produced very different small-sample
results:

| Batch | Wins | Draws | Losses | Score |
| --- | ---: | ---: | ---: | ---: |
| 1 | 1 | 7 | 2 | 45% |
| 2 | 6 | 3 | 1 | 75% |
| **Combined** | **7** | **10** | **3** | **60%** |

The wide batch variance is a reminder that 10 games are not enough to estimate strength.
Across the combined 20 games there were no crashes, illegal moves, or flags.

Commit:

```text
ea16c4e Add quiescence search and save Charlie checkpoint
```

## Stage 3: Dylan adds position awareness

### Repetition and draw awareness

The platform passes only a FEN on each move, and a reconstructed `chess.Board` lacks the
earlier move stack. Dylan therefore keeps a module-level count of real positions reached
during the game.

Its repetition key includes:

- piece placement;
- side to move;
- castling rights; and
- a legally relevant en-passant square.

It intentionally excludes the halfmove and fullmove counters. The current incoming
position and the position after Dylan's selected move are recorded. The platform starts
a fresh process for each game, so no cross-game reset is necessary.

At the root, a candidate that would produce a third occurrence or an immediate
fifty-move claim receives a draw score of `0`. A positive continuation therefore beats
the draw, while a draw still beats a negative losing continuation. A non-drawing move
wins a genuine equal-score tie in Dylan's original full-window root search.

Focused tests confirmed that a side ahead by a queen avoided a manufactured repetition,
while a side behind by a queen deliberately accepted it.

### Passed-pawn evaluation

Passed-pawn masks are built once at import. A pawn is passed when no opposing pawn is
ahead on its own or either adjacent file. Bonuses scale with advancement:

```text
Advancement:  0   1   2   3   4   5    6   7
Bonus:        0   0  10  20  40  80  160   0
```

Tests distinguish a true passer from a pawn blocked by an adjacent opposing pawn.

### King-safety evaluation

Dylan rewards friendly pawns on the three squares immediately in front of the king and
penalizes enemy attacks on the king and its surrounding squares.

Current constants:

```python
KING_SHIELD_BONUS = 12
KING_RING_ATTACK_PENALTY = 8
```

The score is doubled while the opponent has a queen, used at normal weight when only an
enemy rook remains, and disabled when the opponent has neither queen nor rook. This
prevents the engine from treating an active king as inherently unsafe in minor-piece
endgames.

### Regression and timing results

- All four Charlie tactical regressions remained fixed.
- Repetition identity and root draw decisions passed focused tests.
- Passed-pawn and king-shield unit checks passed.
- At the official 2.997-second budget, Dylan completed the same normal depths as Charlie
  in three measured positions.
- At the 247 ms fast-development budget, Dylan lost one ply in the passed-pawn endgame
  but matched Charlie in the other two measured positions.

### Benchmarks against Charlie

Fast development clock, 20 games at 10,000 ms plus 100 ms:

```text
4 wins, 13 draws, 3 losses
52.5% chess score
12 threefold repetitions, 1 fifty-move draw, 7 checkmates
```

Official clock, four games at 120,000 ms plus 500 ms:

```text
2 wins, 2 draws, 0 losses
75.0% chess score
2 threefold repetitions, 2 checkmates
```

The official sample was small, but Dylan won both games as Black, drew both as White,
retained all tactical regressions, and had no technical failures.

Commit:

```text
8e6f887 Add position awareness and save Dylan checkpoint
```

## Current experiment: root alpha and principal-variation ordering

Status: **implemented locally, not committed; fast benchmark passed, combined
official-clock result neutral**.

### Motivation

Dylan's internal alpha-beta search pruned normally, but `search_at_depth` reset the root
window to `[-MATE_SCORE, MATE_SCORE]` for every candidate. It also failed to reuse the
best move from the previous completed iterative-deepening pass. This forced many inferior
root moves to be searched more fully than necessary.

### Implementation

The current root agent now:

1. passes the previous completed depth's best move into the next depth;
2. moves that preferred move to the front of the root move list;
3. tracks `root_alpha`, the best proven root score so far;
4. passes `root_alpha` into subsequent minimizing child searches; and
5. retains the first proven best move rather than treating a cutoff bound as an exact
   equal-score tie.

The legal random fallback is unchanged and is still used if no depth finishes. Once a
depth completes, root tie-breaking is more deterministic than Dylan because later
fail-soft/fail-hard bounds are not assumed to be exact equal scores.

### Verification completed before the arena

- Ruff passed repository-wide.
- Strict mypy passed.
- `git diff --check` passed.
- Fixed-depth tests returned the same exact best score as Dylan even when the candidate
  was deliberately given a different preferred first move.
- Repetition behavior remained correct: avoid a draw while winning, accept it while
  losing.
- All four tactical regressions remained fixed.
- A two-game fast smoke against Dylan scored 1 win and 1 draw with no failure.

Official-budget completed-depth comparison:

| Position | Dylan | Root-alpha/PV candidate |
| --- | ---: | ---: |
| Starting position | 4 | 4 |
| Round 3 before `Ng4` | 3 | 4 |
| Round 3 passed-pawn endgame | 4 | 4 |

The pre-`Ng4` position achieved the intended one-ply gain without losing depth in the
other two positions.

### Fast benchmark against Dylan

The candidate was tested over 20 games at 10,000 ms plus 100 ms per move:

```bash
v-env/bin/python -m harness.arena \
    --agent . \
    --opponent past_models/Dylan \
    --games 20 \
    --base-ms 10000 \
    --increment-ms 100
```

Result:

```text
16 wins, 4 draws, 0 losses
90.0% chess score
16 checkmates, 4 threefold repetitions
```

This is the strongest head-to-head result recorded on Day 2. Every decisive game was
won by the candidate, and there were no crashes, illegal moves, flags, or other
technical failures. The four draws were all threefold repetitions.

The result cleared the fast-development gate and justified an official-clock follow-up.

### Official-clock benchmark against Dylan

The candidate was then tested over four games at 120,000 ms plus 500 ms per move:

```text
1 win, 1 draw, 2 losses
37.5% chess score
3 checkmates, 1 threefold repetition
```

There were no crashes, illegal moves, flags, or other technical failures, but the
playing result failed the acceptance gate. The candidate lost once with White and once
with Black, won once with White, and drew once with Black.

Four games are too few to measure strength reliably, but the negative official-clock
result conflicts with the dominant fast result. The candidate must not replace Dylan
on this evidence alone. The root-alpha window is theoretically valid; likely sources
of variance include Dylan's randomized equal-score selection, the candidate's new
deterministic tie-breaking, and different completed depths at the two clocks.

The six-game official-clock follow-up produced:

```text
2 wins, 3 draws, 1 loss
58.3% chess score
3 checkmates, 3 threefold repetitions
```

Combining both official-clock batches gives:

```text
3 wins, 4 draws, 3 losses
50.0% chess score over 10 games
6 checkmates, 4 threefold repetitions
```

The follow-up recovered the initial deficit but did not establish an advantage at the
relevant clock. With no net win over Dylan, the combined PV-ordering/root-alpha change
is not an upgrade candidate. Any further investigation should separate the two changes
rather than run more games on the same combined implementation.

### Isolated root-search follow-up

PV-only retained Dylan's full root windows, randomized exact-score ties, and draw tie
preference. Its only change was searching the previous completed depth's best root move
first on the next depth.

```text
PV-only vs Dylan, 6 fast games: +3 =2 -1, 66.7%
PV-only vs Dylan, 3 completed official games: +1 =0 -2, 33.3%
```

The official run was manually interrupted during game four of a requested six because
the original buffered invocation was too slow for a development gate. The three
completed games are valid and all ended by checkmate. Their poor result reproduced the
clock sensitivity seen in the combined experiment, so PV carry was removed.

Root-alpha-only retained Dylan's ordinary root move order and did not carry a move
between iterative-deepening passes. It reused the best root alpha bound and retained the
first proven best move because later narrow-window results may be bounds rather than
exact tie scores.

```text
Root-alpha-only vs Dylan, 6 fast games: +3 =3 -0, 75.0%
Root-alpha-only vs Dylan, 4 official games: +1 =3 -0, 62.5%
```

The fast sample ended in three checkmates and three repetitions. The official sample
ended in one checkmate and three repetitions. Root-alpha-only passed both initial gates
without a loss and is the only root-search component retained in the working agent.

## Current experiment: piece-square tables and check extension

The root-alpha-only candidate was extended with side-relative piece-square tables for
pawns, knights, bishops, rooks, and queens. The values are modest centipawn bonuses that
encourage central knights, developed bishops, active rooks, sensible queen placement,
and pawn advancement without allowing placement to outweigh a pawn of material. Black
uses the same tables mirrored by relative rank.

Normal alpha-beta search now also extends a move that gives check by one ply. Each search
line receives at most one such extension, preventing repeated checks from growing the
tree without bound. The extension shares the existing hard deadline; quiescence remains
bounded to four plies.

Focused verification confirmed:

- every table is exactly 8 by 8;
- the starting position is positionally symmetric;
- a central knight scores above an edge knight;
- mirrored White and Black placements cancel;
- checking and non-checking root moves receive the intended different depths;
- the analysis board is restored after search; and
- all four historical tactical blunders remain rejected.

Initial benchmarks against Dylan:

```text
Piece-square/check candidate, 6 fast games: +6 =0 -0, 100.0%
Piece-square/check candidate, 2 official games: +1 =0 -1, 50.0%
```

All eight games ended by checkmate, with no crash, illegal move, or flag. The fast sweep
was encouraging, but the balanced two-game official sample was neutral and too small to
establish an upgrade. An eight-game official-clock follow-up then produced:

```text
3 wins, 4 draws, 1 loss
62.5% chess score
4 checkmates, 4 threefold repetitions
```

Combining both official batches gives:

```text
4 wins, 4 draws, 2 losses
60.0% chess score over 10 games
6 checkmates, 4 threefold repetitions
```

There were no crashes, illegal moves, or flags. The candidate scored positively at both
the fast and official clocks, retained every focused regression, and is ready to be
saved as the next named checkpoint before replacing `main`.

## Consolidated Day 2 benchmark table

| Candidate | Opponent | Games | Clock | W-D-L | Score |
| --- | --- | ---: | --- | --- | ---: |
| 3-second Benjamin | 1-second Benjamin | 10 | Official | 5-5-0 | 75.0% |
| Benjamin | Victor | 2 | Official | 1-1-0 | 75.0% |
| Charlie batch 1 | 3-second Benjamin | 10 | Official | 1-7-2 | 45.0% |
| Charlie batch 2 | 3-second Benjamin | 10 | Official | 6-3-1 | 75.0% |
| Charlie combined | 3-second Benjamin | 20 | Official | 7-10-3 | 60.0% |
| Dylan | Charlie | 20 | Fast | 4-13-3 | 52.5% |
| Dylan | Charlie | 4 | Official | 2-2-0 | 75.0% |
| Root-alpha/PV candidate | Dylan | 2 | Fast smoke | 1-1-0 | 75.0% |
| Root-alpha/PV candidate | Dylan | 20 | Fast | 16-4-0 | 90.0% |
| Root-alpha/PV candidate | Dylan | 4 | Official | 1-1-2 | 37.5% |
| Root-alpha/PV follow-up | Dylan | 6 | Official | 2-3-1 | 58.3% |
| Root-alpha/PV combined | Dylan | 10 | Official | 3-4-3 | 50.0% |
| PV-only | Dylan | 6 | Fast | 3-2-1 | 66.7% |
| PV-only, interrupted sample | Dylan | 3 | Official | 1-0-2 | 33.3% |
| Root-alpha-only | Dylan | 6 | Fast | 3-3-0 | 75.0% |
| Root-alpha-only | Dylan | 4 | Official | 1-3-0 | 62.5% |
| Piece-square/check candidate | Dylan | 6 | Fast | 6-0-0 | 100.0% |
| Piece-square/check candidate | Dylan | 2 | Official | 1-0-1 | 50.0% |
| Piece-square/check follow-up | Dylan | 8 | Official | 3-4-1 | 62.5% |
| Piece-square/check combined | Dylan | 10 | Official | 4-4-2 | 60.0% |

These samples are engineering evidence, not Elo estimates. Fast games emphasize search
overhead differently from the official three-second opening allowance, and all arena
games start from the ordinary initial position rather than the competition's curated
opening set.

## Local Match Maker helper

A standalone Tk desktop interface was added under `match_maker/`. It discovers the
root working agent and all agents in `baselines/` and `past_models/`, without modifying
`harness/` or the submission agent.

Launch it from the repository root:

```bash
v-env/bin/python -m match_maker
```

The interface provides competitor selection, alternating colors, configurable game
count and clocks, fast and official presets, a live board and move list, running clocks,
cumulative statistics, per-game results, technical-failure reporting, and PGN export.
Games run serially so the displayed board always belongs to the active game.

Validation completed:

- Ruff and strict mypy passed for the helper package;
- model discovery found the working agent, four baselines, and five past models;
- an in-memory Fool's Mate exercised four live position updates, checkmate detection,
  the final summary, and clean agent shutdown; and
- the Tk application launched and exited without a runtime error.

The tool has its own usage notes in `match_maker/README.md`. It uses only Python's Tk
interface and the project's existing dependencies.

## Local environment changes

The project continues to use `v-env`; do not introduce `uv` into the user's workflow.

Relevant locally installed runtime packages now include:

```text
python-chess  1.11.2
numpy         2.5.2
numba         0.67.0
onnxruntime   1.29.0
```

ONNX Runtime was added solely so the preserved Victor opponent can run locally. The
competition image already includes the pinned version. Victor's PyTorch training script
will not run in the local environment unless the declared PyTorch dependency is also
installed, but PyTorch is not needed to play against Victor's ONNX model.

An ONNX telemetry attempt briefly created an untracked `:memory:.ses` file during the
first local import. That generated file was inspected and removed. If it reappears,
treat it as local runtime metadata, not source.

## Current known limitations

Even after Dylan and the current search experiment, the engine still has important
limitations:

1. Repetition awareness covers actual game history at the root, not repetitions inside
   every hypothetical search line.
2. Draws have a neutral score rather than a bounded, advantage-dependent contempt score.
3. King safety is intentionally simple and does not explicitly remember whether the
   king castled.
4. Passed-pawn evaluation does not account for whether the pawn is protected, blockaded,
   or supported by the king.
5. There is no transposition table, killer-move heuristic, history heuristic, or cached
   principal variation below the root.
6. Normal move ordering still prioritizes captures but does not explicitly prioritize
   checks, promotions, or a transposition-table move.
7. Piece-square tables are hand-tuned and not phase-aware; evaluation still lacks
   broader pawn structure, bishop-pair scoring, open-file rook scoring, and space.
8. Quiescence has a fixed four-ply cap and excludes ordinary quiet checks; normal search
   permits only one check extension per line.
9. Randomness remains in the emergency fallback, while the current root search retains
   the first proven equal best move.
10. Local arenas use the standard starting position, unlike rated curated openings.

## Remaining acceptance process

The combined root-search experiment should not be promoted. Its isolated root-alpha
component was retained, PV carry was rejected, and the current piece-square/check
candidate has passed its initial gates. The remaining steps are:

1. Keep Dylan unchanged as the stable control.
2. Save the current root as the next named historical checkpoint before merging it.
3. Do not restore PV carry without new evidence.
4. Treat any crash, illegal move, or flag as an automatic rejection pending diagnosis.
5. Re-run all four tactical regressions after any code change.
6. Run the complete repository gate before packaging or merging.
7. Build any eventual upload explicitly as `agent.zip` and verify that `agent.py` is at
   its root.
8. Uploading through the dashboard remains a manual user action.

The next larger search experiment should be a correctly bounded transposition table,
added and benchmarked on a separate branch.

## Common verification commands

Static gates:

```bash
v-env/bin/python -m ruff check .
v-env/bin/python -m mypy
git diff --check
```

Fast development arena:

```bash
v-env/bin/python -m harness.arena \
    --agent . \
    --opponent past_models/Dylan \
    --games 20 \
    --base-ms 10000 \
    --increment-ms 100
```

Official-clock safety arena:

```bash
v-env/bin/python -m harness.arena \
    --agent . \
    --opponent past_models/Dylan \
    --games 4 \
    --base-ms 120000 \
    --increment-ms 500
```

Package and verify:

```bash
v-env/bin/python -m harness.package --out agent.zip
unzip -t agent.zip
unzip -p agent.zip agent.py | cmp - agent.py
```

Do not edit `harness/`, do not commit `.DS_Store`, and do not benchmark deadline-based
agents concurrently on the same CPU.
