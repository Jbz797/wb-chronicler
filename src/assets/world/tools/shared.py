#!/usr/bin/env python3

# Shared constants/helpers reused by `actor/overview.py`, `kingdom/overview.py` and `world/overview.py` — `sys.path`-injected from parent dir; see each bootstrap.

import json
import sys
import zlib
from functools import cache
from pathlib import Path


CURRENT_SAVE = Path.home() / "Library/Application Support/mkarpenko/WorldBox/saves/save1/map.wbox"
DATAS_DIR = Path(__file__).parent / "datas"


def emit(out: dict) -> None:
    print(json.dumps(out, ensure_ascii=False, indent=2))


def index_by_id(records: list[dict], key: str = "id") -> dict:
    return {record[key]: record for record in records}


# Loads (and caches) a JSON file from the datas dir — `{}` if it doesn't exist.
@cache
def load_data(name: str) -> dict:
    path = DATAS_DIR / name
    return json.loads(path.read_text()) if path.exists() else {}


def load_save() -> dict:
    if not CURRENT_SAVE.exists():
        print(f"no save found at {CURRENT_SAVE}", file=sys.stderr)
        sys.exit(2)
    with CURRENT_SAVE.open("rb") as f:
        return json.loads(zlib.decompress(f.read()))


# Parses a comma-separated section list — `None` / "full" expand to all known sections.
def parse_sections(arg: str | None, all_sections: tuple[str, ...]) -> tuple[str, ...]:
    if not arg or arg == "full":
        return all_sections
    requested = tuple(s.strip() for s in arg.split(",") if s.strip())
    if unknown := [s for s in requested if s not in all_sections]:
        raise ValueError(f"unknown section(s): {','.join(unknown)} — valid: full,{','.join(all_sections)}")
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
