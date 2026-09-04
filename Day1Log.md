# Day 1 Development Log

Date completed: 4 September 2026

This document is a handoff for the next developer or AI agent. Read this file,
`AGENTS.md`, the live competition documentation, and the current `agent.py` before
changing anything.

## Executive summary

Day 1 produced a stable classical chess-search agent named **Benjamin**. Benjamin is
currently both:

- the active root submission implementation in `agent.py`; and
- a frozen historical copy in `past_models/Benjamin/agent.py`.

Those two files were byte-for-byte identical at the end of Day 1. Do not modify the
historical copy when developing the next agent. Make future changes only to the root
`agent.py`, preferably on a new feature branch.

Benjamin uses material and mobility evaluation, minimax with alpha-beta pruning,
capture-first move ordering, iterative deepening, and deadline-based time management.
It completed a 500-game local benchmark without a crash, illegal move, or flag loss.

A checkpoint archive called `submission.zip` was built and verified. It contains only
the root `agent.py`. It has not been uploaded by the AI agent; uploading through the
competition dashboard is a manual/user action.

## Current repository state

At the end of Day 1:

- Branch: `main`
- Remote tracking branch: `origin/main`
- Latest committed revision before this log: `ef26699` (`Document Benjamin benchmark
  results`)
- `main` and `origin/main` were synchronized before this log was created.
- `Day1Log.md` is a new, uncommitted file until the user commits it.
- `.DS_Store` is also untracked. It is unrelated macOS metadata and should not be added
  to a commit.
- `submission.zip` exists locally but is ignored by `.gitignore`.
- The local virtual environment is `v-env`. It may be hidden by a global Git ignore;
  it is not part of the repository.

Useful checks:

```bash
git status --short --branch
git log --oneline --decorate --graph -12
git diff --no-index agent.py past_models/Benjamin/agent.py
```

The last command should produce no output while the root agent still equals Benjamin.
A nonzero `git diff --no-index` status means the new root agent has diverged, which is
expected after Day 2 development begins.

## User preferences and working style

The user is a beginner with limited coding experience and no prior AI experience.
Explain new concepts in plain language and show exactly where code should be placed.

The user generally prefers to type changes themselves when asking to be “guided.” Do
not edit code merely because they ask how to implement something. Make edits only when
they explicitly ask to implement, create, change, undo, or fix something.

Other important preferences:

- Do not rely on `uv`.
- Use the existing `v-env` virtual environment.
- Explain why a change matters and how to test it.
- Make one meaningful engine change at a time, then benchmark it.
- Preserve successful agents in `past_models/` before replacing them.
- Never edit `harness/`; it mirrors the competition behavior.

## Git identity

Both the repository-local and global Git identity were configured as:

```text
Name:  T Strachota
Email: 304605867+t-strachota@users.noreply.github.com
```

Earlier project commits were rewritten so this identity applies retrospectively. The
shared remote is already connected. Coordinate before rewriting published history
again.

## Development progression

The main Day 1 progression is visible in these commits, oldest first:

| Commit | Change |
| --- | --- |
| `b199a1b` | Replaced random selection with material-based move evaluation. |
| `2e281bf` | Added a two-ply minimax search: our move, then the opponent's best reply. |
| `4f232a6` | Added mobility to the position evaluation. |
| `a38bebb` | Refactored minimax to use alpha-beta pruning. |
| `5ca1e12` | Ordered captures before quiet moves to make pruning more effective. |
| `538d1b2` | Saved the older two-ply agent as `past_models/Alfred`. |
| `966b7ac` | Added iterative deepening, deadlines, and dynamic time allocation. |
| `7c081cf` | Saved the resulting agent as `past_models/Benjamin`. |
| `ef26699` | Added Benjamin's complete 500-game benchmark results. |

The first material-only version initially repeated moves frequently and scored only
55% in one 50-game random test. Random tie-breaking between equally scored moves
greatly reduced that behavior, and a later material-agent test scored 93% against
random. The project then moved through fixed two-ply minimax, mobility evaluation,
alpha-beta pruning, move ordering, and finally time-managed iterative deepening.

## Historical models

### Alfred

Location: `past_models/Alfred/`

Alfred is the previous fixed two-ply minimax agent. It evaluates material and mobility
but does not use alpha-beta pruning or dynamic search depth. Its README explains its
logic for beginners.

### Benjamin

Location: `past_models/Benjamin/`

Benjamin is the Day 1 checkpoint and current root agent. Its README contains a full
beginner-friendly explanation and all benchmark tables. Keep it frozen so future
changes can be measured against a stable opponent.

The `past_models` directory is for local benchmarking. The packager does not include it
in the submission archive.

## Benjamin's engine logic

Benjamin is a classical search engine, not a neural network or trained machine-learning
model.

### Evaluation

Material values are expressed in centipawn-like integer units:

```text
Pawn    100
Knight  320
Bishop  330
Rook    500
Queen   900
```

The king has no normal material value because losing a king is represented by
checkmate. Checkmate is scored as `1_000_000`, safely larger than any ordinary position
score. Stalemate and insufficient material score zero.

The evaluation also includes mobility:

```text
material advantage + signed legal-move count * 4
```

Mobility is positive when the side being evaluated is to move and negative when the
opponent is to move. This encourages positions with more options for Benjamin and fewer
for the opponent.

### Search

The search assumes both players choose their best move:

- maximizing nodes choose Benjamin's highest score;
- minimizing nodes choose the opponent's lowest score;
- alpha-beta pruning stops exploring branches that cannot affect the final choice.

Alpha-beta pruning does not change the answer of a completed minimax search at the same
depth. It saves time, allowing deeper searches.

All calls that temporarily push a move use `try`/`finally` to guarantee `board.pop()`.
This is a crucial safety invariant: a timeout must never leave the analysis board in a
corrupted state.

### Move ordering

Captures are searched before quiet moves. Captures use MVV-LVA ordering:

- prefer capturing the most valuable victim;
- when victims have equal value, prefer the least valuable attacker;
- en passant is explicitly treated as capturing a pawn.

Better ordering makes alpha-beta cutoffs happen earlier. Current ordering does not give
special priority to checks, promotions, killer moves, or historically successful moves.

### Iterative deepening and time management

Benjamin searches depth 1, then depth 2, then depth 3, and continues while time remains.
It only saves a move after the entire depth finishes. If a deeper search times out, it
returns the result from the last completed depth.

Before searching, it chooses a legal fallback move. This means an immediate timeout
still has a legal response available.

Current constants:

```python
MAX_SEARCH_DEPTH = 10
MAX_THINK_MS = 1_000
CLOCK_MARGIN_MS = 100
EXPECTED_MOVES_LEFT = 40
```

The per-move budget is approximately:

```text
(remaining clock - 100 ms) / 40
```

It is clamped to at least 1 ms and at most 1,000 ms. A monotonic clock provides the
deadline. `SearchTimeoutError` propagates out of the recursive search and is caught by
the iterative-deepening loop.

These constants fit the current competition clock. They were intentionally left
unchanged for the Day 1 checkpoint.

## Benchmark results

The complete tables and methodology are in `past_models/Benjamin/README.md`.

The test suite used 50 games per opponent at each of two time controls, alternating
colors so Benjamin played 25 games as White and 25 as Black in every row. All local arena
games began from the standard starting position.

Opponents:

- `baselines/random`
- `baselines/greedy`
- `baselines/minimax`
- `baselines/numba`
- `past_models/Alfred`

Normal time was 10,000 ms + 100 ms/move. Aggregate result over 250 games:

```text
153 wins, 81 draws, 16 losses
77.4% chess score
```

Longer time was 60,000 ms + 500 ms/move. This is enough for Benjamin to reach its
1,000 ms internal cap. Aggregate result over 250 games:

```text
218 wins, 31 draws, 1 loss
93.4% chess score
```

Combined result over 500 games:

```text
371 wins, 112 draws, 17 losses
85.4% chess score
388 checkmate endings
112 threefold-repetition draws
0 crashes, illegal moves, flags, or other technical failures
```

The most informative comparison was the improvement with more thinking time:

| Opponent | Normal score | Longer score |
| --- | ---: | ---: |
| Random | 96% | 99% |
| Greedy | 99% | 98% |
| Minimax | 64% | 89% |
| Numba | 69% | 88% |
| Alfred | 59% | 93% |

Do not treat these results as an Elo estimate or guaranteed competition performance.
The harness uses one starting position, while the competition uses curated openings.
Benjamin also breaks equal-score ties randomly, so repeated samples vary.

The first numba attempt was invalid because the local environment lacked `numpy` and
`numba`; the opponent crashed in every game. Those invalid games were discarded. Both
declared dependencies were installed into `v-env`, and the complete 50-game numba tests
were rerun successfully at both time controls. Only the valid reruns appear above and in
Benjamin's README.

## Local environment without uv

The user's laptop workflow uses a normal Python virtual environment called `v-env`.
Activate it in a terminal with:

```bash
source v-env/bin/activate
```

The local interpreter at the end of Day 1 was Python 3.14.2 on arm64 macOS. The
competition uses Python 3.12, so avoid Python 3.14-only syntax or behavior. The project
configuration and Ruff target Python 3.12.

Known installed package versions include:

```text
chess  1.11.2
ruff   0.16.6
mypy   2.3.1
numpy  2.5.2
numba  0.67.0
```

The Makefile still calls `uv`, so `make gate`, `make arena`, `make play`, and `make zip`
will fail on this laptop unless the Makefile is deliberately updated. Do not install or
use `uv` merely to run these targets. Use their direct Python equivalents.

Gate equivalent:

```bash
python -m ruff check .
python -m mypy
python -m harness.arena --opponent baselines/random --games 2 --base-ms 5000
```

Common harness commands:

```bash
# One game
python -m harness.play --white . --black past_models/Benjamin \
    --base-ms 5000 --increment-ms 100

# A color-balanced arena
python -m harness.arena --agent . --opponent past_models/Benjamin \
    --games 50 --base-ms 10000 --increment-ms 100

# Official local clock
python -m harness.arena --agent . --opponent past_models/Benjamin \
    --games 2 --base-ms 120000 --increment-ms 500
```

The arena alternates colors automatically. Use an even game count. Run benchmark
matches sequentially rather than in parallel; concurrent engines compete for CPU and
make deadline-based results unreliable.

## Submission checkpoint

Build the archive without `uv`:

```bash
v-env/bin/python -m harness.package
```

At the end of Day 1, `submission.zip` was verified with:

```bash
unzip -t submission.zip
unzip -l submission.zip
unzip -p submission.zip agent.py | cmp - agent.py
```

Verified contents:

```text
submission.zip
└── agent.py   6,370 bytes uncompressed
```

The expanded archive is far below the 50 MB competition limit. Rebuild it whenever the
root agent changes. Because it is ignored by Git, a clean `git status` does not prove
the archive is current.

The Day 1 checkpoint was created but not uploaded by the AI agent. The user intended to
upload Benjamin as a non-final checkpoint. The competition platform makes the latest
submission that passes validation the active agent, so inspect the validation log after
uploading.

## Competition contract checked on Day 1

The live sources are canonical and may change:

- <https://aichessathon.com/docs/agent-contract.md>
- <https://aichessathon.com/docs/rules.md>
- The same current technical material was accessible at
  <https://aichessathon.com/docs> on 4 September 2026.

Important values confirmed from the live documentation on 4 September 2026:

- The zip must contain `agent.py` at its root.
- The required API is `get_move(fen: str, time_left_ms: int) -> str` returning UCI.
- Match clock: 120 seconds per side plus 500 ms per move.
- Import budget: 60 seconds before the match clock starts.
- One dedicated CPU core, 2 GB RAM, no GPU, and no network.
- Read-only filesystem except for 256 MB scratch space at `/tmp`.
- Maximum expanded submission size: 50 MB.
- Python 3.12 with fixed versions of python-chess, numpy, numba, torch, and
  onnxruntime.
- A `requirements.txt` is ignored; use only the preinstalled stack.
- Illegal output, a crash, out-of-memory, or a flag fall loses the game.
- Games reaching 300 plies are adjudicated on material.
- Rated games use curated near-equal opening positions rather than always starting from
  the normal initial board.
- Classical search is explicitly allowed; a learned model is not required.
- Third-party engines such as Stockfish, Lc0, Maia, or wrappers around them are banned
  from the submission.
- The source must remain readable and unobfuscated.
- Six uploads per team per day; the latest upload that passes validation is active.

Always fetch the live pages again before answering questions about deadlines, limits,
allowed components, or competition operations.

## Known limitations and risks

1. **Evaluation is strategically shallow.** Benjamin knows material and mobility but
   not piece placement, king safety, pawn structure, passed pawns, development, or space.
2. **Horizon effect.** Search may stop in the middle of a capture sequence because
   there is no quiescence search.
3. **Basic move ordering.** Only captures receive priority. Checks and promotions are
   not specially ordered.
4. **No transposition table.** The same position can be searched repeatedly through
   different move orders.
5. **Repetition handling is weak.** The platform claims threefold draws, but Benjamin's
   search does not model repetition history. A fresh board built from FEN does not
   contain the earlier game history. Module state could track positions during a game.
6. **No mate-distance preference.** Every forced mate has the same magnitude rather
   than preferring faster mates or delaying unavoidable losses.
7. **Simple time allocation.** It always assumes about 40 moves remain and never spends
   more than one second, even when the official clock could support a larger budget in
   critical positions.
8. **Random tie-breaking.** This reduces deterministic loops but increases benchmark
   variance and makes exact games harder to reproduce.
9. **Local/runtime difference.** Development used Python 3.14.2 on arm64 macOS; the
   platform uses Python 3.12 on its own hardware.
10. **Benchmark openings are narrow.** Day 1 arena tests all started from the standard
    board, unlike the competition's curated positions.
11. **Code formatting is currently uneven.** Ruff and mypy passed during development,
    but parts of `agent.py` use awkward line wrapping. Any cleanup should preserve
    behavior and be benchmarked or at least verified against Benjamin.

## Recommended Day 2 starting process

1. Read `agent.py`, this log, and both historical-model READMEs.
2. Fetch the live competition docs again if discussing current rules.
3. Confirm the workspace state and do not commit `.DS_Store`.
4. Confirm `agent.py` still matches Benjamin before branching.
5. Create a new feature branch from `main`.
6. Choose one engine improvement, explain it to the user, and let the user implement it
   if they ask for guidance rather than direct implementation.
7. Run Ruff, mypy, focused position tests, and small smoke games first.
8. Benchmark against Benjamin and the stronger baselines using even game counts.
9. Compare results at identical time controls and watch for flags or crashes.
10. Merge only after the change is demonstrably safer or stronger.
11. Preserve the next successful root agent as another named model before replacing it.

A sensible first Day 2 improvement is **quiescence search**, because it directly
addresses evaluations that stop during unresolved capture sequences. A simpler
alternative is expanding move ordering to prioritize promotions and checks. Evaluation
improvements such as piece-square tables and king safety are also valuable, but change
playing strength rather than search reliability. Implement and measure one idea at a
time.

Suggested branch command:

```bash
git switch -c feature/quiescence-search
```

Do not assume that a more sophisticated idea is stronger. Keep Benjamin fixed and let
the results decide.

## Day 2 quick-start checklist

```bash
cd /Users/tobiasstrachota/Desktop/Development/ai-chessathon-2026
source v-env/bin/activate
git status --short --branch
git pull --ff-only origin main
git diff --no-index agent.py past_models/Benjamin/agent.py
python -m ruff check .
python -m mypy
git switch -c feature/quiescence-search
```

If `git pull` would overwrite local work or the initial status is not clean, stop and
inspect the changes rather than resetting or deleting them.
