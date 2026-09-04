"""Run observable local matches without changing the competition harness."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import chess
import chess.pgn

from harness.referee import FAILED_TERMINATIONS, PIECE_VALUES, RESULT_HEADERS
from harness.rules import INIT_BUDGET_S, PLY_CAP
from harness.sandbox import Agent, AgentFailure, local

Result = Literal["white", "black", "draw", "void"]


@dataclass(frozen=True)
class SeriesConfig:
    """All user-selected settings for one series."""

    competitor_a_name: str
    competitor_a_path: Path
    competitor_b_name: str
    competitor_b_path: Path
    games: int
    base_ms: int
    increment_ms: int
    ply_cap: int = PLY_CAP


@dataclass(frozen=True)
class GameStarted:
    """Describe the colors at the beginning of a game."""

    game_number: int
    total_games: int
    white_name: str
    black_name: str
    competitor_a_is_white: bool
    initial_fen: str
    base_ms: int


@dataclass(frozen=True)
class AgentStatus:
    """Describe initialization or other non-move work."""

    message: str


@dataclass(frozen=True)
class MoveStarted:
    """Tell the GUI that an agent has started thinking."""

    color: chess.Color
    player_name: str
    remaining_ms: int
    started_at: float


@dataclass(frozen=True)
class PositionChanged:
    """Provide a new board position after a legal move."""

    fen: str
    last_move_uci: str
    last_move_san: str
    ply: int
    white_ms: int
    black_ms: int


@dataclass(frozen=True)
class GameSummary:
    """Store the final result and PGN for one game."""

    game_number: int
    white_name: str
    black_name: str
    competitor_a_is_white: bool
    result: Result
    termination: str
    plies: int
    pgn: str
    final_fen: str
    white_ms: int
    black_ms: int

    @property
    def technical_failure(self) -> bool:
        """Return whether the game ended through an agent or protocol failure."""
        return self.termination in FAILED_TERMINATIONS


@dataclass(frozen=True)
class SeriesFinished:
    """Tell the GUI whether the requested series completed."""

    completed_games: int
    cancelled: bool


@dataclass(frozen=True)
class MatchError:
    """Report an unexpected helper error to the GUI."""

    message: str


type MatchEvent = (
    GameStarted
    | AgentStatus
    | MoveStarted
    | PositionChanged
    | GameSummary
    | SeriesFinished
    | MatchError
)
type EventCallback = Callable[[MatchEvent], None]


class MatchCancelled(Exception):
    """Signal a user-requested cancellation between agent operations."""


def discover_models(repository: Path) -> dict[str, Path]:
    """Find the working agent, baselines, and saved models in display order."""
    models: dict[str, Path] = {}

    if (repository / "agent.py").is_file():
        models["Current agent (working tree)"] = repository

    groups = (
        ("Baseline", repository / "baselines"),
        ("Past model", repository / "past_models"),
    )
    for group_name, parent in groups:
        if not parent.is_dir():
            continue
        for directory in sorted(parent.iterdir(), key=lambda path: path.name.casefold()):
            if directory.is_dir() and (directory / "agent.py").is_file():
                models[f"{group_name} / {directory.name}"] = directory

    return models


def run_series(
    config: SeriesConfig,
    callback: EventCallback,
    cancel_event: threading.Event,
) -> None:
    """Run games serially, alternating which competitor receives White."""
    completed_games = 0

    try:
        for game_index in range(config.games):
            if cancel_event.is_set():
                raise MatchCancelled

            game_number = game_index + 1
            competitor_a_is_white = game_index % 2 == 0
            if competitor_a_is_white:
                white_name = config.competitor_a_name
                white_path = config.competitor_a_path
                black_name = config.competitor_b_name
                black_path = config.competitor_b_path
            else:
                white_name = config.competitor_b_name
                white_path = config.competitor_b_path
                black_name = config.competitor_a_name
                black_path = config.competitor_a_path

            callback(
                GameStarted(
                    game_number=game_number,
                    total_games=config.games,
                    white_name=white_name,
                    black_name=black_name,
                    competitor_a_is_white=competitor_a_is_white,
                    initial_fen=chess.STARTING_FEN,
                    base_ms=config.base_ms,
                )
            )
            summary = _play_observable_game(
                game_number=game_number,
                white_name=white_name,
                white_path=white_path,
                black_name=black_name,
                black_path=black_path,
                competitor_a_is_white=competitor_a_is_white,
                base_ms=config.base_ms,
                increment_ms=config.increment_ms,
                ply_cap=config.ply_cap,
                callback=callback,
                cancel_event=cancel_event,
            )
            completed_games += 1
            callback(summary)
    except MatchCancelled:
        callback(SeriesFinished(completed_games=completed_games, cancelled=True))
    except Exception as error:  # Keep an unexpected helper failure visible in the GUI.
        callback(MatchError(message=f"{type(error).__name__}: {error}"))
        callback(SeriesFinished(completed_games=completed_games, cancelled=True))
    else:
        callback(SeriesFinished(completed_games=completed_games, cancelled=False))


def _play_observable_game(
    *,
    game_number: int,
    white_name: str,
    white_path: Path,
    black_name: str,
    black_path: Path,
    competitor_a_is_white: bool,
    base_ms: int,
    increment_ms: int,
    ply_cap: int,
    callback: EventCallback,
    cancel_event: threading.Event,
) -> GameSummary:
    board = chess.Board()
    white = local(white_path)
    black = local(black_path)
    agents = {chess.WHITE: white, chess.BLACK: black}
    names = {chess.WHITE: white_name, chess.BLACK: black_name}
    clock = {chess.WHITE: float(base_ms), chess.BLACK: float(base_ms)}

    try:
        callback(AgentStatus(message=f"Game {game_number}: starting {white_name}"))
        white_failure = _start_agent(white)
        callback(AgentStatus(message=f"Game {game_number}: starting {black_name}"))
        black_failure = _start_agent(black)

        if cancel_event.is_set():
            raise MatchCancelled
        if white_failure is not None and black_failure is not None:
            return _summary(
                board,
                game_number,
                white_name,
                black_name,
                competitor_a_is_white,
                "void",
                "both_failed",
                clock,
                base_ms,
                increment_ms,
            )
        if white_failure is not None:
            return _summary(
                board,
                game_number,
                white_name,
                black_name,
                competitor_a_is_white,
                "black",
                white_failure,
                clock,
                base_ms,
                increment_ms,
            )
        if black_failure is not None:
            return _summary(
                board,
                game_number,
                white_name,
                black_name,
                competitor_a_is_white,
                "white",
                black_failure,
                clock,
                base_ms,
                increment_ms,
            )

        while True:
            if cancel_event.is_set():
                raise MatchCancelled

            finish = board.outcome(claim_draw=True)
            if finish is not None:
                result: Result
                if finish.winner is None:
                    result = "draw"
                else:
                    result = "white" if finish.winner == chess.WHITE else "black"
                return _summary(
                    board,
                    game_number,
                    white_name,
                    black_name,
                    competitor_a_is_white,
                    result,
                    finish.termination.name.lower(),
                    clock,
                    base_ms,
                    increment_ms,
                )

            if len(board.move_stack) >= ply_cap:
                return _summary(
                    board,
                    game_number,
                    white_name,
                    black_name,
                    competitor_a_is_white,
                    _adjudicate(board),
                    "adjudication",
                    clock,
                    base_ms,
                    increment_ms,
                )

            mover = board.turn
            started_at = time.monotonic()
            callback(
                MoveStarted(
                    color=mover,
                    player_name=names[mover],
                    remaining_ms=max(0, round(clock[mover])),
                    started_at=started_at,
                )
            )
            try:
                uci = agents[mover].move(board.fen(), int(clock[mover]))
            except AgentFailure as failure:
                return _summary(
                    board,
                    game_number,
                    white_name,
                    black_name,
                    competitor_a_is_white,
                    _opponent_wins(mover),
                    failure.reason,
                    clock,
                    base_ms,
                    increment_ms,
                )

            clock[mover] -= (time.monotonic() - started_at) * 1_000.0
            if clock[mover] < 0:
                return _summary(
                    board,
                    game_number,
                    white_name,
                    black_name,
                    competitor_a_is_white,
                    _opponent_wins(mover),
                    "flag",
                    clock,
                    base_ms,
                    increment_ms,
                )

            move = _legal_move(board, uci)
            if move is None:
                return _summary(
                    board,
                    game_number,
                    white_name,
                    black_name,
                    competitor_a_is_white,
                    _opponent_wins(mover),
                    "illegal",
                    clock,
                    base_ms,
                    increment_ms,
                )

            san = board.san(move)
            board.push(move)
            clock[mover] += increment_ms
            callback(
                PositionChanged(
                    fen=board.fen(),
                    last_move_uci=move.uci(),
                    last_move_san=san,
                    ply=len(board.move_stack),
                    white_ms=max(0, round(clock[chess.WHITE])),
                    black_ms=max(0, round(clock[chess.BLACK])),
                )
            )
    finally:
        white.stop()
        black.stop()


def _start_agent(agent: Agent) -> str | None:
    try:
        agent.start(INIT_BUDGET_S)
    except AgentFailure as failure:
        return failure.reason
    return None


def _legal_move(board: chess.Board, uci: str) -> chess.Move | None:
    try:
        move = chess.Move.from_uci(uci)
    except chess.InvalidMoveError:
        return None
    return move if move in board.legal_moves else None


def _opponent_wins(mover: chess.Color) -> Result:
    return "black" if mover == chess.WHITE else "white"


def _adjudicate(board: chess.Board) -> Result:
    balance = sum(
        value * (len(board.pieces(piece, chess.WHITE)) - len(board.pieces(piece, chess.BLACK)))
        for piece, value in PIECE_VALUES.items()
    )
    if balance > 0:
        return "white"
    if balance < 0:
        return "black"
    return "draw"


def _summary(
    board: chess.Board,
    game_number: int,
    white_name: str,
    black_name: str,
    competitor_a_is_white: bool,
    result: Result,
    termination: str,
    clock: dict[chess.Color, float],
    base_ms: int,
    increment_ms: int,
) -> GameSummary:
    game = chess.pgn.Game.from_board(board)
    game.headers["Event"] = "Local Match Maker"
    game.headers["White"] = white_name
    game.headers["Black"] = black_name
    game.headers["Result"] = RESULT_HEADERS[result]
    game.headers["Termination"] = termination
    game.headers["TimeControl"] = f"{base_ms / 1_000:g}+{increment_ms / 1_000:g}"

    return GameSummary(
        game_number=game_number,
        white_name=white_name,
        black_name=black_name,
        competitor_a_is_white=competitor_a_is_white,
        result=result,
        termination=termination,
        plies=len(board.move_stack),
        pgn=str(game),
        final_fen=board.fen(),
        white_ms=max(0, round(clock[chess.WHITE])),
        black_ms=max(0, round(clock[chess.BLACK])),
    )
