#!/usr/bin/env python3

# Rings a spot on the chapter's map, or blows up the ground around it, and hands back the path — no other way finds a tile by its numbers. Docs: `docs/tools.md`.

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))

from PIL import Image, ImageDraw, ImageFont

from shared import arg_parser, take_chapter

_INK = (255, 30, 30)  # a red no biome wears, so the ring never sinks into the ground it marks
_NORTH_UP = "north up (y grows upward)"  # both maps say it where they are read: a picture's rows count down, the world's y counts up
_RADIUS = 46  # wide enough to be seen on a map two thousand tiles across, tight enough to leave the spot itself readable
_STROKE = 6  # thick enough to survive the shrinking a viewer applies to a map this wide
_TICK_INNER = 60  # where each arm starts, clear of the ring, so the marked tile stays in the open
_TICK_OUTER = 110  # and where it ends, far enough out to catch the eye scanning the whole map
_ZOOM_BAR = 10  # tiles the scale bar spans: about a kilometre at `chronicler.md`'s 100–120 m a tile
_ZOOM_MAX = 250  # past this the zoom shows little the whole map does not
_ZOOM_MIN = 4  # under this the square holds too little ground to read a shore by
_ZOOM_SIDE = 720  # pixels the zoomed square is blown up to, whatever its span: a creek reads, and the picture still opens whole


# The map is drawn north-up while the save counts y northward, so the two run against each other — the one conversion this script exists to get right.
def _pixel(y: int, height: int) -> int:
    return height - 1 - y


# A square of `span` tiles each way around the spot, blown up by whole pixels so each tile stays a crisp block: the tile ringed, north and the scale marked.
def _zoomed(image: Image.Image, px: int, py: int, span: int) -> Image.Image:
    left, top = max(px - span, 0), max(py - span, 0)
    crop = image.crop((left, top, min(px + span + 1, image.width), min(py + span + 1, image.height)))
    scale = max(_ZOOM_SIDE // (2 * span + 1), 1)
    crop = crop.resize((crop.width * scale, crop.height * scale), Image.Resampling.NEAREST)
    draw, font = ImageDraw.Draw(crop), ImageFont.load_default(size=18)
    tx, ty = (px - left) * scale, (py - top) * scale
    cx, cy, stroke = tx + scale // 2, ty + scale // 2, max(scale // 3, 2)
    draw.rectangle([tx, ty, tx + scale - 1, ty + scale - 1], outline=_INK, width=max(stroke // 2, 1))  # the ring says where, the square which tile
    ring = 4 * scale + stroke
    draw.ellipse([cx - ring, cy - ring, cx + ring, cy + ring], outline=_INK, width=stroke)
    halo = {"stroke_fill": (0, 0, 0), "stroke_width": 2}  # white on a black edge, readable on sea and snow alike
    draw.text((10, 8), "N", font=font, fill=(255, 255, 255), **halo)
    bar_y = crop.height - 14
    draw.line([10, bar_y, 10 + _ZOOM_BAR * scale, bar_y], fill=(0, 0, 0), width=6)
    draw.line([10, bar_y, 10 + _ZOOM_BAR * scale, bar_y], fill=(255, 255, 255), width=3)
    return crop


def main(argv: list[str]) -> int:
    save_path, argv, label = take_chapter(argv)
    parser = arg_parser(prog="map/show.py", description="Ring a tile on a chapter's map (`C<n>`, the latest by default) and hand back the path.")
    parser.add_argument("position", help="`x,y` in save coordinates — an actor's, a building's, anything `tiles/info.py` reads")
    parser.add_argument("--zoom", type=int, metavar="n", help=f"only the {_ZOOM_MIN}..{_ZOOM_MAX} tiles each way around it, blown up to read a shore by")
    args = parser.parse_args(argv)
    if args.zoom is not None and not _ZOOM_MIN <= args.zoom <= _ZOOM_MAX:  # refused before the map is opened
        print(f"✗ `--zoom` reads {_ZOOM_MIN} to {_ZOOM_MAX} tiles each way, not {args.zoom}", file=sys.stderr)
        return 2

    try:
        x, y = (int(n) for n in args.position.split(","))
    except ValueError:
        print(f"✗ position reads `x,y`, not `{args.position}`", file=sys.stderr)
        return 2

    chapter, preview = label or "live", save_path.parent / "preview.png"  # a chapter's own map, as it stood: a land peopled at C3 lies bare at C1
    if not preview.exists():
        print(f"✗ no map to show — {preview} is missing", file=sys.stderr)
        return 1

    image = Image.open(preview).convert("RGB")
    width, height = image.size
    if not (0 <= x < width and 0 <= y < height):
        print(f"✗ ({x},{y}) falls outside a map of {width}×{height}", file=sys.stderr)
        return 2

    px, py = x, _pixel(y, height)
    if args.zoom is not None:
        out = Path(tempfile.gettempdir()) / f"{chapter}_{x}_{y}_zoom{args.zoom}.png"
        _zoomed(image, px, py, args.zoom).save(out)
        print(f"✓ {chapter} — ({x},{y}) and {args.zoom} tiles each way, {_NORTH_UP}, the white bar {_ZOOM_BAR} tiles\n  {out}")
        print("  → chronicler: this one is yours to read, for the lie of the ground — open it for the player only if he is to see it")
        return 0
    draw = ImageDraw.Draw(image)
    draw.ellipse([px - _RADIUS, py - _RADIUS, px + _RADIUS, py + _RADIUS], outline=_INK, width=_STROKE)
    for near, far in ((-_TICK_OUTER, -_TICK_INNER), (_TICK_INNER, _TICK_OUTER)):  # arms on all four sides, the centre left bare
        draw.line([px + near, py, px + far, py], fill=_INK, width=_STROKE)
        draw.line([px, py + near, px, py + far], fill=_INK, width=_STROKE)

    out = Path(tempfile.gettempdir()) / f"{chapter}_{x}_{y}.png"  # chapter and tile name it whole: two maps of the same spot are the same picture
    image.save(out)
    print(f"✓ {chapter} — ({x},{y}) ringed on a map of {width}×{height}, {_NORTH_UP}\n  {out}")
    # Said here rather than in the manual: the picture is for the player's screen, and a chronicler who only reads it has done half the errand.
    print("  → chronicler: open it on the player's screen — looking at it yourself shows him nothing")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
