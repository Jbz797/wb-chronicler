#!/usr/bin/env python3

# Emits the world sections from the save alone (`mapStats` = WB's period-accurate counters); the chapter's registries are built by
# `chapter/registries.py` (the bootstrap), not here. User-facing docs — usage and sections — live in `docs/tools.md`.
#
# ⚠️ Output keys must stay self-descriptive (chronicler reads them with no other context). Prefer disambiguated names (e.g. `wild_creatures` over `creatures`).
# Exception: WB-native names kept verbatim for raw-save fields (e.g. `asset_id`) — the tools' default, a rename having to earn its churn across py, UI and data.

import contextlib
import difflib
import re
import sys
from collections import Counter, defaultdict
from functools import cache, partial
from math import inf
from operator import itemgetter
from pathlib import Path
lazy import argparse
lazy from collections.abc import Callable, Mapping, Sequence

sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))

from actor_stats import (
    adult_age,
    body_lifespan,
    body_stats,
    breeding_age,
    build_actor_stats_context,
    compute_actor_stats,
    crossed_at,
    crossed_on,
    equipment_power,
    hatch_on,
    is_egg,
    is_hungry,
    kept_statuses,
    kept_task,
    maturation_months,
    status_left,
)
from founding import city_zones, settle_gates, settle_told
from grid import LazyTileGrid, frozen_tally, off_land, patch_finder
from islands import TileIslands, compute_islands_cached, islet_heart
from places import PlaceIndex
from shared import (
    JOBS,
    MAX_LISTED,
    MIN_RANK_PEERS,
    MIN_SCORE_PEERS,
    NEW_BABY_NUTRITION,
    SAVES_DIR,
    SICK_TRAITS,
    UNITS_PER_MONTH,
    UNITS_PER_YEAR,
    absent_entity,
    actor_age,
    actor_xy,
    alive_or_dead_ref,
    arg_parser,
    asset_families,
    asset_kinds,
    bearing,
    biome_lore,
    body_ref,
    breeding_mode,
    building_family,
    built_by_tile,
    children_by_id,
    city_score_dimensions,
    civic_building_ids,
    counted_birth,
    crafted_counts,
    emit,
    entity_born,
    entity_ref,
    fertile,
    first_place,
    house_building_ids,
    i18n,
    index_by_id,
    indoors,
    is_aboard,
    is_boat,
    is_sapient,
    kept_army_since,
    kept_city_since,
    kept_clouds,
    kept_deaths,
    kingdom_score_dimensions,
    latest_chapter,
    life_stage,
    light,
    limit_arg,
    load_data,
    load_save,
    log_entries,
    moved_between,
    needs_food,
    parse_sections,
    passed_unseen,
    quiet_zeros,
    resolve_profession,
    rounded_world_time,
    run,
    score_totals,
    sex_label,
    spores_unfed,
    take_chapter,
    take_since,
    tile_text,
    under_construction,
    unranked,
    unsited_reason,
    walk_tiles,
    wants_detail,
    whereabouts,
    world_date,
    world_laws,
    xy_arg,
)
from walking import WalkMap, walk_way

_AGE_WANING = 5 / 6  # the share of its span past which an age is `waning`: its last sixth, six to nine years of a long one
_AGE_YOUNG = 1 / 4  # and under which it is `young`: its first quarter
_ALL_SECTIONS = ("boats", "cumulative", "leaders", "metadata", "plots", "snapshot")

_CARRYING = ("pregnant", "pregnant_parthenogenesis")  # WB's two statuses that end on a birth

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

_DEAD_SOCLE = ("asset_id", "name", "sex")  # a dead body's line beside what befell it: its name, then its kind, what `--with` drives off — its sex stays
_DEATH_CAUSES = tuple(sorted(set(load_data("attack-types.json").values())))  # what `died:` takes: each cause as the register files it
_DISPLACED = ("city", "island_id", "life_stage", "name", "asset_id")  # what `--with` drives off the socle, one per field asked, least telling first
_FEATS = ("kills", "level", "money", "renown")  # what a life adds up, kept on the body itself — weighed among thinking souls as the skills are
_FIELD_FLOORS = {"births": 0, "equipment_power": 0, "level": 1, "loot": 0, "money": 0, "renown": 0}  # a tally `actor … stats` tells silent at its floor
_GONE_FIELDS = ("asset_id", "at", "born", "killed_by", "name", "parents", "sex")  # what `--with` asks of the dead, the register keeping it, or a sex never changing
_GOOD_ISLET = 5  # WB `TileIsland.isGoodIslandForActor`: an islet of so few tiles is one a body leaves before anything else, breeding included

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

_ISLET = "islet"  # where `roster` says a body stands, or stood, on an islet too small to count — `_WATER` where it floats

# What `--with` reads off the body and its ground, a line's own fields among them, its tile as `metadata` gives it, and its lineage by id: `lineages` names it
_KEPT_FIELDS = (
    "adult_on",
    "age",
    "age_overgrowth",
    "army_since",
    "asset_id",
    "at",
    "beside_building",
    "born",
    "breeds_on",
    "city",
    "city_since",
    "clan",
    "crafted",
    "culture",
    "family",
    "gen",
    "hatch_on",
    "home",
    "in_building",
    "island_id",
    "islet",
    "job",
    "kills",
    "kingdom",
    "language",
    "life_stage",
    "lover",
    "name",
    "parents",
    "place",
    "religion",
    "sex",
    "statuses",
    "subspecies",
    "task",
)

_KEYED = ("born", "died", "has", "lacks", "patch", "status", "task", "trait", "type")  # what `--filter` takes as `key:value` besides each entity's id: an open value
_LIFE_STAGES = ("egg", "baby", "child", "teen", "adult", "elder")  # `shared.life_stage`'s, in the order a body passes them — `--filter`'s stage words
_LIMIT = 10  # the lines a roll gives unless `--limit` says otherwise: its head, the cut told beside
_MAX_FIELDS = 4  # past so many fields a line reads as a sheet: `actor … stats` gives the whole of one body

# What `roster` narrows to by entity: the collection its id answers in, and the body's own field that ties it there — a pact's, through the crown.
_MEMBERSHIPS = {
    "alliance": ("alliances", None),
    "army": ("armies", "army"),  # a town's one force, its id given by `city … army`
    "city": ("cities", "cityID"),
    "clan": ("clans", "clan"),
    "culture": ("cultures", "culture"),
    "family": ("families", "family"),
    "kingdom": ("kingdoms", "civ_kingdom_id"),
    "language": ("languages", "language"),
    "religion": ("religions", "religion"),
    "subspecies": ("subspecies", "subspecies"),
}

# The fewest rivals a record's field needs — `MIN_RANK_PEERS`, as a rank does, save for a town and a crown, which a world raises by the handful.
_MIN_PEERS = {"cities": MIN_SCORE_PEERS, "kingdoms": MIN_SCORE_PEERS}

_ONE_BODY = re.compile(r"(?:p|id:)?(\d+)")  # a body by its id, as `--rank` takes one: `--filter` narrows a roll, one body is `actor`'s
_ON_REQUEST = ("laws", "lineages", "pairings", "roster")  # named only: `full` is what the bootstrap folds into a chapter, and a roll is no chapter's to carry
_RANKED_KEPT = ("age_overgrowth", "gen")  # the figures among a body's kept fields `--rank` reads, every other a word or an id
_SEXED = "reproduction_sexual"  # the one breeding WB pairs by opposite sexes: a hermaphrodite takes any partner of its kind
_SINCE_PARTS = ("arrived", "died", "grew", "left", "moved")  # what a `--since` roll files a body under, `left` an entity's alone
_SINCE_SECTIONS = ("cumulative", "lineages", "roster", "snapshot")  # what `--since` answers: the arrivals of a roll or a census, two counts weighed

# WB's four skills, the ones every `actor … ranks` podium reads — civic abilities, weighed among thinking souls alone: a beast's figure moves nothing.
_SKILLS = ("diplomacy", "intelligence", "stewardship", "warfare")

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

_SOULBORNE = "reproduction_soulborne"  # a lineage born of the souls it strikes: `action_attack_target` harvests one off a body that `has_soul`
_STRATEGIC = frozenset({"reproduction_hermaphroditic", "reproduction_parthenogenesis", "reproduction_sexual"})  # carried only if viviparous, else laid at once
_TALLIES = ("births", "kills", "level", "loot", "money", "renown")  # what `has:` and `lacks:` weigh: a body's own counters, named as `actor … stats` names them
_TIES = ("city", "clan", "culture", "family", "kingdom", "language", "religion")  # what `--with` names a body's ties by, `{id, name}` as `actor … metadata` does
_TOP_MEASURES = tuple(sorted((*_SKILLS, *_TALLIES, "age", "crafted", "equipment_power")))  # what `--rank` ranks by: a counter, a skill, an arsenal, age, work
_UNCARRIED = frozenset({"reproduction_fission", "reproduction_spores"})  # WB makes the new body there and then, `maturation` never read
_WATER = "water"  # where `roster` says a body stands, or stood, afloat — off every land, as `_ISLET` is, but in the sea or a lake


# An age's life stage off the share of its span it has run — three words and no date, the end of an age being the turn a chronicle must not see coming.
def _age_stage(progress: float) -> str:
    return "young" if progress < _AGE_YOUNG else "waning" if progress >= _AGE_WANING else "mature"


# What `--with` asks of a body standing `here`: its `actor … stats`, a silent tally at its floor, kind, land, stage, task, statuses — its stats named into `seen`.
def _asked_fields(actor: dict, here: int | str, fields: list[str], ctx: dict, seen: set[str]) -> dict:
    if not fields:
        return {}
    stats = body_stats(actor, ctx) if any(field not in _KEPT_FIELDS for field in fields) else {}
    seen.update(stats)
    age, lineage = actor_age(actor, ctx["world_time"]), ctx["subspecies_by_id"].get(actor.get("subspecies"))
    kept = {
        "adult_on": lambda: crossed_on(actor, adult) if age < (adult := adult_age(actor, ctx)) else None,
        "age": lambda: age,
        "age_overgrowth": lambda: int(actor.get("age_overgrowth") or 0) or None,  # a migrant's mark, `born` its arrival
        "army_since": lambda: kept_army_since(actor),  # when it joined its town's army, none outside one
        "asset_id": lambda: actor.get("asset_id"),
        "at": lambda: tile_text(*actor_xy(actor)),
        "beside_building": lambda: whereabouts(actor, ctx["buildings_by_id"], ctx["built"])["beside_building"],  # the second ring of `in_building`
        "born": lambda: entity_born(actor),
        # Its lineage's own line, as on the roll: none to come where it never bears
        "breeds_on": lambda: crossed_on(actor, breeding) if age < (breeding := breeding_age(actor, ctx)) and fertile(lineage) else None,
        "city_since": lambda: kept_city_since(actor),
        "crafted": lambda: ctx["made"][actor["id"]],  # the world's items it made, as `actor … ranks` counts them
        "gen": lambda: int(actor.get("generation") or 1),
        "hatch_on": lambda: hatch_on(actor, ctx),
        "home": lambda: actor.get("homeBuildingID"),  # its roof's id, none for one sleeping out: `ground <id>` tells the roof
        "in_building": lambda: {"asset_id": room.get("asset_id"), "id": room["id"]} if (room := indoors(actor, ctx["buildings_by_id"], ctx["built"])) else None,
        "island_id": lambda: here,
        "islet": lambda: here,  # the same land, told as a plain line tells it: an islet's own tile, else the land's id
        "job": lambda: ctx["profession"](actor),
        "kills": lambda: _held(actor, "kills"),  # the body's own counter, as `--rank` reads it: no stat of `actor … stats`
        "life_stage": lambda: _stage(actor, ctx, age, adult_age(actor, ctx)),
        "lover": lambda: lover if (lover := actor.get("lover")) in ctx["living_ids"] else None,  # its mate's id, a dead one none
        "name": lambda: actor.get("name"),
        "parents": lambda: sorted(p for p in (actor.get("parent_id_1"), actor.get("parent_id_2")) if p and p != -1) or None,  # ids, not refs: a line holds one
        "place": lambda: ctx["place_index"].at(*actor_xy(actor)),
        "sex": lambda: sex_label(actor),
        "statuses": lambda: kept_statuses(actor),
        "subspecies": lambda: actor.get("subspecies"),
        "task": lambda: kept_task(actor),
        **{kind: (lambda kind=kind: entity_ref(actor.get(_MEMBERSHIPS[kind][1]), ctx["ties"][kind])) for kind in ctx.get("ties", ())},
    }
    return {field: kept[field]() if field in kept else stats.get(field, _FIELD_FLOORS.get(field)) for field in fields}


# What bars a pair, the bodies one cause holds told after it once: `hungry 425 426`, a world law alone.
def _bars_told(barred: list[str]) -> list[str]:
    by_cause: dict[str, list[str]] = {}
    for bar in barred:
        cause, _, body = bar.rpartition(" ")
        by_cause.setdefault(cause if body.isdigit() else bar, []).extend([body] if body.isdigit() else [])
    return [" ".join([cause, *bodies]) for cause, bodies in by_cause.items()]


# Whether a body belongs to every entity `roster` is narrowed to, read off the body itself — a king the log alone crowned and buried (`fallen`) of the realm he left.
def _belongs(save: dict, entities: list[tuple[str, int | str]], fallen: dict[int, int] | None = None) -> Callable[[dict], bool]:
    ties = [_tie(save, kind, entity_id, fallen or {}) for kind, entity_id in entities]
    return ties[0] if len(ties) == 1 else lambda actor: all(tie(actor) for tie in ties)


# `born:`'s span of world time, a year `y2` or a month `"y2 m12"` as every output dates one, with the words it was asked in.
def _born_arg(value: str) -> tuple[str, float, float]:
    if not (found := re.fullmatch(r"y(\d+)(?: m(\d+))?", value.strip())) or int(found[1]) < 1 or not 1 <= int(found[2] or 1) <= 12:
        raise argparse.ArgumentTypeError(f'`{value}` is no date — a year `y2`, a month `"y2 m12"`')
    start = (int(found[1]) - 1) * UNITS_PER_YEAR + (int(found[2] or 1) - 1) * UNITS_PER_MONTH
    return value.strip(), start, start + (UNITS_PER_MONTH if found[2] else UNITS_PER_YEAR)


# What keeps a body of age from breeding, WB weighing each partner: a belly short of a baby or half-full, a footing to leave first — tagged `tiny_islet 40`.
def _breeding_bars(actor: dict, ctx: dict, island_of: TileIslands, grid: LazyTileGrid, names: list[str]) -> set[str]:
    bars = set()
    if needs_food(ctx["subspecies_by_id"].get(actor.get("subspecies"))) and (int(actor.get("nutrition") or 0) < NEW_BABY_NUTRITION or is_hungry(actor, ctx)):
        bars.add("hungry")
    if (here := _standing(actor, island_of, grid, names)) == _WATER:
        bars.add(_WATER)
    elif here == _ISLET and island_of.islet_size(actor_xy(actor)) <= _GOOD_ISLET:
        bars.add("tiny_islet")
    return {f"{bar} {actor['id']}" for bar in bars}


# How the lineages breed, WB's trait ids prefixes off — `sexual, viviparity` —, each by its ids or count; one shared by all, alone: `subspecies … traits` names them.
def _breedings(save: dict, listed: dict, counted: bool) -> str | dict[str, list[int] | int]:
    held: defaultdict[str, list[int]] = defaultdict(list)
    for lineage in save.get("subspecies") or []:
        if str(lineage["id"]) in listed:
            own = (trait for trait in sorted(lineage.get("saved_traits") or ()) if trait.startswith("reproduction_"))
            traits = [trait.removeprefix("reproduction_").removeprefix("strategy_") for trait in own]
            held[", ".join(traits) or "none"].append(lineage["id"])
    if len(held) == 1:
        return next(iter(held))
    return {breeding: len(ids) if counted else sorted(ids) for breeding, ids in sorted(held.items())}


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
    persons: dict[str, dict[int, float]] = {stat: {} for stat in ("equipment_power", "oldest", *_FEATS, *_SKILLS)}
    sapient = _sapient_subspecies(save)
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
        for stat in _SKILLS:
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


# Every living lineage by its id, a line each as `subspecies … metadata` tells it: its kind, name, members, the biome that shaped it, its month — `type:` narrows.
def _build_lineages(save: dict, kinds: set[str] | None, minded: bool | None = None) -> dict:
    members = Counter(actor.get("subspecies") for actor in save.get("actors_data") or [] if not is_boat(actor))
    rows = {}
    for lineage in sorted(save.get("subspecies") or [], key=lambda s: s["id"]):
        if (kinds is not None and lineage.get("species_id") not in kinds) or (minded is not None and is_sapient(lineage) != minded):
            continue
        biome = (lineage.get("biome_variant") or "").removeprefix("biome_")
        rows[str(lineage["id"])] = {
            "asset_id": lineage.get("species_id"),
            **({"biome": biome} if biome_lore(biome) else {}),
            "born": entity_born(lineage),
            "members": members[lineage["id"]],
            "name": lineage.get("name"),
            **({"sapient": True} if is_sapient(lineage) else {}),
        }
    return rows


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


# Each kind's first couple by WB's `canFallInLoveWith`, dated by the later breeding age (`now` once both hold); today's gap, walked on one shared land only.
def _build_pairings(save: dict, save_path: Path) -> list[dict]:
    ctx, kinds = build_actor_stats_context(save), defaultdict(list)
    for actor in save.get("actors_data") or []:
        if not is_boat(actor):
            kinds[actor.get("asset_id")].append(actor)
    island_of, walk_map = compute_islands_cached(save, save_path)[1], None
    grid, laws = LazyTileGrid(save), world_laws(save)
    # Traits and breeding are a lineage's, read once each: a kind's bodies share a handful of lineages, and every pair below asks of both.
    traits = {sub["id"]: frozenset(sub.get("saved_traits") or ()) for sub in save.get("subspecies") or []}
    mode, empty = {sid: breeding_mode(lineage) for sid, lineage in traits.items()}, frozenset()
    unfed = {sub["id"] for sub in save.get("subspecies") or [] if spores_unfed(sub)}  # spores no meal will ever let go: no date to give them
    carry = {sid: maturation_months(lineage, ctx) * UNITS_PER_MONTH if _carried(lineage) else 0 for sid, lineage in traits.items()}  # the bearer's sets it
    rows: list[tuple[float, dict]] = []
    now = ctx["world_time"]  # a birth is today's at the earliest — and may be, WB saving no status: a `pregnant` begun before the save shows nowhere

    for kind, bodies in kinds.items():
        ready = {actor["id"]: crossed_at(actor, breeding_age(actor, ctx)) for actor in bodies}
        where = {actor["id"]: actor_xy(actor) for actor in bodies}
        mating = [actor for actor in bodies if mode.get(actor.get("subspecies")) == "mate"]
        row: dict = {"asset_id": kind}
        births = []
        lone = [actor for actor in bodies if mode.get(actor.get("subspecies")) == "alone"]
        if fed := [actor for actor in lone if actor.get("subspecies") not in unfed]:  # a lineage breeding alone needs no partner
            row["alone_on"] = min(ready[actor["id"]] for actor in fed)
            if any(_SOULBORNE in traits.get(actor.get("subspecies"), empty) for actor in fed):  # WB births it once a blow has struck a soul
                row["needs"] = "soul"
            births += [max(ready[actor["id"]] + carry.get(actor.get("subspecies"), 0), now) for actor in fed]
        sexed = {actor["id"]: _SEXED in traits.get(actor.get("subspecies"), empty) for actor in mating}
        bars = {actor["id"]: _breeding_bars(actor, ctx, island_of, grid, save["tileMap"]) for actor in mating}
        # WB's law on babies, a beast's or a thinker's, read off the kind's first lineage that mates — every one of a kind thinks or none does.
        law = "world_law_civ_babies" if mating and is_sapient(ctx["subspecies_by_id"].get(mating[0].get("subspecies"))) else "world_law_animals_babies"
        barred_by_law = {law} if not laws.get(law, True) else set()
        # Lovers first, WB never parting them; then a pair nothing bars — a law always, a body's state only if ready now; then the earliest, the nearest.
        best = min(
            (
                (
                    a.get("lover") != b["id"],
                    bool(barred := sorted((bars[a["id"]] | bars[b["id"]] if (mates := max(ready[a["id"]], ready[b["id"]])) <= now else set()) | barred_by_law)),
                    mates,
                    walk_tiles(where[b["id"]][0] - where[a["id"]][0], where[b["id"]][1] - where[a["id"]][1]),
                    a,
                    b,
                    barred,
                )
                for i, a in enumerate(mating)
                for b in mating[i + 1 :]
                if _may_mate(a, b, sexed[a["id"]] or sexed[b["id"]])
            ),
            key=lambda pair: pair[:4],
            default=None,
        )
        if best:
            apart, _, row["mates_on"], crow, a, b, barred = best
            sexual = sexed[a["id"]] or sexed[b["id"]]
            bearer, other = (b, a) if sexual and b.get("sex") == 1 else (a, b)  # a sexed pair's mother carries (WB `checkForBabies`)
            row |= {
                "barred": _bars_told(barred) or None,
                "crow_tiles": round(crow),
                "drawn": True if not sexual else None,  # no mother to put first: the bearer is drawn at the birth itself
                "lovers": True if not apart else None,
                "pair": [bearer["id"], other["id"]],  # the bearer first, whose town the child joins (WB `BabyMaker.makeBaby`), else the other's
            }
            # Lovers may carry already, unseen, where the save keeps no status; where it does, they wait out the afterglow of their last kiss.
            glow = max(status_left(a, "afterglow") or 0, status_left(b, "afterglow") or 0)
            conceived = max(row["mates_on"], now + glow) if apart or status_left(bearer, "pregnant") is not None else row["mates_on"]
            births.append(max(conceived + carry.get(bearer.get("subspecies"), 0), now))
            (ax, ay), (bx, by) = where[a["id"]], where[b["id"]]
            if (land := island_of.get((ax, ay))) is not None and land == island_of.get((bx, by)):
                walk_map = walk_map or WalkMap(save)
                if (way := walk_way(walk_map, walk_map.gait(None, frozenset()), ax, ay, {by * walk_map.width + bx})) is not None:
                    row["walk_tiles"] = round(way[3])  # the tiles trodden between them, not the way's cost
                    if row["walk_tiles"] == row["crow_tiles"]:  # a straight way says its length once
                        del row["crow_tiles"]
        elif not mating and not lone:  # no lineage of the kind holds a breeding trait: it never breeds
            row["missing"] = "reproduction"
        elif mating:  # a partner wanted, none to be had: a sexed kind of one sex says which, else blood or pledges bar every pair
            sexes = {sex_label(actor) for actor in mating}
            row["missing"] = ({"female": "male", "male": "female"}[sexes.pop()]) if len(sexes) == 1 and all(sexed.values()) else "partner"
        elif not fed:  # breeding alone, but by spores a body with no stomach never sheds
            row["missing"] = "meal"
        # A barren lineage beside fertile ones, its bodies by lineage: WB wants `needs_mate` of both lovers, so none of them ever pairs, not even across lineages.
        if (mating or lone) and (barren := Counter(sid for actor in bodies if (sid := actor.get("subspecies")) is not None and mode.get(sid) is None)):
            row["barren"] = {str(sid): count for sid, count in sorted(barren.items())}  # ids as JSON keys, in their numeric order
        if births:  # the pair's own, never a bearer's outside it: a line reads as one couple's
            row["birth_on"] = min(births)
        # A birth under way, as the save keeps it: its date is the game's own, apart as `due` — its bearers counted, each by `roster`.
        if carrying := [left for actor in bodies if (left := max(status_left(actor, status) or 0 for status in _CARRYING))]:
            row["pregnant"], row["due"] = len(carrying), now + min(carrying)
        # The first birth leads, under way or to come: what the chronicle asks is when a body is born, not when two come of age
        rows.append((min(row.get("birth_on", inf), row.get("due", inf)), row))

    for _, row in rows:  # the hours dated only once sorted on: `now` for what already holds
        for key in ("alone_on", "birth_on", "due", "mates_on"):
            if key in row:
                row[key] = "now" if row[key] <= now else world_date(row[key])

    return [row for _, row in sorted(rows, key=lambda entry: (entry[0], entry[1]["asset_id"]))]


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


# Each living body but the hulls, to weigh a world-wide claim (« the only one »); `since` keeps the arrivals and the land-changers, whose `was_on` `land` reads too.
def _build_roster(
    save: dict,
    save_path: Path,
    island_of: TileIslands,
    kinds: set[str] | None,
    trait: str | None,
    lands: frozenset[int | str] | None,
    since: str | None,
    later: list[dict],
    sapient: bool | None,
    settle: bool,
    barred: bool,
    bred: bool,
    patch: set[tuple[int, int]] | None,
    status: str | None,
    task: str | None,
    has: str | None,
    lacks: str | None,
    top: str | None,
    limit: int | None,
    entities: list[tuple[str, int | str]],
    near: tuple[tuple[int, int], int | None] | None,
    fields: list[str],
    stage: frozenset[str] | None,
    born: tuple[str, float, float] | None,
    told_parts: frozenset[str],
    cause: str | None,
) -> list[dict] | dict:
    earlier, was = _then(since) if since else (None, None)
    # Each body's stage then, under `--since`: one that grew from a child to a teen changed as one that changed land did
    once_ctx = build_actor_stats_context(earlier) if earlier is not None else {}
    then_bodies = {a["id"]: a for a in earlier.get("actors_data") or []} if earlier is not None else {}
    entity = entities[0] if entities else None  # the one whose leavers `left` tells: every entity narrows, none shapes the line
    belongs = _belongs(save, entities)
    # Crowned after the earlier save and dead before this one: no save held them king, the log alone did
    fallen = _fallen_kings(save, earlier) if earlier is not None and ("job", "king") in entities else {}
    belonged = _belongs(earlier, entities, fallen) if earlier is not None else belongs  # the same ties read off the earlier save, a pact's crowns as they stood
    # Under an entity, `--since` weighs who belonged then: a body that joined arrives, one alive elsewhere has left, though the world saw both all along.
    members_then = {a["id"] for a in earlier.get("actors_data") or [] if belonged(a)} if entity and earlier is not None else None
    known = was if members_then is None else members_then
    weighed = has or lacks  # one measure each: `has:` keeps whoever holds any, `lacks:` whoever holds none — `--rank`'s own is its order
    thinking = _sapient_subspecies(save) if sapient is not None else None  # `sapient` keeps the minds, `beasts` the rest
    grid = LazyTileGrid(save)  # rows decoded as read: a body off every land alone asks its tile
    asked = lands
    if patch and lands is None and (under := island_of.get(next(iter(patch)))) is not None:
        asked = frozenset({under})  # a patch lies on one land, which then goes unsaid as a lone land's does
    alone = next(iter(asked)) if asked is not None and len(asked) == 1 else None  # one land named goes unsaid on every line: several, each line tells its own
    ctx = build_actor_stats_context(save)
    if ties := [kind for kind in _TIES if kind in fields]:
        ctx["ties"] = {kind: index_by_id(save.get(_MEMBERSHIPS[kind][0]) or []) for kind in ties}
    if not {"beside_building", "in_building"}.isdisjoint(fields):
        ctx["buildings_by_id"] = index_by_id(save.get("buildings") or [])
        ctx["built"] = built_by_tile(save)
    if "job" in fields:
        ctx["profession"] = lambda actor: resolve_profession(actor, save)
    if "lover" in fields:
        ctx["living_ids"] = {actor["id"] for actor in save.get("actors_data") or []}
    stated = fields or (top and top not in _TOP_MEASURES)  # a stat asked or ranked by: every body's `actor … stats` read
    seen = set(_KEPT_FIELDS) | _FIELD_FLOORS.keys() if stated else set()  # every field a body can be asked or ranked by, its stats added as they come
    if stated:
        ctx["children_by_parent"] = children_by_id(save)  # `body_stats` counts each body's children as `actor` does
    if top == "crafted" or "crafted" in fields:  # the world's items by their maker, as `actor … ranks` counts a body's work
        ctx["made"] = crafted_counts(ctx["items_by_id"])
    if "place" in fields:  # each forged place drawn once for the whole roll, as `metadata` draws it for one body
        ctx["place_index"] = PlaceIndex(save, save_path, island_of, WalkMap(save))
    if settle or barred:  # the ground `settle_gates` weighs, gathered only for a roll that filters on it
        ctx |= {
            "city_zones": cache(lambda: city_zones(save, island_of)),
            "island_lookup": lambda: island_of,
            "tile_grid": lambda: grid,
            "tile_map": save["tileMap"],
            "world_laws": world_laws(save),
        }

    # A trait is a body's own or its lineage's: `gift_of_thunder` is born with a whole line, `fire_blood` with one body — `trait:` finds either.
    bearers = {sub["id"] for sub in save.get("subspecies") or [] if trait in (sub.get("saved_traits") or ())} if trait else set()

    # Under `--since`, a tally is weighed against what the body held then: only one that moved is told, as a pair — `level` from its floor, never from 0.
    once = {a["id"]: _held(a, has) for a in earlier.get("actors_data") or []} if has and earlier is not None else None

    floor = 1 if has == "level" else 0
    bodies, still, unranked, aged = [], 0, 0, 0

    (nx, ny), near_id = near or ((0, 0), None)
    far: dict[int, float] = {}  # each body's unrounded length, ranked on: two read alike may still stand apart

    # A body's line beside the one ranked around: its length as the crow flies, and its heading — not under `--since`, its lines full
    def towards(row_id: int, x: int, y: int) -> dict:
        far[row_id] = walk_tiles(x - nx, y - ny)
        return {"crow_tiles": round(far[row_id]), "dir": None if since else bearing(x - nx, y - ny)}

    for actor in save.get("actors_data") or []:
        if near and actor["id"] == near_id:  # the body ranked around stands nearest to itself
            continue
        borne = not trait or trait in (actor.get("saved_traits") or ()) or actor.get("subspecies") in bearers
        if (
            is_boat(actor)
            or (kinds and actor.get("asset_id") not in kinds)
            or not borne
            or (thinking is not None and (actor.get("subspecies") in thinking) != sapient)
        ):
            continue
        if (patch is not None and actor_xy(actor) not in patch) or not belongs(actor):
            continue
        if status and status not in (kept_statuses(actor) or ()):
            continue
        if task and kept_task(actor) != task:
            continue
        # Born in this world that year or month: a migrant's birth is no date the save holds, its arrival less whole years brought guessing the month
        if born and (actor.get("age_overgrowth") or not born[1] <= float(actor.get("created_time") or 0) < born[2]):
            continue
        # Born of a body, its parents kept: under `--since`, born since — one the earlier save held was born before it, whatever it did after
        if bred and (not (actor.get("parent_id_1") or actor.get("parent_id_2")) or (was is not None and actor["id"] in was)):
            continue
        grown = _stage(actor, ctx, actor_age(actor, ctx["world_time"]), adult_age(actor, ctx)) if stage or was is not None else None
        if stage and grown not in stage:
            continue
        held = _held(actor, weighed, ctx) if weighed else 0
        before = once.get(actor["id"], 0) if once is not None else 0  # with no `--since`, a tally is weighed against nought
        if (has and held == before) or (lacks and held):
            continue
        figure = _rank_figure(actor, top, ctx, seen) if top else 0  # `--rank`'s figure: one holding none is counted once every other filter has had its say
        gates = settle_gates(actor, ctx) if settle or barred else None
        if settle and gates not in (True, ["child"]):  # founds where it stands once grown: nothing, or its youth alone, bars it
            continue
        if barred and (gates is None or gates in (True, ["child"])):  # a thinker something besides its youth keeps from founding
            continue
        here = _standing(actor, island_of, grid, save["tileMap"])
        change: dict = {has: held if once is None else [max(before, floor), max(held, floor)]} if has else {}
        if top:  # the figure ranked on, beside the line; under `age`, its month, which tells a cohort of one age apart
            change |= {top: figure} | ({"born": entity_born(actor)} if top == "age" else {})
        if near:
            change |= towards(actor["id"], *actor_xy(actor))
        if was is not None and actor["id"] in known and not has:  # one unseen then was born or set down since, and says so by standing in the roll at all
            past = then_bodies[actor["id"]]
            was_stage = _stage(past, once_ctx, actor_age(past, once_ctx["world_time"]), adult_age(past, once_ctx))
            if (then := was[actor["id"]]) == here and was_stage == grown:
                still += lands is None or here in lands  # stood still: nothing for `since` to say of it, but that it was left out
                continue
            change = (
                ({"was_on": then} if then != here else {})
                | ({"life_stage": [was_stage, grown]} if was_stage != grown else {})
                | ({"crow_tiles": change["crow_tiles"]} if near else {})
            )
        if was is not None and not has:  # under `--since`, the parts asked alone, a stage reached counted where it goes untold
            part = "arrived" if actor["id"] not in known else "moved" if "was_on" in change else "grew"
            if part not in told_parts:
                aged += part == "grew" and (lands is None or here in lands)
                continue
        if lands is None or here in lands or change.get("was_on") in lands:
            if top and not figure:  # holds none of the measure: left out of the ranking, and said so
                unranked += 1
            else:
                bodies.append((actor, here, change | (settle_told(gates) if barred else {}), figure))
    if top and top not in seen and top not in _TOP_MEASURES and (bodies or unranked):  # a stat no body weighed here carries, told once their stats are known
        figures = sorted({*_TOP_MEASURES, *_RANKED_KEPT, *(field for field in seen if field not in _KEPT_FIELDS)})
        raise ValueError(
            f"✗ `{top}`: no figure `--rank` reads{_guessed(top, figures)} — it takes one of `actor <id> stats`, `age`, `crafted`, `gen`, `kills`, `p<id>` or `x,y`"
        )
    gone, mourned = [], False  # `mourned`: the dead searched, found or not — `killed_by` asked of them even where none died

    if earlier is not None and was is not None and not (settle or barred) and "died" in told_parts:  # the dead found nothing
        mourned = True
        standing = partial(_standing, island_of=island_of, grid=grid, names=save["tileMap"])  # where each died, on today's map
        gone = _gone_since(save, earlier, later, kinds, trait, asked, sapient, bred, belonged, stage, standing, fields, born)
        if gone and (unborne := [field for field in fields if field not in _GONE_FIELDS]):  # a stale save's figure would read as the dead's: said, not dropped
            told = ", ".join(f"`{field}`" for field in unborne)
            print(f"⚠ {told}: none on a `died` line — the dead take {', '.join(f'`{field}`' for field in _GONE_FIELDS)} alone", file=sys.stderr)
        if cause:  # `died:`: the dead of one cause, as the register files it — said once by the filter, never on each line
            gone = [{**row, "died_of": None} for row in gone if row["died_of"] == cause]
        if once is not None:  # the dead that held the tally, each with what it takes away: where it stood and who took it are another question's
            gone = [{**row, has: once[row["id"]], "killed_by": None, "was_on": None} for row in gone if once.get(row["id"])]
        if near:  # the dead measured from where they fell
            fell = kept_deaths(save)
            gone = [row | towards(row["id"], fell[row["id"]]["x"], fell[row["id"]]["y"]) for row in gone]

    one_kind = kinds is not None and len(kinds) == 1  # a lone `type:` names the kind, as a lone land its own
    one_stage = stage is not None and len(stage) == 1  # and a lone stage its own
    town = dict(entities).get("city")  # and a town filtered every line's
    towns = index_by_id(save.get("cities") or [])

    # The one line every body gets, whatever the filter: who, its kind, sex, town, land and stage — a filter silences the field it fixes, `--with` drives some off
    def socle(actor: dict, here: int | str, change: dict) -> dict:
        phase = _stage(actor, ctx, actor_age(actor, ctx["world_time"]), adult_age(actor, ctx))
        heart = islet_heart(island_of.islet_tiles(actor_xy(actor))) if here == _ISLET else None  # which islet, as `actor … metadata` names it
        return {
            "asset_id": None if one_kind else actor.get("asset_id"),
            "city": None if town is not None and "part" not in change else entity_ref(actor.get("cityID"), towns),  # a leaver's is where it went
            "id": actor["id"],
            # Said outright beside a `was_on`, a missing one reading as still on the land left; silent where a lone land already named it
            "island_id": None if heart or (here == alone and "was_on" not in change) else here,
            "islet": tile_text(*heart) if heart else None,
            "life_stage": None if phase == "adult" or one_stage else phase,  # silent at `adult`, as in `surroundings`
            "name": actor.get("name"),
            "sex": sex_label(actor),
            **change,
        }

    # Every line's place, the living, the dead and the gone elsewhere alike: nearest first, the measure highest, else by id — and the figure a cut may not split
    def placed(row_id: int, figure: int = 0, actor: dict | None = None) -> tuple[tuple, object]:
        if near:
            return (far[row_id], row_id), round(far[row_id])
        if top == "age" and actor is not None:  # whole years tie a cohort: the earliest born first, the years it arrived with counted
            born_at = counted_birth(actor)
            return (-figure, born_at, row_id), (figure, world_date(born_at))
        return ((-figure, row_id), figure) if top else ((row_id,), row_id)

    asked = [field for field in fields if field not in ("island_id", "islet", "killed_by")]  # the land told as the socle tells it, a killer the dead's alone
    # Each field asked beyond the socle drives one off it, the first the line shows in `_DISPLACED` — never one `--since` or `--rank` put there
    driving = len([field for field in fields if field not in (*_DISPLACED, "islet", "sex")])

    told_as = {"island_id": ("island_id", "islet")}  # a land is one field, islet or not

    def fielded(actor: dict, here: int | str, change: dict) -> dict:
        row = socle(actor, here, change)
        if driving:
            # What a part or a rank put there stays, and what tells it: the land a mover reached, the town a leaver went to
            kept = {*change, *(["island_id"] if "was_on" in change else []), *(["city"] if "part" in change else [])}
            shown = [key for key in _DISPLACED if key not in kept and any(row.get(told) is not None for told in told_as.get(key, (key,)))]
            for key in shown[:driving]:
                for told in told_as.get(key, (key,)):
                    row.pop(told, None)
        return row | _asked_fields(actor, here, asked, ctx, seen)

    lines: list[tuple[tuple, object, dict]] = []
    for actor, here, change, figure in bodies:
        row = fielded(actor, here, change)
        if since and not has:  # filed by what befell it: an arrival bears no mark of its own, read off the others it would be guessed
            row["part"] = _filed_as(change)
        lines.append((*placed(actor["id"], figure, actor), row))
    _refuse_unseen(fields, seen | {"killed_by"} if mourned else seen)
    parted = since and not has
    lines.extend((*placed(row["id"]), row) for row in gone)  # a dead line's `part` said even beside `has:`, where no living line bears one
    if parted and members_then is not None and entity and "left" in told_parts:  # alive and elsewhere now: left the entity, which a death does not say
        for a in sorted((a for a in save.get("actors_data") or [] if a["id"] in members_then and not belongs(a)), key=itemgetter("id")):
            here = _standing(a, island_of, grid, save["tileMap"])
            row = fielded(a, here, {"part": "left"})
            row |= towards(a["id"], *actor_xy(a)) if near else {}  # before `placed`, which ranks on the length it records
            lines.append((*placed(a["id"]), row))
    if parted and len(told_parts) == 1:  # one part named: the filter says it, no line repeats it
        lines = [(order, tie, {**row, "part": None}) for order, tie, row in lines]
    lines.sort(key=itemgetter(0))
    kept = len(lines) if limit is None else _tied_cut([tie for _, tie, _ in lines], limit)
    living = bool(told_parts - {"died", "left"})  # who stood still or only grew is a living part's tally: beside the dead alone it would read as theirs
    unseen = [f"{still} stood still" if still else "", f"{aged} only grew (`--filter grew`)" if aged else ""] if living else []
    left = [f"{unranked} with no {top}" if unranked else "", *unseen]
    if kept < len(lines) or any(left):  # a cut, or bodies a filter set aside unseen: said beside the list, which keeps its shape
        by = f"nearest the {'body' if near[1] is not None else 'tile'}" if near else f"by {top}" if top else "by id"
        cut = f"{len(lines)} bodies, the first {kept} {by} — `--limit all` for every one" if kept < len(lines) else ""
        print(f"⚠ {'; '.join(filter(None, [cut, *left]))}", file=sys.stderr)
    return [row for _, _, row in lines[:kept]]


# Actors split three ways: hulls (`boats`), thinking souls (`sapient_pop`) and the beasts (`wild_creatures`). `infected` = WB's `current_infected`.
def _build_snapshot(save: dict) -> dict:
    actors = save.get("actors_data") or []
    civic, roofs = civic_building_ids(), house_building_ids()
    asset_counts = Counter(b.get("asset_id") or "" for b in save.get("buildings") or [])  # Count `asset_id`s once, classify the distinct keys — four scans saved.

    # `infected` ⊂ `sick` — a plague never shows up in the first, hence both; each drops at 0, outbreaks leaving them idle most chapters.
    boats = infected = passengers = sapients = sick = 0
    sapient, statuses = _sapient_subspecies(save), Counter()
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


# Whether a birth waits `maturation`: a pair's or a virgin's only if viviparous (an egg is laid at once), buds and sprouts always, a fission or a spore never.
def _carried(traits: frozenset[str]) -> bool:
    if traits & _UNCARRIED:
        return False
    return "reproduction_strategy_viviparity" in traits if traits & _STRATEGIC else True


def _count_leaders(counts: Mapping, records: list[dict], min_peers: int) -> list[dict]:
    return [{"id": eid, "name": _name_of(records, eid), "value": n} for eid, n in first_place(counts, min_peers)]


# The kings dead since `then`, by body, with the realm each reigned over: the log tells a king's fall, its murder naming the killer — the register, then, the body.
def _fallen_kings(save: dict, then: dict) -> dict[int, int]:
    since, now = (float((reading.get("mapStats") or {}).get("world_time") or 0) for reading in (then, save))
    deaths, fallen = kept_deaths(save), {}
    for entry in log_entries(since, now, deaths=True):
        if entry["event"] == "king_dead":
            fallen[entry["actor_id"]] = entry["kingdom_id"]
        elif entry["event"] == "king_killed":  # its body the killer's: a king it slew that month, nearest the slain one's point — any, off a table without `job`
            dealt = [dead for dead in deaths.values() if dead["killer"] == entry["actor_id"] and since < dead["died"] <= now and dead["job"] in ("king", None)]
            if dealt:
                at = (entry["date"], entry["x"], entry["y"])
                king = min(dealt, key=lambda dead, at=at: (world_date(dead["died"]) != at[0], walk_tiles(dead["x"] - at[1], dead["y"] - at[2])))
                fallen[king["id"]] = entry["kingdom_id"]
    return fallen


# The part of a `--since` roll a living body falls in, off what changed: a land left, else a stage reached, else nothing seen of it before — an arrival.
def _filed_as(change: dict) -> str:
    return "moved" if "was_on" in change else "grew" if "life_stage" in change else "arrived"


# `--filter`'s words, bare from a closed list (mind, founding, birth, job, land, `--since` part, stage), else `key:value`: a group adds up, groups cross.
def _filter_arg(value: str) -> dict[str, frozenset]:
    groups = {"birth": ("bred",), "founding": ("barred", "settle"), "job": JOBS, "mind": ("beasts", "sapient"), "since": _SINCE_PARTS, "stage": _LIFE_STAGES}
    taken: defaultdict[str, set] = defaultdict(set)
    for word in re.split(r",(?!-?\d)", value):  # a tile's comma, `patch:874,571`, ends no word
        if body := _ONE_BODY.fullmatch(word):
            raise argparse.ArgumentTypeError(f"`{word}` filters nothing — one body is `actor {body[1]}`, the bodies nearest it `--rank p{body[1]}`")
        key, colon, said = word.partition(":")
        if colon:
            taken[key].add(_keyed(key, said))
        elif re.fullmatch(r"i\d+|islets?|water", word):  # a land `i<id>`, as `--to` names one, the islets a body stands on one of, the water
            taken["land"].add(int(word[1:]) if word[1:].isdigit() else _ISLET if word.startswith("islet") else word)
        elif group := next((name for name, words in groups.items() if word in words), None):
            taken[group].add(word)
        else:  # every word and key in `gloss world`, the closest few offered
            known = [*(word for words in groups.values() for word in words), "islets", "water", *(f"{key}:" for key in (*_MEMBERSHIPS, *_KEYED))]
            raise argparse.ArgumentTypeError(f"`{word}` filters nothing{_guessed(word, known)}")
    return {group: frozenset(values) for group, values in taken.items()}


# The dead since an earlier chapter, as the register keeps them — a body some save held filtered as it last stood, one none did by the register's line alone.
def _gone_since(
    save: dict,
    then: dict,
    later: list[dict],
    kinds: set[str] | None,
    trait: str | None,
    asked: frozenset[int | str] | None,
    sapient: bool | None,
    bred: bool,
    belongs: Callable[[dict], bool],
    stage: frozenset[str] | None,
    standing: Callable[[dict], int | str],
    fields: list[str],
    born: tuple[str, float, float] | None,
) -> list[dict]:
    deaths, since = kept_deaths(save), float((then.get("mapStats") or {}).get("world_time") or 0)
    last = {actor["id"]: actor for reading in (then, *later[:-1]) for actor in reading.get("actors_data") or []}  # as the latest save before its death knew it
    lineages = [sub for reading in (then, *later) for sub in reading.get("subspecies") or []]  # one born and gone between included
    thinking = {sub["id"] for sub in lineages if is_sapient(sub)}
    bearers = {sub["id"] for sub in lineages if trait in (sub.get("saved_traits") or ())} if trait else set()
    ctx, alive = build_actor_stats_context(save) if stage else {}, index_by_id(save.get("actors_data") or [])
    lone, rows = asked is not None and len(asked) == 1, []  # one land named: where each fell goes unsaid
    minded = {body.get("asset_id") for body in (*alive.values(), *last.values()) if body.get("subspecies") in thinking}  # the kinds a mind was seen in
    one_kind = kinds is not None and len(kinds) == 1  # its kind unsaid, as on every line of the roll: no field to drive off
    driving = len([field for field in fields if field not in _DEAD_SOCLE])  # each field asked drives one off, as off a living line: its sex stays

    # A dead body's lineage: the register's, else a parent's — one born and gone between two saves never had its own written (`-1`) —, else none
    def lineage(dead: dict) -> int | None:
        for known in (dead, *(alive.get(parent) or last.get(parent) or deaths.get(parent) or {} for parent in dead["parents"])):
            if (sid := known.get("subspecies")) is not None and sid >= 0:
                return sid
        return None

    for dead in deaths.values():
        if dead["died"] <= since or is_boat(dead) or (kinds and dead["asset_id"] not in kinds):
            continue
        if bred and (not dead["parents"] or dead["born"] <= since):  # a birth since, dead before the save
            continue
        if not belongs(body := last.get(dead["id"]) or {**dead, "created_time": dead["born"]}):
            continue
        sid = lineage(dead)
        if trait and trait not in (body.get("saved_traits") or ()) and sid not in bearers:
            continue
        thinks = sid in thinking if sid is not None else dead["asset_id"] in minded  # no lineage known: its kind's mind
        if (sapient is not None and thinks != sapient) or (asked is not None and standing(dead) not in asked):
            continue
        if stage and _stage(body, ctx, actor_age(body, dead["died"]), adult_age(body, ctx)) not in stage:  # the stage it died at
            continue
        if born and (body.get("age_overgrowth") or not born[1] <= dead["born"] < born[2]):  # a migrant told by the last save that saw it alive
            continue
        # Its name at death the register's, not the last save's; `was_on` silent under a lone land; its sex, never changing, off the last save that saw it alive
        row = {
            "blow": dead["blow"],
            "died": world_date(dead["died"]),
            "died_of": dead["cause"],
            "id": dead["id"],
            "part": "died",
            "was_on": None if lone else standing(dead),
        }
        kept = {  # its socle, or under `--with` what is asked of it: the tile it fell on, born, its killer, and parents with WB's -1 already dropped
            "asset_id": None if one_kind else dead["asset_id"],
            "at": tile_text(dead["x"], dead["y"]),
            "born": world_date(dead["born"]),
            "killed_by": alive_or_dead_ref(dead["killer"], alive, deaths),
            "name": dead["name"] or body.get("name"),
            "parents": sorted(dead["parents"]) or None,
            "sex": sex_label(last[dead["id"]]) if dead["id"] in last else None,
        }
        present = [key for key in _DISPLACED if key in _DEAD_SOCLE and kept[key] is not None]
        shown = (*(key for key in _DEAD_SOCLE if key not in present[:driving]), *fields)
        rows.append(row | {field: kept[field] for field in shown if field in kept})
    return sorted(rows, key=lambda row: row["id"])


# The words a mistyped one is closest to, offered after a refusal: ` (`teen`?)`, nothing where none comes near.
def _guessed(word: str, known: Sequence[str]) -> str:
    return f" ({', '.join(f'`{near}`' for near in close)}?)" if (close := difflib.get_close_matches(word, known, cutoff=0.7)) else ""


# A body's measure as `has:`, `lacks:` and `--rank` weigh it — `level` counts past 1, WB's floor. A skill, an arsenal or the age asks for `ctx`.
def _held(actor: dict, tally: str, ctx: dict | None = None) -> int:
    if ctx is not None and tally == "age":  # as `metadata` counts it, the years a body arrived with included: the age that ranks
        return actor_age(actor, ctx["world_time"])
    if ctx is not None and tally == "crafted":  # off the items' maker, never the body's own field
        return ctx["made"][actor["id"]]
    if ctx is not None and tally not in _TALLIES:  # read off its stats, where a counter is the body's own
        return equipment_power(actor, ctx) if tally == "equipment_power" else int(compute_actor_stats(actor, ctx).get(tally, 0))
    value = int(actor.get(tally) or 0)
    return value if tally != "level" or value > 1 else 0


# A `key:value` of `--filter` read as its key takes it: an entity's id, a tally, a cause, a date, a tile, else the id or kind as said.
def _keyed(key: str, said: str) -> object:
    if key in _MEMBERSHIPS:
        if said.isdigit():
            return int(said)
        raise argparse.ArgumentTypeError(f"`{key}:{said}` — `{key}:` takes an id")
    if (choices := _TALLIES if key in ("has", "lacks") else _DEATH_CAUSES if key == "died" else None) and said not in choices:
        told = f"filters nothing{guess}" if (guess := _guessed(said, choices)) else f"— `{key}:` takes {', '.join(choices)}"  # the list only for no near one
        raise argparse.ArgumentTypeError(f"`{key}:{said}` {told}")
    if key == "born":
        return _born_arg(said)
    if key == "patch":
        return xy_arg(said)
    if key in _KEYED and not said:
        raise argparse.ArgumentTypeError(f"`{key}:` takes a value")
    if key not in _KEYED:
        raise argparse.ArgumentTypeError(f"`{key}:{said}` filters nothing{_guessed(f'{key}:', [f'{known}:' for known in (*_MEMBERSHIPS, *_KEYED)])}")
    return said


# A land as a refusal says it: `land 23`, `the islets`, `the water`.
def _land_told(land: int | str) -> str:
    return f"land {land}" if isinstance(land, int) else "the islets" if land == _ISLET else "the water"


# Lineages past `MAX_LISTED` as a count by kind, the rest read by `type:`: a census of a hundred lines tells no one which to read.
def _lineage_tally(rows: dict, typed: bool) -> dict:
    if typed or len(rows) <= MAX_LISTED:
        return rows
    kinds = Counter(row["asset_id"] for row in rows.values())
    return {"asset_id": dict(kinds), "info": f"past {MAX_LISTED} lineages, a count by kind — `--filter type:<kind>` lists each by id", "total": len(rows)}


# The lineages a span saw rise and die out: `gone` as the last save to hold them knew them, `new` as this one does, the ids no save between ever held.
def _lineages_since(save: dict, since: str, chapter: str | None, kinds: set[str] | None, minded: bool | None) -> dict:
    earlier, saves = load_save(SAVES_DIR / since / "map.wbox"), _since_saves(since, chapter, save)
    then, now, seen = _build_lineages(earlier, kinds, minded), _build_lineages(save, kinds, minded), {}
    for rows in (then, *(_build_lineages(reading, kinds, minded) for reading in saves[:-1])):  # as its last save alive knew it, one born and gone between too
        seen |= {key: row for key, row in rows.items() if row["members"]}  # WB keeps an emptied record a while: no living, no lineage
    # The lineages no save held, by the kind the register gives their dead: their mind unknown, a census by mind leaves them out
    came = passed_unseen(earlier, saves).get("subspecies") or []
    kind_of = {dead["subspecies"]: dead["asset_id"] for dead in kept_deaths(save).values()} if came else {}
    unseen = {str(lid): kind_of.get(lid) for lid in came if not kinds or kind_of.get(lid) in kinds}
    out = {
        "came_and_went": None if minded is not None else unseen,
        "gone": _lineage_tally({key: seen[key] for key in sorted(seen, key=int) if not (now.get(key) or {}).get("members")}, kinds is not None),
        "new": _lineage_tally({key: row for key, row in now.items() if key not in then and row["members"]}, kinds is not None),
    }
    return {key: value for key, value in out.items() if value}


# WB `canFallInLoveWith` between two of a kind: neither pledged to a third, no blood — parent, child or a parent shared — and opposite sexes where sexed.
def _may_mate(a: dict, b: dict, sexed: bool) -> bool:
    if a.get("lover") not in (None, b["id"]) or b.get("lover") not in (None, a["id"]):
        return False
    parents_a, parents_b = {a.get("parent_id_1"), a.get("parent_id_2")} - {None}, {b.get("parent_id_1"), b.get("parent_id_2")} - {None}
    if a["id"] in parents_b or b["id"] in parents_a or parents_a & parents_b:
        return False
    return not sexed or a.get("sex") != b.get("sex")


# The one name a leader needs, found by a scan: reading a single row beats indexing a whole collection to serve one key, even on the longest of them.
def _name_of(records: list[dict], target_id: int | None) -> str | None:
    return next((r.get("name") for r in records if r.get("id") == target_id), None)


# `--rank`'s point: a body `p<id>`, else a tile `x,y`.
def _near_arg(value: str) -> int | tuple[int, int]:
    return xy_arg(value) if (body := body_ref(value)) is None else body


# Why `roster` came back empty, told by the filters given — so an empty land never reads as a mistyped kind, and the buildings hint only where no body is that kind.
def _nobody(args: argparse.Namespace, kinds: set[str] | None, save: dict, since: str | None, told_parts: frozenset[str]) -> str:
    # The parts asked alone: `--filter moved` sought no arrival, `died:` the dead of one cause
    words = [f"died of {args.died_of}"] if args.died_of else [part for part in _SINCE_PARTS if part in told_parts]
    changed = ", ".join(words[:-1]) + f" or {words[-1]}" if len(words) > 1 else "".join(words)
    said = [
        f"bearing {args.trait}" if args.trait else None,
        ("past level 1" if args.has == "level" else f"with any {args.has}") if args.has and not since else None,
        ("at level 1" if args.lacks == "level" else f"with no {args.lacks}") if args.lacks else None,
        f"with any {args.top}" if args.top else None,
        f"wearing {args.status}" if args.status else None,
        f"at {args.task}" if args.task else None,
        f"at the {' or '.join(s for s in _LIFE_STAGES if s in args.stage)} stage" if args.stage else None,
        "that could found a town where it stands" if args.settle else None,
        "kept from founding by more than its age" if args.barred else None,
        f"born in {args.born[0]}" if args.born else None,
        "born of another" if args.bred and not since else None,
        f"on {' or '.join(map(_land_told, args.lands))}" if args.lands else None,
        f"on the patch of {args.patch[0]},{args.patch[1]}" if args.patch else None,
        *(f"of {kind} {entity_id}" for kind in _MEMBERSHIPS if (entity_id := getattr(args, kind)) is not None),
        f"working as {args.job}" if args.job else None,
        (f"whose {args.has} moved since {since}" if args.has else f"born since {since}" if args.bred else f"{changed} since {since}") if since else None,
    ]
    thinking = "thinking " if args.sapient or args.settle or args.barred else "unthinking " if args.beasts else ""
    unborn = kinds is not None and not any(a.get("asset_id") in kinds for a in save.get("actors_data") or [] if not is_boat(a))
    hint = " — a family of buildings (`trees`…) holds none, `geography … entity_types` lists the kinds" if unborn else ""
    living = "" if since else "living "  # under `--since` the dead are searched too
    return f"✗ no {living}{thinking}{args.type or 'body'} {', '.join(filter(None, said))}".rstrip() + hint


# `--rank`'s figure of a body: a counter, the age or the work as `_held` weighs them, a kept figure as `--with` reads it, else one of its stats.
def _rank_figure(actor: dict, top: str, ctx: dict, seen: set[str]) -> float:
    if top in _TOP_MEASURES:
        return _held(actor, top, ctx)
    if top in _RANKED_KEPT:
        return _asked_fields(actor, "", [top], ctx, seen)[top] or 0
    stats = body_stats(actor, ctx)
    seen.update(stats)
    return stats.get(top, 0)


# A field of `--with` that no body of the roll carries, refused with the nearest it could take: mistyped, or no lineage here bears it.
def _refuse_unseen(fields: list[str], seen: set[str]) -> None:
    if unknown := [field for field in fields if field not in seen]:
        known = sorted(seen)
        guess = "".join(_guessed(field, known) for field in unknown)
        raise ValueError(
            f"✗ {', '.join(f'`{f}`' for f in unknown)}: no `--with` field, nor a stat a body here carries{guess} — `gloss world.--with`, `actor <id> stats`"
        )


# The subspecies WB hangs `has_sapience` on, as a set of ids — an allegiance is not a mind, and a world can think long before it crowns anyone.
def _sapient_subspecies(save: dict) -> frozenset:
    return frozenset(sid for sid, sub in index_by_id(save.get("subspecies") or []).items() if is_sapient(sub))


# Whoever holds the composite's first place, `{id, name}` alone: a Borda total climbs with every rival, so the points never travel.
def _score_leaders(totals: Counter, records: list[dict]) -> list[dict]:
    field = {r["id"]: totals[r["id"]] for r in records}  # every town or crown a rival, the ones `score_totals` credits nothing included
    return [{"id": eid, "name": _name_of(records, eid)} for eid, _ in first_place(field, MIN_SCORE_PEERS)]


# The saves after `since` up to this one: a body a chapter in between held was seen, and is gone rather than passed unseen.
def _since_saves(since: str, chapter: str | None, save: dict) -> list[dict]:
    later = [SAVES_DIR / f"C{n}" / "map.wbox" for n in range(int(since[1:]) + 1, int(chapter[1:]) if chapter else latest_chapter() + 1)]
    return [*(load_save(path) for path in later if path.exists()), save]


# A body's stage off its raw span alone, as `surroundings` reads one: a roster line and a census say it alike.
def _stage(actor: dict, ctx: dict, age: int, adult: float) -> str:
    return life_stage(age, adult, body_lifespan(actor, ctx), is_egg(actor, ctx))


# Where a body stands as `roster` tells it: its land, else `water` where it floats and `islet` on an islet too small to count, as `surroundings` splits them.
def _standing(actor: dict, island_of: TileIslands, grid: LazyTileGrid, names: list[str]) -> int | str:
    x, y = actor_xy(actor)
    if (land := island_of.get((x, y))) is not None:
        return land
    return _WATER if off_land(names[grid[y][x]]) == "water" else _ISLET


# An earlier chapter's save for `--since`, and the land each body stood on in it: what the roster weighs against it, the dead read off it alone.
def _then(chapter: str) -> tuple[dict, dict[int, int | str]]:
    then_path = SAVES_DIR / chapter / "map.wbox"
    then = load_save(then_path)
    island_of, grid = compute_islands_cached(then, then_path)[1], LazyTileGrid(then)
    return then, {actor["id"]: _standing(actor, island_of, grid, then["tileMap"]) for actor in then.get("actors_data") or [] if not is_boat(actor)}


# A body's tie to one entity: a pact through its crown, every other by its own field — `fallen` given under `king` alone, a king to his realm.
def _tie(save: dict, kind: str, entity_id: int | str, fallen: dict[int, int]) -> Callable[[dict], bool]:
    if kind == "job":  # a trade, the crown and an army's lead among them
        if fallen:
            return lambda actor: resolve_profession(actor, save) == entity_id or actor["id"] in fallen
        return lambda actor: resolve_profession(actor, save) == entity_id
    if kind == "alliance":
        crowns = {kid for pact in save.get("alliances") or [] if pact.get("id") == entity_id for kid in pact.get("kingdoms") or []}
        return lambda actor: actor.get("civ_kingdom_id") in crowns
    field = _MEMBERSHIPS[kind][1]
    if kind == "kingdom" and fallen:
        return lambda actor: actor.get(field) == entity_id or fallen.get(actor["id"]) == entity_id
    return lambda actor: actor.get(field) == entity_id


# How far a cut of `size` runs on a list ranked by `figures`: past it while the last place is shared, which a cut would split.
def _tied_cut(figures: list, size: int) -> int:
    kept = min(size, len(figures))
    while kept < len(figures) and figures[kept] == figures[kept - 1]:
        kept += 1
    return kept


def main(argv: list[str]) -> int:
    try:
        since, argv = take_since(argv)
    except ValueError as e:
        print(f"✗ {e}", file=sys.stderr)
        return 2
    save_path, argv, chapter = take_chapter(argv)
    parser = arg_parser(prog="world/info.py", taken="[--since C<n>] [C<n>]")
    parser.add_argument("sections", nargs="?")
    parser.add_argument("--filter", action="append", type=_filter_arg, metavar="word|key:value,…")  # repeated, each narrows further
    parser.add_argument("--limit", type=limit_arg, metavar="n|all")
    parser.add_argument("--rank", dest="top", metavar="measure|x,y|p<id>")
    parser.add_argument(
        "--with",
        action="append",  # repeated, each adds its fields: a second never drops the first unheard
        dest="fields",
        metavar="field,…",
    )
    args = parser.parse_args(argv)
    picked: defaultdict[str, frozenset] = defaultdict(frozenset)
    for taken in args.filter or ():
        for group, words in taken.items():
            picked[group] |= words
    singles = (*_MEMBERSHIPS, "born", "died", "has", "job", "lacks", "patch", "status", "task", "trait")  # one each: a second would ask another roll
    if several := next((key for key in singles if len(picked[key]) > 1), None):
        print(f"✗ {several}: one at a time — ask each apart", file=sys.stderr)
        return 2
    for kind in _MEMBERSHIPS:
        setattr(args, kind, next(iter(picked[kind]), None))
    args.born, args.died_of, args.has, args.job, args.lacks, args.patch, args.status, args.task, args.trait = (
        next(iter(picked[key]), None) for key in ("born", "died", "has", "job", "lacks", "patch", "status", "task", "trait")
    )
    args.type = ",".join(sorted(picked["type"])) or None  # kinds add up, as `asset_kinds` reads a comma list
    if halves := next((words for group in ("mind", "founding") if len(words := picked[group]) > 1), None):  # two halves of one split name no one
        print(f"✗ {' and '.join(sorted(halves))} split the bodies in two: filter by one", file=sys.stderr)
        return 2
    asked_parts = picked["since"] or None
    # A part or a cause asked with no span: since the chapter before the one read, as a chapter is written against its last — said once the call holds
    previous = int(chapter[1:]) - 1 if chapter else 0
    if defaulted := bool(asked_parts or args.died_of) and not since and previous > 0:
        since = f"C{previous}"
    if asked_parts and not since:  # a part is what befell a body since a chapter
        print(f"✗ {', '.join(sorted(asked_parts))}: parts of `--since C<n>` — name a chapter", file=sys.stderr)
        return 2
    mind, founding = picked["mind"], picked["founding"]
    args.sapient, args.beasts, args.settle, args.barred = "sapient" in mind, "beasts" in mind, "settle" in founding, "barred" in founding
    args.bred, args.stage = "bred" in picked["birth"], picked["stage"] or None
    args.lands = picked["land"] or None
    if args.died_of and not since:  # a cause is a dead body's, and the register files the dead of a span
        print("✗ `died:` sorts the dead of `--since`: name a chapter", file=sys.stderr)
        return 2
    if args.died_of and (living := sorted((asked_parts or set()) - {"died"})):  # a cause is no arrival's nor mover's
        print(f"✗ `died:` sorts the dead: {', '.join(living)} holds none — ask `died` alone", file=sys.stderr)
        return 2
    # `grew` untold unless named, or a stage sought; the dead alone under `died:`
    told_parts = frozenset({"died"}) if args.died_of else asked_parts or frozenset({"arrived", "died", "left", "moved", *(["grew"] if args.stage else [])})
    point = None  # `--rank` by a figure, highest first, or by a body or a tile, nearest first: a word not a point is a field, refused if none
    if args.top and args.top not in _TOP_MEASURES:
        with contextlib.suppress(argparse.ArgumentTypeError):
            point, args.top = _near_arg(args.top), None
    if args.top in _KEPT_FIELDS and args.top not in (*_RANKED_KEPT, *_TOP_MEASURES):
        print(f"✗ `{args.top}` is no figure to rank — `--with {args.top}` shows it on each line", file=sys.stderr)
        return 2
    limit = _LIMIT if args.limit is None else args.limit or None  # `all` read as 0: every line
    requested = args.sections
    try:
        sections = parse_sections(requested, (*_ALL_SECTIONS, *_ON_REQUEST), full=_ALL_SECTIONS)
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 2
    entities = [(kind, entity_id) for kind in _MEMBERSHIPS if (entity_id := getattr(args, kind)) is not None] + ([("job", args.job)] if args.job else [])
    if not entities:  # none to leave: `left` refused if named, else dropped from the default parts
        if "left" in (asked_parts or ()):
            print("✗ `left` is an entity's: name one — `city:<id>`, `family:<id>`, `king`…", file=sys.stderr)
            return 2
        told_parts -= {"left"}
    # What keeps only some bodies of the roll: `type:` among them, though it narrows `lineages` too, and `--with` none — it adds fields to every line
    sifted = (
        any((args.barred, args.born, args.bred, args.has, args.lacks, args.patch, args.settle, args.stage, args.status, args.task, args.top, args.trait))
        or asked_parts is not None
        or args.died_of is not None
        or bool(entities)
        or args.lands is not None
        or point is not None
    )
    minded = True if args.sapient else False if args.beasts else None  # a roll's bodies split by mind, or a census's lineages
    limited = args.limit is not None and "pairings" not in sections  # `--limit` cuts `pairings` too
    narrowing = sifted or ((minded is not None or args.type) and not {"lineages", "pairings"} & set(sections)) or args.fields is not None or limited
    if args.beasts and (other := next((flag for flag in ("settle", "barred") if getattr(args, flag)), None)):  # a founding is a thinker's alone
        print(f"✗ beasts and {other} split the bodies in two: filter by one", file=sys.stderr)
        return 2
    if narrowing and "roster" not in sections:  # refused before the save is read, as a flag that would go unheard
        print("✗ --filter, --rank, --limit, --with narrow `roster` — `type:`, `sapient` and `beasts` `lineages` and `pairings` too: name it", file=sys.stderr)
        return 2
    if args.has and args.lacks:  # the two halves of a roll by one tally: together they name no one
        print("✗ has: and lacks: split a roll in two: filter by one", file=sys.stderr)
        return 2
    if args.top and since:  # a measure read off its own chapter
        print(f"✗ `--rank` ranks one chapter: read the other by its suffix, `{since}`", file=sys.stderr)
        return 2
    if since and (alone := next((flag for flag in ("lacks", "patch", "status", "task") if getattr(args, flag)), None)):
        print(f"✗ `{alone}:` reads one chapter: ask `--since` apart", file=sys.stderr)  # the dead stood, wore and did what no later save tells
        return 2
    # `--since` narrows a roll and weighs two counts: any other section would say a chapter's state as if it were a change
    if since and (unweighed := [section for section in sections if section not in _SINCE_SECTIONS]):
        print(f"✗ {', '.join(unweighed)}: `--since` takes {', '.join(_SINCE_SECTIONS)} alone — name them", file=sys.stderr)
        return 2
    if since and not (SAVES_DIR / since / "map.wbox").exists():
        print(f"✗ no save for {since}", file=sys.stderr)
        return 2
    save = load_save(save_path)
    map_stats = save.get("mapStats") or {}  # WB's own counters, period-accurate.
    out: dict = {}
    families = asset_families(save) if args.type else {}  # swept for `type:` alone, once for every section it narrows: every body and every building
    bred = asset_kinds(families, args.type) if args.type else None
    if "boats" in sections:
        out["boats"] = _build_boats(save, requested)
    if "cumulative" in sections:
        out["cumulative"] = _build_cumulative(save)
    if "laws" in sections:
        out["laws"] = _build_laws(save)
    if "leaders" in sections:
        out["leaders"] = _build_leaders(save)
    if "lineages" in sections:
        of = f" of {args.type}" if args.type else ""
        if since:
            lineages = _lineages_since(save, since, chapter, bred, minded)
            if not lineages:
                print(f"✗ no lineage{of} came or went since {since}", file=sys.stderr)
                return 1
        elif not (lineages := _build_lineages(save, bred, minded)):
            # A mistyped word told apart from a kind with no lineage left, as `roster` tells it
            print(f"✗ {(args.type and unsited_reason(families, args.type)) or f'no living lineage{of} in this world'}", file=sys.stderr)
            return 1
        if not since:  # the census, and how its lineages breed — by ids as its rows, counted where they are: `type:` and `sapient` narrow both
            tally = _lineage_tally(lineages, bred is not None)
            lineages = {**tally, "reproduction": _breedings(save, lineages, counted=tally is not lineages)}
        out["lineages"] = lineages
    if "metadata" in sections:
        out["metadata"] = _build_metadata(map_stats)
    if "pairings" in sections:
        thinking = _sapient_subspecies(save) if minded is not None else frozenset()
        minds = {a.get("asset_id") for a in save.get("actors_data") or [] if a.get("subspecies") in thinking}
        pairings = [
            row for row in _build_pairings(save, save_path) if (bred is None or row["asset_id"] in bred) and (minded is None or (row["asset_id"] in minds) == minded)
        ]
        if not pairings:
            kind = args.type or ("thinking kind" if minded else "beast kind" if minded is False else "kind")
            print(f"✗ {(args.type and unsited_reason(families, args.type)) or f'no {kind} to pair in this world'}", file=sys.stderr)
            return 1
        if limit is not None and len(pairings) > limit:  # the soonest births, as `roster` cuts its roll: the rest said beside
            print(f"⚠ {len(pairings)} kinds, the first {limit} by birth — `--limit all` for every one", file=sys.stderr)
        out["pairings"] = pairings[:limit]
    if "plots" in sections:
        out["plots"] = _build_plots(save)
    if "roster" in sections:
        kinds, later = bred, _since_saves(since, chapter, save) if since else []  # the saves after `since`, read once: the dead as each last stood
        counted, island_of = compute_islands_cached(save, save_path)  # loaded once: the lands named are checked against the lookup the roll then reads
        if unknown := sorted(set(args.lands or ()) - {each["id"] for each in counted} - {_ISLET, _WATER}):
            print(f"✗ no land {', '.join(map(str, unknown))} — `geography … islands` lists them", file=sys.stderr)
            return 2
        stray = args.trait and args.trait not in load_data("creature-traits.json") and args.trait not in load_data("subspecies-traits.json")
        # What this world wears, swept only where a refusal may need it: a trait that is one costs the roll nothing more.
        worn = sorted({status for actor in save.get("actors_data") or [] for status in kept_statuses(actor) or ()}) if args.status or stray else []
        if stray:
            # A status asked as a trait is sent to its own filter: `cursed` reads like one, and the plain refusal would leave no way on.
            hint = f"it is a status: `status:{args.trait}`" if args.trait in worn else "`actor <id> traits` and `subspecies <id> traits` give the ids"
            print(f"✗ `{args.trait}` is no trait of the game, of a body or of a lineage — {hint}", file=sys.stderr)
            return 2
        if args.status and args.status not in worn:  # refused by what this world wears: WB's whole list would not tell a mistyped id from an idle one
            print(f"✗ no body wears {args.status} — worn here: {', '.join(worn) or 'no status at all'}", file=sys.stderr)
            return 2
        if args.task and args.task not in (done := sorted(set(filter(None, map(kept_task, save.get("actors_data") or []))))):
            print(f"✗ no body is at {args.task} — tasks here: {', '.join(done) or 'none kept in this save'}", file=sys.stderr)
            return 2
        for kind, entity_id in entities:
            if kind != "job" and entity_id not in {record.get("id") for record in save.get(_MEMBERSHIPS[kind][0]) or []}:
                # An army has no tool of its own to send the refusal to: a town's names it, where `absent_entity` would point at an `army/info.py`.
                army = f"✗ no army {entity_id} here — `city/info.py <id> army` gives a town's"
                print(army if kind == "army" else absent_entity(kind, _MEMBERSHIPS[kind][0], entity_id, chapter), file=sys.stderr)
                return 1
        near = None
        if isinstance(point, tuple):
            near = point, None
        elif point is not None:
            if (body := next((a for a in save.get("actors_data") or [] if a["id"] == point and not is_boat(a)), None)) is None:
                print(absent_entity("actor", "actors_data", point, chapter, lambda a: not is_boat(a)), file=sys.stderr)
                return 1
            near = actor_xy(body), point
        patch = None
        if args.patch:
            if island_of.get(args.patch) is None:  # off the map as on the water: a patch is one ground of one counted land
                print(f"✗ {args.patch[0]},{args.patch[1]} stands on no counted land — `tiles <x,y> tile_info` tells what a tile is", file=sys.stderr)
                return 2
            patch = patch_finder(save, LazyTileGrid(save), island_of)(*args.patch)[0]
        fields = list(dict.fromkeys(",".join(args.fields).split(","))) if args.fields else []
        if len(fields) > _MAX_FIELDS:
            print(f"✗ `--with` takes {_MAX_FIELDS} fields at most — `actor <id> stats` gives a body's whole sheet", file=sys.stderr)
            return 2
        if defaulted:  # a span unseen, said beside a roll it shapes — never before a refusal
            print(f"⚠ since {since}, the chapter before {chapter} — `--since C<n>` for another", file=sys.stderr)
        try:
            roster = _build_roster(
                save,
                save_path,
                island_of,
                kinds,
                args.trait,
                args.lands,
                since,
                later,
                True if args.sapient else False if args.beasts else None,
                args.settle,
                args.barred,
                args.bred,
                patch,
                args.status,
                args.task,
                args.has,
                args.lacks,
                args.top,
                limit,
                entities,
                near,
                fields,
                args.stage,
                args.born,
                told_parts,
                args.died_of,
            )
        except ValueError as e:  # a field `--with` asks that no body of the roll carries
            print(e, file=sys.stderr)
            return 1
        if not roster:  # a filter nothing answers, never a silent `{}`
            print(_nobody(args, kinds, save, since, told_parts), file=sys.stderr)
            return 1
        out["roster"] = roster
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
            since_then = _since_saves(since, chapter, save)
            out["cumulative"]["came_and_went"] = passed_unseen(then, since_then) or None
        if not out:
            print(f"✗ nothing moved in {', '.join(counted)} since {since}", file=sys.stderr)
            return 1

    emit(out)
    return 0


if __name__ == "__main__":
    sys.exit(run(main))
