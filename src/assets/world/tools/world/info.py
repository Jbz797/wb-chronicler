#!/usr/bin/env python3

# Emits the world sections (`cumulative`/`leaders`/`metadata`/`snapshot`) from the save alone (`mapStats` = WB's period-accurate counters). The chapter's
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
    is_boat,
    kingdom_score_ranks,
    load_data,
    load_save,
    parse_sections,
    take_chapter,
)

_ALL_SECTIONS = ("cumulative", "leaders", "metadata", "snapshot")

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

_SPECIES = load_data("species.json")  # asset_id → {stats, name, description}. Here for the French `name`; falls back to the asset_id when absent.

_UNVEGETATED = {
    "geyser",
    "super_pumpkin",
    "volcano",
}  # Neither civ nor vegetation (`poop` = WB vegetation; `mineral_*` by prefix).


# 0-count entries (counters + per-cause deaths) are dropped — UI treats missing keys as 0. `or 0` also covers the few counters WB stores as null.
def _build_cumulative(map_stats: dict) -> dict:
    out: dict = {k: v for k, src in _CUMULATIVE_COUNTERS.items() if (v := int(map_stats.get(src) or 0)) > 0}
    out["deaths"] = dict(sorted((k, v) for k, src in _DEATH_CAUSES.items() if (v := int(map_stats.get(src) or 0)) > 0))
    return dict(sorted(out.items()))


# Top entity per category (dominant village and realm by their composite scores, dominant culture/language/religion/subspecies, top renown) — WB's « Records ».
def _build_leaders(save: dict) -> dict:
    actors = save.get("actors_data") or []

    # Single pass over actors feeds every leader: category counts, top-renown civilian, and family renown sums (all gated the same way, no need to re-scan).
    counts: dict[str, Counter] = {k: Counter() for k in (*_DOMINANT, "species")}
    family_renown: Counter[int] = Counter()
    top_person, top_renown = None, -1

    for a in actors:
        if is_boat(a):
            continue
        if a.get("civ_kingdom_id"):  # civilian: non-boat, kingdom-bound. `species` is the « thinking population », not wild creatures.
            renown = int(a.get("renown") or 0)
            counts["species"][a.get("asset_id")] += 1
            if renown > top_renown:
                top_person, top_renown = a, renown
            if fid := a.get("family"):
                family_renown[fid] += renown
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

    if scores := city_score_ranks(save):  # heaviest settlement by the composite score, not the most populous — size is only one of its ten dimensions
        top_cid = min(scores, key=lambda cid: scores[cid])
        out["most_dominant_village"] = {"id": top_cid, "name": _name_of(save.get("cities") or [], top_cid)}

    if scores := kingdom_score_ranks(save):  # strongest realm by the composite power score, `{id, name}` only — its score is meaningless to the chronicler
        top_kid = min(scores, key=lambda kid: scores[kid])
        out["most_powerful_kingdom"] = {"id": top_kid, "name": _name_of(save.get("kingdoms") or [], top_kid)}

    if counts["species"]:  # `asset_id` is the UI icon key; `name` is its French label (falls back to the asset_id).
        top_species, value = counts["species"].most_common(1)[0]
        out["dominant_species"] = {"asset_id": top_species, "name": (_SPECIES.get(top_species) or {}).get("name") or top_species, "value": value}

    if top_person is not None:  # Top-renown civilian — emitted as `{id, name}` (+ renown); the UI's `<app-person-tag>` reads its visuals from the person registry.
        out["most_renowned_person"] = {"id": top_person.get("id"), "name": top_person.get("name"), "value": top_renown}

    clans = save.get("clans") or []
    if clans:
        top_clan = max(clans, key=lambda c: int(c.get("renown") or 0))
        out["most_renowned_clan"] = {"id": top_clan.get("id"), "name": top_clan.get("name"), "value": int(top_clan.get("renown") or 0)}

    if family_renown:  # Families carry no native renown (unlike clans) — rank by their members' summed renown, tallied in the pass above.
        top_fid, value = family_renown.most_common(1)[0]
        out["most_renowned_family"] = {"id": top_fid, "name": _name_of(save.get("families") or [], top_fid), "value": value}

    return dict(sorted(out.items()))


# WB's own clock and its age of the world; `months_until_next_age` is derived here because the save states progress as a ratio, never as a countdown.
def _build_metadata(map_stats: dict) -> dict:
    age_duration = float(map_stats.get("current_world_ages_duration") or 0)
    age_progress = float(map_stats.get("current_age_progress") or 0)
    return {
        "age_id": map_stats.get("world_age_id") or "",  # WorldAgeLibrary key (e.g. `age_hope`)
        # Chronicler-only narrative hint, matches WB's UI counter « Lunes jusqu'au prochain âge ». Omitted when 0 / no current age.
        "months_until_next_age": int(age_duration * (1 - age_progress) / 5) if age_duration > 0 else 0,
        "world_time": round(float(map_stats.get("world_time", 0)), 2),
    }


# Actors split three ways: hulls (`boats`), kingdom-bound thinkers (`population`) and everything else (`wild_creatures`). `infected` = WB's `current_infected`.
def _build_snapshot(save: dict) -> dict:
    actors = save.get("actors_data") or []
    civic = civic_building_ids()
    asset_counts = Counter(b.get("asset_id") or "" for b in save.get("buildings") or [])  # Count `asset_id`s once, classify the distinct keys — four scans saved.

    # Both omitted when 0 (outbreak-style, idle most chapters). `infected` ⊂ `sick`: a plague never shows up in `infected`, hence the two counters.
    boats = infected = population = sick = 0
    for a in actors:
        if is_boat(a):  # hulls are actors too, but neither thinking population nor wildlife — they get their own tally
            boats += 1
            continue
        traits = a.get("saved_traits") or []
        infected += "infected" in traits
        population += a.get("civ_kingdom_id") is not None
        sick += not SICK_TRAITS.isdisjoint(traits)

    return dict(
        sorted(
            {
                **{k: len(save.get(coll) or []) for k, coll in _SNAPSHOT_COLLECTIONS.items()},
                "armies": len(save.get("armies") or []),
                "boats": boats,
                "buildings": sum(n for aid, n in asset_counts.items() if aid in civic),  # Built structures worldwide (nature excluded); `houses` = dwellings.
                "frozen_tiles": len(save.get("frozen_tiles") or []),
                "houses": sum(n for aid, n in asset_counts.items() if aid.startswith("house")),
                **({"infected": infected} if infected else {}),
                "plots_active": len(save.get("plots") or []),
                "population": population,
                **({"sick": sick} if sick else {}),
                "trees": sum(n for aid, n in asset_counts.items() if "tree" in aid),  # Catches every `Building_Tree` variant — ≤1% off WB's unstable counter.
                "vegetation": sum(
                    n for aid, n in asset_counts.items() if aid not in civic and aid not in _UNVEGETATED and not aid.startswith(("fishing_docks", "mineral"))
                ),
                "wars": sum(not w.get("winner") for w in save.get("wars") or []),  # Only those still being fought — WB sets `winner` the moment one ends.
                "wild_creatures": len(actors) - boats - population,
            }.items()
        )
    )


# The one name a leader needs, found by a scan: six of them each read a single row, where six `index_by_id` would allocate six dicts to serve six keys.
def _name_of(records: list[dict], target_id) -> str | None:
    return next((r.get("name") for r in records if r.get("id") == target_id), None)


def main(argv: list[str]) -> int:
    save_path, argv, _ = take_chapter(argv)
    try:
        sections = parse_sections(argv[0] if argv else None, _ALL_SECTIONS)
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 2
    save = load_save(save_path)
    map_stats = save.get("mapStats") or {}  # WB's own counters, period-accurate.
    out: dict = {}
    if "cumulative" in sections:
        out["cumulative"] = _build_cumulative(map_stats)
    if "leaders" in sections:
        out["leaders"] = _build_leaders(save)
    if "metadata" in sections:
        out["metadata"] = _build_metadata(map_stats)
    if "snapshot" in sections:
        out["snapshot"] = _build_snapshot(save)
    emit(out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
