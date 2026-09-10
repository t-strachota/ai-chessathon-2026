"""Compare Ian's fixed allowance with adaptive time management."""

import argparse
import json
from pathlib import Path
from typing import Any

import chess

import agent
from match_maker.lab.verify import POSITIONS
from past_models.Ian import agent as ian


def baseline(board: chess.Board, seconds: float) -> dict[str, Any]:
    ian.clear_tables()
    return ian.analyze(board, seconds=seconds)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seconds", type=float, default=1.0)
    parser.add_argument("--out", type=Path, default=Path("match_maker/results/benchmark.json"))
    args = parser.parse_args()
    if not 0 < args.seconds <= 3:
        parser.error("--seconds must be greater than zero and at most 3")
    clock_ms = int(args.seconds * 40000 + 100)
    normal, hard = agent.time_budget(clock_ms)
    report: dict[str, Any] = {
        "seconds_per_search": args.seconds,
        "init_seconds": agent.INIT_SECONDS,
        "remaining_clock_ms": clock_ms,
        "normal_seconds": normal,
        "hard_seconds": hard,
        "note": "Serial cold-table searches. Same evaluator and search, different time allocation. "
        "Adaptive search may spend more or less; this is not an equal-time speed comparison.",
        "positions": [],
    }
    positions = {
        name: POSITIONS[name]
        for name in ("start", "castle", "ep", "promotion", "knight", "mopup", "clock")
    }
    positions["sicilian_castle"] = "rn1qk2r/1p1bbpp1/p2p3p/3Q4/2B1P2B/5P2/PPP3PP/2KR3R b kq - 0 13"
    for name, fen in positions.items():
        board = chess.Board(fen)
        old = baseline(board, args.seconds)
        agent.clear_tables()
        final = agent.analyze(board, hard, soft_seconds=normal)
        record = dict(name=name, fen=board.fen(), ian=old, adaptive=final)
        report["positions"].append(record)
        print(
            f"{name}: Ian {old['move']} d{old['depth']} {old['seconds']:.3f}s; "
            f"adaptive {final['move']} d{final['depth']} {final['seconds']:.3f}s "
            f"(normal {normal:.3f}s, hard {hard:.3f}s)",
            flush=True,
        )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + "\n")
    print("Report:", args.out)


if __name__ == "__main__":
    main()
