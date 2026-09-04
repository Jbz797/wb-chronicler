#!/usr/bin/env python3

# Rings a spot on the chapter's map and hands back the path — the player has no other way to find a tile by its numbers. Docs: `tools/tools.md`.

import argparse
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))

from PIL import Image, ImageDraw

from shared import SAVES_DIR, latest_chapter, live_save

_INK = (255, 30, 30)  # a red no biome wears, so the ring never sinks into the ground it marks
_RADIUS = 46  # wide enough to be seen on a map two thousand tiles across, tight enough to leave the spot itself readable
_STROKE = 6  # thick enough to survive the shrinking a viewer applies to a map this wide
_TICK_INNER = 60  # where each arm starts, clear of the ring, so the marked tile stays in the open
_TICK_OUTER = 110  # and where it ends, far enough out to catch the eye scanning the whole map


# The map is drawn north-up while the save counts y northward, so the two run against each other — the one conversion this script exists to get right.
def _pixel(y: int, height: int) -> int:
    return height - 1 - y


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="map/show.py", description="Ring a tile on the chapter's map and hand back the path.")
    parser.add_argument("position", help="`x,y` in save coordinates — an actor's, a building's, anything `tiles/info.py` reads")
    args = parser.parse_args(argv)

    try:
        x, y = (int(n) for n in args.position.split(","))
    except ValueError:
        print(f"✗ position reads `x,y`, not `{args.position}`", file=sys.stderr)
        return 2

    chapter = f"C{latest_chapter()}"  # the chapter being written, the only one a map is ever asked about
    preview = SAVES_DIR / chapter / "preview.png"
    if not preview.exists():  # before the first chapter there is no archive, and the live save carries the only picture
        preview = live_save().parent / "preview.png"
    if not preview.exists():
        print(f"✗ no map to show — neither {SAVES_DIR / chapter / 'preview.png'} nor the live save has one", file=sys.stderr)
        return 1

    image = Image.open(preview).convert("RGB")
    width, height = image.size
    if not (0 <= x < width and 0 <= y < height):
        print(f"✗ ({x},{y}) falls outside a map of {width}×{height}", file=sys.stderr)
        return 2

    px, py = x, _pixel(y, height)
    draw = ImageDraw.Draw(image)
    draw.ellipse([px - _RADIUS, py - _RADIUS, px + _RADIUS, py + _RADIUS], outline=_INK, width=_STROKE)
    for near, far in ((-_TICK_OUTER, -_TICK_INNER), (_TICK_INNER, _TICK_OUTER)):  # arms on all four sides, the centre left bare
        draw.line([px + near, py, px + far, py], fill=_INK, width=_STROKE)
        draw.line([px, py + near, px, py + far], fill=_INK, width=_STROKE)

    out = Path(tempfile.gettempdir()) / f"{chapter}_{x}_{y}.png"  # chapter and tile name it whole: two maps of the same spot are the same picture
    image.save(out)
    print(f"✓ {chapter} — ({x},{y}) ringed on a map of {width}×{height}\n  {out}")
    # Said here rather than in the manual: the picture is for the player's screen, and a chronicler who only reads it has done half the errand.
    print("  → chronicler: open it on the player's screen — looking at it yourself shows him nothing")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
