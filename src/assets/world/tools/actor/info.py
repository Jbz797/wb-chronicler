#!/usr/bin/env python3

# User-facing docs (usage, available sections) live in `docs/tools.md`. Notes below are for maintainers — algorithm references, gotchas, source pointers.

import sys
from collections import Counter, defaultdict
from collections.abc import Callable
from functools import cache
from math import inf
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))

from actor_stats import actor_stat_totals, adult_age, breeding_age, build_actor_stats_context, compute_actor_stats, hatch_months, is_baby, is_egg
from grid import LazyTileGrid, off_land
from islands import compute_islands_cached
from shared import (
    PROFESSION_KING,
    PROFESSION_LEADER,
    UNITS_PER_MONTH,
    UNITS_PER_YEAR,
    ZONE_TILES,
    actor_age,
    actor_xy,
    bearing,
    build_trait_ids,
    build_trait_list,
    building_tile,
    civic_building_ids,
    competition_ranks,
    emit,
    entity_ref,
    equipment_entry,
    equipment_rarity,
    has_emotions,
    index_by_id,
    is_aboard,
    is_boat,
    is_sapient,
    is_transport,
    life_stage,
    light,
    load_data,
    load_save,
    needs_food,
    parse_sections,
    resolve_profession,
    sex_label,
    take_chapter,
    walk_tiles,
    wants_detail,
    world_date,
    world_laws,
    zone_xy,
)
from walking import Gait, WalkMap, walk_from, walk_way
from waters import waters_cached

_ALL_SECTIONS = ("companions", "gear", "inventory", "metadata", "plot", "ranks_in_species", "stats", "surroundings", "traits")
_BABY_MASS_MULTIPLIER = 0.4  # WB `SimGlobalAsset.baby_mass_multiplier`: what a child weighs of the body it will grow into
_BOAT_REACH = 240  # chronicler.md « La mer ne coupe que… »: a transport boat carries the common reach this far across the sea

# WB `TopTileLibrary`: the biomes any lineage may found on, and those only a meta tag opens — `corrupted` alone spelt apart from its tag.
_BUILD_FREE = (
    "birch",
    "candy",
    "celestial",
    "clover",
    "crystal",
    "enchanted",
    "flower",
    "garlic",
    "grass",
    "jungle",
    "lemon",
    "maple",
    "mushroom",
    "paradox",
    "rocklands",
    "savanna",
    "singularity",
)

_BUILD_TAGS = {"corrupted": "corruption", "desert": "desert", "infernal": "infernal", "permafrost": "permafrost", "swamp": "swamp", "wasteland": "wasteland"}
_CIRCLES = (("intimate", 25), ("common", 120))  # chronicler.md's tiers by distance, in tiles — past the last lies the far-off, which no roster could hold
_CITY_WAVE = 3  # WB `CityPlaceFinder.startWave`: the zones a town keeps founders off, counted from its edge across its own land
_CLAN_CHIEF_ROLE = ("chief_id", "clans", "past_chiefs")  # Chieftainship is a role, not a profession (a king can be both) — hence its own tenure field.
_DAILY_TILES_PER_SPEED = 25.0  # chronicler.md § Échelle: `speed` 10 walks ~250 tiles a day, its halts counted — far short of 24 hours' worth
_DROWNING_PER_SECOND = 2.0  # the `drowning` status takes one point of health every 0.5s, and no armour blunts it — WB spares armour for blows alone

# WB `TileLibrary`: the base tiles a zone counts as ground, all 64 of which `canStartCityHere` wants — the hill left out, ground though it is, as it bars the zone.
_GROUND_BASES = frozenset({"pit_close_ocean", "pit_deep_ocean", "pit_shallow_waters", "sand", "soil_high", "soil_low"})

_HOURLY_TILES_PER_SPEED = 4.0  # chronicler.md § Échelle: `speed` 10 walks ~40 tiles an hour, so a pace twice as quick halves the time
_ISSUE_BACKDATE = 10 * UNITS_PER_YEAR  # WB `Actor.createNewWeapon` → `generateItem(…, 10, …)`: the weapon a body arrives with is stamped ten years before it
_NEW_BABY_NUTRITION = 50  # WB `SimGlobalAsset.nutrition_cost_new_baby`: what a body must still carry to feed one more mouth.
_POSTS = {PROFESSION_KING: "king", PROFESSION_LEADER: "leader"}  # the `job` a crown or a town's head holds, labelled as `resolve_profession` labels it

# Competition rank (1,2,2,4) per stat among `asset_id` peers. Mostly maps to `RankedStatKind` (types.ts; UI: RankedStatComponent). `births` chronicler-only.
_RANKED_STATS = {
    "armor",
    "attack_speed",
    "birth_rate",
    "births",
    "children",
    "critical_chance",
    "damage_max",
    "damage_min",
    "diplomacy",
    "equipment_power",
    "health_max",
    "intelligence",
    "kills",
    "level",
    "lifespan",
    "loot",
    "mana_max",
    "money",
    "renown",
    "speed",
    "stamina_max",
    "stewardship",
    "warfare",
}

_RARITY_POINTS = {"Epic": 3, "Legendary": 4, "Normal": 1, "Rare": 2}  # WB's own ladder, weighing a carried arsenal into the « puissance » gauge.

# UI order: active roles (chief, alpha) before historical foundations (creators before founders). `army_captain` is a `profession`, not a role.
_ROLE_ORDER = (
    "clan_chief",
    "family_alpha",
    "culture_creator",
    "language_creator",
    "religion_creator",
    "alliance_founder",
    "clan_founder",
    "village_founder",
    "family_founder",
)

_SCALE_UNIT = 0.1  # `getMassKG` divides the body's own `scale` by it, so a species drawn at 0.25 weighs two and a half times its `mass_2`

# WB `TopTileLibrary`: the tiles `checkCanSettleInThisBiomes` weighs, each with the meta tag a lineage must bear to build there — `None` where any may.
_SETTLE_BIOMES = {
    **dict.fromkeys(f"{biome}_{height}" for biome in _BUILD_FREE for height in ("high", "low")),
    **{f"{biome}_{height}": f"can_build_in_biome_{tag}" for biome, tag in _BUILD_TAGS.items() for height in ("high", "low")},
    **dict.fromkeys(("ice", "snow_block", "snow_hills", "snow_sand", "snow_summit"), "can_build_in_biome_permafrost"),  # permafrost's frosts, cloned off it
    "sand": None,
}

_SETTLE_ISLAND = 300  # WB `CityPlaceFinder.prepareBasicZones`: the fewest tiles a land needs before a zone of it may found a town
_SETTLE_SOIL = frozenset({"soil_high", "soil_low"})  # bare soil, which the weighing counts apart and then offsets by everything grown over it
_SPENT_BREATH_PACE = 0.4  # WB's own multiplier for a body out of breath: it still swims, at two fifths of its pace
_STAMINA_PER_SECOND = 10.0  # `spendStaminaWithCooldown` takes 1 to 5 points every 0.3s — `Randy.randomInt` leaves its top out, so three on average

# Profession → (current-holder field, save collection, history list). Every post keeps a `past_*` history whose last entry is the sitting holder's start.
_TENURE_ROLES = {
    "army_captain": ("id_captain", "armies", "past_captains"),
    "king": ("kingID", "kingdoms", "past_rulers"),
    "leader": ("leaderID", "cities", "past_rulers"),
}

_TILES_PER_SPEED = 0.2  # tiles a second per point of `speed`: WB's own 0.4 step, halved by the world's `unit_speed_multiplier`


# A `--to` no walk answers: its message says what bars the way, the water's width against the body's reach where the sea is to blame.
class _Unreachable(Exception):
    pass


# Who bears when two make one, per WB `BehCheckForBabiesFromSexualReproduction`: a sexed pair's female `True`, its male `False`, a hermaphrodite `None` (by lot).
def _bears(actor: dict, ctx: dict) -> bool | None:
    biology = _biology(actor, ctx)
    if "reproduction_sexual" in biology:
        return actor.get("sex") == 1
    return None if "reproduction_hermaphroditic" in biology else True  # a lone breeder bears its own


# The traits a body's lineage carries — what its breeding, its gait and its swim are each read off.
def _biology(actor: dict, ctx: dict) -> tuple | list:
    return (ctx["subspecies_by_id"].get(actor.get("subspecies")) or {}).get("saved_traits") or ()


# The tags a body walks and swims by, off its biology's traits and its clan's: `walk_adaptation_*`, `fast_swimming`, `water_creature`.
def _body_tags(actor: dict, biology: tuple | list, ctx: dict) -> frozenset[str]:
    sources = ((biology, ctx["subspecies_traits"]), ((ctx["clans_by_id"].get(actor.get("clan")) or {}).get("saved_traits") or (), ctx["clan_traits"]))
    return frozenset(tag for traits, library in sources for trait in traits for tag in (library.get(trait) or {}).get("tags") or ())


# One home for every index the sections read, so no caller rolls its own. Actor loop = one pass: id, asset_id, children-per-parent (`get_current_children_count`).
def _build_context(save: dict, save_path: Path) -> dict:
    actors_by_asset: defaultdict[str, list[dict]] = defaultdict(list)
    actors_by_id: dict[int, dict] = {}
    children_by_parent: dict[int, int] = {}
    ferrying: set[int] = set()
    for actor in save.get("actors_data") or []:
        asset = actor.get("asset_id")
        actors_by_id[actor["id"]] = actor
        actors_by_asset[asset].append(actor)
        if is_transport(actor) and (kid := actor.get("civ_kingdom_id")):
            ferrying.add(kid)
        # Unrolled: the pair literal rebuilt a tuple per actor. A `Counter` here would read cleaner but measures some 60 % slower than `dict.get` on this pattern.
        if parent := actor.get("parent_id_1"):
            children_by_parent[parent] = children_by_parent.get(parent, 0) + 1
        if parent := actor.get("parent_id_2"):
            children_by_parent[parent] = children_by_parent.get(parent, 0) + 1
    islands = cache(lambda: compute_islands_cached(save, save_path))
    return {
        **build_actor_stats_context(save),
        "actors_by_asset": actors_by_asset,
        "actors_by_id": actors_by_id,
        "alliances_by_id": index_by_id(save.get("alliances") or []),
        "buildings_by_tile": cache(lambda: _buildings_by_tile(save)),  # called not stored: `metadata` alone asks, and the walk covers every building of the world
        "children_by_parent": children_by_parent,
        "cities_by_id": index_by_id(save.get("cities") or []),
        "clan_chiefs": frozenset(chief for c in save.get("clans") or [] if (chief := c.get("chief_id"))),
        "cultures_by_id": index_by_id(save.get("cultures") or []),
        "families_by_id": index_by_id(save.get("families") or []),
        "ferrying_kingdoms": ferrying,  # the crowns a transport boat serves: only their people reach, and are measured, past the common circle
        "city_zones": cache(lambda: _city_zones(save, islands()[1])),  # called not stored: `settle` alone asks, and only of a thinking soul
        "island_lookup": cache(lambda: islands()[1]),  # tile → island id, called not stored: `metadata` and `surroundings` alone ask
        "island_sizes": cache(lambda: {land["id"]: land["size"] for land in islands()[0]}),
        "kingdoms_by_id": index_by_id(save.get("kingdoms") or []),
        "pact_of": {kid: a["id"] for a in save.get("alliances") or [] for kid in a.get("kingdoms") or []},  # a realm sits in one pact at most
        "religions_by_id": index_by_id(save.get("religions") or []),
        # Called not stored: only a `--to` the water bars asks, to say how wide it is, and the sweep of the water costs a second on a save not yet cached.
        "strait_gaps": cache(lambda: {tuple(s["between"]): s["gap"] for s in waters_cached(save, save_path)["straits"]}),
        "tile_grid": cache(lambda: LazyTileGrid(save)),  # rows decoded as read: `settle` reads a zone's eight
        "tile_map": save["tileMap"],
        "walk_map": cache(lambda: WalkMap(save)),  # called not stored: `surroundings` and `--to` alone walk
        "world_laws": world_laws(save),
    }


# Each carried item — provenance, wear, kills, stats folded — by id; the weapon a body arrived with says `with_bearer`, WB backdating its age by ten years
def _build_gear(actor: dict, ctx: dict) -> list:
    item_stats = ctx["equipment"]["items"]
    mod_stats = ctx["equipment"]["modifiers"]
    world_time, arrived = ctx["world_time"], float(actor.get("created_time") or 0)
    gear = []
    for iid in actor.get("saved_items") or []:
        if (item := ctx["items_by_id"].get(iid)) is None:
            continue
        entry = equipment_entry(item, item_stats, mod_stats, world_time, described=True)
        # Exactly its bearer's arrival less the backdate, the save's floats drifting in the sixth place: proof, where a mere `by` left blank is not.
        if (created := item.get("created_time")) is not None and abs(float(created) + _ISSUE_BACKDATE - arrived) < 0.01:
            entry["age"], entry["with_bearer"] = None, True
        gear.append(entry)
    return sorted(gear, key=lambda i: i["id"])


# Resource bag → `{resource_id: amount}`, heaviest stack first then alphabetical — the raw save nests it as `inventory.dict.<id>.amount`.
def _build_inventory(actor: dict) -> dict:
    items = ((actor.get("inventory") or {}).get("dict") or {}).items()
    return dict(sorted(((iid, entry.get("amount", 0)) for iid, entry in items), key=lambda kv: (-kv[1], kv[0])))


# The actor's identity card: civic ties (city/kingdom/culture/family…), body (age tier, mass), posts held and their tenure.
def _build_metadata(actor: dict, ctx: dict, save: dict) -> dict:
    snap = compute_actor_stats(actor, ctx)
    lifespan = snap.get("lifespan", 0)
    age = actor_age(actor, ctx["world_time"])

    # Both off the biology, as WB writes them onto the subspecies — never off this body's own span. `age_adult` is nil where no baby form was ever drawn.
    age_adult, age_breeding = adult_age(actor, ctx), breeding_age(actor, ctx)
    tile = actor_xy(actor)
    profession = resolve_profession(actor, save)

    # WB `Actor.canBreed` asks every partner its age and reserve, a gut-less body fed by definition; `infertile` and the cap stop the one who must bear alone.
    can_reproduce = (
        age >= age_breeding
        and (not needs_food(ctx["subspecies_by_id"].get(actor.get("subspecies"))) or int(actor.get("nutrition") or 0) >= _NEW_BABY_NUTRITION)
        and (
            _bears(actor, ctx) is not True
            or ("infertile" not in (actor.get("saved_traits") or []) and ctx["children_by_parent"].get(actor.get("id"), 0) < int(snap.get("max_children") or 0))
        )
    )

    island_lookup = ctx["island_lookup"]()

    return {
        # Chronicler-only, and only while it still bites: the age WB gives the child its halved `damage_max`/`health_max` back at — a bridling, not an infirmity.
        **({"adult_age": round(age_adult, 1)} if age < age_adult else {}),
        "age": age,
        # A pact reaches him through his crown, WB tying one to a realm and never to a soul — the ref lets `new.py` fan out on it like any other body.
        "alliance": entity_ref(ctx["pact_of"].get(actor.get("civ_kingdom_id")), ctx["alliances_by_id"]),
        "asset_id": actor.get("asset_id"),
        "born": world_date(actor.get("created_time") or 0),  # the month WB set it on the map, dated as the chronicle dates: who came first, and when
        # Chronicler-only, and only while it still bites: the age WB opens a body's own line at — `adult_age` lifts a bridling and lets it found a town, never bear.
        **({"breeding_age": round(age_breeding, 1)} if age < age_breeding else {}),
        # Said only when they hold, as every flag the tools emit: a body that cannot is most of the world, beasts and children first.
        **({"can_reproduce": True} if can_reproduce else {}),
        "city": entity_ref(actor.get("cityID"), ctx["cities_by_id"]),
        "clan": entity_ref(actor.get("clan"), ctx["clans_by_id"]),  # a ref, not a bare name: `clan/info.py <id>` can be called on it, as on `family`
        "clan_chief_years": _resolve_tenure(actor, _CLAN_CHIEF_ROLE, save, ctx["world_time"]),  # Chronicler-only: a role, so it stacks with `tenure_years`.
        "culture": entity_ref(actor.get("culture"), ctx["cultures_by_id"]),  # a ref like `clan`: `culture/info.py <id>` reads the customs it was raised in
        "family": entity_ref(actor.get("family"), ctx["families_by_id"]),  # a ref, not a bare name: `family/info.py <id>` can be called on it
        "favorite_food": actor.get("favorite_food"),
        "gen": int(actor.get("generation") or 1),  # WB counts a first child 2, so a parentless founder is its 1 — a default the save omits
        # Chronicler-only: the months a shell still owes, WB keeping no countdown on the egg — without it a hatching is a fact he can state but never date.
        **({"hatch_months": round(left, 1)} if (left := hatch_months(actor, ctx)) else {}),
        **({"home": home} if (home := actor.get("homeBuildingID")) else {}),  # Chronicler-only: WB names no roof — `ground/info.py <id>` takes the bare id
        "id": actor.get("id"),  # Actor id — lets the favourite's `<app-person-tag>` resolve its chip from the person registry like every other person ref.
        # Chronicler-only: enlistment is in the resident's own city army or nowhere, and never automatic — `false` marks a fighter left out.
        **({"in_army": bool(actor.get("army"))} if profession in ("army_captain", "warrior") or actor.get("army") else {}),
        # Standing on a building's own tile, which is as close as a save comes to saying « indoors »: WB keeps `is_inside_building` on the runtime actor alone.
        **({"in_building": {"asset_id": inside.get("asset_id"), "id": inside["id"]}} if (inside := ctx["buildings_by_tile"]().get(tile)) else {}),
        "island_id": island_lookup.get(tile),  # Chronicler-only: land mass (geography/info.py).
        "job": profession,
        "kingdom": entity_ref(actor.get("civ_kingdom_id"), ctx["kingdoms_by_id"]),
        "language": entity_ref(actor.get("language"), ctx["languages_by_id"]),  # a ref, not a bare name: `language/info.py <id>` reads the tongue it answers in
        "life_stage": life_stage(age, age_adult, lifespan, is_egg(actor, ctx)),
        "mass": _compute_mass(actor, ctx),
        "name": actor.get("name"),  # absent, not a placeholder, where WB never named them — `emit` strips it and the panels drop the row
        "personality": _compute_personality(actor, snap),
        "religion": entity_ref(actor.get("religion"), ctx["religions_by_id"]),  # a ref, not a bare name: `religion/info.py <id>` reads the creed it holds
        "roles": _compute_roles(actor, save),
        "sapient": is_sapient(ctx["subspecies_by_id"].get(actor.get("subspecies"))),  # tells a builder of cities from a beast, and gates his person tag
        # Chronicler-only, a thinker's alone: whether a town could rise where it stands, else what bars it — the zone weighed even for a child.
        **({"settle": settle} if (settle := _settle(actor, ctx)) is not None else {}),
        "sex": sex_label(actor),
        "subspecies": entity_ref(actor.get("subspecies"), ctx["subspecies_by_id"]),  # a ref, not a bare name: the chapter panel resolves its tag from the id
        "tenure_years": _resolve_tenure(actor, _TENURE_ROLES.get(profession or ""), save, ctx["world_time"]),
        # WB `isInsideSomething`: a save keeps the boat half, never the building. A plain ref, souls boarding transports alone — `boat/info.py <id>` spells it out.
        **({"transport": entity_ref(actor.get("transportID"), ctx["actors_by_id"])} if is_aboard(actor) else {}),
        "x": tile[0],
        "y": tile[1],
    }


# Actor's current plot — `actor.plot` points into `save.plots`. Returns `None` when no plot (most actors). Targets → kingdom/alliance names.
def _build_plot(actor: dict, ctx: dict, save: dict) -> dict | None:
    plot_id = actor.get("plot")
    if plot_id is None:
        return None
    plot = next((p for p in save.get("plots") or [] if p.get("id") == plot_id), None)
    if plot is None:
        return None
    type_id = plot.get("plot_type_id")
    kind = load_data("plots.json").get(type_id) or {}
    return {
        # Months, not years: a scheme ripens well inside one. WB never caps the gauge either, so a ripe plot reads past 100.
        "months": int((ctx["world_time"] - float(plot.get("created_time") or 0)) / UNITS_PER_MONTH),
        "progress": round(float(plot.get("progress_current") or 0), 1),
        "target_alliance": entity_ref(plot.get("id_target_alliance"), ctx["alliances_by_id"]),
        "target_city": entity_ref(plot.get("id_target_city"), ctx["cities_by_id"]),  # the rites strike a settlement where a war strikes a crown
        "target_kingdom": entity_ref(plot.get("id_target_kingdom"), ctx["kingdoms_by_id"]),
        # The scheme's kind, as a book carries its genre: WB's English for the chronicler, the id for the panel — the save's own `name` is that label localised.
        "type": {"description": kind.get("description"), "id": type_id, "name": kind.get("name")},
    }


# Every living body within the common reach, nearest first, walked at its own gait — a line is built only for a printed circle: `full` never makes the common one.
def _build_surroundings(actor: dict, ctx: dict, requested: str | None) -> dict:
    cx, cy = actor_xy(actor)
    circles: dict[str, list[tuple]] = {name: [] for name, _ in _CIRCLES}
    island_of = ctx["island_lookup"]()
    home = island_of.get((cx, cy))
    # A crown that ferries none reaches no shore: without a transport boat the sea stays the far-off, and no hull nor body past the common reach is measured.
    ferried = actor.get("civ_kingdom_id") in ctx["ferrying_kingdoms"]
    reach, common = _BOAT_REACH if ferried else _CIRCLES[-1][1], _CIRCLES[-1][1]
    walker = _walker(actor, ctx, common + 0.5)  # the ring keeps a walk that rounds to its edge, as `--to` rounds the same walk
    offshore: list[tuple] = []
    kin: dict[int, str] = {}
    ties = _ties(actor)
    for other in ctx["actors_by_id"].values():
        if other is actor:
            continue
        if boat := is_boat(other):
            if not ferried:
                continue
        elif ctx["subspecies_by_id"].get(other.get("subspecies")) is None:
            continue
        ox, oy = actor_xy(other)
        dx, dy = ox - cx, oy - cy
        # The crow's line first, on whole tiles: no walk is shorter, and a swift swimmer's circles stop at their radius all the same.
        if (crow := round(walk_tiles(dx, dy))) > reach:
            continue
        # His parents, children, siblings and mate stand in full wherever they live: a count by town would drop where they are, which no roster of theirs says.
        if not boat and (tie := _kin_tie(ties, other)):
            kin[other["id"]] = tie
        land = island_of.get((ox, oy))
        distance = None if boat else crow if walker is None else walker(ox, oy, land)
        if distance is not None and (distance := round(distance)) <= common:
            circles[next(name for name, radius in _CIRCLES if distance <= radius)].append((distance, other["id"], dx, dy, land))
        elif ferried and (boat or land != home):  # what only a hull brings in reach, as the crow flies: every boat, and every body off his land no walk reaches
            offshore.append((crow, other["id"], dx, dy, land))
    if ferried:
        circles["common_with_boat"] = offshore
    by_id = ctx["actors_by_id"]
    near = sorted(circles.pop("intimate"))
    rings: dict = {"intimate": [_surroundings_row(by_id[i], ctx, distance, dx, dy, home, land, kin.get(i)) for distance, i, dx, dy, land in near]}
    plans = {name: _surroundings_plan(entries, ctx, kin) for name, entries in circles.items()}
    if detailed := wants_detail(requested, sum(map(len, plans.values()))):
        rings.update({name: _surroundings_rows(plan, ctx, home, kin) for name, plan in plans.items()})
        # Each peopled ring's edge at his own pace, so none is told as a morning or a day it is not — an empty one needs none, and a hull sets a passenger's.
        if not is_aboard(actor) and (hours := {name: _walk_time(actor, radius, ctx)["hours"] for name, radius in _CIRCLES if rings.get(name)}):
            rings["hours"] = hours
    # An adult's line goes unmarked, most bodies standing there: said beside the rows, where a silence read alone passes for youth. A sexless hull has no stage.
    if any("sex" in row and "life_stage" not in row for ring in rings.values() if isinstance(ring, list) for row in ring):
        rings["life_stage_default"] = "adult"
    return rings if detailed else light(rings, withheld=True)  # `full` keeps the circle a chapter opens on, and says the wider ones wait to be named


# The walk to a body, a tile or a land's shore, at his own gait within his swim — a flyer, water-born or passenger goes as the crow flies, landing nearest.
def _build_to(actor: dict, aims: list[tuple[int, int]], whom: str, ctx: dict, land: int | None = None) -> dict:
    cx, cy = actor_xy(actor)
    island_of = ctx["island_lookup"]()
    gx, gy = goal = min(aims, key=lambda t: (t[0] - cx) ** 2 + (t[1] - cy) ** 2)
    to = _heading(cx, cy, gx, gy, land)
    if (gait := _gait(actor, ctx)) is None:  # its way is the straight line: said as a walk, so that no reader takes the silence for a sea it can't cross
        return {**to, "walked": to["tiles"], **_walk_time(actor, to["tiles"], ctx)}
    walk_map = ctx["walk_map"]()
    goals, home = {y * walk_map.width + x for x, y in aims}, island_of.get((cx, cy))
    # WB walks round the bays of his own land, and swims only toward another: an islet of his, small, is tried on foot before the water.
    shore = not walk_map.wet(cx, cy) and (home is None or home == island_of.get(goal))
    way = walk_way(walk_map, gait.ashore(), cx, cy, goals) if shore else None
    if way is None and not (shore and home is not None):
        way = walk_way(walk_map, gait, cx, cy, goals)
    if way is None:
        raise _Unreachable(_why_unreachable(actor, goal, whom, gait, to["tiles"], ctx))
    walked, water, widest, reached = way
    if land is not None:
        to = _heading(cx, cy, reached % walk_map.width, reached // walk_map.width, land)
    # What was swum, in hours as the whole; the widest crossing where it outruns his breath, both weighed in whole tiles as they print, lest 6 stand beside 6
    swum = {"swim_hours": _walk_time(actor, water, ctx)["hours"]} if water else {}
    past = gait.breath < inf and round(widest) > round(gait.breath)  # a tireless swimmer never runs short, whatever it crosses
    return {**to, **swum, **({"widest_crossing": round(widest)} if past else {}), "walked": round(walked), **_walk_time(actor, walked, ctx)}


# What the soul was born with, off WB's creature library — each trait and its rarity, then its effect and flavour once named, and whether this age lulls it.
def _build_traits(actor: dict, ctx: dict, detailed: bool) -> dict | list[dict]:
    sworn, library = actor.get("saved_traits") or [], ctx["creature_traits"]
    if not detailed:
        return light({"ids": build_trait_ids(sworn, library, "rarity")})
    asleep = ctx["era_dormant_traits"]  # the verdict `stats` already heeds: a gift bound to an age this one is not lends none of its stats
    return [{**trait, "dormant": True} if trait["id"] in asleep else trait for trait in build_trait_list(sworn, library)]


# Built structures by their tile, so `metadata` can name the roof a soul stands under. Nature files under `buildings` too, and nobody steps « inside » a field.
def _buildings_by_tile(save: dict) -> dict[tuple, dict]:
    civic = civic_building_ids()  # hoisted out of the comprehension, where the call stood once per building of the world
    return {tile: b for b in save.get("buildings") or [] if b.get("asset_id") in civic and (tile := building_tile(b)) is not None}


# Every zone a town holds, with the land its first tile stands on — the one WB spreads its founders' wave across.
def _city_zones(save: dict, island_of) -> list[tuple[int, int, int | None]]:
    zones = []
    for city in save.get("cities") or []:
        if held := city.get("zones") or []:
            fx, fy = zone_xy(held[0])
            land = island_of.get((fx * ZONE_TILES + ZONE_TILES // 2, fy * ZONE_TILES + ZONE_TILES // 2))
            zones += [(*zone_xy(zone), land) for zone in held]
    return zones


# `Actor.getMassKG`: (`scale` / 0.1) × `mass_2`, cut to two fifths on a child. Both stats ride off the pipeline, where the traits and multipliers have had their say.
def _compute_mass(actor: dict, ctx: dict) -> int | None:
    totals = actor_stat_totals(actor, ctx)
    if (base := totals.get("mass_2")) is None:
        return None
    mass = int(base * (totals.get("scale") or 0) / _SCALE_UNIT)
    return int(mass * _BABY_MASS_MULTIPLIER) if is_baby(actor, ctx) else mass


# `Actor.updateStats` personality: city leaders/kings only → diplomat/administrator/militarist/balanced (diplomacy/stewardship/warfare); `wildcard` never used.
def _compute_personality(actor: dict, snap: dict) -> str | None:
    if actor.get("profession") not in (PROFESSION_KING, PROFESSION_LEADER):
        return None
    diplo, stew, war = snap.get("diplomacy", 0), snap.get("stewardship", 0), snap.get("warfare", 0)
    p, max_val = "balanced", diplo
    if diplo > stew:
        p, max_val = "diplomat", diplo
    elif diplo < stew:
        p, max_val = "administrator", stew
    if war > max_val:
        p = "militarist"
    return p


# Top 3 only — UI hides the rest, no narrative use for "34th out of 114". Zero-skip like the city/kingdom ranks: no podium for a stat the actor has none of.
def _compute_ranks_in_species(actor: dict, ctx: dict) -> dict:
    same_species = ctx["actors_by_asset"].get(actor.get("asset_id"), [])
    peers = [_compute_stats(a, ctx) for a in same_species]
    own = next(s for a, s in zip(same_species, peers) if a["id"] == actor["id"])

    getters = {stat: lambda s, st=stat: s.get(st, 0) for stat in _RANKED_STATS if stat in own}  # `st=stat` binds now, else every lambda reads the last one
    ranks = competition_ranks(own, peers, getters)
    # Age is not in `_compute_stats` (derived from `created_time`) — ranked separately, against the raw actors.
    ranks.update(competition_ranks(actor, same_species, {"age": lambda a: actor_age(a, ctx["world_time"])}))
    return ranks


# Active/historical roles in `_ROLE_ORDER` — each is a linear probe of its collection (all tiny).
def _compute_roles(actor: dict, save: dict) -> list[str]:
    actor_id = actor.get("id")
    checks = {
        "alliance_founder": any(a.get("founder_actor_id") == actor_id for a in save.get("alliances") or []),
        "clan_chief": any(c.get("chief_id") == actor_id for c in save.get("clans") or []),
        "clan_founder": any(c.get("founder_actor_id") == actor_id for c in save.get("clans") or []),
        "culture_creator": any(c.get("creator_id") == actor_id for c in save.get("cultures") or []),
        "family_alpha": any(f.get("alpha_id") == actor_id for f in save.get("families") or []),
        "family_founder": any(f.get("main_founder_id_1") == actor_id or f.get("main_founder_id_2") == actor_id for f in save.get("families") or []),
        "language_creator": any(lang.get("creator_id") == actor_id for lang in save.get("languages") or []),
        "religion_creator": any(r.get("creator_id") == actor_id for r in save.get("religions") or []),
        "village_founder": any(c.get("founder_id") == actor_id for c in save.get("cities") or []),
    }
    return [role for role in _ROLE_ORDER if checks[role]]


# `compute_actor_stats` hands back the cleaned pipeline — what the save carries on the body is appended here: the five vitals always, life's tallies above nought.
def _compute_stats(actor: dict, ctx: dict) -> dict:
    cleaned = compute_actor_stats(actor, ctx)
    if not cleaned:
        return {}
    if _bears(actor, ctx) is False:  # a sire's `offspring` only bars him from starting — his mate starts in his stead, so no count of his says what he can father
        cleaned.pop("max_children", None)
    cleaned.update(
        {
            # Life's tallies, silent at nought as every other stat is: a soul that has killed nobody and owns nothing says so by carrying none of them.
            **({"births": n} if (n := int(actor.get("births") or 0)) else {}),
            **({"children": n} if (n := ctx["children_by_parent"].get(actor.get("id"), 0)) else {}),
            **({"equipment_power": n} if (n := _equipment_power(actor, ctx)) else {}),
            # WB happiness runs -100..+100, surfaced as the 0-100 % the UI shows — and dropped whole where the biology has no `amygdala`, feeling nothing at all.
            **({"happiness": (int(actor.get("happiness") or 0) + 100) // 2} if has_emotions(actor, ctx["subspecies_by_id"]) else {}),
            "health": int(actor.get("health") or 0),
            **({"kills": n} if (n := int(actor.get("kills") or 0)) else {}),
            "level": max(int(actor.get("level") or 0), 1),  # WB displays level 1 as the floor, even when the raw save field is absent / 0.
            **({"loot": n} if (n := int(actor.get("loot") or 0)) else {}),
            "mana": int(actor.get("mana") or 0),
            **({"money": n} if (n := int(actor.get("money") or 0)) else {}),
            "nutrition": int(actor.get("nutrition") or 0),
            **({"renown": n} if (n := int(actor.get("renown") or 0)) else {}),
            "stamina": int(actor.get("stamina") or 0),
        }
    )
    return cleaned  # left as inserted: `render` sorts every record-shaped dict on the way out, and a ranking's peers are only ever read by key


# Sum of `_RARITY_POINTS` over carried items — the « puissance d'équipement » gauge.
def _equipment_power(actor: dict, ctx: dict) -> int:
    items = ctx["items_by_id"]
    total = 0
    for iid in actor.get("saved_items") or []:
        item = items.get(iid)
        if item:
            total += _RARITY_POINTS[equipment_rarity(item.get("modifiers") or [])]
    return total


# How this body walks, or `None` for one the ground never holds — a flyer, a body born to the water, one aboard a hull: all keep the crow's line.
def _gait(actor: dict, ctx: dict) -> Gait | None:
    biology = _biology(actor, ctx)
    tags = _body_tags(actor, biology, ctx)
    if _water_free(actor, tags, ctx) or is_aboard(actor):
        return None
    # The cleaned stats, not the raw totals: a child walks and swims on the halved ceiling WB gives it.
    stats, aloft, swift = compute_actor_stats(actor, ctx), "hovering" in biology, "fast_swimming" in tags
    breath, reach = _swim_reach(actor, stats, biology, aloft, swift)
    blind = bool(_species(actor, ctx).get("ignore_tile_speed_multiplier"))  # WB `ActorAsset`: every ground at one pace
    return ctx["walk_map"]().gait(stats.get("speed"), tags, aloft=aloft, blind=blind, swift=swift, breath=breath, reach=reach)


# The bearing and the crow's tiles to a point — and that point as its `landing`, where the goal is a whole land.
def _heading(cx: int, cy: int, gx: int, gy: int, land: int | None) -> dict:
    to = {"dir": bearing(gx - cx, gy - cy), "tiles": round(walk_tiles(gx - cx, gy - cy))}
    return {**to, "landing": {"x": gx, "y": gy}} if land is not None else to


# The actor's tie to another body, or `None`, off his `_ties`: WB keeps two parents and one mate each — a child names him, a sibling shares a parent.
def _kin_tie(ties: tuple[int, frozenset[int], int | None], other: dict) -> str | None:
    aid, parents, lover = ties
    lineage = (other.get("parent_id_1"), other.get("parent_id_2"))
    if other["id"] in parents:
        return "parent"
    if aid in lineage:
        return "child"
    if other["id"] == lover or other.get("lover") == aid:
        return "lover"
    return "sibling" if not parents.isdisjoint(lineage) else None


# How a body is named in a refusal: its name, or its kind where it has none, and its id either way.
def _named(body: dict) -> str:
    return f"{body.get('name') or body.get('asset_id')} ({body['id']})"


# Where a body off every counted land stands, an islet told by its ground or the water — the grid decoded for its row alone, for the lines that need it.
def _off_land_at(body: dict, ctx: dict) -> dict:
    x, y = actor_xy(body)
    if off_land(ctx["tile_map"][ctx["tile_grid"]()[y][x]]) == "water":
        return {"water": True}
    return {"islet_tiles": ctx["island_lookup"]().islet_size((x, y))}


# Years the actor has held `role` = (holder field, collection, history). `None` unless the history's last entry still names them.
def _resolve_tenure(actor: dict, role: tuple[str, str, str] | None, save: dict, world_time: float) -> int | None:
    if role is None:
        return None
    holder_field, collection, history = role
    actor_id = actor.get("id")
    for record in save.get(collection, []):
        if record.get(holder_field) != actor_id:
            continue
        entries = record.get(history) or []
        if entries and entries[-1].get("id") == actor_id:
            return int((world_time - float(entries[-1].get("timestamp_ago") or 0)) / UNITS_PER_YEAR)
    return None


# WB `try_to_start_new_civilization` for a thinker: `True` where every gate opens, else each that shuts it — the zone weighed for a child too, who founds once grown.
def _settle(actor: dict, ctx: dict) -> bool | list[str] | None:
    subspecies = ctx["subspecies_by_id"].get(actor.get("subspecies"))
    if not is_sapient(subspecies):
        return None
    gates = (
        ("child", is_baby(actor, ctx)),
        # A trait that binds its bearer to a crown of its own (WB `is_forced_by_trait`), which `canStartNewCityCivilizationHere` turns away.
        ("forced_kingdom", any((ctx["creature_traits"].get(trait) or {}).get("forced_kingdom") for trait in actor.get("saved_traits") or ())),
        ("has_city", actor.get("cityID")),
        ("king", actor.get("profession") == PROFESSION_KING),
    )
    shut = [gate for gate, holds in gates if holds]
    if not ctx["world_laws"].get("world_law_kingdom_expansion", True):
        shut.append("law_off")
    x, y = actor_xy(actor)
    zx, zy = x // ZONE_TILES, y // ZONE_TILES
    land = ctx["island_lookup"]().get((zx * ZONE_TILES + ZONE_TILES // 2, zy * ZONE_TILES + ZONE_TILES // 2))  # WB reads the zone's centre tile
    if land is None or ctx["island_sizes"]().get(land, 0) < _SETTLE_ISLAND:
        shut.append("small_land")
    elif any(town == land and abs(tx - zx) + abs(ty - zy) <= _CITY_WAVE for tx, ty, town in ctx["city_zones"]()):
        shut.append("town_near")
    tags = frozenset(tag for trait in _biology(actor, ctx) for tag in (ctx["subspecies_traits"].get(trait) or {}).get("tags") or ())
    names, grid = ctx["tile_map"], ctx["tile_grid"]()
    ground = soil = fit = unfit = 0
    for row in range(zy * ZONE_TILES, (zy + 1) * ZONE_TILES):
        for tile in grid[row][zx * ZONE_TILES : (zx + 1) * ZONE_TILES]:
            base, _, top = names[tile].partition(":")
            ground += base in _GROUND_BASES
            for kind in (base, top):  # a zone weighs both layers of a tile, WB filing each under its own type
                if kind in _SETTLE_SOIL:
                    soil += 1
                elif kind in _SETTLE_BIOMES:
                    if (need := _SETTLE_BIOMES[kind]) is None or need in tags:
                        fit += 1
                    else:
                        unfit += 1
    if ground < ZONE_TILES * ZONE_TILES:  # a zone is 8 × 8, and every tile of it must be ground
        shut.append(f"ground {ground}/{ZONE_TILES * ZONE_TILES}")
    soil -= fit + unfit  # WB `checkCanSettleInThisBiomes`: the bare soil left once every grown tile is offset
    if not (soil > unfit or unfit <= fit):
        shut.append("biomes")
    return shut or True


# The body's own species record in `species.json` — WB's `ActorAsset` flags that no save carries.
def _species(actor: dict, ctx: dict) -> dict:
    return ctx["species_data"].get(actor.get("asset_id")) or {}


# A wide circle, nearest first: kin, killer, named beast, crown or wanderer as its entry, the rest as a group per town or kind — so `full` counts lines unwritten.
def _surroundings_plan(entries: list[tuple], ctx: dict, kin: dict[int, str]) -> list[tuple | dict]:
    by_id, chiefs = ctx["actors_by_id"], ctx["clan_chiefs"]
    groups: dict[tuple, dict] = {}
    plan: list[tuple | dict] = []  # the entries come sorted, so a group stands where its nearest member was met, and nothing is re-sorted
    for entry in sorted(entries):
        distance, i, dx, dy, _ = entry
        other = by_id[i]
        sapient = not is_boat(other) and is_sapient(ctx["subspecies_by_id"][other["subspecies"]])
        city = other.get("cityID") if sapient else None
        charged = other.get("profession") in _POSTS or i in chiefs
        if other.get("kills") or charged or i in kin or (city is None if sapient else other.get("name")):
            plan.append(entry)
            continue
        key = ("city", city) if sapient else ("asset_id", other.get("asset_id"))
        if (group := groups.get(key)) is None:
            head = {"city": entity_ref(city, ctx["cities_by_id"]), "species": Counter()} if sapient else {"asset_id": key[1]}
            group = groups[key] = {**head, "count": 0, "first": entry, "nearest": {"dir": bearing(dx, dy), "distance": distance}}
            plan.append(group)
        group["count"] += 1
        if sapient:
            group["species"][other.get("asset_id")] += 1
    return plan


# One line of `surroundings`: silent on his own land, off it the land's id — or `water` or `islet_tiles` off every counted land, where a bare null reads as home.
def _surroundings_row(other: dict, ctx: dict, distance: int, dx: int, dy: int, home: int | None, land: int | None, tie: str | None) -> dict:
    row = {
        "asset_id": other.get("asset_id"),
        "dir": bearing(dx, dy),
        "distance": distance,
        "id": other["id"],
        **({"kills": n} if (n := int(other.get("kills") or 0)) else {}),
        "name": other.get("name"),
    }
    if is_boat(other):  # a hull: always afloat, sexless and thoughtless — its asset already says what it carries
        return row
    # Raw totals narrowed to `lifespan`, as `population_of` reads a stage: it alone is kept, and the whole pipeline doubled the sweep.
    age, lifespan = actor_age(other, ctx["world_time"]), int(actor_stat_totals(other, ctx, lifespan_only=True).get("lifespan", 0))
    # Why a line stands in full, where the reason tells a story: the tie before the post, a crown before a clan. Each marks a thinker, so `sapient` falls silent.
    job = None if tie else _POSTS.get(other.get("profession", 0))  # WB omits `profession` at 0, its « nothing »
    mark = {"kin": tie} if tie else {"job": job} if job else {"role": "clan_chief"} if other["id"] in ctx["clan_chiefs"] else {}
    return {
        **(_off_land_at(other, ctx) if land is None else {} if land == home else {"island_id": land}),
        **row,
        # Silent at `adult`, the stage most bodies stand at, as a tally at nought: printed on every line it would push a named killer's past the inline width.
        **({} if (stage := life_stage(age, adult_age(other, ctx), lifespan, is_egg(other, ctx))) == "adult" else {"life_stage": stage}),
        **mark,
        # Only when true, as a tally drops at nought: a `false` on every beast would push a named killer's line past the inline width.
        **({"sapient": True} if not mark and is_sapient(ctx["subspecies_by_id"][other["subspecies"]]) else {}),
        "sex": sex_label(other),
    }


# A plan written out: a group of one is no group, so its body stands in full. No `kills` summed on the rest — whoever has killed already stands in full.
def _surroundings_rows(plan: list[tuple | dict], ctx: dict, home: int | None, kin: dict[int, str]) -> list[dict]:
    rows = []
    for item in plan:
        entry = item.pop("first") if isinstance(item, dict) else item
        if isinstance(item, dict) and item["count"] > 1:
            rows.append(item)
            continue
        distance, i, dx, dy, land = entry
        rows.append(_surroundings_row(ctx["actors_by_id"][i], ctx, distance, dx, dy, home, land, kin.get(i)))
    return rows


# How far the body swims now, off the one `_swim_reach` its walks use: `breath` before its wind fails, `reach` once drowning has spent its health too.
def _swim(actor: dict, stats: dict, ctx: dict) -> dict | str | None:
    biology = _biology(actor, ctx)
    tags = _body_tags(actor, biology, ctx)
    if _water_free(actor, tags, ctx):
        return "unlimited"
    if _water_trait_ids().intersection(biology):
        return "never"  # WB sends no such body into the water: it burns there rather than drowns
    breath, reach = _swim_reach(actor, stats, biology, "hovering" in biology, "fast_swimming" in tags)
    if reach == inf:
        return "unlimited"
    return {"breath": round(breath), "reach": round(reach)} if reach else None


# How far this body swims from a shore, in tiles: its breath at full pace, then its whole reach, the drowning that follows slower and a point of health at a time.
def _swim_reach(actor: dict, stats: dict, biology: tuple | list, aloft: bool, swift: bool) -> tuple[float, float]:
    if _water_trait_ids().intersection(biology):  # WB routes no body the water burns through the sea (`ActorMove.goTo`): it walks, or it stays
        return 0.0, 0.0
    if aloft or swift:  # neither spends breath in the water, hovering over it or `fast_swimming` through it: the sea is a road
        return inf, inf
    if not (speed := stats.get("speed")) or not (health_max := stats.get("health_max")):
        return 0.0, 0.0
    pace, health = speed * _TILES_PER_SPEED, min(int(actor.get("health") or 0), health_max)
    breath = pace * int(actor.get("stamina") or 0) / _STAMINA_PER_SECOND  # WB omits a zero, so a body without the field has no breath left
    return breath, breath + pace * _SPENT_BREATH_PACE * health / _DROWNING_PER_SECOND


# `--to` lifted off the command line: an actor id, or a tile as `x,y` — and the words left for the id and the sections.
def _take_target(argv: list[str]) -> tuple[int | tuple[int, int] | str | None, list[str]]:
    if "--to" not in argv:
        return None, argv
    at = argv.index("--to")
    try:
        value, rest = argv[at + 1], argv[:at] + argv[at + 2 :]
        if value[:1] == "i" and value[1:].isdigit():  # a whole land, by the id `geography … islands` gives it
            return value, rest
        x, sep, y = value.partition(",")
        return ((int(x), int(y)) if sep else int(value)), rest
    except (IndexError, ValueError):
        raise ValueError("`--to` takes an actor id, a tile or a land, e.g. `--to 42`, `--to 415,117` or `--to i7`") from None


# What `_kin_tie` weighs every neighbour against, read off the actor once: his id, his parents (a missing one left out) and his mate.
def _ties(actor: dict) -> tuple[int, frozenset[int], int | None]:
    return actor["id"], frozenset(p for p in (actor.get("parent_id_1"), actor.get("parent_id_2")) if p), actor.get("lover")


# The walk in the chronicler's hours, and days past a day's march, at the body's own pace — none aboard, where the hull sets it.
def _walk_time(actor: dict, walked: float, ctx: dict) -> dict:
    if is_aboard(actor):
        return {}
    speed = compute_actor_stats(actor, ctx).get("speed") or 1
    days = walked / (_DAILY_TILES_PER_SPEED * speed)
    return {"hours": round(walked / (_HOURLY_TILES_PER_SPEED * speed), 1), **({"days": round(days, 1)} if days >= 1 else {})}


# How far on foot each tile lies, `None` for a body the ground never holds: round his land's bays, swum within reach toward another, each walk drawn once asked for.
def _walker(actor: dict, ctx: dict, limit: float) -> Callable[[int, int, int | None], float | None] | None:
    if (gait := _gait(actor, ctx)) is None:
        return None
    (cx, cy), walk_map = actor_xy(actor), ctx["walk_map"]()
    home, afloat = ctx["island_lookup"]().get((cx, cy)), cache(lambda: walk_from(walk_map, gait, cx, cy, limit))
    ashore = afloat if walk_map.wet(cx, cy) else cache(lambda: walk_from(walk_map, gait.ashore(), cx, cy, limit))

    def walk(x: int, y: int, land: int | None) -> float | None:
        tile = y * walk_map.width + x
        if home is not None and land != home:
            return afloat().get(tile)
        if (cost := ashore().get(tile)) is None and home is None:  # off any counted land, his islet first on foot, then the water
            cost = afloat().get(tile)
        return cost

    return walk


# A body the water never bars — aloft over it, born of it, or living in it: one rule, that no walk measures it and its `swim` says unlimited alike.
def _water_free(actor: dict, tags: frozenset[str], ctx: dict) -> bool:
    species = _species(actor, ctx)
    # WB's `force_ocean_creature` binds a hull to the water as well: it keeps to the sea where an ant is free of every ground.
    return bool(species.get("airborne") or (species.get("force_ocean_creature") and not is_boat(actor)) or "water_creature" in tags)


# WB's `isDamagedByOcean`: `hydrophobia` and any other trait tagged `damaged_by_water` — such a body burns in the water rather than drowning in it.
@cache
def _water_trait_ids() -> frozenset[str]:
    return frozenset(name for name, spec in load_data("subspecies-traits.json").items() if "damaged_by_water" in (spec.get("tags") or []))


# Why no walk joins the two, named: the rock of their one land, the water between two lands too wide for his reach, or no crossing short enough at all.
def _why_unreachable(actor: dict, goal: tuple[int, int], whom: str, gait: Gait, crow: int, ctx: dict) -> str:
    island_of = ctx["island_lookup"]()
    home, land, who = island_of.get(actor_xy(actor)), island_of.get(goal), _named(actor)
    head = f"✗ {who} can't reach {whom}, {crow} tiles away as the crow flies"
    if (home is not None and home == land) or gait.reach == inf:  # his own land, walked round its bays, or a sea he crosses at will: the ground is to blame
        return f"{head}: rock, lava or goo walls the way off"
    swims = f"swims {round(gait.reach)} tiles at most" if gait.reach else "never takes to the water"
    if home is not None and land is not None and (gap := ctx["strait_gaps"]().get(tuple(sorted((home, land))))) is not None and gap > gait.reach:
        return f"{head}: lands {home} and {land} are {gap} tiles of water apart at their narrowest, and {who} {swims}"
    where = f"land {land}" if land is not None else "its spot, off any counted land"
    if not gait.reach:
        return f"{head}: {who} {swims}, and no walk on land reaches {where}"
    return f"{head}: no crossing short enough for {who}, who {swims}, reaches {where}"


def main(argv: list[str]) -> int:
    save_path, argv, _ = take_chapter(argv)
    try:
        target, argv = _take_target(argv)
    except ValueError as e:
        print(f"✗ {e}", file=sys.stderr)
        return 2
    if not argv:
        print("✗ usage: info.py <id> [sections] [--to <id>|<x,y>|i<land>] [C<n>] — see docs/tools.md", file=sys.stderr)
        return 2
    try:
        actor_id = int(argv[0])
    except ValueError:
        print(f"✗ invalid id: {argv[0]}", file=sys.stderr)  # a malformed call, like a bad section — not an entity that happens to be missing
        return 2

    requested = argv[1] if len(argv) > 1 else None
    try:
        sections = parse_sections(requested, _ALL_SECTIONS) if requested or target is None else ()  # a `--to` alone answers alone
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 2
    save = load_save(save_path)
    ctx = _build_context(save, save_path)
    actor = ctx["actors_by_id"].get(actor_id)
    if actor is None:
        print(f"✗ unknown actor: {actor_id}", file=sys.stderr)
        return 1
    if ctx["subspecies_by_id"].get(actor.get("subspecies")) is None:  # every stat is derived from the biology's base, so there is nothing to report without it
        print(f"✗ no subspecies for actor {actor_id}", file=sys.stderr)
        return 1
    aims, land, whom = [], None, ""
    if isinstance(target, int):
        if (other := ctx["actors_by_id"].get(target)) is None:
            print(f"✗ unknown actor: {target}", file=sys.stderr)
            return 1
        aims, whom = [actor_xy(other)], _named(other)
    elif isinstance(target, str):
        land, sizes = int(target[1:]), ctx["island_sizes"]()
        if land not in sizes:
            print(f"✗ unknown land: {land} — the counted lands run 1 to {max(sizes, default=0)}", file=sys.stderr)
            return 1
        if ctx["island_lookup"]().get(actor_xy(actor)) == land:
            print(f"✗ {_named(actor)} already stands on land {land}", file=sys.stderr)
            return 1
        aims, whom = [(x, y) for x, y, owner in ctx["island_lookup"]().edges() if owner == land], f"land {land}"  # its shore
    elif target is not None:
        height, width = len(save.get("tileArray") or []), sum((save.get("tileAmounts") or [[]])[0])
        if not (0 <= target[0] < width and 0 <= target[1] < height):
            print(f"✗ coords {target} out of bounds — map is {width}×{height}", file=sys.stderr)
            return 2
        aims, whom = [target], f"{target[0]},{target[1]}"

    out: dict = {}
    if "companions" in sections:  # both attachments as plain refs — `emit` drops whichever is unset or dead, and the section itself when the actor has neither
        by_id = ctx["actors_by_id"]
        out["companions"] = {"best_friend": entity_ref(actor.get("best_friend_id"), by_id), "lover": entity_ref(actor.get("lover"), by_id)}
    if "gear" in sections:
        out["gear"] = _build_gear(actor, ctx)
    if "inventory" in sections:
        out["inventory"] = _build_inventory(actor)
    if "metadata" in sections:
        out["metadata"] = _build_metadata(actor, ctx, save)
    if "plot" in sections:
        out["plot"] = _build_plot(actor, ctx, save)
    if "ranks_in_species" in sections:
        out["ranks_in_species"] = _compute_ranks_in_species(actor, ctx)
    if "stats" in sections:
        stats = _compute_stats(actor, ctx)
        out["stats"] = {**stats, "swim": _swim(actor, stats, ctx)} if stats else stats
    if "surroundings" in sections:
        out["surroundings"] = _build_surroundings(actor, ctx, requested)
    if "traits" in sections:
        out["traits"] = _build_traits(actor, ctx, detailed=requested not in (None, "full"))
    if aims:
        try:
            out["to"] = _build_to(actor, aims, whom, ctx, land)
        except _Unreachable as e:
            print(str(e), file=sys.stderr)
            return 1

    emit(out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
