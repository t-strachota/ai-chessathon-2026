"""Run fixed lab commands off the GUI thread, with cancellation and log capture."""

import subprocess
import sys
import threading
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class LabOutput:
    text: str
    finished: bool = False


def run_job(
    kind: str,
    repository: Path,
    output: Path,
    callback: Callable[[LabOutput], None],
    cancel: threading.Event,
) -> None:
    module = "match_maker.lab.verify" if kind == "verify" else "match_maker.lab.benchmark"
    command = [sys.executable, "-u", "-m", module]
    if kind != "verify":
        command += ["--seconds", "3", "--out", str(output.with_suffix(".json"))]
    process: subprocess.Popen[str] | None = None
    done = threading.Event()
    try:
        process = subprocess.Popen(
            command, cwd=repository, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
        )
        child = process

        def watch() -> None:
            while not done.wait(0.1):
                if cancel.is_set():
                    child.kill()
                    return

        watcher = threading.Thread(target=watch, daemon=True)
        watcher.start()
        assert process.stdout is not None
        with output.with_suffix(".log").open("w") as log, process.stdout:
            for line in process.stdout:
                log.write(line)
                log.flush()
                callback(LabOutput(line))
        code = process.wait()
        label = (
            "Cancelled" if cancel.is_set() else "Passed" if code == 0 else f"Failed (exit {code})"
        )
        callback(LabOutput(f"\n{label}. Log: {output.with_suffix('.log')}\n", True))
    except Exception as error:
        callback(LabOutput(f"\nLab error: {error}\n", True))
    finally:
        done.set()
        if process is not None:
            if process.poll() is None:
                process.kill()
            process.wait()
