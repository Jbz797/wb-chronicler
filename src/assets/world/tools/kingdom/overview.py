#!/usr/bin/env python3

import json
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).parent.parent))
from shared import emit, index_by_id, load_data, load_save, parse_sections  # noqa: E402

_ALL_SECTIONS = ("metadata",)
_REGISTRY = Path(__file__).parent.parent.parent / "saves" / "kingdoms.json"


def _build_metadata(kingdom: dict) -> dict:
    return {
        "id": kingdom.get("id"),
        "name": kingdom.get("name"),
    }


# Incrementally enrich the registry consumed by the reader: add this kingdom's color + banner icon
# only if absent (the name lives in each chapter.json, not here).
def _register_kingdom(kingdom: dict) -> None:
    registry = json.loads(_REGISTRY.read_text()) if _REGISTRY.exists() else {}
    key = str(kingdom.get("id"))
    if key in registry:
        return
    registry[key] = {
        "banner_icon": load_data("banner-icons.json").get(str(kingdom.get("banner_icon_id", ""))),
        "color": load_data("colors.json").get(str(kingdom.get("color_id", ""))),
    }
    _REGISTRY.write_text(json.dumps(registry, ensure_ascii=False, indent=2) + "\n")


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
    kingdom = index_by_id(save.get("kingdoms", [])).get(kingdom_id)
    if kingdom is None:
        print(f"unknown kingdom: {kingdom_id}", file=sys.stderr)
        return 1
    _register_kingdom(kingdom)

    out: dict = {}
    if "metadata" in sections:
        out["metadata"] = _build_metadata(kingdom)

    emit(out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
