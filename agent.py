"""The submission entrypoint. The platform imports this file and calls get_move."""

import random
import time

import chess

# Import time runs once per game, inside a 60 second budget, before your clock starts.
# Load weights and build tables out here, not inside get_move.

# Assign Values to each piece (can be changed)

PIECE_VALUES: dict[chess.PieceType, int] = {
    chess.PAWN: 100,
    chess.KNIGHT: 320,
    chess.BISHOP: 330,
    chess.ROOK: 500,
    chess.QUEEN: 900,
}

MATE_SCORE = 1_000_000
MOBILITY_WEIGHT = 4

MAX_SEARCH_DEPTH = 10
MAX_THINK_MS = 1_000
CLOCK_MARGIN_MS = 100
EXPECTED_MOVES_LEFT = 40

class SearchTimeoutError(Exception):
    """Signal that the current search has run out of time."""

# Create function to calculate material score of a board

def material_score(board: chess.Board, side: chess.Color) -> int:
    """Return side's material advantage."""
    score = 0

    for piece_type, value in PIECE_VALUES.items():
        own_pieces = len(board.pieces(piece_type, side))
        opponent_pieces = len(board.pieces(piece_type, not side))

        score += value * (own_pieces - opponent_pieces)

    return score

def position_score(board: chess.Board, side: chess.Color) -> int:
    """Evaluate a position from side's perspective."""
    if board.is_checkmate():
        return -MATE_SCORE if board.turn == side else MATE_SCORE

    if board.is_stalemate() or board.is_insufficient_material():
        return 0

    mobility = len(list(board.legal_moves))
    mobility_sign = 1 if board.turn == side else -1

    return material_score(board, side) + mobility_sign * MOBILITY_WEIGHT * mobility

def move_order_key(board: chess.Board, move: chess.Move,) -> tuple[int, int, int]:
    """Prioritize captures by victim value, then attacker value."""

    if not board.is_capture(move):
        return (0, 0, 0)

    attacker = board.piece_at(move.from_square)

    if board.is_en_passant(move):
        victim_value = PIECE_VALUES[chess.PAWN]
    else:
        victim = board.piece_at(move.to_square)
        victim_value = (
            0
            if victim is None
            else PIECE_VALUES.get(victim.piece_type, 0))

    attacker_value = (
        MATE_SCORE
        if attacker is None
        else PIECE_VALUES.get(attacker.piece_type, MATE_SCORE)
    )

    return (1, victim_value, -attacker_value)

def ordered_moves(board: chess.Board) -> list[chess.Move]:
    """Return legal moves in an alpha-beta-friendly order."""
    moves = list(board.legal_moves)
    moves.sort(key=lambda move: move_order_key(board, move), reverse=True,)
    return moves

def alpha_beta(board: chess.Board, depth: int, alpha: int, beta: int,
    maximizing: bool, mover: chess.Color, deadline: float,) -> int:

    """Search a position using minimax with alpha-beta pruning."""
    if time.monotonic() >= deadline:
        raise SearchTimeoutError

    if depth == 0 or board.is_insufficient_material():
        return position_score(board, mover)

    moves = ordered_moves(board)

    if not moves:
        return position_score(board, mover)

    if maximizing:
        value = -MATE_SCORE

        for move in moves:
            board.push(move)

            try:
                score = alpha_beta(board,
                      depth - 1, alpha,
                      beta, False,
                      mover, deadline,)
            finally:
                board.pop()

            value = max(value, score)
            alpha = max(alpha, value)

            if alpha >= beta:
                break

        return value

    value = MATE_SCORE

    for move in moves:
        board.push(move)

        try:
            score = alpha_beta(board,
                  depth - 1, alpha,
                  beta, True,
                  mover, deadline,)
        finally:
            board.pop()

        value = min(value, score)
        beta = min(beta, value)

        if alpha >= beta:
            break

    return value

def search_at_depth(board: chess.Board,
    mover: chess.Color, depth: int,
    deadline: float,) -> chess.Move:

    """Find the best move at one complete search depth."""
    moves = ordered_moves(board)

    if not moves:
        raise ValueError("No legal moves available")

    best_score = -MATE_SCORE
    best_moves: list[chess.Move] = []

    for move in moves:
        if time.monotonic() >= deadline:
            raise SearchTimeoutError

        board.push(move)

        try:
            score = alpha_beta(
                board,
                depth - 1,
                -MATE_SCORE,
                MATE_SCORE,
                False,
                mover,
                deadline,)
        finally:
            board.pop()

        if score > best_score:
            best_score = score
            best_moves = [move]
        elif score == best_score:
            best_moves.append(move)

    return random.choice(best_moves)

# Try every legal move and select the best material result.

def get_move(fen: str, time_left_ms: int) -> str:
    """Return a legal move in UCI notation.

    fen           the position to move in; your colour is the side to move
    time_left_ms  your clock before this move, in milliseconds
    returns       "e2e4", or "e7e8q" for a promotion

    The process stays alive between your moves, so state you keep on a module or in a
    closure survives to the next call. It does not survive to the next game.

    print() is safe. Your stdout is redirected away from the protocol stream, discarded
    during rated games and shown back to you in the validation log.
    """

    board = chess.Board(fen)
    moves = ordered_moves(board)

    if not moves:
        raise ValueError("No legal moves available")

    mover = board.turn

    # Always have a legal move available, even if the search times out immediately.
    best_move = random.choice(moves)

    usable_ms = max(1, time_left_ms - CLOCK_MARGIN_MS)
    budget_ms = max(1,min(MAX_THINK_MS, usable_ms // EXPECTED_MOVES_LEFT),)
    deadline = time.monotonic() + budget_ms / 1_000

    for depth in range(1, MAX_SEARCH_DEPTH + 1):
        try:
            completed_move = search_at_depth(board, mover, depth, deadline)
        except SearchTimeoutError:
            break

        # Only save a result after the entire depth completed successfully.
        best_move = completed_move

    return best_move.uci()
