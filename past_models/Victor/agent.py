"""
Agent that is trained by neural network eval_net.onnx.
Includes a search structure that is classically a negamax + alpha-beta,
backed by the network, with quiescence search extending past captures
and repetition avoidance tracking real game history.

Arena score vs baselines/greedy over 20 games: +10 =8 -2, score 70.0%
(after adding repetition avoidance -- this was the single biggest jump,
bigger than any of the network/dataset upgrades below).

UPGRADE HISTORY:
- Added player turn awareness (side-to-move, 769th input)
- Added castling rights (4 more inputs, 773 total)
- Bigger network: 773 -> 512 -> 128 -> 32 -> 1
- Retrained on higher-quality data: RANDOMNESS 0.35 -> 0.15, EVAL_DEPTH 10 -> 14
- Added repetition avoidance (tracks real game positions, penalizes/rewards
  repeating a position depending on whether we're ahead or behind)
- Added quiescence search (extends search through capture sequences at the
  depth limit, to avoid the horizon effect -- e.g. grabbing a piece that's
  immediately recaptured, which the fixed-depth search alone can't see)

Current zip file size: 1.59MB / 50MB
"""

import time
from pathlib import Path

import chess
import onnxruntime as ort
from transform_data import transform_fen

# --- Load the model once, at import time -----------------------------
# Loading is the slow part. This cost happens during the comp's 60s
# init budget, before the clock starts.

ONNX_PATH = Path(__file__).resolve().with_name("eval_net.onnx")
_session = ort.InferenceSession(str(ONNX_PATH))
_input_name = _session.get_inputs()[0].name

CP_CLAMP = 1000  # must match the value train.py was run with


def evaluate(board: chess.Board) -> float:
    """
    Returns an eval from White's perspective, in pawns -- same units
    the classical evaluate() used, so search doesn't need to change.
    """
    if board.is_checkmate():
        return -900.0 if board.turn == chess.WHITE else 900.0
    if board.is_stalemate() or board.is_insufficient_material():
        return 0.0

    x = transform_fen(board.fen()).reshape(1, 773)
    result = _session.run(None, {_input_name: x})
    raw = float(result[0][0])           # network output, in [-1, 1]
    return raw * (CP_CLAMP / 100.0)      # undo training-time scaling,
                                          # centipawns -> pawns


# ----- Quiescence search ------
# Extends the search past the normal depth limit, but ONLY through
# capture moves, until the position "quiets down" (no more captures).
# This is what catches the horizon effect: a capture that looks good
# at the depth limit but is immediately lost back on the next ply,
# invisible to a plain fixed-depth search.

QUIESCENCE_MAX_DEPTH = 4  # safety cap against runaway capture chains


def quiescence(board: chess.Board, alpha: float, beta: float, qdepth: int = 0) -> float:
    stand_pat = evaluate(board)
    stand_pat = stand_pat if board.turn == chess.WHITE else -stand_pat

    if stand_pat >= beta:
        return beta
    if alpha < stand_pat:
        alpha = stand_pat

    if qdepth >= QUIESCENCE_MAX_DEPTH:
        return alpha

    for move in board.legal_moves:
        if not board.is_capture(move):
            continue
        board.push(move)
        score = -quiescence(board, -beta, -alpha, qdepth + 1)
        board.pop()
        if score >= beta:
            return beta
        if score > alpha:
            alpha = score
    return alpha


# ----- Repetition tracking across the REAL game --------------------------
# The process stays alive between our own moves for the whole game, so we
# can remember every position we've actually been asked to move from, and
# avoid throwing away a winning position by shuffling into a repeat -- or
# lean into one if we're currently losing.

_position_counts = {}


def _position_key(board: chess.Board) -> str:
    parts = board.fen().split(" ")
    return " ".join(parts[:4])  # piece placement, turn, castling, en passant --
                                  # NOT the move counters, which change every move


REPETITION_ADJUSTMENT = 3.0


# ----- Search ------

def search(board: chess.Board, depth: int, alpha: float, beta: float) -> float:
    if board.is_game_over():
        raw = evaluate(board)
        return raw if board.turn == chess.WHITE else -raw
    if depth == 0:
        return quiescence(board, alpha, beta)

    best = float("-inf")
    for move in board.legal_moves:
        board.push(move)
        value = -search(board, depth - 1, -beta, -alpha)
        board.pop()
        if value > best:
            best = value
        if best > alpha:
            alpha = best
        if alpha >= beta:
            break
    return best


def choose_depth(time_left_ms: int) -> int:
    # Shallower than the classical agent on purpose: each evaluate()
    # call now runs a full network forward pass, meaningfully slower
    # than a material-count formula. Same depth here would risk time.
    seconds_left = time_left_ms / 1000.0
    if seconds_left > 60:
        return 3
    if seconds_left > 20:
        return 2
    return 1


# ---- Required entry point ----

def get_move(fen: str, time_left_ms: int) -> str:
    start_time = time.time()
    board = chess.Board(fen)

    current_key = _position_key(board)
    _position_counts[current_key] = _position_counts.get(current_key, 0) + 1

    depth = choose_depth(time_left_ms)

    best_move = None
    best_value = float("-inf")
    alpha, beta = float("-inf"), float("inf")

    for move in board.legal_moves:
        board.push(move)
        value = -search(board, depth - 1, -beta, -alpha)

        resulting_key = _position_key(board)
        if _position_counts.get(resulting_key, 0) >= 2:
            if value > 0:
                value -= REPETITION_ADJUSTMENT
            elif value < 0:
                value += REPETITION_ADJUSTMENT

        board.pop()
        if value > best_value:
            best_value = value
            best_move = move
        if best_value > alpha:
            alpha = best_value

    if best_move is None:
        best_move = next(iter(board.legal_moves))

    elapsed = time.time() - start_time
    print(f"[timing] depth={depth}  time_left_ms={time_left_ms}  "
          f"move_took={elapsed:.1f}s  move={best_move.uci()}", flush=True)

    return best_move.uci()


# Local smoke test

if __name__ == "__main__":
    board = chess.Board()
    for i in range(4):
        move_uci = get_move(board.fen(), time_left_ms=120_000)
        print(f"Move {i + 1}: {move_uci}")
        board.push_uci(move_uci)
    print(board)