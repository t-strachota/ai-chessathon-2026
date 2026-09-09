# Chess Lab

One local desktop accessory for matches, live diagnostics, search verification,
and benchmarks. All implementation lives in `match_maker/`, including `lab/`.
The old `engine_lab` commands remain as compatibility entry points; existing
results in that folder are preserved. Neither folder goes into `agent.zip`.

## Start

```sh
v-env/bin/python -m match_maker
```

No new dependencies are required. The existing virtual environment includes Tk.
The app has a dark slate theme, mint accents, a redesigned board, and separate
Match room and Engine tools workspaces.

## Match room

- Select the working agent, any baseline, or a saved model.
- Set game count, base time, increment, and total-ply draw cap.
- Choose the normal start, a custom FEN, or the four-opening suite from the lab.
  The suite plays each opening with colors reversed before moving to the next.
  Eight games cover all four openings. Odd counts leave one color pair incomplete;
  longer series cycle through the same openings, not new random positions.
- Watch the board and live clocks. Inspect individual moves in the telemetry
  table; Follow live returns to the latest position.
- After a series, select a finished game in Results to review its moves, clocks,
  and telemetry. Board flipping is available.

### Statistics

Per move: SAN/UCI, response time, remaining clock, reported completed depth,
nodes, nodes/second, TT score cutoffs, material balance, legal moves for the side
to move, halfmove clock, captures, checks, and promotions. Timing and depth are
also shown as separate charts, with White in mint and Black in amber.

The Series analysis tab includes:

- wins/draws/losses, score, voids, technical failures, and terminations;
- A's performance as White and Black, and by opening;
- total thinking time and mean, median, p95, and maximum move response time;
- mean/max completed depth and number of moves reporting depth;
- total nodes, mean reported NPS, and total reported table score cutoffs;
- capture/check/promotion counts and lowest post-move clock;
- initialization time by competitor and completed-game wall time.

Voids are excluded from chess scores. Missing search telemetry is shown as `—`
and excluded from averages, not counted as zero. Depth, nodes, NPS, and TT hits
come from an agent's optional `LAST_SEARCH` dictionary. The current agent reports
these; older models may not. The accessory does not guess missing depths or run
additional searches to invent evaluations. Material balance is not an engine
evaluation, and NPS counters need not be comparable across different engines.

The local diagnostic runner returns the UCI reply plus a small optional stats
object, using the harness's existing process transport/watchdog. No harness or
agent source is modified. Response time includes local IPC and the small telemetry
serialization overhead; initialization is measured separately. This is a local
diagnostic tool, not a faithful reproduction of the competition container.

### Saving

Every finished game automatically updates timestamped `.pgn` and `.json` files
in `match_maker/results/`. JSON includes settings, full per-move records, and
aggregate statistics. A stopped partial game's legal move records are saved in
`unfinished_game_moves`, but it is not counted as a completed game. Files are
ignored by Git; use Export to save copies elsewhere.

Manual exports: PGN, full JSON, or one-row-per-move CSV. PGNs include clock and
elapsed-move-time annotations. Existing engine-lab results are not removed or
rewritten. JSON/CSV imports are not provided in this version.

Stop takes effect after the currently thinking agent returns or times out.
Closing the window requests the same cleanup. Export completed games at any time.
Only one match series or lab job can run in the app at once, avoiding misleading
measurements caused by running its benchmarks alongside its matches.

## Engine tools

Run correctness verification or the one-second search benchmark from the GUI.
Verification targets the working agent, with Gabriel retained only as a reference
for the legacy evaluation. Benchmarks compare the candidate against frozen Horst,
and isolate PVS and passer-safety evaluation, independently of the match selectors.
Reports include PVS probe and full re-search counts. Output streams into the console
and is saved to timestamped `.log`
files; benchmarks also save a JSON report. Cancel tool terminates a running lab
job. A failed command is shown as failed, never as a successful verification.

CLI equivalents:

```sh
v-env/bin/python -m match_maker.lab.verify
v-env/bin/python -m match_maker.lab.benchmark --seconds 1 --out match_maker/results/benchmark.json
v-env/bin/python -m match_maker.lab.series --opponent past_models/Horst --openings 4 --base-ms 120000 --increment-ms 500 --out match_maker/results/series
```

The original `python -m engine_lab.verify`, `.benchmark`, and `.series` commands
still work. The lab's CLI series retains its unmodified-harness runner and PGN
export; rich per-move diagnostic exports are provided by the GUI match runner.

## Tests

```sh
v-env/bin/python -m unittest match_maker.test_accessory -v
v-env/bin/python -m match_maker.smoke_gui
v-env/bin/ruff check .
v-env/bin/mypy agent.py harness match_maker engine_lab
```

The desktop smoke test briefly opens a window, plays two short capped games,
checks telemetry/replay/autosave, and runs verification through the lab UI.

## Local rule choices

The [contract](https://aichessathon.com/docs/agent-contract.md) and
[rules](https://aichessathon.com/docs/rules.md), checked September 6, 2026,
specify a draw at 600 total plies including the supplied opening. That is the
GUI's default cap; custom caps are local testing settings. The underlying old
harness still uses its stricter 60-second init budget instead of the live 90
seconds. The GUI retains the harness's unconditional loss-on-flag behavior;
the live contract has an exception when the opponent cannot mate. The app does
not enforce the platform's CPU/memory limits or suspend processes on opponent
time. Use platform validation for authoritative acceptance.
