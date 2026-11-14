# Every `--roster`'s mechanics — the cut, `--with`'s one-for-one, the refusals — and `actor --roster` whole: the bodies line by line, as its options leave them.

import contextlib
import difflib
import re
import sys
from collections import defaultdict
from functools import cache, partial
from operator import itemgetter
lazy import argparse
lazy from collections.abc import Callable, Collection, Sequence
lazy from pathlib import Path

from actor_stats import (
    adult_age,
    body_lifespan,
    body_stats,
    breeding_age,
    build_actor_stats_context,
    compute_actor_stats,
    crossed_on,
    equipment_power,
    hatch_on,
    is_egg,
    kept_statuses,
    kept_task,
)
from founding import GATES, city_zones, settle_gates, settle_told
from grid import LazyTileGrid, off_land, patch_finder
from islands import TileIslands, compute_islands_cached, islet_heart
from places import PlaceIndex
from shared import (
    JOBS,
    SAVES_DIR,
    SKILLS,
    absent_entity,
    actor_age,
    actor_xy,
    alive_or_dead_ref,
    arg_parser,
    asset_families,
    asset_kinds,
    bearing,
    body_ref,
    built_by_tile,
    children_by_id,
    counted_birth,
    crafted_counts,
    crowns_at_death,
    crowns_served,
    date_span,
    emit,
    entity_born,
    entity_ref,
    fertile,
    index_by_id,
    indoors,
    is_boat,
    is_sapient,
    kept_army_since,
    kept_city_since,
    kept_deaths,
    latest_chapter,
    life_stage,
    limit_arg,
    load_data,
    load_save,
    log_entries,
    overgrowth,
    resolve_profession,
    sapient_subspecies,
    sex_label,
    since_saves,
    take_chapter,
    take_since,
    tile_text,
    walk_tiles,
    war_camps,
    weapon_assets,
    whereabouts,
    world_date,
    world_laws,
    xy_arg,
    zone_at_death,
    zone_cities,
    zone_of,
)
from walking import WalkMap

_DEAD_SOCLE = ("asset_id", "name", "sex")  # a dead body's line beside what befell it: its name, then its kind, what `--with` drives off — its sex stays
_DEATH_CAUSES = tuple(sorted({*load_data("attack-types.json").values(), "lightning"}))  # what `died:` takes: each cause as the register files it, a bolt the mod's
_DISPLACED = ("city", "island_id", "life_stage", "name", "asset_id", "age")  # what `--with` and `--since` drive off the socle, one per field, least telling first
_FIELD_FLOORS = {"births": 0, "equipment_power": 0, "level": 1, "loot": 0, "money": 0, "renown": 0}  # a tally `actor … stats` tells silent at its floor

# What `--with` asks of the dead: the register keeps it, a sex never changes, a war its side, a tally what the last save saw
_GONE_FIELDS = (
    "asset_id",
    "at",
    "births",
    "born",
    "camp",
    "crow_tiles",
    "dir",
    "killed_by",
    "kills",
    "level",
    "loot",
    "money",
    "name",
    "parents",
    "renown",
    "sex",
    "zone_of",
)

# What `has:`/`lacks:` weigh held or not: a lineage, every body has
_HELD = ("army", "city", "clan", "culture", "family", "home", "kingdom", "language", "lover", "religion")

_HELD_FIELDS = {"home": "homeBuildingID", "lover": "lover"}  # the held a body keeps apart from its ties, by its field: a roof, a mate

# What `--with` reads off the body and its ground, a line's own fields among them, its tile as `metadata` gives it, its lineage by id: `subspecies --roster` names it
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
    "camp",
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
    "settle",
    "sex",
    "statuses",
    "subspecies",
    "task",
    "weapon",
    "zone_of",
)

# What `--filter` takes as `key:value` besides each entity's id: an open value
_KEYED = ("barred", "born", "died", "gear", "has", "lacks", "patch", "status", "task", "trait", "type")

_LIFE_STAGES = ("egg", "baby", "child", "teen", "adult", "elder")  # `shared.life_stage`'s, in the order a body passes them — `--filter`'s stage words
LIMIT = 10  # the lines every roll gives unless `--limit` says otherwise: its head, the cut told beside
MAX_FIELDS = 4  # past so many fields a line reads as a sheet, under every `--roster`: the tool's own sheet gives the whole of one

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
    "war": ("wars", None),  # its two camps, each body by the crown it serves
}

_ONE_BODY = re.compile(r"(?:p|id:)?(\d+)")  # a body by its id, as `--rank` takes one: `--filter` narrows a roll, one body is `actor`'s
_RANKED_KEPT = ("age_overgrowth", "gen")  # the figures among a body's kept fields `--rank` reads, every other a word or an id
_SINCE_PARTS = ("arrived", "died", "grew", "left", "moved")  # what a `--since` roll files a body under, `left` an entity's alone
_TALLIES = ("births", "kills", "level", "loot", "money", "renown")  # what `has:` and `lacks:` weigh: a body's own counters, named as `actor … stats` names them
_TIES = ("city", "clan", "culture", "family", "kingdom", "language", "religion")  # what `--with` names a body's ties by, `{id, name}` as `actor … metadata` does
_TOP_MEASURES = tuple(sorted((*SKILLS, *_TALLIES, "age", "crafted", "equipment_power")))  # what `--rank` ranks by: a counter, a skill, an arsenal, age, work

ISLET = "islet"  # where `roster` says a body stands, or stood, on an islet too small to count — `WATER` where it floats
WATER = "water"  # where `roster` says a body stands, or stood, afloat — off every land, as `ISLET` is, but in the sea or a lake


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
        "age_overgrowth": lambda: n if (n := overgrowth(actor)) != 1 else None,  # a migrant's mark, `born` its arrival
        "army_since": lambda: kept_army_since(actor),  # when it joined its town's army, none outside one
        "asset_id": lambda: actor.get("asset_id"),
        "at": lambda: tile_text(*actor_xy(actor)),
        "beside_building": lambda: whereabouts(actor, ctx["buildings_by_id"], ctx["built"])["beside_building"],  # the second ring of `in_building`
        "born": lambda: entity_born(actor),
        "camp": lambda: ctx["camp"](actor),  # its side in the war filtered on
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
        "weapon": lambda: _weapon(actor, ctx["items_by_id"]),
        "zone_of": lambda: zone_of(*actor_xy(actor), ctx["zone_cities"]),  # whose town's ground it stands on, none in the wild
        **{kind: (lambda kind=kind: entity_ref(actor.get(_MEMBERSHIPS[kind][1]), ctx["ties"][kind])) for kind in ctx.get("ties", ())},
    }
    return {field: kept[field]() if field in kept else stats.get(field, _FIELD_FLOORS.get(field)) for field in fields}


# Whether a body belongs to every entity `roster` is narrowed to, read off the body itself — a king the log alone crowned and buried (`fallen`) of the realm he left.
def _belongs(save: dict, entities: list[tuple[str, int | str]], fallen: dict[int, int] | None = None) -> Callable[[dict], bool]:
    ties = [_tie(save, kind, entity_id, fallen or {}) for kind, entity_id in entities]
    return ties[0] if len(ties) == 1 else lambda actor: all(tie(actor) for tie in ties)


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
    gear: str | None,
    bar: str | None,
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
    # A war's dead are weighed by their crown at death and their killer's, not by a save that saw them: `_war_side` keeps them, the other ties alone sift
    war_id = dict(entities).get("war")
    camps = war_camps(index_by_id(save.get("wars") or []).get(war_id) or {}) if war_id is not None else None
    if "camp" in fields and camps is None:
        raise ValueError("✗ `camp` tells a war's side: `--filter war:<id>` first")
    # Under an entity, `--since` weighs who belonged then: a body that joined arrives, one alive elsewhere has left, though the world saw both all along.
    members_then = {a["id"] for a in earlier.get("actors_data") or [] if belonged(a)} if entity and earlier is not None else None
    known = was if members_then is None else members_then
    weighed = has or lacks  # one measure each: `has:` keeps whoever holds any, `lacks:` whoever holds none — `--rank`'s own is its order
    thinking = sapient_subspecies(save) if sapient is not None else None  # `sapient` keeps the minds, `beasts` the rest
    grid = LazyTileGrid(save)  # rows decoded as read: a body off every land alone asks its tile
    asked = lands
    if patch and lands is None and (under := island_of.get(next(iter(patch)))) is not None:
        asked = frozenset({under})  # a patch lies on one land, which then goes unsaid as a lone land's does
    alone = next(iter(asked)) if asked is not None and len(asked) == 1 else None  # one land named goes unsaid on every line: several, each line tells its own
    ctx = build_actor_stats_context(save)
    if camps is not None:
        ctx["camp"] = lambda actor: next(
            (side for side, crowns in zip(("attackers", "defenders"), camps, strict=True) if actor.get("civ_kingdom_id") in crowns), None
        )
    if ties := [kind for kind in _TIES if kind in fields]:
        ctx["ties"] = {kind: index_by_id(save.get(_MEMBERSHIPS[kind][0]) or []) for kind in ties}
    if not {"beside_building", "in_building"}.isdisjoint(fields):
        ctx["buildings_by_id"] = index_by_id(save.get("buildings") or [])
        ctx["built"] = built_by_tile(save)
    if "job" in fields:
        ctx["profession"] = lambda actor: resolve_profession(actor, save)
    if "lover" in fields or weighed == "lover":
        ctx["living_ids"] = {actor["id"] for actor in save.get("actors_data") or []}
    stated = fields or (top and top not in (*_TOP_MEASURES, "died"))  # a stat asked or ranked by: every body's `actor … stats` read
    seen = set(_KEPT_FIELDS) | _FIELD_FLOORS.keys() if stated else set()  # every field a body can be asked or ranked by, its stats added as they come
    if near:  # the length and heading to the point ranked around, `--with crow_tiles,dir`
        seen |= {"crow_tiles", "dir"}
    if stated:
        ctx["children_by_parent"] = children_by_id(save)  # `body_stats` counts each body's children as `actor` does
    if top == "crafted" or "crafted" in fields:  # the world's items by their maker, as `actor … ranks` counts a body's work
        ctx["made"] = crafted_counts(ctx["items_by_id"])
    if "place" in fields:  # each forged place drawn once for the whole roll, as `metadata` draws it for one body
        ctx["place_index"] = PlaceIndex(save, save_path, island_of, WalkMap(save))
    if settle or barred or "settle" in fields:  # the ground `settle_gates` weighs, gathered only for a roll that filters on it or asks it
        ctx |= {
            "city_zones": cache(lambda: city_zones(save, island_of)),
            "island_lookup": lambda: island_of,
            "tile_grid": lambda: grid,
            "tile_map": save["tileMap"],
            "world_laws": world_laws(save),
        }
    if "zone_of" in fields:  # every town's zones indexed once for the roll
        ctx["zone_cities"] = zone_cities(save)

    # A trait is a body's own or its lineage's: `gift_of_thunder` is born with a whole line, `fire_blood` with one body — `trait:` finds either.
    bearers = {sub["id"] for sub in save.get("subspecies") or [] if trait in (sub.get("saved_traits") or ())} if trait else set()

    # Under `--since`, `has:` keeps the bodies whose tally moved, each weighed against what it held then; the pair itself, `--with` asks.
    once = {a["id"]: _held(a, has) for a in earlier.get("actors_data") or []} if has and earlier is not None else None

    bodies, still, unranked, aged = [], 0, 0, 0
    weighed_gates: dict[int, bool | list[str] | None] = {}  # what `settle`/`barred` weighed, `--with settle` reads again rather than weigh twice

    (nx, ny), near_id = near or ((0, 0), None)
    far: dict[int, float] = {}  # each body's unrounded length, ranked on: two read alike may still stand apart

    # A body's line beside the one ranked around: its length as the crow flies, and its heading — not under `--since`, its lines full
    def towards(row_id: int, x: int, y: int) -> dict:
        far[row_id] = walk_tiles(x - nx, y - ny)
        measured = {"crow_tiles": round(far[row_id]), "dir": None if since else bearing(x - nx, y - ny)}
        return {key: value for key, value in measured.items() if key in fields}  # `--rank` orders alone: `--with` shows the length

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
        if gear and gear not in {(ctx["items_by_id"].get(item) or {}).get("asset_id") for item in actor.get("saved_items") or ()}:
            continue
        # Born in this world that year or month: a migrant's birth is no date the save holds, its arrival less whole years brought guessing the month
        if born and (overgrowth(actor) != 1 or not born[1] <= float(actor.get("created_time") or 0) < born[2]):
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
        figure = _rank_figure(actor, top, ctx, seen) if top and top != "died" else 0  # `--rank`'s figure: one holding none counted once every filter has spoken
        gates = weighed_gates[actor["id"]] = settle_gates(actor, ctx) if settle or barred else None
        if settle and gates not in (True, ["child"]):  # founds where it stands once grown: nothing, or its youth alone, bars it
            continue
        if barred and (gates is None or gates in (True, ["child"])):  # a thinker something besides its youth keeps from founding
            continue
        if bar and not (isinstance(gates, list) and any(gate.split(" ", 1)[0] == bar for gate in gates)):  # one gate named, told by its first word
            continue
        here = stands_on(actor, island_of, grid, save["tileMap"])
        change: dict = {}  # a filter sets no field: what `has:` weighs, `--with` asks
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
                | ({"crow_tiles": change["crow_tiles"]} if "crow_tiles" in change else {})
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
                bodies.append((actor, here, change, figure))
    if top and top not in (*seen, *_TOP_MEASURES, "died") and (bodies or unranked):  # a stat no body weighed here carries, told once their stats are known
        figures = sorted({*_TOP_MEASURES, *_RANKED_KEPT, *(field for field in seen if field not in _KEPT_FIELDS)})
        raise ValueError(refused("--rank", [top], figures, "`gloss actor.roster.--rank`, `actor <id> stats`, `p<id>` or `x,y`"))
    gone, mourned = [], False  # `mourned`: the dead searched, found or not — `killed_by` asked of them even where none died

    if earlier is not None and was is not None and not (settle or barred) and "died" in told_parts:  # the dead found nothing
        mourned = True
        standing = partial(stands_on, island_of=island_of, grid=grid, names=save["tileMap"])  # where each died, on today's map
        sifted = belonged if war_id is None else _belongs(earlier, [tie for tie in entities if tie[0] != "war"], fallen)
        gone = _gone_since(save, earlier, later, kinds, trait, asked, sapient, bred, sifted, stage, standing, fields, born)
        if gone and (unborne := [field for field in fields if field not in _GONE_FIELDS]):  # a stale save's figure would read as the dead's: said, not dropped
            told = ", ".join(f"`{field}`" for field in unborne)
            print(f"⚠ {told}: none on a `died` line — the dead take {', '.join(f'`{field}`' for field in _GONE_FIELDS)} alone", file=sys.stderr)
        if cause:  # `died:`: the dead of one cause, as the register files it — said once by the filter, never on each line
            gone = [{**row, "died_of": None} for row in gone if row["died_of"] == cause]
        if war_id is not None:
            side = _war_side(save, int(war_id), int(save_path.parent.name[1:]) if re.fullmatch(r"C\d+", save_path.parent.name) else latest_chapter())
            gone = [{**row, **({"camp": camp} if "camp" in fields else {})} for row in gone if (camp := side(row["id"]))]
        if once is not None:  # the dead that held the tally, each with what it takes away: where it stood and who took it are another question's
            gone = [row for row in gone if once.get(row["id"])]
        if near:  # the dead measured from where they fell
            fell = kept_deaths(save)
            gone = [row | towards(row["id"], fell[row["id"]]["x"], fell[row["id"]]["y"]) for row in gone]

    one_stage = stage is not None and len(stage) == 1  # and a lone stage its own
    town = dict(entities).get("city")  # and a town filtered every line's
    towns = index_by_id(save.get("cities") or [])

    # The one line every body gets, whatever the filter: who, its kind, sex, town, land and stage — a filter silences the field it fixes, `--with` drives some off
    def socle(actor: dict, here: int | str, change: dict) -> dict:
        phase = _stage(actor, ctx, actor_age(actor, ctx["world_time"]), adult_age(actor, ctx))
        heart = islet_heart(island_of.islet_tiles(actor_xy(actor))) if here == ISLET else None  # which islet, as `actor … metadata` names it
        return {
            "age": actor_age(actor, ctx["world_time"]),
            "asset_id": None if one_kind(kinds) else actor.get("asset_id"),
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
    def placed(row_id: int, figure: int = 0, actor: dict | None = None, fell: float = 0.0) -> tuple[tuple, object]:
        if top == "died":  # the dead as they fell, the earliest first: a war's months read down the list
            return (fell, row_id), fell
        if near:
            return (far[row_id], row_id), round(far[row_id])
        if top == "age" and actor is not None:  # whole years tie a cohort: the earliest born first, the years it arrived with counted
            born_at = counted_birth(actor)
            return (-figure, born_at, row_id), (figure, world_date(born_at))
        return ((-figure, row_id), figure) if top else ((row_id,), row_id)

    wanted = [field for field in fields if field not in ("crow_tiles", "dir", "island_id", "islet", "killed_by")]  # the socle's land, the dead's killer, a length
    # Each field asked beyond the socle drives one off it, the first the line shows in `_DISPLACED`, and a `--since` line's part one more — never what it put there
    driving = len([field for field in fields if field not in (*_DISPLACED, "islet", "sex")]) + (1 if since and not has else 0)

    told_as = {"island_id": ("island_id", "islet")}  # a land is one field, islet or not

    def fielded(actor: dict, here: int | str, change: dict) -> dict:
        row = socle(actor, here, change)
        founding = settle_told(weighed_gates.get(actor["id"]) or settle_gates(actor, ctx)) if "settle" in fields else {}  # two fields of one gate
        added = _asked_fields(actor, here, wanted, ctx, seen) | founding
        # What a part put there stays, and what tells it: the land a mover reached, the town a leaver went to — a land is one field, islet or not
        kept = {*change, *(["island_id"] if "was_on" in change else []), *(["city"] if "part" in change else [])}
        gives = [told for key in _DISPLACED if key not in kept for told in told_as.get(key, (key,)) if row.get(told) is not None]
        return make_room(row, added, gives, owed=driving)

    lines: list[tuple[tuple, object, dict]] = []
    for actor, here, change, figure in bodies:
        row = fielded(actor, here, change)
        if since and (past := then_bodies.get(actor["id"])):  # a tally asked under `--since` weighed as a pair, from its floor: `level` from 1, never 0
            row |= {tally: [max(_held(body, tally), int(tally == "level")) for body in (past, actor)] for tally in wanted if tally in _TALLIES}
        if since and not has:  # filed by what befell it: an arrival bears no mark of its own, read off the others it would be guessed
            row["part"] = _filed_as(change)
        lines.append((*placed(actor["id"], figure, actor), row))
    _refuse_unseen(fields, seen | {"killed_by"} if mourned else seen)
    parted = since and not has
    fell = kept_deaths(save) if top == "died" else {}
    lines.extend((*placed(row["id"], fell=fell[row["id"]]["died"] if fell else 0.0), row) for row in gone)  # a dead line's `part` said beside `has:` too
    if parted and members_then is not None and entity and "left" in told_parts:  # alive and elsewhere now: left the entity, which a death does not say
        for a in sorted((a for a in save.get("actors_data") or [] if a["id"] in members_then and not belongs(a)), key=itemgetter("id")):
            here = stands_on(a, island_of, grid, save["tileMap"])
            row = fielded(a, here, {"part": "left"})
            row |= towards(a["id"], *actor_xy(a)) if near else {}  # before `placed`, which ranks on the length it records
            lines.append((*placed(a["id"]), row))
    if parted:
        lines = told_part(lines, told_parts)
    living = bool(told_parts - {"died", "left"})  # who stood still or only grew is a living part's tally: beside the dead alone it would read as theirs
    unseen = [f"{still} stood still" if still else "", f"{aged} only grew (`--filter grew`)" if aged else ""] if living else []
    by = f"nearest the {'body' if near[1] is not None else 'tile'}" if near else "as they fell" if top == "died" else f"by {top}" if top else "by id"
    return roll(lines, limit, "bodies", by, [f"{unranked} with no {top}" if unranked else "", *unseen])


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
            taken["land"].add(int(word[1:]) if word[1:].isdigit() else ISLET if word.startswith("islet") else word)
        elif group := next((name for name, words in groups.items() if word in words), None):
            taken[group].add(word)
        else:  # every word and key in `gloss actor.roster`, the closest few offered
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
        if born and (overgrowth(body) != 1 or not born[1] <= dead["born"] < born[2]):  # a migrant told by the last save that saw it alive
            continue
        # Its name and sex at death the register's, not the last save's — a register older than its sex falls back on it; `was_on` silent under a lone land
        row = {
            "blow": dead["blow"],
            "died": world_date(dead["died"]),
            "died_of": dead["cause"],
            "id": dead["id"],
            "part": "died",
            "was_on": None if lone else standing(dead),
        }
        kept = {  # its socle, or under `--with` what is asked of it: the tile it fell on, born, its killer, and parents with WB's -1 already dropped
            "asset_id": None if one_kind(kinds) else dead["asset_id"],
            "at": tile_text(dead["x"], dead["y"]),
            "born": world_date(dead["born"]),
            "killed_by": alive_or_dead_ref(dead["killer"], alive, deaths),
            "name": dead["name"] or body.get("name"),
            "parents": sorted(dead["parents"]) or None,
            "sex": dead["sex"] or (sex_label(last[dead["id"]]) if dead["id"] in last else None),
            **{tally: _held(body, tally) or None for tally in _TALLIES if tally in fields},  # what it took away, as the last save saw it alive
            **({"zone_of": zone_at_death(dead)} if "zone_of" in fields else {}),  # a save read for it: asked alone
        }
        socle = row | {key: kept[key] for key in _DEAD_SOCLE}
        gives = [key for key in _DISPLACED if key in _DEAD_SOCLE and kept[key] is not None]  # its name, then its kind: its sex stays
        rows.append(make_room(socle, {field: kept[field] for field in fields if field in kept and field not in _DEAD_SOCLE}, gives, owed=driving))
    return sorted(rows, key=lambda row: row["id"])


# The words a mistyped one is closest to, offered after a refusal: ` (`teen`?)`, nothing where none comes near.
def _guessed(word: str, known: Sequence[str]) -> str:
    return f" ({', '.join(f'`{near}`' for near in close)}?)" if (close := difflib.get_close_matches(word, known, cutoff=0.7)) else ""


# A body's measure as `has:`, `lacks:` and `--rank` weigh it — `level` counts past 1, WB's floor. A skill, an arsenal or the age asks for `ctx`.
def _held(actor: dict, tally: str, ctx: dict | None = None) -> int:
    if tally in _HELD:  # the key absent where none is held: WB writes no -1; a dead mate is none, as `--with lover` tells
        held = actor.get(_HELD_FIELDS.get(tally) or _MEMBERSHIPS[tally][1])
        return int(held is not None and (tally != "lover" or ctx is None or held in ctx["living_ids"]))
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
    weighed = sorted((*_TALLIES, *_HELD))
    if (choices := {"barred": GATES, "died": _DEATH_CAUSES, "has": weighed, "lacks": weighed}.get(key)) and said not in choices:
        told = f"filters nothing{guess}" if (guess := _guessed(said, choices)) else f"— `{key}:` takes {', '.join(choices)}"  # the list only for no near one
        raise argparse.ArgumentTypeError(f"`{key}:{said}` {told}")
    if key == "born":
        return date_span(said)
    if key == "patch":
        return xy_arg(said)
    if key in _KEYED and not said:
        raise argparse.ArgumentTypeError(f"`{key}:` takes a value")
    if key not in _KEYED:
        raise argparse.ArgumentTypeError(f"`{key}:{said}` filters nothing{_guessed(f'{key}:', [f'{known}:' for known in (*_MEMBERSHIPS, *_KEYED)])}")
    return said


# A land as a refusal says it: `land 23`, `the islets`, `the water`.
def _land_told(land: int | str) -> str:
    return f"land {land}" if isinstance(land, int) else "the islets" if land == ISLET else "the water"


# A line widened by `added`: one field of `gives_way` driven off per new field, or `owed` where the caller counts them — never more, every line alike.
def make_room(row: dict, added: dict, gives_way: Sequence[str], owed: int | None = None) -> dict:
    owed = len([key for key in added if key not in row]) if owed is None else owed
    gone = [key for key in gives_way if row.get(key) is not None and key not in added][:owed]
    return {key: value for key, value in row.items() if key not in gone} | added


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
        f"carrying {args.gear}" if args.gear else None,
        f"at the {' or '.join(s for s in _LIFE_STAGES if s in args.stage)} stage" if args.stage else None,
        "that could found a town where it stands" if args.settle else None,
        (f"kept from founding by {args.bar}" if args.bar else "kept from founding by more than its age") if args.barred else None,
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


# A lone `type:` names the kind of every line, its `asset_id` then unsaid — as a lone land its own, every roll alike.
def one_kind(kinds: Collection[str] | None) -> bool:
    return kinds is not None and len(kinds) == 1


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
        raise ValueError(refused("--with", unknown, seen, "`gloss actor.roster.--with`, `actor <id> stats`"))


# A field an option takes on no line of the roll, refused alike under every `--roster`: the closest offered, then `where` the fields are told.
def refused(option: str, asked: Sequence[str], known: Collection[str], where: str) -> str:
    guess = "".join(_guessed(field, sorted(known)) for field in asked)
    return f"✗ {', '.join(f'`{field}`' for field in asked)}: no `{option}` field{guess} — {where}"


# A roll as every `--roster` gives it: each line `(order, tie, row)`, sorted, cut at `limit` with a tie kept whole — the cut and `notes` said beside, one `⚠`.
def roll(lines: Sequence[tuple[object, object, dict]], limit: int | None, noun: str, by: str, notes: Sequence[str] = ()) -> list[dict]:
    lines = sorted(lines, key=itemgetter(0))
    kept = len(lines) if limit is None else _tied_cut([tie for _, tie, _ in lines], limit)
    cut = f"{len(lines)} {noun}, the first {kept} {by} — `--limit all` for every one" if kept < len(lines) else ""
    if told := [note for note in (cut, *notes) if note]:  # what the list leaves out, said beside it: the list keeps its shape
        print(f"⚠ {'; '.join(told)}", file=sys.stderr)
    return [row for *_, row in lines[:kept]]


# `--roster` taken off a call, the rest handed back — `None` where an id came with it, refused there: a roll reads every one of its kind.
def roster_call(argv: list[str], noun: str, tool: str) -> list[str] | None:
    rest = [arg for arg in argv if arg != "--roster"]
    if rest[:1] and rest[0].isdigit():
        print(f"✗ `--roster` lists every {noun}: no id — `{tool} {rest[0]}` reads one", file=sys.stderr)
        return None
    return rest


# A body's stage off its raw span alone, as `surroundings` reads one: a roster line and a census say it alike.
def _stage(actor: dict, ctx: dict, age: int, adult: float) -> str:
    return life_stage(age, adult, body_lifespan(actor, ctx), is_egg(actor, ctx))


# Where a body stands as `roster` tells it: its land, else `water` where it floats and `islet` on an islet too small to count, as `surroundings` splits them.
def stands_on(actor: dict, island_of: TileIslands, grid: LazyTileGrid, names: list[str]) -> int | str:
    x, y = actor_xy(actor)
    if (land := island_of.get((x, y))) is not None:
        return land
    return WATER if off_land(names[grid[y][x]]) == "water" else ISLET


# An earlier chapter's save for `--since`, and the land each body stood on in it: what the roster weighs against it, the dead read off it alone.
def _then(chapter: str) -> tuple[dict, dict[int, int | str]]:
    then_path = SAVES_DIR / chapter / "map.wbox"
    then = load_save(then_path)
    island_of, grid = compute_islands_cached(then, then_path)[1], LazyTileGrid(then)
    return then, {actor["id"]: stands_on(actor, island_of, grid, then["tileMap"]) for actor in then.get("actors_data") or [] if not is_boat(actor)}


# A body's tie to one entity: a pact through its crown, every other by its own field — `fallen` given under `king` alone, a king to his realm.
def _tie(save: dict, kind: str, entity_id: int | str, fallen: dict[int, int]) -> Callable[[dict], bool]:
    if kind == "job":  # a trade, the crown and an army's lead among them
        if fallen:
            return lambda actor: resolve_profession(actor, save) == entity_id or actor["id"] in fallen
        return lambda actor: resolve_profession(actor, save) == entity_id
    if kind == "alliance":
        crowns = {kid for pact in save.get("alliances") or [] if pact.get("id") == entity_id for kid in pact.get("kingdoms") or []}
        return lambda actor: actor.get("civ_kingdom_id") in crowns
    if kind == "war":
        camps = set().union(*war_camps(index_by_id(save.get("wars") or []).get(entity_id) or {}))
        return lambda actor: actor.get("civ_kingdom_id") in camps
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


# A `--since` roll's parts: one asked, the filter says it and no line repeats it — several, each line its own `part`, every roll alike.
def told_part[O, T](lines: list[tuple[O, T, dict]], parts: Collection[str]) -> list[tuple[O, T, dict]]:
    return [(order, tie, {**row, "part": None}) for order, tie, row in lines] if len(parts) == 1 else lines


# A dead body's camp in a war, `None` where it is no dead of that war: struck down since the declaration by a body of the other camp, as WB's camp tolls count it.
def _war_side(save: dict, war_id: int, upto: int) -> Callable[[int], str | None]:
    war = index_by_id(save.get("wars") or []).get(war_id) or {}
    attackers, defenders = war_camps(war)
    declared, crowns, deaths = float(war.get("created_time") or 0), crowns_served(save, upto), kept_deaths(save)

    def side(body_id: int) -> str | None:
        dead = deaths[body_id]
        if dead["died"] < declared or dead["killer"] is None or dead["cause"] == "metamorphosis":  # WB credits no kill on a change
            return None
        crown, killer = crowns_at_death(dead, crowns)
        camp, foes = ("attackers", defenders) if crown in attackers else ("defenders", attackers) if crown in defenders else (None, set())
        return camp if camp and (killer is None or killer in foes) else None  # a killer of unknown crown counted, as `war`'s nobles are

    return side


# The weapon in its hand, by its kind: what tells an armed body, where `job` tells only its post — none for one empty-handed.
def _weapon(actor: dict, items_by_id: dict[int, dict]) -> str | None:
    weapons = weapon_assets()
    return next((kind for item in actor.get("saved_items") or () if (kind := (items_by_id.get(item) or {}).get("asset_id")) in weapons), None)


# `actor --roster`, the call past `--roster` handed over by `actor`: every body of the world as its options leave them, a stray argument refused.
def roster_main(argv: list[str]) -> int:
    try:
        since, argv = take_since(argv)
    except ValueError as e:
        print(f"✗ {e}", file=sys.stderr)
        return 2
    save_path, argv, chapter = take_chapter(argv)
    parser = arg_parser(prog="actor/info.py --roster", taken="[--since C<n>] [C<n>]", gloss="actor.roster")
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
    # One each: a second would ask another roll
    singles = (*_MEMBERSHIPS, "barred", "born", "died", "gear", "has", "job", "lacks", "patch", "status", "task", "trait")
    if several := next((key for key in singles if len(picked[key]) > 1), None):
        print(f"✗ {several}: one at a time — ask each apart", file=sys.stderr)
        return 2
    for kind in _MEMBERSHIPS:
        setattr(args, kind, next(iter(picked[kind]), None))
    args.born, args.died_of, args.gear, args.has, args.job, args.lacks, args.patch, args.status, args.task, args.trait = (
        next(iter(picked[key]), None) for key in ("born", "died", "gear", "has", "job", "lacks", "patch", "status", "task", "trait")
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
    args.sapient, args.beasts, args.settle = "sapient" in mind, "beasts" in mind, "settle" in founding
    args.bar = next(iter(picked["barred"]), None)  # one gate named: those it shuts, the bare word any
    args.barred = "barred" in founding or args.bar is not None
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
    limit = LIMIT if args.limit is None else args.limit or None  # `all` read as 0: every line
    entities = [(kind, entity_id) for kind in _MEMBERSHIPS if (entity_id := getattr(args, kind)) is not None] + ([("job", args.job)] if args.job else [])
    if not entities:  # none to leave: `left` refused if named, else dropped from the default parts
        if "left" in (asked_parts or ()):
            print("✗ `left` is an entity's: name one — `city:<id>`, `family:<id>`, `king`…", file=sys.stderr)
            return 2
        told_parts -= {"left"}
    if args.beasts and (other := next((flag for flag in ("settle", "barred") if getattr(args, flag)), None)):  # a founding is a thinker's alone
        print(f"✗ beasts and {other} split the bodies in two: filter by one", file=sys.stderr)
        return 2
    if args.has and args.lacks:  # the two halves of a roll by one tally: together they name no one
        print("✗ has: and lacks: split a roll in two: filter by one", file=sys.stderr)
        return 2
    if args.top == "died" and (not since or told_parts != {"died"}):  # the dead as they fell, the one order a `--since` roll takes
        print("✗ `--rank died` orders the dead of a `--since` roll alone: `--since C<n> --filter died`", file=sys.stderr)
        return 2
    if args.top and since and args.top != "died":  # a measure read off its own chapter
        print(f"✗ `--rank` ranks one chapter: read the other by its suffix, `{since}`", file=sys.stderr)
        return 2
    if since and args.has in _HELD:  # a tie held is a state, not a count that moves: which one changed, `actor … since` tells
        print(f"✗ `has:{args.has}` reads one chapter: ask `--since` apart", file=sys.stderr)
        return 2
    if since and (alone := next((flag for flag in ("gear", "lacks", "patch", "status", "task") if getattr(args, flag)), None)):
        print(f"✗ `{alone}:` reads one chapter: ask `--since` apart", file=sys.stderr)  # the dead stood, wore and did what no later save tells
        return 2
    if since and not (SAVES_DIR / since / "map.wbox").exists():
        print(f"✗ no save for {since}", file=sys.stderr)
        return 2
    save = load_save(save_path)
    families = asset_families(save) if args.type else {}  # swept for `type:` alone: every body and every building
    kinds, later = asset_kinds(families, args.type) if args.type else None, since_saves(since, chapter, save) if since else []
    counted, island_of = compute_islands_cached(save, save_path)  # loaded once: the lands named are checked against the lookup the roll then reads
    if unknown := sorted(set(args.lands or ()) - {each["id"] for each in counted} - {ISLET, WATER}):
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
    if args.gear:  # refused by what this world carries, as a status by what it wears — swept only for a roll that asks it
        kinds_of = {item["id"]: item.get("asset_id") for item in save.get("items") or []}
        carried = {kind for actor in save.get("actors_data") or [] for item in actor.get("saved_items") or () if (kind := kinds_of.get(item))}
        if args.gear not in carried:
            print(f"✗ no body carries {args.gear}{_guessed(args.gear, sorted(carried))} — `actor <id> gear` names a body's", file=sys.stderr)
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
            print(absent_entity("actor", "actors_data", point, chapter, lambda a: not is_boat(a), aim="--rank"), file=sys.stderr)
            return 1
        near = actor_xy(body), point
    patch = None
    if args.patch:
        if island_of.get(args.patch) is None:  # off the map as on the water: a patch is one ground of one counted land
            print(f"✗ {args.patch[0]},{args.patch[1]} stands on no counted land — `tiles <x,y> tile_info` tells what a tile is", file=sys.stderr)
            return 2
        patch = patch_finder(save, LazyTileGrid(save), island_of)(*args.patch)[0]
    fields = list(dict.fromkeys(",".join(args.fields).split(","))) if args.fields else []
    if len(fields) > MAX_FIELDS:
        print(f"✗ `--with` takes {MAX_FIELDS} fields at most — `actor <id> stats` gives a body's whole sheet", file=sys.stderr)
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
            args.gear,
            args.bar,
        )
    except ValueError as e:  # a field `--with` asks that no body of the roll carries
        print(e, file=sys.stderr)
        return 1
    if not roster:  # a filter nothing answers, never a silent `{}`
        print(_nobody(args, kinds, save, since, told_parts), file=sys.stderr)
        return 1
    emit(roster)
    return 0
