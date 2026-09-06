"""Compare search speed and ordering/TT variants without modifying the harness."""

import argparse
import json
import time
from pathlib import Path
from typing import Any
from unittest.mock import patch

import chess

import agent
from match_maker.lab.verify import POSITIONS
from past_models.Gabriel import agent as gabriel


def baseline(board: chess.Board, seconds: float) -> dict[str, Any]:
    counts = {"nodes": 0, "depth": 0}
    original_ab, original_q, original_root = (
        gabriel.alpha_beta,
        gabriel.quiescence,
        gabriel.search_at_depth,
    )

    def count_ab(*args: Any, **kwargs: Any) -> int:
        counts["nodes"] += 1
        return original_ab(*args, **kwargs)

    def count_q(*args: Any, **kwargs: Any) -> int:
        counts["nodes"] += 1
        return original_q(*args, **kwargs)

    def count_root(*args: Any, **kwargs: Any) -> chess.Move:
        result = original_root(*args, **kwargs)
        counts["depth"] = args[2]
        return result

    gabriel._POSITION_COUNTS.clear()
    start = time.monotonic()
    with (
        patch.object(gabriel, "alpha_beta", count_ab),
        patch.object(gabriel, "quiescence", count_q),
        patch.object(gabriel, "search_at_depth", count_root),
    ):
        move = gabriel.get_move(board.fen(), int(seconds * 40000 + 100))
    elapsed = time.monotonic() - start
    return dict(move=move, **counts, seconds=elapsed, nps=int(counts["nodes"] / elapsed))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seconds", type=float, default=1.0)
    parser.add_argument("--out", type=Path, default=Path("match_maker/results/benchmark.json"))
    args = parser.parse_args()
    report: dict[str, Any] = {
        "seconds_per_search": args.seconds,
        "init_seconds": agent.INIT_SECONDS,
        "note": (
            "Gabriel nodes count alpha-beta and quiescence entries; instrumentation adds overhead."
        ),
        "positions": [],
    }
    for name in ("start", "castle", "ep", "promotion", "knight", "mopup", "clock"):
        board = chess.Board(POSITIONS[name])
        old = baseline(board, args.seconds)
        modes = {}
        for label, tt, ordering in (
            ("unordered", 0, False),
            ("ordered", 0, True),
            ("move_table", 1, True),
            ("score_table", 2, True),
        ):
            agent.clear_tables()
            modes[label] = agent.analyze(board, args.seconds, tt_mode=tt, ordering=ordering)
        record = dict(name=name, fen=board.fen(), gabriel=old, compiled=modes)
        report["positions"].append(record)
        final = modes["score_table"]
        print(
            f"{name}: Gabriel d{old['depth']} {old['nps']:,} entries/s; "
            f"compiled d{final['depth']} {final['nps']:,} nodes/s, "
            f"move {final['move']}, TT hits {final['tt_hits']}",
            flush=True,
        )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + "\n")
    print("Report:", args.out)


if __name__ == "__main__":
    main()
