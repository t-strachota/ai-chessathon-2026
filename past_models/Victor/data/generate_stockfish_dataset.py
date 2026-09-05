"""
Runs Stockfish games on the local CPU and records positions in a dataset file.

Replace the engine location with the appropriate path on your computer. The number of
positions, engine depth, and randomness can also be configured below.
"""

import json
import random
import time

import chess
import chess.engine

STOCKFISH_PATH = (
    r"C:\Users\vikiv\stockfish-windows-x86-64-avx2\stockfish"
    r"\stockfish-windows-x86-64-avx2.exe"
)

POSITIONS_TARGET = 1000
MAX_PLIES_PER_GAME = 60  # Stop at certain number of moves
EVAL_DEPTH = 10  # Depth of search
RANDOMNESS = 0.30  # Fraction of moves chosen randomly

OUTPUT_PATH = "dataset.jsonl"


def pick_move(board, engine):
    """
    Mostly-random move selection, occasionally nudged by a shallow
    Stockfish search, so games don't immediately fall apart into
    nonsense (e.g. hanging the queen every single move) while still
    covering a wide variety of positions.
    """
    legal = list(board.legal_moves)
    if random.random() < RANDOMNESS:
        return random.choice(legal)
    # Occasionally take Stockfish's own suggestion at very shallow
    # depth, just to keep games somewhat coherent.
    result = engine.play(board, chess.engine.Limit(depth=4))
    return result.move


def generate():
    engine = chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH)
    positions = []
    start_time = time.time()

    try:
        while len(positions) < POSITIONS_TARGET:
            board = chess.Board()
            ply = 0
            while not board.is_game_over() and ply < MAX_PLIES_PER_GAME:
                move = pick_move(board, engine)
                board.push(move)
                ply += 1

                # Sample this position for the dataset (skip the very
                # start, it's always the same and adds no signal).
                if ply > 4 and len(positions) < POSITIONS_TARGET:
                    info = engine.analyse(board, chess.engine.Limit(depth=EVAL_DEPTH))
                    score = info["score"].white()
                    # Mate scores get mapped to a large finite number
                    # so they're usable as plain numeric labels.
                    if score.is_mate():
                        cp = 10000 if score.mate() > 0 else -10000
                    else:
                        cp = score.score()
                    positions.append({"fen": board.fen(), "cp": cp})

                if len(positions) % 50 == 0 and len(positions) > 0:
                    elapsed = time.time() - start_time
                    print(f"{len(positions)}/{POSITIONS_TARGET} positions ({elapsed:.1f}s elapsed)")
    finally:
        engine.quit()

    with open(OUTPUT_PATH, "w") as f:
        for p in positions:
            f.write(json.dumps(p) + "\n")

    print(f"Wrote {len(positions)} positions to {OUTPUT_PATH}")


if __name__ == "__main__":
    generate()
