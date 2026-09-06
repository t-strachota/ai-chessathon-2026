"""Tk desktop interface for running and watching local agent matches."""

from __future__ import annotations

import queue
import threading
import time
import tkinter as tk
from collections import Counter
from datetime import datetime
from functools import partial
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import chess

from harness.referee import RESULT_HEADERS
from match_maker.jobs import LabOutput, run_job
from match_maker.matches import (
    AgentStatus,
    GameStarted,
    GameSummary,
    MatchError,
    MatchEvent,
    MoveRecord,
    MoveStarted,
    PositionChanged,
    SeriesConfig,
    SeriesFinished,
    discover_models,
    run_series,
)
from match_maker.statistics import export_csv, export_json, series_statistics

REPOSITORY = Path(__file__).resolve().parents[1]
BOARD_PIXELS = 448
SQUARE_PIXELS = BOARD_PIXELS // 8
LIGHT_SQUARE = "#dce5e5"
DARK_SQUARE = "#55777c"
LIGHT_LAST_MOVE = "#a7e8d0"
DARK_LAST_MOVE = "#52ab99"
CHECK_SQUARE = "#e57373"
BG, PANEL, INK, MUTED, ACCENT = "#101820", "#1a2632", "#edf4f7", "#9eb2c0", "#61d9b0"


class MatchMakerApp:
    """Coordinate the GUI, background match thread, and cumulative statistics."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Chess Lab · Match room & engine tools")
        self.root.geometry("1440x980")
        self.root.minsize(1180, 920)

        self.models = discover_models(REPOSITORY)
        self.events: queue.Queue[MatchEvent | LabOutput] = queue.Queue()
        self.cancel_event = threading.Event()
        self.worker: threading.Thread | None = None
        self.closing = False
        self.config: SeriesConfig | None = None
        self.current_records: list[MoveRecord] = []
        self.game_a_white = True
        self.series_started_at = 0.0
        self.output_base: Path | None = None
        self.lab_running = False
        self.game_in_progress = False

        self.current_fen = chess.STARTING_FEN
        self.last_move_uci = ""
        self.flipped = False
        self.square_pixels = SQUARE_PIXELS
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
        self.opening_var = tk.StringVar(value="Paired opening suite")
        self.fen_var = tk.StringVar(value=chess.STARTING_FEN)
        self.ply_cap_var = tk.StringVar(value="600")
        self.position_var = tk.StringVar(value="Material balance is not an engine evaluation.")
        self.session_var = tk.StringVar(value="LOCAL WORKSPACE  /  READY")
        self.auto_follow = tk.BooleanVar(value=True)
        self.initial_ply = 0

    def _configure_style(self) -> None:
        style = ttk.Style(self.root)
        style.theme_use("clam")
        self.root.configure(background=BG)
        style.configure(
            ".",
            background=BG,
            foreground=INK,
            font=("Helvetica", 12),
            bordercolor="#304252",
            troughcolor=PANEL,
        )
        style.configure("TFrame", background=BG)
        style.configure("TLabel", background=BG, foreground=INK)
        style.configure("TLabelframe", background=BG, bordercolor="#304252")
        style.configure("TLabelframe.Label", foreground=MUTED, background=BG)
        style.configure("TButton", background=PANEL, foreground=INK, padding=(12, 7))
        style.map(
            "TButton", background=[("active", "#304252")], foreground=[("disabled", "#637788")]
        )
        style.configure("Accent.TButton", background=ACCENT, foreground=BG)
        style.map("Accent.TButton", background=[("active", "#8fe9cc")])
        style.configure("TEntry", fieldbackground=PANEL, foreground=INK, insertcolor=INK)
        style.configure("TSpinbox", fieldbackground=PANEL, foreground=INK, arrowcolor=INK)
        style.configure("TCombobox", fieldbackground=PANEL, foreground=INK, arrowcolor=INK)
        style.map(
            "TCombobox",
            fieldbackground=[("readonly", PANEL)],
            foreground=[("readonly", INK), ("disabled", MUTED)],
        )
        self.root.option_add("*TCombobox*Listbox.background", PANEL)
        self.root.option_add("*TCombobox*Listbox.foreground", INK)
        style.configure("TNotebook", background=BG, borderwidth=0)
        style.configure("TNotebook.Tab", background=PANEL, foreground=MUTED, padding=(16, 9))
        style.map(
            "TNotebook.Tab", background=[("selected", "#304252")], foreground=[("selected", ACCENT)]
        )
        style.configure(
            "Treeview",
            background=PANEL,
            fieldbackground=PANEL,
            foreground=INK,
            rowheight=28,
            borderwidth=0,
        )
        style.configure(
            "Treeview.Heading",
            background="#263847",
            foreground=MUTED,
            font=("Helvetica", 11, "bold"),
            padding=6,
        )
        style.map("Treeview", background=[("selected", "#325a63")])
        style.configure("Horizontal.TProgressbar", background=ACCENT, troughcolor=PANEL)
        style.configure("Title.TLabel", font=("Helvetica", 27, "bold"))
        style.configure("Subtitle.TLabel", foreground=MUTED)
        style.configure("Clock.TLabel", font=("Menlo", 21, "bold"))
        style.configure("Stat.TLabel", font=("Helvetica", 13, "bold"))

    def _build_layout(self) -> None:
        outer = ttk.Frame(self.root, padding=16)
        outer.grid(row=0, column=0, sticky="nsew")
        self.root.rowconfigure(0, weight=1)
        self.root.columnconfigure(0, weight=1)
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(1, weight=1)

        heading = ttk.Frame(outer)
        heading.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        heading.columnconfigure(0, weight=1)
        ttk.Label(heading, text="CHESS LAB", style="Title.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(
            heading,
            text="Play. Measure. Improve.   /   Your engine development workspace",
            style="Subtitle.TLabel",
        ).grid(row=1, column=0, sticky="w")

        ttk.Label(heading, textvariable=self.session_var, style="Subtitle.TLabel").grid(
            row=0, column=1, sticky="e"
        )
        workspace = ttk.Notebook(outer)
        workspace.grid(row=1, column=0, sticky="nsew")
        room = ttk.Frame(workspace, padding=(4, 12))
        lab = ttk.Frame(workspace, padding=18)
        workspace.add(room, text="01  Match room")
        workspace.add(lab, text="02  Engine tools")
        room.columnconfigure(0, weight=1)
        room.rowconfigure(2, weight=1)
        self._build_controls(room)
        self._build_lab(lab)

        content = ttk.Panedwindow(room, orient=tk.HORIZONTAL)
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

        openings = ttk.Frame(controls)
        openings.grid(row=3, column=0, columnspan=6, sticky="ew", pady=(10, 0))
        openings.columnconfigure(3, weight=1)
        ttk.Label(openings, text="Start from").grid(row=0, column=0, padx=(0, 8))
        self.opening_box = ttk.Combobox(
            openings,
            textvariable=self.opening_var,
            width=23,
            values=("Paired opening suite", "Standard position", "Custom FEN"),
            state="readonly",
        )
        self.opening_box.grid(row=0, column=1)
        ttk.Label(openings, text="Custom FEN").grid(row=0, column=2, padx=8)
        self.fen_box = ttk.Entry(openings, textvariable=self.fen_var)
        self.fen_box.grid(row=0, column=3, sticky="ew")
        ttk.Label(openings, text="Total ply cap (draw)").grid(row=0, column=4, padx=8)
        self.cap_box = ttk.Entry(openings, textvariable=self.ply_cap_var, width=6)
        self.cap_box.grid(row=0, column=5)

        presets = ttk.Frame(controls)
        presets.grid(row=2, column=0, columnspan=5, sticky="w", pady=(10, 0))
        ttk.Label(presets, text="Presets:").pack(side=tk.LEFT)
        ttk.Button(presets, text="Fast 10s + 0.1s", command=self._set_fast_timing).pack(
            side=tk.LEFT, padx=(6, 4)
        )
        ttk.Button(presets, text="120s + 0.5s", command=self._set_official_timing).pack(
            side=tk.LEFT
        )

        button_box = ttk.Frame(controls)
        button_box.grid(row=1, column=5, rowspan=2, sticky="ns", padx=(14, 0))
        self.start_button = ttk.Button(
            button_box, text="Start series", command=self._start_match, style="Accent.TButton"
        )
        self.start_button.pack(fill=tk.X)
        self.stop_button = ttk.Button(
            button_box, text="Stop", command=self._request_stop, state=tk.DISABLED
        )
        self.stop_button.pack(fill=tk.X, pady=(6, 0))

        self.progress = ttk.Progressbar(controls, mode="determinate")
        self.progress.grid(row=4, column=0, columnspan=6, sticky="ew", pady=(12, 0))

        self.control_widgets: tuple[ttk.Combobox | ttk.Spinbox | ttk.Entry, ...] = (
            self.competitor_a_box,
            self.competitor_b_box,
            self.games_box,
            self.base_box,
            self.increment_box,
            self.opening_box,
            self.fen_box,
            self.cap_box,
        )

    def _build_board_panel(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        parent.bind("<Configure>", self._resize_board)

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
        ttk.Checkbutton(
            lower, text="Follow live", variable=self.auto_follow, command=self._follow_live
        ).grid(row=1, column=1, sticky="e", pady=6)
        ttk.Label(
            parent, textvariable=self.position_var, style="Subtitle.TLabel", wraplength=500
        ).grid(row=4, column=0, sticky="w", pady=12)

    def _build_details_panel(self, parent: ttk.Frame) -> None:
        parent.rowconfigure(1, weight=1)
        parent.columnconfigure(0, weight=1)

        statistics = ttk.LabelFrame(parent, text="Statistics", padding=12)
        statistics.grid(row=0, column=0, sticky="ew")
        statistics.columnconfigure(0, weight=1)
        ttk.Label(
            statistics, textvariable=self.record_var, style="Stat.TLabel", wraplength=580
        ).grid(row=0, column=0, sticky="w")
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
        telemetry_tab = ttk.Frame(notebook, padding=8)
        analysis_tab = ttk.Frame(notebook, padding=8)
        notebook.add(telemetry_tab, text="Live telemetry")
        notebook.add(moves_tab, text="Moves")
        notebook.add(analysis_tab, text="Series analysis")
        notebook.add(results_tab, text="Results")
        self._build_moves_tab(moves_tab)
        self._build_results_tab(results_tab)
        self._build_telemetry(telemetry_tab)
        self.analysis_text = self._text_panel(analysis_tab)

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
            background=PANEL,
            foreground=INK,
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
        self.export_button.grid(row=1, column=0, sticky="w", pady=(8, 0))
        exports = ttk.Frame(parent)
        exports.grid(row=2, column=0, sticky="ew", pady=6)
        ttk.Button(exports, text="Export JSON…", command=lambda: self._export_data("json")).pack(
            side=tk.LEFT, padx=(0, 8)
        )
        ttk.Button(exports, text="Export move CSV…", command=lambda: self._export_data("csv")).pack(
            side=tk.LEFT
        )
        ttk.Label(exports, text="Select a game to inspect", style="Subtitle.TLabel").pack(
            side=tk.RIGHT
        )
        self.results_tree.bind("<<TreeviewSelect>>", self._inspect_game)

    def _text_panel(self, parent: ttk.Frame) -> tk.Text:
        parent.rowconfigure(0, weight=1)
        parent.columnconfigure(0, weight=1)
        widget = tk.Text(
            parent,
            background=PANEL,
            foreground=INK,
            insertbackground=INK,
            font=("Menlo", 11),
            wrap=tk.WORD,
            padx=12,
            pady=12,
            relief=tk.FLAT,
            state=tk.DISABLED,
            width=48,
            height=10,
        )
        scroll = ttk.Scrollbar(parent, command=widget.yview)
        widget.configure(yscrollcommand=scroll.set)
        widget.grid(row=0, column=0, sticky="nsew")
        scroll.grid(row=0, column=1, sticky="ns")
        return widget

    def _build_telemetry(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(2, weight=1)
        self.live_var = tk.StringVar(value="Search telemetry appears after each move.")
        ttk.Label(parent, textvariable=self.live_var, wraplength=580, style="Stat.TLabel").grid(
            row=0, column=0, sticky="w", pady=(0, 8)
        )
        self.chart = tk.Canvas(parent, height=150, background=PANEL, highlightthickness=0)
        self.chart.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        self.chart.bind("<Configure>", lambda event: self._draw_charts())
        table_frame = ttk.Frame(parent)
        table_frame.grid(row=2, column=0, sticky="nsew")
        table_frame.rowconfigure(0, weight=1)
        table_frame.columnconfigure(0, weight=1)
        columns = ("ply", "side", "move", "time", "depth", "nodes", "nps", "tt", "clock")
        self.telemetry_tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=7)
        for col, label, width in zip(
            columns,
            ("Ply", "Side", "Move", "Time ms", "Depth", "Nodes", "Nodes/s", "TT hits", "Clock s"),
            (45, 50, 60, 85, 60, 90, 90, 75, 85),
            strict=True,
        ):
            self.telemetry_tree.heading(col, text=label)
            self.telemetry_tree.column(col, width=width, minwidth=40, stretch=False)
        vertical = ttk.Scrollbar(table_frame, command=self.telemetry_tree.yview)
        horizontal = ttk.Scrollbar(
            table_frame, orient=tk.HORIZONTAL, command=self.telemetry_tree.xview
        )
        self.telemetry_tree.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        self.telemetry_tree.grid(row=0, column=0, sticky="nsew")
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal.grid(row=1, column=0, sticky="ew")
        self.telemetry_tree.bind("<<TreeviewSelect>>", self._inspect_move)
        ttk.Label(
            parent,
            text="— = not reported · depth = completed iteration · select a move to inspect",
            style="Subtitle.TLabel",
            wraplength=580,
        ).grid(row=3, column=0, sticky="w", pady=8)

    def _build_lab(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(3, weight=1)
        ttk.Label(parent, text="A workbench for your search engine", style="Title.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(
            parent,
            text="Run checks here, without leaving the app. Jobs and matches run one at a time.\n"
            "These tools target the working agent and frozen Gabriel—not the match selectors.",
            style="Subtitle.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(8, 22))
        cards = ttk.Frame(parent)
        cards.grid(row=2, column=0, sticky="ew", pady=(0, 18))
        self.lab_buttons = []
        for column, (title, description, kind) in enumerate(
            (
                (
                    "01 / Correctness",
                    "Legal moves, special rules, draw handling,\nTT bounds and timeout safety.",
                    "verify",
                ),
                (
                    "02 / Search benchmark",
                    "One-second positions against Gabriel.\nCompare ordering and table variants.",
                    "benchmark",
                ),
            )
        ):
            cards.columnconfigure(column, weight=1)
            card = ttk.LabelFrame(cards, text=title, padding=20)
            card.grid(row=0, column=column, sticky="nsew", padx=(0, 14))
            ttk.Label(card, text=description).pack(anchor="w", pady=(0, 15))
            button = ttk.Button(
                card,
                text="Run " + kind,
                style="Accent.TButton",
                command=partial(self._start_lab, kind),
            )
            button.pack(anchor="w")
            self.lab_buttons.append(button)
        console = ttk.Frame(parent)
        console.grid(row=3, column=0, sticky="nsew")
        self.lab_text = self._text_panel(console)
        self.lab_stop = ttk.Button(
            parent, text="Cancel tool", state=tk.DISABLED, command=self._request_stop
        )
        self.lab_stop.grid(row=4, column=0, sticky="e", pady=12)

    def _start_lab(self, kind: str) -> None:
        if self.worker is not None and self.worker.is_alive():
            return
        output = self._new_output(kind)
        self.cancel_event.clear()
        self.lab_running = True
        self._set_running(True)
        self._replace_text(self.lab_text, f"Running {kind}…\n\n")
        self.session_var.set("ENGINE TOOLS  /  RUNNING")
        self.worker = threading.Thread(
            target=run_job,
            args=(kind, REPOSITORY, output, self.events.put, self.cancel_event),
            daemon=True,
        )
        self.worker.start()

    def _new_output(self, label: str) -> Path:
        folder = REPOSITORY / "match_maker" / "results"
        folder.mkdir(parents=True, exist_ok=True)
        return folder / f"{label}-{datetime.now():%Y%m%d-%H%M%S-%f}"

    def _replace_text(self, widget: tk.Text, text: str) -> None:
        widget.configure(state=tk.NORMAL)
        widget.delete("1.0", tk.END)
        widget.insert("1.0", text)
        widget.configure(state=tk.DISABLED)

    def _choose_defaults(self) -> None:
        names = list(self.models)
        if not names:
            self.status_var.set("No folders containing agent.py were found.")
            self.start_button.configure(state=tk.DISABLED)
            return
        self.competitor_a_var.set(names[0])
        gabriel = "Past model / Gabriel"
        self.competitor_b_var.set(
            gabriel if gabriel in self.models else names[min(1, len(names) - 1)]
        )

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
            ply_cap = int(self.ply_cap_var.get())
        except (ValueError, OverflowError):
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

        if not 1 <= ply_cap <= 2000:
            messagebox.showerror("Invalid settings", "Ply cap must be between 1 and 2,000.")
            return None
        if self.opening_var.get() == "Custom FEN":
            try:
                board = chess.Board(self.fen_var.get())
                if not board.is_valid() or board.ply() >= ply_cap:
                    raise ValueError("Invalid position or starting ply already at the cap.")
            except ValueError as error:
                messagebox.showerror("Invalid FEN", str(error))
                return None

        return SeriesConfig(
            competitor_a_name=name_a,
            competitor_a_path=self.models[name_a],
            competitor_b_name=name_b,
            competitor_b_path=self.models[name_b],
            games=games,
            base_ms=base_ms,
            increment_ms=increment_ms,
            ply_cap=ply_cap,
            opening_mode=self.opening_var.get(),
            custom_fen=self.fen_var.get(),
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
        self.config = config
        self.output_base = self._new_output("series")
        self.series_started_at = time.monotonic()
        self.current_records.clear()
        self.auto_follow.set(True)
        self.telemetry_tree.delete(*self.telemetry_tree.get_children())
        self.session_var.set("MATCH ROOM  /  RUNNING")
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
            self.opening_box.configure(state="readonly")
        for button in self.lab_buttons:
            button.configure(state=tk.DISABLED if running else tk.NORMAL)
        self.lab_stop.configure(state=tk.NORMAL if running and self.lab_running else tk.DISABLED)
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

    def _handle_event(self, event: MatchEvent | LabOutput) -> None:
        if isinstance(event, LabOutput):
            self.lab_text.configure(state=tk.NORMAL)
            self.lab_text.insert(tk.END, event.text)
            self.lab_text.configure(state=tk.DISABLED)
            self.lab_text.see(tk.END)
            if event.finished:
                self.lab_running = False
                self._set_running(False)
                self.session_var.set("ENGINE TOOLS  /  FINISHED")
        elif isinstance(event, GameStarted):
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
        self.game_in_progress = True
        self.current_records.clear()
        self.game_a_white = event.competitor_a_is_white
        self.initial_ply = chess.Board(event.initial_fen).ply()
        self.auto_follow.set(True)
        self.telemetry_tree.delete(*self.telemetry_tree.get_children())
        self.live_var.set("Initializing engines…")
        self._draw_charts()
        self.current_fen = event.initial_fen
        self.last_move_uci = ""
        self.move_sans.clear()
        self.clock_ms = {chess.WHITE: event.base_ms, chess.BLACK: event.base_ms}
        self.thinking_color = None
        self.white_player_var.set(f"White · {event.white_name}")
        self.black_player_var.set(f"Black · {event.black_name}")
        self.game_progress_var.set(
            f"Game {event.game_number} / {event.total_games} · {event.opening}"
        )
        self.status_var.set(f"Starting game {event.game_number}…")
        self._render_moves()
        self._draw_board()

    def _handle_position_changed(self, event: PositionChanged) -> None:
        self.current_records.append(event.record)
        if self.auto_follow.get():
            self.current_fen = event.fen
            self.last_move_uci = event.last_move_uci
        self.move_sans.append(event.last_move_san)
        self.clock_ms = {chess.WHITE: event.white_ms, chess.BLACK: event.black_ms}
        self.thinking_color = None
        self.status_var.set(f"Move {event.ply}: {event.last_move_san}")
        self._render_moves()
        self._append_telemetry(event.record)
        self._draw_charts()
        self._update_position_stats()
        self._draw_board()

    def _handle_game_summary(self, summary: GameSummary) -> None:
        self.game_in_progress = False
        self.summaries.append(summary)
        self.terminations[summary.termination] += 1
        self.total_plies += summary.plies
        self.current_fen = summary.final_fen
        self.clock_ms = {chess.WHITE: summary.white_ms, chess.BLACK: summary.black_ms}
        self.thinking_color = None

        if summary.result == "draw":
            self.a_draws += 1
        elif summary.result != "void":
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
        self._autosave()

    def _handle_series_finished(self, event: SeriesFinished) -> None:
        self.thinking_color = None
        self._set_running(False)
        self.session_var.set(
            "MATCH ROOM  /  STOPPED" if event.cancelled else "MATCH ROOM  /  COMPLETE"
        )
        self._autosave(unfinished=event.cancelled)
        if event.cancelled:
            self.status_var.set(f"Series stopped after {event.completed_games} completed games.")
        else:
            score = (self.a_wins + self.a_draws / 2) / max(
                1, self.a_wins + self.a_draws + self.a_losses
            )
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
            scored = self.a_wins + self.a_draws + self.a_losses
            score = (self.a_wins + self.a_draws / 2) / max(1, scored)
            average_plies = self.total_plies / completed
            voids = completed - scored
            self.score_var.set(
                f"Score: {score:.1%} · {scored} scored games · {voids} voids excluded"
                if scored
                else f"Score: — · {voids} voids excluded"
            )
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
        self._update_analysis()

    def _render_moves(self) -> None:
        lines: list[str] = []
        for index, san in enumerate(self.move_sans):
            ply = self.initial_ply + index
            prefix = f"{ply // 2 + 1}." if ply % 2 == 0 else f"{ply // 2 + 1}…"
            lines.append(f"{prefix:>6} {san}")
        self.moves_text.configure(state=tk.NORMAL)
        self.moves_text.delete("1.0", tk.END)
        self.moves_text.insert("1.0", "\n".join(lines))
        self.moves_text.configure(state=tk.DISABLED)
        self.moves_text.see(tk.END)

    def _append_telemetry(self, record: MoveRecord) -> None:
        values = (
            record.ply,
            record.color,
            record.san,
            f"{record.elapsed_ms:.1f}",
            _number(record.depth),
            _number(record.nodes),
            _number(record.nps),
            _number(record.tt_hits),
            f"{record.clock_ms / 1000:.2f}",
        )
        item = self.telemetry_tree.insert("", tk.END, values=values)
        self.telemetry_tree.see(item)
        self.live_var.set(
            f"{record.color.title()} · {record.san}    {record.elapsed_ms:.1f} ms\n"
            f"Depth {_number(record.depth)}   /   {_number(record.nodes)} nodes   /   "
            f"{_number(record.nps)} nodes/s"
        )

    def _draw_charts(self) -> None:
        self.chart.delete("all")
        width = max(200, self.chart.winfo_width())
        for panel, (field, title) in enumerate(
            (("elapsed_ms", "Response time · ms"), ("depth", "Completed search depth · plies"))
        ):
            left = panel * width / 2 + 40
            right = (panel + 1) * width / 2 - 16
            self.chart.create_text(
                left, 12, text=title, anchor="w", fill=MUTED, font=("Helvetica", 10)
            )
            values = [
                getattr(r, field) for r in self.current_records if getattr(r, field) is not None
            ]
            maximum = max(values, default=1) or 1
            self.chart.create_line([left, 32.0, left, 125.0, right, 125.0], fill="#3b5060")
            self.chart.create_text(
                left - 5, 36, text=f"{maximum:.0f}", anchor="e", fill=MUTED, font=("Helvetica", 9)
            )
            self.chart.create_text(
                right, 140, text="move sequence →", anchor="e", fill=MUTED, font=("Helvetica", 9)
            )
            if not values:
                self.chart.create_text((left + right) / 2, 80, text="No data yet", fill=MUTED)
            for color, ink in (("white", ACCENT), ("black", "#e6b878")):
                points: list[float] = []
                for i, record in enumerate(self.current_records):
                    value = getattr(record, field)
                    if record.color != color or value is None:
                        continue
                    x = left + i / max(1, len(self.current_records) - 1) * (right - left)
                    y = 125 - value / maximum * 86
                    points.extend((x, y))
                    self.chart.create_oval(x - 2, y - 2, x + 2, y + 2, fill=ink, outline=ink)
                if len(points) >= 4:
                    self.chart.create_line(points, fill=ink, width=2)
        self.chart.create_text(
            width / 2,
            150,
            text="White: mint   ·   Black: amber",
            fill=MUTED,
            anchor="s",
            font=("Helvetica", 9),
        )

    def _update_position_stats(self) -> None:
        board = chess.Board(self.current_fen)
        material = sum(
            value * (len(board.pieces(piece, chess.WHITE)) - len(board.pieces(piece, chess.BLACK)))
            for piece, value in ((1, 1), (2, 3), (3, 3), (4, 5), (5, 9))
        )
        self.position_var.set(
            f"Material (White - Black): {material:+d} pawns · "
            f"Legal moves: {board.legal_moves.count()}\n"
            f"Halfmove clock: {board.halfmove_clock} / 100 · "
            f"{'CHECK' if board.is_check() else 'Not in check'} · "
            "Material is not an engine evaluation."
        )

    def _update_analysis(self) -> None:
        stats = series_statistics(self.summaries)
        lines = ["SERIES BREAKDOWN · Competitor A perspective", ""]
        for label in ("white", "black"):
            row = stats[label]
            score = "—" if row["score"] is None else f"{row['score']:.1%}"
            lines.append(
                f"As {label:5}: +{row['wins']} ={row['draws']} -{row['losses']}  score {score}"
            )
        lines += ["", "BY OPENING"]
        for opening, row in stats["openings"].items():
            lines.append(f"{opening}: +{row['wins']} ={row['draws']} -{row['losses']}")
        for side, name in (("A", self.competitor_a_name), ("B", self.competitor_b_name)):
            row = stats["competitors"][side]
            lines += [
                "",
                f"{side} / {name}",
                f"Moves: {row['moves']} · Total move time: {row['total_seconds']:.2f} s",
                f"Time ms: mean {_number(row['mean_ms'], 1)} / "
                f"median {_number(row['median_ms'], 1)}",
                f"         p95 {_number(row['p95_ms'], 1)} / max {_number(row['max_ms'], 1)}",
                f"Depth: mean {_number(row['mean_depth'], 1)} / max {_number(row['max_depth'])}",
                f"Depth reporting: {row['depth_samples']} of {row['moves']} moves",
                f"Total nodes: {_number(row['total_nodes'])} · "
                f"Mean NPS: {_number(row['mean_nps'])}",
                f"TT score cutoffs reported: {_number(row['tt_hits'])}",
                f"Captures: {row['captures']} · Checks: {row['checks']} · "
                f"Promotions: {row['promotions']}",
                f"Lowest post-move clock: {_number(row['min_clock_ms'])} ms",
            ]
            initialization = [
                g.white_init_seconds
                if (side == "A") == g.competitor_a_is_white
                else g.black_init_seconds
                for g in self.summaries
            ]
            if initialization:
                lines.append(
                    f"Mean initialization: {sum(initialization) / len(initialization):.2f} s"
                )
        lines += [
            "",
            f"Completed-game wall time (incl. init): {stats['total_wall_seconds']:.1f} s",
            "Voids excluded from scores. Missing telemetry is excluded from averages.",
            "Repeated openings are correlated; these scores are not a rating estimate.",
            "Move times include local IPC and telemetry. No extra analysis is run.",
        ]
        self._replace_text(self.analysis_text, "\n".join(lines))

    def _follow_live(self) -> None:
        if self.auto_follow.get() and self.current_records:
            record = self.current_records[-1]
            self.current_fen, self.last_move_uci = record.fen, record.uci
            self._update_position_stats()
            self._draw_board()

    def _inspect_move(self, event: tk.Event[tk.Misc]) -> None:
        selected = self.telemetry_tree.selection()
        if not selected:
            return
        index = self.telemetry_tree.index(selected[0])
        if index >= len(self.current_records):
            return
        self.auto_follow.set(False)
        record = self.current_records[index]
        self.current_fen, self.last_move_uci = record.fen, record.uci
        self._update_position_stats()
        self._draw_board()

    def _inspect_game(self, event: tk.Event[tk.Misc]) -> None:
        if self.worker is not None and self.worker.is_alive():
            return
        selected = self.results_tree.selection()
        if not selected:
            return
        game = self.summaries[self.results_tree.index(selected[0])]
        self.current_records = list(game.moves)
        self.move_sans = [r.san for r in game.moves]
        self.initial_ply = chess.Board(game.initial_fen).ply()
        self.current_fen, self.last_move_uci = (
            game.final_fen,
            game.moves[-1].uci if game.moves else "",
        )
        self.white_player_var.set(f"White · {game.white_name}")
        self.black_player_var.set(f"Black · {game.black_name}")
        self.clock_ms = {chess.WHITE: game.white_ms, chess.BLACK: game.black_ms}
        self.telemetry_tree.delete(*self.telemetry_tree.get_children())
        for record in game.moves:
            self._append_telemetry(record)
        self.game_progress_var.set(f"Reviewing game {game.game_number} · {game.opening}")
        self._render_moves()
        self._draw_charts()
        self._update_position_stats()
        self._draw_board()

    def _autosave(self, unfinished: bool = False) -> None:
        if self.output_base is None:
            return
        try:
            export_json(
                self.output_base.with_suffix(".json"),
                self.summaries,
                self.config,
                self.current_records if unfinished and self.game_in_progress else None,
            )
            self.output_base.with_suffix(".pgn").write_text(
                "\n\n".join(g.pgn for g in self.summaries) + "\n"
            )
        except OSError as error:
            self.status_var.set(f"Autosave failed: {error}. Use Export to save elsewhere.")

    def _export_data(self, kind: str) -> None:
        if not self.summaries:
            messagebox.showinfo("No completed games", "Finish a game before exporting statistics.")
            return
        filename = filedialog.asksaveasfilename(
            title=f"Export {kind.upper()}",
            defaultextension=f".{kind}",
            initialfile=f"chess-lab.{kind}",
            filetypes=((kind.upper(), f"*.{kind}"),),
        )
        if filename:
            try:
                if kind == "json":
                    export_json(Path(filename), self.summaries, self.config)
                else:
                    export_csv(Path(filename), self.summaries)
                self.status_var.set(f"Exported {filename}")
            except OSError as error:
                messagebox.showerror("Export failed", str(error))

    def _resize_board(self, event: tk.Event[tk.Misc]) -> None:
        size = max(240, min(512, event.width - 24, event.height - 210)) // 8 * 8
        if size // 8 != self.square_pixels:
            self.square_pixels = size // 8
            self.board_canvas.configure(width=size, height=size)
            self._draw_board()

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

                x0 = display_file * self.square_pixels
                y0 = display_rank * self.square_pixels
                self.board_canvas.create_rectangle(
                    x0,
                    y0,
                    x0 + self.square_pixels,
                    y0 + self.square_pixels,
                    fill=color,
                    outline=color,
                )
                piece = board.piece_at(square)
                if piece is not None:
                    self.board_canvas.create_text(
                        x0 + self.square_pixels / 2,
                        y0 + self.square_pixels / 2 + 1,
                        text=piece.unicode_symbol(),
                        font=("Arial Unicode MS", max(20, round(self.square_pixels * 0.66))),
                        fill="#17212b",
                    )

                file_label = chess.FILE_NAMES[chess.square_file(square)]
                rank_label = str(chess.square_rank(square) + 1)
                label_color = "#506070" if light else "#eef4e8"
                if display_rank == 7:
                    self.board_canvas.create_text(
                        x0 + self.square_pixels - 5,
                        y0 + self.square_pixels - 4,
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
        try:
            Path(filename).write_text("\n\n".join(summary.pgn for summary in self.summaries) + "\n")
            self.status_var.set(f"Exported {len(self.summaries)} games to {filename}")
        except OSError as error:
            messagebox.showerror("Export failed", str(error))

    def _on_close(self) -> None:
        if self.worker is None or not self.worker.is_alive():
            self.root.destroy()
            return
        self.closing = True
        self.cancel_event.set()
        self.stop_button.configure(state=tk.DISABLED)
        self.status_var.set("Closing after the current agent response…")


def _number(value: float | int | None, digits: int = 0) -> str:
    return "—" if value is None else f"{value:,.{digits}f}"


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
