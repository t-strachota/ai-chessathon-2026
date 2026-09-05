"""Tk desktop interface for running and watching local agent matches."""

from __future__ import annotations

import queue
import threading
import time
import tkinter as tk
from collections import Counter
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import chess

from harness.referee import RESULT_HEADERS
from match_maker.matches import (
    AgentStatus,
    GameStarted,
    GameSummary,
    MatchError,
    MatchEvent,
    MoveStarted,
    PositionChanged,
    SeriesConfig,
    SeriesFinished,
    discover_models,
    run_series,
)

REPOSITORY = Path(__file__).resolve().parents[1]
BOARD_PIXELS = 512
SQUARE_PIXELS = BOARD_PIXELS // 8
LIGHT_SQUARE = "#e8edf1"
DARK_SQUARE = "#769656"
LIGHT_LAST_MOVE = "#f4e66a"
DARK_LAST_MOVE = "#c9b937"
CHECK_SQUARE = "#e57373"


class MatchMakerApp:
    """Coordinate the GUI, background match thread, and cumulative statistics."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Chessathon Match Maker")
        self.root.geometry("1240x820")
        self.root.minsize(1080, 720)

        self.models = discover_models(REPOSITORY)
        self.events: queue.Queue[MatchEvent] = queue.Queue()
        self.cancel_event = threading.Event()
        self.worker: threading.Thread | None = None
        self.closing = False

        self.current_fen = chess.STARTING_FEN
        self.last_move_uci = ""
        self.flipped = False
        self.move_sans: list[str] = []
        self.summaries: list[GameSummary] = []
        self.terminations: Counter[str] = Counter()
        self.competitor_a_name = ""
        self.competitor_b_name = ""
        self.requested_games = 0
        self.a_wins = 0
        self.a_draws = 0
        self.a_losses = 0
        self.total_plies = 0
        self.clock_ms = {chess.WHITE: 0, chess.BLACK: 0}
        self.thinking_color: chess.Color | None = None
        self.thinking_started_at = 0.0
        self.thinking_initial_ms = 0

        self._create_variables()
        self._configure_style()
        self._build_layout()
        self._choose_defaults()
        self._draw_board()
        self._poll_events()
        self._refresh_clocks()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _create_variables(self) -> None:
        self.competitor_a_var = tk.StringVar()
        self.competitor_b_var = tk.StringVar()
        self.games_var = tk.StringVar(value="4")
        self.base_seconds_var = tk.StringVar(value="120")
        self.increment_ms_var = tk.StringVar(value="500")
        self.status_var = tk.StringVar(value="Choose two agents and start a match.")
        self.game_progress_var = tk.StringVar(value="Game 0 / 0")
        self.white_player_var = tk.StringVar(value="White")
        self.black_player_var = tk.StringVar(value="Black")
        self.white_clock_var = tk.StringVar(value="00:00.000")
        self.black_clock_var = tk.StringVar(value="00:00.000")
        self.record_var = tk.StringVar(value="0 wins · 0 draws · 0 losses")
        self.score_var = tk.StringVar(value="Score: —")
        self.average_length_var = tk.StringVar(value="Average length: —")
        self.termination_var = tk.StringVar(value="Terminations: —")
        self.failure_var = tk.StringVar(value="Technical failures: 0")

    def _configure_style(self) -> None:
        style = ttk.Style(self.root)
        if "aqua" in style.theme_names():
            style.theme_use("aqua")
        style.configure("Title.TLabel", font=("Helvetica", 22, "bold"))
        style.configure("Subtitle.TLabel", foreground="#59636e")
        style.configure("Clock.TLabel", font=("Menlo", 21, "bold"))
        style.configure("Stat.TLabel", font=("Helvetica", 13, "bold"))

    def _build_layout(self) -> None:
        outer = ttk.Frame(self.root, padding=16)
        outer.grid(row=0, column=0, sticky="nsew")
        self.root.rowconfigure(0, weight=1)
        self.root.columnconfigure(0, weight=1)
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(2, weight=1)

        heading = ttk.Frame(outer)
        heading.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        heading.columnconfigure(0, weight=1)
        ttk.Label(heading, text="Chessathon Match Maker", style="Title.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(
            heading,
            text="Local visualization and statistics · colors alternate each game",
            style="Subtitle.TLabel",
        ).grid(row=1, column=0, sticky="w")

        self._build_controls(outer)

        content = ttk.Panedwindow(outer, orient=tk.HORIZONTAL)
        content.grid(row=2, column=0, sticky="nsew", pady=(14, 0))

        board_panel = ttk.Frame(content, padding=(0, 0, 14, 0))
        details_panel = ttk.Frame(content)
        content.add(board_panel, weight=5)
        content.add(details_panel, weight=6)
        self._build_board_panel(board_panel)
        self._build_details_panel(details_panel)

    def _build_controls(self, parent: ttk.Frame) -> None:
        controls = ttk.LabelFrame(parent, text="Match setup", padding=12)
        controls.grid(row=1, column=0, sticky="ew")
        for column in range(7):
            controls.columnconfigure(column, weight=1 if column in (0, 1) else 0)

        ttk.Label(controls, text="Competitor A").grid(row=0, column=0, sticky="w")
        ttk.Label(controls, text="Competitor B").grid(row=0, column=1, sticky="w", padx=(10, 0))
        ttk.Label(controls, text="Games").grid(row=0, column=2, sticky="w", padx=(10, 0))
        ttk.Label(controls, text="Base (seconds)").grid(row=0, column=3, sticky="w", padx=(10, 0))
        ttk.Label(controls, text="Increment (ms)").grid(row=0, column=4, sticky="w", padx=(10, 0))

        model_names = list(self.models)
        self.competitor_a_box = ttk.Combobox(
            controls,
            textvariable=self.competitor_a_var,
            values=model_names,
            state="readonly",
            width=28,
        )
        self.competitor_b_box = ttk.Combobox(
            controls,
            textvariable=self.competitor_b_var,
            values=model_names,
            state="readonly",
            width=28,
        )
        self.games_box = ttk.Spinbox(
            controls, from_=1, to=1_000, textvariable=self.games_var, width=7
        )
        self.base_box = ttk.Entry(controls, textvariable=self.base_seconds_var, width=12)
        self.increment_box = ttk.Spinbox(
            controls, from_=0, to=60_000, textvariable=self.increment_ms_var, width=12
        )
        self.competitor_a_box.grid(row=1, column=0, sticky="ew")
        self.competitor_b_box.grid(row=1, column=1, sticky="ew", padx=(10, 0))
        self.games_box.grid(row=1, column=2, sticky="ew", padx=(10, 0))
        self.base_box.grid(row=1, column=3, sticky="ew", padx=(10, 0))
        self.increment_box.grid(row=1, column=4, sticky="ew", padx=(10, 0))

        presets = ttk.Frame(controls)
        presets.grid(row=2, column=0, columnspan=5, sticky="w", pady=(10, 0))
        ttk.Label(presets, text="Presets:").pack(side=tk.LEFT)
        ttk.Button(presets, text="Fast 10s + 0.1s", command=self._set_fast_timing).pack(
            side=tk.LEFT, padx=(6, 4)
        )
        ttk.Button(presets, text="Official 120s + 0.5s", command=self._set_official_timing).pack(
            side=tk.LEFT
        )

        button_box = ttk.Frame(controls)
        button_box.grid(row=1, column=5, rowspan=2, sticky="ns", padx=(14, 0))
        self.start_button = ttk.Button(button_box, text="Start match", command=self._start_match)
        self.start_button.pack(fill=tk.X)
        self.stop_button = ttk.Button(
            button_box, text="Stop", command=self._request_stop, state=tk.DISABLED
        )
        self.stop_button.pack(fill=tk.X, pady=(6, 0))

        self.progress = ttk.Progressbar(controls, mode="determinate")
        self.progress.grid(row=3, column=0, columnspan=6, sticky="ew", pady=(12, 0))

        self.control_widgets: tuple[ttk.Combobox | ttk.Spinbox | ttk.Entry, ...] = (
            self.competitor_a_box,
            self.competitor_b_box,
            self.games_box,
            self.base_box,
            self.increment_box,
        )

    def _build_board_panel(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)

        black_header = ttk.Frame(parent)
        black_header.grid(row=0, column=0, sticky="ew", pady=(0, 7))
        black_header.columnconfigure(0, weight=1)
        ttk.Label(black_header, textvariable=self.black_player_var, style="Stat.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(black_header, textvariable=self.black_clock_var, style="Clock.TLabel").grid(
            row=0, column=1, sticky="e"
        )

        self.board_canvas = tk.Canvas(
            parent,
            width=BOARD_PIXELS,
            height=BOARD_PIXELS,
            highlightthickness=1,
            highlightbackground="#46515c",
        )
        self.board_canvas.grid(row=1, column=0, sticky="n")

        white_header = ttk.Frame(parent)
        white_header.grid(row=2, column=0, sticky="ew", pady=(7, 0))
        white_header.columnconfigure(0, weight=1)
        ttk.Label(white_header, textvariable=self.white_player_var, style="Stat.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(white_header, textvariable=self.white_clock_var, style="Clock.TLabel").grid(
            row=0, column=1, sticky="e"
        )

        lower = ttk.Frame(parent)
        lower.grid(row=3, column=0, sticky="ew", pady=(10, 0))
        lower.columnconfigure(0, weight=1)
        ttk.Label(lower, textvariable=self.game_progress_var).grid(row=0, column=0, sticky="w")
        ttk.Button(lower, text="Flip board", command=self._flip_board).grid(
            row=0, column=1, sticky="e"
        )

    def _build_details_panel(self, parent: ttk.Frame) -> None:
        parent.rowconfigure(1, weight=1)
        parent.columnconfigure(0, weight=1)

        statistics = ttk.LabelFrame(parent, text="Statistics", padding=12)
        statistics.grid(row=0, column=0, sticky="ew")
        statistics.columnconfigure(0, weight=1)
        ttk.Label(statistics, textvariable=self.record_var, style="Stat.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(statistics, textvariable=self.score_var).grid(row=1, column=0, sticky="w")
        ttk.Label(statistics, textvariable=self.average_length_var).grid(
            row=2, column=0, sticky="w"
        )
        ttk.Label(statistics, textvariable=self.termination_var, wraplength=570).grid(
            row=3, column=0, sticky="w"
        )
        ttk.Label(statistics, textvariable=self.failure_var).grid(row=4, column=0, sticky="w")

        notebook = ttk.Notebook(parent)
        notebook.grid(row=1, column=0, sticky="nsew", pady=(12, 0))
        moves_tab = ttk.Frame(notebook, padding=8)
        results_tab = ttk.Frame(notebook, padding=8)
        notebook.add(moves_tab, text="Current game")
        notebook.add(results_tab, text="Results")
        self._build_moves_tab(moves_tab)
        self._build_results_tab(results_tab)

        status = ttk.LabelFrame(parent, text="Status", padding=8)
        status.grid(row=2, column=0, sticky="ew", pady=(12, 0))
        ttk.Label(status, textvariable=self.status_var, wraplength=570).grid(
            row=0, column=0, sticky="w"
        )

    def _build_moves_tab(self, parent: ttk.Frame) -> None:
        parent.rowconfigure(0, weight=1)
        parent.columnconfigure(0, weight=1)
        self.moves_text = tk.Text(
            parent,
            height=15,
            wrap=tk.WORD,
            state=tk.DISABLED,
            font=("Menlo", 12),
            padx=8,
            pady=8,
        )
        scrollbar = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=self.moves_text.yview)
        self.moves_text.configure(yscrollcommand=scrollbar.set)
        self.moves_text.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")

    def _build_results_tab(self, parent: ttk.Frame) -> None:
        parent.rowconfigure(0, weight=1)
        parent.columnconfigure(0, weight=1)
        columns = ("game", "white", "black", "result", "termination", "plies")
        self.results_tree = ttk.Treeview(parent, columns=columns, show="headings", height=13)
        headings = {
            "game": "Game",
            "white": "White",
            "black": "Black",
            "result": "Result",
            "termination": "Termination",
            "plies": "Plies",
        }
        widths = {
            "game": 48,
            "white": 145,
            "black": 145,
            "result": 60,
            "termination": 135,
            "plies": 50,
        }
        for column in columns:
            self.results_tree.heading(column, text=headings[column])
            self.results_tree.column(column, width=widths[column], minwidth=40, stretch=True)
        scrollbar = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=self.results_tree.yview)
        self.results_tree.configure(yscrollcommand=scrollbar.set)
        self.results_tree.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")

        self.export_button = ttk.Button(
            parent, text="Export PGNs…", command=self._export_pgns, state=tk.DISABLED
        )
        self.export_button.grid(row=1, column=0, sticky="e", pady=(8, 0))

    def _choose_defaults(self) -> None:
        names = list(self.models)
        if not names:
            self.status_var.set("No folders containing agent.py were found.")
            self.start_button.configure(state=tk.DISABLED)
            return
        self.competitor_a_var.set(names[0])
        dylan = "Past model / Dylan"
        self.competitor_b_var.set(dylan if dylan in self.models else names[min(1, len(names) - 1)])

    def _set_fast_timing(self) -> None:
        self.base_seconds_var.set("10")
        self.increment_ms_var.set("100")

    def _set_official_timing(self) -> None:
        self.base_seconds_var.set("120")
        self.increment_ms_var.set("500")

    def _read_config(self) -> SeriesConfig | None:
        try:
            games = int(self.games_var.get())
            base_ms = round(float(self.base_seconds_var.get()) * 1_000)
            increment_ms = int(self.increment_ms_var.get())
        except ValueError:
            messagebox.showerror("Invalid settings", "Games and time controls must be numbers.")
            return None

        if not 1 <= games <= 1_000:
            messagebox.showerror("Invalid settings", "Games must be between 1 and 1,000.")
            return None
        if not 100 <= base_ms <= 3_600_000:
            messagebox.showerror("Invalid settings", "Base time must be from 0.1 to 3,600 seconds.")
            return None
        if not 0 <= increment_ms <= 60_000:
            messagebox.showerror("Invalid settings", "Increment must be from 0 to 60,000 ms.")
            return None

        name_a = self.competitor_a_var.get()
        name_b = self.competitor_b_var.get()
        if name_a not in self.models or name_b not in self.models:
            messagebox.showerror("Missing agent", "Select a valid agent for each competitor.")
            return None

        return SeriesConfig(
            competitor_a_name=name_a,
            competitor_a_path=self.models[name_a],
            competitor_b_name=name_b,
            competitor_b_path=self.models[name_b],
            games=games,
            base_ms=base_ms,
            increment_ms=increment_ms,
        )

    def _start_match(self) -> None:
        if self.worker is not None and self.worker.is_alive():
            return
        config = self._read_config()
        if config is None:
            return

        self._reset_series(config)
        self.cancel_event.clear()
        self._set_running(True)
        self.worker = threading.Thread(
            target=run_series,
            args=(config, self.events.put, self.cancel_event),
            name="match-series",
            daemon=True,
        )
        self.worker.start()

    def _reset_series(self, config: SeriesConfig) -> None:
        self.competitor_a_name = config.competitor_a_name
        self.competitor_b_name = config.competitor_b_name
        self.requested_games = config.games
        self.a_wins = self.a_draws = self.a_losses = self.total_plies = 0
        self.summaries.clear()
        self.terminations.clear()
        self.move_sans.clear()
        self.current_fen = chess.STARTING_FEN
        self.last_move_uci = ""
        self.clock_ms = {chess.WHITE: config.base_ms, chess.BLACK: config.base_ms}
        self.thinking_color = None
        self.progress.configure(maximum=config.games, value=0)
        self.game_progress_var.set(f"Game 0 / {config.games}")
        self.status_var.set("Preparing the first game…")
        self.results_tree.delete(*self.results_tree.get_children())
        self.export_button.configure(state=tk.DISABLED)
        self._render_moves()
        self._update_statistics()
        self._draw_board()

    def _set_running(self, running: bool) -> None:
        for widget in self.control_widgets:
            widget.configure(state=tk.DISABLED if running else tk.NORMAL)
        if not running:
            self.competitor_a_box.configure(state="readonly")
            self.competitor_b_box.configure(state="readonly")
        self.start_button.configure(state=tk.DISABLED if running else tk.NORMAL)
        self.stop_button.configure(state=tk.NORMAL if running else tk.DISABLED)

    def _request_stop(self) -> None:
        self.cancel_event.set()
        self.stop_button.configure(state=tk.DISABLED)
        self.status_var.set("Stop requested; waiting for the current agent response…")

    def _poll_events(self) -> None:
        try:
            while True:
                self._handle_event(self.events.get_nowait())
        except queue.Empty:
            pass

        if self.closing and (self.worker is None or not self.worker.is_alive()):
            self.root.destroy()
            return
        self.root.after(50, self._poll_events)

    def _handle_event(self, event: MatchEvent) -> None:
        if isinstance(event, GameStarted):
            self._handle_game_started(event)
        elif isinstance(event, AgentStatus):
            self.status_var.set(event.message)
        elif isinstance(event, MoveStarted):
            self.thinking_color = event.color
            self.thinking_started_at = event.started_at
            self.thinking_initial_ms = event.remaining_ms
            color_name = "White" if event.color == chess.WHITE else "Black"
            self.status_var.set(f"{color_name} · {event.player_name} is thinking…")
        elif isinstance(event, PositionChanged):
            self._handle_position_changed(event)
        elif isinstance(event, GameSummary):
            self._handle_game_summary(event)
        elif isinstance(event, MatchError):
            self.status_var.set(f"Match Maker error: {event.message}")
            messagebox.showerror("Match Maker error", event.message)
        elif isinstance(event, SeriesFinished):
            self._handle_series_finished(event)

    def _handle_game_started(self, event: GameStarted) -> None:
        self.current_fen = event.initial_fen
        self.last_move_uci = ""
        self.move_sans.clear()
        self.clock_ms = {chess.WHITE: event.base_ms, chess.BLACK: event.base_ms}
        self.thinking_color = None
        self.white_player_var.set(f"White · {event.white_name}")
        self.black_player_var.set(f"Black · {event.black_name}")
        self.game_progress_var.set(f"Game {event.game_number} / {event.total_games}")
        self.status_var.set(f"Starting game {event.game_number}…")
        self._render_moves()
        self._draw_board()

    def _handle_position_changed(self, event: PositionChanged) -> None:
        self.current_fen = event.fen
        self.last_move_uci = event.last_move_uci
        self.move_sans.append(event.last_move_san)
        self.clock_ms = {chess.WHITE: event.white_ms, chess.BLACK: event.black_ms}
        self.thinking_color = None
        self.status_var.set(f"Move {event.ply}: {event.last_move_san}")
        self._render_moves()
        self._draw_board()

    def _handle_game_summary(self, summary: GameSummary) -> None:
        self.summaries.append(summary)
        self.terminations[summary.termination] += 1
        self.total_plies += summary.plies
        self.current_fen = summary.final_fen
        self.clock_ms = {chess.WHITE: summary.white_ms, chess.BLACK: summary.black_ms}
        self.thinking_color = None

        if summary.result in ("draw", "void"):
            self.a_draws += 1
        else:
            white_won = summary.result == "white"
            if white_won == summary.competitor_a_is_white:
                self.a_wins += 1
            else:
                self.a_losses += 1

        self.results_tree.insert(
            "",
            tk.END,
            values=(
                summary.game_number,
                summary.white_name,
                summary.black_name,
                RESULT_HEADERS[summary.result],
                summary.termination,
                summary.plies,
            ),
        )
        self.progress.configure(value=len(self.summaries))
        self.export_button.configure(state=tk.NORMAL)
        self.status_var.set(
            f"Game {summary.game_number}: {RESULT_HEADERS[summary.result]} by {summary.termination}"
        )
        self._update_statistics()
        self._draw_board()

    def _handle_series_finished(self, event: SeriesFinished) -> None:
        self.thinking_color = None
        self._set_running(False)
        if event.cancelled:
            self.status_var.set(f"Series stopped after {event.completed_games} completed games.")
        else:
            score = (self.a_wins + self.a_draws / 2) / max(1, event.completed_games)
            self.status_var.set(
                f"Series complete: +{self.a_wins} ={self.a_draws} -{self.a_losses}, "
                f"score {score:.1%} for {self.competitor_a_name}."
            )

    def _update_statistics(self) -> None:
        completed = len(self.summaries)
        self.record_var.set(
            f"{self.competitor_a_name or 'Competitor A'}: "
            f"{self.a_wins} wins · {self.a_draws} draws · {self.a_losses} losses"
        )
        if completed:
            score = (self.a_wins + self.a_draws / 2) / completed
            average_plies = self.total_plies / completed
            self.score_var.set(f"Score: {score:.1%} after {completed} games")
            self.average_length_var.set(
                f"Average length: {average_plies:.1f} plies ({average_plies / 2:.1f} moves)"
            )
        else:
            self.score_var.set("Score: —")
            self.average_length_var.set("Average length: —")

        if self.terminations:
            values = ", ".join(f"{name} {count}" for name, count in self.terminations.most_common())
            self.termination_var.set(f"Terminations: {values}")
        else:
            self.termination_var.set("Terminations: —")
        failures = sum(summary.technical_failure for summary in self.summaries)
        self.failure_var.set(f"Technical failures: {failures}")

    def _render_moves(self) -> None:
        lines: list[str] = []
        for index in range(0, len(self.move_sans), 2):
            white_move = self.move_sans[index]
            black_move = self.move_sans[index + 1] if index + 1 < len(self.move_sans) else ""
            lines.append(f"{index // 2 + 1:>3}. {white_move:<12} {black_move}")
        self.moves_text.configure(state=tk.NORMAL)
        self.moves_text.delete("1.0", tk.END)
        self.moves_text.insert("1.0", "\n".join(lines))
        self.moves_text.configure(state=tk.DISABLED)
        self.moves_text.see(tk.END)

    def _draw_board(self) -> None:
        self.board_canvas.delete("all")
        try:
            board = chess.Board(self.current_fen)
        except ValueError:
            board = chess.Board()

        highlighted: set[chess.Square] = set()
        if self.last_move_uci:
            try:
                last_move = chess.Move.from_uci(self.last_move_uci)
                highlighted = {last_move.from_square, last_move.to_square}
            except chess.InvalidMoveError:
                pass

        checked_king = board.king(board.turn) if board.is_check() else None
        for display_rank in range(8):
            for display_file in range(8):
                square = self._display_to_square(display_file, display_rank)
                light = (chess.square_file(square) + chess.square_rank(square)) % 2 == 1
                color = LIGHT_SQUARE if light else DARK_SQUARE
                if square in highlighted:
                    color = LIGHT_LAST_MOVE if light else DARK_LAST_MOVE
                if square == checked_king:
                    color = CHECK_SQUARE

                x0 = display_file * SQUARE_PIXELS
                y0 = display_rank * SQUARE_PIXELS
                self.board_canvas.create_rectangle(
                    x0,
                    y0,
                    x0 + SQUARE_PIXELS,
                    y0 + SQUARE_PIXELS,
                    fill=color,
                    outline=color,
                )
                piece = board.piece_at(square)
                if piece is not None:
                    self.board_canvas.create_text(
                        x0 + SQUARE_PIXELS / 2,
                        y0 + SQUARE_PIXELS / 2 + 1,
                        text=piece.unicode_symbol(),
                        font=("Arial Unicode MS", 42),
                        fill="#17212b",
                    )

                file_label = chess.FILE_NAMES[chess.square_file(square)]
                rank_label = str(chess.square_rank(square) + 1)
                label_color = "#506070" if light else "#eef4e8"
                if display_rank == 7:
                    self.board_canvas.create_text(
                        x0 + SQUARE_PIXELS - 5,
                        y0 + SQUARE_PIXELS - 4,
                        text=file_label,
                        anchor=tk.SE,
                        font=("Helvetica", 9, "bold"),
                        fill=label_color,
                    )
                if display_file == 0:
                    self.board_canvas.create_text(
                        x0 + 5,
                        y0 + 4,
                        text=rank_label,
                        anchor=tk.NW,
                        font=("Helvetica", 9, "bold"),
                        fill=label_color,
                    )

    def _display_to_square(self, display_file: int, display_rank: int) -> chess.Square:
        if self.flipped:
            board_file = 7 - display_file
            board_rank = display_rank
        else:
            board_file = display_file
            board_rank = 7 - display_rank
        return chess.square(board_file, board_rank)

    def _flip_board(self) -> None:
        self.flipped = not self.flipped
        self._draw_board()

    def _refresh_clocks(self) -> None:
        displayed = dict(self.clock_ms)
        if self.thinking_color is not None:
            elapsed_ms = (time.monotonic() - self.thinking_started_at) * 1_000
            displayed[self.thinking_color] = max(0, round(self.thinking_initial_ms - elapsed_ms))
        self.white_clock_var.set(_format_clock(displayed[chess.WHITE]))
        self.black_clock_var.set(_format_clock(displayed[chess.BLACK]))
        self.root.after(100, self._refresh_clocks)

    def _export_pgns(self) -> None:
        if not self.summaries:
            return
        filename = filedialog.asksaveasfilename(
            title="Export match PGNs",
            defaultextension=".pgn",
            filetypes=(("PGN files", "*.pgn"), ("All files", "*.*")),
            initialfile="match-series.pgn",
        )
        if not filename:
            return
        Path(filename).write_text("\n\n".join(summary.pgn for summary in self.summaries) + "\n")
        self.status_var.set(f"Exported {len(self.summaries)} games to {filename}")

    def _on_close(self) -> None:
        if self.worker is None or not self.worker.is_alive():
            self.root.destroy()
            return
        self.closing = True
        self.cancel_event.set()
        self.stop_button.configure(state=tk.DISABLED)
        self.status_var.set("Closing after the current agent response…")


def _format_clock(milliseconds: int) -> str:
    milliseconds = max(0, milliseconds)
    minutes, remainder = divmod(milliseconds, 60_000)
    seconds, millis = divmod(remainder, 1_000)
    return f"{minutes:02d}:{seconds:02d}.{millis:03d}"


def main() -> None:
    """Create and run the Tk application."""
    root = tk.Tk()
    MatchMakerApp(root)
    root.mainloop()
