"""Read optional telemetry using the unmodified harness process transport."""

import json
import math
import sys
from pathlib import Path

from harness.sandbox import Agent


class DiagnosticAgent(Agent):
    def __init__(self, directory: Path) -> None:
        super().__init__(
            [
                sys.executable,
                str(Path(__file__).with_name("diagnostic_runner.py")),
                str(directory.resolve()),
            ]
        )
        self.stats: dict[str, float] = {}

    def _await_line(self, deadline: float) -> bytes | None:
        line = super()._await_line(deadline)
        self.stats = {}
        if line is not None:
            try:
                payload = json.loads(line)
                stats = payload.get("stats", {}) if isinstance(payload, dict) else {}
                if isinstance(stats, dict):
                    self.stats = {
                        key: float(value)
                        for key, value in stats.items()
                        if key
                        in {
                            "depth",
                            "nodes",
                            "tt_hits",
                            "nps",
                            "seconds",
                            "normal_seconds",
                            "hard_seconds",
                            "extended",
                        }
                        and type(value) in (int, float)
                        and math.isfinite(value)
                        and 0 <= value < 1e18
                    }
            except (ValueError, UnicodeError):
                pass
        return line
