#!/usr/bin/env python3

# Per-cell inspector at (x, y) with optional radius (0..2) — feeds the chronicler ad-hoc tile investigations (battle sites, neighbours, frontier scouting).
# Output: dict keyed by `"x,y"`, each value contains the requested sections for that tile.
# Coordinate convention: WB UI / actor coords; `grid[y][x]` (no inversion — y grows north and so does the row index).

import argparse
import sys
from collections import defaultdict
from pathlib import Path


sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "geography"))
from shared import ZONE_TILES, emit, entity_ref, index_by_id, load_save, parse_sections, take_chapter
from grid import decode_tile_grid, tile_biome, tile_elevation, tile_kind, tile_layer
from islands import compute_islands_cached

_ALL_SECTIONS = ("actors", "buildings", "context", "distances", "tile_info")
_MAX_RADIUS = 2


def _actors_at(x: int, y: int, actors_by_pos: dict[tuple[int, int], list[dict]], cities_by_id: dict, kingdoms_by_id: dict) -> list[dict]:
    return [
        {
            "asset_id": a.get("asset_id"),
            "city": entity_ref(a.get("cityID"), cities_by_id),
            "id": a.get("id"),
            "kingdom": entity_ref(a.get("civ_kingdom_id"), kingdoms_by_id),
            "name": a.get("name"),
        }
        for a in actors_by_pos.get((x, y), [])
    ]


def _buildings_at(x: int, y: int, buildings_by_pos: dict[tuple[int, int], list[dict]]) -> list[dict]:
    return [{"asset_id": b.get("asset_id")} for b in buildings_by_pos.get((x, y), [])]


# Returns `{}` for unclaimed tiles (stripped by `emit`). Distances live in the `distances` section, not here.
def _context_at(x: int, y: int, city_by_pos: dict[tuple[int, int], dict], kingdoms_by_id: dict[int, dict]) -> dict:
    city = city_by_pos.get((x // ZONE_TILES, y // ZONE_TILES))
    if city is None:
        return {}
    return {
        "city": {"id": city["id"], "name": city.get("name") or f"#{city['id']}"},
        "kingdom": entity_ref(city.get("kingdomID"), kingdoms_by_id),
    }


# `to_water` always; `to_capital` only when owned by a city, `to_nearest_city` only when unclaimed. Manhattan distance in tiles.
def _distances_at(
    x: int,
    y: int,
    grid: list[list[int]],
    layer_by_id: list[str],
    city_by_pos: dict[tuple[int, int], dict],
    capital_pos_by_kingdom: dict[int, tuple[int, int]],
    city_centroids: list[tuple[int, int]],
) -> dict:
    out: dict = {"to_water": _water_distance(x, y, grid, layer_by_id)}
    city = city_by_pos.get((x // ZONE_TILES, y // ZONE_TILES))
    if city is None:
        if city_centroids:
            out["to_nearest_city"] = min(abs(x - cx) + abs(y - cy) for cx, cy in city_centroids)
    elif (kid := city.get("kingdomID")) and (cap := capital_pos_by_kingdom.get(kid)) is not None:
        out["to_capital"] = abs(x - cap[0]) + abs(y - cap[1])
    return out


def _radius_tiles(cx: int, cy: int, radius: int, width: int, height: int) -> list[tuple[int, int]]:
    return [(x, y) for dy in range(-radius, radius + 1) for dx in range(-radius, radius + 1) if 0 <= (x := cx + dx) < width and 0 <= (y := cy + dy) < height]


def _tile_info_at(x: int, y: int, grid: list[list[int]], tile_map: list[str], tile_to_island: dict[tuple[int, int], int], frozen_set: set[tuple[int, int]]) -> dict:
    name = tile_map[grid[y][x]]
    out: dict = {"biome": tile_biome(name), "elevation": tile_elevation(name), "island_id": tile_to_island.get((x, y)), "kind": tile_kind(name)}
    if (x, y) in frozen_set:
        out["frozen"] = True
    return out


# All cells walkable => water distance == Manhattan: diamonds expand to the first Ocean ring — coastal sites end it fast, vs a 300k-cell full BFS. `-1` = no water.
def _water_distance(x: int, y: int, grid: list[list[int]], layer_by_id: list[str]) -> int:
    height, width = len(grid), len(grid[0])
    for r in range(width + height):
        for dx in range(-r, r + 1):
            nx = x + dx
            if not 0 <= nx < width:
                continue
            for ny in {y + r - abs(dx), y - r + abs(dx)}:
                if 0 <= ny < height and layer_by_id[grid[ny][nx]] == "Ocean":
                    return r
    return -1


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
        sections = parse_sections(args.sections, _ALL_SECTIONS)
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 2

    save = load_save(save_path)
    grid = decode_tile_grid(save)
    if not grid:
        print("empty grid", file=sys.stderr)
        return 2

    height, width = len(grid), len(grid[0])
    if not (0 <= cx < width and 0 <= cy < height):
        print(f"coords ({cx}, {cy}) out of bounds — map is {width}×{height}", file=sys.stderr)
        return 2

    tile_map = save["tileMap"]
    coords = _radius_tiles(cx, cy, args.radius, width, height)
    wanted = set(coords)
    wanted_zones = {(x // ZONE_TILES, y // ZONE_TILES) for x, y in coords}

    # Index only the queried positions — the save carries ~15k buildings and ~1.5k actors for at most 25 tiles of interest.
    actors_by_pos: dict[tuple[int, int], list[dict]] = defaultdict(list)
    if "actors" in sections:
        for a in save.get("actors_data", []):
            ax, ay = a.get("x"), a.get("y")
            if ax is not None and ay is not None and (pos := (int(ax), int(ay))) in wanted:
                actors_by_pos[pos].append(a)
    buildings_by_pos: dict[tuple[int, int], list[dict]] = defaultdict(list)

    if "buildings" in sections:
        for b in save.get("buildings", []):
            bx, by = b.get("mainX"), b.get("mainY")
            if bx is not None and by is not None and (pos := (int(bx), int(by))) in wanted:
                buildings_by_pos[pos].append(b)
    # `cities/kingdoms_by_id` resolve refs for `actors` + `context`; `city_by_pos`, centroids and capital positions only serve `context`/`distances`.
    cities_by_id: dict[int, dict] = {}
    kingdoms_by_id: dict[int, dict] = {}

    if {"actors", "context", "distances"} & set(sections):
        cities_by_id = index_by_id(save.get("cities") or [])
        kingdoms_by_id = index_by_id(save.get("kingdoms") or [])
    city_by_pos: dict[tuple[int, int], dict] = {}
    capital_pos_by_kingdom: dict[int, tuple[int, int]] = {}
    city_centroids: list[tuple[int, int]] = []

    if {"context", "distances"} & set(sections):
        for c in cities_by_id.values():
            zones = c.get("zones") or []
            if not zones:
                continue
            city_centroids.append(_zone_centroid(zones))
            for z in zones:
                if (zx := z.get("x")) is not None and (zy := z.get("y")) is not None and (zx, zy) in wanted_zones:
                    city_by_pos[(zx, zy)] = c
        for k in kingdoms_by_id.values():
            if (cap_id := k.get("capitalID")) is None:
                continue
            if cap_zones := (cities_by_id.get(cap_id) or {}).get("zones"):
                capital_pos_by_kingdom[k["id"]] = _zone_centroid(cap_zones)
    tile_to_island: dict[tuple[int, int], int] = {}
    frozen_set: set[tuple[int, int]] = set()

    if "tile_info" in sections:
        _, tile_to_island = compute_islands_cached(save, save_path)
        # `frozen_tiles` are packed as `y * width + x` ints — decode to positions, keeping only the queried ones.
        frozen_set = {pos for idx in save.get("frozen_tiles") or [] if (pos := (idx % width, idx // width)) in wanted}
    layer_by_id: list[str] = []

    if "distances" in sections:
        layer_by_id = [tile_layer(name) for name in tile_map]

    out: dict = {}
    for x, y in coords:
        cell: dict = {}
        if "actors" in sections:
            cell["actors"] = _actors_at(x, y, actors_by_pos, cities_by_id, kingdoms_by_id)
        if "buildings" in sections:
            cell["buildings"] = _buildings_at(x, y, buildings_by_pos)
        if "context" in sections:
            cell["context"] = _context_at(x, y, city_by_pos, kingdoms_by_id)
        if "distances" in sections:
            cell["distances"] = _distances_at(x, y, grid, layer_by_id, city_by_pos, capital_pos_by_kingdom, city_centroids)
        if "tile_info" in sections:
            cell["tile_info"] = _tile_info_at(x, y, grid, tile_map, tile_to_island, frozen_set)
        out[f"{x},{y}"] = cell
    emit(out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
