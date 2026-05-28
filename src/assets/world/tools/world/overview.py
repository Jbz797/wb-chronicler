#!/usr/bin/env python3

# Primary source: `map.meta` (sibling of `map.wbox`). Falls back to the compressed
# save only for live-only collections not exposed in `map.meta` (armies, frozen
# tiles, relations). User-facing docs live in `tools/tools.md`.
#
# ⚠️ Output keys must stay self-descriptive — the chronicler reads them with no other
# context. Prefer disambiguated names (e.g. `wild_creatures` over `creatures`).
# Exception: keep the WB-native name verbatim for anything sourced from the raw save
# (e.g. `relations`, `world_time`) — the chronicler also reads the save directly and
# divergent names would create friction.

import json
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).parent.parent))
from shared import CURRENT_SAVE, emit, load_save, parse_sections  # noqa: E402

_ALL_SECTIONS = ("cumulative", "metadata", "snapshot")

# Chronicler key => map.meta top-level key. Most match 1:1; `wild_creatures` aliases `mobs`.
_SNAPSHOT_KEYS = {
    "alliances": "alliances",
    "books": "books",
    "cities": "cities",
    "clans": "clans",
    "cultures": "cultures",
    "equipment": "equipment",
    "families": "families",
    "kingdoms": "kingdoms",
    "languages": "languages",
    "population": "population",
    "religions": "religions",
    "subspecies": "subspecies",
    "vegetation": "vegetation",
    "wars": "wars",
    "wild_creatures": "mobs",
}

# `water` aggregates `deaths_water` (hydrophobic damage) + `deaths_drowning` (suffocation).
_DEATH_CAUSES = {
    "eaten": ("deaths_eaten",),
    "explosion": ("deaths_explosion",),
    "fire": ("deaths_fire",),
    "hunger": ("deaths_hunger",),
    "old_age": ("deaths_age",),
    "water": ("deaths_water", "deaths_drowning"),
    "weapon": ("deaths_weapon",),
}


def _build_snapshot(meta: dict, map_stats: dict) -> dict:
    # `frozen_tiles` / `relations` aren't in `map.meta` — decompress the save.
    save = load_save()
    return dict(
        sorted(
            {
                **{k: int(meta.get(v, 0)) for k, v in _SNAPSHOT_KEYS.items()},
                "armies": int(map_stats.get("armiesCreated", 0)) - int(map_stats.get("armiesDestroyed", 0)),
                "frozen_tiles": len(save.get("frozen_tiles") or []),
                "houses": int(map_stats.get("housesBuilt", 0))
                - int(map_stats.get("housesDestroyed", 0)),  # current city-buildings (matches `world_statistics_houses`)
                "plots_active": len(save.get("plots") or []),
                "relations": len(save.get("relations") or []),
            }.items()
        )
    )


def _build_cumulative(map_stats: dict) -> dict:
    return {
        "books_read": int(map_stats.get("booksRead", 0)),
        "deaths": dict(sorted((k, sum(int(map_stats.get(s, 0)) for s in srcs)) for k, srcs in _DEATH_CAUSES.items())),
        "plots_succeeded": int(map_stats.get("plotsSucceeded", 0)),
    }


def _build_metadata(map_stats: dict) -> dict:
    return {
        "age_id": map_stats.get("world_age_id") or "",  # WorldAgeLibrary key (e.g. `stone_age`)
        "world_time": round(float(map_stats.get("world_time", 0)), 2),  # months elapsed; 60 = 1 year — name kept aligned with the raw save field
    }


def main(argv: list[str]) -> int:
    try:
        sections = parse_sections(argv[0] if argv else None, _ALL_SECTIONS)
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 2
    meta_path = CURRENT_SAVE.with_name("map.meta")
    if not meta_path.exists():
        print(f"no map.meta found next to {CURRENT_SAVE}", file=sys.stderr)
        return 2
    meta = json.loads(meta_path.read_text())
    map_stats = meta.get("mapStats") or {}
    out: dict = {}
    if "cumulative" in sections:
        out["cumulative"] = _build_cumulative(map_stats)
    if "metadata" in sections:
        out["metadata"] = _build_metadata(map_stats)
    if "snapshot" in sections:
        out["snapshot"] = _build_snapshot(meta, map_stats)
    emit(out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
