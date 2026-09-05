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

The user uploaded the Day 1 checkpoint as a non-final submission. The platform reported
`valid`. It expanded to 6,370 bytes, built successfully, and completed two 20-ply smoke
games—one as each color—without an initialization error, crash, illegal move, or flag.
Benjamin won both shortened smoke games by material adjudication. The Docker legacy-
builder warning in the log came from the organizer's infrastructure and required no
project change.

The competition platform makes the latest submission that passes validation the active
agent. A future upload therefore replaces Benjamin as the ladder agent once it validates.

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

## Live ladder and rated-game review

Benjamin's first live results were much weaker than its local baseline results. The
dashboard showed this record after Round 4:

```text
0 wins, 1 draw, 3 losses
0.5 points from 4 games
12.5% chess score
all three losses by checkmate
```

The public leaderboard had not yet incorporated Round 4 when checked. After Round 3 it
listed Benjamin / Stocked Fish at provisional rank 150 of 167, rating 1234, with a
0-1-2 record. The middle of the field was around rating 1500. These ratings had very few
games behind them, but Benjamin was clearly underperforming the field at that point.

Opponent context at the time of review:

- Sun was near Benjamin at rank 151 and rating 1232; their draw was consistent with
  similar provisional strength.
- Prophylaxis was much stronger at rank 96 and rating 1462, so that loss was not
  surprising.
- OpenAnand was below Benjamin at approximately rating 1202 with two previous losses;
  losing that game was the most concerning result.
- Check Republic could not be confidently matched to a current public leaderboard row,
  so no unsupported strength estimate was made.

The local random and greedy results had been useful engineering gates, but not measures
of average competition strength. The corresponding weak house bots were also near the
bottom of the live ladder. The curated competition openings exposed weaknesses that the
standard-start local arena did not.

### Rated PGN files

The four downloaded games were reviewed from:

```text
/Users/tobiasstrachota/Downloads/aichessathon-round-1-check-republic.pgn
/Users/tobiasstrachota/Downloads/aichessathon-round-2-sun.pgn
/Users/tobiasstrachota/Downloads/aichessathon-round-3-prophylaxis.pgn
/Users/tobiasstrachota/Downloads/aichessathon-round-4-openanand.pgn
```

These files are in `Downloads`, not the repository. Do not assume they will exist on a
different computer. Preserve copies in an appropriate test-fixture location if the user
chooses to add regression tests.

### Round 1: Check Republic

Benjamin played Black and lost by checkmate. The first large mistake was:

```text
13...e4? 14.gxf5
```

This left the knight on f5 hanging. Replaying Benjamin's own evaluator showed `e4`
tied for second at depth 2 but falling to 29th of 41 legal moves at depth 3. Benjamin
probably completed depth 2 but not depth 3 within its one-second budget.

White later established a pawn on g7 and promoted with `30.g8=Q+`. By Benjamin's
`28...Bh2+`, the position was already badly lost; that check merely delayed promotion.
The game demonstrates insufficient depth early and weak awareness of passed-pawn and
promotion threats.

### Round 2: Sun

Benjamin played Black and drew by threefold repetition despite being materially winning.
After `45...Rxa3`, Benjamin was ahead by about 1,130 evaluation units—more than a rook
and pawn—and Sun had almost no time left. Benjamin shuffled its king and rook instead of
converting the endgame, allowing the platform's automatic repetition claim.

The root cause is not a protocol failure. Each `get_move` call builds a new board from
FEN, which lacks the previous move stack. Benjamin therefore cannot see repetition
history even though module state survives between its moves. This game motivates
tracking position keys across calls and discouraging repeatable moves while materially
ahead.

### Round 3: Prophylaxis

Benjamin played White and lost by checkmate. The sequence

```text
26.Ng4 Qxe1+
27.Kxe1 Bxa1
```

exchanged Benjamin's two rooks for the opposing queen. `Ng4` still ranked first in
Benjamin's depth-3 and depth-4 replays, so deeper search alone does not fully solve this
game. Its evaluation underestimated the opponent's active rooks, Benjamin's exposed
king, and the long-term power of connected passed pawns.

Benjamin then gave many checks without improving its position while Black advanced the
c- and d-pawns. The c-pawn eventually promoted with check after `69...c1=Q+`, enabling
the final mating sequence. This game is direct evidence for passed-pawn, promotion-
threat, king-safety, and endgame improvements.

### Round 4: OpenAnand

Benjamin played White and lost by checkmate after only ten moves from the supplied
opening. This was the clearest horizon-effect failure:

```text
11.Nc4? dxc4
12.Bxc4 Bxc4
...
14.b4? Bxb4
15.Qd2? Bxc3
16.O-O-O?? Qa3+
17.Kb1 Bxa2#
```

Depth replays using Benjamin's own search produced:

| Move | Shorter-search judgment | Depth-4 judgment |
| --- | --- | --- |
| `11.Nc4` | 1st at depth 3 | 36th of 46 |
| `14.b4` | 1st at depth 2 | 16th of 36 |
| `15.Qd2` | 1st at depth 3 | 27th of 34 |
| `16.O-O-O` | tied 1st at depth 3 | 25th of 25; forced mate |

At depth 4, `O-O-O` received `-1_000_000`, Benjamin's checkmate score. One additional
ply exposed the exact mating move, but the live one-second search stopped immediately
before it.

### Clock evidence

Benjamin consumed approximately one second per move. With the 500 ms increment, its
displayed clock usually decreased by only about 500 ms per turn. Approximate clock time
remaining after its last move in each game was:

| Round | Benjamin's color | Remaining clock |
| --- | --- | ---: |
| Check Republic | Black | 106 seconds |
| Sun | Black | 96 seconds |
| Prophylaxis | White | 88 seconds |
| OpenAnand | White | 115 seconds |

Benjamin was therefore losing or drawing while leaving most of its clock unused. The
formula `(remaining time - margin) / 40` would initially allocate about 3,000 ms, but
`MAX_THINK_MS = 1_000` overrides it. More time would have allowed deeper completed
searches in at least some critical positions. It will not solve every weakness: Round
3's `Ng4` remained preferred at depth 4 because the evaluation itself was incomplete.

### Rated-game conclusion

Benjamin's deployment reliability was excellent, but the PGNs identify four chess
weaknesses in priority order:

1. It underuses the official clock.
2. It stops on tactically unstable positions—the horizon effect.
3. It does not know repetition history or convert winning endings reliably.
4. It undervalues king safety and dangerous passed pawns.

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
6. Turn the rated failures into focused regression positions before optimizing broadly.
7. Implement and measure the priority plan below one stage at a time.
8. Run Ruff, mypy, focused position tests, and small smoke games before a large arena.
9. Benchmark against Benjamin and the stronger baselines using even game counts.
10. Compare results at identical time controls and watch for flags or crashes.
11. Merge only after the change is demonstrably safer or stronger.
12. Preserve the next successful root agent as another named model before replacing it.

### Priority 0: rated-position regression checks

Extract at least these positions from the PGNs into a test or diagnostic script outside
`harness/`:

- Round 1 immediately before `13...e4`;
- Round 2 before the late repetition cycle while Benjamin is materially ahead;
- Round 3 before the connected passed pawns become decisive;
- Round 4 before `11.Nc4`, `15.Qd2`, and `16.O-O-O`.

Key single-position FENs are preserved here in case the downloaded PGNs are unavailable:

```text
# Round 1, before 13...e4
r3k2r/pp1b1pbp/3p2p1/q1pPpnB1/6P1/3P3P/PPP1NPB1/R2QR1K1 b kq - 0 13

# Round 3, before 26.Ng4
1r5r/1ppk4/p2pp2p/4q1p1/PP1b4/3QN1PP/6P1/R2KR3 w - - 2 26

# Round 3, before 62.Kc4 with connected passed pawns advancing
8/4b3/3kp3/6p1/3p1r1r/2pK2Q1/8/8 w - - 6 62

# Round 4, before 11.Nc4
r2qkb1r/1p3ppp/p1n1bn2/3pp3/4P3/N1N1BP2/PPPQ2PP/R3KB1R w KQkq - 0 11

# Round 4, before 15.Qd2
r3k2r/1p3ppp/p1n2n2/q3p3/1bb1P3/2N1BP2/P1P3PP/R2QK2R w KQkq - 0 15

# Round 4, before 16.O-O-O
r3k2r/1p3ppp/p1n2n2/q3p3/2b1P3/2b1BP2/P1PQ2PP/R3K2R w KQkq - 0 16
```

Round 2 repetition cannot be reproduced from one FEN because FEN does not contain the
full position history. Its regression must replay the late-game sequence or initialize
the proposed module-state tracker with the relevant earlier position keys.

The most important hard assertion is that the new agent must reject Round 4's
`16.O-O-O`, because depth 4 proves it leads to forced mate. Tests should use FENs and
legal-move assertions; never edit `harness/` to make the agent pass.

### Priority 1: use more of the clock

Start with an isolated time-management experiment. Raise `MAX_THINK_MS` from 1,000 ms
to approximately 3,000 ms while leaving evaluation unchanged. The existing division by
`EXPECTED_MOVES_LEFT = 40` already reduces the budget as the clock falls, so 3,000 ms is
approximately the natural opening allocation at the official 120-second clock.

Acceptance criteria:

- no flags in official-clock smoke games;
- the last fully completed depth is still returned on timeout;
- the Round 4 critical positions reach enough depth to reject the tactical blunders;
- measurable improvement against Benjamin or stronger baselines.

Do not merge a time increase based only on theoretical depth. Test it on the platform-
like one-core harness because the laptop and competition server have different speeds.

### Priority 2: quiescence or forcing-move extensions

At ordinary depth-zero leaves, continue searching tactically unstable moves such as
captures and promotions. Carefully selected checking moves may also need extensions.
This should expose sequences such as `Nc4 dxc4 Bxc4 Bxc4` without requiring every quiet
branch to reach depth 4.

Requirements:

- carry the existing deadline through every extension;
- retain `try`/`finally` around every pushed move;
- order promotions, checks, and valuable captures early;
- impose a sensible extension limit or quiet-position stopping rule;
- verify that search does not explode and cause flags.

### Priority 3: repetition awareness and conversion

Use module state to track prior position keys during the current game. The process is
fresh for each game, so game state does not need to survive between games. A position
key must account for piece placement, side to move, castling rights, and en-passant
state—not the halfmove/fullmove counters.

When materially ahead, penalize moves that permit automatic threefold repetition and
prefer irreversible progress such as safe pawn moves or captures. Test this against the
late Round 2 position. Take care not to reject a draw when Benjamin is losing and a
repetition is the best result.

### Priority 4: improve strategic evaluation

After search reliability improves, add evaluation terms incrementally:

1. dangerous passed pawns, scaled more strongly as they approach promotion;
2. immediate promotion threats;
3. king safety and exposed-king penalties;
4. piece-square tables and development;
5. pawn structure.

Round 3 is the primary regression game for these changes. Do not add all terms in one
commit; otherwise it will be impossible to know which term helped or hurt.

### Day 2 benchmarking gate

For each priority stage:

1. Run the rated-position checks.
2. Run Ruff and mypy.
3. Play two official-clock smoke games, one as each color.
4. Play a small 10- or 20-game arena against Benjamin and minimax.
5. If promising, expand to at least 50 games per important opponent.
6. Run matches sequentially so deadline tests receive uncontested CPU.
7. Reject any version that introduces crashes, illegal moves, or flags.

The first four live games are too small a sample to estimate final Elo, but they are
high-value regression cases because the exact failure sequences are known. Implement
and measure one idea at a time.

Suggested branch command:

```bash
git switch -c feature/time-management
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
git switch -c feature/time-management
```

If `git pull` would overwrite local work or the initial status is not clean, stop and
inspect the changes rather than resetting or deleting them.
