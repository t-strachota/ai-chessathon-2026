"""Reproducible correctness checks for the original compiled engine."""

import random
import time

import chess
import numpy as np

import agent
from past_models.Gabriel import agent as gabriel

POSITIONS = {
    "start": chess.STARTING_FEN,
    "castle": "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1",
    "ep": "8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - - 0 1",
    "promotion": "r3k2r/Pppp1ppp/1b3nbN/nP6/BBP1P3/q4N2/Pp1P2PP/R2Q1RK1 w kq - 0 1",
    "pinned_ep": "k3r3/8/8/3pP3/8/8/8/4K3 w - d6 0 1",
    "mate": "7k/6Q1/5K2/8/8/8/8/8 b - - 100 1",
    "stalemate": "7k/5K2/6Q1/8/8/8/8/8 b - - 99 1",
    "mopup": "7R/8/5Q2/8/8/4P1k1/8/6K1 w - - 1 64",
    "clock": "8/5R2/8/3Q4/8/4P2k/8/6K1 w - - 93 110",
    "knight": "r1b1k2r/1pq2ppp/p2p1n2/2p1p3/2N2Q2/P1PPP3/3P1PPP/R1B1K2R w KQkq - 0 13",
}


@agent.compiled
def perft(pos: agent.Array, depth: int) -> int:
    if depth == 0:
        return 1
    total = 0
    for move in agent.legal_moves(pos):
        undo = agent.make_move(pos, move)
        total += perft(pos, depth - 1)
        agent.unmake_move(pos, move, undo)
    return total


def reference_perft(board: chess.Board, depth: int) -> int:
    if depth == 0:
        return 1
    total = 0
    for move in list(board.legal_moves):
        board.push(move)
        total += reference_perft(board, depth - 1)
        board.pop()
    return total


def check_position(board: chess.Board) -> int:
    assert board.is_valid(), board.fen()
    pos = agent.encode(board)
    original = pos.copy()
    moves = agent.legal_moves(pos)
    assert {agent.uci(int(m)) for m in moves} == {m.uci() for m in board.legal_moves}, board.fen()
    assert np.array_equal(pos, original)
    assert agent.insufficient(pos) == board.is_insufficient_material(), board.fen()
    if not board.is_game_over():
        assert agent.evaluate(pos) == gabriel.position_score(board, board.turn), (
            board.fen(),
            agent.evaluate(pos),
            gabriel.position_score(board, board.turn),
        )
    for move in moves:
        undo = agent.make_move(pos, int(move))
        board.push_uci(agent.uci(int(move)))
        assert np.array_equal(pos, agent.encode(board)), board.fen()
        board.pop()
        agent.unmake_move(pos, int(move), undo)
        assert np.array_equal(pos, original)
    return len(moves)


def check_draws() -> None:
    for clock in (0, 98, 99, 100):
        b = chess.Board(POSITIONS["clock"])
        b.halfmove_clock = clock
        p = agent.encode(b)
        hist = np.array([agent.position_hash(p)], dtype=np.uint64)
        assert agent.draw_node(p, agent.legal_moves(p), hist, 1) == b.can_claim_fifty_moves()
    b = chess.Board()
    keys = [int(agent.position_hash(agent.encode(b)))]
    for move in ("g1f3", "g8f6", "f3g1", "f6g8", "g1f3", "g8f6", "f3g1"):
        b.push_uci(move)
        keys.append(int(agent.position_hash(agent.encode(b))))
    assert b.can_claim_threefold_repetition() and not b.is_repetition(3)
    p = agent.encode(b)
    assert agent.draw_node(p, agent.legal_moves(p), np.array(keys, dtype=np.uint64), len(keys))
    a = agent.encode(chess.Board(POSITIONS["pinned_ep"]))
    bpos = a.copy()
    bpos[agent.EP] = -1
    assert agent.position_hash(a) == agent.position_hash(bpos)
    legal_ep = chess.Board("k7/8/8/3pP3/8/8/8/4K3 w - d6 0 1")
    a = agent.encode(legal_ep)
    bpos = a.copy()
    bpos[agent.EP] = -1
    assert agent.position_hash(a) != agent.position_hash(bpos)


def check_search() -> None:
    for name in ("start", "ep", "promotion", "knight", "clock"):
        board = chess.Board(POSITIONS[name])
        agent.clear_tables()
        reference = agent.analyze(board, seconds=20, max_depth=3, tt_mode=0)
        for mode in (1, 2):
            agent.clear_tables()
            result = agent.analyze(board, seconds=20, max_depth=3, tt_mode=mode)
            assert result["depth"] == 3 or abs(result["score"]) >= agent.MATE - agent.MAX_PLY
            assert result["score"] == reference["score"], (name, reference, result)
        # Reuse scores from another clock and history: must not contaminate the result.
        board.halfmove_clock = 98
        reused = agent.analyze(board, seconds=20, max_depth=3)
        agent.clear_tables()
        clean = agent.analyze(board, seconds=20, max_depth=3)
        assert clean["score"] == reused["score"], (name, reused, clean)
    for name in ("mate", "stalemate"):
        result = agent.analyze(chess.Board(POSITIONS[name]), max_depth=2)
        assert result["score"] == (-agent.MATE if name == "mate" else 0)
    board = chess.Board(POSITIONS["knight"])
    pos = agent.encode(board)
    original = pos.copy()
    history = np.zeros(100, dtype=np.uint64)
    history[0] = agent.position_hash(pos)
    stats = np.zeros(3, dtype=np.int64)
    agent.search(
        pos,
        10,
        -agent.INF,
        agent.INF,
        0,
        2,
        6,
        history,
        1,
        history[0],
        stats,
        time.monotonic() + 1,
        25,
        agent.TT_KEYS,
        agent.TT_CONTEXT,
        agent.TT_DATA,
        agent.ORDER_KEYS,
        agent.ORDER_MOVES,
        np.zeros((agent.MAX_PLY, 2), dtype=np.int64),
        np.zeros((2, 128, 128), dtype=np.int64),
        2,
        True,
    )
    assert stats[1] == 1 and np.array_equal(pos, original)


def raw_search(
    board: chess.Board, alpha: int, beta: int, ply: int = 0, extensions: int = 3
) -> tuple[int, int]:
    pos = agent.encode(board)
    history = np.zeros(100, dtype=np.uint64)
    history[0] = agent.position_hash(pos)
    stats = np.zeros(3, dtype=np.int64)
    score, _ = agent.search(
        pos,
        3,
        alpha,
        beta,
        ply,
        extensions,
        6,
        history,
        1,
        history[0],
        stats,
        time.monotonic() + 10,
        1000000,
        agent.TT_KEYS,
        agent.TT_CONTEXT,
        agent.TT_DATA,
        agent.ORDER_KEYS,
        agent.ORDER_MOVES,
        np.zeros((agent.MAX_PLY, 2), dtype=np.int64),
        np.zeros((2, 128, 128), dtype=np.int64),
        2,
        True,
    )
    assert not stats[1]
    return score, int(stats[2])


def check_table_bounds() -> None:
    board = chess.Board(POSITIONS["knight"])
    agent.clear_tables()
    expected, _ = raw_search(board, -agent.INF, agent.INF)
    for alpha, beta in ((expected + 1, expected + 2), (expected - 2, expected - 1)):
        agent.clear_tables()
        raw_search(board, alpha, beta)
        actual, _ = raw_search(board, -agent.INF, agent.INF)
        assert actual == expected, (alpha, beta, actual, expected)
    actual, hits = raw_search(board, -agent.INF, agent.INF)
    assert actual == expected and hits > 0
    # An extension-budget mismatch must invalidate a cached score.
    actual, _ = raw_search(board, -agent.INF, agent.INF, extensions=0)
    agent.clear_tables()
    expected_no_extension, _ = raw_search(board, -agent.INF, agent.INF, extensions=0)
    assert actual == expected_no_extension
    # Mate scores stored at the root must be adjusted when reused deeper in a line.
    board = chess.Board(POSITIONS["mopup"])
    agent.clear_tables()
    root_score, _ = raw_search(board, -agent.INF, agent.INF)
    deep_score, hits = raw_search(board, -agent.INF, agent.INF, ply=5)
    assert root_score > agent.MATE - agent.MAX_PLY
    assert deep_score == root_score - 5 and hits > 0
    # Same FEN and clock, but a different repetition history.
    board = chess.Board()
    keys = [int(agent.position_hash(agent.encode(board)))]
    for move in ("g1f3", "g8f6", "f3g1", "f6g8", "g1f3", "g8f6", "f3g1"):
        board.push_uci(move)
        keys.append(int(agent.position_hash(agent.encode(board))))
    agent.analyze(board, seconds=2, max_depth=3)
    drawn = agent.analyze(board, seconds=2, max_depth=3, prior=keys[:-1])
    assert drawn["score"] == 0 and drawn["move"] == ""
    for milliseconds in (10, 50, 100, 500):
        start = time.monotonic()
        move = agent.get_move(chess.STARTING_FEN, milliseconds)
        elapsed = time.monotonic() - start
        assert chess.Move.from_uci(move) in chess.Board().legal_moves
        assert elapsed < milliseconds / 1000, (milliseconds, elapsed)


def main() -> None:
    start = time.monotonic()
    positions, transitions = 0, 0
    for fen in POSITIONS.values():
        b = chess.Board(fen)
        transitions += check_position(b)
        transitions += check_position(b.mirror())
        positions += 2
    for name in ("start", "castle", "ep", "promotion"):
        b = chess.Board(POSITIONS[name])
        depth = 4 if name == "start" else 3
        count = perft(agent.encode(b), depth)
        reference = reference_perft(b, depth)
        assert count == reference, (name, count, reference)
        print("perft", name, depth, count, flush=True)
    rng = random.Random(20260906)
    for _ in range(30):
        b = chess.Board()
        for _ in range(100):
            transitions += check_position(b)
            positions += 1
            if b.is_game_over():
                break
            b.push(rng.choice(list(b.legal_moves)))
    check_draws()
    check_search()
    check_table_bounds()
    print(
        f"PASS: {positions} positions, {transitions} make/undo transitions, "
        f"draws, TT equivalence, timeout restoration; {time.monotonic() - start:.1f}s"
    )


if __name__ == "__main__":
    main()
