#!/usr/bin/env python3

# Per-cell inspector at (x, y) with optional radius (0..2) — feeds the chronicler ad-hoc tile investigations (battle sites, neighbours, frontier scouting).
# Output: dict keyed by `"x,y"`, each value contains the requested sections for that tile.
# Coordinate convention: WB UI / actor coords; `grid[y][x]` (no inversion — y grows north and so does the row index).

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))

from grid import decode_tile_grid, tile_biome, tile_elevation, tile_kind, tile_layer
from islands import compute_islands_cached
from shared import ZONE_TILES, emit, entity_ref, index_by_id, load_data, load_save, parse_sections, take_chapter

_ALL_SECTIONS = ("actors", "buildings", "context", "distances", "tile_info")
_MAX_RADIUS = 2


# Identity and allegiance only — the chronicler follows up with `actor/info.py <id>` for the rest, so a tile sweep stays readable at 25 cells.
def _actors_at(x: int, y: int, ctx: dict) -> list[dict]:
    return [
        {
            "asset_id": a.get("asset_id"),
            "city": entity_ref(a.get("cityID"), ctx["cities_by_id"]),
            "id": a.get("id"),
            "kingdom": entity_ref(a.get("civ_kingdom_id"), ctx["kingdoms_by_id"]),
            "name": a.get("name"),
        }
        for a in ctx["actors_by_pos"].get((x, y), ())
    ]


# One home for every index, each built only for the sections that asked — ~15 k buildings and ~1.5 k actors for 25 tiles, and 331 k cells to decode.
def _build_context(save: dict, save_path: Path, sections: set[str], coords: list[tuple[int, int]], center: tuple[int, int], width: int) -> dict:
    wanted = set(coords)
    ctx: dict = {"actors_by_pos": {}, "buildings_by_pos": {}, "center": center, "cities_by_id": {}, "grid": [], "kingdoms_by_id": {}, "tile_map": save["tileMap"]}

    if "actors" in sections:
        for a in save.get("actors_data") or []:
            ax, ay = a.get("x"), a.get("y")
            if ax is not None and ay is not None and (pos := (int(ax), int(ay))) in wanted:
                ctx["actors_by_pos"].setdefault(pos, []).append(a)

    if "buildings" in sections:
        for b in save.get("buildings") or []:
            bx, by = b.get("mainX"), b.get("mainY")
            if bx is not None and by is not None and (pos := (int(bx), int(by))) in wanted:
                ctx["buildings_by_pos"].setdefault(pos, []).append(b)

    if {"actors", "context", "distances"} & sections:  # the two id maps resolve refs for `actors` as well as `context`
        ctx["cities_by_id"] = index_by_id(save.get("cities") or [])
        ctx["kingdoms_by_id"] = index_by_id(save.get("kingdoms") or [])

    if {"distances", "tile_info"} & sections:
        ctx["grid"] = decode_tile_grid(save)

    if {"context", "distances"} & sections:
        _index_cities(ctx, {(x // ZONE_TILES, y // ZONE_TILES) for x, y in coords})

    if "tile_info" in sections:
        _, ctx["tile_to_island"] = compute_islands_cached(save, save_path)
        # `frozen_tiles` are packed as `y * width + x` ints — decode to positions, keeping only the queried ones.
        ctx["frozen_set"] = {pos for idx in save.get("frozen_tiles") or [] if (pos := (idx % width, idx // width)) in wanted}

    if "distances" in sections:
        ctx["layer_by_id"] = [tile_layer(name) for name in ctx["tile_map"]]
        ctx["water_at_center"] = _water_distance(*center, ctx["grid"], ctx["layer_by_id"])

    return ctx


def _buildings_at(x: int, y: int, ctx: dict) -> list[dict]:
    return [{"asset_id": b.get("asset_id")} for b in ctx["buildings_by_pos"].get((x, y), ())]


# Returns `{}` for unclaimed tiles (stripped by `emit`). Distances live in the `distances` section, not here.
def _context_at(x: int, y: int, ctx: dict) -> dict:
    city = ctx["city_by_pos"].get((x // ZONE_TILES, y // ZONE_TILES))
    if city is None:
        return {}
    return {"city": {"id": city["id"], "name": city.get("name")}, "kingdom": entity_ref(city.get("kingdomID"), ctx["kingdoms_by_id"])}


# `to_water` always, `to_capital` if owned else `to_nearest_city`, in tiles. No neighbour undercuts the centre's water by their gap, so its diamond starts there.
def _distances_at(x: int, y: int, ctx: dict) -> dict:
    cx, cy = ctx["center"]
    gap, floor = abs(x - cx) + abs(y - cy), ctx["water_at_center"]
    water = floor if gap == 0 or floor < 0 else _water_distance(x, y, ctx["grid"], ctx["layer_by_id"], max(0, floor - gap))

    out: dict = {"to_water": water}
    city = ctx["city_by_pos"].get((x // ZONE_TILES, y // ZONE_TILES))
    if city is None:
        if centroids := ctx["city_centroids"]:
            out["to_nearest_city"] = min(abs(x - ox) + abs(y - oy) for ox, oy in centroids)
    elif (kid := city.get("kingdomID")) and (cap := ctx["capital_pos_by_kingdom"].get(kid)) is not None:
        out["to_capital"] = abs(x - cap[0]) + abs(y - cap[1])
    return out


# Zone-to-city for the queried tiles, every city's anchor, and each crown's seat — centroids memoised across the three, a capital being a city already walked.
def _index_cities(ctx: dict, wanted_zones: set[tuple[int, int]]) -> None:
    centroids: dict[int, tuple[int, int]] = {}
    ctx["capital_pos_by_kingdom"] = {}
    ctx["city_by_pos"] = {}

    for city in ctx["cities_by_id"].values():
        if not (zones := city.get("zones")):
            continue
        centroids[city["id"]] = _zone_centroid(zones)
        for zone in zones:
            if (zx := zone.get("x")) is not None and (zy := zone.get("y")) is not None and (zx, zy) in wanted_zones:
                ctx["city_by_pos"][(zx, zy)] = city

    ctx["city_centroids"] = list(centroids.values())
    for kingdom in ctx["kingdoms_by_id"].values():
        if (seat := centroids.get(kingdom.get("capitalID"))) is not None:
            ctx["capital_pos_by_kingdom"][kingdom["id"]] = seat


def _radius_tiles(cx: int, cy: int, radius: int, width: int, height: int) -> list[tuple[int, int]]:
    return [(x, y) for dy in range(-radius, radius + 1) for dx in range(-radius, radius + 1) if 0 <= (x := cx + dx) < width and 0 <= (y := cy + dy) < height]


# `frozen` only when true — 25 `false` otherwise; the biome flavour rides on the queried tile alone, 70 % of radius-2 sweeps holding a single biome.
def _tile_info_at(x: int, y: int, ctx: dict, queried: bool) -> dict:
    name = ctx["tile_map"][ctx["grid"][y][x]]
    biome = tile_biome(name)
    out: dict = {"biome": biome, "elevation": tile_elevation(name), "island_id": ctx["tile_to_island"].get((x, y)), "kind": tile_kind(name)}
    if biome and queried:  # chronicler-only: WB's own English line on the terrain, which nothing else in the tools surfaces
        out["biome_description"] = (load_data("biomes.json").get(biome) or {}).get("description")
    if (x, y) in ctx["frozen_set"]:
        out["frozen"] = True
    return out


# Diamonds expand to the first Ocean ring, every cell walkable — coastal sites end fast, vs a 300 k-cell BFS. `-1` = no water, and one tile settles it for all.
def _water_distance(x: int, y: int, grid: list[list[int]], layer_by_id: list[str], start: int = 0) -> int:
    height, width = len(grid), len(grid[0])
    for r in range(start, width + height):
        for dx in range(-r, r + 1):
            nx = x + dx
            if not 0 <= nx < width:
                continue
            for ny in {y + r - abs(dx), y - r + abs(dx)}:
                if 0 <= ny < height and layer_by_id[grid[ny][nx]] == "Ocean":
                    return r
    return -1


# argparse type converter — raising `ArgumentTypeError` is what makes it print the usage line rather than a traceback.
def _xy(value: str) -> tuple[int, int]:
    try:
        x_str, y_str = value.split(",", 1)
        return int(x_str), int(y_str)
    except ValueError as e:
        raise argparse.ArgumentTypeError(f"expected `x,y` (e.g. `415,117`), got {value!r}") from e


# Cities are zone polygons, not points — collapse to one integer anchor for distances, in tile space like every coord here.
def _zone_centroid(zones: list[dict]) -> tuple[int, int]:
    n, half = len(zones), ZONE_TILES // 2
    return sum(z.get("x", 0) * ZONE_TILES + half for z in zones) // n, sum(z.get("y", 0) * ZONE_TILES + half for z in zones) // n


def main(argv: list[str]) -> int:
    save_path, argv, _ = take_chapter(argv)  # pop the `C<n>` token first — argparse has no such positional and would abort on it

    parser = argparse.ArgumentParser(prog="tiles/info.py", description="Inspect tile(s) at (x, y) with optional radius. Output is keyed by `'x,y'`.")
    parser.add_argument("xy", type=_xy, metavar="x,y", help="Tile coords (WB UI, y grows north), comma-separated — e.g. `415,117`.")
    parser.add_argument("sections", nargs="?", default="full", help=f"Comma-separated sections or `full`. Valid: {', '.join(_ALL_SECTIONS)}")
    parser.add_argument("--radius", "-r", type=int, default=0, choices=range(_MAX_RADIUS + 1), help=f"Radius around (x, y) — 0..{_MAX_RADIUS} (default 0).")
    args = parser.parse_args(argv)
    cx, cy = args.xy

    try:
        sections = set(parse_sections(args.sections, _ALL_SECTIONS))  # membership only, never walked in order — the emitting `if`s below name each one
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 2

    save = load_save(save_path)

    # The grid ships run-length encoded, so its shape reads off the header — no need to decode 331 k tiles to bounds-check the query.
    height = len(save.get("tileArray") or [])
    width = sum((save.get("tileAmounts") or [[]])[0])

    if not (height and width):
        print("empty grid", file=sys.stderr)
        return 2

    if not (0 <= cx < width and 0 <= cy < height):
        print(f"coords ({cx}, {cy}) out of bounds — map is {width}×{height}", file=sys.stderr)
        return 2

    coords = _radius_tiles(cx, cy, args.radius, width, height)
    ctx = _build_context(save, save_path, sections, coords, (cx, cy), width)

    out: dict = {}
    for x, y in coords:
        cell: dict = {}
        if "actors" in sections:
            cell["actors"] = _actors_at(x, y, ctx)
        if "buildings" in sections:
            cell["buildings"] = _buildings_at(x, y, ctx)
        if "context" in sections:
            cell["context"] = _context_at(x, y, ctx)
        if "distances" in sections:
            cell["distances"] = _distances_at(x, y, ctx)
        if "tile_info" in sections:
            cell["tile_info"] = _tile_info_at(x, y, ctx, (x, y) == (cx, cy))
        out[f"{x},{y}"] = cell
    emit(out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
