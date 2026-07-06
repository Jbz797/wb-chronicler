#!/usr/bin/env python3

# Shared constants/helpers reused by `actor/info.py`, `kingdom/info.py` and `world/info.py` — `sys.path`-injected from parent dir; see each bootstrap.

import json
import sys
import zlib
from functools import cache
from pathlib import Path


CURRENT_SAVE = Path.home() / "Library/Application Support/mkarpenko/WorldBox/saves/save1/map.wbox"
ELDER_AGE_RATIO = 0.7  # WB `Actor.isPrettyOld`: an actor is « old » once age / lifespan exceeds this.
UNITS_PER_YEAR = 60  # 60 `world_time` units = 1 year (12 months × 5 units).

_DATAS_DIR = Path(__file__).parent / "datas"


# Drop `None`, `[]` and `{}` from a nested JSON-like structure — chronicler tokens optimisation. `0`/`""`/`False` are preserved (semantically meaningful values).
def _strip_none(value):
    if isinstance(value, dict):
        return {k: stripped for k, v in value.items() if (stripped := _strip_none(v)) not in (None, [], {})}
    if isinstance(value, list):
        return [stripped for v in value if (stripped := _strip_none(v)) not in (None, [], {})]
    return value


def emit(out: dict) -> None:
    print(json.dumps(_strip_none(out), ensure_ascii=False, indent=2))


def index_by_id(records: list[dict], key: str = "id") -> dict:
    return {record[key]: record for record in records}


# Loads (and caches) a JSON file from the datas dir — `{}` if it doesn't exist.
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


# Upsert an entry into a JSON registry keyed by numeric id; write only on value change. One line per entry, sorted by id, fields alphabetical — single-line diffs.
def register_entity(path: Path, key: str, value: dict) -> None:
    registry = json.loads(path.read_text()) if path.exists() else {}
    if registry.get(key) == value:
        return
    registry[key] = value
    rows = []
    for entry_key, entry_value in sorted(registry.items(), key=lambda item: int(item[0])):
        fields = ", ".join(f"{json.dumps(k)}: {json.dumps(v, ensure_ascii=False)}" for k, v in sorted(entry_value.items()))
        rows.append(f"  {json.dumps(entry_key)}: {{ {fields} }}")
    path.write_text("{\n" + ",\n".join(rows) + "\n}\n")
