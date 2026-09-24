#!/usr/bin/env python3

# Emits the world sections from the save alone (`mapStats` = WB's period-accurate counters); the chapter's registries are built by
# `chapter/registries.py` (the bootstrap), not here. User-facing docs — usage and sections — live in `docs/tools.md`.
#
# ⚠️ Output keys must stay self-descriptive (chronicler reads them with no other context). Prefer disambiguated names (e.g. `wild_creatures` over `creatures`).
# Exception: WB-native names kept verbatim for raw-save fields (e.g. `world_time`) — the tools' default, a rename having to earn its churn across py, UI and data.

import re
import sqlite3
import sys
from collections import Counter, defaultdict
from math import inf
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))

from actor_stats import adult_age, breeding_age, build_actor_stats_context, compute_actor_stats, crossed_at, crossed_on
from grid import frozen_tally
from islands import compute_islands_cached
from shared import (
    HISTORY_S3DB,
    MIN_RANK_PEERS,
    MIN_SCORE_PEERS,
    SAVES_DIR,
    SICK_TRAITS,
    UNITS_PER_YEAR,
    actor_age,
    actor_xy,
    arg_parser,
    asset_families,
    asset_kinds,
    breeding_mode,
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
    rounded_world_time,
    score_totals,
    sex_label,
    take_chapter,
    take_since,
    walk_tiles,
    wants_detail,
    world_date,
)
from walking import WalkMap, walk_to

_ALL_SECTIONS = ("boats", "cumulative", "leaders", "metadata", "plots", "snapshot", "timeline")

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

# A `WorldYearly1` column that only rises, an event's tally — where a bare noun (`cities`, `grass`) is a state that moves every year and dates nothing.
_EVENT_COLUMN = re.compile(r"_(born|built|burnt|conquered|created|destroyed|dissolved|extinct|forgotten|made|read|rebelled|started|succeeded|written)$")

_EVENT_EXTRAS = ("evolutions", "metamorphosis")  # the two tallies WB names without a suffix

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

_MAX_ROSTER = 50  # past so many bodies a roll is read for its species, not its names: filters narrow it back to a list

# The fewest rivals a record's field needs — `MIN_RANK_PEERS`, as a rank does, save for a town and a crown, which a world raises by the handful.
_MIN_PEERS = {"cities": MIN_SCORE_PEERS, "kingdoms": MIN_SCORE_PEERS}

_OFF_LAND = "off_land"  # where `roster` says a body stands, or stood, on no counted land — an islet or the water
_ON_REQUEST = ("pairings", "roster")  # named only: `full` is what the bootstrap folds into a chapter, and a roll of bodies is no chapter's to carry

_SEXED = "reproduction_sexual"  # the one breeding WB pairs by opposite sexes: a hermaphrodite takes any partner of its kind

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

# `_DEATH_CAUSES`' keys => their `WorldYearly1` column, where old age is WB's `deaths_natural`.
_YEARLY_DEATHS = {**{cause: f"deaths_{cause}" for cause in _DEATH_CAUSES}, "old_age": "deaths_natural"}

_YEARLY_RENAMED = {"houses_built": "buildings_built", "houses_destroyed": "buildings_destroyed"}  # `cumulative`'s names: WB's houses are all its buildings


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


# The world's standouts, shaped as every tier's `leaders`: group, then measure, then its first place — `persons` weighing thinking souls alone.
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
        "world_time": rounded_world_time(map_stats),
    }


# Each kind's first couple by WB's `canFallInLoveWith`, dated by the later breeding age (`now` once both hold); today's gap, walked on one shared land only.
def _build_pairings(save: dict, save_path: Path) -> list[dict]:
    ctx, kinds = build_actor_stats_context(save), defaultdict(list)
    for actor in save.get("actors_data") or []:
        if not is_boat(actor):
            kinds[actor.get("asset_id")].append(actor)
    island_of, walk_map = compute_islands_cached(save, save_path)[1], None
    # Traits and breeding are a lineage's, read once each: a kind's bodies share a handful of lineages, and every pair below asks of both.
    traits = {sub["id"]: frozenset(sub.get("saved_traits") or ()) for sub in save.get("subspecies") or []}
    mode, empty = {sid: breeding_mode(lineage) for sid, lineage in traits.items()}, frozenset()
    rows: list[tuple[float, dict]] = []
    for kind, bodies in kinds.items():
        ready = {actor["id"]: crossed_at(actor, breeding_age(actor, ctx)) for actor in bodies}
        where = {actor["id"]: actor_xy(actor) for actor in bodies}
        mating = [actor for actor in bodies if mode.get(actor.get("subspecies")) == "mate"]
        row: dict = {"asset_id": kind}
        if lone := [ready[actor["id"]] for actor in bodies if mode.get(actor.get("subspecies")) == "alone"]:  # a lineage breeding alone needs no one
            row["alone_on"] = min(lone)
        sexed = {actor["id"]: _SEXED in traits.get(actor.get("subspecies"), empty) for actor in mating}
        best = min(
            (
                (max(ready[a["id"]], ready[b["id"]]), walk_tiles(where[b["id"]][0] - where[a["id"]][0], where[b["id"]][1] - where[a["id"]][1]), a, b)
                for i, a in enumerate(mating)
                for b in mating[i + 1 :]
                if _may_mate(a, b, sexed[a["id"]] or sexed[b["id"]])
            ),
            key=lambda pair: pair[:2],
            default=None,
        )
        if best:
            row["on"], crow, a, b = best
            row |= {"pair": [a["id"], b["id"]], "tiles": round(crow)}
            (ax, ay), (bx, by) = where[a["id"]], where[b["id"]]
            if (land := island_of.get((ax, ay))) is not None and land == island_of.get((bx, by)):
                walk_map = walk_map or WalkMap(save)
                if (walked := walk_to(walk_map, walk_map.gait(None, frozenset()), ax, ay, {by * walk_map.width + bx})) is not None:
                    row["walked"] = round(walked)
        elif not mating and not lone:  # no lineage of the kind holds a breeding trait: it never breeds
            row["missing"] = "reproduction"
        elif mating:  # a partner wanted, none to be had: a sexed kind of one sex says which, else blood or pledges bar every pair
            sexes = {sex_label(actor) for actor in mating}
            row["missing"] = ({"female": "male", "male": "female"}[sexes.pop()]) if len(sexes) == 1 and all(sexed.values()) else "partner"
        rows.append((min(row.get("on", inf), row.get("alone_on", inf)), row))
    now = ctx["world_time"]
    for _, row in rows:  # the hours dated only once sorted on: `now` for what already holds
        for key in ("alone_on", "on"):
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
def _build_roster(save: dict, island_of, kinds: set[str] | None, trait: str | None, land: int | None, since: str | None) -> list[dict] | dict:
    was = _lands_then(since) if since else None
    bodies = []
    for actor in save.get("actors_data") or []:
        if is_boat(actor) or (kinds and actor.get("asset_id") not in kinds) or (trait and trait not in (actor.get("saved_traits") or ())):
            continue
        here = island_of.get(actor_xy(actor))
        change: dict = {}
        if was is not None and actor["id"] in was:  # one unseen then was born or set down since, and says so by standing in the roll at all
            if (then := was[actor["id"]]) == here:
                continue  # stood still: nothing for `since` to say
            change = {"was_on": then if then is not None else _OFF_LAND}
        if land is None or land in (here, change.get("was_on")):
            bodies.append((actor, here, change))
    if len(bodies) > _MAX_ROSTER:
        counts = Counter(actor.get("asset_id") for actor, _, _ in bodies)
        return {"by_species": dict(counts.most_common()), "info": f"{len(bodies)} bodies — narrow them with -t, --trait or -i"}
    ctx = build_actor_stats_context(save)
    rows = []
    for actor, here, change in sorted(bodies, key=lambda body: (body[1] is None, body[1] or 0, body[0]["id"])):  # land by land, off every land last
        age, adult, breeding = actor_age(actor, ctx["world_time"]), adult_age(actor, ctx), breeding_age(actor, ctx)
        rows.append(
            {
                "adult_on": crossed_on(actor, adult) if age < adult else None,
                "asset_id": actor.get("asset_id"),
                "breeds_on": crossed_on(actor, breeding) if age < breeding else None,
                "id": actor["id"],
                "island_id": here if here is not None else _OFF_LAND,  # said outright, as `was_on` is: a missing one read as still on the land left
                "name": actor.get("name"),
                "sex": sex_label(actor),
                **change,
            }
        )
    return rows


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

    frozen, tiles = frozen_tally(save)
    return {
        **{k: len(save.get(coll) or []) for k, coll in _SNAPSHOT_COLLECTIONS.items()},
        "armies": len(save.get("armies") or []),
        "buildings": sum(n for aid, n in asset_counts.items() if aid in civic),  # Built structures worldwide (nature excluded); `houses` = dwellings.
        "frozen_pct": round(frozen / (tiles or 1) * 100),  # the map's frozen share, whole — permafrost, snow, ice and frost; `geography … totals` has the tenth
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


# Each year's gains: a blank cell carries, a missing year was quiet, and a ~20-year window past year 1 opens on a baseline — a count seen after it dates nothing.
def _build_timeline(map_stats: dict) -> list[dict]:
    year = int(float(map_stats.get("world_time") or 0) // UNITS_PER_YEAR) + 1
    try:
        with sqlite3.connect(f"file:{HISTORY_S3DB}?mode=ro", uri=True) as conn:
            conn.row_factory = sqlite3.Row
            # WB writes a year's row as it closes, and the s3db is the latest save's: the years before this save's own, never one run on past it.
            cursor = conn.execute("SELECT * FROM WorldYearly1 WHERE timestamp < ? ORDER BY timestamp", (year,))
            rows, names = cursor.fetchall(), [column for column, *_ in cursor.description]
    except sqlite3.Error:  # no copy yet, or a table WB has not written
        return []
    counters = {_YEARLY_RENAMED.get(column, column): column for column in names if _EVENT_COLUMN.search(column) or column in _EVENT_EXTRAS}
    stats = {**{column: _camel(column) for column in counters.values()}, **{column: _DEATH_CAUSES[cause] for cause, column in _YEARLY_DEATHS.items()}}
    held: dict[str, int | None] = dict.fromkeys(stats, 0 if not rows or rows[0]["timestamp"] == 1 else None)
    timeline = []
    for row in rows:
        now = {column: held[column] if row[column] is None else int(row[column]) for column in stats}
        timeline += _year_gains(row["timestamp"], held, now, counters)
        held = now
    # The year under way, which has no row yet: the save's own tallies over the last year closed, marked `so_far`.
    return timeline + _year_gains(year, held, {column: int(map_stats.get(stat) or 0) for column, stat in stats.items()}, counters, so_far=True)


# A `WorldYearly1` column's `mapStats` twin, the same tally in camelCase — the deaths, snake-cased there too, go through `_DEATH_CAUSES` instead.
def _camel(column: str) -> str:
    return re.sub(r"_(\w)", lambda m: m.group(1).upper(), column)


def _count_leaders(counts: Counter, records: list[dict], min_peers: int) -> list[dict]:
    return [{"id": eid, "name": _name_of(records, eid), "value": n} for eid, n in first_place(counts, min_peers)]


# A count's rise between two readings, 0 where the earlier one is unknown — a window opened past year 1 holds the total, never the year it grew in.
def _gain(before: int | None, after: int | None) -> int:
    return after - before if before is not None and after is not None else 0


# The land each body stood on in an earlier chapter's save, for `--since`: the one fact the roster weighs against it.
def _lands_then(chapter: str) -> dict[int, int | None]:
    then_path = SAVES_DIR / chapter / "map.wbox"
    then = load_save(then_path)
    island_of = compute_islands_cached(then, then_path)[1]
    return {actor["id"]: island_of.get(actor_xy(actor)) for actor in then.get("actors_data") or [] if not is_boat(actor)}


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


# The subspecies WB hangs `has_sapience` on, as a set of ids — an allegiance is not a mind, and a world can think long before it crowns anyone.
def _sapient_subspecies(save: dict) -> frozenset:
    return frozenset(sid for sid, sub in index_by_id(save.get("subspecies") or []).items() if is_sapient(sub))


# Whoever holds the composite's first place, `{id, name}` alone: a Borda total climbs with every rival, so the points never travel.
def _score_leaders(totals: Counter, records: list[dict]) -> list[dict]:
    field = {r["id"]: totals[r["id"]] for r in records}  # every town or crown a rival, the ones `score_totals` credits nothing included
    return [{"id": eid, "name": _name_of(records, eid)} for eid, _ in first_place(field, MIN_SCORE_PEERS)]


# A year's entry, none where nothing moved: its gains under `cumulative`'s names, its deaths by cause — `so_far` on the one still under way.
def _year_gains(year: int, held: dict, now: dict, counters: dict[str, str], so_far: bool = False) -> list[dict]:
    gains = {key: gain for key, column in counters.items() if (gain := _gain(held[column], now[column]))}
    deaths = {cause: gain for cause, column in _YEARLY_DEATHS.items() if (gain := _gain(held[column], now[column]))}
    return [{"year": year, **gains, **({"deaths": deaths} if deaths else {}), **({"so_far": True} if so_far else {})}] if gains or deaths else []


def main(argv: list[str]) -> int:
    try:
        since, argv = take_since(argv)
    except ValueError as e:
        print(f"✗ {e}", file=sys.stderr)
        return 2
    save_path, argv, _ = take_chapter(argv)
    parser = arg_parser(prog="world/info.py", description="World-wide sections, from the save alone.")
    parser.add_argument("sections", nargs="?", help=f"Comma-separated sections, `full` by default. Valid: {', '.join((*_ALL_SECTIONS, *_ON_REQUEST))}")
    parser.add_argument("--island", "-i", type=int, metavar="id", help="`roster`: the bodies standing on one land")
    parser.add_argument("--trait", help="`roster`: the bodies bearing one trait, by its id")
    parser.add_argument("--type", "-t", help="`roster`: one kind, a family (`actors`) or a comma list")
    args = parser.parse_args(argv)
    requested = args.sections
    try:
        sections = parse_sections(requested, (*_ALL_SECTIONS, *_ON_REQUEST))
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 2
    if not requested or requested == "full":
        sections = _ALL_SECTIONS
    narrowing = args.type or args.trait or args.island is not None or since
    if narrowing and "roster" not in sections:  # refused before the save is read, as a flag that would go unheard
        print("✗ -t, --trait, -i and --since narrow `roster`: name it", file=sys.stderr)
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
        if args.island is not None and args.island not in {land["id"] for land in lands}:
            print(f"✗ no land with id {args.island} — `geography … islands` lists them", file=sys.stderr)
            return 2
        if args.trait and args.trait not in load_data("creature-traits.json"):
            print(f"✗ no trait {args.trait} — `actor <id> traits` gives the ids", file=sys.stderr)
            return 2
        if not (roster := _build_roster(save, island_of, kinds, args.trait, args.island, since)):  # a filter nothing answers, never a silent `{}`
            why = f"bears {args.trait}" if args.trait else "matches — a family of buildings (`trees`…) holds none, `geography … entity_types` lists the kinds"
            print(f"✗ no living body {why}", file=sys.stderr)
            return 1
        out["roster"] = roster
    if "snapshot" in sections:
        out["snapshot"] = _build_snapshot(save)
    if "timeline" in sections:
        out["timeline"] = _build_timeline(map_stats)

    emit(out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
