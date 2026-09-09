"""Replay saved Sicilian positions with isolated search/evaluation switches."""

import argparse
import csv
import hashlib
import io
import json
from pathlib import Path
from typing import Any

import chess
import chess.pgn

import agent
from past_models.Horst import agent as horst


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--depth", type=int, default=32)
    parser.add_argument("--seconds", type=float, default=3.0)
    parser.add_argument("--game", type=int, help="Restrict diagnostics to one saved game")
    parser.add_argument("--turn", type=int, help="Restrict diagnostics to one fullmove number")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        parser.error("Choose a new output path to preserve previous diagnostics.")
    source = Path("Testing Outcomes/chess-lab.json")
    data = json.loads(source.read_text())
    with Path("Testing Outcomes/chess-lab.csv").open() as stream:
        rows = {(int(r["game"]), int(r["ply"])): r for r in csv.DictReader(stream)}
    selected = {
        6: {(9, False), (12, False), (13, False), (14, False)},
        5: {(9, True), (17, True), (25, True)},
    }
    report: dict[str, Any] = {
        "agent_sha256": hashlib.sha256(Path("agent.py").read_bytes()).hexdigest(),
        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "max_depth": args.depth,
        "seconds": args.seconds,
        "method": "Serial cold-table searches with the agent's available real-game history. "
        "Scores are side-to-move centipawns, not an external ground truth. "
        "Leaf fixes are present in all candidate variants; Horst is the frozen control.",
        "positions": [],
    }
    for game in data["games"]:
        number = game["game_number"]
        if number not in selected:
            continue
        if args.game is not None and number != args.game:
            continue
        parsed = chess.pgn.read_game(io.StringIO(game["pgn"]))
        assert parsed is not None and not parsed.errors
        board = parsed.board()
        keys = [int(agent.position_hash(agent.encode(board)))]
        for move in parsed.mainline_moves():
            if (board.fullmove_number, board.turn) in selected[number] and (
                args.turn is None or board.fullmove_number == args.turn
            ):
                row = rows[(number, board.ply() + 1)]
                prior = keys[:-1] if board.turn else keys[1:-1]
                record: dict[str, Any] = {
                    "game": number,
                    "turn": f"{board.fullmove_number}{'.' if board.turn else '...'}",
                    "fen": board.fen(),
                    "played": board.san(move),
                    "original_depth": float(row["depth"]),
                    "original_seconds": float(row["elapsed_ms"]) / 1000,
                    "legacy_static": agent.evaluate(agent.encode(board), -1, False),
                    "candidate_static": agent.evaluate(agent.encode(board)),
                    "variants": {},
                }
                for label, pvs, safe in (
                    ("horst", False, False),
                    ("leaf_fixes", False, False),
                    ("pvs_only", True, False),
                    ("passers_only", False, True),
                    ("candidate", True, True),
                ):
                    engine = horst if label == "horst" else agent
                    engine.clear_tables()
                    if label == "horst":
                        result = horst.analyze(
                            board, seconds=args.seconds, max_depth=args.depth, prior=prior
                        )
                    else:
                        result = agent.analyze(
                            board,
                            seconds=args.seconds,
                            max_depth=args.depth,
                            prior=prior,
                            pvs=pvs,
                            safe_passers=safe,
                        )
                    assert chess.Move.from_uci(result["move"]) in board.legal_moves
                    result["san"] = board.san(chess.Move.from_uci(result["move"]))
                    record["variants"][label] = result
                    print(
                        f"game {number} {record['turn']} {label}: "
                        f"{result['san']} score {result['score']} d{result['depth']} "
                        f"{result['seconds']:.3f}s",
                        flush=True,
                    )
                report["positions"].append(record)
                args.out.parent.mkdir(parents=True, exist_ok=True)
                args.out.write_text(json.dumps(report, indent=2) + "\n")
            board.push(move)
            keys.append(int(agent.position_hash(agent.encode(board))))
    print("Report:", args.out, flush=True)


if __name__ == "__main__":
    main()
