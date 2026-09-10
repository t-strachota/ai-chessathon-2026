# John

Approved checkpoint after Ian, saved on 10 September 2026. This `agent.py`
matches the root submission byte-for-byte at checkpoint time. Keep it frozen.

## Changes from Ian

John retains Ian's evaluation and compiled search, adding adaptive time allocation:

- Reserve up to one second of the remaining clock; derive the normal allowance
  from the remaining spendable time, capped at three seconds.
- Apply the normal deadline unless a completed depth changes the best move or
  drops the score by at least 60 centipawns (from depth three onward).
- Extra-time permission expires after two completed depths without a fresh signal.
  The absolute limit is at most three normal allowances and at most nine seconds,
  and shrinks with the remaining clock.
- Stop earlier for stable decisions and return forced moves without searching.
- Preserve the last completed result if a deeper iteration times out, including
  at the normal deadline. Record actual use of granted extra time in telemetry.

The GUI defaults to Ian as the comparison opponent. Benchmarks compare fixed and
adaptive allowances; JSON/CSV game exports include normal/hard timing allowances.

## Accepted candidate results

Both user-run series used the paired four-opening suite against Ian, with
alternating colors and a 600-ply cap:

| Clock | Games | Wins | Draws | Losses | Score |
| --- | ---: | ---: | ---: | ---: | ---: |
| 10 seconds + 0.1 seconds/move | 8 | 4 | 1 | 3 | 56.25% |
| 120 seconds + 0.5 seconds/move | 24 | 17 | 3 | 4 | 77.08% |

No crashes, illegal moves or time losses occurred. All 844 smoke-test and 3,330
extended-test plies were replayed against their CSV records and final results.
The longer series ended in 21 checkmates, two insufficient-material draws and
one threefold repetition, with 24 distinct complete move sequences.

| Opening, longer series | Wins | Draws | Losses |
| --- | ---: | ---: | ---: |
| Open game | 5 | 1 | 0 |
| Queen's Gambit | 5 | 1 | 0 |
| Sicilian | 5 | 0 | 1 |
| English | 2 | 1 | 3 |

Mean thinking time was 1.953 seconds versus Ian's 1.596 seconds. Granted extra
time was used on 922 of 1,668 moves (55.3%). John's minimum remaining clock was
8.177 seconds, with maximum measured hard-allowance overrun about 2.25 ms.
Mean depth was 6.10 versus Ian's 6.41; the gain was not uniform extra depth.

These results justify the checkpoint, but repeated samples of four openings do
not establish an Elo gain. The English remains the weakest tested opening.

## Verification and evidence

Ruff, strict mypy, and the expanded verifier passed, including 2,955 positions,
92,581 make/undo transitions, PVS/TT equivalence, passer safety, check evasions,
normal/hard deadlines, expiration of extra-time permission, forced-move history,
and retention of the last completed result after timeout.

The accepted smoke exports are in `Smoke Test Results/`; the longer series is
in `extended test results/`. Earlier smoke/benchmark figures from the initial,
more permissive timing policy are not results for John. The user approved this
candidate after the longer test. Platform upload remains the user's action.
