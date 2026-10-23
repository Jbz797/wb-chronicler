#!/usr/bin/env python3

# Rings a spot on the chapter's map, or blows up the ground around it, and hands back the path — no other way finds a tile by its numbers. Docs: `docs/tools.md`.

import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))

from PIL import Image, ImageDraw, ImageFont

from grid import BARE, LazyTileGrid, listed_tiles, tile_frost, tile_ground, tile_layer
from islands import compute_islands_cached
from shared import arg_parser, load_save, take_chapter

_INK = (255, 30, 30)  # a red no biome wears, so the ring never sinks into the ground it marks
_MAPS_DIR = Path(__file__).parent.parent / ".cache" / "maps"  # inside the chronicler's own directory, read without a prompt; gitignored with the other caches
_MAPS_KEPT = 20  # the latest pictures kept, as many as `shared`'s cache slots: a map redraws in an instant, so the oldest gives way
_NORTH_UP = "north up (y grows upward)"  # both maps say it where they are read: a picture's rows count down, the world's y counts up
_RADIUS = 46  # wide enough to be seen on a map two thousand tiles across, tight enough to leave the spot itself readable
_SHARES_NAMED = 6  # the shares a zoom names, the rest summed as `others`: past a handful, the line lists more than it tells
_STROKE = 6  # thick enough to survive the shrinking a viewer applies to a map this wide
_TICK_INNER = 60  # where each arm starts, clear of the ring, so the marked tile stays in the open
_TICK_OUTER = 110  # and where it ends, far enough out to catch the eye scanning the whole map
_ZOOM_BAR = 10  # tiles the scale bar spans: a kilometre at `chronicler.md`'s 100 m a tile
_ZOOM_MAX = 250  # past this the zoom shows little the whole map does not
_ZOOM_MIN = 4  # under this the square holds too little ground to read a shore by
_ZOOM_SIDE = 720  # pixels the zoomed square is blown up to, whatever its span: a creek reads, and the picture still opens whole


# The map is drawn north-up while the save counts y northward, so the two run against each other — the one conversion this script exists to get right.
def _pixel(y: int, height: int) -> int:
    return height - 1 - y


# A picture into the maps' cache, the oldest beyond `_MAPS_KEPT` let go → its path.
def _saved(image: Image.Image, name: str) -> Path:
    _MAPS_DIR.mkdir(parents=True, exist_ok=True)
    out = _MAPS_DIR / name
    image.save(out)
    others = sorted((f for f in _MAPS_DIR.glob("*.png") if f != out), key=lambda f: f.stat().st_mtime, reverse=True)  # the one just drawn is never let go
    for stale in others[_MAPS_KEPT - 1 :]:
        stale.unlink(missing_ok=True)
    return out


# What the zoomed square is made of, by share of its tiles — the numbers beside the picture: each ground as `biomes` names it, then fire, snowcap, ice, frost.
def _shares(save_path: Path, x: int, y: int, span: int) -> str:
    save = load_save(save_path)
    grid, island_of = LazyTileGrid(save), compute_islands_cached(save, save_path)[1]
    # Each tile by its ground as `geography … biomes` names it, a biome or a bare ground, rock and lava among them; water where no ground is.
    names = save.get("tileMap") or []
    ground = [(tile_ground(name) or "").removeprefix(BARE) or "water" for name in names]
    soil, frost = [tile_layer(name) == "Ground" for name in names], [tile_frost(name) for name in names]
    counts, cover = Counter[str](), Counter[str]()  # the grounds, then what lies over them: a snowcap hides its rock, ice its sea, so both are told beside
    rows, cols = range(max(y - span, 0), min(y + span, grid.height - 1) + 1), range(max(x - span, 0), min(x + span, grid.width - 1) + 1)
    for row in rows:
        for col in cols:
            tile = grid[row][col]
            counts["islets" if soil[tile] and island_of.get((col, row)) is None else ground[tile]] += 1  # soil too small to be a land, as `geography` buckets it
            if frost[tile] and frost[tile] != ground[tile]:  # bare snow is a ground of its own, already a share
                cover[frost[tile]] += 1
    total = sum(counts.values())
    ranked = counts.most_common()
    if len(ranked) > _SHARES_NAMED:  # a wide square holds a score of grounds: the lesser ones read as one
        ranked = [*ranked[: _SHARES_NAMED - 1], ("others", sum(n for _, n in ranked[_SHARES_NAMED - 1 :]))]
    shown = " · ".join(f"{what} {round(n * 100 / total) or '<1'}%" for what, n in ranked)  # `<1%` where a few tiles stand: never read as none
    # The fire and the passing frost, as `geography` names them: the save lists their tiles, the square counts its own.
    cover["burning"], cover["frost"] = (sum(col in cols and row in rows for col, row in listed_tiles(save, key)) for key in ("fire", "frozen_tiles"))
    told = "".join(f", {n} {what}" for what, n in sorted(cover.items()) if n)
    return shown + f" — of the {total:,} tiles shown".replace(",", " ") + told


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
        out = _saved(_zoomed(image, px, py, args.zoom), f"{chapter}_{x}_{y}_zoom{args.zoom}.png")
        print(f"✓ {chapter} — ({x},{y}) and {args.zoom} tiles each way, {_NORTH_UP}, the white bar {_ZOOM_BAR} tiles\n  {out}")
        print(f"  {_shares(save_path, x, y, args.zoom)}")
        return 0
    draw = ImageDraw.Draw(image)
    draw.ellipse([px - _RADIUS, py - _RADIUS, px + _RADIUS, py + _RADIUS], outline=_INK, width=_STROKE)
    for near, far in ((-_TICK_OUTER, -_TICK_INNER), (_TICK_INNER, _TICK_OUTER)):  # arms on all four sides, the centre left bare
        draw.line([px + near, py, px + far, py], fill=_INK, width=_STROKE)
        draw.line([px, py + near, px, py + far], fill=_INK, width=_STROKE)

    out = _saved(image, f"{chapter}_{x}_{y}.png")  # chapter and tile name it whole: two maps of the same spot are the same picture
    print(f"✓ {chapter} — ({x},{y}) ringed on a map of {width}×{height}, {_NORTH_UP}\n  {out}")
    # Said here rather than in the manual: the picture is for the player's screen, and a chronicler who only reads it has done half the errand.
    print("  → chronicler: open it on the player's screen — looking at it yourself shows him nothing")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
