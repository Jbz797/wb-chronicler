#!/usr/bin/env python3

# Shared constants/helpers reused by `actor/info.py`, `kingdom/info.py` and `world/info.py` — `sys.path`-injected from parent dir; see each bootstrap.

import json
import os
import sys
import zlib
from functools import cache
from pathlib import Path


# Live game save by default; `WB_SAVE` env var overrides it to regenerate a past chapter from its archived `map.wbox`.
CURRENT_SAVE = Path(os.environ.get("WB_SAVE") or Path.home() / "Library/Application Support/mkarpenko/WorldBox/saves/save1/map.wbox")

SICK_TRAITS = frozenset({"infected", "mush_spores", "plague", "tumor_infection"})  # WB `calculateIsSick` traits — `infected` ⊂ `sick`.

UNITS_PER_YEAR = 60  # 60 `world_time` units = 1 year (12 months × 5 units).

_DATAS_DIR = Path(__file__).parent / "datas"
_ELDER_AGE_RATIO = 0.7  # WB `Actor.isPrettyOld`: an actor is « old » once age / lifespan exceeds this.
_PROFESSIONS = {2: "unit", 3: "king", 4: "leader", 5: "warrior"}  # WB `profession` int → label.


# Drop `None`, `[]` and `{}` from a nested JSON-like structure — chronicler tokens optimisation. `0`/`""`/`False` are preserved (semantically meaningful values).
def _strip_none(value):
    if isinstance(value, dict):
        return {k: stripped for k, v in value.items() if (stripped := _strip_none(v)) not in (None, [], {})}
    if isinstance(value, list):
        return [stripped for v in value if (stripped := _strip_none(v)) not in (None, [], {})]
    return value


# Serialize a registry to disk: one line per entry, sorted by numeric id, fields alphabetical — single-line diffs.
def _write_registry(path: Path, registry: dict) -> None:
    rows = []
    for entry_key, entry_value in sorted(registry.items(), key=lambda item: int(item[0])):
        fields = ", ".join(f"{json.dumps(k)}: {json.dumps(v, ensure_ascii=False)}" for k, v in sorted(entry_value.items()))
        rows.append(f"  {json.dumps(entry_key)}: {{ {fields} }}")
    path.write_text("{\n" + ",\n".join(rows) + "\n}\n")


# WB `Subspecies.calculateAgeRelatedStats`: lifespan > 30 → (16, 18); else `Pow(lifespan, 0.55)×1.1` capped 16/18 (civ species always > 30).
def age_thresholds(lifespan: float) -> tuple[float, float]:
    if lifespan > 30:
        return 16.0, 18.0
    adult = min((lifespan**0.55) * 1.1, 16.0)
    return adult, min(adult, 18.0)


# Asset ids of built structures (ResourceManager path `buildings/civ_*`) — excludes nature. Source: `datas/building-categories.json`.
def civic_building_ids() -> frozenset[str]:
    return frozenset(asset for asset, category in load_data("building-categories.json").items() if category.startswith("civ_"))


def emit(out: dict) -> None:
    print(json.dumps(_strip_none(out), ensure_ascii=False, indent=2))


def index_by_id(records: list[dict], key: str = "id") -> dict:
    return {record[key]: record for record in records}


# Narrative age tier (exact tally source for kingdom demographics): baby/child/teen scale with `age_adult` (÷8, ÷2, ·1); `elder` = WB `isPrettyOld` (age/lifespan > 0.7).
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


def load_save() -> dict:
    if not CURRENT_SAVE.exists():
        print(f"no save found at {CURRENT_SAVE}", file=sys.stderr)
        sys.exit(2)
    with CURRENT_SAVE.open("rb") as f:
        return json.loads(zlib.decompress(f.read()))


# Parses a comma-separated section list — `None` expands to all known sections; `full` is an alias for "all" iff the caller opts in.
def parse_sections(arg: str | None, all_sections: tuple[str, ...], accept_full: bool = True) -> tuple[str, ...]:
    if not arg or (accept_full and arg == "full"):
        return all_sections
    requested = tuple(s.strip() for s in arg.split(",") if s.strip())
    if unknown := [s for s in requested if s not in all_sections]:
        valid = ("full", *all_sections) if accept_full else all_sections
        raise ValueError(f"unknown section(s): {','.join(unknown)} — valid: {','.join(valid)}")
    return requested


# Global registry: flip « dead » for `dead`-keyed persons absent from the save. Re-swept each run (resurrections clear it); keyless demo entries ignored.
def reconcile_deaths(path: Path, alive_ids: set[int]) -> None:
    if not path.exists():
        return
    registry = json.loads(path.read_text())
    changed = False
    for pid, entry in registry.items():
        if "dead" in entry and (dead := int(pid) not in alive_ids) != entry["dead"]:
            entry["dead"] = dead
            changed = True
    if changed:
        _write_registry(path, registry)


# Upsert an entry into a JSON registry keyed by numeric id; write only on value change.
def register_entity(path: Path, key: str, value: dict) -> None:
    registry = json.loads(path.read_text()) if path.exists() else {}
    if registry.get(key) == value:
        return
    registry[key] = value
    _write_registry(path, registry)


# `army_captain` isn't a `profession` int — it's a warrior (5) leading an army, so it overrides the base label when this actor captains one.
def resolve_profession(actor: dict, save: dict) -> str | None:
    if any(army.get("id_captain") == actor.get("id") for army in save.get("armies", [])):
        return "army_captain"
    return _PROFESSIONS.get(actor.get("profession") or 0)
