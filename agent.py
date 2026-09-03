"""The submission entrypoint. The platform imports this file and calls get_move."""

import random

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

    if board.is_stalemate():
        return 0

    return material_score(board, side)

def worst_reply_score(board: chess.Board, mover: chess.Color) -> int:
    """Return the score after the opponent's best reply."""
    replies = list(board.legal_moves)

    if not replies:
        return position_score(board, mover)

    worst_score = MATE_SCORE

    for reply in replies:
        board.push(reply)
        score = position_score(board, mover)
        board.pop()

        worst_score = min(worst_score, score)

    return worst_score

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

    mover = board.turn
    moves = list(board.legal_moves)

    if not moves:
        raise ValueError("No legal moves available")

    best_score = -MATE_SCORE
    best_moves: list[chess.Move] = []

    for move in moves:
        board.push(move)

        score = worst_reply_score(board, mover)

        board.pop()

        if score > best_score:
            best_score = score
            best_moves = [move]
        elif score == best_score:
            best_moves.append(move)

    # Randomly selects one of the best moves if there are multiple to avoid stalemate by repetition
    return random.choice(best_moves).uci()
