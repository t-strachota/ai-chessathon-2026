# Horst

Horst is the checkpoint of the compiled-search engine developed after Gabriel.
Its `agent.py` is a byte-for-byte snapshot of the repository root at checkpoint
time. Gabriel and all earlier checkpoints remain preserved.

## Features

- Numba-compiled 0x88 legal move generation, make/unmake, evaluation, and search.
- Iterative-deepening alpha-beta with capture, promotion, killer, history, and
  transposition-table move ordering.
- Context-safe transposition-table scores that account for repetition history,
  halfmove clock, extension budget, and mate distance.
- Bounded check and advanced passed-pawn extensions, plus six-ply quiescence.
- Prospective threefold and fifty-move draw detection and legal fallback moves.
- Gabriel's material, piece-square, mobility, passed-pawn, king-safety, and
  endgame-conversion evaluation retained unchanged.

## Validation

The four-opening full-clock suite against Gabriel scored 8 wins from 8 games,
all by checkmate, with colors reversed. The later 75-game PGN contained 33 wins,
42 draws, and no losses. Its test harness capped every draw at 100 plies, so the
draws are not natural 600-ply competition draws and should not be treated as a
rating estimate. The current agent averaged depth 5.66 in that PGN and reached
depth 9 at best.

The source passed the compiled engine verification suite, strict mypy, Ruff, two
random-agent smoke games, and the Chess Lab accessory tests. The submission zip
contains only the root `agent.py`; Chess Lab is local tooling and is not shipped.
