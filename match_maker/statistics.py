"""Pure statistics and portable exports; missing telemetry is never treated as zero."""

import csv
import json
import math
from collections import Counter
from dataclasses import asdict
from pathlib import Path
from statistics import mean, median
from typing import Any

from match_maker.matches import GameSummary, MoveRecord, SeriesConfig


def move_statistics(records: list[MoveRecord]) -> dict[str, float | int | None]:
    times = sorted(r.elapsed_ms for r in records)
    depths = [r.depth for r in records if r.depth is not None]
    nodes = [r.nodes for r in records if r.nodes is not None]
    speeds = [r.nps for r in records if r.nps is not None]
    hits = [r.tt_hits for r in records if r.tt_hits is not None]
    return {
        "moves": len(records),
        "total_seconds": sum(times) / 1000,
        "mean_ms": mean(times) if times else None,
        "median_ms": median(times) if times else None,
        "p95_ms": times[max(0, math.ceil(len(times) * 0.95) - 1)] if times else None,
        "max_ms": max(times) if times else None,
        "mean_depth": mean(depths) if depths else None,
        "max_depth": max(depths) if depths else None,
        "depth_samples": len(depths),
        "total_nodes": sum(nodes) if nodes else None,
        "mean_nps": mean(speeds) if speeds else None,
        "tt_hits": sum(hits) if hits else None,
        "captures": sum(r.capture for r in records),
        "checks": sum(r.check for r in records),
        "promotions": sum(r.promotion for r in records),
        "min_clock_ms": min((r.clock_ms for r in records), default=None),
    }


def score_record(games: list[GameSummary]) -> dict[str, Any]:
    wins = losses = draws = voids = 0
    for game in games:
        if game.result == "void":
            voids += 1
        elif game.result == "draw":
            draws += 1
        elif (game.result == "white") == game.competitor_a_is_white:
            wins += 1
        else:
            losses += 1
    counted = wins + losses + draws
    return dict(
        wins=wins,
        draws=draws,
        losses=losses,
        voids=voids,
        scored_games=counted,
        score=(wins + draws / 2) / counted if counted else None,
    )


def series_statistics(games: list[GameSummary]) -> dict[str, Any]:
    sides: dict[str, list[MoveRecord]] = {"A": [], "B": []}
    for game in games:
        for record in game.moves:
            side = "A" if (record.color == "white") == game.competitor_a_is_white else "B"
            sides[side].append(record)
    return {
        **score_record(games),
        "completed_games": len(games),
        "technical_failures": sum(g.technical_failure for g in games),
        "terminations": dict(Counter(g.termination for g in games)),
        "mean_plies": mean(g.plies for g in games) if games else None,
        "total_wall_seconds": sum(g.elapsed_seconds for g in games),
        "white": score_record([g for g in games if g.competitor_a_is_white]),
        "black": score_record([g for g in games if not g.competitor_a_is_white]),
        "openings": {
            name: score_record([g for g in games if g.opening == name])
            for name in dict.fromkeys(g.opening for g in games)
        },
        "competitors": {side: move_statistics(records) for side, records in sides.items()},
    }


def export_json(
    path: Path,
    games: list[GameSummary],
    config: SeriesConfig | None,
    current: list[MoveRecord] | None = None,
) -> None:
    settings = asdict(config) if config else None
    if settings:
        settings = {
            key: str(value) if isinstance(value, Path) else value for key, value in settings.items()
        }
    payload = dict(
        schema_version=1,
        config=settings,
        statistics=series_statistics(games),
        games=[asdict(g) for g in games],
        unfinished_game_moves=[asdict(r) for r in current or []],
        telemetry_note="Depth/nodes/NPS/TT hits are optional self-reports; null = unknown.",
    )
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n")
    temporary.replace(path)


def export_csv(path: Path, games: list[GameSummary]) -> None:
    fields = ["game", "opening", "competitor", *MoveRecord.__dataclass_fields__]
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for game in games:
            for record in game.moves:
                side = "A" if (record.color == "white") == game.competitor_a_is_white else "B"
                writer.writerow(
                    dict(
                        game=game.game_number,
                        opening=game.opening,
                        competitor=side,
                        **asdict(record),
                    )
                )
