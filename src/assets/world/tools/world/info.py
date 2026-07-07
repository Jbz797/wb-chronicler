#!/usr/bin/env python3

# Source: `map.meta` (sibling of `map.wbox`), fallback raw save for live-only collections (armies, frozen tiles, relations). User-facing docs: `tools/tools.md`.
#
# ⚠️ Output keys must stay self-descriptive (chronicler reads them with no other context). Prefer disambiguated names (e.g. `wild_creatures` over `creatures`).
# Exception: WB-native names verbatim for raw-save fields (e.g. `relations`, `world_time`) — chronicler reads save directly, divergent names would cause friction.

import json
import sys
from collections import Counter
from pathlib import Path


sys.path.insert(0, str(Path(__file__).parent.parent))
from shared import CURRENT_SAVE, civic_building_ids, emit, index_by_id, load_save, parse_sections  # noqa: E402

_ALL_SECTIONS = ("cumulative", "leaders", "metadata", "snapshot")

# Chronicler key => WB save fields (sum). Mirrors the 16 rows of WB's « Deaths » panel; `water` is hydrophobic damage (separate from `drowning`).
_DEATH_CAUSES = {
    "acid": ("deaths_acid",),
    "divine": ("deaths_divine",),
    "drowning": ("deaths_drowning",),
    "eaten": ("deaths_eaten",),
    "explosion": ("deaths_explosion",),
    "fire": ("deaths_fire",),
    "gravity": ("deaths_gravity",),
    "hunger": ("deaths_hunger",),
    "infection": ("deaths_infection",),
    "old_age": ("deaths_age",),
    "other": ("deaths_other",),
    "plague": ("deaths_plague",),
    "poison": ("deaths_poison",),
    "tumor": ("deaths_tumor",),
    "water": ("deaths_water",),
    "weapon": ("deaths_weapon",),
}

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


def _build_cumulative(map_stats: dict) -> dict:
    # 0-count entries (counters + per-cause deaths) are dropped — UI treats missing keys as 0.
    deaths = ((k, sum(int(map_stats.get(s, 0)) for s in srcs)) for k, srcs in _DEATH_CAUSES.items())
    # Mix UI-driven (`CUMULATIVE_STATS`) + chronicler-only keys. Chronicler-only ones expose churn that net snapshots hide (e.g. 5 kingdoms fall + 5 rise → net 0).
    # Only the `_created` side of each binary lifecycle is stored — `destroyed = created − snapshot.alive` is derivable, so the counter would be redundant.
    counters = {
        "alliances_made": int(map_stats.get("alliancesMade", 0)),
        "armies_created": int(map_stats.get("armiesCreated", 0)),
        "books_burnt": int(map_stats.get("booksBurnt", 0)),
        "books_read": int(map_stats.get("booksRead", 0)),
        "cities_conquered": int(map_stats.get("citiesConquered", 0)),
        "cities_created": int(map_stats.get("citiesCreated", 0)),
        "cities_rebelled": int(map_stats.get("citiesRebelled", 0)),
        "clans_created": int(map_stats.get("clansCreated", 0)),
        "creatures_born": int(map_stats.get("creaturesBorn", 0)),  # natural reproduction
        "creatures_created": int(map_stats.get("creaturesCreated", 0)),  # divine spawn + worldgen
        "cultures_created": int(map_stats.get("culturesCreated", 0)),
        "evolutions": int(map_stats.get("evolutions") or 0),
        "families_created": int(map_stats.get("familiesCreated", 0)),
        "houses_built": int(map_stats.get("housesBuilt", 0)),
        "kingdoms_created": int(map_stats.get("kingdomsCreated", 0)),
        "languages_created": int(map_stats.get("languagesCreated", 0)),
        "metamorphosis": int(map_stats.get("metamorphosis") or 0),
        "peaces_made": int(map_stats.get("peacesMade", 0)),
        "plots_started": int(map_stats.get("plotsStarted", 0)),
        "plots_succeeded": int(map_stats.get("plotsSucceeded", 0)),
        "religions_created": int(map_stats.get("religionsCreated", 0)),
        "subspecies_created": int(map_stats.get("subspeciesCreated", 0)),
        "wars_started": int(map_stats.get("warsStarted", 0)),
    }
    out: dict = {k: v for k, v in counters.items() if v > 0}
    out["deaths"] = dict(sorted((k, v) for k, v in deaths if v > 0))
    return dict(sorted(out.items()))


# Top entity per category (populous village/kingdom, dominant culture/language/religion/subspecies, top renown) — mirrors WB's « Records » panel.
def _build_leaders(save: dict) -> dict:
    actors = save.get("actors_data") or []
    cities_by_id = index_by_id(save.get("cities") or [])
    kingdoms_by_id = index_by_id(save.get("kingdoms") or [])
    cultures_by_id = index_by_id(save.get("cultures") or [])
    languages_by_id = index_by_id(save.get("languages") or [])
    religions_by_id = index_by_id(save.get("religions") or [])
    subspecies_by_id = index_by_id(save.get("subspecies") or [])
    counts: dict[str, Counter] = {k: Counter() for k in ("city", "kingdom", "culture", "language", "religion", "subspecies")}
    for a in actors:
        if (a.get("asset_id") or "").startswith("boat_"):
            continue
        for key, field in (
            ("city", "cityID"),
            ("kingdom", "civ_kingdom_id"),
            ("culture", "culture"),
            ("language", "language"),
            ("religion", "religion"),
            ("subspecies", "subspecies"),
        ):
            if (v := a.get(field)) is not None:
                counts[key][v] += 1
    out: dict[str, dict] = {}
    for key, registry, dest in (
        ("city", cities_by_id, "most_populous_village"),
        ("kingdom", kingdoms_by_id, "most_populous_kingdom"),
        ("culture", cultures_by_id, "dominant_culture"),
        ("language", languages_by_id, "dominant_language"),
        ("religion", religions_by_id, "dominant_religion"),
        ("subspecies", subspecies_by_id, "dominant_subspecies"),
    ):
        if not counts[key]:
            continue
        top_id, value = counts[key].most_common(1)[0]
        entry = registry.get(top_id) or {}
        out[dest] = {"id": top_id, "name": entry.get("name") or f"#{top_id}", "value": value}
    # Most renowned civilian actor (excludes boats + creatures via `civ_kingdom_id` presence). Carries `asset_id` + `sex` so the UI can render the `<app-person-tag>`.
    civilians = [a for a in actors if a.get("civ_kingdom_id") and not (a.get("asset_id") or "").startswith("boat_")]
    if civilians:
        top = max(civilians, key=lambda a: int(a.get("renown") or 0))
        out["most_renowned_person"] = {
            "asset_id": top.get("asset_id"),
            "id": top.get("id"),
            "name": top.get("name") or f"#{top.get('id')}",
            "sex": "female" if top.get("sex") == 1 else "male",
            "value": int(top.get("renown") or 0),
        }
    clans = save.get("clans") or []
    if clans:
        top_clan = max(clans, key=lambda c: int(c.get("renown") or 0))
        out["most_renowned_clan"] = {"id": top_clan.get("id"), "name": top_clan.get("name") or f"#{top_clan.get('id')}", "value": int(top_clan.get("renown") or 0)}
    return dict(sorted(out.items()))


def _build_metadata(map_stats: dict) -> dict:
    age_duration = float(map_stats.get("current_world_ages_duration") or 0)
    age_progress = float(map_stats.get("current_age_progress") or 0)
    return {
        "age_id": map_stats.get("world_age_id") or "",  # WorldAgeLibrary key (e.g. `stone_age`)
        # Chronicler-only narrative hint, matches WB's UI counter « Lunes jusqu'au prochain âge ». Omitted when 0 / no current age.
        "months_until_next_age": int(age_duration * (1 - age_progress) / 5) if age_duration > 0 else 0,
        "world_time": round(float(map_stats.get("world_time", 0)), 2),
    }


# `frozen_tiles` / `relations` / `infected` aren't in `map.meta` — read from the decompressed save. `infected` mirrors WB's runtime `current_infected`.
def _build_snapshot(meta: dict, map_stats: dict, save: dict) -> dict:
    civic = civic_building_ids()
    asset_counts = Counter(b.get("asset_id") or "" for b in save.get("buildings", []))  # Count `asset_id`s once, classify distinct keys — avoids 3 scans.
    return dict(
        sorted(
            {
                **{k: int(meta.get(v, 0)) for k, v in _SNAPSHOT_KEYS.items()},
                "armies": int(map_stats.get("armiesCreated", 0)) - int(map_stats.get("armiesDestroyed", 0)),
                "buildings": sum(n for aid, n in asset_counts.items() if aid in civic),  # Built structures worldwide (nature excluded); `houses` = dwellings.
                "frozen_tiles": len(save.get("frozen_tiles") or []),
                "houses": sum(n for aid, n in asset_counts.items() if aid.startswith("house")),
                "infected": sum(1 for a in save.get("actors_data", []) if "infected" in (a.get("saved_traits") or [])),
                "plots_active": len(save.get("plots") or []),
                "relations": len(save.get("relations") or []),
                # `tree` substring catches every `Building_Tree` asset_id (pine/swamp/birch/…). ≤1% drift vs WB UI — counter moves between snapshots.
                "trees": sum(n for aid, n in asset_counts.items() if "tree" in aid),
            }.items()
        )
    )


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
    # Decompress once and share between `leaders` + `snapshot`; `cumulative`/`metadata` read from `map.meta` alone.
    if {"leaders", "snapshot"} & set(sections):
        save = load_save()
        if "leaders" in sections:
            out["leaders"] = _build_leaders(save)
        if "snapshot" in sections:
            out["snapshot"] = _build_snapshot(meta, map_stats, save)
    emit(out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
