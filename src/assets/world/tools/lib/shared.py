# Cross-domain constants + helpers — one of the `tools/lib/` libraries every entry point puts on its `sys.path` (see each bootstrap).
# Rule: a symbol lives here only if ≥2 scripts need it — either directly, or through another exported symbol that does. Single-script helpers live in that script.

import json
import os
import pickle
import re
import sys
import zlib
from bisect import bisect_right
from collections import Counter
from collections.abc import Sequence
from functools import cache
from pathlib import Path

ASCENSION_STATS = {"diplomatic_ascension": "diplomacy", "warriors_ascension": "warfare"}  # Culture succession by that stat (else renown, coins, age).
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

HAPPY_MIN_HAPPINESS = 20  # WB `Actor.isHappy`: `getHappinessRatio ≥ 0.6` ⟺ raw happiness ≥ 20. (Emotionless non-civ actors also count — ignored.)
NON_FOOD_SPECIES = frozenset({"skeleton"})  # WB `needsFood`=false (undead have no diet ⇒ never hungry); excluded from `fed_pct`.
PROFESSION_KING = 3  # WB `profession` ints — see `_PROFESSIONS` for the full map.
PROFESSION_LEADER = 4
PROFESSION_WARRIOR = 5
SATED_MIN_NUTRITION = 60  # `fed_pct` threshold: nutrition ratio ≥ 0.6 (like `tier-high`) — stricter than WB's own `isHungry` (≤ 50).
SAVES_DIR = Path(__file__).parents[2] / "saves"  # Single source of truth for the chapter dirs `C<n>/`; `chapter/` reaches back to `C<n-1>` through it.
SICK_TRAITS = frozenset({"infected", "mush_spores", "plague", "tumor_infection"})  # WB `calculateIsSick` traits — `infected` ⊂ `sick`.
UNITS_PER_YEAR = 60  # 60 `world_time` units = 1 year (12 months × 5 units).
ZONE_TILES = 8  # WB `TileZone` side (tiles): `zones` are in zone units — divide tile coords by this; centre = `z*ZONE_TILES + ZONE_TILES//2`.

_CACHE_KEEP = 12  # roughly a world's worth of chapters plus the live save — old entries fall off by mtime rather than piling up

# Live game save by default; a trailing `C<n>` script arg (via `take_chapter`) overrides it to a chapter's archived `map.wbox`. `WB_SAVE` still forces a path.
_CURRENT_SAVE = Path(os.environ.get("WB_SAVE") or Path.home() / "Library/Application Support/mkarpenko/WorldBox/saves/save1/map.wbox")

_DATAS_DIR = Path(__file__).parent.parent / "datas"
_ELDER_AGE_RATIO = 0.7  # WB `Actor.isPrettyOld`: an actor is « old » once age / lifespan exceeds this.
_EMPTY_VALUES = (None, [], {})  # module-level so `_strip_none` doesn't rebuild a list and a dict at every node it tests.
_INLINE_WIDTH = 165  # `emit` collapses a dict/list onto one line when it fits this width, else expands — compact yet readable, fewer tokens.
_LEVEL_RE = re.compile(r"(\d+)$")  # trailing enchant tier on a modifier id (`power5`) — `re` rides in free, `pathlib` already pulls it.
_PROFESSIONS = {2: "unit", 3: "king", 4: "leader", 5: "warrior"}  # WB `profession` int → label.


# Item base stats + its modifiers' bonuses, floats trimmed to 4 decimals (ints when whole), zeros dropped.
def _equipment_stats(asset_id: str, modifiers: list[str], item_stats: dict, mod_stats: dict) -> dict:
    out = dict(item_stats.get(asset_id, {}))
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


# Newest `_CACHE_KEEP` entries kept, the rest dropped by mtime — chapter saves each want their own, unlike the islands cache's single slot.
def _write_save_cache(cache_file: Path, save: dict) -> None:
    CACHE_DIR.mkdir(exist_ok=True)
    with cache_file.open("wb") as f:
        pickle.dump(save, f, protocol=5)
    stale = sorted(CACHE_DIR.glob("save_v1_*.pkl"), key=lambda f: f.stat().st_mtime, reverse=True)[_CACHE_KEEP:]
    for old_entry in stale:
        old_entry.unlink(missing_ok=True)


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


# Ten dimensions, `{name: {city id: value}}` — six transposed from the kingdom, four village-only. Exported: `city/info.py` surfaces two it has no other source for.
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
        if stock := building.get("resources"):  # barely 0.5 % of buildings hold one, so gating the walk beats spending an `or {}` on every wall and tree
            for resource in stock.get("saved_resources") or []:
                if resource.get("id") == "gold":
                    gold[cid] += resource.get("amount", 0)
    book_reach: Counter = Counter()  # 10 per authored book + how widely it's read, as the kingdom score counts it

    for book in save.get("books") or []:
        if (cid := book.get("author_city_id")) is not None:
            book_reach[cid] += 10 + (book.get("times_read") or 0)

    return {
        # Net settlers won over: `joined` had no city, `moved` came from another, `left` walked out. `migrated` is out — a world law spawns those outright.
        "attractivity": {c["id"]: c.get("joined", 0) + c.get("moved", 0) - c.get("left", 0) for c in cities},
        "book_reach": book_reach,
        "buildings": buildings,
        "elite": elite,  # the renown of its inhabitants — who lives there, where `renown` below is what the city itself achieved
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


# Asset ids of built structures (ResourceManager path `buildings/civ_*`) — excludes nature. Source: `datas/building-categories.json`.
@cache
def civic_building_ids() -> frozenset[str]:
    return frozenset(asset for asset, category in load_data("building-categories.json").items() if category.startswith("civ_"))


# Standard competition rank (1,2,2,4) among `peers` per getter — top 3 only. `skip_zero` drops metrics the entity has none of (no meaningless podium at 0).
def competition_ranks(entity, peers: list, getters: dict, skip_zero: bool = True) -> dict:
    ranks = {}
    for stat, getter in sorted(getters.items()):
        own = getter(entity)
        if skip_zero and own == 0:
            continue
        rank = sum(1 for p in peers if getter(p) > own) + 1
        if rank <= 3:
            ranks[stat] = rank
    return ranks


def emit(out: dict) -> None:
    print(render(_strip_none(out)))


# `{id, name}` ref or `None` — the name feeds the narration, the id a follow-up script query. One shape for every kingdom/city/alliance ref across the outputs.
def entity_ref(entity_id: int | None, by_id: dict) -> dict | None:
    entity = by_id.get(entity_id) if entity_id is not None else None
    return None if entity is None else {"id": entity_id, "name": entity.get("name") or f"#{entity_id}"}


# One equipped-or-racked item as both tiers report it: provenance (`by`/`from`), wear, kills, and its stats already folded with the modifiers' bonuses.
def equipment_entry(item: dict, item_stats: dict, mod_stats: dict, world_time: float) -> dict:
    mods = sorted(item.get("modifiers") or [])
    created = item.get("created_time")
    return {
        "age": int((world_time - created) / UNITS_PER_YEAR) if created is not None else None,
        "asset_id": item["asset_id"],
        "by": item.get("by"),
        "durability": item.get("durability"),
        "from": item.get("from"),
        "id": item["id"],
        "kills": item.get("kills", 0),
        "modifiers": mods,
        "name": item.get("name"),
        "rarity": equipment_rarity(mods),
        "stats": _equipment_stats(item["asset_id"], mods, item_stats, mod_stats),
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


def index_by_id(records: list[dict]) -> dict:
    return {record["id"]: record for record in records}


# WB models boats as actors: they sit in `actors_data` and even carry a `civ_kingdom_id`, so every actor tally must decide whether to skip them.
def is_boat(actor: dict) -> bool:
    return (actor.get("asset_id") or "").startswith("boat_")


# Ten dimensions, `{name: {kingdom id: value}}` — size, might, wealth, prestige, reach. Exported: `kingdom/info.py` surfaces four it has no other source for.
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
            if coins := actor.get("money"):  # a quarter of the world carries none — see `city_score_dimensions`
                money[kid] += coins
        if (cid := actor.get("cityID")) and actor.get("profession") == PROFESSION_WARRIOR:
            warriors_by_city[cid] += 1
    cities = save.get("cities") or []
    cities_by_id = index_by_id(cities)
    territory: Counter = Counter()
    warriors: Counter = Counter()  # WB `Kingdom.countTotalWarriors` sums its cities, so a fighter between two homes counts for nobody

    for city in cities:
        if (kid := city.get("kingdomID")) is not None:
            territory[kid] += len(city.get("zones") or [])
            warriors[kid] += warriors_by_city[city["id"]]
    gold: Counter = Counter()  # gold ore stockpiled in a kingdom's buildings; each building carries its `cityID`, so no spatial lookup

    for building in save.get("buildings") or []:  # `resources` first: by far the rarest of the three tests, so it spares the city lookup on 99 % of the walk
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
    book_reach: Counter = Counter()  # 10 per authored book + how widely it's read

    for book in save.get("books") or []:
        if (kid := book.get("author_kingdom_id")) is not None:
            book_reach[kid] += 10 + (book.get("times_read") or 0)

    traits = {coll: {x["id"]: len(x.get("saved_traits") or []) for x in save.get(coll) or []} for coll in ("cultures", "languages", "religions")}
    return {
        "book_reach": book_reach,
        "culture_traits": {
            k["id"]: traits["cultures"].get(k.get("id_culture"), 0)
            + traits["languages"].get(k.get("id_language"), 0)
            + traits["religions"].get(k.get("id_religion"), 0)
            for k in kingdoms
        },
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


@cache
def load_data(name: str) -> dict:
    path = _DATAS_DIR / name
    return json.loads(path.read_text()) if path.exists() else {}


# Path required on purpose — a default would silently read the live save. Disk-cached on `mtime+size`: 49 ms of JSON parsing against 16 to unpickle.
def load_save(path: Path) -> dict:
    if not path.exists():
        print(f"no save found at {path}", file=sys.stderr)
        sys.exit(2)
    stat = path.stat()
    cache_file = CACHE_DIR / f"save_v1_{int(stat.st_mtime)}_{stat.st_size}.pkl"
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


# Parses a comma-separated section list — `None` and `full` both expand to all known sections.
def parse_sections(arg: str | None, all_sections: tuple[str, ...]) -> tuple[str, ...]:
    if not arg or arg == "full":
        return all_sections
    requested = tuple(s.strip() for s in arg.split(",") if s.strip())
    if unknown := [s for s in requested if s not in all_sections]:
        raise ValueError(f"unknown section(s): {','.join(unknown)} — valid: {','.join(('full', *all_sections))}")
    return requested


# Top-3 shares per dimension over civ `actors` (% of the group); `species` also carries its `asset_id`. Needs the four `*_by_id` indexes in `ctx`.
def population_breakdown(actors: list[dict], ctx: dict) -> dict:
    species, cultures, languages, religions, subspecies = Counter(), Counter(), Counter(), Counter(), Counter()
    # Hoisted out of the loop below: written inline, this literal would rebuild four tuples for every actor.
    optional = ((cultures, "culture"), (languages, "language"), (religions, "religion"), (subspecies, "subspecies"))
    for a in actors:
        species[a.get("asset_id")] += 1
        for counter, field in optional:
            if (v := a.get(field)) is not None:
                counter[v] += 1
    pop = len(actors)
    species_names = load_data("species.json")

    def top3(counter: Counter, names: dict) -> list[dict]:
        return [{"name": (names.get(k) or {}).get("name") or f"#{k}", "pct": pct} for k, n in counter.most_common(3) if pop and (pct := round(n / pop * 100)) > 0]

    return {
        "cultures": top3(cultures, ctx["cultures_by_id"]),
        "languages": top3(languages, ctx["languages_by_id"]),
        "religions": top3(religions, ctx["religions_by_id"]),
        "species": [  # `asset_id` (icon key) alongside the French `name`; the others need only their registry name.
            {"asset_id": k, "name": (species_names.get(k) or {}).get("name") or k, "pct": pct}
            for k, n in species.most_common(3)
            if pop and (pct := round(n / pop * 100)) > 0
        ],
        "subspecies": top3(subspecies, ctx["subspecies_by_id"]),
    }


# `json.dumps(indent=2)` that inlines whatever fits `_INLINE_WIDTH`. `used` = what the caller already spent (key + comma), so the test measures the real line.
def render(value, indent: int = 0, used: int = 0) -> str:
    if not isinstance(value, (dict, list)) or not value:
        # A ratio that lands whole prints whole: `5.0` is noise the chronicler would have to read past, and no consumer distinguishes it from `5`.
        return json.dumps(int(value) if isinstance(value, float) and value.is_integer() else value, ensure_ascii=False)
    if isinstance(value, dict):
        parts = []
        for k, v in value.items():
            key = json.dumps(k)  # dumped once and reused for the width it costs — the naive form dumps every key twice
            parts.append(f"{key}: {render(v, indent + 1, len(key) + 3)}")
        one, ends = "{ " + ", ".join(parts) + " }", "{}"
    else:
        parts = [render(v, indent + 1, 1) for v in value]
        one, ends = "[" + ", ".join(parts) + "]", "[]"
    pad = "  " * indent
    # A child that had to expand leaves a newline in `one` — that rules the parent out of the single-line form. Most nodes fit, hence the late split.
    if "\n" not in one and len(pad) + used + len(one) <= _INLINE_WIDTH:
        return one
    return f"{ends[0]}\n" + ",\n".join(f"{pad}  {p}" for p in parts) + f"\n{pad}{ends[1]}"


# `army_captain` isn't a `profession` int — a warrior (5) leading an army. Hot loops pass `captain_ids` to spare rescanning `armies`.
def resolve_profession(actor: dict, save: dict, captain_ids: set | None = None) -> str | None:
    cid = actor.get("id")
    captain = cid in captain_ids if captain_ids is not None else any(army.get("id_captain") == cid for army in save.get("armies", []))
    return "army_captain" if captain else _PROFESSIONS.get(actor.get("profession") or 0)


# The 20 rank getters both `ranks` sections share — `tier` picks the ctx tallies (`*_by_city` / `*_by_kingdom`); kingdom stacks its extras on top.
def settlement_rank_getters(ctx: dict, tier: str) -> dict:
    def tally(name: str):
        counter = ctx[f"{name}_by_{tier}"]
        return lambda r: counter.get(r.get("id"), 0)

    eaters, fed, food, gold = tally("eaters"), tally("fed"), tally("food"), tally("gold")
    homeless, money, populations = tally("homeless"), tally("money"), tally("populations")

    def wealth(r: dict) -> int:
        return money(r) + gold(r)

    return {
        "age": lambda r: int((ctx["world_time"] - float(r.get("created_time") or 0)) / UNITS_PER_YEAR),
        "buildings": tally("buildings"),
        "deaths": lambda r: r.get("total_deaths", 0),
        "fed_pct": lambda r: fed(r) / n if (n := eaters(r)) else 0.0,
        "food": food,
        "food_per_capita": lambda r: food(r) / n if (n := populations(r)) else 0.0,
        "gold": gold,
        "goods": tally("goods"),
        "housed_pct": lambda r: (n - homeless(r)) / n if (n := populations(r)) else 0.0,
        "houses": tally("houses"),
        "kills": lambda r: r.get("total_kills", 0),
        "money": money,
        "nobles": tally("nobles"),
        "population": populations,
        "renown": lambda r: r.get("renown", 0),
        "renown_total": tally("renown"),
        "territory": lambda r: len(r.get("zones") or []),
        "warriors": tally("warriors"),
        "wealth": wealth,
        "wealth_per_capita": lambda r: wealth(r) / n if (n := populations(r)) else 0.0,
    }


# WB `ListSorters.sortUnitsSortedByAgeAndTraits`: age, then a trait re-sorts on renown/stat/coins, then sex — sorted last, so it wins. Callers pick the pool.
def succession_heir(candidates: Sequence[dict], traits: set[str], world_time: float, stat_of) -> dict | None:
    if not candidates:
        return None
    stat = next((s for t, s in ASCENSION_STATS.items() if t in traits), None)

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

    return max(candidates, key=lambda a: (preferred_sex(a), score(a), -a.get("id", 0)))


# WB omits default values at save time: an absent `sex` IS male (0) — every species has sexed members, living swords included.
def sex_label(actor: dict) -> str:
    return "female" if actor.get("sex") == 1 else "male"


# Pop a `C<n>` chapter token from argv → (that chapter's `map.wbox`, argv without it, chapter label). No token → the live save and `None`.
def take_chapter(argv: list[str]) -> tuple[Path, list[str], str | None]:
    for i, arg in enumerate(argv):
        if len(arg) > 1 and arg[0] == "C" and arg[1:].isdigit():
            return SAVES_DIR / arg / "map.wbox", argv[:i] + argv[i + 1 :], arg
    return _CURRENT_SAVE, argv, None
