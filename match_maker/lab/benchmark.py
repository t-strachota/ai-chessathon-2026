"""Compare Horst with isolated PVS and passer-evaluation changes."""

import argparse
import json
from pathlib import Path
from typing import Any

import chess

import agent
from match_maker.lab.verify import POSITIONS
from past_models.Horst import agent as horst


def baseline(board: chess.Board, seconds: float) -> dict[str, Any]:
    horst.clear_tables()
    return horst.analyze(board, seconds=seconds)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seconds", type=float, default=1.0)
    parser.add_argument("--out", type=Path, default=Path("match_maker/results/benchmark.json"))
    args = parser.parse_args()
    report: dict[str, Any] = {
        "seconds_per_search": args.seconds,
        "init_seconds": agent.INIT_SECONDS,
        "note": "Serial, cold-table searches. Compare scores only within the same evaluator.",
        "positions": [],
    }
    for name in ("start", "castle", "ep", "promotion", "knight", "mopup", "clock"):
        board = chess.Board(POSITIONS[name])
        old = baseline(board, args.seconds)
        modes = {}
        for label, pvs, safe_passers in (
            ("leaf_fixes", False, False),
            ("pvs_only", True, False),
            ("passers_only", False, True),
            ("candidate", True, True),
        ):
            agent.clear_tables()
            modes[label] = agent.analyze(board, args.seconds, pvs=pvs, safe_passers=safe_passers)
        record = dict(name=name, fen=board.fen(), horst=old, compiled=modes)
        report["positions"].append(record)
        final = modes["candidate"]
        print(
            f"{name}: Horst d{old['depth']} {old['nps']:,} nodes/s; "
            f"candidate d{final['depth']} {final['nps']:,} nodes/s, "
            f"move {final['move']}, PVS re-searches "
            f"{final['pvs_researches']}/{final['pvs_probes']}",
            flush=True,
        )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + "\n")
    print("Report:", args.out)


if __name__ == "__main__":
    main()
