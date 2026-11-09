#!/usr/bin/env python3

# Emits the world sections from the save alone (`mapStats` = WB's period-accurate counters); the chapter's registries are built by
# `chapter/registries.py` (the bootstrap), not here. User-facing docs — usage and sections — live in `docs/tools.md`.
#
# ⚠️ Output keys must stay self-descriptive (chronicler reads them with no other context). Prefer disambiguated names (e.g. `wild_creatures` over `creatures`).
# Exception: WB-native names kept verbatim for raw-save fields (e.g. `asset_id`) — the tools' default, a rename having to earn its churn across py, UI and data.

import sys
from collections import Counter
from pathlib import Path
lazy from collections.abc import Mapping

sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))

from actor_stats import (
    build_actor_stats_context,
    compute_actor_stats,
    equipment_power,
    kept_statuses,
)
from grid import frozen_tally
from shared import (
    MIN_RANK_PEERS,
    MIN_SCORE_PEERS,
    SAVES_DIR,
    SICK_TRAITS,
    SKILLS,
    actor_age,
    arg_parser,
    building_family,
    city_score_dimensions,
    civic_building_ids,
    counted_birth,
    emit,
    first_place,
    house_building_ids,
    i18n,
    is_aboard,
    is_boat,
    kept_clouds,
    kept_deaths,
    kingdom_score_dimensions,
    light,
    load_data,
    load_save,
    moved_between,
    parse_sections,
    passed_unseen,
    quiet_zeros,
    rounded_world_time,
    run,
    sapient_subspecies,
    score_totals,
    since_saves,
    take_chapter,
    take_since,
    under_construction,
    unranked,
    wants_detail,
    world_date,
    world_laws,
)

_AGE_WANING = 5 / 6  # the share of its span past which an age is `waning`: its last sixth, six to nine years of a long one
_AGE_YOUNG = 1 / 4  # and under which it is `young`: its first quarter
_ALL_SECTIONS = ("boats", "cumulative", "leaders", "metadata", "plots", "snapshot")

# Chronicler key, `history world`'s column name where it has one => WB `mapStats` counter — beginnings and ends both, the churn a net snapshot hides.
_CUMULATIVE_COUNTERS = {
    "alliances_dissolved": "alliancesDissolved",
    "alliances_made": "alliancesMade",
    "armies_created": "armiesCreated",
    "armies_destroyed": "armiesDestroyed",
    "books_burnt": "booksBurnt",
    "books_read": "booksRead",
    "books_written": "booksWritten",
    "buildings_built": "housesBuilt",  # WB's two `houses…` counters take every building, not dwellings alone — their net ≈ `buildings`
    "buildings_destroyed": "housesDestroyed",
    "cities_conquered": "citiesConquered",
    "cities_created": "citiesCreated",
    "cities_destroyed": "citiesDestroyed",
    "cities_rebelled": "citiesRebelled",
    "clans_created": "clansCreated",
    "clans_destroyed": "clansDestroyed",
    "creatures_born": "creaturesBorn",  # natural reproduction
    "creatures_created": "creaturesCreated",  # WB `Actor.newCreature`: whatever appears unborn — set down, migrant, summoned, changed kind, a hull
    "cultures_created": "culturesCreated",
    "cultures_forgotten": "culturesForgotten",
    "evolutions": "evolutions",
    "families_created": "familiesCreated",
    "families_destroyed": "familiesDestroyed",
    "kingdoms_created": "kingdomsCreated",
    "kingdoms_destroyed": "kingdomsDestroyed",
    "languages_created": "languagesCreated",
    "languages_forgotten": "languagesForgotten",
    "peaces_made": "peacesMade",
    "plots_forgotten": "plotsForgotten",
    "plots_started": "plotsStarted",
    "plots_succeeded": "plotsSucceeded",
    "religions_created": "religionsCreated",
    "religions_forgotten": "religionsForgotten",
    "subspecies_created": "subspeciesCreated",
    "subspecies_extinct": "subspeciesExtinct",
    "wars_started": "warsStarted",
}

_FEATS = ("kills", "level", "money", "renown")  # what a life adds up, kept on the body itself — weighed among thinking souls as the skills are

# Actor field => the save collection it points into, feeding its `pop` record — every actor counted, wildlife included, as each tier's medal counts its own.
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

_MIN_PEERS = {"cities": MIN_SCORE_PEERS, "kingdoms": MIN_SCORE_PEERS}
_ON_REQUEST = ("laws",)  # named only: `full` is what the bootstrap folds into a chapter
_SINCE_SECTIONS = ("cumulative", "snapshot")  # what `--since` weighs: two counts, the difference between them

# Chronicler key => save collection simply counted. What needs classifying (buildings) or filtering (actors, wars) lives in `_build_snapshot` instead.
_SNAPSHOT_COLLECTIONS = {
    "alliances": "alliances",
    "books": "books",
    "cities": "cities",
    "clans": "clans",
    "cultures": "cultures",
    "families": "families",
    "gear": "items",
    "kingdoms": "kingdoms",
    "languages": "languages",
    "religions": "religions",
    "subspecies": "subspecies",
}


# An age's life stage off the share of its span it has run — three words and no date, the end of an age being the turn a chronicle must not see coming.
def _age_stage(progress: float) -> str:
    return "young" if progress < _AGE_YOUNG else "waning" if progress >= _AGE_WANING else "mature"


# The world's hulls, WB modelling them as actors: `total` is what the panel reads, the section names each one, `boat/info.py <id>` spelling one out.
def _build_boats(save: dict, requested: str | None) -> dict:
    afloat = [b for b in save.get("actors_data") or [] if is_boat(b)]
    if not wants_detail(requested, len(afloat)):  # `full` shrinks a fleet past `wants_detail`'s floor to its count — a handful, or the section by name, lists each
        return light({"total": len(afloat)})
    return {"afloat": [{"asset_id": b.get("asset_id"), "id": b["id"], "name": b.get("name")} for b in afloat], "total": len(afloat)}


# The counters past nought, a missing key read as 0 — and the deaths by cause off the register, every one named; a metamorphosis is its own tally, no death.
def _build_cumulative(save: dict) -> dict:
    map_stats = save.get("mapStats") or {}
    out: dict = {k: v for k, src in _CUMULATIVE_COUNTERS.items() if (v := int(map_stats.get(src) or 0)) > 0}
    causes = Counter(dead["cause"] for dead in kept_deaths(save).values())
    if changed := causes.pop("metamorphosis", 0):  # a crab reborn as WB never counts it, whose tally sees a bite's alone
        out["metamorphosis"] = changed
    if migrated := sum(int(k.get("migrated") or 0) for k in save.get("kingdoms") or []):  # `Kingdom.increaseMigrants`: a realm gone takes its count along
        out["migrated"] = migrated
    return out | {"deaths": dict(causes)}


# The laws by WB's own English title, the label a wiki row goes by, split by state — the age switches of the same list left out: the next age stays a surprise.
def _build_laws(save: dict) -> dict:
    names = load_data("world-laws.json")
    laws = {names.get(law, law): on for law, on in world_laws(save).items() if law.startswith("world_law_")}
    return {"off": sorted(name for name, on in laws.items() if not on), "on": sorted(name for name, on in laws.items() if on)}


# The world's standouts, shaped as every tier's `leaders`: group, then measure, then its first place — `persons` weighing thinking souls alone, `unranked` the thin.
def _build_leaders(save: dict) -> dict:
    actors = save.get("actors_data") or []
    ctx = build_actor_stats_context(save)
    members: dict[str, Counter] = {coll: Counter() for coll in _GROUP_FIELDS.values()}
    # One figure per soul, never summed: a `Counter` would type it an int, where a birth is a fraction of a year.
    persons: dict[str, dict[int, float]] = {stat: {} for stat in ("equipment_power", "oldest", *_FEATS, *SKILLS)}
    sapient = sapient_subspecies(save)
    species: Counter[str] = Counter()

    # One pass over actors feeds every tally: the rolls and the species first, then the thinking souls' feats, gear and skills — only the scores walk them again.
    for a in actors:
        if is_boat(a):
            continue
        for field, coll in _GROUP_FIELDS.items():
            if (v := a.get(field)) is not None:
                members[coll][v] += 1
        species[a.get("asset_id")] += 1  # every body, beasts included, as the rolls above count them
        if a.get("subspecies") not in sapient:  # a mind, not an allegiance: the thinking population counts one owing no crown all the same
            continue
        aid, stats = a["id"], compute_actor_stats(a, ctx)
        persons["equipment_power"][aid] = equipment_power(a, ctx)
        persons["oldest"][aid] = -counted_birth(a)  # ranked on the birth, the finer clock: told in the years a fiche would give
        for stat in _FEATS:
            persons[stat][aid] = int(a.get(stat) or 0)
        for stat in SKILLS:
            persons[stat][aid] = stats.get(stat, 0)

    # `{id, name}` apiece, `value` on a tally, the UI reading the rest (palette, banner, size, species) off the registries — `new.py` keeping the first holder.
    out: dict[str, dict] = {coll: {"pop": _count_leaders(tally, save.get(coll) or [], _MIN_PEERS.get(coll, MIN_RANK_PEERS))} for coll, tally in members.items()}
    out["persons"] = {stat: _count_leaders(tally, actors, MIN_RANK_PEERS) for stat, tally in persons.items()}
    for ref in out["persons"]["oldest"]:
        ref["value"] = actor_age(next(a for a in actors if a["id"] == ref["id"]), ctx["world_time"])
    out["species"] = {"pop": [{"asset_id": asset, "value": n} for asset, n in first_place(species, MIN_RANK_PEERS)]}  # `asset_id`: its icon
    for coll, dimensions in (("cities", city_score_dimensions), ("kingdoms", kingdom_score_dimensions)):
        records = save.get(coll) or []
        out[coll]["score"] = _score_leaders(score_totals([r["id"] for r in records], dimensions(save)), records)
    pools = {coll: (len(tally), _MIN_PEERS.get(coll, MIN_RANK_PEERS)) for coll, tally in members.items()}
    if short := unranked({**pools, "persons": (len(persons["level"]), MIN_RANK_PEERS), "species": (len(species), MIN_RANK_PEERS)}):
        out["unranked"] = short
    return out


# The world's day and its age — when it began and how far it has run, never when it ends: WB's UI counts the moons left, a chronicle told it would foretell it.
def _build_metadata(map_stats: dict) -> dict:
    age_id = map_stats.get("world_age_id") or ""
    age = load_data("world-ages.json").get(age_id) or {}
    key = age_id.removeprefix("age_")  # `WorldAgeLibrary` key without WB's prefix — `hope`, as the panel keys its French and its icon
    world_time = rounded_world_time(map_stats)
    span, run = float(map_stats.get("current_world_ages_duration") or 0), float(map_stats.get("current_age_progress") or 0)  # no span where no age runs
    return {
        "age_description": age.get("description"),  # Chronicler-only: WB's English line on the age, one per chapter
        "age_id": key,
        # Chronicler-only: the age as the chronicle names it, said here so nobody opens `i18n/<lang>/ages.json`, where every age to come is listed. Else WB's title.
        "age_name": i18n("ages.json").get(key) or age.get("name"),
        # Chronicler-only: the month the age began, off the share run — WB's `world_age_started_at` is stamped anew at each load, the share kept
        "age_since": world_date(max(0.0, world_time - run * span)) if span > 0 else None,
        "age_stage": _age_stage(run) if span > 0 else None,  # Chronicler-only: an age's own life stage, off the share of its span the save says it has run
        "date": world_date(world_time),  # Chronicler-only: the day as every other date is written — the raw clock stays the scripts', read off the save
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


# Actors split three ways: hulls (`boats`), thinking souls (`sapient_pop`) and the beasts (`wild_creatures`). `infected` = WB's `current_infected`.
def _build_snapshot(save: dict) -> dict:
    actors = save.get("actors_data") or []
    civic, roofs = civic_building_ids(), house_building_ids()
    asset_counts = Counter(b.get("asset_id") or "" for b in save.get("buildings") or [])  # Count `asset_id`s once, classify the distinct keys — four scans saved.

    # `infected` ⊂ `sick` — a plague never shows up in the first, hence both; each drops at 0, outbreaks leaving them idle most chapters.
    boats = infected = passengers = sapients = sick = 0
    sapient, statuses = sapient_subspecies(save), Counter()
    for a in actors:
        if is_boat(a):  # hulls are actors too, but neither thinking population nor wildlife — they get their own tally
            boats += 1
            continue
        statuses.update(kept_statuses(a) or ())
        passengers += is_aboard(a)
        sapients += a.get("subspecies") in sapient
        traits = a.get("saved_traits") or []
        if not SICK_TRAITS.isdisjoint(traits):  # the narrow test rides inside the wide one, as every other tier does it — one walk of the traits
            sick += 1
            infected += "infected" in traits

    frozen, tiles = frozen_tally(save)
    return quiet_zeros(
        {
            **{k: len(save.get(coll) or []) for k, coll in _SNAPSHOT_COLLECTIONS.items()},
            "armies": len(save.get("armies") or []),
            "buildings": sum(n for aid, n in asset_counts.items() if aid in civic),  # Built structures worldwide (nature excluded)
            "clouds": dict(sorted(Counter(cloud["asset_id"] for cloud in kept_clouds(save)).items())) or None,  # Chronicler-only: each one, `geography … clouds`
            "frozen_pct": round(frozen / (tiles or 1) * 100),  # the map's frozen share, whole — permafrost, snow, ice and frost; `geography … totals` has the tenth
            "houses": sum(n for aid, n in asset_counts.items() if aid in roofs),  # as WB counts a town's (`City.getHouseCurrent`): tents and sites in
            "infected": infected,
            "passengers": passengers,  # souls at sea this instant, WB's own word (`Boat.countPassengers`) — chronicler-only, `boats` counts the hulls
            "sapient_pop": sapients,  # named apart from every tier's `pop`, which counts members: this one weighs minds, and no crown gathers them
            "sick": sick,
            # Chronicler-only: how many bodies each status holds this instant, as the Faithful Saves mod kept them.
            "statuses": dict(sorted(statuses.items())) or None,
            "trees": sum(n for aid, n in asset_counts.items() if building_family(aid) == "trees"),
            "under_construction": sum(under_construction(b) for b in save.get("buildings") or [] if b.get("asset_id") in civic),  # the sites among `buildings`
            "vegetation": sum(n for aid, n in asset_counts.items() if building_family(aid) == "vegetation"),  # `trees` counts apart — WB files the two as it pleases
            "wars": sum(not w.get("winner") for w in save.get("wars") or []),  # Only those still being fought — WB sets `winner` the moment one ends.
            "wild_creatures": len(actors) - boats - sapients,
        }
    )


def _count_leaders(counts: Mapping, records: list[dict], min_peers: int) -> list[dict]:
    return [{"id": eid, "name": _name_of(records, eid), "value": n} for eid, n in first_place(counts, min_peers)]


# The one name a leader needs, found by a scan: reading a single row beats indexing a whole collection to serve one key, even on the longest of them.
def _name_of(records: list[dict], target_id: int | None) -> str | None:
    return next((r.get("name") for r in records if r.get("id") == target_id), None)


# Whoever holds the composite's first place, `{id, name}` alone: a Borda total climbs with every rival, so the points never travel.
def _score_leaders(totals: Counter, records: list[dict]) -> list[dict]:
    field = {r["id"]: totals[r["id"]] for r in records}  # every town or crown a rival, the ones `score_totals` credits nothing included
    return [{"id": eid, "name": _name_of(records, eid)} for eid, _ in first_place(field, MIN_SCORE_PEERS)]


def main(argv: list[str]) -> int:
    try:
        since, argv = take_since(argv)
    except ValueError as e:
        print(f"✗ {e}", file=sys.stderr)
        return 2
    save_path, argv, chapter = take_chapter(argv)
    parser = arg_parser(prog="world/info.py", taken="[--since C<n>] [C<n>]")
    parser.add_argument("sections", nargs="?")
    args = parser.parse_args(argv)
    requested = args.sections
    try:
        sections = parse_sections(requested, (*_ALL_SECTIONS, *_ON_REQUEST), full=_ALL_SECTIONS)
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 2
    # `--since` weighs two counts: any other section would say a chapter's state as if it were a change
    if since and (unweighed := [section for section in sections if section not in _SINCE_SECTIONS]):
        print(f"✗ {', '.join(unweighed)}: `--since` takes {', '.join(_SINCE_SECTIONS)} alone — name them", file=sys.stderr)
        return 2
    if since and not (SAVES_DIR / since / "map.wbox").exists():
        print(f"✗ no save for {since}", file=sys.stderr)
        return 2
    save = load_save(save_path)
    out: dict = {}
    if "boats" in sections:
        out["boats"] = _build_boats(save, requested)
    if "cumulative" in sections:
        out["cumulative"] = _build_cumulative(save)
    if "laws" in sections:
        out["laws"] = _build_laws(save)
    if "leaders" in sections:
        out["leaders"] = _build_leaders(save)
    if "metadata" in sections:
        out["metadata"] = _build_metadata(save.get("mapStats") or {})  # WB's own counters, period-accurate
    if "plots" in sections:
        out["plots"] = _build_plots(save)
    if "snapshot" in sections:
        out["snapshot"] = _build_snapshot(save)
    readings = {"cumulative": _build_cumulative, "snapshot": _build_snapshot}  # each read again off the save before
    if since and (counted := [section for section in readings if section in out]):
        then = load_save(SAVES_DIR / since / "map.wbox")
        # A count by count difference, `[then, now]` and 0 where a counter was not: a section that holds still drops out, and none moving says so
        for section in counted:
            if isinstance(moved := moved_between(readings[section](then), out.pop(section)), dict):
                out[section] = moved
        if "cumulative" in out:
            out["cumulative"]["came_and_went"] = passed_unseen(then, since_saves(since, chapter, save)) or None
        if not out:
            print(f"✗ nothing moved in {', '.join(counted)} since {since}", file=sys.stderr)
            return 1

    emit(out)
    return 0


if __name__ == "__main__":
    sys.exit(run(main))
