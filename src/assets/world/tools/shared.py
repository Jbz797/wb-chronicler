#!/usr/bin/env python3

# Shared constants/helpers reused by ≥2 of `actor/`, `city/`, `kingdom/`, `world/`, `geography/`, `tiles/` `info.py` — `sys.path`-injected from parent dir; see each bootstrap.
# Rule: an exported symbol must serve ≥2 scripts; single-script helpers live in that script.

import json
import os
import sys
import zlib
from collections import Counter
from functools import cache
from pathlib import Path


HAPPY_MIN_HAPPINESS = 20  # WB `Actor.isHappy`: `getHappinessRatio ≥ 0.6` ⟺ raw happiness ≥ 20. (Emotionless non-civ actors also count — ignored.)
NON_FOOD_SPECIES = frozenset({"skeleton"})  # WB `needsFood`=false (undead have no diet ⇒ never hungry); excluded from `fed_pct`.
PROFESSION_KING = 3  # WB `profession` ints — see `_PROFESSIONS` for the full map.
PROFESSION_LEADER = 4
PROFESSION_WARRIOR = 5
SATED_MIN_NUTRITION = 60  # `fed_pct` threshold: nutrition ratio ≥ 0.6 (like `tier-high`) — stricter than WB's own `isHungry` (≤ 50).
SAVES_DIR = Path(__file__).parent.parent / "saves"  # Single source of truth for the chapter dirs `C<n>/`; `world/info.py` needs it to reach back to `C<n-1>`.
SICK_TRAITS = frozenset({"infected", "mush_spores", "plague", "tumor_infection"})  # WB `calculateIsSick` traits — `infected` ⊂ `sick`.
UNITS_PER_YEAR = 60  # 60 `world_time` units = 1 year (12 months × 5 units).
ZONE_TILES = 8  # WB `TileZone` side in tiles: city `zones` are stored in zone units — tile coords divide by this, zone centres are `z * ZONE_TILES + ZONE_TILES // 2`.

# Live game save by default; a trailing `C<n>` script arg (via `take_chapter`) overrides it to a chapter's archived `map.wbox`. `WB_SAVE` still forces a path.
_CURRENT_SAVE = Path(os.environ.get("WB_SAVE") or Path.home() / "Library/Application Support/mkarpenko/WorldBox/saves/save1/map.wbox")
_DATAS_DIR = Path(__file__).parent / "datas"
_ELDER_AGE_RATIO = 0.7  # WB `Actor.isPrettyOld`: an actor is « old » once age / lifespan exceeds this.
_INLINE_WIDTH = 165  # `emit` collapses a dict/list onto one line when it fits this width, else expands — compact yet readable, fewer tokens.
_PROFESSIONS = {2: "unit", 3: "king", 4: "leader", 5: "warrior"}  # WB `profession` int → label.


# `json.dumps(indent=2)` with anything fitting `_INLINE_WIDTH` inlined. `used` = width the caller already spent (key + comma), so the fit test measures the real line.
def _render(value, indent: int = 0, used: int = 0) -> str:
    if not isinstance(value, (dict, list)) or not value:
        return json.dumps(value, ensure_ascii=False)
    pad = "  " * indent
    if isinstance(value, dict):
        parts = [f"{json.dumps(k)}: {_render(v, indent + 1, len(json.dumps(k)) + 3)}" for k, v in value.items()]
        one = "{ " + ", ".join(parts) + " }"
        multi = "{\n" + ",\n".join(f"{pad}  {p}" for p in parts) + "\n" + pad + "}"
    else:
        parts = [_render(v, indent + 1, 1) for v in value]
        one = "[" + ", ".join(parts) + "]"
        multi = "[\n" + ",\n".join(f"{pad}  {p}" for p in parts) + "\n" + pad + "]"
    # A child that had to expand leaves a newline in `one` — that rules the whole parent out of the single-line form.
    return one if "\n" not in one and len(pad) + used + len(one) <= _INLINE_WIDTH else multi


# Drop `None`, `[]` and `{}` from a nested JSON-like structure — chronicler tokens optimisation. `0`/`""`/`False` are preserved (semantically meaningful values).
def _strip_none(value):
    if isinstance(value, dict):
        return {k: stripped for k, v in value.items() if (stripped := _strip_none(v)) not in (None, [], {})}
    if isinstance(value, list):
        return [stripped for v in value if (stripped := _strip_none(v)) not in (None, [], {})]
    return value


# WB `Subspecies.calculateAgeRelatedStats`: lifespan > 30 → (16, 18); else `Pow(lifespan, 0.55)×1.1` capped 16/18 (civ species always > 30).
def age_thresholds(lifespan: float) -> tuple[float, float]:
    if lifespan > 30:
        return 16.0, 18.0
    adult = min((lifespan**0.55) * 1.1, 16.0)
    return adult, min(adult, 18.0)


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
    print(_render(_strip_none(out)))


# `{id, name}` ref or `None` — the name feeds the narration, the id a follow-up script query. One shape for every kingdom/city/alliance ref across the outputs.
def entity_ref(entity_id: int | None, by_id: dict) -> dict | None:
    entity = by_id.get(entity_id) if entity_id is not None else None
    return None if entity is None else {"id": entity_id, "name": entity.get("name") or f"#{entity_id}"}


# WB eatable resource ids (`initFood` + `initFoodRecipes`) — raw + cooked/drinks. Cached function, not a constant: `load_data` is defined below.
@cache
def food_resources() -> frozenset[str]:
    return frozenset(load_data("food-resources.json"))


def index_by_id(records: list[dict]) -> dict:
    return {record["id"]: record for record in records}


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


# Path is required on purpose: a default would silently read the live save when a chapter was meant — the bug class `take_chapter` exists to prevent.
def load_save(path: Path) -> dict:
    if not path.exists():
        print(f"no save found at {path}", file=sys.stderr)
        sys.exit(2)
    with path.open("rb") as f:
        return json.loads(zlib.decompress(f.read()))


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
    for a in actors:
        species[a.get("asset_id")] += 1
        for counter, field in ((cultures, "culture"), (languages, "language"), (religions, "religion"), (subspecies, "subspecies")):
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


# `army_captain` isn't a `profession` int — a warrior (5) leading an army. Hot loops pass `captain_ids` to spare rescanning `armies`.
def resolve_profession(actor: dict, save: dict, captain_ids: set | None = None) -> str | None:
    cid = actor.get("id")
    captain = cid in captain_ids if captain_ids is not None else any(army.get("id_captain") == cid for army in save.get("armies", []))
    return "army_captain" if captain else _PROFESSIONS.get(actor.get("profession") or 0)


# The 20 rank getters shared by the city and kingdom `ranks` sections — `tier` picks the ctx tallies (`*_by_city` / `*_by_kingdom`); kingdom stacks its extras on top.
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
        "fed_pct": lambda r: fed(r) / eaters(r) if eaters(r) else 0.0,
        "food": food,
        "food_per_capita": lambda r: food(r) / populations(r) if populations(r) else 0.0,
        "gold": gold,
        "goods": tally("goods"),
        "housed_pct": lambda r: (populations(r) - homeless(r)) / populations(r) if populations(r) else 0.0,
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
        "wealth_per_capita": lambda r: wealth(r) / populations(r) if populations(r) else 0.0,
    }


# WB omits default values at save time: an absent `sex` IS male (0) — every species has sexed members, living swords included.
def sex_label(actor: dict) -> str:
    return "female" if actor.get("sex") == 1 else "male"


# Pop a `C<n>` chapter token from argv → (that chapter's `map.wbox`, argv without it, chapter label). No token → the live save and `None`.
def take_chapter(argv: list[str]) -> tuple[Path, list[str], str | None]:
    for i, arg in enumerate(argv):
        if len(arg) > 1 and arg[0] == "C" and arg[1:].isdigit():
            return SAVES_DIR / arg / "map.wbox", argv[:i] + argv[i + 1 :], arg
    return _CURRENT_SAVE, argv, None
