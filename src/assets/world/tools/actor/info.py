#!/usr/bin/env python3

# User-facing docs (usage, available sections) live in `docs/tools.md`. Notes below are for maintainers — algorithm references, gotchas, source pointers.

import json
import re
import sys
from argparse import ArgumentTypeError
from collections import Counter, defaultdict
from functools import cache
from math import inf
from pathlib import Path
lazy from collections.abc import Callable, Mapping

sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))

from actor_stats import (
    MULTIPLIER_TARGETS,
    actor_stat_totals,
    adult_age,
    bears,
    body_stats,
    breeding_age,
    build_actor_stats_context,
    compute_actor_stats,
    crossed_on,
    hatch_on,
    hatches_as,
    is_baby,
    is_egg,
    kept_statuses,
    kept_task,
    kept_task_target,
    lineage_traits,
    status_left,
)
from founding import city_zones, settle_gates, settle_told
from grid import BARE, LazyTileGrid, listed_tiles, off_land, tile_ground, tile_mask
from islands import compute_islands_cached, islet_heart
from places import PLACE_REACH, PlaceError, PlaceIndex, UnknownPlaceError, kind_word, named_place
from shared import (
    NEW_BABY_NUTRITION,
    PROFESSION_KING,
    PROFESSION_LEADER,
    SAVES_DIR,
    UNITS_PER_MONTH,
    UNITS_PER_YEAR,
    UNWRITTEN_HEALTH,
    absent_entity,
    actor_age,
    actor_xy,
    asset_families,
    asset_kinds,
    asset_sites,
    bearing,
    body_ref,
    build_trait_ids,
    build_trait_list,
    building_footprint,
    building_tile,
    built_by_tile,
    chunk_window,
    chunks_apart,
    city_centre,
    competition_ranks,
    emit,
    entity_born,
    entity_ref,
    equipment_entry,
    fertile,
    gazetteer,
    index_by_id,
    is_aboard,
    is_boat,
    is_sapient,
    is_transport,
    kept_army_since,
    kept_city_since,
    kept_victims,
    latest_chapter,
    life_stage,
    light,
    load_data,
    load_save,
    moved_between,
    named_body,
    needs_food,
    parse_sections,
    place_point,
    resolve_profession,
    sex_label,
    take_chapter,
    take_since,
    unsited_reason,
    walk_tiles,
    wants_detail,
    water_ref,
    whereabouts,
    world_laws,
)
from walking import Gait, WalkMap, walk_from, walk_way, walk_ways, walled_in
from waters import water_bodies, water_family, water_tiles, waters_cached, waters_within

_ALL_SECTIONS = ("companions", "gear", "inventory", "kin", "metadata", "plot", "ranks_in_species", "stats", "surroundings", "traits")
_BABY_MASS_MULTIPLIER = 0.4  # WB `SimGlobalAsset.baby_mass_multiplier`: what a child weighs of the body it will grow into
_CIRCLES = (("intimate", 30), ("common", 120))  # chronicler.md's tiers, in minutes at his own pace — past the last lies the far-off, which no roster could hold
_CLAN_CHIEF_ROLE = ("chief_id", "clans", "past_chiefs")  # Chieftainship is a role, not a profession (a king can be both) — hence its own tenure field.
_DAILY_TILES_PER_SPEED = 24.0  # chronicler.md § Échelle: `speed` 10 walks 240 tiles a day, 6 hours of road, its halts counted — far short of 24 hours' worth
_DROWNING_PER_SECOND = 2.0  # the `drowning` status takes one point of health every 0.5s, and no armour blunts it — WB spares armour for blows alone
_FLOORS = {"gen": 1}  # a count `--since` reads unsaid as its floor: WB counts a founder its first generation
_GOAL_ONLY = frozenset({"chunks_apart", "circle", "crow_tiles", "dir", "widest_crossing", "with_boat"})  # a goal's words: `moved` keeps its own heading and length
_HOURLY_TILES_PER_SPEED = 4.0  # chronicler.md § Échelle: `speed` 10 walks ~40 tiles an hour, so a pace twice as quick halves the time
_IDS = frozenset({"home"})  # the counts that are no counts: a roof's id, which `--since` tells as `new` or `gone`, never from 0
_ISSUE_BACKDATE = 10 * UNITS_PER_YEAR  # WB `Actor.createNewWeapon` → `generateItem(…, 10, …)`: the weapon a body arrives with is stamped ten years before it
_LONE_ID = re.compile(r"[bcip]?\d+")  # the ids a `--to` aims at alone, a water's aside (`water_ref`): a body, a building, a town, a land — a bare number too
_NEAR_REACH = 32  # tiles past which no tile can be a chunk from the body's own: a place farther off is never weighed as close
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
_SPENT_BREATH_PACE = 0.4  # WB's own multiplier for a body out of breath: it still swims, at two fifths of its pace
_STAMINA_PER_SECOND = 10.0  # `spendStaminaWithCooldown` takes 1 to 5 points every 0.3s — `Randy.randomInt` leaves its top out, so three on average
_STATUS_SPANS = ((3 * UNITS_PER_MONTH, "soon"), (UNITS_PER_YEAR, "months"))  # a status's time left as a state: under 3 months, under a year, else `years`

# Profession → (current-holder field, save collection, history list). Every post keeps a `past_*` history whose last entry is the sitting holder's start.
_TENURE_ROLES = {
    "army_captain": ("id_captain", "armies", "past_captains"),
    "king": ("kingID", "kingdoms", "past_rulers"),
    "leader": ("leaderID", "cities", "past_rulers"),
}

_TILES_PER_SPEED = 0.2  # tiles a second per point of `speed`: WB's own 0.4 step, halved by the world's `unit_speed_multiplier`
_TO_USAGE = (
    "`--to` takes a body, a tile, a building, a town, a land, every land, a named place, a water, the nearest fire, a kind or a ground: `--to p42`,"
    ' `--to 415,117`, `--to b219`, `--to c3`, `--to i7`, `--to lands`, `--to "<place>"`, `--to lake4`, `--to lake`, `--to burning`, `--to volcano`, `--to lava`'
)

# What `since` leaves out of `changed`: a place is told as a path, `moved`, a task is an instant — and a status that moves no stat, weeded out apart.
_UNCOMPARED = frozenset({"island_id", "near_places", "place", "statuses_left", "task", "task_target", "x", "y"})
_WATERS = ("lake", "river", "sea", "water")  # the families a `--to` word may name: the nearest numbered water of one, `water` of any


# A `--to` that names no goal — a body, a building, a town or a land unknown, a kind nowhere: its message, and the exit it calls for.
class _AimError(Exception):
    def __init__(self, message: str, code: int = 1) -> None:
        super().__init__(message)
        self.code = code


# A `--to` no walk answers: its message says what bars the way, the water's width against the body's reach where the sea is to blame.
class _UnreachableError(Exception):
    pass


# The stats a trait moves that a WB bound swallows on this body: its total the same without it, as a `-5` accuracy on a floor of 1 — `None` where none is.
def _absorbed(actor: dict, trait: dict, ctx: dict, totals: dict) -> list[str] | None:
    if not (moved := trait.get("stats")):
        return None
    without = actor_stat_totals({**actor, "saved_traits": [t for t in actor.get("saved_traits") or () if t != trait["id"]]}, ctx)
    # A multiplier is weighed on the stat it multiplies, WB folding it into that one: `multiplier_damage` shows in `damage`, and nowhere else.
    return sorted(stat for stat in moved if round(totals.get(key := MULTIPLIER_TARGETS.get(stat, stat), 0), 6) == round(without.get(key, 0), 6)) or None


# Where one `--to` aims: its goal in both chapters, the tiles a walk seeks, how its end is told, each word of a list of kinds, what the trip adds — a refusal raised.
def _aim(target: int | tuple[int, int] | str, actor: dict, ctx: dict, save: dict, chapter: str | None) -> tuple:
    aims, mark, about, whom, told = [], None, {}, "", {}
    each: dict[str, tuple[list, Mapping] | None] = {}  # the words of a `--to` naming kinds, each with its sites, `None` where it has none: a question apiece
    if isinstance(target, int):
        if (other := ctx["actors_by_id"].get(target)) is None:
            refusal = absent_entity("actor", "actors_data", target, chapter, lambda a: not is_boat(a))
            # An id no body ever bore may be a building's, the two counted apart: `b<id>` aims at it, so the refusal hands that over.
            sites = (b for b in save.get("buildings") or [] if b.get("id") == target)
            if refusal.startswith("✗ unknown") and (building := next(sites, None)) is not None:
                refusal = f"✗ p{target} is no body — a {building.get('asset_id')}'s id: aim at it, `--to b{target}`"
            raise _AimError(refusal)
        aims, whom = [actor_xy(other)], named_body(other)
    elif isinstance(target, str) and target[:1] == "b" and target[1:].isdigit():
        # A building by its id, aimed at the nearest tile of its ground — or the one its task seeks there —, the same goal in either chapter: it never moves.
        building_id = int(target[1:])
        site = next((b for b in save.get("buildings") or [] if b.get("id") == building_id), None)
        if site is None or (tile := building_tile(site)) is None:
            raise _AimError(absent_entity("ground", "buildings", building_id, chapter, noun="building"))
        task = kept_task_target(actor) or {}
        sought = (task["x"], task["y"]) if task.get("ground") == building_id and "x" in task and "y" in task else None
        target, whom = tile, f"{site.get('asset_id')} {site.get('id')}"
        aims, told = ([sought], {"by_task": kept_task(actor)}) if sought else (building_footprint(site), {})
    elif isinstance(target, str) and target[:1] == "c" and target[1:].isdigit():
        # A town by its id, aimed at its centre as `tiles … distances` aims at a capital: one point, the same goal in either chapter while it stands.
        city = ctx["cities_by_id"].get(city_id := int(target[1:]))
        if city is None or (tile := city_centre(city)) is None:
            raise _AimError(absent_entity("city", "cities", city_id, chapter))
        target, aims, whom = tile, [tile], city.get("name") or f"city {city_id}"
    elif target == "lands":  # every land but its own, each tried as `i<id>` is: `_trip` answers with those reached
        whom = "every land"
    elif isinstance(target, str) and target[:1] == "i" and target[1:].isdigit():
        land, sizes = int(target[1:]), ctx["island_sizes"]()
        if land not in sizes:
            raise _AimError(f"✗ unknown land: {land} — the counted lands run 1 to {max(sizes, default=0)}")
        if ctx["island_lookup"]().get(actor_xy(actor)) == land:
            raise _AimError(f"✗ {named_body(actor)} already stands on land {land}")
        aims, mark, whom = _shore(land, ctx), "landing", f"land {land}"
    elif isinstance(target, str) and (water := water_ref(target)):  # a water by its id: its nearest tile, the shore a walk ends on
        kind, water_id = water
        if not (aims := ctx["water_tiles"](kind, water_id)):
            raise _AimError(f"✗ no {kind} {water_id} — `geography … waters` lists them")
        mark, whom = "reached", _named(gazetteer(), f"{kind}s", water_id) or f"{kind} {water_id}"
    elif isinstance(target, str) and (place := _place_aim(target, actor, ctx)) is not None:
        (aims, aimed), mark, whom = place, "reached", target
        told = {"place": {"aimed": aimed, "name": target}}
    elif target == "burning":  # a fire's nearest flame, where `geography … burning` sites its middle: what a body would meet first
        if not (aims := list(listed_tiles(save, "fire"))):
            raise _AimError("✗ nothing burns in this world")
        mark, whom = "burning", "the nearest fire"
    elif isinstance(target, str):  # a kind, a family, a resource or a ground a word, the body itself left out: each answered by the cheapest of its own reached
        families, words = asset_families(save), list(dict.fromkeys(filter(None, (word.strip() for word in target.split(",")))))
        # The lone goals among the words, refused at once with the line to type: each is aimed at by its own `--to`, the kinds answered still.
        if lone := [word for word in words if _lone_target(word)]:
            told, again = ", ".join(f"`{word}`" for word in lone), " ".join(f"--to {_retyped(word)}" for word in lone)
            print(f"✗ {told}: a list takes kinds, grounds and waters only — one `--to` each: `{again}`", file=sys.stderr)
        for word in words:
            if word in lone:
                each[word] = None
                continue
            if sites := [(record, tile) for record, tile in asset_sites(save, asset_kinds(families, word), footprint=True) if record is not actor]:
                each[word] = [tile for _, tile in sites], {tile: {"asset_id": record.get("asset_id"), "id": record.get("id")} for record, tile in sites}
                continue
            if word in _WATERS and (waters := ctx["water_family"](word))[0]:  # no kind, a family of waters: its nearest numbered one, a pond left out
                each[word] = waters
                continue
            if grounds := _ground_tiles(save, word):  # no kind, a ground as `biomes` names it: lava, rock, sand — its nearest tile, a wall's edge
                each[word] = grounds, {tile: {"ground": word} for tile in grounds}
                continue
            each[word] = None
            none = unsited_reason(families, word) or f"no {word} in this world, {named_body(actor)} aside"
            print(f"✗ {none} — the families: {', '.join(sorted(families))}; the waters: {', '.join(_WATERS)}", file=sys.stderr)
        if not any(each.values()):
            raise _AimError("")
    else:  # a tile, `x,y`
        height, width = len(save.get("tileArray") or []), sum((save.get("tileAmounts") or [[]])[0])
        if not (0 <= target[0] < width and 0 <= target[1] < height):
            raise _AimError(f"✗ coords {target} out of bounds — map is {width}×{height}", 2)
        aims, whom = [target], f"{target[0]},{target[1]}"

    return target, aims, mark, about, whom, each, told


# Tiles a hull sails in an hour, off its trade's `speed` in `boat-assets.json` — a transport's when none is named, the one kind that ferries.
def _boat_per_hour(hull: dict | None = None) -> float:
    kinds = load_data("boat-assets.json").get("kinds") or {}
    kind = ((hull or {}).get("asset_id") or "").removeprefix("boat_").partition("_")[0]
    return _HOURLY_TILES_PER_SPEED * (kinds.get(kind) or kinds["transport"])["speed"]


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
    islands, walk_map = cache(lambda: compute_islands_cached(save, save_path)), cache(lambda: WalkMap(save))
    return {
        **build_actor_stats_context(save),
        "actors_by_asset": actors_by_asset,
        "actors_by_id": actors_by_id,
        "alliances_by_id": index_by_id(save.get("alliances") or []),
        "buildings_by_tile": cache(lambda: built_by_tile(save)),  # called not stored: `metadata` alone asks, and the walk covers every building of the world
        "children_by_parent": children_by_parent,
        "cities_by_id": index_by_id(save.get("cities") or []),
        "clan_chiefs": frozenset(chief for c in save.get("clans") or [] if (chief := c.get("chief_id"))),
        "cultures_by_id": index_by_id(save.get("cultures") or []),
        "families_by_id": index_by_id(save.get("families") or []),
        "ferrying_kingdoms": ferrying,  # the crowns a transport boat serves: only their people reach, and are measured, past the common circle
        "city_zones": cache(lambda: city_zones(save, islands()[1])),  # called not stored: `settle` alone asks, and only of a thinking soul
        "island_lookup": cache(lambda: islands()[1]),  # tile → island id, called not stored: `metadata` and `surroundings` alone ask
        "island_sizes": cache(lambda: {land["id"]: land["size"] for land in islands()[0]}),
        "kingdoms_by_id": index_by_id(save.get("kingdoms") or []),
        "named_place": lambda name: named_place(name, save, save_path, islands()[1], walk_map()),  # a name of `places.json`, for `--to "<place>"`
        "pact_of": {kid: a["id"] for a in save.get("alliances") or [] for kid in a.get("kingdoms") or []},  # a realm sits in one pact at most
        "place_index": cache(lambda: PlaceIndex(save, save_path, islands()[1], walk_map())),  # what a body stands on, for `metadata`'s `place`
        "religions_by_id": index_by_id(save.get("religions") or []),
        # Called not stored: only a `--to` the water bars asks, to say how wide it is, and the sweep of the water costs a second on a save not yet cached.
        "strait_gaps": cache(lambda: {tuple(s["between"]): s["swim_tiles"] for s in waters_cached(save, save_path)["straits"]}),
        "tile_grid": cache(lambda: LazyTileGrid(save)),  # rows decoded as read: `settle` reads a zone's eight
        "tile_map": save["tileMap"],
        "walk_map": walk_map,  # called not stored: `surroundings` and `--to` alone walk
        "water_body": cache(lambda: water_bodies(save, save_path)),  # what water a tile lies in: the one a body swims in, struck from its `near_places`
        "water_family": lambda family: water_family(save, save_path, family),  # `--to lake`'s tiles and which water each is
        "water_tiles": lambda kind, water_id: water_tiles(save, save_path, kind, water_id),  # `--to lake4`'s
        "waters_within": lambda *window: waters_within(save, save_path, *window),  # the named waters by a body, for `metadata`'s `near_places`
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
    lifespan = int(actor_stat_totals(actor, ctx, lifespan_only=True).get("lifespan", 0))  # its own span, as a roster reads a stage: no status makes a body young
    age = actor_age(actor, ctx["world_time"])

    # Both off the biology, as WB writes them onto the subspecies — never off this body's own span. `age_adult` is nil where no baby form was ever drawn.
    age_adult, age_breeding = adult_age(actor, ctx), breeding_age(actor, ctx)
    tile = actor_xy(actor)
    profession = resolve_profession(actor, save)
    seats = _tenures(_TENURE_ROLES.get(profession or ""), save, ctx["world_time"])  # every holder of the post, read once: the years, then the place among them
    held, tenure = [{"years": years} for years in seats.values()], seats.get(actor["id"])

    # A lineage that can bear first (`fertile`); then `Actor.canBreed`'s age and reserve (a gut-less body fed), `infertile` and the cap on whoever bears.
    lineage = ctx["subspecies_by_id"].get(actor.get("subspecies"))
    lineage_bears = fertile(lineage)
    can_reproduce = (
        lineage_bears
        and age >= age_breeding
        and (not needs_food(lineage) or int(actor.get("nutrition") or 0) >= NEW_BABY_NUTRITION)
        and (
            bears(actor, ctx) is not True
            or ("infertile" not in (actor.get("saved_traits") or []) and ctx["children_by_parent"].get(actor.get("id"), 0) < int(snap.get("max_children") or 0))
        )
    )

    land = _land_of(actor, ctx)
    return {
        **whereabouts(actor, save.get("buildings") or [], ctx["buildings_by_tile"]()),  # Chronicler-only: the roof it is under, the structure it stands at
        # Chronicler-only, and only while it still bites: the date WB gives the child its halved `damage_max`/`health_max` back — a bridling, not an infirmity.
        **({"adult_on": crossed_on(actor, age_adult)} if age < age_adult else {}),
        "age": age,
        # Years `age` counts that the body never lived here — a migrant called in grown (WB `updateMigrants`), a clone, a time paradox: `born` dates its coming
        **({"age_overgrowth": n} if (n := int(actor.get("age_overgrowth") or 0)) else {}),
        # A pact reaches him through his crown, WB tying one to a realm and never to a soul — the ref lets `new.py` fan out on it like any other body.
        "alliance": entity_ref(ctx["pact_of"].get(actor.get("civ_kingdom_id")), ctx["alliances_by_id"]),
        "army_since": kept_army_since(actor),  # Chronicler-only: the month it joined its army, the mod's stamp
        "asset_id": actor.get("asset_id"),
        "born": entity_born(actor),  # the month WB set it on the map, dated as the chronicle dates: who came first, and when
        # Chronicler-only, and only while it still bites: the date WB opens a body's own line — `adult_on` lifts a bridling and lets it found a town, never bear.
        **({"breeds_on": crossed_on(actor, age_breeding)} if age < age_breeding and lineage_bears else {}),
        # Said only when they hold, as every flag the tools emit: a body that cannot is most of the world, beasts and children first.
        **({"can_reproduce": True} if can_reproduce else {}),
        "city": entity_ref(actor.get("cityID"), ctx["cities_by_id"]),
        "city_since": kept_city_since(actor),  # Chronicler-only: the month it settled there, the mod's stamp
        "clan": entity_ref(actor.get("clan"), ctx["clans_by_id"]),  # a ref, not a bare name: `clan/info.py <id>` can be called on it, as on `family`
        "clan_chief_years": _tenures(_CLAN_CHIEF_ROLE, save, ctx["world_time"]).get(actor["id"]),  # Chronicler-only: a role, so it stacks with `tenure_years`.
        "culture": entity_ref(actor.get("culture"), ctx["cultures_by_id"]),  # a ref like `clan`: `culture/info.py <id>` reads the customs it was raised in
        "family": entity_ref(actor.get("family"), ctx["families_by_id"]),  # a ref, not a bare name: `family/info.py <id>` can be called on it
        "favorite_food": actor.get("favorite_food"),
        # WB counts a first child 2, so a parentless founder is its 1: a floor, which says nothing and goes unsaid as a count at nought does.
        **({"gen": gen} if (gen := int(actor.get("generation") or 1)) > 1 else {}),
        "hatch_on": hatch_on(actor, ctx),  # Chronicler-only: the hatching, past or to come — `born` dates the laying, the chronicle the hatching
        "hatches_as": hatches_as(actor, ctx),  # Chronicler-only, an egg's alone: a state, never a date — the migrant's breaks out grown
        **({"home": home} if (home := actor.get("homeBuildingID")) else {}),  # Chronicler-only: WB names no roof — `ground/info.py <id>` takes the bare id
        "id": actor.get("id"),  # Actor id — lets the favourite's `<app-person-tag>` resolve its chip from the person registry like every other person ref.
        # Chronicler-only: enlistment is in the resident's own city army or nowhere, and never automatic — `false` marks a fighter left out.
        **({"in_army": bool(actor.get("army"))} if profession in ("army_captain", "warrior") or actor.get("army") else {}),
        "island_id": land,  # Chronicler-only: its land (geography/info.py), else `water` or `islet`
        # Chronicler-only: which islet, by its `heart` as `tiles … islet` gives it — the same from a chapter to the next while the rock holds its shape
        **({"islet": {"x": at[0], "y": at[1]}} if land == "islet" and (at := islet_heart(ctx["island_lookup"]().islet_tiles(tile))) else {}),
        "job": profession,
        "kingdom": entity_ref(actor.get("civ_kingdom_id"), ctx["kingdoms_by_id"]),
        "language": entity_ref(actor.get("language"), ctx["languages_by_id"]),  # a ref, not a bare name: `language/info.py <id>` reads the tongue it answers in
        "life_stage": life_stage(age, age_adult, lifespan, is_egg(actor, ctx)),
        "mass": _compute_mass(actor, ctx),
        **_places_at(actor, ctx),  # Chronicler-only: the named place it stands on, those it stands close to
        "name": actor.get("name"),  # absent, not a placeholder, where WB never named them — `emit` strips it and the panels drop the row
        "personality": _compute_personality(actor, snap),
        "religion": entity_ref(actor.get("religion"), ctx["religions_by_id"]),  # a ref, not a bare name: `religion/info.py <id>` reads the creed it holds
        "roles": _compute_roles(actor, save),
        "sapient": is_sapient(lineage),  # tells a builder of cities from a beast, and gates his person tag
        # Chronicler-only, a thinker's alone: whether a town could rise where it stands, else what bars it — the zone weighed even for a child.
        **settle_told(settle_gates(actor, ctx)),
        "sex": sex_label(actor),
        "statuses": kept_statuses(actor),  # Chronicler-only: what the body is in the middle of — asleep, with young —, where the save keeps it
        "statuses_left": _statuses_left(actor),  # Chronicler-only: how long a lasting one still runs, a state and never a date
        "subspecies": entity_ref(actor.get("subspecies"), ctx["subspecies_by_id"]),  # a ref, not a bare name: the chapter panel resolves its tag from the id
        "task": kept_task(actor),  # Chronicler-only: what the body was doing the instant of the save, by WB's own id, where the save keeps it
        "task_target": _task_target(actor, ctx, save),
        # A chief among chiefs, a king among kings: no species seats enough of either for its own podium to rank them.
        "tenure_rank_in_post": competition_ranks({"years": tenure or 0}, held, {"tenure": lambda seat: seat["years"]}).get("tenure"),
        "tenure_years": tenure,
        # WB `isInsideSomething`: a save keeps the boat half, never the building. A plain ref, souls boarding transports alone — `boat/info.py <id>` spells it out.
        **({"transport": entity_ref(actor.get("transportID"), ctx["actors_by_id"])} if is_aboard(actor) else {}),
        "victims": kept_victims(actor),  # Chronicler-only: the latest deaths it dealt, the mod's stamp — WB counts them, never whom
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


# A body between two chapters: its path, a heading and a length, never a bearing from anyone; then what moved of `metadata`, `stats` and traits — gaps, not events.
def _build_since(actor: dict | None, then: dict | None, ctx: dict, save: dict, then_ctx: dict, then_save: dict) -> dict:
    if then is None:
        return {"new": True}  # born or set down since, with nothing then to weigh it against
    was = actor_xy(then)
    was_land = _land_of(then, then_ctx)
    if actor is None:  # WB drops the dead from the save: a body gone is a body dead, its place then all that is left — none keeps where it fell
        return {"asset_id": then.get("asset_id"), "gone": True, "name": then.get("name"), "was_at": {"island_id": was_land, "x": was[0], "y": was[1]}}
    out: dict = {}
    if (now := actor_xy(actor)) != was:
        dx, dy = now[0] - was[0], now[1] - was[1]
        out["moved"] = {"crow_tiles": round(walk_tiles(dx, dy)), "dir": bearing(dx, dy), **_trip_back(actor, was, ctx)}
        if (land := _land_of(actor, ctx)) != was_land:
            out["moved"]["land"] = [was_land, land]
    before, after = _build_metadata(then, then_ctx, then_save), _build_metadata(actor, ctx, save)
    lasting = load_data("statuses.json")  # the statuses that move a stat, a curse among them: a nap or a laugh is an instant, never a change
    for side in (before, after):
        side["statuses"] = [status for status in side.get("statuses") or () if status in lasting] or None
    changed = {
        key: _change(key, before.get(key), after.get(key)) for key in sorted((before.keys() | after.keys()) - _UNCOMPARED) if before.get(key) != after.get(key)
    }
    # A level unsaid is WB's floor, 1: left out, it would weigh as 0. No `swim`, which only follows stamina and health.
    stats_then, stats_now = ({"level": 1, **body_stats(body, side)} for body, side in ((then, then_ctx), (actor, ctx)))
    names = ctx["creature_traits"]  # WB's own library, the same whichever chapter is read
    traits_then, traits_now = (sorted((names.get(tid) or {}).get("name") or tid for tid in body.get("saved_traits") or []) for body in (then, actor))
    return {**out, "changed": changed or None, "stats": moved_between(stats_then, stats_now), "traits": moved_between(traits_then, traits_now)}


# Every living body within the common reach, nearest first, walked at its own gait — a line is built only for a printed circle: `full` never makes the common one.
def _build_surroundings(actor: dict, ctx: dict, requested: str | None) -> dict:
    cx, cy = actor_xy(actor)
    circles: dict[str, list[tuple]] = {name: [] for name, _ in _CIRCLES}
    island_of = ctx["island_lookup"]()
    home = island_of.get((cx, cy))
    ctx["home_islet"] = frozenset(island_of.islet_tiles((cx, cy))) if home is None else frozenset()  # his own islet, as silent in the rows as his land
    # A crown that ferries none reaches no shore: without a transport boat the sea stays the far-off, and no hull nor body past the common reach is measured.
    ferried = actor.get("civ_kingdom_id") in ctx["ferrying_kingdoms"]
    per_hour, gait, walk_map = _per_hour(actor, ctx), _gait(actor, ctx), ctx["walk_map"]()
    limit = _ring_bound(_CIRCLES[-1][1]) * per_hour  # the costliest way still told within the common edge, as `--to` tells the same way
    sail = per_hour / _boat_per_hour()
    reach = limit / min(gait.cheapest, sail if ferried else 1.0) if gait else limit  # the farthest tile the cheapest pace brings within it
    kin: dict[int, str] = {}
    ties = _ties(actor)
    within: list[tuple] = []
    for other in ctx["actors_by_id"].values():
        if other is actor:
            continue
        if not (boat := is_boat(other)) and ctx["subspecies_by_id"].get(other.get("subspecies")) is None:
            continue
        ox, oy = actor_xy(other)
        # The crow's line first: no walk is shorter, and a swift swimmer's circles stop at their edge all the same.
        if (crow := walk_tiles(ox - cx, oy - cy)) > reach:
            continue
        # His parents, children, siblings and mate stand in full wherever they live: a count by town would drop where they are, which no roster of theirs says.
        if not boat and (tie := _kin_tie(ties, other)):
            kin[other["id"]] = tie
        within.append((other["id"], boat, crow, ox, oy, island_of.get((ox, oy))))
    # Each walk stops at the last body it may be asked for, rather than sweeping its whole limit: every one within reach is known before any walk is drawn.
    walker = _walker(actor, gait, ctx, limit, [(ox, oy, land) for *_, ox, oy, land in within])
    # A crown's hull carries him on: walked to a shore, sailed at the transport's pace, walked on — the whole trip timed against the same edge.
    offshore_tiles = {oy * walk_map.width + ox for _, boat, _, ox, oy, land in within if boat or land != home}
    sailed = cache(lambda: walk_from(walk_map, gait.sailing(sail), cx, cy, limit, offshore_tiles)) if ferried and gait else None
    offshore: list[tuple] = []
    for i, boat, crow, ox, oy, land in within:
        dx, dy = ox - cx, oy - cy
        # Filed by the time as told, as `--to` files it: a row that says « 2 h » stands in the common circle. A hull too, walked and swum to like any body.
        if (cost := crow if walker is None else walker(ox, oy, land)) is not None and (ring := _ring(cost / per_hour)):
            circles[ring].append((cost, i, dx, dy, land))
        elif sailed and (boat or land != home) and (cost := sailed().get(oy * walk_map.width + ox)) is not None and _ring(cost / per_hour):
            offshore.append((cost, i, dx, dy, land))  # what only a hull brings in reach: every boat, every body off his land
    if ferried:
        circles["common_with_boat"] = offshore
    if not any(circles.values()):  # none within his circles: the nearest body still said, lest an empty section read as a silence
        return {"nearest": _nearest_body(actor, ctx)}
    by_id = ctx["actors_by_id"]
    near = sorted(circles.pop("intimate"))
    rings: dict = {"intimate": [_surroundings_row(by_id[i], ctx, dx, dy, home, land, kin.get(i)) for _, i, dx, dy, land in near]}
    plans = {name: _surroundings_plan(entries, ctx, kin) for name, entries in circles.items()}
    if detailed := wants_detail(requested, sum(map(len, plans.values()))):
        rings.update({name: _surroundings_rows(plan, ctx, home, kin) for name, plan in plans.items()})
    # An adult's line goes unmarked, most bodies standing there: said beside the rows, where a silence read alone passes for youth. A sexless hull has no stage.
    if any("sex" in row and "life_stage" not in row for ring in rings.values() if isinstance(ring, list) for row in ring):
        rings["life_stage_default"] = "adult"
    return rings if detailed else light(rings, withheld=True)  # `full` keeps the circle a chapter opens on, and says the wider ones wait to be named


# The walk to a body, a tile or a land's shore, at his own gait within his swim — a flyer, water-born or passenger goes as the crow flies, landing nearest.
def _build_to(actor: dict, aims: list[tuple[int, int]], whom: str, ctx: dict, mark: str | None, about: Mapping[tuple[int, int], dict]) -> dict:
    cx, cy = actor_xy(actor)
    island_of = ctx["island_lookup"]()
    gx, gy = goal = min(aims, key=lambda t: (t[0] - cx) ** 2 + (t[1] - cy) ** 2)
    to = _heading(cx, cy, gx, gy, mark, about)
    home, per_hour = island_of.get((cx, cy)), _per_hour(actor, ctx)
    if (gait := _gait(actor, ctx)) is None:  # its way is the straight line, flown, swum or sailed: no walk to tell, only its time
        crow = to["crow_tiles"]
        return {**to, "circle": _circle(actor, ctx, crow / per_hour, home != island_of.get(goal), lambda: None), **_trip_time(per_hour, crow)}
    walk_map = ctx["walk_map"]()
    goals = {y * walk_map.width + x for x, y in aims}
    # A lone goal the rock shuts in, off a body it does not shut in too, is refused at once: the search would walk the whole world before giving up.
    if len(goals) == 1 and walled_in(walk_map, gait, gx, gy) and not walled_in(walk_map, gait, cx, cy):
        raise _UnreachableError(_why_unreachable(actor, goal, whom, gait, to["crow_tiles"], ctx))
    # WB walks round the bays of his own land, and swims only toward another — each aim by its own land, as `_walker` does: of many, the cheapest reached wins.
    if walk_map.wet(cx, cy):
        way = walk_way(walk_map, gait, cx, cy, goals)
    elif home is None:  # an islet of his, small, is tried on foot before the water
        way = walk_way(walk_map, gait.ashore(), cx, cy, goals) or walk_way(walk_map, gait, cx, cy, goals)
    else:
        own = {y * walk_map.width + x for x, y in aims if island_of.get((x, y)) == home}
        # On foot first, the cheap search: the swim toward the other lands, far dearer to draw, then goes no farther than the walk it must beat.
        way = walk_way(walk_map, gait.ashore(), cx, cy, own) if own else None
        if (abroad := goals - own) and (swum := walk_way(walk_map, gait, cx, cy, abroad, way[0] if way else inf)) and (way is None or swum < way):
            way = swum

    @cache
    def sailed() -> tuple | None:  # the trip by a crown's hull, walks to and fro counted — asked only once the walk falls past the common circle
        return walk_way(walk_map, gait.sailing(per_hour / _boat_per_hour()), cx, cy, goals, _ring_bound(_CIRCLES[-1][1]) * per_hour)

    def sailed_hours() -> float | None:
        return trip[0] / per_hour if (trip := sailed()) else None

    if way is None:  # no walk nor swim gets there, but a crown's hull may: its trip told in place of a walk that has none
        if _circle(actor, ctx, None, island_of.get(goal) != home, sailed_hours) == "common_with_boat":
            return {**to, "circle": "common_with_boat", "with_boat": _way_parts(sailed(), per_hour, "sail")}
        raise _UnreachableError(_why_unreachable(actor, goal, whom, gait, to["crow_tiles"], ctx))
    walked, _, _, _, widest, reached, _ = way
    if mark:
        to = _heading(cx, cy, reached % walk_map.width, reached // walk_map.width, mark, about)
    part = "sail" if is_aboard(actor) else "swim"  # a passenger's water is sailed, never swum
    past = {"widest_crossing": round(widest)} if gait.breath < inf and round(widest) > round(gait.breath) else {}  # a tireless swimmer never runs short
    # `walked` is the way's cost, terrain and swim weighed: it times the goal, which files it in a circle, and only its trodden length is printed.
    circle = _circle(actor, ctx, walked / per_hour, island_of.get((reached % walk_map.width, reached // walk_map.width)) != home, sailed_hours)
    boat = {"with_boat": _way_parts(sailed(), per_hour, "sail")} if circle == "common_with_boat" else {}  # the trip that files it there, beside the walk

    return {**to, **boat, **_way_parts(way, per_hour, part), **past, "circle": circle}


# What the soul was born with, off WB's creature library — each trait and its rarity, then its effect and flavour once named, and whether this age lulls it.
def _build_traits(actor: dict, ctx: dict, detailed: bool) -> dict | list[dict]:
    sworn, library = actor.get("saved_traits") or [], ctx["creature_traits"]
    if not detailed:
        return light({"ids": build_trait_ids(sworn, library, "rarity")})
    asleep, totals = ctx["era_dormant_traits"], actor_stat_totals(actor, ctx)  # `asleep`: the verdict `stats` already heeds, an age's gift lulled by another
    return [
        {**trait, "dormant": True} if trait["id"] in asleep else {**trait, "absorbed": _absorbed(actor, trait, ctx, totals)}
        for trait in build_trait_list(sworn, library)
    ]


# A field as it moved: a list, `roles`, by what came and went; a count or a flag as its pair, unsaid read as its floor; anything else as the pair, or `new`/`gone`.
def _change(key: str, before: object, after: object) -> dict | list | None:
    if isinstance(before, list) and isinstance(after, list):
        return moved_between(before, after)
    if key not in _IDS and isinstance(said := before if after is None else after, int):  # a bool is an int: `False` unsaid as a 0 is
        floor = _FLOORS.get(key, False if isinstance(said, bool) else 0)
        return [floor if before is None else before, floor if after is None else after]
    if after is None:  # a pair would lose its empty side to `emit`, which drops every `None`
        return {"gone": before}
    return {"new": after} if before is None else [before, after]


# The body at each chapter up to the one read, off each chapter's save, where it stood at all: one walk for every option that reads the chapters' past.
@cache
def _chapter_bodies(actor_id: int, upto: int) -> tuple[tuple[int, dict], ...]:
    found = []
    for n in range(1, upto + 1):
        if (path := SAVES_DIR / f"C{n}" / "map.wbox").exists():
            body = next((a for a in load_save(path).get("actors_data") or [] if a.get("id") == actor_id), None)
            if body is not None:
                found.append((n, body))
    return tuple(found)


# Chapter numbers as runs, `C2–C5, C7`: a status or a total held chapter after chapter reads as one stretch, its breaks as a comma.
def _chapter_spans(numbers: list[int]) -> str:
    runs: list[list[int]] = []
    for n in numbers:
        if runs and n == runs[-1][-1] + 1:
            runs[-1].append(n)
        else:
            runs.append([n])
    return ", ".join(f"C{run[0]}" if len(run) == 1 else f"C{run[0]}–C{run[-1]}" for run in runs)


# The circle a goal falls in, filed as `surroundings` files a body: by the walk's time as told, then off his land by a crown's hull, the walks to and fro counted.
def _circle(actor: dict, ctx: dict, hours: float | None, offshore: bool, sailed: Callable[[], float | None]) -> str:
    if hours is not None and (ring := _ring(hours)):  # `None`: no walk gets there at all
        return ring
    ferried = actor.get("civ_kingdom_id") in ctx["ferrying_kingdoms"]
    return "common_with_boat" if ferried and offshore and (trip := sailed()) is not None and _ring(trip) else "far"


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
    peers = [body_stats(a, ctx) for a in same_species]
    own = next(s for a, s in zip(same_species, peers, strict=True) if a["id"] == actor["id"])

    getters = {stat: lambda s, st=stat: s.get(st, 0) for stat in _RANKED_STATS if stat in own}  # `st=stat` binds now, else every lambda reads the last one
    ranks = competition_ranks(own, peers, getters)
    # Age is not in `body_stats` (derived from `created_time`) — ranked separately, against the raw actors.
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


# A time as the chronicler reads it: whole minutes under the hour, where a tenth of an hour would round a few tiles to nought, else hours to the tenth.
def _duration(hours: float, prefix: str = "") -> dict:
    if (minutes := round(hours * 60)) >= 60:
        return {f"{prefix}hours": round(hours, 1)}
    return {f"{prefix}minutes": max(minutes, 1) if hours else 0}  # a trip, however short, takes a minute: 0 is for the tile he stands on


# The same trip made by the body aimed at, which no shared figure tells: its own pace, its own swim — only what differs, and nothing where both agree.
def _from_them(other: dict, actor: dict, to: dict, ctx: dict) -> dict | None:
    try:
        back = _build_to(other, [actor_xy(actor)], named_body(actor), ctx, None, {})
    except _UnreachableError:
        return {"unreachable": True}
    return {key: value for key, value in back.items() if key != "dir" and to.get(key) != value} or None


# How this body walks, or `None` for one the ground never holds — a flyer, a body born to the water, one aboard a hull: all keep the crow's line.
def _gait(actor: dict, ctx: dict) -> Gait | None:
    biology = lineage_traits(actor, ctx)
    tags = _body_tags(actor, biology, ctx)
    if _water_free(actor, tags, ctx):
        return None
    # The cleaned stats, not the raw totals: a child walks and swims on the halved ceiling WB gives it.
    stats, aloft, swift = compute_actor_stats(actor, ctx), "hovering" in biology, "fast_swimming" in tags
    breath, reach = _swim_reach(actor, stats, biology, aloft, swift)
    blind = bool(_species(actor, ctx).get("ignore_tile_speed_multiplier"))  # WB `ActorAsset`: every ground at one pace
    gait = ctx["walk_map"]().gait(stats.get("speed"), tags, aloft=aloft, blind=blind, swift=swift, breath=breath, reach=reach)
    if is_aboard(actor):  # a passenger: his hull sails him by water, and he walks on from the shore it lands him on
        return gait.sailing(_per_hour(actor, ctx) / _boat_per_hour(ctx["actors_by_id"].get(actor.get("transportID"))))
    return gait


# Every tile of one ground as `geography … biomes` names it, for `--to <ground>` — none where the world bears none, the word then left to the kinds' refusal.
def _ground_tiles(save: dict, ground: str) -> list[tuple[int, int]]:
    if ground not in (names := [(tile_ground(name) or "").removeprefix(BARE) for name in save.get("tileMap") or []]):
        return []
    return [(x, y) for y, row in enumerate(tile_mask(save, [own == ground for own in names])) for x, held in enumerate(row) if held]


# The bearing and the crow's tiles to a point — and, where the goal was many, which one: a land's `landing`, the `nearest` of a kind with its id, or of a ground.
def _heading(cx: int, cy: int, gx: int, gy: int, mark: str | None, about: Mapping[tuple[int, int], dict]) -> dict:
    to = {"chunks_apart": chunks_apart(cx, cy, gx, gy), "crow_tiles": round(walk_tiles(gx - cx, gy - cy)), "dir": bearing(gx - cx, gy - cy)}
    return {**to, mark: {**about.get((gx, gy), {}), "x": gx, "y": gy}} if mark else to


# A body's kills at each chapter, total by total: the save dates no death it dealt, so a rise lies between the chapter before its first (or birth) and that one.
def _kill_history(actor_id: int, upto: int) -> dict | None:
    totals = defaultdict(list)
    for n, body in _chapter_bodies(actor_id, upto):
        totals[str(body.get("kills") or 0)].append(n)
    return {total: _chapter_spans(at) for total, at in totals.items()} or None


# Whom a body was born of and whom it bore, off the parents WB writes on each body: a parent gone is named by the registry, its own dead kept; children, the living.
def _kin(actor: dict, ctx: dict) -> dict:
    by_id, aid = ctx["actors_by_id"], actor["id"]
    ids = [pid for pid in (actor.get("parent_id_1"), actor.get("parent_id_2")) if pid]
    gone = [pid for pid in ids if pid not in by_id]
    path = SAVES_DIR / f"C{latest_chapter()}" / "persons.json"
    known = json.loads(path.read_text()) if gone and path.exists() else {}
    parents = [entity_ref(pid, by_id) or {"gone": True, "id": pid, "name": (known.get(str(pid)) or {}).get("name")} for pid in ids]
    children = [entity_ref(kid, by_id) for kid in sorted(b["id"] for b in by_id.values() if aid in (b.get("parent_id_1"), b.get("parent_id_2")))]
    return {"children": children or None, "parents": parents or None}


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


# Its land's id, else `water` afloat or `islet` on an islet too small to count — as `roster` says it.
def _land_of(body: dict, ctx: dict) -> int | str:
    return ctx["island_lookup"]().get(actor_xy(body)) or ("water" if "water" in _off_land_at(body, ctx) else "islet")


# A word a `--to` list cannot hold: an id, the fire, every land or a place's name — each a goal aimed at by its own `--to`.
def _lone_target(word: str) -> bool:
    return bool(_LONE_ID.fullmatch(word) or water_ref(word)) or word in {"burning", "lands"} or not kind_word(word)


# A counted land's or water's name in `places.json`, `None` while the chronicler has not named it.
def _named(toponyms: dict, book: str, entry_id: int) -> str | None:
    return ((toponyms.get(book) or {}).get(str(entry_id)) or {}).get("name") or None


# The body nearest him as the crow flies, wherever it stands — for one whose circles hold nobody. No hull: a boat is no neighbour.
def _nearest_body(actor: dict, ctx: dict) -> dict | None:
    cx, cy = actor_xy(actor)
    best: tuple[float, dict, int, int] | None = None
    for other in ctx["actors_by_id"].values():
        if other is actor or is_boat(other) or ctx["subspecies_by_id"].get(other.get("subspecies")) is None:
            continue
        ox, oy = actor_xy(other)
        crow = walk_tiles(ox - cx, oy - cy)
        if best is None or crow < best[0]:
            best = (crow, other, ox - cx, oy - cy)
    if best is None:
        return None
    crow, other, dx, dy = best
    return {"asset_id": other.get("asset_id"), "crow_tiles": round(crow), "dir": bearing(dx, dy), "id": other["id"], "name": other.get("name")}


# Where a body off every counted land stands, an islet told by its ground or the water — the grid decoded for its row alone, for the lines that need it.
def _off_land_at(body: dict, ctx: dict) -> dict:
    x, y = actor_xy(body)
    if off_land(ctx["tile_map"][ctx["tile_grid"]()[y][x]]) == "water":
        return {"water": True}
    return {"islet_tiles": ctx["island_lookup"]().islet_size((x, y))}


# Tiles walked in an hour at the body's own pace — a passenger's too, the unit his hull's sailing is counted in (`_gait`).
def _per_hour(actor: dict, ctx: dict) -> float:
    return _HOURLY_TILES_PER_SPEED * (compute_actor_stats(actor, ctx).get("speed") or 1)


# A name of `places.json` as `--to` aims at it (`places.named_place`), a land landed on its walkable rim and never the one the body stands on — `None`: a kind.
def _place_aim(name: str, actor: dict, ctx: dict) -> tuple[list[tuple[int, int]], str] | None:
    try:
        if (found := ctx["named_place"](name)) is None:
            return None
    except PlaceError as e:
        if isinstance(e, UnknownPlaceError) and "," in name:  # a list of goals, kinds or not: the kinds tell each word apart
            return None
        raise _AimError(str(e)) from None
    tiles, aimed = found
    if aimed[:1] == "i" and aimed[1:].isdigit():
        if ctx["island_lookup"]().get(actor_xy(actor)) == (land := int(aimed[1:])):
            raise _AimError(f"✗ {named_body(actor)} already stands on {name}")
        tiles = _shore(land, ctx)
    return tiles, aimed


# The named places a body stands on, and those the game would call close (`chunks_apart` ≤ 1) — of the forged, only those whose box or point is in reach.
def _places_at(actor: dict, ctx: dict) -> dict:
    (ax, ay), index, near = actor_xy(actor), ctx["place_index"](), []
    for name, spot in (gazetteer().get("places") or {}).items():
        box, (px, py) = spot.get("box"), place_point(spot)
        if box:
            reach = all(min(box[f"{a}0"], box[f"{a}1"]) - _NEAR_REACH <= at <= max(box[f"{a}0"], box[f"{a}1"]) + _NEAR_REACH for a, at in (("x", ax), ("y", ay)))
        else:
            reach = walk_tiles(px - ax, py - ay) <= _NEAR_REACH + PLACE_REACH
        if not reach:
            continue
        if (tiles := index.tiles(name, spot)) and (ax, ay) not in tiles and min(chunks_apart(ax, ay, tx, ty) for tx, ty in tiles) <= 1:
            near.append(name)
    # The named waters and the other named lands with a tile in the chunks round it, read off the masks of that window alone, the sea's half million spared.
    toponyms, island_of, (x0, y0, x1, y1) = gazetteer(), ctx["island_lookup"](), chunk_window(ax, ay)
    named = {(kind, water_id): name for kind, water_id in ctx["waters_within"](x0, y0, x1, y1) if (name := _named(toponyms, f"{kind}s", water_id))}
    if ctx["walk_map"]().wet(ax, ay):  # the water it is in is no neighbour: `place` names it, where no forged place holds it
        named.pop(next(iter(ctx["water_body"]()(ax, ay).items())), None)
    lands = {land for y in range(max(y0, 0), y1 + 1) for land in island_of.row(y)[max(x0, 0) : x1 + 1]} - {0, island_of.get((ax, ay))}
    near += [*named.values(), *filter(None, (_named(toponyms, "islands", land) for land in lands))]
    return {**({"near_places": sorted(set(near))} if near else {}), **({"place": on} if (on := index.at(ax, ay)) else {})}


# Every land the body can gain, the nearest first, each by its cheapest shore as `--to i<id>` lands it: its heading, time and swim — the rest counted.
def _reachable_lands(actor: dict, ctx: dict) -> dict:
    (cx, cy), island_of, per_hour = actor_xy(actor), ctx["island_lookup"](), _per_hour(actor, ctx)
    home, barred = island_of.get((cx, cy)), ctx["walk_map"]().barred
    shores: defaultdict[int, list[tuple[int, int]]] = defaultdict(list)  # every land's rim in one sweep of the edges, as `_shore` reads one
    for x, y, owner in island_of.edges():
        if owner != home and owner is not None and not barred(x, y):
            shores[owner].append((x, y))
    if (gait := _gait(actor, ctx)) is None:  # flown, swum or sailed at will: every land reached on the straight line, as `--to` times it
        rows = []
        for land, rim in shores.items():
            to = _heading(cx, cy, *min(rim, key=lambda t: (t[0] - cx) ** 2 + (t[1] - cy) ** 2), "landing", {})
            rows.append({"dir": to["dir"], "island_id": land, **_trip_time(per_hour, to["crow_tiles"])})
        return {"reachable": sorted(rows, key=_told_time) or None}
    walk_map = ctx["walk_map"]()
    land_of = {y * walk_map.width + x: land for land, rim in shores.items() for x, y in rim}
    ways = walk_ways(walk_map, gait, cx, cy, land_of)  # one settling for every land: a walk apiece would cross the world once a land
    rows = []
    for land, way in ways.items():
        tile = way[5]
        times = {key: value for key, value in _way_parts(way, per_hour, "swim").items() if not key.endswith("_tiles") and key.startswith(("swim_", "total_"))}
        rows.append({"dir": _heading(cx, cy, tile % walk_map.width, tile // walk_map.width, "landing", {})["dir"], "island_id": land, **times})
    rows.sort(key=_told_time)  # by the time as told, days counting a march's halts: the way's raw cost would file a long swim after a longer walk
    lands = sum(land != home for land in ctx["island_sizes"]())  # a land rimmed by rock alone has no shore, and counts as out of reach
    return {"reachable": rows or None, "unreachable": lands - len(ways) or None}


# A goal of a `--to` list as its own `--to` takes it: a number is a body's, a name with a space or a capital is a place's, quoted.
def _retyped(word: str) -> str:
    return f"p{word}" if word.isdigit() else word if kind_word(word) else f'"{word}"'


# The circle a time falls in, read as `_duration` tells it, so a row printed « 2 h » stands in the common circle though its walk ran to 2.04 — `None` past them.
def _ring(hours: float) -> str | None:
    told = minutes if (minutes := round(hours * 60)) < 60 else round(hours, 1) * 60
    return next((name for name, limit in _CIRCLES if told <= limit), None)


# The longest time still told within `minutes`, as `_ring` files by the rounded time: the bound a sweep of the circles walks to.
def _ring_bound(minutes: int) -> float:
    return (minutes + 0.5) / 60 if minutes < 60 else minutes / 60 + 0.05


# The tiles a land is landed on: the ground of its rim, a land owning its rock, where no body sets foot.
def _shore(land: int, ctx: dict) -> list[tuple[int, int]]:
    barred = ctx["walk_map"]().barred
    return [(x, y) for x, y, owner in ctx["island_lookup"]().edges() if owner == land and not barred(x, y)]


# The body's own species record in `species.json` — WB's `ActorAsset` flags that no save carries.
def _species(actor: dict, ctx: dict) -> dict:
    return ctx["species_data"].get(actor.get("asset_id")) or {}


# A body's lasting statuses at each chapter up to the one read, off each chapter's save: `seen` where it stood at all, what came and went in between unseen.
def _status_history(actor_id: int, upto: int) -> dict | None:
    lasting, held, seen = load_data("statuses.json"), defaultdict(list), []
    for n, body in _chapter_bodies(actor_id, upto):
        seen.append(n)
        for status in kept_statuses(body) or ():
            if status in lasting:
                held[status].append(n)
    return {"held": {status: _chapter_spans(at) for status, at in sorted(held.items())}, "seen": _chapter_spans(seen)} if seen else None


# What each lasting status has still to run, off WB's own clock that Faithful Saves keeps: `soon`, `months` or `years`. An egg's end is `hatch_on`'s to date.
def _statuses_left(actor: dict) -> dict | None:
    lasting, left = load_data("statuses.json"), {}
    for status in kept_statuses(actor) or ():
        if status in lasting and status != "egg" and (seconds := status_left(actor, status)) is not None:
            left[status] = next((span for bound, span in _STATUS_SPANS if seconds < bound), "years")
    return left or None


# A wide circle, nearest first: kin, killer, named beast, crown or wanderer as its entry, the rest as a group per town or kind — so `full` counts lines unwritten.
def _surroundings_plan(entries: list[tuple], ctx: dict, kin: dict[int, str]) -> list[tuple | dict]:
    by_id, chiefs = ctx["actors_by_id"], ctx["clan_chiefs"]
    groups: dict[tuple, dict] = {}
    plan: list[tuple | dict] = []  # the entries come sorted, so a group stands where its nearest member was met, and nothing is re-sorted
    for entry in sorted(entries):
        _, i, dx, dy, _ = entry
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
            group = groups[key] = {**head, "count": 0, "first": entry, "nearest": {"crow_tiles": round(walk_tiles(dx, dy)), "dir": bearing(dx, dy)}}
            plan.append(group)
        group["count"] += 1
        if sapient:
            group["species"][other.get("asset_id")] += 1
    return plan


# One line of `surroundings`: silent on his own land or islet, off it the land's id — or `water` or `islet_tiles` off every land, a bare null reading as home.
def _surroundings_row(other: dict, ctx: dict, dx: int, dy: int, home: int | None, land: int | None, tie: str | None) -> dict:
    row = {
        "asset_id": other.get("asset_id"),
        "crow_tiles": round(walk_tiles(dx, dy)),  # what a sentence with no walker says: his own pace's time is `--to`'s to tell
        "dir": bearing(dx, dy),
        "id": other["id"],
        **({"kills": n} if (n := int(other.get("kills") or 0)) else {}),
        "name": other.get("name"),
    }
    if is_boat(other):  # a hull: always afloat, sexless and thoughtless — its asset already says what it carries
        return row
    # Raw totals narrowed to `lifespan`, as `pop_of` reads a stage: it alone is kept, and the whole pipeline doubled the sweep.
    age, lifespan = actor_age(other, ctx["world_time"]), int(actor_stat_totals(other, ctx, lifespan_only=True).get("lifespan", 0))
    # Why a line stands in full, where the reason tells a story: the tie before the post, a crown before a clan. Each marks a thinker, so `sapient` falls silent.
    job = None if tie else _POSTS.get(other.get("profession", 0))  # WB omits `profession` at 0, its « nothing »
    mark = {"kin": tie} if tie else {"job": job} if job else {"role": "clan_chief"} if other["id"] in ctx["clan_chiefs"] else {}
    beside = land == home if land is not None else actor_xy(other) in ctx["home_islet"]  # `home_islet` is empty unless he stands on one
    return {
        **({} if beside else _off_land_at(other, ctx) if land is None else {"island_id": land}),
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
        _, i, dx, dy, land = entry
        rows.append(_surroundings_row(ctx["actors_by_id"][i], ctx, dx, dy, home, land, kin.get(i)))
    return rows


# How far the body swims now, off the `_swim_reach` its walks use — `breath` before its wind fails, `reach` drowning too — and `rested`, what full gauges change.
def _swim(actor: dict, stats: dict, ctx: dict) -> dict | str | None:
    biology = lineage_traits(actor, ctx)
    tags = _body_tags(actor, biology, ctx)
    if _water_free(actor, tags, ctx):
        return "unlimited"
    if _water_trait_ids().intersection(biology):
        return "never"  # WB sends no such body into the water: it burns there rather than drowns
    aloft, swift = "hovering" in biology, "fast_swimming" in tags
    breath, reach = _swim_reach(actor, stats, biology, aloft, swift)
    if reach == inf:
        return "unlimited"
    now = {"breath": round(breath), "reach": round(reach)}
    # What comes back once it has rested, where it differs: the breath off a wind spent, the reach off either gauge — a gauge at its top changes nothing.
    full = zip(("breath", "reach"), map(round, _swim_reach(actor, stats, biology, aloft, swift, rested=True)), strict=True)
    rested = {gauge: value for gauge, value in full if value != now[gauge]}
    return {**now, **({"rested": rested} if rested else {})} if reach or rested else None


# How far this body swims from a shore, in tiles: its breath at full pace, then its reach, drowning a point of health at a time — at its gauges' top if `rested`.
def _swim_reach(actor: dict, stats: dict, biology: tuple | list, aloft: bool, swift: bool, rested: bool = False) -> tuple[float, float]:
    if _water_trait_ids().intersection(biology):  # WB routes no body the water burns through the sea (`ActorMove.goTo`): it walks, or it stays
        return 0.0, 0.0
    if aloft or swift:  # neither spends breath in the water, hovering over it or `fast_swimming` through it: the sea is a road
        return inf, inf
    if not (speed := stats.get("speed")) or not (health_max := stats.get("health_max")):
        return 0.0, 0.0
    pace, health = speed * _TILES_PER_SPEED, health_max if rested else min(int(actor.get("health", UNWRITTEN_HEALTH)), health_max)
    stamina = int(stats.get("stamina_max") or 0) if rested else int(actor.get("stamina") or 0)  # WB omits a zero, so a body without the field has no breath left
    breath = pace * stamina / _STAMINA_PER_SECOND
    return breath, breath + pace * _SPENT_BREATH_PACE * health / _DROWNING_PER_SECOND


# Every `--to` on the line, in order: a body, a tile, a building, a town, a land, a water, fire, kinds or grounds — repeated where a list of ids would be a tile.
def _take_targets(argv: list[str]) -> tuple[list[int | tuple[int, int] | str], list[str]]:
    targets: list[int | tuple[int, int] | str] = []
    while "--to" in argv:
        at = argv.index("--to")
        if at + 1 == len(argv):
            raise ValueError(_TO_USAGE)
        value, argv = argv[at + 1], argv[:at] + argv[at + 2 :]
        x, sep, y = value.partition(",")
        if (body := body_ref(value)) is not None:
            targets.append(body)
        elif x.lstrip("-").isdigit() and sep and y.lstrip("-").isdigit():
            targets.append((int(x), int(y)))
        else:  # a land (`i7`, as `geography … islands` ids it), every land, a building, a town, a water, the fire, or kinds, families and grounds
            targets.append(value)
    return targets, argv


# Chronicler-only: what the body's task was aimed at the instant of the save — a prey, a store, a tile —, a body and a building told as every ref is.
def _task_target(actor: dict, ctx: dict, save: dict) -> dict | None:
    if (aim := kept_task_target(actor)) is None:
        return None
    if (target := aim.get("actor")) is not None:  # a prey is most often a beast with no name: its kind tells it
        other = ctx["actors_by_id"].get(target) or {}
        aim["actor"] = {"asset_id": other.get("asset_id"), "id": target, "name": other.get("name")}
    if (target := aim.get("ground")) is not None:
        site = next((b for b in save.get("buildings") or [] if b.get("id") == target), None) or {}
        aim["ground"] = {"asset_id": site.get("asset_id"), "id": target}
    return aim


# Years each holder of a post has sat in it, by its id — `role` = (holder field, collection, history). A seat counts while its history's last entry names its holder.
def _tenures(role: tuple[str, str, str] | None, save: dict, world_time: float) -> dict[int, int]:
    if role is None:
        return {}
    holder_field, collection, history = role
    seats: dict[int, int] = {}
    for record in save.get(collection, []):
        entries = record.get(history) or []
        if entries and (holder := record.get(holder_field)) is not None and entries[-1].get("id") == holder:
            seats.setdefault(holder, int((world_time - float(entries[-1].get("timestamp_ago") or 0)) / UNITS_PER_YEAR))
    return seats


# What `_kin_tie` weighs every neighbour against, read off the actor once: his id, his parents (a missing one left out) and his mate.
def _ties(actor: dict) -> tuple[int, frozenset[int], int | None]:
    return actor["id"], frozenset(p for p in (actor.get("parent_id_1"), actor.get("parent_id_2")) if p), actor.get("lover")


# A trip's time as told, for sorting: minutes before hours before days, each read by its own figure — the whole trip's, or a flyer's march.
def _told_time(row: dict) -> tuple[int, float, int]:
    for rank, key in ((0, "total_minutes"), (1, "total_hours"), (2, "total_days"), (2, "march_days")):
        if key in row:
            return rank, row[key], row["island_id"]
    return 3, 0.0, row["island_id"]


# One `--to` answered: the walk, the way back from a body, the same goal in the chapter `--since` names — `None` where its refusal was told.
def _trip(actor: dict, aim: tuple, ctx: dict, then: dict | None, then_ctx: dict, since: str | None) -> dict | None:
    target, aims, mark, about, whom, each, told = aim
    if target == "lands":
        return _reachable_lands(actor, ctx)
    trip: dict | None = None
    if aims:
        try:
            trip = {**_build_to(actor, aims, whom, ctx, mark, about), **told}
            if isinstance(target, int):
                trip["from_them"] = _from_them(ctx["actors_by_id"][target], actor, trip, ctx)
        except _UnreachableError as e:
            print(f"{e} — `circle`: far", file=sys.stderr)  # out of reach is past every circle: said, a refusal bearing no field
            return None
        if then is not None and isinstance(target, int) and target not in then_ctx["actors_by_id"]:
            print(f"✗ no `then`: {whom} not yet in {since}", file=sys.stderr)
        elif then is not None and not isinstance(target, str):
            goals = aims if isinstance(target, tuple) else [actor_xy(then_ctx["actors_by_id"][target])]
            trip["then"] = _trip_then(then, goals, whom, then_ctx)
    if isinstance(target, str) and then is not None:  # a land's numbers and a kind's sites are redrawn from save to save: the goal then would be another
        print("✗ no `then`: only a point or a body is the same goal in both chapters", file=sys.stderr)
    if each:
        reached: dict = dict.fromkeys(each)  # a word left unanswered keeps its place: the others then keep their names, where one alone would come bare
        for word, goal in each.items():  # out of reach, it says so and leaves the others their answer: the command fails where none has one
            try:
                reached[word] = goal and _build_to(actor, goal[0], f"the nearest {word}", ctx, "nearest", goal[1])
            except _UnreachableError as e:
                print(f"{e} — `circle`: far", file=sys.stderr)
        if not any(reached.values()):
            return None
        return reached if len(each) > 1 else next(iter(reached.values()))

    return trip


# How long the shortest way between two places takes at the body's pace, walked back from where it stands — the way it truly took, no save keeps.
def _trip_back(actor: dict, was: tuple[int, int], ctx: dict) -> dict:
    try:
        trip = _build_to(actor, [was], f"{was[0]},{was[1]}", ctx, None, {})
    except _UnreachableError:
        return {}
    return {key: value for key, value in trip.items() if key not in _GOAL_ONLY}


# The same goal timed in the chapter `--since` names: from where the body stood then, at its pace and on its ground of then — the two times side by side.
def _trip_then(then: dict, goals: list[tuple[int, int]], whom: str, then_ctx: dict) -> dict:
    try:
        trip = _build_to(then, goals, whom, then_ctx, None, {})
    except _UnreachableError:
        return {"circle": "far"}
    return {key: value for key, value in trip.items() if key == "crow_tiles" or key not in _GOAL_ONLY}


# A trip's time by parts: `walk_`, `swim_` or `sail_`, `total_` once two (`foot` None: unwalked); past a day `march_days`, a crossing's `total_days`.
def _trip_time(per_hour: float, total: float, foot: float | None = None, water: tuple[str, float] | None = None) -> dict:
    day = _DAILY_TILES_PER_SPEED / _HOURLY_TILES_PER_SPEED * per_hour  # a day's march, in the cost's own tiles
    if water and foot is not None:  # water is crossed in one go, swum or sailed: the march alone keeps its halts, and the whole day by day
        (part, wet), marched = water, foot / day
        told = _duration(wet / per_hour, f"{part}_") | ({"march_days": round(marched, 1)} if marched >= 1 else _duration(foot / per_hour, "walk_"))
        whole = marched + wet / per_hour / 24
        return told | ({"total_days": round(whole, 1)} if whole >= 1 else _duration(total / per_hour, "total_"))
    return {"march_days": round(total / day, 1)} if total >= day else _duration(total / per_hour, "walk_" if foot is not None else "total_")


# How far on foot each of `spots` lies, `None` for a body the ground never holds: round his land's bays, swum within reach toward another, each walk drawn if asked.
def _walker(actor: dict, gait: Gait | None, ctx: dict, limit: float, spots: list[tuple]) -> Callable[[int, int, int | None], float | None] | None:
    if gait is None:
        return None
    (cx, cy), walk_map = actor_xy(actor), ctx["walk_map"]()
    home, wet = ctx["island_lookup"]().get((cx, cy)), walk_map.wet(cx, cy)
    lands = {y * walk_map.width + x: land for x, y, land in spots}  # each walk aims at the tiles `walk` may ask it for, his land's or the others'
    afloat = cache(lambda: walk_from(walk_map, gait, cx, cy, limit, {t for t, land in lands.items() if wet or home is None or land != home}))
    ashore = afloat if wet else cache(lambda: walk_from(walk_map, gait.ashore(), cx, cy, limit, {t for t, land in lands.items() if home is None or land == home}))

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


# A way by parts, lengths and times: `walk_`, the water's `part` (`swim_`/`sail_`, 1 tile at least), its `crossings`, `total_` once two — never summed by hand.
def _way_parts(way: tuple | None, per_hour: float, part: str) -> dict:
    if way is None:
        return {}
    cost, water, swam, trod, _, _, crossings = way
    wet = {"crossings": crossings, f"{part}_tiles": max(round(swam), 1), "total_tiles": round(trod)} if water else {}
    return {**wet, "walk_tiles": round(trod - swam), **_trip_time(per_hour, cost, cost - water, (part, water) if water else None)}


# Why no walk joins the two, named: the rock of their one land or round the goal, a water shut to the body, a strait no islet chain shortens, no crossing in reach.
def _why_unreachable(actor: dict, goal: tuple[int, int], whom: str, gait: Gait, crow: int, ctx: dict) -> str:
    island_of = ctx["island_lookup"]()
    home, land, who = island_of.get(actor_xy(actor)), island_of.get(goal), named_body(actor)
    head = f"✗ {who} can't reach {whom}, {crow} tiles away as the crow flies"
    if (home is not None and home == land) or gait.reach == inf:  # his own land, walked round its bays, or a sea he crosses at will: the ground is to blame
        return f"{head}: rock, lava or goo walls the way off"
    islet, walk_map = "an islet off any counted land", ctx["walk_map"]()
    if walled_in(walk_map, gait, *actor_xy(actor)):  # shut in where it stands: no swim would get it out, whatever its breath
        return f"{head}: rock, lava or goo walls its own ground in, on {f'land {home}' if home is not None else islet} — no water leads out"
    if walled_in(walk_map, gait, *goal):  # no swim, however long, would get there: the water is not to blame
        return f"{head}: rock, lava or goo walls it in, on {f'land {land}' if land is not None else islet} — no water leads there"
    where = f"land {land}" if land is not None else "its spot, off any counted land"
    if (reach := round(gait.reach)) < 1:  # a breath that crosses no whole tile: the water is shut to it, and a strait's width is beside the point
        return f"{head}: {who} never takes to the water, and no walk on land reaches {where}"
    swims = f"swims {reach} tile{'s' if reach > 1 else ''} at most"
    if home is not None and land is not None and (gap := ctx["strait_gaps"]().get(tuple(sorted((home, land))))) is not None and gap > reach:
        return f"{head}: lands {home} and {land} are {gap} tiles of water apart at their narrowest, and no islet chain shortens it enough for {who}, who {swims}"
    return f"{head}: no crossing short enough for {who}, who {swims}, reaches {where}"


def main(argv: list[str]) -> int:
    try:
        since, argv = take_since(argv)
    except ValueError as e:
        print(f"✗ {e}", file=sys.stderr)
        return 2
    kills, statuses = "--kills" in argv, "--statuses" in argv
    argv = [arg for arg in argv if arg not in {"--kills", "--statuses"}]
    save_path, argv, chapter = take_chapter(argv)
    if (kills or statuses) and chapter is None:  # the chapters' saves are the record it reads: before the first, there is none
        print(f"✗ `--{'kills' if kills else 'statuses'}` reads the chapters' saves, and none is written yet", file=sys.stderr)
        return 2
    upto = int(chapter[1:]) if chapter else 0
    try:
        targets, argv = _take_targets(argv)
    except (ArgumentTypeError, ValueError) as e:
        print(f"✗ {e}", file=sys.stderr)
        return 2
    if not argv:
        print(
            "✗ usage: info.py <id> [sections] [--to p<id>|<x,y>|b<id>|c<id>|i<land>|<kind>] [--since C<n>] [--kills] [--statuses] [C<n>] — docs/tools.md",
            file=sys.stderr,
        )
        return 2
    try:
        actor_id = int(argv[0])
    except ValueError:
        print(f"✗ invalid id: {argv[0]}", file=sys.stderr)  # a malformed call, like a bad section — not an entity that happens to be missing
        return 2

    requested = argv[1] if len(argv) > 1 else None
    flagged = since is not None or kills or statuses
    try:
        sections = parse_sections(requested, _ALL_SECTIONS) if requested or (not targets and not flagged) else ()  # a flag alone answers alone
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 2
    save = load_save(save_path)
    ctx = _build_context(save, save_path)
    actor = ctx["actors_by_id"].get(actor_id)
    then_save, then_ctx, then = {}, {}, None
    if since:
        then_path = SAVES_DIR / since / "map.wbox"
        if (late := chapter is not None and int(since[1:]) >= int(chapter[1:])) or not then_path.exists():
            print(f"✗ `--since {since}`: {f'not before {chapter}, the chapter read' if late else 'no such chapter'} — name an earlier one", file=sys.stderr)
            return 2
        then_save = load_save(then_path)
        then_ctx = _build_context(then_save, then_path)
        then = then_ctx["actors_by_id"].get(actor_id)
    if actor is None and not sections and not targets:  # a body gone still answers `--since`, `--kills` and `--statuses`, each with its own past, and they alone
        dealt, history = _kill_history(actor_id, upto) if kills else None, _status_history(actor_id, upto) if statuses else None
        if (since or kills or statuses) and (not since or then is not None) and (not kills or dealt) and (not statuses or history):
            emit({"kills": dealt, "since": _build_since(None, then, ctx, save, then_ctx, then_save) if since else None, "statuses": history})
            return 0
    if actor is None:
        print(absent_entity("actor", "actors_data", actor_id, chapter, lambda a: not is_boat(a)), file=sys.stderr)
        return 1
    if ctx["subspecies_by_id"].get(actor.get("subspecies")) is None:  # every stat is derived from the biology's base, so there is nothing to report without it
        print(f"✗ no subspecies for actor {actor_id}", file=sys.stderr)
        return 1
    aimed: dict[str, tuple | None] = {}  # each `--to` by its own words: where it aims, or `None` where its refusal was told
    for target in targets:
        words = f"{target[0]},{target[1]}" if isinstance(target, tuple) else str(target)
        try:
            aimed[words] = _aim(target, actor, ctx, save, chapter)
        except _AimError as e:
            if str(e):  # a list of kinds told its own refusals, word by word
                print(e, file=sys.stderr)
            if len(targets) == 1:
                return e.code
            aimed[words] = None
    if targets and not any(aimed.values()):
        return 1
    out: dict = {}
    if "companions" in sections:  # both attachments as plain refs — `emit` drops whichever is unset or dead, and the section itself when the actor has neither
        by_id = ctx["actors_by_id"]
        out["companions"] = {"best_friend": entity_ref(actor.get("best_friend_id"), by_id), "lover": entity_ref(actor.get("lover"), by_id)}
    if "gear" in sections:
        out["gear"] = _build_gear(actor, ctx)
    if "inventory" in sections:
        out["inventory"] = _build_inventory(actor)
    if "kin" in sections:  # its blood, where a mate or a friend is a bond: a parent gone stays (`gone`), and the section goes where it has neither
        out["kin"] = _kin(actor, ctx)
    if "metadata" in sections:
        out["metadata"] = _build_metadata(actor, ctx, save)
    if "plot" in sections:
        out["plot"] = _build_plot(actor, ctx, save)
    if "ranks_in_species" in sections:
        out["ranks_in_species"] = _compute_ranks_in_species(actor, ctx)
    if "stats" in sections:
        stats = body_stats(actor, ctx)
        out["stats"] = {**stats, "swim": _swim(actor, stats, ctx)} if stats else stats
    if "surroundings" in sections:
        out["surroundings"] = _build_surroundings(actor, ctx, requested)
    if "traits" in sections:
        out["traits"] = _build_traits(actor, ctx, detailed=requested not in (None, "full"))
    if since:
        out["since"] = _build_since(actor, then, ctx, save, then_ctx, then_save)
    if kills:
        out["kills"] = _kill_history(actor_id, upto)
    if statuses:
        out["statuses"] = _status_history(actor_id, upto)
    trips = {words: aim and _trip(actor, aim, ctx, then, then_ctx, since) for words, aim in aimed.items()}
    if targets and not any(trips.values()):
        return 1
    if trips:  # several `--to` keep each its words, where one alone comes bare
        out["to"] = trips if len(trips) > 1 else next(iter(trips.values()))
    if out.keys() == {"kin"} and not any(out["kin"].values()):  # asked alone, a bare `{}` would read as a field gone missing
        print(f"✗ no kin — {named_body(actor)} appeared, born of none, and none is born of it", file=sys.stderr)
        return 1

    emit(out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
