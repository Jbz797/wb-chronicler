#!/usr/bin/env python3

# Geographic stats reserved for the chronicler (not consumed by the UI). User-facing docs: `tools/tools.md`.

import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).parent.parent))
from shared import emit, load_save, parse_sections, take_chapter
from islands import compute_islands_cached

_ALL_SECTIONS = ("islands", "natural_features")
# Rare geological/mineral landmarks. Common minerals (stone/metals/silver/mythril) and vegetation excluded — too noisy narratively.
_NATURAL_ASSETS = frozenset({"geyser", "mineral_adamantine", "mineral_bones", "mineral_gems", "mineral_gold", "volcano"})


# Sorted by asset_id alpha then (y, x) for stable output across saves.
def _build_natural_features(save: dict) -> list[dict]:
    out = []
    for b in save.get("buildings") or []:
        asset = b.get("asset_id")
        if asset in _NATURAL_ASSETS and (bx := b.get("mainX")) is not None and (by := b.get("mainY")) is not None:
            out.append({"asset_id": asset, "x": int(bx), "y": int(by)})
    return sorted(out, key=lambda b: (b["asset_id"], b["y"], b["x"]))


def main(argv: list[str]) -> int:
    save_path, argv, _ = take_chapter(argv)
    try:
        sections = parse_sections(argv[0] if argv else None, _ALL_SECTIONS)
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 2
    save = load_save(save_path)
    out: dict = {}
    if "islands" in sections:
        islands, _ = compute_islands_cached(save, save_path)
        out["islands"] = islands
    if "natural_features" in sections:
        out["natural_features"] = _build_natural_features(save)
    emit(out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
