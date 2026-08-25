#!/usr/bin/env python3

# Emits the world sections from the save alone (`mapStats` = WB's period-accurate counters), `tools/tools.md` listing them. The chapter's
# registries are built by `chapter/registries.py` (the bootstrap), not here. User-facing docs: `tools/tools.md`.
#
# ⚠️ Output keys must stay self-descriptive (chronicler reads them with no other context). Prefer disambiguated names (e.g. `wild_creatures` over `creatures`).
# Exception: WB-native names verbatim for raw-save fields (e.g. `relations`, `world_time`) — chronicler reads save directly, divergent names would cause friction.

import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))

from shared import (
    SICK_TRAITS,
    city_score_ranks,
    civic_building_ids,
    emit,
    is_aboard,
    is_boat,
    kingdom_score_ranks,
    light,
    load_data,
    load_save,
    parse_sections,
    take_chapter,
    wants_detail,
)

_ALL_SECTIONS = ("boats", "cumulative", "leaders", "metadata", "plots", "snapshot")

# Chronicler key => WB `mapStats` counter — UI keys (`CUMULATIVE_STATS`) + churn a net snapshot hides; `_created` stored, `destroyed = created − snapshot.alive`.
_CUMULATIVE_COUNTERS = {
    "alliances_made": "alliancesMade",
    "armies_created": "armiesCreated",
    "books_burnt": "booksBurnt",
    "books_read": "booksRead",
    "buildings_built": "housesBuilt",  # WB `housesBuilt` counts all buildings, not dwellings (net ≈ `buildings`)
    "cities_conquered": "citiesConquered",
    "cities_created": "citiesCreated",
    "cities_rebelled": "citiesRebelled",
    "clans_created": "clansCreated",
    "creatures_born": "creaturesBorn",  # natural reproduction
    "creatures_created": "creaturesCreated",  # divine spawn + worldgen
    "cultures_created": "culturesCreated",
    "evolutions": "evolutions",
    "families_created": "familiesCreated",
    "kingdoms_created": "kingdomsCreated",
    "languages_created": "languagesCreated",
    "metamorphosis": "metamorphosis",
    "peaces_made": "peacesMade",
    "plots_started": "plotsStarted",
    "plots_succeeded": "plotsSucceeded",
    "religions_created": "religionsCreated",
    "subspecies_created": "subspeciesCreated",
    "wars_started": "warsStarted",
}

# Chronicler key => WB save field. Mirrors the 16 rows of WB's « Deaths » panel; `water` is hydrophobic damage (separate from `drowning`).
_DEATH_CAUSES = {
    "acid": "deaths_acid",
    "divine": "deaths_divine",
    "drowning": "deaths_drowning",
    "eaten": "deaths_eaten",
    "explosion": "deaths_explosion",
    "fire": "deaths_fire",
    "gravity": "deaths_gravity",
    "hunger": "deaths_hunger",
    "infection": "deaths_infection",
    "old_age": "deaths_age",
    "other": "deaths_other",
    "plague": "deaths_plague",
    "poison": "deaths_poison",
    "tumor": "deaths_tumor",
    "water": "deaths_water",
    "weapon": "deaths_weapon",
}

# Actor field => the save collection naming it. Each yields a `dominant_<field>` leader; the plurals are irregular enough (`subspecies`) to spell out.
_DOMINANT = {
    "culture": "cultures",
    "language": "languages",
    "religion": "religions",
    "subspecies": "subspecies",
}

# Chronicler key => save collection simply counted. What needs classifying (buildings) or filtering (actors, wars) lives in `_build_snapshot` instead.
_SNAPSHOT_COLLECTIONS = {
    "alliances": "alliances",
    "books": "books",
    "cities": "cities",
    "clans": "clans",
    "cultures": "cultures",
    "equipment": "items",
    "families": "families",
    "kingdoms": "kingdoms",
    "languages": "languages",
    "religions": "religions",
    "subspecies": "subspecies",
}


# The world's hulls, WB modelling them as actors: `total` is what the panel reads, the section names each one, `boat/info.py <id>` spelling one out.
def _build_boats(save: dict, requested: str | None) -> dict:
    afloat = [b for b in save.get("actors_data") or [] if is_boat(b)]
    if not wants_detail(requested, len(afloat)):  # `full` keeps the chapter light — one count, the hulls themselves only when the section is asked for by name
        return light({"total": len(afloat)})
    return {"afloat": [{"asset_id": b.get("asset_id"), "id": b["id"], "name": b.get("name")} for b in afloat], "total": len(afloat)}


# 0-count entries drop — the UI reads a missing key as 0, and `or 0` covers the counters WB stores as null. Keys stay as inserted: `render` sorts on the way out.
def _build_cumulative(map_stats: dict) -> dict:
    out: dict = {k: v for k, src in _CUMULATIVE_COUNTERS.items() if (v := int(map_stats.get(src) or 0)) > 0}
    out["deaths"] = {k: v for k, src in _DEATH_CAUSES.items() if (v := int(map_stats.get(src) or 0)) > 0}
    return out


# Top entity per category — WB's « Records ». Three readings the panel tables apart: a level, a headcount, and the composite score only a town and a crown take.
def _build_leaders(save: dict) -> dict:
    actors = save.get("actors_data") or []

    # Single pass over actors feeds every leader: the category counts, the highest-level civilian and the four rolls below — each gated apart, none re-scanned.
    counts: dict[str, Counter] = {k: Counter() for k in (*_DOMINANT, "species")}
    city_members: Counter[int] = Counter()
    clan_members: Counter[int] = Counter()
    family_members: Counter[int] = Counter()
    kingdom_members: Counter[int] = Counter()
    top_person, top_level = None, -1

    for a in actors:
        if is_boat(a):
            continue
        if a.get("civ_kingdom_id"):  # civilian: non-boat, kingdom-bound. `species` is the « thinking population », not wild creatures.
            counts["species"][a.get("asset_id")] += 1
            kingdom_members[a["civ_kingdom_id"]] += 1
            if (level := int(a.get("level") or 0)) > top_level:
                top_person, top_level = a, level
        if (cid := a.get("cityID")) is not None:  # a townsman need answer to no crown — counted apart from the kingdom roll above
            city_members[cid] += 1
        if cid := a.get("clan"):  # the sworn and the born are counted over every actor, as their registries do — a band outlives the crown it served
            clan_members[cid] += 1
        if fid := a.get("family"):
            family_members[fid] += 1
        for field in _DOMINANT:  # counted on every actor, wildlife included — a culture or a tongue outlives the crown that carried it
            if (v := a.get(field)) is not None:
                counts[field][v] += 1

    # The four dominant traits, emitted as `{id, name, value}` — the UI reads the rest (palette, banner, size, species) from the registries.
    out: dict[str, dict] = {}
    for field, coll in _DOMINANT.items():
        if not counts[field]:
            continue
        top_id, value = counts[field].most_common(1)[0]
        out[f"dominant_{field}"] = {"id": top_id, "name": _name_of(save.get(coll) or [], top_id), "value": value}

    if city_members:  # the most populous, where `most_dominant_village` weighs eleven dimensions — two readings of the same world, each with its own table
        top_cid, value = city_members.most_common(1)[0]
        out["largest_city"] = {"id": top_cid, "name": _name_of(save.get("cities") or [], top_cid), "value": value}

    if kingdom_members:
        top_kid, value = kingdom_members.most_common(1)[0]
        out["largest_kingdom"] = {"id": top_kid, "name": _name_of(save.get("kingdoms") or [], top_kid), "value": value}

    if scores := city_score_ranks(save):  # heaviest settlement by the composite score, not the most populous — size is only one dimension of it
        top_cid = min(scores, key=scores.__getitem__)
        out["most_dominant_village"] = {"id": top_cid, "name": _name_of(save.get("cities") or [], top_cid)}

    if scores := kingdom_score_ranks(save):  # strongest realm by the composite power score, `{id, name}` only — its score is meaningless to the chronicler
        top_kid = min(scores, key=scores.__getitem__)
        out["most_powerful_kingdom"] = {"id": top_kid, "name": _name_of(save.get("kingdoms") or [], top_kid)}

    if counts["species"]:  # `asset_id` alone: the icon key doubles as the key `SPECIES_NAMES` translates, as a biome's does.
        top_species, value = counts["species"].most_common(1)[0]
        out["dominant_species"] = {"asset_id": top_species, "value": value}

    if top_person is not None:  # Highest-level civilian, as the subject's own medal ranks them — `{id, name}` (+ level), visuals off the person registry.
        out["highest_level_person"] = {"id": top_person.get("id"), "name": top_person.get("name"), "value": top_level}

    if clan_members:  # the sworn, as the band's medal counts them — WB scores a clan's `renown` too, but no plate reads it
        top_cid, value = clan_members.most_common(1)[0]
        out["largest_clan"] = {"id": top_cid, "name": _name_of(save.get("clans") or [], top_cid), "value": value}

    if family_members:  # the living who carry the name, as the lineage's medal counts them
        top_fid, value = family_members.most_common(1)[0]
        out["largest_family"] = {"id": top_fid, "name": _name_of(save.get("families") or [], top_fid), "value": value}

    return out


# WB's own clock and its age of the world; `months_until_next_age` is derived here because the save states progress as a ratio, never as a countdown.
def _build_metadata(map_stats: dict) -> dict:
    age_duration = float(map_stats.get("current_world_ages_duration") or 0)
    age_id = map_stats.get("world_age_id") or ""
    age_progress = float(map_stats.get("current_age_progress") or 0)
    age = load_data("world-ages.json").get(age_id) or {}
    return {
        "age_description": age.get("description"),  # Chronicler-only: WB's English line on the age, one per chapter
        "age_id": age_id.removeprefix("age_"),  # `WorldAgeLibrary` key without WB's prefix — `hope`, as the panel keys its French and its icon
        "age_name": age.get("name"),  # Chronicler-only: WB's own English title, the id above being what the panel translates
        # Chronicler-only narrative hint, matches WB's UI counter « Lunes jusqu'au prochain âge ». Omitted when 0 / no current age.
        "months_until_next_age": int(age_duration * (1 - age_progress) / 5) if age_duration > 0 else 0,
        "world_time": round(float(map_stats.get("world_time", 0)), 2),
    }


# Every scheme afoot this instant, its schemer named — WB hangs a plot on one actor, so `actor/info.py <id> plot` spells out its target, its age and its progress.
def _build_plots(save: dict) -> list[dict]:
    holder_of = {a["plot"]: a for a in save.get("actors_data") or [] if a.get("plot") is not None}
    library = load_data("plots.json")
    return [
        {
            "actor": {"id": holder["id"], "name": holder.get("name")} if (holder := holder_of.get(plot["id"])) else None,
            "type": {"id": tid, "name": (library.get(tid) or {}).get("name")},
        }
        for plot in sorted(save.get("plots") or [], key=lambda p: p["id"])
        if (tid := plot.get("plot_type_id"))
    ]


# Actors split three ways: hulls (`boats`), kingdom-bound thinkers (`population`) and everything else (`wild_creatures`). `infected` = WB's `current_infected`.
def _build_snapshot(save: dict) -> dict:
    actors = save.get("actors_data") or []
    civic = civic_building_ids()
    asset_counts = Counter(b.get("asset_id") or "" for b in save.get("buildings") or [])  # Count `asset_id`s once, classify the distinct keys — four scans saved.
    categories = load_data("building-categories.json")  # WB's own grouping of what it files under `buildings`: what grows, what lies there, and what was built

    # `infected` ⊂ `sick` — a plague never shows up in the first, hence both; each drops at 0, outbreaks leaving them idle most chapters.
    boats = infected = passengers = population = sick = 0
    for a in actors:
        if is_boat(a):  # hulls are actors too, but neither thinking population nor wildlife — they get their own tally
            boats += 1
            continue
        passengers += is_aboard(a)
        population += a.get("civ_kingdom_id") is not None
        traits = a.get("saved_traits") or []
        if not SICK_TRAITS.isdisjoint(traits):  # the narrow test rides inside the wide one, as every other tier does it — one walk of the traits
            sick += 1
            infected += "infected" in traits

    return {
        **{k: len(save.get(coll) or []) for k, coll in _SNAPSHOT_COLLECTIONS.items()},
        "passengers": passengers,  # souls at sea this instant, WB's own word (`Boat.countPassengers`) — chronicler-only, `boats` counts the hulls
        "armies": len(save.get("armies") or []),
        "buildings": sum(n for aid, n in asset_counts.items() if aid in civic),  # Built structures worldwide (nature excluded); `houses` = dwellings.
        "frozen_tiles": len(save.get("frozen_tiles") or []),
        "houses": sum(n for aid, n in asset_counts.items() if aid.startswith("house")),
        **({"infected": infected} if infected else {}),
        "population": population,
        **({"sick": sick} if sick else {}),
        "trees": sum(n for aid, n in asset_counts.items() if categories.get(aid) == "trees"),
        "vegetation": sum(n for aid, n in asset_counts.items() if categories.get(aid) == "vegetation"),  # `trees` counts apart — WB files the two as it pleases
        "wars": sum(not w.get("winner") for w in save.get("wars") or []),  # Only those still being fought — WB sets `winner` the moment one ends.
        "wild_creatures": len(actors) - boats - population,
    }


# The one name a leader needs, found by a scan: reading a single row beats indexing a whole collection to serve one key, even on the longest of them.
def _name_of(records: list[dict], target_id) -> str | None:
    return next((r.get("name") for r in records if r.get("id") == target_id), None)


def main(argv: list[str]) -> int:
    save_path, argv, _ = take_chapter(argv)
    requested = argv[0] if argv else None
    try:
        sections = parse_sections(requested, _ALL_SECTIONS)
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 2
    save = load_save(save_path)
    map_stats = save.get("mapStats") or {}  # WB's own counters, period-accurate.
    out: dict = {}
    if "boats" in sections:
        out["boats"] = _build_boats(save, requested)
    if "cumulative" in sections:
        out["cumulative"] = _build_cumulative(map_stats)
    if "leaders" in sections:
        out["leaders"] = _build_leaders(save)
    if "metadata" in sections:
        out["metadata"] = _build_metadata(map_stats)
    if "plots" in sections:
        out["plots"] = _build_plots(save)
    if "snapshot" in sections:
        out["snapshot"] = _build_snapshot(save)
    emit(out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
