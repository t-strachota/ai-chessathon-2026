"""Local-only runner: same move contract, optional self-reported diagnostics.

Never packaged with the competition agent. No monkey-patching or extra search.
"""

import json
import math
import os
import sys
from importlib import import_module


def main() -> None:
    protocol = os.fdopen(os.dup(1), "w")
    os.dup2(2, 1)
    sys.path.insert(0, sys.argv[1])
    agent = import_module("agent")
    protocol.write(json.dumps({"ready": True}) + "\n")
    protocol.flush()
    for line in sys.stdin:
        request = json.loads(line)
        previous = getattr(agent, "LAST_SEARCH", None)
        if isinstance(previous, dict):
            previous.clear()
        move = agent.get_move(request["fen"], request["time_left_ms"])
        reported = getattr(agent, "LAST_SEARCH", {})
        stats = {}
        if isinstance(reported, dict):
            for name in ("depth", "nodes", "tt_hits", "nps", "seconds"):
                value = reported.get(name)
                if isinstance(value, (int, float)) and math.isfinite(value) and 0 <= value < 1e18:
                    stats[name] = value
        protocol.write(json.dumps({"move": move, "stats": stats}) + "\n")
        protocol.flush()


if __name__ == "__main__":
    main()
