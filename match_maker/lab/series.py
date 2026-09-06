"""Color-paired matches from varied openings, with PGN export.

This uses the unmodified harness for process isolation and clocks. Its optional
600-ply cap is recorded; reaching it is reported as a draw to match the live
contract rather than the older harness's material-adjudication result.
"""

import argparse
import io
import json
from collections import Counter
from pathlib import Path

import chess
import chess.pgn

from harness.referee import play_match
from harness.sandbox import local

OPENINGS = {
    "open_game": "e4 e5 Nf3 Nc6 Bc4 Bc5 c3 Nf6 d3 d6",
    "queens_gambit": "d4 d5 c4 e6 Nc3 Nf6 Bg5 Be7 e3 O-O",
    "sicilian": "e4 c5 Nf3 d6 d4 cxd4 Nxd4 Nf6 Nc3 a6",
    "english": "c4 e5 Nc3 Nf6 g3 d5 cxd5 Nxd5 Bg2 Nb6",
}


def opening_fen(line: str) -> str:
    board = chess.Board()
    for san in line.split():
        board.push_san(san)
    return board.fen()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--agent", type=Path, default=Path("."))
    parser.add_argument("--opponent", type=Path, default=Path("past_models/Gabriel"))
    parser.add_argument("--base-ms", type=int, default=10000)
    parser.add_argument("--increment-ms", type=int, default=100)
    parser.add_argument("--openings", type=int, default=4, choices=range(1, 5))
    parser.add_argument("--out", type=Path, default=Path("match_maker/results/series"))
    args = parser.parse_args()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    pgn_path = args.out.with_suffix(".pgn")
    json_path = args.out.with_suffix(".json")
    if pgn_path.exists() or json_path.exists():
        parser.error("Choose a new --out path to preserve existing results.")
    report: dict[str, object] = {
        "agent": str(args.agent),
        "opponent": str(args.opponent),
        "base_ms": args.base_ms,
        "increment_ms": args.increment_ms,
        "init_budget_note": (
            "The older harness's 60-second init is stricter than the live 90 seconds."
        ),
    }
    games = []
    totals: Counter[str] = Counter()
    for name, line in list(OPENINGS.items())[: args.openings]:
        fen = opening_fen(line)
        # Start the cap relative to the FEN: include the opening's played plies.
        cap = 600 - chess.Board(fen).ply()
        for candidate_white in (True, False):
            white = args.agent if candidate_white else args.opponent
            black = args.opponent if candidate_white else args.agent
            outcome = play_match(
                local(white), local(black), args.base_ms, args.increment_ms, cap, fen
            )
            result = outcome.result
            termination = outcome.termination
            if termination == "adjudication":
                result, termination = "draw", "ply_limit"
            won = result == ("white" if candidate_white else "black")
            record = "D" if result == "draw" else "V" if result == "void" else "W" if won else "L"
            totals[record] += 1
            game = chess.pgn.read_game(io.StringIO(outcome.pgn))
            assert game is not None
            game.headers["White"], game.headers["Black"] = str(white), str(black)
            game.headers["Event"] = f"Compiled engine verification: {name}"
            game.headers["TimeControl"] = f"{args.base_ms / 1000:g}+{args.increment_ms / 1000:g}"
            game.headers["Termination"] = termination
            game.headers["Result"] = {
                "white": "1-0",
                "black": "0-1",
                "draw": "1/2-1/2",
                "void": "*",
            }[result]
            with pgn_path.open("a") as stream:
                stream.write(str(game) + "\n\n")
            entry = dict(
                opening=name,
                candidate_color="white" if candidate_white else "black",
                record=record,
                termination=termination,
                fen=fen,
                plies=len(list(game.mainline_moves())),
            )
            games.append(entry)
            report.update(games=games, totals=dict(totals))
            json_path.write_text(json.dumps(report, indent=2) + "\n")
            print(
                f"{name}, candidate {entry['candidate_color']}: {record} by {termination}; "
                f"total {dict(totals)}",
                flush=True,
            )
    print(f"PGN: {pgn_path}; report: {json_path}")


if __name__ == "__main__":
    main()
