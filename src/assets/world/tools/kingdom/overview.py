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


# One line per kingdom, value inlined, entries sorted by id and fields alphabetically — keeps a
# clean, stable git diff regardless of the order kingdoms are registered in.
def _format_registry(registry: dict) -> str:
    if not registry:
        return "{}\n"
    rows = []
    for key, value in sorted(registry.items(), key=lambda item: int(item[0])):
        fields = ", ".join(f"{json.dumps(k)}: {json.dumps(v, ensure_ascii=False)}" for k, v in sorted(value.items()))
        rows.append(f"  {json.dumps(key)}: {{ {fields} }}")
    return "{\n" + ",\n".join(rows) + "\n}\n"


# Relative luminance (WCAG) of a "#RRGGBB" colour — used to pick the darkest / lightest of a palette.
def _luminance(color: str) -> float:
    channels = [int(color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    linear = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


# Incrementally enrich the reader's registry, adding this kingdom only if absent. The name is kept
# here (alongside the immutable colour + icon) so the UI can render any kingdom from its id alone —
# tags reference kingdoms beyond the current chapter.
def _register_kingdom(kingdom: dict, save: dict) -> None:
    registry = json.loads(_REGISTRY.read_text()) if _REGISTRY.exists() else {}
    key = str(kingdom.get("id"))
    if key in registry:
        return
    # Background = darkest of the colour's 4 game hues, ink (icon/text/border) = lightest — maximises
    # contrast while staying within the kingdom's real palette (colors-all.json).
    palette = [h for h in load_data("colors-all.json").get(str(kingdom.get("color_id", "")), {}).values() if h]
    registry[key] = {
        "banner_icon": _resolve_banner_sprite(kingdom, save),
        "color": min(palette, key=_luminance) if palette else None,
        "ink": max(palette, key=_luminance) if palette else None,
        "name": kingdom.get("name"),
    }
    _REGISTRY.write_text(_format_registry(registry))


# Resolve the banner glyph WorldBox renders, mirroring Kingdom.getElementIcon: index banner_icon_id
# into the icon list of the king's species banner set (the founder species when there is no living
# king). banner_icon_id is used as-is (null -> 0) and reset to 0 when out of range.
#
# CLAUDE: banner-icons.json is generated from the game's *BannerLibrary assets and covers every
# species, so this always resolves — don't hand-patch it; regenerate from the game files if a new
# species ever appears.
def _resolve_banner_sprite(kingdom: dict, save: dict) -> int:
    king = next((a for a in save.get("actors_data", []) if a.get("id") == kingdom.get("kingID")), None)
    subspecies = index_by_id(save.get("subspecies", [])).get(king.get("subspecies")) if king else None
    species = (subspecies or {}).get("species_id") or kingdom.get("original_actor_asset")
    banners = load_data("banner-icons.json")
    icons = banners["banner_id_icons"][banners["species_to_banner_id"][species]]
    index = kingdom.get("banner_icon_id") or 0
    return icons[index if index < len(icons) else 0]


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
    _register_kingdom(kingdom, save)

    out: dict = {}
    if "metadata" in sections:
        out["metadata"] = _build_metadata(kingdom)

    emit(out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
