"""
Runs multiple Stockfish instances at once on separate CPU cores.

See generate_stockfish_dataset.py for more information. Viktor's laptop has 8 cores,
so this script assigns 7 of them to work. The value can be changed below.
"""

import json
import multiprocessing
import os
import random
import time

import chess
import chess.engine

STOCKFISH_PATH = (
    r"C:\Users\vikiv\stockfish-windows-x86-64-avx2\stockfish"
    r"\stockfish-windows-x86-64-avx2.exe"
)

NUM_WORKERS = 7  # Put 7 for safety, 8 for max speed

POSITIONS_TARGET_TOTAL = 1000000
MAX_PLIES_PER_GAME = 60  # Stop at certain number of moves
EVAL_DEPTH = 12  # Depth of search
RANDOMNESS = 0.30  # Fraction of moves chosen randomly. Tune this

OUTPUT_DIR = "dataset_parts"
FINAL_OUTPUT = "dataset.jsonl"


def pick_move(board, engine):
    legal = list(board.legal_moves)
    if random.random() < RANDOMNESS:
        return random.choice(legal)
    result = engine.play(board, chess.engine.Limit(depth=4))
    return result.move


def estimate_remaining(start_time, produced_so_far, total_needed):
    elapsed = time.time() - start_time
    if produced_so_far == 0:
        return "unknown (no data yet)"
    rate = produced_so_far / elapsed
    remaining = total_needed - produced_so_far
    eta_seconds = remaining / rate
    hours, rem = divmod(eta_seconds, 3600)
    minutes, seconds = divmod(rem, 60)
    return f"{int(hours)}h {int(minutes)}m {int(seconds)}s"


def generate_worker(worker_id, positions_target):
    """
    Runs its own process (single core). Different random seed
    each time so they dont generate the same random
    """
    random.seed(os.getpid() + worker_id + int(time.time()))
    engine = chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH)
    positions = []
    start_time = time.time()

    try:
        while len(positions) < positions_target:
            board = chess.Board()
            ply = 0
            while not board.is_game_over() and ply < MAX_PLIES_PER_GAME:
                move = pick_move(board, engine)
                board.push(move)
                ply += 1

                if ply > 4 and len(positions) < positions_target:
                    info = engine.analyse(board, chess.engine.Limit(depth=EVAL_DEPTH))
                    score = info["score"].white()
                    if score.is_mate():
                        cp = 10000 if score.mate() > 0 else -10000
                    else:
                        cp = score.score()
                    positions.append({"fen": board.fen(), "cp": cp})

                if len(positions) % 100 == 0 and len(positions) > 0:
                    elapsed = time.time() - start_time
                    eta = estimate_remaining(start_time, len(positions), positions_target)
                    print(
                        f"[worker {worker_id}] {len(positions)}/{positions_target} "
                        f"({elapsed:.1f}s elapsed, ETA {eta})"
                    )
    finally:
        engine.quit()

    out_path = os.path.join(OUTPUT_DIR, f"part_{worker_id}.jsonl")
    with open(out_path, "w") as f:
        for p in positions:
            f.write(json.dumps(p) + "\n")
    print(f"[worker {worker_id}] done: wrote {len(positions)} positions to {out_path}")


def merge_parts():
    total = 0
    with open(FINAL_OUTPUT, "w") as outfile:
        for fname in sorted(os.listdir(OUTPUT_DIR)):
            path = os.path.join(OUTPUT_DIR, fname)
            with open(path) as infile:
                for line in infile:
                    outfile.write(line)
                    total += 1
    print(f"Merged all parts into {FINAL_OUTPUT}: {total} total positions")


if __name__ == "__main__":
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    per_worker = POSITIONS_TARGET_TOTAL // NUM_WORKERS
    processes = []

    overall_start = time.time()
    for worker_id in range(NUM_WORKERS):
        p = multiprocessing.Process(target=generate_worker, args=(worker_id, per_worker))
        p.start()
        processes.append(p)

    for p in processes:
        p.join()

    merge_parts()
    print(f"Total wall-clock time: {time.time() - overall_start:.1f}s")
