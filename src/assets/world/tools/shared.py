#!/usr/bin/env python3

# Shared constants + helpers reused by `actor/overview.py` and `world/overview.py`.
# Importable via `sys.path` injection from the parent dir — see how each script
# bootstraps before `from shared import ...`.

import json
import sys
import zlib
from pathlib import Path


CURRENT_SAVE = Path.home() / "Library/Application Support/mkarpenko/WorldBox/saves/save1/map.wbox"


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
