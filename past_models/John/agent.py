"""Original compiled chess engine. Only Python source is needed in the submission.

The 0x88 mailbox stores signed pieces on ranks 16 squares apart. Off-board squares
have bit 0x88 set. Slots 128..131 hold turn, castling rights, en passant and clock.
Numba compiles the complete move generator, evaluation and search at import.
"""

import time
from collections.abc import Callable
from typing import Any, cast

import chess
import numpy as np
import numpy.typing as npt
from numba import njit, objmode

Array = npt.NDArray[np.int64]
Keys = npt.NDArray[np.uint64]


def compiled[**P, R](function: Callable[P, R]) -> Callable[P, R]:
    """Keep Python signatures visible to type checking while compiling at import."""
    return cast(Callable[P, R], njit(cache=False)(function))


TURN, RIGHTS, EP, CLOCK = 128, 129, 130, 131
MATE, INF, MAX_PLY = 100000, 200000, 96
VALUES = np.array([0, 100, 320, 330, 500, 900, 0], dtype=np.int64)
PST = np.array(
    [
        [
            [0, 0, 0, 0, 0, 0, 0, 0],
            [0, 0, 0, 0, 0, 0, 0, 0],
            [0, 0, 0, 0, 0, 0, 0, 0],
            [0, 0, 0, 0, 0, 0, 0, 0],
            [0, 0, 0, 0, 0, 0, 0, 0],
            [0, 0, 0, 0, 0, 0, 0, 0],
            [0, 0, 0, 0, 0, 0, 0, 0],
            [0, 0, 0, 0, 0, 0, 0, 0],
        ],
        [
            [0, 0, 0, 0, 0, 0, 0, 0],
            [0, 5, 5, -10, -10, 5, 5, 0],
            [5, 5, 10, 15, 15, 10, 5, 5],
            [5, 10, 15, 22, 22, 15, 10, 5],
            [8, 12, 18, 25, 25, 18, 12, 8],
            [15, 20, 25, 32, 32, 25, 20, 15],
            [30, 35, 40, 45, 45, 40, 35, 30],
            [0, 0, 0, 0, 0, 0, 0, 0],
        ],
        [
            [-40, -25, -15, -10, -10, -15, -25, -40],
            [-25, -10, 0, 5, 5, 0, -10, -25],
            [-15, 0, 10, 15, 15, 10, 0, -15],
            [-10, 5, 15, 22, 22, 15, 5, -10],
            [-10, 5, 15, 22, 22, 15, 5, -10],
            [-15, 0, 10, 15, 15, 10, 0, -15],
            [-25, -10, 0, 5, 5, 0, -10, -25],
            [-40, -25, -15, -10, -10, -15, -25, -40],
        ],
        [
            [-20, -10, -10, -10, -10, -10, -10, -20],
            [-10, 5, 0, 0, 0, 0, 5, -10],
            [-10, 10, 10, 12, 12, 10, 10, -10],
            [-10, 0, 12, 15, 15, 12, 0, -10],
            [-10, 5, 10, 15, 15, 10, 5, -10],
            [-10, 0, 8, 10, 10, 8, 0, -10],
            [-10, 0, 0, 0, 0, 0, 0, -10],
            [-20, -10, -10, -10, -10, -10, -10, -20],
        ],
        [
            [0, 0, 5, 8, 8, 5, 0, 0],
            [5, 10, 10, 10, 10, 10, 10, 5],
            [0, 0, 5, 5, 5, 5, 0, 0],
            [0, 0, 5, 8, 8, 5, 0, 0],
            [0, 0, 5, 8, 8, 5, 0, 0],
            [5, 5, 8, 10, 10, 8, 5, 5],
            [20, 20, 20, 20, 20, 20, 20, 20],
            [5, 5, 5, 10, 10, 5, 5, 5],
        ],
        [
            [-15, -10, -5, 0, 0, -5, -10, -15],
            [-10, 0, 5, 0, 0, 5, 0, -10],
            [-5, 5, 8, 8, 8, 8, 5, -5],
            [0, 0, 8, 10, 10, 8, 0, 0],
            [0, 0, 8, 10, 10, 8, 0, 0],
            [-5, 5, 8, 8, 8, 8, 5, -5],
            [-10, 0, 5, 0, 0, 5, 0, -10],
            [-15, -10, -5, 0, 0, -5, -10, -15],
        ],
        [
            [0, 0, 0, 0, 0, 0, 0, 0],
            [0, 0, 0, 0, 0, 0, 0, 0],
            [0, 0, 0, 0, 0, 0, 0, 0],
            [0, 0, 0, 0, 0, 0, 0, 0],
            [0, 0, 0, 0, 0, 0, 0, 0],
            [0, 0, 0, 0, 0, 0, 0, 0],
            [0, 0, 0, 0, 0, 0, 0, 0],
            [0, 0, 0, 0, 0, 0, 0, 0],
        ],
    ],
    dtype=np.int64,
)
KNIGHT = (-33, -31, -18, -14, 14, 18, 31, 33)
RAYS = (-17, -16, -15, -1, 1, 15, 16, 17)
TABLE_SIZE = 1 << 17
_rng = np.random.default_rng(20260906)
ZOBRIST = _rng.integers(1, 2**63, size=(13, 128), dtype=np.uint64)
STATE_KEYS = _rng.integers(1, 2**63, size=160, dtype=np.uint64)
# Tables are allocated once per game, approximately 10 MB in total.
TT_KEYS = np.zeros(TABLE_SIZE, dtype=np.uint64)
TT_CONTEXT = np.zeros(TABLE_SIZE, dtype=np.uint64)
# depth, score, bound (1 exact, 2 lower, 3 upper), move, extension budget
TT_DATA = np.zeros((TABLE_SIZE, 5), dtype=np.int64)
ORDER_KEYS = np.zeros(TABLE_SIZE, dtype=np.uint64)
ORDER_MOVES = np.zeros(TABLE_SIZE, dtype=np.int64)
_HISTORY: list[int] = []
_LAST_FEN: str | None = None
LAST_SEARCH: dict[str, int | float] = {}
_SEARCH_CONFIG: tuple[bool, bool] | None = None


@compiled
def attacked(pos: Array, square: int, side: int) -> bool:
    for offset in (-17, -15):
        source = square + offset * side
        if not source & 0x88 and pos[source] == side:
            return True
    for offset in KNIGHT:
        source = square + offset
        if not source & 0x88 and pos[source] == 2 * side:
            return True
    for offset in RAYS:
        source = square + offset
        distance = 1
        while not source & 0x88:
            piece = pos[source]
            if piece:
                if piece * side > 0:
                    kind = abs(piece)
                    diagonal = abs(offset) in (15, 17)
                    if kind == 5 or (kind == 6 and distance == 1):
                        return True
                    if (diagonal and kind == 3) or (not diagonal and kind == 4):
                        return True
                break
            source += offset
            distance += 1
    return False


@compiled
def king_square(pos: Array, side: int) -> int:
    for square in range(128):
        if not square & 0x88 and pos[square] == side * 6:
            return square
    return -1


@compiled
def in_check(pos: Array, side: int) -> bool:
    square = king_square(pos, side)
    return square < 0 or attacked(pos, square, -side)


@compiled
def pack(source: int, target: int, promotion: int = 0) -> int:
    return source | (target << 7) | (promotion << 14)


@compiled
def make_move(pos: Array, move: int) -> Array:
    source, target, promotion = move & 127, (move >> 7) & 127, move >> 14
    piece, side = pos[source], pos[TURN]
    capture_square = target
    if abs(piece) == 1 and target == pos[EP] and pos[target] == 0:
        capture_square = target - 16 * side
    undo = np.array(
        [pos[capture_square], capture_square, pos[RIGHTS], pos[EP], pos[CLOCK], piece],
        dtype=np.int64,
    )
    pos[capture_square] = 0
    pos[source] = 0
    pos[target] = side * promotion if promotion else piece
    if abs(piece) == 6 and abs(target - source) == 2:
        rook_from = source + 3 if target > source else source - 4
        rook_to = source + 1 if target > source else source - 1
        pos[rook_from] = 0
        pos[rook_to] = side * 4
    rights = pos[RIGHTS]
    if abs(piece) == 6:
        rights &= 12 if side == 1 else 3
    for square, mask in ((0, 2), (7, 1), (112, 8), (119, 4)):
        if source == square or target == square:
            rights &= ~mask
    pos[RIGHTS] = rights
    pos[EP] = (source + target) // 2 if abs(piece) == 1 and abs(target - source) == 32 else -1
    pos[CLOCK] = 0 if abs(piece) == 1 or undo[0] else pos[CLOCK] + 1
    pos[TURN] = -side
    return undo


@compiled
def unmake_move(pos: Array, move: int, undo: Array) -> None:
    source, target = move & 127, (move >> 7) & 127
    side = -pos[TURN]
    pos[target] = 0
    pos[source] = undo[5]
    pos[undo[1]] = undo[0]
    if abs(undo[5]) == 6 and abs(target - source) == 2:
        rook_from = source + 3 if target > source else source - 4
        rook_to = source + 1 if target > source else source - 1
        pos[rook_to] = 0
        pos[rook_from] = side * 4
    pos[RIGHTS], pos[EP], pos[CLOCK], pos[TURN] = undo[2], undo[3], undo[4], side


@compiled
def append_pawn(moves: Array, count: int, source: int, target: int) -> int:
    if target // 16 in (0, 7):
        for promotion in (5, 4, 3, 2):
            moves[count] = pack(source, target, promotion)
            count += 1
    else:
        moves[count] = pack(source, target)
        count += 1
    return count


@compiled
def legal_moves(pos: Array) -> Array:
    moves = np.empty(256, dtype=np.int64)
    count, side = 0, pos[TURN]
    for source in range(128):
        if source & 0x88 or pos[source] * side <= 0:
            continue
        kind = abs(pos[source])
        if kind == 1:
            target = source + 16 * side
            if not target & 0x88 and pos[target] == 0:
                count = append_pawn(moves, count, source, target)
                start_rank = 1 if side == 1 else 6
                if source // 16 == start_rank and pos[target + 16 * side] == 0:
                    moves[count] = pack(source, target + 16 * side)
                    count += 1
            for offset in (15, 17):
                target = source + side * offset
                if not target & 0x88 and (pos[target] * side < 0 or target == pos[EP]):
                    count = append_pawn(moves, count, source, target)
        elif kind == 2:
            for offset in KNIGHT:
                target = source + offset
                if not target & 0x88 and pos[target] * side <= 0:
                    moves[count] = pack(source, target)
                    count += 1
        else:
            for offset in RAYS:
                diagonal = abs(offset) in (15, 17)
                if (kind == 3 and not diagonal) or (kind == 4 and diagonal):
                    continue
                target = source + offset
                while not target & 0x88:
                    if pos[target] * side > 0:
                        break
                    moves[count] = pack(source, target)
                    count += 1
                    if pos[target] or kind == 6:
                        break
                    target += offset
            home = 4 if side == 1 else 116
            if kind == 6 and source == home and not attacked(pos, home, -side):
                shift = 0 if side == 1 else 2
                if (
                    pos[RIGHTS] & (1 << shift)
                    and pos[home + 3] == 4 * side
                    and pos[home + 1] == 0
                    and pos[home + 2] == 0
                    and not attacked(pos, home + 1, -side)
                    and not attacked(pos, home + 2, -side)
                ):
                    moves[count] = pack(home, home + 2)
                    count += 1
                if (
                    pos[RIGHTS] & (2 << shift)
                    and pos[home - 4] == 4 * side
                    and pos[home - 1] == 0
                    and pos[home - 2] == 0
                    and pos[home - 3] == 0
                    and not attacked(pos, home - 1, -side)
                    and not attacked(pos, home - 2, -side)
                ):
                    moves[count] = pack(home, home - 2)
                    count += 1
    valid = 0
    for i in range(count):
        move = moves[i]
        undo = make_move(pos, move)
        ok = not in_check(pos, side)
        unmake_move(pos, move, undo)
        if ok:
            moves[valid] = move
            valid += 1
    return moves[:valid]


@compiled
def position_hash(pos: Array) -> np.uint64:
    key = STATE_KEYS[pos[RIGHTS]]
    if pos[TURN] == -1:
        key ^= STATE_KEYS[16]
    for square in range(128):
        if not square & 0x88 and pos[square]:
            key ^= ZOBRIST[pos[square] + 6, square]
    ep, side = pos[EP], pos[TURN]
    if ep >= 0:
        # EP changes repetition identity only when an EP capture is actually legal.
        for offset in (15, 17):
            source = ep - offset * side
            if not source & 0x88 and pos[source] == side:
                move = pack(source, ep)
                undo = make_move(pos, move)
                ok = not in_check(pos, side)
                unmake_move(pos, move, undo)
                if ok:
                    key ^= STATE_KEYS[17 + ep]
                    break
    return np.uint64(key)


@compiled
def insufficient(pos: Array) -> bool:
    minors, knights, bishop_color = 0, 0, -1
    same_color = True
    for square in range(128):
        if square & 0x88:
            continue
        kind = abs(pos[square])
        if kind in (1, 4, 5):
            return False
        if kind in (2, 3):
            minors += 1
            if kind == 2:
                knights += 1
            else:
                color = (square // 16 + square % 16) % 2
                if bishop_color >= 0 and color != bishop_color:
                    same_color = False
                bishop_color = color
    return minors <= 1 or (knights == 0 and same_color)


@compiled
def passed_pawn(pos: Array, square: int, side: int) -> bool:
    for file_offset in (-1, 0, 1):
        target = square + 16 * side + file_offset
        while not target & 0x88:
            if pos[target] == -side:
                return False
            target += 16 * side
    return True


@compiled
def passer_bonus(pos: Array, square: int, side: int, safe_passers: bool = True) -> int:
    """Discount advanced passers whose progress is blocked or vulnerable.

    Attack maps are positional hints, not proof of a winning promotion. Search
    still resolves captures, pins and sacrifices. Keep Gabriel's bonus ceiling.
    """
    rank = square // 16 if side == 1 else 7 - square // 16
    bonus = (0, 0, 10, 25, 60, 180, 500, 0)[rank]
    if not safe_passers or rank < 4 or rank > 6:
        return bonus
    forward = square + 16 * side
    if pos[forward]:
        bonus //= 4
    elif attacked(pos, forward, -side):
        bonus = bonus * 3 // 4 if attacked(pos, forward, side) else bonus // 2
    if attacked(pos, square, -side) and not attacked(pos, square, side):
        bonus //= 2
    if rank == 5:
        promotion = square % 16 + (112 if side == 1 else 0)
        if pos[promotion] or (
            attacked(pos, promotion, -side) and not attacked(pos, promotion, side)
        ):
            bonus = bonus * 3 // 4
    return bonus


@compiled
def evaluate(pos: Array, move_count: int = -1, safe_passers: bool = True) -> int:
    """Side-to-move evaluation; search supplies its already generated move count."""
    score, material = 0, 0
    kings = np.zeros(2, dtype=np.int64)
    others = np.zeros(2, dtype=np.int64)
    danger = np.zeros(2, dtype=np.int64)
    for square in range(128):
        if square & 0x88 or pos[square] == 0:
            continue
        piece = pos[square]
        side = 1 if piece > 0 else -1
        index = 0 if side == 1 else 1
        kind = abs(piece)
        if kind == 6:
            kings[index] = square
            continue
        others[index] += 1
        if kind == 5:
            danger[index] = 2
        elif kind == 4:
            danger[index] = max(danger[index], 1)
        rank = square // 16 if side == 1 else 7 - square // 16
        material += side * VALUES[kind]
        score += side * PST[kind, rank, square % 16]
        if kind == 1 and passed_pawn(pos, square, side):
            score += side * passer_bonus(pos, square, side, safe_passers)
    for index in range(2):
        side = 1 if index == 0 else -1
        king, enemy = kings[index], kings[1 - index]
        if danger[1 - index]:
            shield, ring = 0, int(attacked(pos, king, -side))
            for offset in (15, 16, 17):
                target = king + side * offset
                if not target & 0x88 and pos[target] == side:
                    shield += 1
            for offset in RAYS:
                target = king + offset
                if not target & 0x88 and attacked(pos, target, -side):
                    ring += 1
            score += side * danger[1 - index] * (shield * 12 - ring * 8)
        if others[1 - index] == 0 and danger[index]:
            distance = max(abs(king % 16 - enemy % 16), abs(king // 16 - enemy // 16))
            edge = abs(2 * (enemy % 16) - 7) + abs(2 * (enemy // 16) - 7)
            escapes = 0
            for offset in RAYS:
                target = enemy + offset
                if (
                    not target & 0x88
                    and pos[target] * side >= 0
                    and not attacked(pos, target, side)
                ):
                    escapes += 1
            score += side * (edge * 10 + (7 - distance) * 12 + (8 - escapes) * 12)
    if abs(material) >= 500:
        urgency = max(0, pos[CLOCK] - 40) * 4
        score += -urgency if material > 0 else urgency
    if move_count < 0:
        move_count = len(legal_moves(pos))
    return int((score + material) * pos[TURN] + 4 * move_count)


@compiled
def draw_node(pos: Array, moves: Array, history: Keys, length: int) -> bool:
    if insufficient(pos):
        return True
    if pos[CLOCK] >= 100:
        return True
    if pos[CLOCK] == 99:
        for move in moves:
            undo = make_move(pos, move)
            # A move ending in mate/stalemate does not create a fifty-move claim.
            claim = pos[CLOCK] >= 100 and len(legal_moves(pos)) > 0
            unmake_move(pos, move, undo)
            if claim:
                return True
    current = history[length - 1]
    occurrences = 0
    start = max(0, length - 1 - pos[CLOCK])
    duplicate = False
    for i in range(start, length):
        if history[i] == current:
            occurrences += 1
        for j in range(start, i):
            if history[i] == history[j]:
                duplicate = True
                break
    if occurrences >= 3:
        return True
    if duplicate:
        # The referee claims even if the third occurrence is only available next move.
        for move in moves:
            undo = make_move(pos, move)
            key = position_hash(pos)
            unmake_move(pos, move, undo)
            count = 0
            for i in range(start, length):
                if history[i] == key:
                    count += 1
            if count >= 2:
                return True
    return False


@compiled
def move_priority(
    pos: Array, move: int, hint: int, ply: int, killers: Array, history_order: Array, ordering: bool
) -> int:
    if not ordering:
        return 0
    if move == hint:
        return 2000000
    source, target, promotion = move & 127, (move >> 7) & 127, move >> 14
    victim = abs(pos[target])
    if victim or (abs(pos[source]) == 1 and target == pos[EP]):
        if victim == 0:
            victim = 1
        return int(100000 + VALUES[victim] * 16 - VALUES[abs(pos[source])] + promotion * 10000)
    if promotion:
        return int(150000 + VALUES[promotion])
    if move == killers[ply, 0]:
        return 90000
    if move == killers[ply, 1]:
        return 80000
    side_index = 0 if pos[TURN] == 1 else 1
    return int(history_order[side_index, source, target])


@compiled
def search(
    pos: Array,
    depth: int,
    alpha: int,
    beta: int,
    ply: int,
    extensions: int,
    qleft: int,
    history: Keys,
    length: int,
    context: np.uint64,
    stats: Array,
    deadline: float,
    node_limit: int,
    tt_keys: Keys,
    tt_context: Keys,
    tt_data: Array,
    order_keys: Keys,
    order_moves: Array,
    killers: Array,
    history_order: Array,
    tt_mode: int,
    ordering: bool,
    pvs: bool = True,
    safe_passers: bool = True,
) -> tuple[int, int]:
    stats[0] += 1
    if stats[0] >= node_limit:
        stats[1] = 1
    if stats[0] % 256 == 0:
        with objmode(now="float64"):
            now = time.monotonic()
        if now >= deadline:
            stats[1] = 1
    if stats[1]:
        return 0, 0
    moves = legal_moves(pos)
    checked = in_check(pos, pos[TURN])
    if len(moves) == 0:
        return (-MATE + ply if checked else 0), 0
    if draw_node(pos, moves, history, length):
        return 0, 0
    if ply >= MAX_PLY - 1:
        return evaluate(pos, len(moves), safe_passers), 0
    key = history[length - 1]
    slot = int(key % np.uint64(TABLE_SIZE))
    # Full reversible-history multiset, clock and remaining extension budget must
    # match before using a score. A separate position-only table supplies move hints.
    signature = context ^ STATE_KEYS[32 + min(100, pos[CLOCK])]
    hint = 0
    if tt_mode and order_keys[slot] == key:
        hint = order_moves[slot]
    original_alpha = alpha
    if (
        depth > 0
        and tt_mode == 2
        and tt_keys[slot] == key
        and tt_context[slot] == signature
        and tt_data[slot, 4] == extensions
        and tt_data[slot, 0] >= depth
    ):
        value = tt_data[slot, 1]
        if value > MATE - MAX_PLY:
            value -= ply
        elif value < -MATE + MAX_PLY:
            value += ply
        bound = tt_data[slot, 2]
        if bound == 1 or (bound == 2 and value >= beta) or (bound == 3 and value <= alpha):
            stats[2] += 1
            return int(value), int(tt_data[slot, 3])
    best, best_move = -INF, 0
    quiet_search = depth <= 0
    if quiet_search:
        # A checked position is not quiet: resolve evasions even at the q cap.
        # Repeated checks remain bounded by draws, MAX_PLY and the deadline.
        if qleft <= 0 and not checked:
            return evaluate(pos, len(moves), safe_passers), 0
        if not checked:
            best = evaluate(pos, len(moves), safe_passers)
            if best >= beta:
                return best, 0
            alpha = max(alpha, best)
    scores = np.empty(len(moves), dtype=np.int64)
    for i in range(len(moves)):
        scores[i] = move_priority(pos, moves[i], hint, ply, killers, history_order, ordering)
    for i in range(len(moves)):
        pick = i
        for j in range(i + 1, len(moves)):
            if scores[j] > scores[pick]:
                pick = j
        moves[i], moves[pick] = moves[pick], moves[i]
        scores[i], scores[pick] = scores[pick], scores[i]
        move = moves[i]
        source, target, promotion = move & 127, (move >> 7) & 127, move >> 14
        pawn = abs(pos[source]) == 1
        side = pos[TURN]
        rank = target // 16 if side == 1 else 7 - target // 16
        capture = pos[target] != 0 or (pawn and target == pos[EP])
        advanced = pawn and rank >= 5 and not promotion and passed_pawn(pos, target, side)
        if quiet_search and not checked and not (capture or promotion or advanced):
            continue
        undo = make_move(pos, move)
        child_key = position_hash(pos)
        history[length] = child_key
        child_context = child_key if pos[CLOCK] == 0 else context + child_key
        extra = 0
        consumed = 0
        if depth > 0:
            if extensions & 1 and in_check(pos, -side):
                consumed |= 1
            if extensions & 2 and advanced:
                consumed |= 2
            extra = int(consumed != 0)
        scout = pvs and not quiet_search and i > 0 and beta > alpha + 1
        child_beta = alpha + 1 if scout else beta
        if scout and len(stats) > 3:
            stats[3] += 1
        value, _ = search(
            pos,
            max(0, depth - 1 + extra),
            -child_beta,
            -alpha,
            ply + 1,
            extensions & ~consumed,
            qleft - 1 if quiet_search else qleft,
            history,
            length + 1,
            child_context,
            stats,
            deadline,
            node_limit,
            tt_keys,
            tt_context,
            tt_data,
            order_keys,
            order_moves,
            killers,
            history_order,
            tt_mode,
            ordering,
            pvs,
            safe_passers,
        )
        value = -value
        if not stats[1] and scout and alpha < value < beta:
            # A scout only supplies a bound. Resolve an improving move with
            # the full window before accepting its score as an exact result.
            if len(stats) > 4:
                stats[4] += 1
            value, _ = search(
                pos,
                max(0, depth - 1 + extra),
                -beta,
                -alpha,
                ply + 1,
                extensions & ~consumed,
                qleft,
                history,
                length + 1,
                child_context,
                stats,
                deadline,
                node_limit,
                tt_keys,
                tt_context,
                tt_data,
                order_keys,
                order_moves,
                killers,
                history_order,
                tt_mode,
                ordering,
                pvs,
                safe_passers,
            )
            value = -value
        unmake_move(pos, move, undo)
        if stats[1]:
            return 0, 0
        if value > best:
            best, best_move = value, move
        alpha = max(alpha, value)
        if alpha >= beta:
            if not capture and not promotion and depth > 0:
                if killers[ply, 0] != move:
                    killers[ply, 1] = killers[ply, 0]
                    killers[ply, 0] = move
                index = 0 if side == 1 else 1
                history_order[index, source, target] = min(
                    60000, history_order[index, source, target] + depth * depth
                )
            break
    if depth > 0 and best_move and tt_mode:
        order_keys[slot], order_moves[slot] = key, best_move
        if tt_mode == 2:
            stored = best
            if best > MATE - MAX_PLY:
                stored += ply
            elif best < -MATE + MAX_PLY:
                stored -= ply
            tt_keys[slot], tt_context[slot] = key, signature
            tt_data[slot, 0], tt_data[slot, 1] = depth, stored
            tt_data[slot, 2] = 3 if best <= original_alpha else 2 if best >= beta else 1
            tt_data[slot, 3], tt_data[slot, 4] = best_move, extensions
    return int(best), int(best_move)


def encode(board: chess.Board) -> Array:
    pos = np.zeros(132, dtype=np.int64)
    for square, piece in board.piece_map().items():
        pos[(square // 8) * 16 + square % 8] = piece.piece_type * (1 if piece.color else -1)
    pos[TURN] = 1 if board.turn else -1
    pos[RIGHTS] = (
        int(board.has_kingside_castling_rights(chess.WHITE))
        + 2 * int(board.has_queenside_castling_rights(chess.WHITE))
        + 4 * int(board.has_kingside_castling_rights(chess.BLACK))
        + 8 * int(board.has_queenside_castling_rights(chess.BLACK))
    )
    pos[EP] = -1 if board.ep_square is None else board.ep_square // 8 * 16 + board.ep_square % 8
    pos[CLOCK] = board.halfmove_clock
    return pos


def uci(move: int) -> str:
    source, target, promotion = move & 127, (move >> 7) & 127, move >> 14
    return chess.Move(
        source // 16 * 8 + source % 16, target // 16 * 8 + target % 16, promotion or None
    ).uci()


def time_budget(time_left_ms: int) -> tuple[float, float]:
    """Normal allowance and absolute search limit, in seconds.

    Reserve up to one second for returning moves and later clock pressure.
    Never budget an increment that has not yet arrived.
    """
    reserve = min(1000.0, max(50.0, time_left_ms * 0.05))
    available = max(0.0, (time_left_ms - reserve) / 1000)
    normal = min(3.0, available / 40)
    hard = min(9.0, normal * 3, available * 0.1)
    return normal, hard


def analyze(
    board: chess.Board,
    seconds: float = 1.0,
    max_depth: int = 32,
    tt_mode: int = 2,
    ordering: bool = True,
    node_limit: int = 1000000000,
    prior: list[int] | None = None,
    pvs: bool = True,
    safe_passers: bool = True,
    soft_seconds: float | None = None,
) -> dict[str, Any]:
    """Instrumented search; seconds is always the hard limit.

    Optional soft_seconds enables adaptive stopping between completed depths.
    Omitting it preserves fixed-budget diagnostics and import warm-up behavior.
    """
    global _SEARCH_CONFIG
    start = time.monotonic()
    config = (pvs, safe_passers)
    if config != _SEARCH_CONFIG:
        # Diagnostic switches must never reuse scores from another evaluator.
        clear_tables()
        _SEARCH_CONFIG = config
    pos = encode(board)
    keys = list(prior) if prior is not None else []
    keys.append(int(position_hash(pos)))
    history = np.zeros(len(keys) + MAX_PLY + 2, dtype=np.uint64)
    history[: len(keys)] = keys
    reversible_start = max(0, len(keys) - 1 - board.halfmove_clock)
    context = np.uint64(sum(keys[reversible_start:]) % (1 << 64))
    # nodes, stopped, TT cutoffs, PVS probes, PVS full-window re-searches
    stats = np.zeros(5, dtype=np.int64)
    killers = np.zeros((MAX_PLY, 2), dtype=np.int64)
    history_order = np.zeros((2, 128, 128), dtype=np.int64)
    deadline = start + max(0.0001, seconds)
    result: dict[str, Any] = dict(move="", score=0, depth=0)
    normal = min(seconds, max(0.0, soft_seconds)) if soft_seconds is not None else seconds
    stable, volatile, previous_move, previous_score = 0, 0, 0, 0
    previous_duration = 0.0
    target = normal
    extra_time_used = False
    iterations: list[dict[str, int | float | str]] = []
    for depth in range(1, max_depth + 1):
        iteration_start = time.monotonic()
        # Extra time must be earned by an instability seen at a completed depth.
        # Starting an expensive iteration alone must not unlock the hard limit.
        extension_allowed = soft_seconds is not None and volatile > 0
        iteration_deadline = deadline
        if soft_seconds is not None and not extension_allowed:
            iteration_deadline = min(deadline, start + normal)
        if iteration_start >= iteration_deadline:
            break
        score, move = search(
            pos,
            depth,
            -INF,
            INF,
            0,
            3,
            6,
            history,
            len(keys),
            context,
            stats,
            iteration_deadline,
            node_limit,
            TT_KEYS,
            TT_CONTEXT,
            TT_DATA,
            ORDER_KEYS,
            ORDER_MOVES,
            killers,
            history_order,
            tt_mode,
            ordering,
            pvs,
            safe_passers,
        )
        now = time.monotonic()
        if extension_allowed and now - start > normal:
            extra_time_used = True
        if stats[1]:
            break
        result.update(move=uci(move) if move else "", score=int(score), depth=depth)
        duration = now - iteration_start
        volatile = max(0, volatile - 1)
        if previous_move:
            delta = score - previous_score
            stable = stable + 1 if move == previous_move and abs(delta) <= 25 else 0
            if depth >= 3 and (move != previous_move or delta <= -60):
                volatile = 2
        target = min(seconds, normal * (2.5 if volatile else 0.7 if stable >= 3 else 1.0))
        iterations.append(
            dict(
                depth=depth,
                move=result["move"],
                score=int(score),
                seconds=now - start,
                target_seconds=target,
                deadline_seconds=iteration_deadline - start,
            )
        )
        if abs(score) >= MATE - MAX_PLY or not move:
            break
        if soft_seconds is not None:
            if now - start >= target:
                break
            # Avoid starting a likely unfinished iteration on a stable move.
            # Unstable searches may use the hard deadline to seek a better line.
            growth = min(6.0, max(2.0, duration / max(previous_duration, 0.0001)))
            if (
                stable >= 3
                and not volatile
                and depth >= 4
                and now - start >= normal * 0.35
                and now - start + duration * growth > target
            ):
                break
        previous_move, previous_score, previous_duration = move, score, duration
    elapsed = time.monotonic() - start
    result.update(
        nodes=int(stats[0]),
        tt_hits=int(stats[2]),
        pvs_probes=int(stats[3]),
        pvs_researches=int(stats[4]),
        seconds=elapsed,
        nps=int(stats[0] / max(elapsed, 1e-9)),
        normal_seconds=normal,
        hard_seconds=seconds,
        extended=int(extra_time_used),
        iterations=iterations,
    )
    return result


def clear_tables() -> None:
    TT_KEYS.fill(0)
    TT_CONTEXT.fill(0)
    TT_DATA.fill(0)
    ORDER_KEYS.fill(0)
    ORDER_MOVES.fill(0)


def get_move(fen: str, time_left_ms: int) -> str:
    global _LAST_FEN
    start = time.monotonic()
    board = chess.Board(fen)
    moves = list(board.legal_moves)
    if not moves:
        raise ValueError("No legal moves")
    # New games get fresh processes. Also support local reuse after a FEN rewind.
    if _LAST_FEN is not None:
        previous = chess.Board(_LAST_FEN)
        if board.fullmove_number < previous.fullmove_number or fen == _LAST_FEN:
            _HISTORY.clear()
            clear_tables()
    normal, hard = time_budget(time_left_ms)
    remaining = hard - (time.monotonic() - start)
    if len(moves) == 1 or time_left_ms <= 100 or remaining <= 0.002:
        # Still record real-game history below, even when no search is needed.
        result: dict[str, Any] = dict(
            move=moves[0].uci(),
            nodes=0,
            depth=0,
            tt_hits=0,
            nps=0,
            pvs_probes=0,
            pvs_researches=0,
            extended=0,
        )
    else:
        result = analyze(board, remaining, prior=_HISTORY, soft_seconds=normal)
    choice = chess.Move.from_uci(result["move"]) if result["move"] else moves[0]
    if choice not in board.legal_moves:
        choice = moves[0]
    _HISTORY.append(int(position_hash(encode(board))))
    board.push(choice)
    _HISTORY.append(int(position_hash(encode(board))))
    _LAST_FEN = fen
    LAST_SEARCH.clear()
    LAST_SEARCH.update(
        {
            key: result[key]
            for key in ("nodes", "depth", "tt_hits", "nps", "pvs_probes", "pvs_researches")
        }
    )
    LAST_SEARCH["seconds"] = time.monotonic() - start
    LAST_SEARCH["normal_seconds"] = normal
    LAST_SEARCH["hard_seconds"] = hard
    LAST_SEARCH["extended"] = result["extended"]
    return choice.uci()


# Compile the exact signatures used by get_move, including recursive search, at import.
_WARMUP_START = time.monotonic()
analyze(chess.Board(), seconds=60.0, max_depth=2, node_limit=10000)
clear_tables()
INIT_SECONDS = time.monotonic() - _WARMUP_START
