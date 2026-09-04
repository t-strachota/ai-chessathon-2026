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
PASSED_PAWN_BONUSES: tuple[int, ...] = (0, 0, 10, 20, 40, 80, 160, 0)
KING_SHIELD_BONUS = 12
KING_RING_ATTACK_PENALTY = 8

MAX_SEARCH_DEPTH = 10
MAX_QUIESCENCE_DEPTH = 4
MAX_THINK_MS = 3_000
CLOCK_MARGIN_MS = 100
EXPECTED_MOVES_LEFT = 40

PositionKey = tuple[str, bool, int, int | None]
_POSITION_COUNTS: dict[PositionKey, int] = {}


class SearchTimeoutError(Exception):
    """Signal that the current search has run out of time."""


def _build_passed_pawn_masks(side: chess.Color) -> tuple[int, ...]:
    """Build masks containing the opposing pawn squares that block a passer."""
    masks: list[int] = []

    for square in chess.SQUARES:
        pawn_file = chess.square_file(square)
        pawn_rank = chess.square_rank(square)
        files = range(max(0, pawn_file - 1), min(8, pawn_file + 2))
        ranks = range(pawn_rank + 1, 8) if side == chess.WHITE else range(pawn_rank - 1, -1, -1)
        mask = 0

        for target_file in files:
            for target_rank in ranks:
                mask |= chess.BB_SQUARES[chess.square(target_file, target_rank)]

        masks.append(mask)

    return tuple(masks)


PASSED_PAWN_MASKS: dict[chess.Color, tuple[int, ...]] = {
    chess.WHITE: _build_passed_pawn_masks(chess.WHITE),
    chess.BLACK: _build_passed_pawn_masks(chess.BLACK),
}


def position_key(board: chess.Board) -> PositionKey:
    """Return the parts of a position that determine repetition identity."""
    legal_ep_square = board.ep_square if board.has_legal_en_passant() else None
    return (
        board.board_fen(),
        board.turn,
        board.castling_rights,
        legal_ep_square,
    )


def record_position(board: chess.Board) -> None:
    """Record one position reached in the real game."""
    key = position_key(board)
    _POSITION_COUNTS[key] = _POSITION_COUNTS.get(key, 0) + 1


def is_immediate_history_draw(board: chess.Board) -> bool:
    """Return whether the current root candidate immediately allows a claimed draw."""
    return _POSITION_COUNTS.get(position_key(board), 0) >= 2 or board.is_fifty_moves()


# Create function to calculate material score of a board


def material_score(board: chess.Board, side: chess.Color) -> int:
    """Return side's material advantage."""
    score = 0

    for piece_type, value in PIECE_VALUES.items():
        own_pieces = len(board.pieces(piece_type, side))
        opponent_pieces = len(board.pieces(piece_type, not side))

        score += value * (own_pieces - opponent_pieces)

    return score


def passed_pawn_bonus(board: chess.Board, side: chess.Color) -> int:
    """Reward pawns with no opposing pawn blocking their path to promotion."""
    opponent_pawns = board.pieces_mask(chess.PAWN, not side)
    masks = PASSED_PAWN_MASKS[side]
    bonus = 0

    for square in board.pieces(chess.PAWN, side):
        if opponent_pawns & masks[square]:
            continue

        rank = chess.square_rank(square)
        advancement = rank if side == chess.WHITE else 7 - rank
        bonus += PASSED_PAWN_BONUSES[advancement]

    return bonus


def passed_pawn_score(board: chess.Board, side: chess.Color) -> int:
    """Return side's passed-pawn advantage."""
    return passed_pawn_bonus(board, side) - passed_pawn_bonus(board, not side)


def king_safety_bonus(board: chess.Board, side: chess.Color) -> int:
    """Score a king's pawn shield and pressure around its surrounding squares."""
    king_square = board.king(side)

    if king_square is None:
        return 0

    enemy = not side

    if board.pieces_mask(chess.QUEEN, enemy):
        danger_multiplier = 2
    elif board.pieces_mask(chess.ROOK, enemy):
        danger_multiplier = 1
    else:
        return 0

    king_file = chess.square_file(king_square)
    king_rank = chess.square_rank(king_square)
    shield_rank = king_rank + 1 if side == chess.WHITE else king_rank - 1
    shield_pawns = 0

    if 0 <= shield_rank < 8:
        for shield_file in range(max(0, king_file - 1), min(8, king_file + 2)):
            piece = board.piece_at(chess.square(shield_file, shield_rank))

            if piece is not None and piece.piece_type == chess.PAWN and piece.color == side:
                shield_pawns += 1

    king_zone = chess.SquareSet(chess.BB_KING_ATTACKS[king_square] | chess.BB_SQUARES[king_square])
    attacked_squares = sum(board.is_attacked_by(enemy, square) for square in king_zone)

    return danger_multiplier * (
        shield_pawns * KING_SHIELD_BONUS - attacked_squares * KING_RING_ATTACK_PENALTY
    )


def king_safety_score(board: chess.Board, side: chess.Color) -> int:
    """Return side's king-safety advantage."""
    return king_safety_bonus(board, side) - king_safety_bonus(board, not side)


def position_score(board: chess.Board, side: chess.Color) -> int:
    """Evaluate a position from side's perspective."""
    if board.is_checkmate():
        return -MATE_SCORE if board.turn == side else MATE_SCORE

    if board.is_stalemate() or board.is_insufficient_material():
        return 0

    mobility = len(list(board.legal_moves))
    mobility_sign = 1 if board.turn == side else -1

    return (
        material_score(board, side)
        + mobility_sign * MOBILITY_WEIGHT * mobility
        + passed_pawn_score(board, side)
        + king_safety_score(board, side)
    )


def move_order_key(
    board: chess.Board,
    move: chess.Move,
) -> tuple[int, int, int]:
    """Prioritize captures by victim value, then attacker value."""

    if not board.is_capture(move):
        return (0, 0, 0)

    attacker = board.piece_at(move.from_square)

    if board.is_en_passant(move):
        victim_value = PIECE_VALUES[chess.PAWN]
    else:
        victim = board.piece_at(move.to_square)
        victim_value = 0 if victim is None else PIECE_VALUES.get(victim.piece_type, 0)

    attacker_value = (
        MATE_SCORE if attacker is None else PIECE_VALUES.get(attacker.piece_type, MATE_SCORE)
    )

    return (1, victim_value, -attacker_value)


def ordered_moves(board: chess.Board) -> list[chess.Move]:
    """Return legal moves in an alpha-beta-friendly order."""
    moves = list(board.legal_moves)
    moves.sort(
        key=lambda move: move_order_key(board, move),
        reverse=True,
    )
    return moves


def tactical_move_order_key(
    board: chess.Board,
    move: chess.Move,
) -> tuple[int, int, int, int]:
    """Prioritize promotions and valuable captures."""
    promotion_value = 0 if move.promotion is None else PIECE_VALUES.get(move.promotion, 0)
    capture_flag, victim_value, attacker_score = move_order_key(board, move)

    return (
        promotion_value,
        capture_flag,
        victim_value,
        attacker_score,
    )


def ordered_tactical_moves(board: chess.Board) -> list[chess.Move]:
    """Return captures and promotions in tactical order."""
    moves = [
        move for move in board.legal_moves if board.is_capture(move) or move.promotion is not None
    ]
    moves.sort(
        key=lambda move: tactical_move_order_key(board, move),
        reverse=True,
    )
    return moves


def quiescence(
    board: chess.Board,
    alpha: int,
    beta: int,
    maximizing: bool,
    mover: chess.Color,
    deadline: float,
    remaining_depth: int,
) -> int:
    """Continue forcing moves until the position is tactically quiet."""
    if time.monotonic() >= deadline:
        raise SearchTimeoutError

    if remaining_depth == 0 or board.is_insufficient_material():
        return position_score(board, mover)

    in_check = board.is_check()

    if in_check:
        # The king must escape, so every legal response must be considered.
        moves = ordered_moves(board)

        if not moves:
            return position_score(board, mover)

        value = -MATE_SCORE if maximizing else MATE_SCORE
    else:
        # Standing pat means choosing not to enter another capture.
        value = position_score(board, mover)
        moves = ordered_tactical_moves(board)

        if not moves:
            return value

        if maximizing:
            if value >= beta:
                return value
            alpha = max(alpha, value)
        else:
            if value <= alpha:
                return value
            beta = min(beta, value)

    if maximizing:
        for move in moves:
            board.push(move)

            try:
                score = quiescence(
                    board,
                    alpha,
                    beta,
                    False,
                    mover,
                    deadline,
                    remaining_depth - 1,
                )
            finally:
                board.pop()

            value = max(value, score)
            alpha = max(alpha, value)

            if alpha >= beta:
                break

        return value

    for move in moves:
        board.push(move)

        try:
            score = quiescence(
                board,
                alpha,
                beta,
                True,
                mover,
                deadline,
                remaining_depth - 1,
            )
        finally:
            board.pop()

        value = min(value, score)
        beta = min(beta, value)

        if alpha >= beta:
            break

    return value


def alpha_beta(
    board: chess.Board,
    depth: int,
    alpha: int,
    beta: int,
    maximizing: bool,
    mover: chess.Color,
    deadline: float,
) -> int:
    """Search a position using minimax with alpha-beta pruning."""
    if time.monotonic() >= deadline:
        raise SearchTimeoutError

    if depth == 0:
        return quiescence(
            board,
            alpha,
            beta,
            maximizing,
            mover,
            deadline,
            MAX_QUIESCENCE_DEPTH,
        )

    if board.is_insufficient_material():
        return position_score(board, mover)

    moves = ordered_moves(board)

    if not moves:
        return position_score(board, mover)

    if maximizing:
        value = -MATE_SCORE

        for move in moves:
            board.push(move)

            try:
                score = alpha_beta(
                    board,
                    depth - 1,
                    alpha,
                    beta,
                    False,
                    mover,
                    deadline,
                )
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
            score = alpha_beta(
                board,
                depth - 1,
                alpha,
                beta,
                True,
                mover,
                deadline,
            )
        finally:
            board.pop()

        value = min(value, score)
        beta = min(beta, value)

        if alpha >= beta:
            break

    return value


def search_at_depth(
    board: chess.Board,
    mover: chess.Color,
    depth: int,
    deadline: float,
) -> chess.Move:
    """Find the best move at one complete search depth."""
    moves = ordered_moves(board)

    if not moves:
        raise ValueError("No legal moves available")

    best_score = -MATE_SCORE
    best_moves: list[chess.Move] = []
    best_move_is_draw = True

    for move in moves:
        if time.monotonic() >= deadline:
            raise SearchTimeoutError

        board.push(move)

        try:
            move_is_draw = is_immediate_history_draw(board)

            if move_is_draw:
                score = 0
            else:
                score = alpha_beta(
                    board,
                    depth - 1,
                    -MATE_SCORE,
                    MATE_SCORE,
                    False,
                    mover,
                    deadline,
                )
        finally:
            board.pop()

        if score > best_score or (score == best_score and best_move_is_draw and not move_is_draw):
            best_score = score
            best_moves = [move]
            best_move_is_draw = move_is_draw
        elif score == best_score and move_is_draw == best_move_is_draw:
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
    record_position(board)

    # Always have a legal move available, even if the search times out immediately.
    best_move = random.choice(moves)

    usable_ms = max(1, time_left_ms - CLOCK_MARGIN_MS)
    budget_ms = max(
        1,
        min(MAX_THINK_MS, usable_ms // EXPECTED_MOVES_LEFT),
    )
    deadline = time.monotonic() + budget_ms / 1_000

    for depth in range(1, MAX_SEARCH_DEPTH + 1):
        try:
            completed_move = search_at_depth(board, mover, depth, deadline)
        except SearchTimeoutError:
            break

        # Only save a result after the entire depth completed successfully.
        best_move = completed_move

    board.push(best_move)

    try:
        record_position(board)
    finally:
        board.pop()

    return best_move.uci()
