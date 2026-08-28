# Cross-domain constants + helpers — one of the `tools/lib/` libraries every entry point puts on its `sys.path` (see each bootstrap).
# Rule: a symbol lives here only if ≥2 scripts need it — directly, or through another exported symbol that does. Single-script helpers live in that script.

import json
import os
import pickle
import re
import subprocess
import sys
import zlib
from bisect import bisect_right
from collections import Counter
from collections.abc import Mapping, Sequence
from functools import cache
from pathlib import Path

CACHE_DIR = Path(__file__).parent.parent / ".cache"  # holds the save and islands pickles alike; gitignored via the root `.gitignore`

# WB `CityData.item_storage_*` — the six racks a settlement stores gear on, keyed by the tab its « Équipement » panel shows rather than the save field.
EQUIPMENT_RACKS = {
    "amulets": "item_storage_amulets",
    "armor": "item_storage_armor",
    "boots": "item_storage_boots",
    "helmets": "item_storage_helmets",
    "rings": "item_storage_rings",
    "weapons": "item_storage_weapons",
}

MIN_PER_CAPITA_UNITS = 3  # Below three souls a per-head ratio measures the divisor, not the body — a lone survivor would top every podium.
NON_FOOD_SPECIES = frozenset({"skeleton"})  # WB `needsFood`=false (undead have no diet ⇒ never hungry); excluded from `fed_pct`.
PROFESSION_KING = 3  # WB `profession` ints — see `_PROFESSIONS` for the full map.
PROFESSION_LEADER = 4
PROFESSION_WARRIOR = 5
SATED_MIN_NUTRITION = 60  # `fed_pct` threshold: nutrition ratio ≥ 0.6 (like `tier-high`) — stricter than WB's own `isHungry` (≤ 50).
SAVES_DIR = Path(__file__).parents[2] / "saves"  # Single source of truth for the chapter dirs `C<n>/`; `chapter/` reaches back to `C<n-1>` through it.
SICK_TRAITS = frozenset({"infected", "mush_spores", "plague", "tumor_infection"})  # WB `calculateIsSick` traits — `infected` ⊂ `sick`.
UNITS_PER_YEAR = 60  # 60 `world_time` units = 1 year (12 months × 5 units).
ZONE_TILES = 8  # WB `TileZone` side (tiles): `zones` are in zone units — divide tile coords by this; centre = `z*ZONE_TILES + ZONE_TILES//2`.

_ASCENSION_STATS = {"diplomatic_ascension": "diplomacy", "warriors_ascension": "warfare"}  # Culture succession by that stat (else renown, coins, age).
_BIOME_ALIASES = {"pumpkin": "super_pumpkin", "singularity": "singularity_swamp"}  # One lore under two WB spellings: its tiles say one, its biome sheet the other.
_BOOK_POINTS = 12  # what authoring one is worth in `book_reach`, before its readings — ours to set, WB scores books nowhere.
_CACHE_KEEP = 20  # slots for a world's chapters plus the live save, a few Mo each: chapters sharing a `map.wbox` share one, so a long game still fits
_CAPTURE_PROFESSIONS = frozenset({3, 4, 5})  # WB `ProfessionAsset.can_capture` — `PROFESSION_KING`/`_LEADER`/`_WARRIOR`, spelt out: they sort after this.

# The seven verdicts only a settlement can answer, WB slotting them between the moods and the headcounts — a biology or a band keeps no granary to run dry.
_CITY_STORES = ("food_none", "food_plenty", "food_running_out", "wood_none", "stone_none", "gold_none", "metal_none")

_COMPRESSION = 9  # WB reads any zlib stream; the tightest level keeps a rewritten save a shade smaller than the one it replaces
_DATAS_DIR = Path(__file__).parent.parent / "datas"
_ELDER_AGE_RATIO = 0.7  # WB `Actor.isPrettyOld`: an actor is « old » once age / lifespan exceeds this.
_EMOTION_TRAIT = "amygdala"  # WB `SubspeciesTraitLibrary`: the one trait tagged `has_emotions` — the sole reader, and the reason this stays private.
_EMPTY_VALUES = (None, [], {})  # module-level so `_strip_none` doesn't rebuild a list and a dict at every node it tests.
_HEAD_FIELD = {"city": "leaderID", "kingdom": "kingID"}  # WB names the office-holder apart on each tier.
_INLINE_WIDTH = 165  # `emit` collapses a dict/list onto one line when it fits this width, else expands — compact yet readable, fewer tokens.
_LEVEL_RE = re.compile(r"(\d+)$")  # trailing enchant tier on a modifier id (`power5`) — `re` rides in free, `pathlib` already pulls it.

_META_CONDITIONS = {  # WB `MetaTextReportLibrary`, one lambda per verdict, ported field for field — ratios are shares of the living, stocks raw amounts.
    "food_none": lambda s: not s["food"],
    "food_plenty": lambda s: s["food"] > s["people"] * 4,
    "food_running_out": lambda s: s["food"] and s["food"] < s["people"] * 2,
    "gold_none": lambda s: not s["gold"],
    "happy": lambda s: s["happy"] > 0.8,
    "many_children": lambda s: s["units"] >= _META_REPORT_MIN_UNITS and s["children"] > 0.7,
    "many_homeless": lambda s: s["units"] >= _META_REPORT_MIN_UNITS and s["homeless"] > 0.8,
    "metal_none": lambda s: not s["common_metals"],
    "stone_none": lambda s: not s["stone"],
    "unhappy": lambda s: s["unhappy"] > 0.8,
    "war_attackers_getting_captured": lambda s: s["attackers_besieged"] and not s["defenders_besieged"],
    "war_defenders_getting_captured": lambda s: s["defenders_besieged"] and not s["attackers_besieged"],
    "war_fresh": lambda s: s["age"] < 5,
    "war_full_on_battle": lambda s: s["attackers_besieged"] and s["defenders_besieged"],
    "war_high_casualties": lambda s: s["deaths"] > 100,
    "war_long": lambda s: s["age"] > 100,
    "war_quiet": lambda s: not s["attackers_besieged"] and not s["defenders_besieged"],
    "wood_none": lambda s: not s["wood"],
}

# WB `MetaTypeAsset.reports`: every body carries its own ordered list. Eight collectives share `meta` word for word; only the city weighs its stores as well.
_META_REPORTS = {
    "army": ("happy", "unhappy"),  # WB gives a host only its two moods: it holds no town, bears no young and sleeps where it marches.
    "city": ("happy", "unhappy", *_CITY_STORES, "many_children", "many_homeless"),  # its stores wedged into the moods every other body answers with
    "meta": ("happy", "unhappy", "many_children", "many_homeless"),
    "war": ("war_high_casualties", "war_long", "war_fresh", "war_defenders_getting_captured", "war_attackers_getting_captured", "war_quiet", "war_full_on_battle"),
}

_META_REPORT_MIN_UNITS = 20  # WB's own gate on `many_children` and `many_homeless` — the two that count heads rather than weigh hearts.
_MIN_LEADERS_UNITS = 5  # below this a podium names a champion among two or three — the body is too small for any of its members to stand out
_MIN_SUMMARY_ENTRIES = 5  # Under this, summarising saves a few dozen characters and still forces the follow-up call — the full form travels instead.
_PROFESSIONS = {2: "civilian", 3: "king", 4: "leader", 5: "warrior"}  # WB `profession` int → label; 0 none, 1 (`Baby`) unused, `unit` renamed after `is_civilian`.
_SETTINGS_JSON = SAVES_DIR.parent / "history" / "settings.json"  # where the reader records the live save, WorldBox keeping it elsewhere on every OS
_VALUE_ORDERED = frozenset({"drivers", "inventory", "taxonomy"})  # shapes whose key order carries meaning: stores heaviest-first, ranks broadest-first

_books_memo: list = [None, None]  # `books_held`'s one slot: (save, result). Module state rather than `@cache` — a save dict is unhashable.
_captains_memo: list = [None, None]  # `resolve_profession`'s one slot: (save, captain ids). Same reason as `_books_memo`, and the same single-save lifetime.


# `_BOOK_POINTS` per volume plus its readings. A razed author-town would strand that reach, so the book goes to whoever shelves it — `holder_of` picks the tier.
def _book_reach(save: dict, author_field: str, living: set, holder_of) -> Counter:
    _, _, city_of_book = books_held(save)
    reach: Counter = Counter()
    for book in save.get("books") or []:
        owner = book.get(author_field)
        if owner not in living:
            owner = holder_of(city_of_book.get(book.get("id")))
        if owner is not None:
            reach[owner] += _BOOK_POINTS + (book.get("times_read") or 0)
    return reach


# The live save: `WB_SAVE` first, else what the reader's settings panel recorded — never guessed from the platform. A `C<n>` in argv beats both, wherever it sits.
def _current_save() -> Path | None:
    if override := os.environ.get("WB_SAVE"):
        return Path(override)
    try:
        return Path(json.loads(_SETTINGS_JSON.read_text())["savePath"])
    except (KeyError, OSError, ValueError):
        return None


# Item base stats + its modifiers' bonuses, floats trimmed to 4 decimals (ints when whole), zeros dropped.
def _equipment_stats(asset_id: str, modifiers: list[str], item_stats: dict, mod_stats: dict) -> dict:
    out = dict((item_stats.get(asset_id) or {}).get("stats") or {})
    for mod in modifiers:
        for k, v in mod_stats.get(mod, {}).items():
            out[k] = out.get(k, 0) + v
    result = {}
    for k, v in out.items():
        if isinstance(v, float):
            v = round(v, 4)
            if v.is_integer():
                v = int(v)
        if v:
            result[k] = v
    return dict(sorted(result.items()))


# The families with someone on the ground: `oldest`/`kills`/`deaths` are WB's own counters, `population`/`renown` are scoped to who is present.
def _family_leaders(actors: Sequence[dict], families_by_id: dict) -> dict:
    members: Counter = Counter()
    renown: Counter = Counter()

    for actor in actors:
        if family_id := actor.get("family"):
            members[family_id] += 1
            if fame := actor.get("renown"):
                renown[family_id] += int(fame)

    present = [family for fid in members if (family := families_by_id.get(fid))]
    if not present:
        return {}
    picks = {
        "deaths": _top_by(present, lambda f: int(f.get("total_deaths") or 0)),
        "kills": _top_by(present, lambda f: int(f.get("total_kills") or 0)),
        "population": _top_by(present, lambda f: members[f["id"]]),
        "renown": _top_by(present, lambda f: renown[f["id"]]),
    }
    out = {name: _leader_ref(family) for name, family in picks.items() if family is not None}
    out["oldest"] = _leader_ref(min(present, key=lambda f: (float(f.get("created_time") or 0), f["id"])))
    return dict(sorted(out.items()))


# `{id, name}` off a record carrying its own name — a family or an actor the caller already holds. `emit` drops `name` where WB wrote none, leaving `{id}` alone.
def _leader_ref(record: dict) -> dict:
    return {"id": record["id"], "name": record.get("name")}


# The standout souls. `hungriest` skips the undead, who hold no nutrition to be low on; the combat stats share one pass, that being the cost.
def _person_leaders(actors: Sequence[dict], children: Mapping[int, int], stat_of) -> dict:
    picks = {
        "births": _top_by(actors, lambda a: int(a.get("births") or 0)),
        "children": _top_by(actors, lambda a: children.get(a["id"], 0)),
        "kills": _top_by(actors, lambda a: int(a.get("kills") or 0)),
        "level": _top_by(actors, lambda a: int(a.get("level") or 0)),
        "money": _top_by(actors, lambda a: int(a.get("money") or 0)),
        "renown": _top_by(actors, lambda a: int(a.get("renown") or 0)),
    }
    scored = [(actor, stat_of(actor)) for actor in actors]

    for name in ("damage", "health", "intelligence", "speed"):
        actor, stats = max(scored, key=lambda pair: (pair[1].get(name, 0), -pair[0]["id"]))
        picks[name] = actor if stats.get(name, 0) > 0 else None

    out = {name: _leader_ref(actor) for name, actor in picks.items() if actor is not None}
    out["oldest"] = _leader_ref(min(actors, key=lambda a: (float(a.get("created_time") or 0), a["id"])))
    out["youngest"] = _leader_ref(max(actors, key=lambda a: (float(a.get("created_time") or 0), -a["id"])))

    if eaters := [a for a in actors if (a.get("asset_id") or "") not in NON_FOOD_SPECIES]:
        out["hungriest"] = _leader_ref(min(eaters, key=lambda a: (int(a.get("nutrition") or 0), a["id"])))
    return dict(sorted(out.items()))


def _save_cache_name(path: Path) -> str:
    return f"save_v1_{save_cache_key(path)}.pkl"


# Borda shared by both composites → `{id: place}`, 1 = strongest: each dimension awards `N − those strictly ahead`, a 0 none — so thousands can't drown tens.
def _score_ranks(ids: list[int], dimensions: dict[str, dict]) -> dict[int, int]:
    if not ids:
        return {}
    totals: Counter = Counter()
    for values in dimensions.values():
        owns = [values.get(eid, 0) for eid in ids]  # read once, then sorted: those at or below `own` are exactly `N − those ahead`, one sort per dimension.
        ordered = sorted(owns)
        for eid, own in zip(ids, owns):
            if own > 0:
                totals[eid] += bisect_right(ordered, own)
    return {eid: place + 1 for place, eid in enumerate(sorted(ids, key=lambda eid: (-totals[eid], eid)))}


# Drop `None`, `[]` and `{}` from a nested JSON-like structure — chronicler tokens optimisation. `0`/`""`/`False` are preserved (semantically meaningful values).
def _strip_none(value):
    if isinstance(value, dict):
        return {k: stripped for k, v in value.items() if (stripped := _strip_none(v)) not in _EMPTY_VALUES}
    if isinstance(value, list):
        return [stripped for v in value if (stripped := _strip_none(v)) not in _EMPTY_VALUES]
    return value


# Highest `key`, ties to the lowest id. `None` when nobody scores above zero — a settlement without a killer has no deadliest soul, and that is not a zero.
def _top_by(records: Sequence[dict], key) -> dict | None:
    best = max(records, key=lambda r: (key(r), -r["id"]), default=None)
    return best if best is not None and key(best) > 0 else None


# Orphan slots go — a chapter's save never changes, where the live one mints a fresh key at every in-game save. `_CACHE_KEEP` then caps what survives, newest first.
def _write_save_cache(cache_file: Path, save: dict) -> None:
    CACHE_DIR.mkdir(exist_ok=True)
    with cache_file.open("wb") as f:
        pickle.dump(save, f, protocol=5)
    live = _current_save()
    claimed = {_save_cache_name(p) for p in ([live] if live else []) + list(SAVES_DIR.glob("C*/map.wbox"))}
    cached = list(CACHE_DIR.glob("save_v1_*.pkl"))
    kept = sorted((f for f in cached if f.name in claimed), key=lambda f: f.stat().st_mtime, reverse=True)
    for doomed in [f for f in cached if f.name not in claimed] + kept[_CACHE_KEEP:]:
        doomed.unlink(missing_ok=True)


# Years lived, as the WB tooltip reads it: elapsed world time plus `age_overgrowth`, the years a soul carries past its species' cap.
def actor_age(actor: dict, world_time: float) -> int:
    return entity_age(actor, world_time) + (actor.get("age_overgrowth") or 0)


# WB `Subspecies.calculateAgeRelatedStats`: lifespan > 30 → (16, 18); else `Pow(lifespan, 0.55)×1.1` capped 16/18 (civ species always > 30).
def age_thresholds(lifespan: float) -> tuple[float, float]:
    if lifespan > 30:
        return 16.0, 18.0
    adult = min((lifespan**0.55) * 1.1, 16.0)
    return adult, min(adult, 18.0)


# A named set of WB asset ids (`food`, `ranged`) from `datas/asset-sets.json`. A cached function, not a constant: `load_data` is defined below.
@cache
def asset_set(name: str) -> frozenset[str]:
    return frozenset(load_data("asset-sets.json").get(name) or ())


# WB `City.isGettingCaptured`: the enemy crowns whose warriors, kings or leaders stand in a town's zones — WB excuses one indoors, which a save never records.
def besieging_kingdoms(save: dict) -> dict[int, set[int]]:
    enemies: dict[int, set[int]] = {}
    for war in save.get("wars") or []:
        if not war.get("winner"):
            sides = [({war.get(f"main_{camp}")} | set(war.get(f"list_{camp}s") or [])) - {None} for camp in ("attacker", "defender")]
            for side, foes in (sides, sides[::-1]):
                for kid in side:
                    enemies.setdefault(kid, set()).update(foes)
    zone_city = {(z["x"], z["y"]): c["id"] for c in save.get("cities") or [] for z in c.get("zones") or []}
    owner = {c["id"]: c.get("kingdomID") for c in save.get("cities") or []}
    besieging: dict[int, set[int]] = {}
    for actor in save.get("actors_data") or []:
        if actor.get("profession") not in _CAPTURE_PROFESSIONS or is_aboard(actor) or not (kid := actor.get("civ_kingdom_id")):
            continue
        cid = zone_city.get((int(actor["x"]) // ZONE_TILES, int(actor["y"]) // ZONE_TILES))
        if cid is not None and kid in enemies.get(owner[cid], ()):
            besieging.setdefault(cid, set()).add(kid)
    return besieging


# What `datas/biomes.json` says of a biome, whichever of WB's two spellings it is asked under — `{}` for a tile that carries none.
def biome_lore(biome_id: str | None) -> dict:
    if not biome_id:  # a tile carrying no biome, and the one lookup that would otherwise take `None` for a key
        return {}
    return load_data("biomes.json").get(_BIOME_ALIASES.get(biome_id, biome_id)) or {}


# Books sit in a settlement's hall (`buildings[].books.list_books`), so their holder is that city and its crown. Memoised: a `full` run asks twice, 15 k rows each.
def books_held(save: dict) -> tuple[Counter, Counter, dict[int, int]]:
    if _books_memo[0] is save:
        return _books_memo[1]
    kingdom_of_city = {c["id"]: c.get("kingdomID") for c in save.get("cities") or []}
    by_city: Counter = Counter()
    by_kingdom: Counter = Counter()
    city_of_book: dict[int, int] = {}
    for building in save.get("buildings") or []:
        shelved = ((building.get("books") or {}).get("list_books")) or []
        if not shelved or (cid := building.get("cityID")) is None:
            continue
        by_city[cid] += len(shelved)
        for book_id in shelved:
            city_of_book[book_id] = cid
        if (kid := kingdom_of_city.get(cid)) is not None:
            by_kingdom[kid] += len(shelved)
    _books_memo[0], _books_memo[1] = save, (by_city, by_kingdom, city_of_book)
    return by_city, by_kingdom, city_of_book


# Summarised, a trait keeps its id and the one field the caller weighs it on — a creature's carries both, sorted on its group where graded on its rarity.
def build_trait_ids(trait_ids: list[str], traits_data: dict, key: str) -> dict | list[str]:
    entries = {tid: traits_data.get(tid) or {} for tid in trait_ids or []}
    weighed = {tid: tag for tid, entry in sorted(entries.items()) if (tag := entry.get(key))}
    return weighed or sorted(entries)


# Trait entries with their stats, WB's English `name` and whichever narrative field the library carries: a group everywhere, a rarity on a creature's. Sorted by id.
def build_trait_list(trait_ids: list[str], traits_data: dict) -> list[dict]:
    out = []
    for tid in trait_ids or []:
        entry = traits_data.get(tid) or {}
        item: dict = {"id": tid, "stats": entry.get("stats") or {}}
        for key in ("description", "flavor", "group", "name", "rarity"):
            if key in entry:
                item[key] = entry[key]
        out.append(item)  # keys left as inserted: `render` sorts every record-shaped dict on the way out, so ordering them here would be sorting twice
    return sorted(out, key=lambda t: t["id"])


# Living children per parent, counted off `parent_id_1`/`parent_id_2`. World-wide on purpose — a parent's brood is theirs wherever it settled.
def children_by_id(save: dict) -> Counter:
    tally: Counter = Counter()
    for actor in save.get("actors_data") or []:
        for parent in (actor.get("parent_id_1"), actor.get("parent_id_2")):
            if parent:
                tally[parent] += 1
    return tally


# WB's own anchor for a town (`updateCityCenter`), so what sites one and what distances aim at: the zone centre closest to their average, nudged 2 tiles north.
def city_centre(city: dict) -> tuple[int, int] | None:
    zones = [(z["x"] * ZONE_TILES + ZONE_TILES // 2, z["y"] * ZONE_TILES + ZONE_TILES // 2) for z in city.get("zones") or []]
    if not zones:
        return None
    mean_x, mean_y = (sum(c) / len(zones) for c in zip(*zones))
    closest = min(zones, key=lambda z: (z[0] - mean_x) ** 2 + (z[1] - mean_y) ** 2)
    return closest[0], closest[1] + 2


# `{name: {city id: value}}` — most transposed from the kingdom, the rest village-only. Exported: `city/info.py` surfaces the ones nothing else covers.
def city_score_dimensions(save: dict) -> dict[str, dict]:
    cities = save.get("cities") or []
    civic = civic_building_ids()
    elite: Counter = Counter()  # the four per-inhabitant tallies, gathered in one pass rather than by re-walking per-city actor lists
    money: Counter = Counter()
    population: Counter = Counter()
    warriors: Counter = Counter()

    # Guarded rather than summed blind: three of these four are zero on most actors, and a `+= 0` still costs a hash and a store. Absent reads back as 0 anyway.
    for actor in save.get("actors_data") or []:
        if (cid := actor.get("cityID")) is None or is_boat(actor):
            continue
        population[cid] += 1
        if renown := actor.get("renown"):
            elite[cid] += renown
        if coins := actor.get("money"):
            money[cid] += coins
        if actor.get("profession") == PROFESSION_WARRIOR:
            warriors[cid] += 1

    buildings: Counter = Counter()  # civic only — `save.buildings` is mostly flora and ore, which would drown the tally
    gold: Counter = Counter()

    for building in save.get("buildings") or []:
        if (cid := building.get("cityID")) is None:
            continue
        if building.get("asset_id") in civic:
            buildings[cid] += 1
        if stock := building.get("resources"):  # a handful of buildings hold one, so gating the walk beats spending an `or {}` on every wall and tree
            for resource in stock.get("saved_resources") or []:
                if resource.get("id") == "gold":
                    gold[cid] += resource.get("amount", 0)

    return {
        # Net settlers won over: `joined` had no city, `moved` came from another, `left` walked out. `migrated` is out — a world law spawns those outright.
        "attractivity": {c["id"]: c.get("joined", 0) + c.get("moved", 0) - c.get("left", 0) for c in cities},
        "book_reach": _book_reach(save, "author_city_id", {c["id"] for c in cities}, lambda cid: cid),  # a city shelves its own, so the holder is the owner
        "buildings": buildings,
        "elite": elite,  # the renown of its inhabitants — who lives there, where `renown` below is what the city itself achieved
        # Racked gear, counted apart from `wealth`: nearly orthogonal to the other nine (−0.21 with `warriors`, 0.16 with `wealth`), so it earns its own rank.
        "equipment": {c["id"]: sum(len((c.get("equipment") or {}).get(f) or []) for f in EQUIPMENT_RACKS.values()) for c in cities},
        "kills": {c["id"]: c.get("total_kills", 0) for c in cities},
        "population": population,
        "renown": {c["id"]: c.get("renown", 0) for c in cities},
        "territory": {c["id"]: len(c.get("zones") or []) for c in cities},
        "warriors": warriors,
        "wealth": {c["id"]: money[c["id"]] + gold[c["id"]] for c in cities},
    }


# Composite « settlement weight » ranking → `{city id: place}` (1 = heaviest, id-tiebroken). Drives the tag medal and the world panel's dominant village.
def city_score_ranks(save: dict, dimensions: dict | None = None) -> dict[int, int]:
    return _score_ranks([c["id"] for c in save.get("cities") or []], dimensions if dimensions is not None else city_score_dimensions(save))


# Built structures (`buildings/civ_*` in `datas/building-categories.json`), nature excluded — plus the `fishing_docks_*` that manifest omits, derived from `docks_*`.
@cache
def civic_building_ids() -> frozenset[str]:
    listed = {asset for asset, category in load_data("building-categories.json").items() if category.startswith("civ_")}
    return frozenset(listed | {f"fishing_{asset}" for asset in listed if asset.startswith("docks_")})


# Standard competition rank (1,2,2,4) among `peers` per getter — top 3 only, and a metric the entity has none of is skipped rather than given a podium at 0.
def competition_ranks(entity, peers: list, getters: dict) -> dict:
    ranks = {}
    for stat, getter in sorted(getters.items()):
        own = getter(entity)
        if own == 0:
            continue
        rank = sum(1 for p in peers if getter(p) > own) + 1
        if rank <= 3:
            ranks[stat] = rank
    return ranks


def emit(out: dict) -> None:
    print(render(_strip_none(out)))


# Years since a record was created: a city, a crown, a clan, a lineage, a biology, a roof. An actor answers to `actor_age`, which adds its `age_overgrowth`.
def entity_age(record: dict, world_time: float) -> int:
    return int((world_time - float(record.get("created_time") or 0)) / UNITS_PER_YEAR)


# `{id, name}` ref or `None` — the name feeds the narration, the id a follow-up query; an unnamed entity keeps the id and loses the key, having nothing to quote.
def entity_ref(entity_id: int | None, by_id: dict) -> dict | None:
    entity = by_id.get(entity_id) if entity_id is not None else None
    return None if entity is None else {"id": entity_id, "name": entity.get("name")}


# One equipped-or-racked item as both tiers report it: provenance (`by`/`from`), wear, kills, and its stats already folded with the modifiers' bonuses.
def equipment_entry(item: dict, item_stats: dict, mod_stats: dict, world_time: float, described: bool = False) -> dict:
    mods = sorted(item.get("modifiers") or [])
    created = item.get("created_time")
    asset_id = item["asset_id"]
    return {
        "age": int((world_time - created) / UNITS_PER_YEAR) if created is not None else None,
        "asset_id": asset_id,
        "by": item.get("by"),
        "durability": item.get("durability"),
        "from": item.get("from"),
        "id": item["id"],
        "kills": item.get("kills", 0),
        "modifiers": mods,
        "name": item.get("name"),
        "rarity": equipment_rarity(mods),
        "stats": _equipment_stats(asset_id, mods, item_stats, mod_stats),
        # chronicler-only, and only where the piece is the subject: a rack repeats one model four times, where a carried weapon characterises its bearer.
        **({"description": (item_stats.get(asset_id) or {}).get("description")} if described else {}),
    }


# Rarity = the highest numbered suffix among an item's modifiers (`…_5` ⇒ Legendary) — mirrors WB's enchant tiers.
def equipment_rarity(modifiers: list[str]) -> str:
    max_level = max((int(m.group(1)) for m in (_LEVEL_RE.search(x) for x in modifiers) if m), default=0)
    if max_level >= 5:
        return "Legendary"
    if max_level >= 4:
        return "Epic"
    if max_level >= 3:
        return "Rare"
    return "Normal"


# WB `Actor.hasEmotions`, which reads its biology's `has_emotions` meta tag — a single trait grants it, and without it a soul is never happy nor unhappy.
def has_emotions(actor: dict, subspecies_by_id: dict) -> bool:
    return _EMOTION_TRAIT in ((subspecies_by_id.get(actor.get("subspecies")) or {}).get("saved_traits") or [])


# The office-holder's own purse — a mayor's or a king's. Netted out of `subjects_money` on both tiers, and reported on its own in `metadata`.
def head_money(entity: dict, ctx: dict, tier: str) -> int:
    return int((ctx["actors_by_id"].get(entity.get(_HEAD_FIELD[tier])) or {}).get("money") or 0)


def index_by_id(records: list[dict]) -> dict:
    return {record["id"]: record for record in records}


# WB `Actor.isInsideSomething`, the half a save records: `transportID` names the boat a soul boarded, and `disembarkTo` clears it. Indoors, WB never writes.
def is_aboard(actor: dict) -> bool:
    return bool(actor.get("transportID"))


# WB models boats as actors: they sit in `actors_data` and even carry a `civ_kingdom_id`, so every actor tally must decide whether to skip them.
def is_boat(actor: dict) -> bool:
    return (actor.get("asset_id") or "").startswith("boat_")


# `{name: {kingdom id: value}}` — size, might, wealth, prestige, reach. Exported: `kingdom/info.py` surfaces the ones nothing else covers.
def kingdom_score_dimensions(save: dict) -> dict[str, dict]:
    kingdoms = save.get("kingdoms") or []
    ids = [k["id"] for k in kingdoms]
    money: Counter = Counter()  # the per-member tallies the dimensions need, gathered in one pass rather than by re-walking per-kingdom actor lists
    population: Counter = Counter()
    warriors_by_city: Counter = Counter()  # per city, because a kingdom's warriors are reached through its cities — see `warriors` below

    for actor in save.get("actors_data") or []:
        if is_boat(actor):
            continue
        if kid := actor.get("civ_kingdom_id"):
            population[kid] += 1
            if coins := actor.get("money"):  # a third of the world carries none — see `city_score_dimensions`
                money[kid] += coins
        if (cid := actor.get("cityID")) and actor.get("profession") == PROFESSION_WARRIOR:
            warriors_by_city[cid] += 1

    cities = save.get("cities") or []
    cities_by_id = index_by_id(cities)

    equipment: Counter = Counter()  # a crown racks nothing itself: its armoury is the sum of its towns'
    territory: Counter = Counter()
    warriors: Counter = Counter()  # WB `Kingdom.countTotalWarriors` sums its cities, so a fighter between two homes counts for nobody

    for city in cities:
        if (kid := city.get("kingdomID")) is not None:
            equipment[kid] += sum(len((city.get("equipment") or {}).get(f) or []) for f in EQUIPMENT_RACKS.values())
            territory[kid] += len(city.get("zones") or [])
            warriors[kid] += warriors_by_city[city["id"]]

    gold: Counter = Counter()  # gold ore stockpiled in a kingdom's buildings; each building carries its `cityID`, so no spatial lookup

    for building in save.get("buildings") or []:  # `resources` first: by far the rarest of the three tests, so it spares the city lookup on nearly every building
        if (stock := building.get("resources")) and (city := cities_by_id.get(building.get("cityID"))) and (kid := city.get("kingdomID")):
            for resource in stock.get("saved_resources") or []:
                if resource.get("id") == "gold":
                    gold[kid] += resource.get("amount", 0)

    wars_won: Counter = Counter()

    for war in save.get("wars") or []:
        if (winner := war.get("winner")) == 1:
            wars_won[war.get("main_attacker")] += 1
        elif winner == 2:
            wars_won[war.get("main_defender")] += 1

    kingdom_of_city = {c["id"]: c.get("kingdomID") for c in cities}  # a crown shelves nothing itself: a book reaches it through the town that holds it
    traits = {coll: {x["id"]: len(x.get("saved_traits") or []) for x in save.get(coll) or []} for coll in ("cultures", "languages", "religions")}
    return {
        "book_reach": _book_reach(save, "author_kingdom_id", set(ids), kingdom_of_city.get),
        "culture_traits": {
            k["id"]: traits["cultures"].get(k.get("id_culture"), 0)
            + traits["languages"].get(k.get("id_language"), 0)
            + traits["religions"].get(k.get("id_religion"), 0)
            for k in kingdoms
        },
        "equipment": equipment,  # its towns' racks summed — see the city dimension: a martial capital none of the other nine sees
        "foundings": Counter(item.get("creator_kingdom_id") for coll in ("cultures", "languages", "religions") for item in save.get(coll) or []),
        "kills": {k["id"]: k.get("total_kills", 0) for k in kingdoms},
        "population": population,
        "renown": {k["id"]: k.get("renown", 0) for k in kingdoms},
        "territory": territory,
        "warriors": warriors,
        "wars_won": wars_won,
        "wealth": {kid: gold[kid] + money[kid] for kid in ids},
    }


# Composite « kingdom power » ranking → `{kingdom id: place}` (1 = strongest, id-tiebroken). Drives the tag medal.
def kingdom_score_ranks(save: dict, dimensions: dict | None = None) -> dict[int, int]:
    return _score_ranks([k["id"] for k in save.get("kingdoms") or []], dimensions if dimensions is not None else kingdom_score_dimensions(save))


# The last chapter standing, 0 where none does yet. Three callers glob these dirs, and a chapter is `C<n>` on disk and nowhere else.
def latest_chapter() -> int:
    return max((int(p.name[1:]) for p in SAVES_DIR.glob("C*") if p.is_dir() and p.name[1:].isdigit()), default=0)


# Narrative age tier for kingdom demographics: baby/child/teen from `age_adult` (÷8, ÷2, ·1); `elder` = WB `isPrettyOld` (age/lifespan > 0.7).
def life_stage(age: int, age_adult: float, lifespan: float) -> str:
    if age < age_adult / 8:
        return "baby"
    if age < age_adult / 2:
        return "child"
    if age < age_adult:
        return "teen"
    if lifespan and age > lifespan * _ELDER_AGE_RATIO:
        return "elder"
    return "adult"


# Stamps a summarised section with its own way out, so no doc has to list which ones shrink under `full` — an empty payload stays bare, hiding nothing.
def light(payload: dict) -> dict:
    if not any(payload.values()):
        return payload
    return {**payload, "info": "call this section for the full detail"}


# The file itself, for the two scripts that must have it: one archives it into the chapter, the other writes the favorite's flag into it.
def live_save() -> Path:
    if (live := _current_save()) is None:
        raise SystemExit("✗ no WorldBox save on record — ask the player to point the reader at it, from the settings cog under the map")
    return live


# A `datas/` table, parsed once per run. A missing file reads as empty rather than raising — a tier whose library WB never shipped still answers, trait-less.
@cache
def load_data(name: str) -> dict:
    path = _DATAS_DIR / name
    return json.loads(path.read_text()) if path.exists() else {}


# Path required on purpose — a default would silently read the live save. Disk-cached on `mtime+size`: unpickling runs some 3× faster than parsing the JSON.
def load_save(path: Path) -> dict:
    if not path.exists():
        print(f"✗ no save found at {path}", file=sys.stderr)
        sys.exit(2)
    cache_file = CACHE_DIR / _save_cache_name(path)
    if cache_file.exists():
        try:
            with cache_file.open("rb") as f:
                return pickle.load(f)
        except Exception:  # noqa: BLE001 — corrupt cache, fall through and reparse.
            cache_file.unlink(missing_ok=True)
    with path.open("rb") as f:
        save = json.loads(zlib.decompress(f.read()))
    _write_save_cache(cache_file, save)
    return save


# WB `City.getMainSubspecies` / `Kingdom.getMainSubspecies` — the office-holder's biology, or its first member's while the seat is empty; `None` with neither.
def main_subspecies(entity: dict, ctx: dict, tier: str) -> int | None:
    head = ctx["actors_by_id"].get(entity.get(_HEAD_FIELD[tier]))
    if head:
        return head.get("subspecies")
    members = ctx[f"actors_by_{tier}"].get(entity["id"]) or []
    return members[0].get("subspecies") if members else None


# WB `MetaTextReportHelper.getText`: what a body says of itself — every verdict of its own list that holds, joined in that order. `None` where none does, as in game.
def meta_report(kind: str, state: dict) -> str | None:
    import random  # deferred: a millisecond or two of import for one `choice`, which every tool would pay at startup where only a few tiers ever report

    phrases = load_data("meta-reports.json")  # one of five phrasings per verdict, drawn as WB draws it — the wording never reaches a chapter, so it need not settle
    said = [random.choice(wordings) for report in _META_REPORTS[kind] if _META_CONDITIONS[report](state) and (wordings := phrases.get(report))]
    return " ".join(said) or None


# Parses a comma-separated section list — `None` and `full` both expand to all known sections, unless the caller has no `full` to offer (`geography`).
def parse_sections(arg: str | None, all_sections: tuple[str, ...], allow_full: bool = True) -> tuple[str, ...]:
    if allow_full and (not arg or arg == "full"):
        return all_sections
    requested = tuple(s.strip() for s in (arg or "").split(",") if s.strip())
    if unknown := [s for s in requested if s not in all_sections]:
        raise ValueError(f"✗ unknown section(s): {','.join(unknown)} — valid: {','.join((*(('full',) if allow_full else ()), *all_sections))}")
    return requested


# Top-3 shares per dimension over civ `actors` (% of the group); `species` also carries its `asset_id`. Needs the five `*_by_id` indexes in `ctx`.
def population_breakdown(actors: list[dict], ctx: dict) -> dict:
    species, cultures, kingdoms, languages, religions, subspecies = Counter(), Counter(), Counter(), Counter(), Counter(), Counter()

    # Hoisted out of the loop below: written inline, this literal would rebuild five tuples for every actor.
    optional = ((cultures, "culture"), (kingdoms, "civ_kingdom_id"), (languages, "language"), (religions, "religion"), (subspecies, "subspecies"))
    for a in actors:
        species[a.get("asset_id")] += 1
        for counter, field in optional:
            if (v := a.get(field)) is not None:
                counter[v] += 1
    pop = len(actors)

    # The id rides along on every dimension here: each has a tag to resolve and a script to query. The species has neither, and builds its own rows below.
    def top3(counter: Counter, names: dict) -> list[dict]:
        return [{"id": k, "name": (names.get(k) or {}).get("name"), "pct": pct} for k, n in counter.most_common(3) if pop and (pct := round(n / pop * 100)) > 0]

    return {
        "cultures": top3(cultures, ctx["cultures_by_id"]),
        "kingdoms": top3(kingdoms, ctx["kingdoms_by_id"]),
        "languages": top3(languages, ctx["languages_by_id"]),
        "religions": top3(religions, ctx["religions_by_id"]),
        "species": [  # the `asset_id` alone, which the UI translates; the others carry a world-generated name no table could hold.
            {"asset_id": k, "pct": pct} for k, n in species.most_common(3) if pop and (pct := round(n / pop * 100)) > 0
        ],
        "subspecies": top3(subspecies, ctx["subspecies_by_id"]),
    }


# `json.dumps(indent=2)` that inlines whatever fits `_INLINE_WIDTH`. `used` = what the caller already spent (key + comma), so the test measures the real line.
def render(value, indent: int = 0, used: int = 0, key: str | None = None) -> str:
    if not isinstance(value, (dict, list)) or not value:
        if type(value) is int:  # a third of a roster's leaves, and `json.dumps` walks its whole encoder to print one — `bool` has a type of its own, so it misses
            return str(value)
        # A ratio that lands whole prints whole: `5.0` is noise the chronicler would have to read past, and no consumer distinguishes it from `5`.
        return json.dumps(int(value) if isinstance(value, float) and value.is_integer() else value, ensure_ascii=False)
    if isinstance(value, dict):
        parts = []
        record = all(isinstance(k, str) and k.isidentifier() for k in value)  # Records sort; late keys move nothing. Data-keyed maps and `_VALUE_ORDERED` apart.
        numbered = all(isinstance(k, str) and k.lstrip("-").isdigit() for k in value)  # ids as keys sort on their value: `2` belongs before `10`, not after `1`
        items = sorted(value.items(), key=lambda kv: int(kv[0])) if numbered else sorted(value.items()) if record and key not in _VALUE_ORDERED else value.items()
        for k, v in items:
            dumped = f'"{k}"' if record else json.dumps(k, ensure_ascii=False)  # `record` proved every key an identifier; the rest keep their accents
            parts.append(f"{dumped}: {render(v, indent + 1, len(dumped) + 3, k)}")
        one, ends = "{ " + ", ".join(parts) + " }", "{}"
    else:
        parts = [render(v, indent + 1, 1) for v in value]
        one, ends = "[" + ", ".join(parts) + "]", "[]"
    # A child that had to expand leaves a newline in `one` — that rules the parent out of the single-line form. Most nodes fit, hence the late split.
    if "\n" not in one and indent * 2 + used + len(one) <= _INLINE_WIDTH:
        return one
    pad = "  " * indent
    # A list of numbers too long to inline packs across filled lines — an id roster reads as a block, where one value per row spends more padding than data.
    if isinstance(value, list) and all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in value):
        rows = [""]
        for piece in [f"{p}," for p in parts[:-1]] + parts[-1:]:
            if rows[-1] and len(pad) + len(rows[-1]) + len(piece) + 3 > _INLINE_WIDTH:
                rows.append(piece)
            else:
                rows[-1] = f"{rows[-1]} {piece}".lstrip()
        return "[\n" + "\n".join(f"{pad}  {r}" for r in rows) + f"\n{pad}]"
    return f"{ends[0]}\n" + ",\n".join(f"{pad}  {p}" for p in parts) + f"\n{pad}{ends[1]}"


# `army_captain` isn't a `profession` int — a warrior (5) leading an army. The roll is memoised: every roster asks this per soul, and rescanning would be O(n×m).
def resolve_profession(actor: dict, save: dict) -> str | None:
    if _captains_memo[0] is not save:
        _captains_memo[0], _captains_memo[1] = save, {c for army in save.get("armies") or [] if (c := army.get("id_captain"))}
    if actor.get("id") in _captains_memo[1]:
        return "army_captain"
    profession = actor.get("profession") or 0  # `0`/absent is WB's `nothing` — no profession, not an unknown one; anything else off the map surfaces as `#<int>`.
    return _PROFESSIONS.get(profession) or (f"#{profession}" if profession else None)


# A save's cache slot, keyed on `mtime+size`: a chapter's `map.wbox` never moves, so its slot holds for the world's life. `None` where the file is gone.
def save_cache_key(path: Path) -> str | None:
    try:
        stat = path.stat()
    except OSError:
        return None
    return f"{int(stat.st_mtime)}_{stat.st_size}"


# Who stands out among a body's own — its leading lineages and its most singular souls, `{id, name}` apiece. Shared by every tier that rosters people.
def settlement_leaders(actors: Sequence[dict], families_by_id: dict, children: Mapping[int, int], stat_of) -> dict:
    if len(actors) < _MIN_LEADERS_UNITS:
        return {}
    return {"families": _family_leaders(actors, families_by_id), "persons": _person_leaders(actors, children, stat_of)}


# The rank getters both `ranks` sections share — `tier` picks the ctx tallies (`*_by_city` / `*_by_kingdom`); kingdom stacks its extras on top.
def settlement_rank_getters(ctx: dict, tier: str) -> dict:
    def tally(name: str):
        counter = ctx[f"{name}_by_{tier}"]
        return lambda r: counter.get(r.get("id"), 0)

    eaters, fed, food, gold = tally("eaters"), tally("fed"), tally("food"), tally("gold")
    homeless, money, populations = tally("homeless"), tally("money"), tally("populations")
    nobles_money = tally("nobles_money")

    def wealth(r: dict) -> int:
        return money(r) + gold(r)

    return {
        "age": lambda r: entity_age(r, ctx["world_time"]),
        "buildings": tally("buildings"),
        "deaths": lambda r: r.get("total_deaths", 0),
        "fed_pct": lambda r: fed(r) / n if (n := eaters(r)) else 0.0,
        "food": food,
        "food_per_capita": lambda r: food(r) / n if (n := populations(r)) else 0.0,
        "gold": gold,
        "goods": tally("goods"),
        "housed_pct": lambda r: (n - homeless(r)) / n if (n := populations(r)) else 0.0,
        "houses": tally("houses"),
        "immortals": tally("immortals"),
        "infected": tally("infected"),
        "kills": lambda r: r.get("total_kills", 0),
        # Per-head, so a small town can out-rank a capital — floored at `MIN_PER_CAPITA_UNITS`, under which the divisor speaks louder than the body.
        "kills_per_capita": lambda r: r.get("total_kills", 0) / n if (n := populations(r)) >= MIN_PER_CAPITA_UNITS else 0.0,
        "money": money,
        "nobles": tally("nobles"),
        "nobles_money": nobles_money,  # the head's own purse excluded — it is reported on its own in `metadata`
        "population": populations,
        "renown": lambda r: r.get("renown", 0),
        "renown_per_capita": lambda r: r.get("renown", 0) / n if (n := populations(r)) >= MIN_PER_CAPITA_UNITS else 0.0,
        "renown_total": tally("renown"),
        "sick": tally("sick"),
        "subjects_money": lambda r: money(r) - head_money(r, ctx, tier) - nobles_money(r),  # commoners' coins: `money` minus the head and the nobility
        "territory": lambda r: len(r.get("zones") or []),
        "warriors": tally("warriors"),
        "wealth": wealth,
        "wealth_per_capita": lambda r: wealth(r) / n if (n := populations(r)) else 0.0,
    }


# WB omits default values at save time: an absent `sex` IS male (0) — every species has sexed members, living swords included.
def sex_label(actor: dict) -> str:
    return "female" if actor.get("sex") == 1 else "male"


# WB `ListSorters.sortUnitsSortedByAgeAndTraits`: age, then a trait re-sorts on renown/stat/coins, then sex — sorted last, so it wins. Callers pick the pool.
def succession_heir(candidates: Sequence[dict], traits: set[str], world_time: float, stat_of) -> dict | None:
    if not candidates:
        return None
    stat = next((s for t, s in _ASCENSION_STATS.items() if t in traits), None)

    def score(actor: dict) -> float:
        if stat is not None:
            return stat_of(actor).get(stat, 0)
        if "fames_crown" in traits:  # WB tests renown before coins, so a culture holding both crowns the famous, not the rich
            return int(actor.get("renown") or 0)
        if "golden_rule" in traits:
            return int(actor.get("money") or 0)
        age = world_time - float(actor.get("created_time") or 0)
        return -age if "ultimogeniture" in traits else age  # `ultimogeniture` = youngest inherits, else eldest

    def preferred_sex(actor: dict) -> int:
        if "patriarchy" in traits:
            return 0 if actor.get("sex") == 1 else 1
        if "matriarchy" in traits:
            return 1 if actor.get("sex") == 1 else 0
        return 0

    # Twins share a `created_time` to the digit, so ties fall to the pool's order — `max` keeps the first, like WB's stable sort; callers must pass it save-ordered.
    return max(candidates, key=lambda a: (preferred_sex(a), score(a)))


# Pop a `C<n>` token from argv → (that chapter's `map.wbox`, argv without it, its label). No token → the chapter standing, whose copy cannot move under a player.
def take_chapter(argv: list[str]) -> tuple[Path, list[str], str | None]:
    for i, arg in enumerate(argv):
        if len(arg) > 1 and arg[0] == "C" and arg[1:].isdigit():
            return SAVES_DIR / arg / "map.wbox", argv[:i] + argv[i + 1 :], arg
    if n := latest_chapter():
        return SAVES_DIR / f"C{n}" / "map.wbox", argv, f"C{n}"
    # No chapter yet — the baptism's world tour, no archive yet to be stale against. Said out loud, but in hand: no save on record must answer that alone.
    live = live_save()
    print("⚠ no chapter yet — reading the live save itself, which moves under a player still at play", file=sys.stderr)
    return live, argv, None


# Spelled out because the section was named, or too small for a summary to earn the call it forces — only where that summary is a pure signpost, never traits.
def wants_detail(requested: str | None, count: int) -> bool:
    return requested not in (None, "full") or count < _MIN_SUMMARY_ENTRIES


def worldbox_running() -> bool:
    return subprocess.run(["pgrep", "-i", "worldbox"], capture_output=True, check=False).returncode == 0


# Written aside then swapped in: a crash mid-write leaves the old save whole rather than half a new one. Both scripts that touch the live file go through here.
def write_save(wbox: Path, save: dict) -> None:
    staged = wbox.with_suffix(".wbox.tmp")
    staged.write_bytes(zlib.compress(json.dumps(save, separators=(",", ":"), ensure_ascii=False).encode(), _COMPRESSION))
    staged.replace(wbox)
