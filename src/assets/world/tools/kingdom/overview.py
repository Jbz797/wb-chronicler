#!/usr/bin/env python3

import json
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).parent.parent))
from shared import load_save, parse_sections  # noqa: E402

_ALL_SECTIONS = ("metadata",)


def _build_metadata(kingdom: dict) -> dict:
    return {
        "name": kingdom.get("name"),
    }


def main(argv: list[str]) -> int:
    if not argv:
        print("usage: overview.py <id> [sections] — see tools/tools.md", file=sys.stderr)
        return 2
    try:
        kingdom_id = int(argv[0])
    except ValueError:
        print(f"invalid id: {argv[0]}", file=sys.stderr)
        return 1
    try:
        sections = parse_sections(argv[1] if len(argv) > 1 else None, _ALL_SECTIONS)
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 2
    save = load_save()
    kingdom = next((k for k in save.get("kingdoms", []) if k.get("id") == kingdom_id), None)
    if kingdom is None:
        print(f"unknown kingdom: {kingdom_id}", file=sys.stderr)
        return 1

    out: dict = {}
    if "metadata" in sections:
        out["metadata"] = _build_metadata(kingdom)

    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
