"""Desktop smoke test; opens a real window and exercises matches and lab jobs."""

import argparse
import subprocess
import time
import tkinter as tk
from pathlib import Path

from match_maker.app import MatchMakerApp


def wait_for_work(root: tk.Tk, app: MatchMakerApp) -> None:
    deadline = time.monotonic() + 45
    while app.worker is not None and app.worker.is_alive():
        assert time.monotonic() < deadline, "Worker did not finish"
        root.update()
        time.sleep(0.02)
    for _ in range(5):
        root.update()
        time.sleep(0.06)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--screenshot", type=Path)
    args = parser.parse_args()
    root = tk.Tk()
    errors: list[str] = []

    def report_error(kind: type[BaseException], error: BaseException, trace: object) -> None:
        errors.append(f"{kind.__name__}: {error}")

    root.report_callback_exception = report_error
    app = MatchMakerApp(root)
    root.geometry("1280x940+20+25")
    root.update()
    try:
        root_bounds = (
            root.winfo_rootx(),
            root.winfo_rooty(),
            root.winfo_rootx() + root.winfo_width(),
            root.winfo_rooty() + root.winfo_height(),
        )

        def check_layout(widget: tk.Misc) -> None:
            if widget.winfo_ismapped() and widget.winfo_class() in {
                "TButton",
                "TLabel",
                "TCombobox",
                "TEntry",
                "Canvas",
            }:
                x, y = widget.winfo_rootx(), widget.winfo_rooty()
                assert x >= root_bounds[0] and y >= root_bounds[1], str(widget)
                assert x + widget.winfo_width() <= root_bounds[2] + 1, str(widget)
                assert y + widget.winfo_height() <= root_bounds[3] + 1, (
                    str(widget),
                    y,
                    widget.winfo_height(),
                    root_bounds,
                )
            for child in widget.winfo_children():
                check_layout(child)

        check_layout(root)
        app.games_var.set("2")
        app.base_seconds_var.set("5")
        app.increment_ms_var.set("100")
        app.ply_cap_var.set("16")
        app.competitor_b_var.set("Baseline / random")
        app._start_match()
        wait_for_work(root, app)
        assert len(app.summaries) == 2, app.status_var.get()
        assert any(r.depth is not None for g in app.summaries for r in g.moves)
        assert len(app.telemetry_tree.get_children()) == 6
        assert app.output_base and app.output_base.with_suffix(".json").is_file()
        app.results_tree.selection_set(app.results_tree.get_children()[0])
        root.update()
        app.telemetry_tree.selection_set(app.telemetry_tree.get_children()[0])
        root.update()
        assert not app.auto_follow.get()
        app._flip_board()
        root.update()
        if args.screenshot:
            root.lift()
            root.focus_force()
            root.update()
            time.sleep(0.3)
            region = (
                f"{root.winfo_rootx()},{root.winfo_rooty()},"
                f"{root.winfo_width()},{root.winfo_height()}"
            )
            capture = subprocess.run(
                ["/usr/sbin/screencapture", "-x", "-R", region, str(args.screenshot)], check=False
            )
            if capture.returncode:
                print("Screenshot unavailable (screen capture permission/display).")
        app._start_lab("verify")
        wait_for_work(root, app)
        assert "Passed." in app.lab_text.get("1.0", tk.END)
        app._start_lab("benchmark")
        app._request_stop()
        wait_for_work(root, app)
        assert "Cancelled." in app.lab_text.get("1.0", tk.END)
        assert not errors, errors
        print(
            "PASS: real GUI, two matches, telemetry, replay, autosave, "
            "lab verification, no Tk errors"
        )
    finally:
        app.cancel_event.set()
        root.destroy()


if __name__ == "__main__":
    main()
