#!/usr/bin/env python3

# Emits the world sections from the save alone (`mapStats` = WB's period-accurate counters); the chapter's registries are built by
# `chapter/registries.py` (the bootstrap), not here. User-facing docs — usage and sections — live in `docs/tools.md`.
#
# ⚠️ Output keys must stay self-descriptive (chronicler reads them with no other context). Prefer disambiguated names (e.g. `wild_creatures` over `creatures`).
# Exception: WB-native names kept verbatim for raw-save fields (e.g. `asset_id`) — the tools' default, a rename having to earn its churn across py, UI and data.

import re
import sys
from collections import Counter, defaultdict
from functools import cache
from math import floor, inf
from operator import itemgetter
from pathlib import Path
from statistics import median
lazy import argparse
lazy from collections.abc import Callable, Mapping

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
from founding import city_zones, settle_gates, settle_rank, settle_told
from grid import LazyTileGrid, frozen_tally, off_land, patch_finder
from islands import TileIslands, compute_islands_cached
from places import PlaceIndex
from shared import (
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
    arg_parser,
    asset_families,
    asset_kinds,
    biome_lore,
    body_ref,
    breeding_mode,
    building_family,
    children_by_id,
    city_centre,
    city_score_dimensions,
    civic_building_ids,
    counted_birth,
    death_causes,
    emit,
    entity_born,
    entity_ref,
    fertile,
    first_place,
    i18n,
    index_by_id,
    is_aboard,
    is_boat,
    is_sapient,
    kept_army_since,
    kept_city_since,
    kingdom_score_dimensions,
    land_arg,
    life_stage,
    light,
    load_data,
    load_save,
    moved_between,
    needs_food,
    parse_sections,
    passed_unseen,
    quiet_zeros,
    resolve_profession,
    rounded_world_time,
    score_totals,
    sex_label,
    spores_unfed,
    take_chapter,
    take_since,
    under_construction,
    unranked,
    unsited_reason,
    walk_tiles,
    wants_detail,
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
    "metamorphosis": "metamorphosis",
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

# Chronicler key => WB save field: its « Deaths » rows less « Other », never written, plus the Grin Reaper's it omits; `water` is hydrophobic damage, not `drowning`.
_DEATH_CAUSES = {
    "acid": "deaths_acid",
    "divine": "deaths_divine",
    "drowning": "deaths_drowning",
    "eaten": "deaths_eaten",
    "explosion": "deaths_explosion",
    "fire": "deaths_fire",
    "gravity": "deaths_gravity",
    "grin_reaper": "deaths_smile",
    "hunger": "deaths_hunger",
    "infection": "deaths_infection",
    "old_age": "deaths_age",
    "plague": "deaths_plague",
    "poison": "deaths_poison",
    "tumor": "deaths_tumor",
    "water": "deaths_water",
    "weapon": "deaths_weapon",
}

_FEATS = ("kills", "level", "money", "renown")  # what a life adds up, kept on the body itself — weighed among thinking souls as the skills are
_FIELD_FLOORS = {"births": 0, "equipment_power": 0, "kills": 0, "level": 1, "loot": 0, "money": 0, "renown": 0}  # a tally `actor … stats` tells silent at its floor
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
    "age_overgrowth",
    "asset_id",
    "born",
    "breeds_on",
    "city_since",
    "gen",
    "hatch_on",
    "island_id",
    "life_stage",
    "place",
    "sex",
    "statuses",
    "subspecies",
    "task",
    "x",
    "y",
)

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

_ON_REQUEST = ("laws", "lineages", "pairings", "roster")  # named only: `full` is what the bootstrap folds into a chapter, and a roll is no chapter's to carry
_SEXED = "reproduction_sexual"  # the one breeding WB pairs by opposite sexes: a hermaphrodite takes any partner of its kind
_SINCE_SECTIONS = ("cumulative", "roster", "snapshot")  # what `--since` answers: the arrivals of a roll, and two counts weighed chapter against chapter

# WB's four skills, the ones every `ranks_in_species` podium reads — civic abilities, weighed among thinking souls alone: a beast's figure moves nothing.
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
_TALLIES = ("births", "kills", "level", "loot", "money", "renown")  # what `--has` and `--lacks` weigh: a body's own counters, named as `actor … stats` names them
_TOP_MEASURES = tuple(sorted((*_SKILLS, *_TALLIES, "equipment_power")))  # what `--top` ranks by: those counters, a skill, an arsenal
_TOP_ROWS = 10  # a ranking is asked for its head: who comes first, second, third — the rest is counted
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
        "age_overgrowth": lambda: int(actor.get("age_overgrowth") or 0) or None,  # a migrant's mark, `born` its arrival
        "asset_id": lambda: actor.get("asset_id"),
        "born": lambda: entity_born(actor),
        # Its lineage's own line, as on the roll: none to come where it never bears
        "breeds_on": lambda: crossed_on(actor, breeding) if age < (breeding := breeding_age(actor, ctx)) and fertile(lineage) else None,
        "city_since": lambda: kept_city_since(actor),
        "gen": lambda: int(actor.get("generation") or 1),
        "hatch_on": lambda: hatch_on(actor, ctx),
        "island_id": lambda: here,
        "life_stage": lambda: _stage(actor, ctx, age, adult_age(actor, ctx)),
        "place": lambda: ctx["place_index"].at(*actor_xy(actor)),
        "sex": lambda: sex_label(actor),
        "statuses": lambda: kept_statuses(actor),
        "subspecies": lambda: actor.get("subspecies"),
        "task": lambda: kept_task(actor),
        "x": lambda: actor_xy(actor)[0],
        "y": lambda: actor_xy(actor)[1],
    }
    return {field: kept[field]() if field in kept else stats.get(field, _FIELD_FLOORS.get(field)) for field in fields}


# Whether a body belongs to the entity `roster` is narrowed to, read off the body itself: a pact through its crown, every other tie by its own field.
def _belongs(save: dict, entity: tuple[str, int] | None) -> Callable[[dict], bool]:
    if entity is None:
        return lambda _actor: True
    kind, entity_id = entity
    if kind == "alliance":
        crowns = {kid for pact in save.get("alliances") or [] if pact.get("id") == entity_id for kid in pact.get("kingdoms") or []}
        return lambda actor: actor.get("civ_kingdom_id") in crowns
    field = _MEMBERSHIPS[kind][1]
    return lambda actor: actor.get(field) == entity_id


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
    # WB `Actor.countDeath` counts a metamorphosis as a death and files `Other`, `AshFever` and `None` under no cause: what the causes leave of the true deaths.
    if (unknown := int(map_stats.get("deaths") or 0) - out.get("metamorphosis", 0) - sum(out["deaths"].values())) > 0:
        out["deaths"]["unknown"] = unknown
    return out


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


# Every living lineage by its id, a line each as `subspecies … metadata` tells it: its kind, name, members, the biome that shaped it, its month — `-t` narrows.
def _build_lineages(save: dict, kinds: set[str] | None) -> dict:
    members = Counter(actor.get("subspecies") for actor in save.get("actors_data") or [] if not is_boat(actor))
    rows = {}
    for lineage in sorted(save.get("subspecies") or [], key=lambda s: s["id"]):
        if kinds is not None and lineage.get("species_id") not in kinds:
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


# The world's day and its age — how far that age has run, never when it ends: WB's UI counts the moons left, and a chronicle told the month would foretell it.
def _build_metadata(map_stats: dict) -> dict:
    age_id = map_stats.get("world_age_id") or ""
    age = load_data("world-ages.json").get(age_id) or {}
    key = age_id.removeprefix("age_")  # `WorldAgeLibrary` key without WB's prefix — `hope`, as the panel keys its French and its icon
    world_time = rounded_world_time(map_stats)
    return {
        "age_description": age.get("description"),  # Chronicler-only: WB's English line on the age, one per chapter
        "age_id": key,
        # Chronicler-only: the age as the chronicle names it, said here so nobody opens `i18n/<lang>/ages.json`, where every age to come is listed. Else WB's title.
        "age_name": i18n("ages.json").get(key) or age.get("name"),
        # Chronicler-only: an age's own life stage, off the share of its span the save says it has run. Absent where no age runs: WB then stores no span.
        "age_stage": _age_stage(float(map_stats.get("current_age_progress") or 0)) if float(map_stats.get("current_world_ages_duration") or 0) > 0 else None,
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
        # Lovers first, WB never parting them for another; then a pair nothing bars; then the earliest, the nearest — its bars said, never hidden.
        best = min(
            (
                (
                    a.get("lover") != b["id"],
                    bool(barred := sorted(bars[a["id"]] | bars[b["id"]] | barred_by_law)),
                    max(ready[a["id"]], ready[b["id"]]),
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
                "barred": barred or None,
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
        # A birth under way, as the save keeps it: its date is the game's own, and it leads whatever a pair could still conceive.
        if carrying := {actor["id"]: left for actor in bodies if (left := max(status_left(actor, status) or 0 for status in _CARRYING))}:
            row["pregnant"] = sorted(carrying)
            births += [now + left for left in carrying.values()]
        if births:
            row["birth_on"] = min(births)
        rows.append((row.get("birth_on", inf), row))  # the first birth leads: what the chronicle asks is when a body is born, not when two come of age

    for _, row in rows:  # the hours dated only once sorted on: `now` for what already holds
        for key in ("alone_on", "birth_on", "mates_on"):
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
    land: int | str | None,
    since: str | None,
    sapient: bool | None,
    settle: bool,
    barred: bool,
    patch: set[tuple[int, int]] | None,
    status: str | None,
    task: str | None,
    has: str | None,
    lacks: str | None,
    top: str | None,
    entity: tuple[str, int] | None,
    near: tuple[tuple[int, int], int | None] | None,
    fields: list[str],
) -> list[dict] | dict:
    earlier, was = _then(since) if since else (None, None)
    belongs = _belongs(save, entity)
    belonged = _belongs(earlier, entity) if earlier is not None else belongs  # the same tie read off the earlier save, a pact's crowns as they stood
    # Under an entity, `--since` weighs who belonged then: a body that joined arrives, one alive elsewhere has left, though the world saw both all along.
    members_then = {a["id"] for a in earlier.get("actors_data") or [] if belonged(a)} if entity and earlier is not None else None
    known = was if members_then is None else members_then
    weighed = has or lacks or top  # one measure each: `--has` keeps whoever holds any, `--lacks` whoever holds none, `--top` the highest alone
    thinking = _sapient_subspecies(save) if sapient is not None else None  # `--sapient` keeps the minds, `--beasts` the rest
    grid = LazyTileGrid(save)  # rows decoded as read: a body off every land alone asks its tile
    asked = _ISLET if land == "islets" else land  # `-i islets` names the islets as a body stands on one, `islet`
    if patch and land is None:
        asked = island_of.get(next(iter(patch)))  # a patch lies on one land, which then goes unsaid as `-i`'s does
    ctx = build_actor_stats_context(save)
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

    # A trait is a body's own or its lineage's: `gift_of_thunder` is born with a whole line, `fire_blood` with one body — `--trait` finds either.
    bearing = {sub["id"] for sub in save.get("subspecies") or [] if trait in (sub.get("saved_traits") or ())} if trait else set()

    # Under `--since`, a tally is weighed against what the body held then: only one that moved is told, as a pair — `level` from its floor, never from 0.
    once = {a["id"]: _held(a, has) for a in earlier.get("actors_data") or []} if has and earlier is not None else None

    floor = 1 if has == "level" else 0
    bodies, still, unranked = [], 0, 0

    (nx, ny), near_id = near or ((0, 0), None)
    far: dict[int, float] = {}  # each body's unrounded length, ranked on: two read alike may still stand apart
    for actor in save.get("actors_data") or []:
        if near and actor["id"] == near_id:  # the body ranked around stands nearest to itself
            continue
        borne = not trait or trait in (actor.get("saved_traits") or ()) or actor.get("subspecies") in bearing
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
        held = _held(actor, weighed, ctx) if weighed else 0
        before = once.get(actor["id"], 0) if once is not None else 0  # with no `--since`, a tally is weighed against nought
        if (has and held == before) or (lacks and held):  # `--top` counts a body with none once every other filter has had its say
            continue
        gates = settle_gates(actor, ctx) if settle or barred else None
        if settle and gates not in (True, ["child"]):  # founds where it stands once grown: nothing, or its youth alone, bars it
            continue
        if barred and (gates is None or gates in (True, ["child"])):  # a thinker something besides its youth keeps from founding
            continue
        here = _standing(actor, island_of, grid, save["tileMap"])
        change: dict = {weighed: held if once is None else [max(before, floor), max(held, floor)]} if has or top else {}
        if near:
            x, y = actor_xy(actor)
            far[actor["id"]] = walk_tiles(x - nx, y - ny)
            change["crow_tiles"] = round(far[actor["id"]])
        if was is not None and actor["id"] in known and not has:  # one unseen then was born or set down since, and says so by standing in the roll at all
            if (then := was[actor["id"]]) == here:
                still += land is None or asked == here  # stood still: nothing for `since` to say of it, but that it was left out
                continue
            change = {"was_on": then}
        if land is None or asked in (here, change.get("was_on")):
            if top and held == before:  # holds none of the measure: left out of the ranking, and said so
                unranked += 1
            else:
                bodies.append((actor, here, change | (settle_told(gates) if barred else {})))
    gone = []

    if earlier is not None and was is not None and not (settle or barred):  # the dead found nothing
        gone = _gone_since(save, earlier, was, kinds, trait, asked, sapient, belonged)
        if once is not None:  # the dead that held the tally, each with what it takes away: where it stood and what took it are another question's
            gone = [{**row, has: once[row["id"]], "old_from": None, "was_on": None} for row in gone if once.get(row["id"])]

    one_kind = kinds is not None and len(kinds) == 1  # a lone `-t` names the kind, as `-i` the land
    seen = set(_KEPT_FIELDS) | _FIELD_FLOORS.keys() if fields else set()  # every field a body of the roll can be asked, its own stats added as they come
    if fields:
        ctx["children_by_parent"] = children_by_id(save)  # `body_stats` counts each body's children as `actor` does
    if not (top or near) and len(bodies) + len(gone) > MAX_LISTED:  # past the list a count, its parts what `--with` asks
        told = f"{len(bodies)} bodies"
        if once is not None:
            told = f"{len(bodies)} bodies whose {has} moved since {since}" + (f", {len(gone)} gone with theirs" if gone else "")
        elif since:  # the roll then holds what changed alone: told by its parts, lest its total read as the world's
            moved = sum("was_on" in change for _, _, change in bodies)
            parts = ((len(bodies) - moved, "arrived"), (moved, "moved"), (len(gone), "gone"))
            told = f"{', '.join(f'{n} {word}' for n, word in parts if n)} since {since}" + (f" — {still} stood still, left out" if still else "")
        few = len(gone) <= MAX_LISTED
        wanted = [_asked_fields(actor, here, fields, ctx, seen) for actor, here, _ in bodies]  # `--with` grouped over the roll, its lines too many to read
        _refuse_unseen(fields, seen)
        return {
            # Named while they are few, each side of a `--since` keeping its own list: it is the arrivals that crowd a census out, and the dead a chapter seeks.
            "gone": [{**row, "asset_id": None if one_kind else row["asset_id"], "gone": None} for row in gone] if few else None,
            "gone_by_species": None if few else dict(Counter(row["asset_id"] for row in gone)),
            "info": told,  # the counts alone: what a cut roll is and how to narrow it are glossed (`gloss roster.info`)
            "with": {field: _grouped_field(field, [w.get(field) for w in wanted]) for field in fields} or None,
        }
    rows = []

    # Land by land, off every land last — the founders by who founds first, the barred by the gate told
    def order(body: tuple[dict, int | str, dict]) -> tuple:
        if near:
            return far[body[0]["id"]], body[0]["id"]
        if barred:  # the steadiest kind first, then who comes nearest to passing it
            return settle_rank(body[2]["settle"]), body[0]["id"]
        if settle:  # the grown first, whose youth is past, then by the date each comes of age
            return crossed_at(body[0], adult_age(body[0], ctx)), body[0]["id"]
        if has or top:  # the measure asked, highest first — its latest figure under `--since`: whoever stands in no line has none, or has not moved
            return -(body[2][weighed] if once is None else body[2][weighed][1]), body[0]["id"]
        if entity:  # its members eldest first, as each entity's own list ran
            return -actor_age(body[0], ctx["world_time"]), body[0]["id"]
        return isinstance(body[1], str), body[1], body[0]["id"]

    lineages = ctx["subspecies_by_id"]
    # Unsaid where a view never reads it — `--barred`'s gates, a measure's figure, a distance, `--since`'s blocks — whose lines it would push past inline
    breeds_said = not (barred or has or top or near or since)
    ranked = sorted(bodies, key=order)
    refs = {"city": index_by_id(save.get("cities") or []), "family": index_by_id(save.get("families") or [])} if entity else {}
    # A town's own land goes unsaid on its residents' lines, as `-i` does: the room it frees tells their stage instead
    seat = island_of.get(centre) if entity and entity[0] == "city" and (centre := city_centre(refs["city"].get(entity[1]) or {})) else None
    for actor, here, change in ranked[:_TOP_ROWS] if top or near else ranked:
        if fields:  # the line is what was asked: who, and those fields, a filter's own figure kept — the default columns stay with the plain roll
            rows.append({"id": actor["id"], "name": actor.get("name"), **change, **_asked_fields(actor, here, fields, ctx, seen)})
            continue
        if entity:
            told = None if here in (asked, seat) and "was_on" not in change else here
            rows.append({**_member_row(actor, entity[0], told, refs, save, ctx, one_kind), **change})
            continue
        age, adult, breeding = actor_age(actor, ctx["world_time"]), adult_age(actor, ctx), breeding_age(actor, ctx)
        stage = _stage(actor, ctx, age, adult)
        rows.append(
            {
                "adult_on": crossed_on(actor, adult) if age < adult and not near else None,  # beside a distance, `life_stage` tells the youth
                "asset_id": None if one_kind else actor.get("asset_id"),
                "breeds_on": crossed_on(actor, breeding) if breeds_said and age < breeding and fertile(lineages.get(actor.get("subspecies"))) else None,
                "id": actor["id"],
                # Said outright beside a `was_on`, a missing one reading as still on the land left; silent where `-i` already named it
                "island_id": None if here == asked and "was_on" not in change else here,
                # Silent at `adult`, as in `surroundings`, and under `--barred`: on every line it would push the longest past inline
                "life_stage": None if stage == "adult" or barred else stage,
                "name": actor.get("name"),
                "sex": None if barred else sex_label(actor),  # founding asks no mate: under `--barred`, `adult_on` alone says what the youth waits for
                **change,
            }
        )
    _refuse_unseen(fields, seen)

    if (top or near) and rows:  # one shape whatever the world, its `info` keeping a lone key from coming bare: the cut said, a tie it falls in, and who holds none
        key = top or "crow_tiles"
        if len(ranked) <= _TOP_ROWS:
            told = f"all {len(ranked)} by {top}, none cut" if top else f"all {len(ranked)}, nearest first, none cut"
        else:
            tied = sum(body[2][key] == ranked[_TOP_ROWS - 1][2][key] for body in ranked[_TOP_ROWS:])  # a tenth place shared would read as one body's own
            told = f"{_TOP_ROWS} highest of {len(ranked)} by {top}" if top else f"{_TOP_ROWS} nearest of {len(ranked)}"
            told += f" — {tied} more share the last figure" if tied else ""
        return {"info": told + (f"; {unranked} with no {top}, left out" if unranked else ""), "roster": rows}

    gone = [{**row, "asset_id": None if one_kind else row["asset_id"]} for row in gone]
    if since and not has:  # each body filed by what befell it, the block saying it: an arrival bears no mark of its own, read off the others it would be guessed
        parts = {"arrived": [r for r in rows if "was_on" not in r], "gone": [{**r, "gone": None} for r in gone], "moved": [r for r in rows if "was_on" in r]}
        if members_then is not None and entity:  # alive and elsewhere now: left the entity, which a death alone does not say
            leavers = sorted((a for a in save.get("actors_data") or [] if a["id"] in members_then and not belongs(a)), key=itemgetter("id"))
            parts["left"] = [_member_row(a, entity[0], _standing(a, island_of, grid, save["tileMap"]), refs, save, ctx, one_kind) for a in leavers]
        return {part: bodies for part, bodies in parts.items() if bodies}
    return rows + gone


# Actors split three ways: hulls (`boats`), thinking souls (`sapient_pop`) and the beasts (`wild_creatures`). `infected` = WB's `current_infected`.
def _build_snapshot(save: dict) -> dict:
    actors = save.get("actors_data") or []
    civic = civic_building_ids()
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
            "buildings": sum(n for aid, n in asset_counts.items() if aid in civic),  # Built structures worldwide (nature excluded); `houses` = dwellings.
            "frozen_pct": round(frozen / (tiles or 1) * 100),  # the map's frozen share, whole — permafrost, snow, ice and frost; `geography … totals` has the tenth
            "houses": sum(n for aid, n in asset_counts.items() if aid.startswith("house")),
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


# The causes each lineage's deaths rose by between two saves — under `None`, the world's past every living lineage's: those of the lineages that died out.
def _death_rises(then: dict, now: dict) -> dict[int | None, list[str]]:
    before = {sub["id"]: death_causes(sub) for sub in then.get("subspecies") or []}
    rises, counted = {}, Counter()
    for sub in now.get("subspecies") or []:
        was = before.get(sub["id"], {})
        rose = {cause: n - was.get(cause, 0) for cause, n in death_causes(sub).items() if n > was.get(cause, 0)}
        rises[sub["id"]] = sorted(rose)
        counted.update(rose)
    world_then, world_now = _world_deaths(then), _world_deaths(now)
    rises[None] = sorted(cause for cause, n in world_now.items() if n - world_then.get(cause, 0) > counted[cause])
    return rises


# The dead since an earlier chapter, as it knew them — WB keeps no dead, so a body gone from the save is one gone from the world: filtered as the living are.
def _gone_since(
    save: dict,
    then: dict,
    was: dict[int, int | str],
    kinds: set[str] | None,
    trait: str | None,
    asked: int | str | None,
    sapient: bool | None,
    belongs: Callable[[dict], bool],
) -> list[dict]:
    alive = {actor["id"] for actor in save.get("actors_data") or []}
    thinking = _sapient_subspecies(then) if sapient is not None else None
    bearing = {sub["id"] for sub in then.get("subspecies") or [] if trait in (sub.get("saved_traits") or ())} if trait else set()
    ctx, rises, now = build_actor_stats_context(then), _death_rises(then, save), float((save.get("mapStats") or {}).get("world_time") or 0)
    rows = []
    for actor in then.get("actors_data") or []:
        if actor["id"] in alive or actor["id"] not in was or (kinds and actor.get("asset_id") not in kinds) or not belongs(actor):
            continue
        if trait and trait not in (actor.get("saved_traits") or ()) and actor.get("subspecies") not in bearing:
            continue
        if (thinking is not None and (actor.get("subspecies") in thinking) != sapient) or (asked is not None and was[actor["id"]] != asked):
            continue
        # `was_on` silent under `-i`, which names the land it held
        old = _old_at(actor, ctx)
        row = {"asset_id": actor.get("asset_id"), "gone": True, "id": actor["id"], "name": actor.get("name"), "old_from": None if old is None else world_date(old)}
        # The cause its lineage's counters rose by, the world's past the living lineages' where it died out: one alone is its own, several what it may have
        # died of — old age struck off where the body could not have reached it by the later save
        causes = [cause for cause in rises.get(actor.get("subspecies"), rises[None]) if cause != "old_age" or (old is not None and old <= now)]
        if causes:
            row["died_of"] = causes[0] if len(causes) == 1 else causes
        rows.append({**row, "was_on": None if asked else was[actor["id"]]})
    return sorted(rows, key=lambda row: row["id"])


# One field of `--with` over a roll too long to list: a task or a status counted by its value, a stat by its spread — `of` the bodies it applies to.
def _grouped_field(field: str, values: list) -> dict | None:
    if field in _KEPT_FIELDS:  # lands by their id first, the islets and the water after, every other value by its name, a date's figures as numbers
        counts = Counter(item for value in values if value for item in (value if isinstance(value, list) else [value]))
        return {str(key): counts[key] for key in sorted(counts, key=lambda key: (isinstance(key, str), _natural(key)))} or None
    held = sorted(value for value in values if value is not None)
    return {"max": held[-1], "median": median(held), "min": held[0], "of": len(held)} if held else None


# A body's measure as `--has`, `--lacks` and `--top` weigh it — `level` counts past 1, WB's floor, where every body starts. A skill or an arsenal asks for `ctx`.
def _held(actor: dict, tally: str, ctx: dict | None = None) -> int:
    if ctx is not None and tally not in _TALLIES:  # read off its stats, where a counter is the body's own
        return equipment_power(actor, ctx) if tally == "equipment_power" else int(compute_actor_stats(actor, ctx).get(tally, 0))
    value = int(actor.get(tally) or 0)
    return value if tally != "level" or value > 1 else 0


# WB `canFallInLoveWith` between two of a kind: neither pledged to a third, no blood — parent, child or a parent shared — and opposite sexes where sexed.
def _may_mate(a: dict, b: dict, sexed: bool) -> bool:
    if a.get("lover") not in (None, b["id"]) or b.get("lover") not in (None, a["id"]):
        return False
    parents_a, parents_b = {a.get("parent_id_1"), a.get("parent_id_2")} - {None}, {b.get("parent_id_1"), b.get("parent_id_2")} - {None}
    if a["id"] in parents_b or b["id"] in parents_a or parents_a & parents_b:
        return False
    return not sexed or a.get("sex") != b.get("sex")


# A member's line under an entity, as that entity's own list wrote it: its age, stage and post, one ref the entity leaves open — the town, or a lineage's family.
def _member_row(actor: dict, kind: str, here: int | str | None, refs: dict, save: dict, ctx: dict, one_kind: bool) -> dict:
    age = actor_age(actor, ctx["world_time"])
    row = {
        "age": age,
        "asset_id": actor.get("asset_id") if kind == "city" and not one_kind else None,  # a town's line alone: elsewhere the ref fills its room
        "id": actor["id"],
        "job": resolve_profession(actor, save),
        **({"level": level} if (level := int(actor.get("level") or 0)) > 1 else {}),  # WB leaves most souls at 1: a rung above is earned
        "life_stage": None if (stage := _stage(actor, ctx, age, adult_age(actor, ctx))) == "adult" else stage,  # an age says no stage: each kind grows at its pace
        "name": actor.get("name"),
        "sex": sex_label(actor),
    }
    if kind == "army":  # its own town's, every one of them: the line tells when each joined instead
        return {**row, "army_since": kept_army_since(actor), "island_id": here}
    if kind == "city":  # the town is the filter: its roof is what a line can still tell, `ground/info.py <id>` behind it
        return {**row, "home": actor.get("homeBuildingID"), "island_id": here}
    if kind == "family":  # kin under a roof: the generation and the house, the land left to `actor`
        return {
            **row,
            "city": entity_ref(actor.get("cityID"), refs["city"]),
            "gen": gen if (gen := int(actor.get("generation") or 1)) > 1 else None,
            "home": actor.get("homeBuildingID"),
        }
    ref = ("family", actor.get("family")) if kind == "subspecies" else ("city", actor.get("cityID"))  # one ref a line can afford: a second blows the inline budget
    return {**row, ref[0]: entity_ref(ref[1], refs[ref[0]]), "island_id": here}


# The one name a leader needs, found by a scan: reading a single row beats indexing a whole collection to serve one key, even on the longest of them.
def _name_of(records: list[dict], target_id: int | None) -> str | None:
    return next((r.get("name") for r in records if r.get("id") == target_id), None)


# A value as `--with` ranks it, its figures as numbers: `y2 m7` before `y10 m3`, an id 9 before 10.
def _natural(value: object) -> list:
    return [int(part) if part.isdigit() else part for part in re.split(r"(\d+)", str(value))]


# `--nearest`'s goal: a body `p<id>`, else a tile `x,y`.
def _near_arg(value: str) -> int | tuple[int, int]:
    return xy_arg(value) if (body := body_ref(value)) is None else body


# Why `roster` came back empty, told by the filters given — so an empty land never reads as a mistyped kind, and the buildings hint only where no body is that kind.
def _nobody(args: argparse.Namespace, kinds: set[str] | None, save: dict, since: str | None) -> str:
    said = [
        f"bearing {args.trait}" if args.trait else None,
        ("past level 1" if args.has == "level" else f"with any {args.has}") if args.has and not since else None,
        ("at level 1" if args.lacks == "level" else f"with no {args.lacks}") if args.lacks else None,
        f"with any {args.top}" if args.top else None,
        f"wearing {args.status}" if args.status else None,
        f"at {args.task}" if args.task else None,
        "that could found a town where it stands" if args.settle else None,
        "kept from founding by more than its age" if args.barred else None,
        (f"on land {args.island}" if isinstance(args.island, int) else f"on the {args.island}") if args.island is not None else None,
        f"on the patch of {args.patch[0]},{args.patch[1]}" if args.patch else None,
        *(f"of {kind} {entity_id}" for kind in _MEMBERSHIPS if (entity_id := getattr(args, kind)) is not None),
        (f"whose {args.has} moved since {since}" if args.has else f"arrived, moved or died since {since}") if since else None,
    ]
    thinking = "thinking " if args.sapient or args.settle or args.barred else "unthinking " if args.beasts else ""
    unborn = kinds is not None and not any(a.get("asset_id") in kinds for a in save.get("actors_data") or [] if not is_boat(a))
    hint = " — a family of buildings (`trees`…) holds none, `geography … entity_types` lists the kinds" if unborn else ""
    return f"✗ no living {thinking}{args.type or 'body'} {', '.join(filter(None, said))}".rstrip() + hint


# WB `checkNaturalDeath`: no old age before the age, counted from 1, passes the whole span (an insect's half year opens it at once), nor ever for an immortal.
def _old_at(actor: dict, ctx: dict) -> float | None:
    lifespan = body_lifespan(actor, ctx)
    if not lifespan or "immortal" in (actor.get("saved_traits") or ()):
        return None
    return float(actor.get("created_time") or 0) + max(floor(lifespan - 1 - (actor.get("age_overgrowth") or 0)) + 1, 0) * UNITS_PER_YEAR


# A field of `--with` that no body of the roll carries, refused with every one it could take: mistyped, or no lineage here bears it.
def _refuse_unseen(fields: list[str], seen: set[str]) -> None:
    if unknown := [field for field in fields if field not in seen]:
        raise ValueError(f"✗ no body here has {', '.join(f'`{f}`' for f in unknown)} — `--with` takes {', '.join(sorted(seen))}")


# The subspecies WB hangs `has_sapience` on, as a set of ids — an allegiance is not a mind, and a world can think long before it crowns anyone.
def _sapient_subspecies(save: dict) -> frozenset:
    return frozenset(sid for sid, sub in index_by_id(save.get("subspecies") or []).items() if is_sapient(sub))


# Whoever holds the composite's first place, `{id, name}` alone: a Borda total climbs with every rival, so the points never travel.
def _score_leaders(totals: Counter, records: list[dict]) -> list[dict]:
    field = {r["id"]: totals[r["id"]] for r in records}  # every town or crown a rival, the ones `score_totals` credits nothing included
    return [{"id": eid, "name": _name_of(records, eid)} for eid, _ in first_place(field, MIN_SCORE_PEERS)]


# The saves after `since` up to this one: a body a chapter in between held was seen, and is gone rather than passed unseen.
def _since_saves(since: str, chapter: str | None, save: dict) -> list[dict]:
    later = [SAVES_DIR / f"C{n}" / "map.wbox" for n in range(int(since[1:]) + 1, int(chapter[1:]) if chapter else 0)]
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


# Why the deaths WB counted since a save and the bodies gone since differ, those no chapter saw counted in — nothing where they agree, `saves` from then to now.
def _unseen_deaths(saves: list[dict], since: str, unseen: int) -> dict:
    seen, now_ids = ({actor["id"] for save in held for actor in save.get("actors_data") or []} for held in (saves[:-1], saves[-1:]))
    gone = len(seen - now_ids)
    died = int((saves[-1].get("mapStats") or {}).get("deaths") or 0) - int((saves[0].get("mapStats") or {}).get("deaths") or 0)
    if not (off := gone + unseen - died):
        return {}
    # The counts alone, the why glossed: `Actor.die` skips the count (`pCountDeath` false) on a metamorphosis, `dieAndDestroy` and `dieSimpleNone`.
    told = f"{gone} bodies gone since {since} and {unseen} passed unseen for {died} deaths counted"
    return {"deaths_without_body" if off < 0 else "gone_without_death": abs(off), "info": told}


# The world's deaths by cause as `mapStats` keeps them, named as a lineage's are (`death_causes`): WB writes the world's old age `age`, a lineage's `natural`.
def _world_deaths(save: dict) -> dict[str, int]:
    return {
        "old_age" if (cause := key.removeprefix("deaths_")) == "age" else cause: n
        for key, n in (save.get("mapStats") or {}).items()
        if key.startswith("deaths_") and n
    }


def main(argv: list[str]) -> int:
    try:
        since, argv = take_since(argv)
    except ValueError as e:
        print(f"✗ {e}", file=sys.stderr)
        return 2
    save_path, argv, chapter = take_chapter(argv)
    parser = arg_parser(prog="world/info.py", description="World-wide sections, from the save alone.")
    parser.add_argument("sections", nargs="?", help=f"Comma-separated sections, `full` by default. Valid: {', '.join((*_ALL_SECTIONS, *_ON_REQUEST))}")
    for kind in _MEMBERSHIPS:
        parser.add_argument(f"--{kind}", type=int, metavar="id", help=f"`roster`: the members of one {kind}, in the line its own list kept")
    parser.add_argument("--barred", action="store_true", help="`roster`: the thinkers something besides their age keeps from founding, and what")
    parser.add_argument("--beasts", action="store_true", help="`roster`: the bodies of no thinking lineage alone, `--sapient`'s other half")
    parser.add_argument("--has", choices=_TALLIES, help="`roster`: the bodies with one tally above nought — `level` past 1 — and its figure, highest first")
    parser.add_argument("--island", "-i", type=land_arg, metavar="id", help="`roster`: the bodies standing on one land, or on the `islets` or the `water`")
    parser.add_argument("--lacks", choices=_TALLIES, help="`roster`: the bodies with none of one tally — `level` at 1 —, `--has`'s other half")
    parser.add_argument("--nearest", type=_near_arg, metavar="x,y|p<id>", help=f"`roster`: its {_TOP_ROWS} nearest to a tile or a body, as the crow flies")
    parser.add_argument("--patch", type=xy_arg, metavar="x,y", help="`roster`: the bodies standing on that tile's patch, one ground of one land")
    parser.add_argument("--sapient", action="store_true", help="`roster`: the thinking bodies alone")
    parser.add_argument("--settle", action="store_true", help="`roster`: the bodies that could found a town where they stand, once grown")
    parser.add_argument("--status", help="`roster`: the bodies wearing one status, by its id — what a body wears now, where a trait is what it is")
    parser.add_argument("--task", help="`roster`: the bodies at one task the instant of the save, by its id — what a body does, where a status is what it wears")
    parser.add_argument("--top", choices=_TOP_MEASURES, help=f"`roster`: its {_TOP_ROWS} highest by one measure, a tally or a skill, each with its figure")
    parser.add_argument("--trait", help="`roster`: the bodies bearing one trait, their own or their lineage's, by its id")
    parser.add_argument("--type", "-t", help="`roster` and `lineages`: one kind, a family (`actors`) or a comma list")
    parser.add_argument(
        "--with", dest="fields", metavar="field,…", help=f"`roster`: up to {_MAX_FIELDS} of `actor … stats`, `task`, `subspecies` or a line's own field on each line"
    )
    args = parser.parse_args(argv)
    requested = args.sections
    try:
        sections = parse_sections(requested, (*_ALL_SECTIONS, *_ON_REQUEST), full=_ALL_SECTIONS)
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 2
    entities = [(kind, entity_id) for kind in _MEMBERSHIPS if (entity_id := getattr(args, kind)) is not None]
    # What keeps only some bodies of the roll: `-t` among them, though it narrows `lineages` too, and `--with` none — it adds fields to every line
    filtered = (
        any((args.barred, args.beasts, args.has, args.lacks, args.patch, args.sapient, args.settle, args.status, args.task, args.top, args.trait, entities))
        or args.island is not None
        or args.nearest is not None
    )
    narrowing = filtered or (args.type and "lineages" not in sections) or args.fields is not None
    if len(entities) > 1:  # one roll, one entity: the others are its members' own fields
        print(f"✗ {' and '.join(f'--{kind}' for kind, _ in entities)}: name one entity — the others are fields of its members", file=sys.stderr)
        return 2
    if args.beasts and (other := next((flag for flag in ("sapient", "settle", "barred") if getattr(args, flag)), None)):  # minds and the rest: none in both
        print(f"✗ --beasts and --{other} split the bodies in two: name one", file=sys.stderr)
        return 2
    if args.settle and args.barred:  # the two halves of the thinkers: together they name no one
        print("✗ --settle and --barred split the thinkers in two: name one", file=sys.stderr)
        return 2
    if narrowing and "roster" not in sections:  # refused before the save is read, as a flag that would go unheard
        flags = "-t, --trait, --has, --lacks, --top, --nearest, --with, --status, --task, --patch, --sapient, --beasts, --settle, --barred, -i and an entity"
        print(f"✗ {flags} narrow `roster`, `-t` `lineages` too: name it", file=sys.stderr)
        return 2
    if args.has and args.lacks:  # the two halves of a roll by one tally: together they name no one
        print("✗ --has and --lacks split a roll in two: name one", file=sys.stderr)
        return 2
    if args.top and (other := next((flag for flag in ("has", "lacks", "settle", "barred") if getattr(args, flag)), None)):
        print(f"✗ `--top` ranks a roll by one measure: ask `--{other}` apart", file=sys.stderr)
        return 2
    if args.top and args.nearest is not None:
        print("✗ `--top` and `--nearest` each rank a roll: ask one", file=sys.stderr)
        return 2
    if (ranked := "--top" if args.top else "--nearest" if args.nearest is not None else None) and since:  # each read off its own chapter
        print(f"✗ `{ranked}` ranks one chapter: read the other by its suffix, `{since}`", file=sys.stderr)
        return 2
    if since and (alone := next((flag for flag in ("lacks", "patch", "status", "task") if getattr(args, flag)), None)):
        print(f"✗ `--{alone}` reads one chapter: ask `--since` apart", file=sys.stderr)  # the dead stood, wore and did what no later save tells
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
    if "boats" in sections:
        out["boats"] = _build_boats(save, requested)
    if "cumulative" in sections:
        out["cumulative"] = _build_cumulative(map_stats)
    if "laws" in sections:
        out["laws"] = _build_laws(save)
    if "leaders" in sections:
        out["leaders"] = _build_leaders(save)
    if "lineages" in sections:
        families = asset_families(save) if args.type else {}  # swept for `-t` alone: every body and every building
        if not (lineages := _build_lineages(save, asset_kinds(families, args.type) if args.type else None)):
            # A mistyped word told apart from a kind with no lineage left, as `roster` tells it
            why = (args.type and unsited_reason(families, args.type)) or f"no living lineage{f' of {args.type}' if args.type else ''} in this world"
            print(f"✗ {why}", file=sys.stderr)
            return 1
        out["lineages"] = lineages
    if "metadata" in sections:
        out["metadata"] = _build_metadata(map_stats)
    if "pairings" in sections:
        out["pairings"] = _build_pairings(save, save_path)
    if "plots" in sections:
        out["plots"] = _build_plots(save)
    if "roster" in sections:
        kinds = asset_kinds(asset_families(save), args.type) if args.type else None
        lands, island_of = compute_islands_cached(save, save_path)  # loaded once: the land `-i` names is checked against the lookup the roll then reads
        if isinstance(args.island, int) and args.island not in {land["id"] for land in lands}:
            print(f"✗ no land with id {args.island} — `geography … islands` lists them", file=sys.stderr)
            return 2
        stray = args.trait and args.trait not in load_data("creature-traits.json") and args.trait not in load_data("subspecies-traits.json")
        # What this world wears, swept only where a refusal may need it: a trait that is one costs the roll nothing more.
        worn = sorted({status for actor in save.get("actors_data") or [] for status in kept_statuses(actor) or ()}) if args.status or stray else []
        if stray:
            # A status asked as a trait is sent to its own filter: `cursed` reads like one, and the plain refusal would leave no way on.
            hint = f"it is a status: `--status {args.trait}`" if args.trait in worn else "`actor <id> traits` and `subspecies <id> traits` give the ids"
            print(f"✗ no trait {args.trait}, of a body or of a lineage — {hint}", file=sys.stderr)
            return 2
        if args.status and args.status not in worn:  # refused by what this world wears: WB's whole list would not tell a mistyped id from an idle one
            print(f"✗ no body wears {args.status} — worn here: {', '.join(worn) or 'no status at all'}", file=sys.stderr)
            return 2
        if args.task and args.task not in (done := sorted(set(filter(None, map(kept_task, save.get("actors_data") or []))))):
            print(f"✗ no body is at {args.task} — tasks here: {', '.join(done) or 'none kept in this save'}", file=sys.stderr)
            return 2
        entity = entities[0] if entities else None
        if entity and entity[1] not in {record.get("id") for record in save.get(_MEMBERSHIPS[entity[0]][0]) or []}:
            # An army has no tool of its own to send the refusal to: a town's names it, where `absent_entity` would point at an `army/info.py`.
            army = f"✗ no army {entity[1]} here — `city/info.py <id> army` gives a town's"
            print(army if entity[0] == "army" else absent_entity(entity[0], _MEMBERSHIPS[entity[0]][0], entity[1], chapter), file=sys.stderr)
            return 1
        near = None
        if isinstance(args.nearest, tuple):
            near = args.nearest, None
        elif args.nearest is not None:
            if (body := next((a for a in save.get("actors_data") or [] if a["id"] == args.nearest and not is_boat(a)), None)) is None:
                print(absent_entity("actor", "actors_data", args.nearest, chapter, lambda a: not is_boat(a)), file=sys.stderr)
                return 1
            near = actor_xy(body), args.nearest
        patch = None
        if args.patch:
            if island_of.get(args.patch) is None:  # off the map as on the water: a patch is one ground of one counted land
                print(f"✗ {args.patch[0]},{args.patch[1]} stands on no counted land — `tiles <x,y> tile_info` tells what a tile is", file=sys.stderr)
                return 2
            patch = patch_finder(save, LazyTileGrid(save), island_of)(*args.patch)[0]
        fields = args.fields.split(",") if args.fields else []
        if len(fields) > _MAX_FIELDS:
            print(f"✗ `--with` takes {_MAX_FIELDS} fields at most — `actor <id> stats` gives a body's whole sheet", file=sys.stderr)
            return 2
        try:
            roster = _build_roster(
                save,
                save_path,
                island_of,
                kinds,
                args.trait,
                args.island,
                since,
                True if args.sapient else False if args.beasts else None,
                args.settle,
                args.barred,
                patch,
                args.status,
                args.task,
                args.has,
                args.lacks,
                args.top,
                entity,
                near,
                fields,
            )
        except ValueError as e:  # a field `--with` asks that no body of the roll carries
            print(e, file=sys.stderr)
            return 1
        # The bodies born and gone between the two saves, no roll's to name: an absence over the span is unproven while any passed (`came_and_went`)
        unseen = passed_unseen(load_save(SAVES_DIR / since / "map.wbox"), _since_saves(since, chapter, save)).get("bodies_and_hulls") if since else None
        if not roster:  # a filter nothing answers, never a silent `{}`
            print(_nobody(args, kinds, save, since) + (f" — {unseen} more came and went unseen in the world, kind unknown" if unseen else ""), file=sys.stderr)
            return 1
        if unseen and isinstance(roster, dict):
            # The world's, whatever the filter: no save keeps what they were, so a filtered roll says whose count it is — yet keeps it, an absence unproven
            roster["came_and_went"] = {"world": unseen} if filtered or args.type else unseen
        out["roster"] = roster
    if "snapshot" in sections:
        out["snapshot"] = _build_snapshot(save)
    readings = {"cumulative": lambda then: _build_cumulative(then.get("mapStats") or {}), "snapshot": _build_snapshot}  # each read again off the save before
    if since and (counted := [section for section in readings if section in out]):
        then = load_save(SAVES_DIR / since / "map.wbox")
        # A count by count difference, `[then, now]` and 0 where a counter was not: a section that holds still drops out, and none moving says so
        for section in counted:
            if isinstance(moved := moved_between(readings[section](then), out.pop(section)), dict):
                out[section] = moved
        if "cumulative" in out:
            since_then = _since_saves(since, chapter, save)
            unseen = passed_unseen(then, since_then)
            out["cumulative"] |= {"came_and_went": unseen or None, **_unseen_deaths([then, *since_then], since, unseen.get("bodies_and_hulls", 0))}
        if not out:
            print(f"✗ nothing moved in {', '.join(counted)} since {since}", file=sys.stderr)
            return 1

    emit(out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
