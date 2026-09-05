"""
Agent that is trained by neural network eval_net.onnx .
Includes a search structure that is a classically a negamax + alpha-beta
but is also backed by the network.

Average arena score:
game 1/20: draw by insufficient_material
game 2/20: draw by insufficient_material
game 3/20: draw by insufficient_material
game 4/20: draw by insufficient_material
game 5/20: draw by insufficient_material
game 6/20: draw by threefold_repetition
game 7/20: white by checkmate
game 8/20: black by checkmate
game 9/20: black by checkmate
game 10/20: draw by insufficient_material
game 11/20: draw by insufficient_material
game 12/20: draw by insufficient_material
game 13/20: draw by insufficient_material
game 14/20: draw by insufficient_material
game 15/20: draw by insufficient_material
game 16/20: draw by threefold_repetition
game 17/20: draw by threefold_repetition
game 18/20: draw by insufficient_material
game 19/20: draw by stalemate
game 20/20: draw by stalemate

. vs baselines greedy over 20 games
+2 =17 -1, score 52.5%


It turns out that unfortunately, the trained data only added 1-5% success
over the classical search system.
UPGRADES:
-Decide whether to continue with the nn or go classical
- IF nn:
- Add player turn awareness
- Lower RANDOMNESS and increase EVAL_DEPTH
- Bigger network

Current zip file size: 1.59MB / 50MB

"""

from pathlib import Path

import chess
import onnxruntime as ort
from transform_data import transform_fen

# --- Load the model once, at import time -----------------------------
# Loading is the slow part.
# This cost happens during the comps 60s init budget

ONNX_PATH = Path(__file__).resolve().with_name("eval_net.onnx")
_session = ort.InferenceSession(str(ONNX_PATH))
_input_name = _session.get_inputs()[0].name

CP_CLAMP = 1000  # must match the value train.py was run with


def evaluate(board: chess.Board) -> float:
    """
    Returns an eval from White's perspective, in pawns -- same units
    your classical evaluate() used, so search doesn't need to change.
    """
    if board.is_checkmate():
        return -900.0 if board.turn == chess.WHITE else 900.0
    if board.is_stalemate() or board.is_insufficient_material():
        return 0.0

    x = transform_fen(board.fen()).reshape(1, 768)
    result = _session.run(None, {_input_name: x})
    raw = float(result[0][0])  # network output, in [-1, 1]
    return raw * (CP_CLAMP / 100.0)  # undo training-time scaling,
    # centipawns -> pawns


# ----- Search ------


def search(board: chess.Board, depth: int, alpha: float, beta: float) -> float:
    if depth == 0 or board.is_game_over():
        raw = evaluate(board)
        return raw if board.turn == chess.WHITE else -raw

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
        return 2
    if seconds_left > 20:
        return 1
    return 1


# ---- Required entry point ----


def get_move(fen: str, time_left_ms: int) -> str:
    board = chess.Board(fen)
    depth = choose_depth(time_left_ms)

    best_move = None
    best_value = float("-inf")
    alpha, beta = float("-inf"), float("inf")

    for move in board.legal_moves:
        board.push(move)
        value = -search(board, depth - 1, -beta, -alpha)
        board.pop()
        if value > best_value:
            best_value = value
            best_move = move
        if best_value > alpha:
            alpha = best_value

    if best_move is None:
        best_move = next(iter(board.legal_moves))

    return best_move.uci()


# Local smoke test

if __name__ == "__main__":
    board = chess.Board()
    for i in range(4):
        move_uci = get_move(board.fen(), time_left_ms=120_000)
        print(f"Move {i + 1}: {move_uci}")
        board.push_uci(move_uci)
    print(board)
