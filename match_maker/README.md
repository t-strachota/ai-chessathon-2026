# Chessathon Match Maker

This is a local desktop interface for watching matches between the current agent,
saved agents in `past_models/`, and agents in `baselines/`. It does not modify the
competition harness or any agent.

## Start it

From the repository root, run:

```bash
v-env/bin/python -m match_maker
```

The existing `v-env` includes the required Tk interface. No additional package is
needed.

## What it provides

- automatic discovery of every folder containing an `agent.py` under `baselines/` and
  `past_models/`, plus the root working agent;
- competitor selection with colors alternating after every game;
- editable game count, base clock, and increment;
- fast and official-clock preset buttons;
- a live board, last-move highlighting, check highlighting, clocks, and move list;
- cumulative wins, draws, losses, chess score, average length, termination counts, and
  technical-failure count;
- a per-game result table; and
- optional export of all completed games to one PGN file.

Matches run serially so one live board always corresponds to the current game. The Stop
button takes effect after the agent currently thinking returns. Closing the window also
requests a clean stop.

This tool starts from the normal initial chess position. Like the existing local arena,
it cannot reproduce the competition's unpublished curated opening set.
