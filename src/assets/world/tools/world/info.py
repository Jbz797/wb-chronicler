#!/usr/bin/env python3

# Emits the world sections from the save alone (`mapStats` = WB's period-accurate counters); the chapter's registries are built by
# `chapter/registries.py` (the bootstrap), not here. User-facing docs — usage and sections — live in `tools/tools.md`.
#
# ⚠️ Output keys must stay self-descriptive (chronicler reads them with no other context). Prefer disambiguated names (e.g. `wild_creatures` over `creatures`).
# Exception: WB-native names kept verbatim for raw-save fields (e.g. `world_time`) — the tools' default, a rename having to earn its churn across py, UI and data.

import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))

from actor_stats import build_actor_stats_context, compute_actor_stats
from shared import (
    MIN_RANK_PEERS,
    MIN_SCORE_PEERS,
    SICK_TRAITS,
    city_score_dimensions,
    civic_building_ids,
    emit,
    first_place,
    index_by_id,
    is_aboard,
    is_boat,
    is_sapient,
    kingdom_score_dimensions,
    light,
    load_data,
    load_save,
    parse_sections,
    score_totals,
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

# Actor field => the save collection it points into, feeding its `population` record — every actor counted, wildlife included, as each tier's medal counts its own.
_GROUP_FIELDS = {
    "cityID": "cities",  # a townsman need answer to no crown — counted apart from the kingdom's roll
    "civ_kingdom_id": "kingdoms",  # the crown's own roll, which many a thinking soul is not on — a people can stand before any banner is raised
    "clan": "clans",  # a band outlives the crown it served
    "culture": "cultures",  # a culture or a tongue outlives the crown that carried it
    "family": "families",
    "language": "languages",
    "religion": "religions",
    "subspecies": "subspecies",
}

# The fewest rivals a record's field needs — `MIN_RANK_PEERS`, as a rank does, save for a town and a crown, which a world raises by the handful.
_MIN_PEERS = {"cities": MIN_SCORE_PEERS, "kingdoms": MIN_SCORE_PEERS}

# WB's four skills, the ones every `ranks_in_species` podium reads — civic abilities, weighed among thinking souls alone: a beast's figure moves nothing.
_SKILLS = ("diplomacy", "intelligence", "stewardship", "warfare")

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
    if not wants_detail(requested, len(afloat)):  # `full` shrinks a fleet past `wants_detail`'s floor to its count — a handful, or the section by name, lists each
        return light({"total": len(afloat)})
    return {"afloat": [{"asset_id": b.get("asset_id"), "id": b["id"], "name": b.get("name")} for b in afloat], "total": len(afloat)}


# 0-count entries drop — the UI reads a missing key as 0, and `or 0` covers the counters WB stores as null. Keys stay as inserted: `render` sorts on the way out.
def _build_cumulative(map_stats: dict) -> dict:
    out: dict = {k: v for k, src in _CUMULATIVE_COUNTERS.items() if (v := int(map_stats.get(src) or 0)) > 0}
    out["deaths"] = {k: v for k, src in _DEATH_CAUSES.items() if (v := int(map_stats.get(src) or 0)) > 0}
    return out


# The world's standouts, shaped as every tier's `leaders`: group, then measure, then its first place — `species` and `persons` weighing thinking souls alone.
def _build_leaders(save: dict) -> dict:
    actors = save.get("actors_data") or []
    ctx = build_actor_stats_context(save)
    members: dict[str, Counter] = {coll: Counter() for coll in _GROUP_FIELDS.values()}
    persons: dict[str, Counter] = {stat: Counter() for stat in (*_SKILLS, "level")}
    sapient = _sapient_subspecies(save)
    species: Counter[str] = Counter()

    # One pass over actors feeds every tally: the rolls first, then the thinking population's levels and skills — only the scores walk them again, in `shared`.
    for a in actors:
        if is_boat(a):
            continue
        for field, coll in _GROUP_FIELDS.items():
            if (v := a.get(field)) is not None:
                members[coll][v] += 1
        if a.get("subspecies") not in sapient:  # a mind, not an allegiance: the thinking population counts one owing no crown all the same
            continue
        species[a.get("asset_id")] += 1
        persons["level"][a["id"]] = int(a.get("level") or 0)
        stats = compute_actor_stats(a, ctx)
        for stat in _SKILLS:
            persons[stat][a["id"]] = stats.get(stat, 0)

    # `{id, name}` apiece, `value` on a tally, the UI reading the rest (palette, banner, size, species) off the registries — `new.py` keeping the first holder.
    out: dict[str, dict] = {
        coll: {"population": _count_leaders(tally, save.get(coll) or [], _MIN_PEERS.get(coll, MIN_RANK_PEERS))} for coll, tally in members.items()
    }
    out["persons"] = {stat: _count_leaders(tally, actors, MIN_RANK_PEERS) for stat, tally in persons.items()}
    out["species"] = {"population": [{"asset_id": asset, "value": n} for asset, n in first_place(species, MIN_RANK_PEERS)]}  # `asset_id`: its icon
    for coll, dimensions in (("cities", city_score_dimensions), ("kingdoms", kingdom_score_dimensions)):
        records = save.get(coll) or []
        out[coll]["score"] = _score_leaders(score_totals([r["id"] for r in records], dimensions(save)), records)
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
        # Chronicler-only narrative hint, matches WB's UI counter « Lunes jusqu'au prochain âge ». `0` where no age runs: WB then stores no span to count down.
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


# Actors split three ways: hulls (`boats`), thinking souls (`sapient_population`) and the beasts (`wild_creatures`). `infected` = WB's `current_infected`.
def _build_snapshot(save: dict) -> dict:
    actors = save.get("actors_data") or []
    civic = civic_building_ids()
    asset_counts = Counter(b.get("asset_id") or "" for b in save.get("buildings") or [])  # Count `asset_id`s once, classify the distinct keys — four scans saved.
    categories = load_data("building-categories.json")  # WB's own grouping of what it files under `buildings`: what grows, what lies there, and what was built

    # `infected` ⊂ `sick` — a plague never shows up in the first, hence both; each drops at 0, outbreaks leaving them idle most chapters.
    boats = infected = passengers = sapients = sick = 0
    sapient = _sapient_subspecies(save)
    for a in actors:
        if is_boat(a):  # hulls are actors too, but neither thinking population nor wildlife — they get their own tally
            boats += 1
            continue
        passengers += is_aboard(a)
        sapients += a.get("subspecies") in sapient
        traits = a.get("saved_traits") or []
        if not SICK_TRAITS.isdisjoint(traits):  # the narrow test rides inside the wide one, as every other tier does it — one walk of the traits
            sick += 1
            infected += "infected" in traits

    return {
        **{k: len(save.get(coll) or []) for k, coll in _SNAPSHOT_COLLECTIONS.items()},
        "armies": len(save.get("armies") or []),
        "buildings": sum(n for aid, n in asset_counts.items() if aid in civic),  # Built structures worldwide (nature excluded); `houses` = dwellings.
        "frozen_tiles": len(save.get("frozen_tiles") or []),
        "houses": sum(n for aid, n in asset_counts.items() if aid.startswith("house")),
        **({"infected": infected} if infected else {}),
        "passengers": passengers,  # souls at sea this instant, WB's own word (`Boat.countPassengers`) — chronicler-only, `boats` counts the hulls
        "sapient_population": sapients,  # named apart from every tier's `population`, which counts members: this one weighs minds, and no crown gathers them
        **({"sick": sick} if sick else {}),
        "trees": sum(n for aid, n in asset_counts.items() if categories.get(aid) == "trees"),
        "vegetation": sum(n for aid, n in asset_counts.items() if categories.get(aid) == "vegetation"),  # `trees` counts apart — WB files the two as it pleases
        "wars": sum(not w.get("winner") for w in save.get("wars") or []),  # Only those still being fought — WB sets `winner` the moment one ends.
        "wild_creatures": len(actors) - boats - sapients,
    }


def _count_leaders(counts: Counter, records: list[dict], min_peers: int) -> list[dict]:
    return [{"id": eid, "name": _name_of(records, eid), "value": n} for eid, n in first_place(counts, min_peers)]


# The one name a leader needs, found by a scan: reading a single row beats indexing a whole collection to serve one key, even on the longest of them.
def _name_of(records: list[dict], target_id) -> str | None:
    return next((r.get("name") for r in records if r.get("id") == target_id), None)


# The subspecies WB hangs `has_sapience` on, as a set of ids — an allegiance is not a mind, and a world can think long before it crowns anyone.
def _sapient_subspecies(save: dict) -> frozenset:
    return frozenset(sid for sid, sub in index_by_id(save.get("subspecies") or []).items() if is_sapient(sub))


# Whoever holds the composite's first place, `{id, name}` alone: a Borda total climbs with every rival, so the points never travel.
def _score_leaders(totals: Counter, records: list[dict]) -> list[dict]:
    field = {r["id"]: totals[r["id"]] for r in records}  # every town or crown a rival, the ones `score_totals` credits nothing included
    return [{"id": eid, "name": _name_of(records, eid)} for eid, _ in first_place(field, MIN_SCORE_PEERS)]


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
