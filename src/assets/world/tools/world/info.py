#!/usr/bin/env python3

# Emits the world sections from the save alone (`mapStats` = WB's period-accurate counters); the chapter's registries are built by
# `chapter/registries.py` (the bootstrap), not here. User-facing docs — usage and sections — live in `docs/tools.md`.
#
# ⚠️ Output keys must stay self-descriptive (chronicler reads them with no other context). Prefer disambiguated names (e.g. `wild_creatures` over `creatures`).
# Exception: WB-native names kept verbatim for raw-save fields (e.g. `asset_id`) — the tools' default, a rename having to earn its churn across py, UI and data.

import sys
from collections import Counter, defaultdict
from functools import cache
from math import inf
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))

from actor_stats import (
    actor_stat_totals,
    adult_age,
    breeding_age,
    build_actor_stats_context,
    compute_actor_stats,
    crossed_at,
    crossed_on,
    is_egg,
    is_hungry,
    kept_statuses,
    kept_task,
    maturation_months,
    status_left,
)
from founding import city_zones, settle_gates, settle_rank, settle_told
from grid import LazyTileGrid, frozen_tally, off_land, patch_finder
from islands import compute_islands_cached
from shared import (
    MAX_LISTED,
    MIN_RANK_PEERS,
    MIN_SCORE_PEERS,
    NEW_BABY_NUTRITION,
    SAVES_DIR,
    SICK_TRAITS,
    UNITS_PER_MONTH,
    UNITS_PER_YEAR,
    actor_age,
    actor_xy,
    arg_parser,
    asset_families,
    asset_kinds,
    breeding_mode,
    building_family,
    city_score_dimensions,
    civic_building_ids,
    emit,
    fertile,
    first_place,
    i18n,
    index_by_id,
    is_aboard,
    is_boat,
    is_sapient,
    kingdom_score_dimensions,
    land_arg,
    life_stage,
    light,
    load_data,
    load_save,
    moved_between,
    needs_food,
    parse_sections,
    quiet_zeros,
    rounded_world_time,
    score_totals,
    sex_label,
    spores_unfed,
    take_chapter,
    take_since,
    under_construction,
    unranked,
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
    "creatures_created": "creaturesCreated",  # divine spawn + worldgen
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

_GOOD_ISLET = 5  # WB `TileIsland.isGoodIslandForActor`: an islet of so few tiles is one a body leaves before anything else, breeding included

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

_ISLET = "islet"  # where `roster` says a body stands, or stood, on an islet too small to count — `_WATER` where it floats

# The fewest rivals a record's field needs — `MIN_RANK_PEERS`, as a rank does, save for a town and a crown, which a world raises by the handful.
_MIN_PEERS = {"cities": MIN_SCORE_PEERS, "kingdoms": MIN_SCORE_PEERS}

_ON_REQUEST = ("laws", "pairings", "roster")  # named only: `full` is what the bootstrap folds into a chapter, and a roll of bodies is no chapter's to carry
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

_STRATEGIC = frozenset({"reproduction_hermaphroditic", "reproduction_parthenogenesis", "reproduction_sexual"})  # carried only if viviparous, else laid at once
_UNCARRIED = frozenset({"reproduction_fission", "reproduction_spores"})  # WB makes the new body there and then, `maturation` never read
_WATER = "water"  # where `roster` says a body stands, or stood, afloat — off every land, as `_ISLET` is, but in the sea or a lake


# An age's life stage off the share of its span it has run — three words and no date, the end of an age being the turn a chronicle must not see coming.
def _age_stage(progress: float) -> str:
    return "young" if progress < _AGE_YOUNG else "waning" if progress >= _AGE_WANING else "mature"


# What keeps a body of age from breeding, WB weighing each partner: a belly short of a baby or half-full, a footing to leave first — tagged `tiny_islet 40`.
def _breeding_bars(actor: dict, ctx: dict, island_of, grid: LazyTileGrid, names: list[str]) -> set[str]:
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
    persons: dict[str, Counter] = {stat: Counter() for stat in (*_SKILLS, "level")}
    sapient = _sapient_subspecies(save)
    species: Counter[str] = Counter()

    # One pass over actors feeds every tally: the rolls and the species first, then the thinking population's levels and skills — only the scores walk them again.
    for a in actors:
        if is_boat(a):
            continue
        for field, coll in _GROUP_FIELDS.items():
            if (v := a.get(field)) is not None:
                members[coll][v] += 1
        species[a.get("asset_id")] += 1  # every body, beasts included, as the rolls above count them
        if a.get("subspecies") not in sapient:  # a mind, not an allegiance: the thinking population counts one owing no crown all the same
            continue
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
    pools = {coll: (len(tally), _MIN_PEERS.get(coll, MIN_RANK_PEERS)) for coll, tally in members.items()}
    if short := unranked({**pools, "persons": (len(persons["level"]), MIN_RANK_PEERS), "species": (len(species), MIN_RANK_PEERS)}):
        out["unranked"] = short
    return out


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
        if fed := [actor for actor in lone if actor.get("subspecies") not in unfed]:  # a lineage breeding alone needs no one
            row["alone_on"] = min(ready[actor["id"]] for actor in fed)
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
            apart, _, row["on"], crow, a, b, barred = best
            row |= {"barred": barred or None, "crow_tiles": round(crow), "lovers": True if not apart else None, "pair": [a["id"], b["id"]]}
            bearer = b if sexed[a["id"]] and b.get("sex") == 1 else a  # a sexed pair's mother carries; a hermaphrodite pair, either — WB draws it
            # Lovers may carry already, unseen, where the save keeps no status; where it does, they wait out the afterglow of their last kiss.
            glow = max(status_left(a, "afterglow") or 0, status_left(b, "afterglow") or 0)
            conceived = max(row["on"], now + glow) if apart or status_left(bearer, "pregnant") is not None else row["on"]
            births.append(max(conceived + carry.get(bearer.get("subspecies"), 0), now))
            (ax, ay), (bx, by) = where[a["id"]], where[b["id"]]
            if (land := island_of.get((ax, ay))) is not None and land == island_of.get((bx, by)):
                walk_map = walk_map or WalkMap(save)
                if (way := walk_way(walk_map, walk_map.gait(None, frozenset()), ax, ay, {by * walk_map.width + bx})) is not None:
                    row["walk_tiles"] = round(way[3])  # the tiles trodden between them, not the way's cost
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
        for key in ("alone_on", "birth_on", "on"):
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
    island_of,
    kinds: set[str] | None,
    trait: str | None,
    land: int | str | None,
    since: str | None,
    sapient: bool,
    settle: bool,
    barred: bool,
    patch: set[tuple[int, int]] | None,
    status: str | None,
    task: str | None,
) -> list[dict] | dict:
    earlier, was = _then(since) if since else (None, None)
    thinking = _sapient_subspecies(save) if sapient else None
    grid = LazyTileGrid(save)  # rows decoded as read: a body off every land alone asks its tile
    asked = _ISLET if land == "islets" else land  # `-i islets` names the islets as a body stands on one, `islet`
    if patch and land is None:
        asked = island_of.get(next(iter(patch)))  # a patch lies on one land, which then goes unsaid as `-i`'s does
    ctx = build_actor_stats_context(save)
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
    bodies = []
    for actor in save.get("actors_data") or []:
        borne = not trait or trait in (actor.get("saved_traits") or ()) or actor.get("subspecies") in bearing
        if is_boat(actor) or (kinds and actor.get("asset_id") not in kinds) or not borne or (thinking is not None and actor.get("subspecies") not in thinking):
            continue
        if patch is not None and actor_xy(actor) not in patch:
            continue
        if status and status not in (kept_statuses(actor) or ()):
            continue
        if task and kept_task(actor) != task:
            continue
        gates = settle_gates(actor, ctx) if settle or barred else None
        if settle and gates not in (True, ["child"]):  # founds where it stands once grown: nothing, or its youth alone, bars it
            continue
        if barred and (gates is None or gates in (True, ["child"])):  # a thinker something besides its youth keeps from founding
            continue
        here = _standing(actor, island_of, grid, save["tileMap"])
        change: dict = {}
        if was is not None and actor["id"] in was:  # one unseen then was born or set down since, and says so by standing in the roll at all
            if (then := was[actor["id"]]) == here:
                continue  # stood still: nothing for `since` to say
            change = {"was_on": then}
        if land is None or asked in (here, change.get("was_on")):
            bodies.append((actor, here, change | (settle_told(gates) if barred else {})))
    gone = []
    if earlier is not None and was is not None and not (settle or barred):  # the dead found nothing
        gone = _gone_since(save, earlier, was, kinds, trait, asked, sapient)
    if len(bodies) + len(gone) > MAX_LISTED:  # a census past the list: how many on each land, of each kind and of each stage, the adults counted too
        lands = Counter(here for _, here, _ in bodies)
        by_land = {str(land): lands[land] for land in sorted(lands, key=lambda land: (isinstance(land, str), land))}
        species = Counter(actor.get("asset_id") for actor, _, _ in bodies)
        stages = Counter(_stage(actor, ctx, actor_age(actor, ctx["world_time"]), adult_age(actor, ctx)) for actor, _, _ in bodies)
        return {
            "by_land": None if asked is not None else by_land,  # silent under `-i`, which names the land
            "by_species": dict(species),
            "by_stage": dict(stages),
            "gone_by_species": dict(Counter(row["asset_id"] for row in gone)) or None,
            "info": f"{len(bodies) + len(gone)} bodies — narrow them with -t, --trait, --sapient, --settle, --barred or -i",
        }
    rows, one_kind = [], kinds is not None and len(kinds) == 1  # a lone `-t` names the kind, as `-i` the land

    # Land by land, off every land last — the founders by who founds first, the barred by the gate told
    def order(body: tuple[dict, int | str, dict]) -> tuple:
        if barred:  # the steadiest kind first, then who comes nearest to passing it
            return settle_rank(body[2]["settle"]), body[0]["id"]
        if settle:  # the grown first, whose youth is past, then by the date each comes of age
            return crossed_at(body[0], adult_age(body[0], ctx)), body[0]["id"]
        return isinstance(body[1], str), body[1], body[0]["id"]

    lineages = ctx["subspecies_by_id"]
    for actor, here, change in sorted(bodies, key=order):
        age, adult, breeding = actor_age(actor, ctx["world_time"]), adult_age(actor, ctx), breeding_age(actor, ctx)
        stage = _stage(actor, ctx, age, adult)
        rows.append(
            {
                "adult_on": crossed_on(actor, adult) if age < adult else None,
                "asset_id": None if one_kind else actor.get("asset_id"),
                # Under `--barred`, what founding weighs alone: no mate nor sex, and `adult_on` says the youth — its gates keep each line inline
                "breeds_on": crossed_on(actor, breeding) if age < breeding and not barred and fertile(lineages.get(actor.get("subspecies"))) else None,
                "id": actor["id"],
                # Said outright beside a `was_on`, a missing one reading as still on the land left; silent where `-i` already named it
                "island_id": None if here == asked and "was_on" not in change else here,
                # Silent at `adult`, as in `surroundings`, and under `--barred`: on every line it would push the longest past inline
                "life_stage": None if stage == "adult" or barred else stage,
                "name": actor.get("name"),
                "sex": None if barred else sex_label(actor),
                **change,
            }
        )
    return rows + [{**row, "asset_id": None if one_kind else row["asset_id"]} for row in gone]


# Actors split three ways: hulls (`boats`), thinking souls (`sapient_population`) and the beasts (`wild_creatures`). `infected` = WB's `current_infected`.
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
            "sapient_population": sapients,  # named apart from every tier's `population`, which counts members: this one weighs minds, and no crown gathers them
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


def _count_leaders(counts: Counter, records: list[dict], min_peers: int) -> list[dict]:
    return [{"id": eid, "name": _name_of(records, eid), "value": n} for eid, n in first_place(counts, min_peers)]


# The dead since an earlier chapter, as it knew them — WB keeps no dead, so a body gone from the save is one gone from the world: filtered as the living are.
def _gone_since(save: dict, then: dict, was: dict[int, int | str], kinds: set[str] | None, trait: str | None, asked, sapient: bool) -> list[dict]:
    alive = {actor["id"] for actor in save.get("actors_data") or []}
    thinking = _sapient_subspecies(then) if sapient else None
    bearing = {sub["id"] for sub in then.get("subspecies") or [] if trait in (sub.get("saved_traits") or ())} if trait else set()
    ctx = build_actor_stats_context(then)
    rows = []
    for actor in then.get("actors_data") or []:
        if actor["id"] in alive or actor["id"] not in was or (kinds and actor.get("asset_id") not in kinds):
            continue
        if trait and trait not in (actor.get("saved_traits") or ()) and actor.get("subspecies") not in bearing:
            continue
        if (thinking is not None and actor.get("subspecies") not in thinking) or (asked is not None and was[actor["id"]] != asked):
            continue
        # `was_on` silent under `-i`, which names the land it held
        row = {"asset_id": actor.get("asset_id"), "gone": True, "id": actor["id"], "name": actor.get("name"), "old_from": _old_from(actor, ctx)}
        rows.append({**row, "was_on": None if asked else was[actor["id"]]})
    return sorted(rows, key=lambda row: row["id"])


# WB `canFallInLoveWith` between two of a kind: neither pledged to a third, no blood — parent, child or a parent shared — and opposite sexes where sexed.
def _may_mate(a: dict, b: dict, sexed: bool) -> bool:
    if a.get("lover") not in (None, b["id"]) or b.get("lover") not in (None, a["id"]):
        return False
    parents_a, parents_b = {a.get("parent_id_1"), a.get("parent_id_2")} - {None}, {b.get("parent_id_1"), b.get("parent_id_2")} - {None}
    if a["id"] in parents_b or b["id"] in parents_a or parents_a & parents_b:
        return False
    return not sexed or a.get("sex") != b.get("sex")


# The one name a leader needs, found by a scan: reading a single row beats indexing a whole collection to serve one key, even on the longest of them.
def _name_of(records: list[dict], target_id) -> str | None:
    return next((r.get("name") for r in records if r.get("id") == target_id), None)


# Why `roster` came back empty, told by the filters given — so an empty land never reads as a mistyped kind, and the buildings hint only where no body is that kind.
def _nobody(args, kinds: set[str] | None, save: dict, since: str | None) -> str:
    said = [
        f"bearing {args.trait}" if args.trait else None,
        f"wearing {args.status}" if args.status else None,
        f"at {args.task}" if args.task else None,
        "that could found a town where it stands" if args.settle else None,
        "kept from founding by more than its age" if args.barred else None,
        (f"on land {args.island}" if isinstance(args.island, int) else f"on the {args.island}") if args.island is not None else None,
        f"on the patch of {args.patch[0]},{args.patch[1]}" if args.patch else None,
        f"arrived, moved or died since {since}" if since else None,
    ]
    thinking = "thinking " if args.sapient or args.settle or args.barred else ""
    unborn = kinds is not None and not any(a.get("asset_id") in kinds for a in save.get("actors_data") or [] if not is_boat(a))
    hint = " — a family of buildings (`trees`…) holds none, `geography … entity_types` lists the kinds" if unborn else ""
    return f"✗ no living {thinking}{args.type or 'body'} {', '.join(filter(None, said))}".rstrip() + hint


# WB `checkNaturalDeath`: old age takes no body before its age passes its span, and never an immortal — the date that bars it as a cause, or opens it.
def _old_from(actor: dict, ctx: dict) -> str | None:
    lifespan = int(actor_stat_totals(actor, ctx, lifespan_only=True).get("lifespan", 0))
    if not lifespan or "immortal" in (actor.get("saved_traits") or ()):
        return None
    return world_date(float(actor.get("created_time") or 0) + max(lifespan - (actor.get("age_overgrowth") or 0), 0) * UNITS_PER_YEAR)


# The subspecies WB hangs `has_sapience` on, as a set of ids — an allegiance is not a mind, and a world can think long before it crowns anyone.
def _sapient_subspecies(save: dict) -> frozenset:
    return frozenset(sid for sid, sub in index_by_id(save.get("subspecies") or []).items() if is_sapient(sub))


# Whoever holds the composite's first place, `{id, name}` alone: a Borda total climbs with every rival, so the points never travel.
def _score_leaders(totals: Counter, records: list[dict]) -> list[dict]:
    field = {r["id"]: totals[r["id"]] for r in records}  # every town or crown a rival, the ones `score_totals` credits nothing included
    return [{"id": eid, "name": _name_of(records, eid)} for eid, _ in first_place(field, MIN_SCORE_PEERS)]


# A body's stage off its raw span alone, as `surroundings` reads one: a roster line and a census say it alike.
def _stage(actor: dict, ctx: dict, age: int, adult: float) -> str:
    lifespan = int(actor_stat_totals(actor, ctx, lifespan_only=True).get("lifespan", 0))
    return life_stage(age, adult, lifespan, is_egg(actor, ctx))


# Where a body stands as `roster` tells it: its land, else `water` where it floats and `islet` on an islet too small to count, as `surroundings` splits them.
def _standing(actor: dict, island_of, grid: LazyTileGrid, names: list[str]) -> int | str:
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


# Why the deaths WB counted between two saves and the bodies gone between them differ, `None` where they agree — WB keeps no dead, so none is named.
def _unseen_deaths(save: dict, then: dict, since: str) -> str | None:
    now_ids = {actor["id"] for actor in save.get("actors_data") or []}
    gone = sum(actor["id"] not in now_ids for actor in then.get("actors_data") or [])
    died = int((save.get("mapStats") or {}).get("deaths") or 0) - int((then.get("mapStats") or {}).get("deaths") or 0)
    if gone == died:
        return None
    dying, unborn = f"dying as {since} was saved, counted before it yet still in its save", "born and dead between the two saves, in neither"
    return f"{gone} bodies gone since {since} for {died} deaths counted: {abs(gone - died)} {dying if gone > died else unborn}"


def main(argv: list[str]) -> int:
    try:
        since, argv = take_since(argv)
    except ValueError as e:
        print(f"✗ {e}", file=sys.stderr)
        return 2
    save_path, argv, _ = take_chapter(argv)
    parser = arg_parser(prog="world/info.py", description="World-wide sections, from the save alone.")
    parser.add_argument("sections", nargs="?", help=f"Comma-separated sections, `full` by default. Valid: {', '.join((*_ALL_SECTIONS, *_ON_REQUEST))}")
    parser.add_argument("--barred", action="store_true", help="`roster`: the thinkers something besides their age keeps from founding, and what")
    parser.add_argument("--island", "-i", type=land_arg, metavar="id", help="`roster`: the bodies standing on one land, or on the `islets` or the `water`")
    parser.add_argument("--patch", type=xy_arg, metavar="x,y", help="`roster`: the bodies standing on that tile's patch, one ground of one land")
    parser.add_argument("--sapient", action="store_true", help="`roster`: the thinking bodies alone")
    parser.add_argument("--settle", action="store_true", help="`roster`: the bodies that could found a town where they stand, once grown")
    parser.add_argument("--status", help="`roster`: the bodies wearing one status, by its id — what a body wears now, where a trait is what it is")
    parser.add_argument("--task", help="`roster`: the bodies at one task the instant of the save, by its id — what a body does, where a status is what it wears")
    parser.add_argument("--trait", help="`roster`: the bodies bearing one trait, their own or their lineage's, by its id")
    parser.add_argument("--type", "-t", help="`roster`: one kind, a family (`actors`) or a comma list")
    args = parser.parse_args(argv)
    requested = args.sections
    try:
        sections = parse_sections(requested, (*_ALL_SECTIONS, *_ON_REQUEST), full=_ALL_SECTIONS)
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 2
    narrowing = args.type or args.trait or args.status or args.task or args.sapient or args.settle or args.barred or args.island is not None or args.patch
    if args.settle and args.barred:  # the two halves of the thinkers: together they name no one
        print("✗ --settle and --barred split the thinkers in two: name one", file=sys.stderr)
        return 2
    if narrowing and "roster" not in sections:  # refused before the save is read, as a flag that would go unheard
        print("✗ -t, --trait, --status, --task, --patch, --sapient, --settle, --barred and -i narrow `roster`: name it", file=sys.stderr)
        return 2
    if since and (alone := next((flag for flag in ("patch", "status", "task") if getattr(args, flag)), None)):
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
        patch = None
        if args.patch:
            if island_of.get(args.patch) is None:  # off the map as on the water: a patch is one ground of one counted land
                print(f"✗ {args.patch[0]},{args.patch[1]} stands on no counted land — `tiles <x,y> tile_info` tells what a tile is", file=sys.stderr)
                return 2
            patch = patch_finder(save, LazyTileGrid(save), island_of)(*args.patch)[0]
        roster = _build_roster(save, island_of, kinds, args.trait, args.island, since, args.sapient, args.settle, args.barred, patch, args.status, args.task)
        if not roster:  # a filter nothing answers, never a silent `{}`
            print(_nobody(args, kinds, save, since), file=sys.stderr)
            return 1
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
            out["cumulative"]["info"] = _unseen_deaths(save, then, since)
        if not out:
            print(f"✗ nothing moved in {', '.join(counted)} since {since}", file=sys.stderr)
            return 1

    emit(out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
