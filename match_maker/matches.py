"""Observable local matches; the competition harness and agents stay untouched."""

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
from harness.rules import INIT_BUDGET_S
from harness.sandbox import AgentFailure
from match_maker.diagnostics import DiagnosticAgent
from match_maker.lab.series import OPENINGS, opening_fen

Result = Literal["white", "black", "draw", "void"]


@dataclass(frozen=True)
class SeriesConfig:
    competitor_a_name: str
    competitor_a_path: Path
    competitor_b_name: str
    competitor_b_path: Path
    games: int
    base_ms: int
    increment_ms: int
    ply_cap: int = 600
    opening_mode: str = "Paired opening suite"
    custom_fen: str = chess.STARTING_FEN


@dataclass(frozen=True)
class GameStarted:
    game_number: int
    total_games: int
    white_name: str
    black_name: str
    competitor_a_is_white: bool
    initial_fen: str
    base_ms: int
    opening: str


@dataclass(frozen=True)
class AgentStatus:
    message: str


@dataclass(frozen=True)
class MoveStarted:
    color: chess.Color
    player_name: str
    remaining_ms: int
    started_at: float


@dataclass(frozen=True)
class MoveRecord:
    ply: int
    color: str
    san: str
    uci: str
    fen: str
    elapsed_ms: float
    clock_ms: int
    depth: float | None
    nodes: float | None
    nps: float | None
    tt_hits: float | None
    search_seconds: float | None
    material_white: int
    legal_moves: int
    halfmove_clock: int
    capture: bool
    check: bool
    promotion: bool
    normal_seconds: float | None = None
    hard_seconds: float | None = None
    extended: float | None = None


@dataclass(frozen=True)
class PositionChanged:
    fen: str
    last_move_uci: str
    last_move_san: str
    ply: int
    white_ms: int
    black_ms: int
    record: MoveRecord


@dataclass(frozen=True)
class GameSummary:
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
    opening: str
    initial_fen: str
    elapsed_seconds: float
    white_init_seconds: float
    black_init_seconds: float
    moves: tuple[MoveRecord, ...]
    error_detail: str = ""

    @property
    def technical_failure(self) -> bool:
        return self.termination in FAILED_TERMINATIONS


@dataclass(frozen=True)
class SeriesFinished:
    completed_games: int
    cancelled: bool


@dataclass(frozen=True)
class MatchError:
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
    """User requested cancellation between agent operations."""


def discover_models(repository: Path) -> dict[str, Path]:
    models: dict[str, Path] = {}
    if (repository / "agent.py").is_file():
        models["Current agent (working tree)"] = repository
    for group, parent in (
        ("Baseline", repository / "baselines"),
        ("Past model", repository / "past_models"),
    ):
        if parent.is_dir():
            for directory in sorted(parent.iterdir(), key=lambda p: p.name.casefold()):
                if directory.is_dir() and (directory / "agent.py").is_file():
                    models[f"{group} / {directory.name}"] = directory
    return models


def starting_position(config: SeriesConfig, index: int) -> tuple[str, str]:
    if config.opening_mode == "Paired opening suite":
        name, line = list(OPENINGS.items())[(index // 2) % len(OPENINGS)]
        return name, opening_fen(line)
    if config.opening_mode == "Custom FEN":
        return "custom", config.custom_fen
    return "standard", chess.STARTING_FEN


def run_series(
    config: SeriesConfig, callback: EventCallback, cancel_event: threading.Event
) -> None:
    completed = 0
    try:
        for index in range(config.games):
            if cancel_event.is_set():
                raise MatchCancelled
            opening, fen = starting_position(config, index)
            a_white = index % 2 == 0
            white_name = config.competitor_a_name if a_white else config.competitor_b_name
            black_name = config.competitor_b_name if a_white else config.competitor_a_name
            callback(
                GameStarted(
                    index + 1,
                    config.games,
                    white_name,
                    black_name,
                    a_white,
                    fen,
                    config.base_ms,
                    opening,
                )
            )
            summary = _play_game(config, index + 1, a_white, opening, fen, callback, cancel_event)
            callback(summary)
            completed += 1
    except MatchCancelled:
        callback(SeriesFinished(completed, True))
    except Exception as error:
        callback(MatchError(f"{type(error).__name__}: {error}"))
        callback(SeriesFinished(completed, True))
    else:
        callback(SeriesFinished(completed, False))


def _play_game(
    config: SeriesConfig,
    number: int,
    a_white: bool,
    opening: str,
    fen: str,
    callback: EventCallback,
    cancel: threading.Event,
) -> GameSummary:
    board = chess.Board(fen)
    paths = (config.competitor_a_path, config.competitor_b_path)
    names = (config.competitor_a_name, config.competitor_b_name)
    white = DiagnosticAgent(paths[0 if a_white else 1])
    black = DiagnosticAgent(paths[1 if a_white else 0])
    agents = {chess.WHITE: white, chess.BLACK: black}
    player_names = {
        chess.WHITE: names[0 if a_white else 1],
        chess.BLACK: names[1 if a_white else 0],
    }
    clock = {chess.WHITE: float(config.base_ms), chess.BLACK: float(config.base_ms)}
    init = {chess.WHITE: 0.0, chess.BLACK: 0.0}
    records: list[MoveRecord] = []
    started = time.monotonic()

    def finish(result: Result, termination: str, detail: str = "") -> GameSummary:
        if termination in FAILED_TERMINATIONS:
            white.stop()
            black.stop()
            detail = "\n".join(
                part
                for part in (detail, white.stderr_tail[-4096:], black.stderr_tail[-4096:])
                if part
            )
        game = chess.pgn.Game.from_board(board)
        game.headers.update(
            Event="Chess Lab",
            White=player_names[chess.WHITE],
            Black=player_names[chess.BLACK],
            Result=RESULT_HEADERS[result],
            Termination=termination,
            Opening=opening,
            TimeControl=f"{config.base_ms / 1000:g}+{config.increment_ms / 1000:g}",
        )
        for node, record in zip(game.mainline(), records, strict=True):
            node.set_clock(record.clock_ms / 1000)
            node.set_emt(record.elapsed_ms / 1000)
            if record.depth is not None:
                node.comment += f" depth={record.depth:g}"
        return GameSummary(
            number,
            player_names[chess.WHITE],
            player_names[chess.BLACK],
            a_white,
            result,
            termination,
            len(records),
            str(game),
            board.fen(),
            max(0, round(clock[chess.WHITE])),
            max(0, round(clock[chess.BLACK])),
            opening,
            fen,
            time.monotonic() - started,
            init[chess.WHITE],
            init[chess.BLACK],
            tuple(records),
            detail,
        )

    try:
        failures = {}
        for color, process in agents.items():
            if cancel.is_set():
                raise MatchCancelled
            callback(AgentStatus(f"Game {number}: initializing {player_names[color]}…"))
            stamp = time.monotonic()
            try:
                process.start(INIT_BUDGET_S)
            except AgentFailure as error:
                failures[color] = error.reason
            init[color] = time.monotonic() - stamp
        if len(failures) == 2:
            return finish("void", "both_failed")
        if failures:
            loser, reason = next(iter(failures.items()))
            return finish("black" if loser else "white", reason)
        while True:
            if cancel.is_set():
                raise MatchCancelled
            outcome = board.outcome(claim_draw=True)
            if outcome:
                result: Result = (
                    "draw" if outcome.winner is None else "white" if outcome.winner else "black"
                )
                return finish(result, outcome.termination.name.lower())
            if board.ply() >= config.ply_cap:
                return finish("draw", "ply_limit")
            mover = board.turn
            callback(MoveStarted(mover, player_names[mover], round(clock[mover]), time.monotonic()))
            stamp = time.monotonic()
            failure = ""
            try:
                reply = agents[mover].move(board.fen(), int(clock[mover]))
            except AgentFailure as error:
                failure, reply = error.reason, ""
            elapsed = (time.monotonic() - stamp) * 1000
            clock[mover] -= elapsed
            if failure or clock[mover] < 0:
                return finish("black" if mover else "white", failure or "flag")
            try:
                move = chess.Move.from_uci(reply)
            except chess.InvalidMoveError:
                return finish("black" if mover else "white", "illegal", repr(reply))
            if move not in board.legal_moves:
                return finish("black" if mover else "white", "illegal", repr(reply))
            san, capture = board.san(move), board.is_capture(move)
            board.push(move)
            clock[mover] += config.increment_ms
            stats = agents[mover].stats
            material = sum(
                v * (len(board.pieces(p, chess.WHITE)) - len(board.pieces(p, chess.BLACK)))
                for p, v in PIECE_VALUES.items()
            )
            record = MoveRecord(
                board.ply(),
                "white" if mover else "black",
                san,
                reply,
                board.fen(),
                elapsed,
                max(0, round(clock[mover])),
                stats.get("depth"),
                stats.get("nodes"),
                stats.get("nps"),
                stats.get("tt_hits"),
                stats.get("seconds"),
                material,
                board.legal_moves.count(),
                board.halfmove_clock,
                capture,
                board.is_check(),
                move.promotion is not None,
                normal_seconds=stats.get("normal_seconds"),
                hard_seconds=stats.get("hard_seconds"),
                extended=stats.get("extended"),
            )
            records.append(record)
            callback(
                PositionChanged(
                    board.fen(),
                    reply,
                    san,
                    board.ply(),
                    round(clock[chess.WHITE]),
                    round(clock[chess.BLACK]),
                    record,
                )
            )
    finally:
        white.stop()
        black.stop()
