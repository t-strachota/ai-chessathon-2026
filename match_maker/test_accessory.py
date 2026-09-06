"""Run with python -m unittest match_maker.test_accessory (no desktop needed)."""

import io
import json
import tempfile
import threading
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

import chess
import chess.pgn

from harness.sandbox import AgentFailure
from match_maker.diagnostics import DiagnosticAgent
from match_maker.matches import (
    GameStarted,
    GameSummary,
    MatchEvent,
    PositionChanged,
    SeriesConfig,
    SeriesFinished,
    run_series,
    starting_position,
)
from match_maker.statistics import export_csv, export_json, move_statistics, series_statistics

ROOT = Path(__file__).resolve().parents[1]


class FakeAgent:
    stopped = 0

    def __init__(self, path: Path) -> None:
        self.stats: dict[str, float] = {}
        self.stderr_tail = ""

    def start(self, budget: float) -> None:
        pass

    def move(self, fen: str, left: int) -> str:
        return next(iter(chess.Board(fen).legal_moves)).uci()

    def stop(self) -> None:
        FakeAgent.stopped += 1


def config(**changes: object) -> SeriesConfig:
    initial = SeriesConfig("A", ROOT, "B", ROOT / "baselines/random", 2, 5000, 100, ply_cap=14)
    return replace(initial, **changes)  # type: ignore[arg-type]


class AccessoryTests(unittest.TestCase):
    def fake_series(self, settings: SeriesConfig | None = None) -> list[MatchEvent]:
        events: list[MatchEvent] = []
        with patch("match_maker.matches.DiagnosticAgent", FakeAgent):
            run_series(settings or config(), events.append, threading.Event())
        return events

    def test_pairing_and_custom_black_start(self) -> None:
        self.assertEqual(starting_position(config(), 0), starting_position(config(), 1))
        self.assertNotEqual(starting_position(config(), 1), starting_position(config(), 2))
        events = self.fake_series()
        starts = [e for e in events if isinstance(e, GameStarted)]
        self.assertEqual([s.competitor_a_is_white for s in starts], [True, False])
        games = [e for e in events if isinstance(e, GameSummary)]
        self.assertEqual(len(games), 2)
        self.assertEqual([g.plies for g in games], [4, 4])
        self.assertTrue(all(g.termination == "ply_limit" for g in games))
        parsed = chess.pgn.read_game(io.StringIO(games[0].pgn))
        assert parsed is not None
        self.assertEqual(parsed.board().fen(), games[0].initial_fen)
        self.assertIsNotNone(next(iter(parsed.mainline())).clock())
        self.assertIsNotNone(next(iter(parsed.mainline())).emt())
        black_fen = "7k/8/8/8/8/8/8/R5K1 b - - 0 1"
        custom = self.fake_series(
            config(games=1, opening_mode="Custom FEN", custom_fen=black_fen, ply_cap=3)
        )
        moves = [e.record for e in custom if isinstance(e, PositionChanged)]
        self.assertEqual(moves[0].color, "black")
        self.assertEqual(moves[0].ply, 2)

    def test_voids_missing_data_and_exports(self) -> None:
        game = next(e for e in self.fake_series() if isinstance(e, GameSummary))
        void = replace(game, result="void", termination="both_failed")
        win = replace(game, result="white")
        stats = series_statistics([game, void, win])
        self.assertEqual(stats["voids"], 1)
        self.assertEqual(stats["scored_games"], 2)
        self.assertEqual(stats["score"], 0.75)
        self.assertIsNone(move_statistics(list(game.moves))["mean_depth"])
        self.assertIsNone(move_statistics([])["mean_ms"])
        measured = [
            replace(game.moves[0], elapsed_ms=10, depth=4),
            replace(game.moves[1], elapsed_ms=30, depth=None),
        ]
        metrics = move_statistics(measured)
        self.assertEqual(metrics["mean_depth"], 4)
        self.assertEqual(metrics["mean_ms"], 20)
        self.assertEqual(metrics["p95_ms"], 30)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)
            export_json(path / "report.json", [game, void], config())
            payload = json.loads((path / "report.json").read_text())
            self.assertEqual(payload["statistics"]["voids"], 1)
            export_csv(path / "moves.csv", [game])
            self.assertEqual(len((path / "moves.csv").read_text().splitlines()), 5)

    def test_cancellation_and_failures(self) -> None:
        cancel = threading.Event()
        cancel.set()
        events: list[MatchEvent] = []
        run_series(config(), events.append, cancel)
        self.assertEqual(events, [SeriesFinished(0, True)])
        with patch.object(FakeAgent, "move", return_value="not-a-move"):
            failures = self.fake_series(config(games=1))
        game = next(e for e in failures if isinstance(e, GameSummary))
        self.assertEqual(game.termination, "illegal")
        self.assertTrue(game.technical_failure)
        with patch.object(FakeAgent, "start", side_effect=AgentFailure("init")):
            failures = self.fake_series(config(games=1))
        game = next(e for e in failures if isinstance(e, GameSummary))
        self.assertEqual(game.result, "void")

    def test_real_process_telemetry(self) -> None:
        for path, reported in ((ROOT, True), (ROOT / "baselines/random", False)):
            process = DiagnosticAgent(path)
            try:
                process.start(60)
                move = process.move(chess.STARTING_FEN, 1000)
                self.assertIn(chess.Move.from_uci(move), chess.Board().legal_moves)
                self.assertEqual("depth" in process.stats, reported)
                if reported:
                    self.assertGreater(process.stats["nodes"], 0)
            finally:
                process.stop()


if __name__ == "__main__":
    unittest.main()
