# Ian

Approved checkpoint after Horst, saved on 9 September 2026. Its `agent.py`
matches the root submission byte-for-byte. Keep this historical copy frozen.

## Changes from Horst

- Reuse the search's legal-move count during evaluation.
- Continue quiescence through check evasions after the ordinary cap, still
  bounded by the deadline, draw detection and maximum ply.
- Principal Variation Search (PVS), with full-window re-search of improving
  alternatives and diagnostic probe/re-search counters.
- Discount advanced passed pawns for blockades, vulnerability and enemy control
  of forward/promotion squares, retaining the previous bonus ceilings.

The Numba board, legal move generation, transposition-table context protection,
move ordering, time allocation and legal fallback are inherited from Horst.

## Verification and matches

The expanded verifier passed 2,955 positions and 92,581 make/undo transitions,
including PVS/TT equivalence, passer safety, checked quiescence, draw detection
and timeout restoration. Ruff and strict mypy passed.

Both series played Horst using four openings with colors reversed:

| Clock | Games | Wins | Draws | Losses | Score |
| --- | ---: | ---: | ---: | ---: | ---: |
| 10 seconds + 0.1 seconds/move | 8 | 5 | 0 | 3 | 62.5% |
| 120 seconds + 0.5 seconds/move | 24 | 14 | 1 | 9 | 60.4% |

No crashes, illegal moves or time losses occurred. All fast games ended by
checkmate; the longer series had 23 checkmates and one fifty-move draw.
All 993 fast-series and 2,877 longer-series moves and final results were replayed
and verified. The longer-series average depth was 6.10 versus Horst's 5.69,
with essentially equal mean thinking time.

`Testing Outcomes/chess-lab.json` and `.csv` contain the longer series. They
replaced the fast-series exports; that earlier result is preserved here from
the reviewed records. These samples repeat four openings and are not an Elo
estimate or proof of a general strength gain.

## Sicilian limitation

The longer series scored 4-0-2 in the open game, 6-0-0 in the Queen's Gambit,
0-1-5 in the Sicilian and 4-0-2 in the English (wins-draws-losses).

Forty-five serial diagnostic searches compared Horst and all four combinations
of PVS and the new pawn evaluation. Pawn toggles changed none of the sampled
moves/scores. At Black's ninth-move position, every configuration chose `h6`
with score +37 at depth 6. At the later castling position, all chose `O-O` at
depth 6 but preferred `Bg5+` with score +116 at depth 7. Ian needed about 6.8
seconds for the latter search, beyond its normal maximum time allocation.

This indicates a shared depth limitation at the sampled positions, not a
demonstrated PVS scoring defect. It does not prove `Bg5+` wins or explain all
later losses. Reports are the three `Testing Outcomes/sicilian-*.json` files;
the reproducible diagnostic is `match_maker/lab/sicilian_diagnostic.py`.

Adaptive thinking time is the proposed next separate experiment. Ian does not
include that change. Platform upload remains the user's action.
