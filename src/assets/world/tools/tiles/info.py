#!/usr/bin/env python3

# Per-cell inspector at (x, y) with optional radius (0..2) — feeds the chronicler ad-hoc tile investigations (battle sites, neighbours, frontier scouting).
# Output: dict keyed by `"x,y"`, each value contains the requested sections for that tile.
# Coordinate convention: WB UI / actor coords; `grid[y][x]` (no inversion — y grows north and so does the row index).

import argparse
import sys
from collections import defaultdict, deque
from pathlib import Path


sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "geography"))
from shared import CURRENT_SAVE, emit, index_by_id, load_save, parse_sections
from grid import decode_tile_grid, tile_biome, tile_elevation, tile_kind, tile_layer
from islands import compute_islands_cached

_ALL_SECTIONS = ("actors", "buildings", "context", "distances", "tile_info")
_DELTAS_4 = ((-1, 0), (1, 0), (0, -1), (0, 1))
_MAX_RADIUS = 2


def _actors_at(x: int, y: int, actors_by_pos: dict[tuple[int, int], list[dict]]) -> list[dict]:
    return [{"asset_id": a.get("asset_id"), "id": a.get("id"), "kingdom_id": a.get("civ_kingdom_id"), "name": a.get("name")} for a in actors_by_pos.get((x, y), [])]


# Precompute distance-to-nearest-water for every tile via multi-source 4-conn BFS from all Ocean tiles. O(W·H) once → O(1) lookup per tile after.
def _build_water_distance_grid(grid: list[list[int]], layer_by_id: list[str], width: int, height: int) -> list[list[int]]:
    dist = [[-1] * width for _ in range(height)]
    queue: deque[tuple[int, int]] = deque()
    for y in range(height):
        for x in range(width):
            if layer_by_id[grid[y][x]] == "Ocean":
                dist[y][x] = 0
                queue.append((x, y))
    while queue:
        x, y = queue.popleft()
        for dx, dy in _DELTAS_4:
            nx, ny = x + dx, y + dy
            if 0 <= nx < width and 0 <= ny < height and dist[ny][nx] == -1:
                dist[ny][nx] = dist[y][x] + 1
                queue.append((nx, ny))
    return dist


def _buildings_at(x: int, y: int, buildings_by_pos: dict[tuple[int, int], list[dict]]) -> list[dict]:
    return [{"asset_id": b.get("asset_id")} for b in buildings_by_pos.get((x, y), [])]


# Returns `{}` for unclaimed tiles (stripped by `emit`). Distances live in the `distances` section, not here.
def _context_at(x: int, y: int, city_by_pos: dict[tuple[int, int], dict], kingdoms_by_id: dict[int, dict]) -> dict:
    city = city_by_pos.get((x, y))
    if city is None:
        return {}
    out: dict = {"city": {"id": city["id"], "name": city.get("name")}}
    if kid := city.get("kingdomID"):
        out["kingdom"] = {"id": kid, "name": kingdoms_by_id.get(kid, {}).get("name")}
    return out


# `to_water` always; `to_capital` only when owned by a city, `to_nearest_city` only when unclaimed. Manhattan distance in tiles.
def _distances_at(
    x: int,
    y: int,
    water_dist: list[list[int]],
    city_by_pos: dict[tuple[int, int], dict],
    capital_pos_by_kingdom: dict[int, tuple[int, int]],
    city_centroids: list[tuple[int, int]],
) -> dict:
    out: dict = {"to_water": water_dist[y][x]}
    city = city_by_pos.get((x, y))
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


def _xy(value: str) -> tuple[int, int]:
    try:
        x_str, y_str = value.split(",", 1)
        return int(x_str), int(y_str)
    except ValueError as e:
        raise argparse.ArgumentTypeError(f"expected `x,y` (e.g. `415,117`), got {value!r}") from e


# Mean (x, y) over a city's `zones` (or capital's). Used twice in `main` to compute city centroids + capital positions.
def _zone_centroid(zones: list[dict]) -> tuple[int, int]:
    n = len(zones)
    return sum(z.get("x", 0) for z in zones) // n, sum(z.get("y", 0) for z in zones) // n


def main(argv: list[str]) -> int:
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
    save = load_save()
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

    # Precompute position indices once — each lookup is O(1) per tile afterwards.
    actors_by_pos: dict[tuple[int, int], list[dict]] = defaultdict(list)
    if "actors" in sections:
        for a in save.get("actors_data", []):
            ax, ay = a.get("x"), a.get("y")
            if ax is not None and ay is not None:
                actors_by_pos[(int(ax), int(ay))].append(a)
    buildings_by_pos: dict[tuple[int, int], list[dict]] = defaultdict(list)
    if "buildings" in sections:
        for b in save.get("buildings", []):
            bx, by = b.get("mainX"), b.get("mainY")
            if bx is not None and by is not None:
                buildings_by_pos[(int(bx), int(by))].append(b)
    # `city_by_pos` shared by both `context` and `distances`; centroids + capital positions only needed by `distances`.
    city_by_pos: dict[tuple[int, int], dict] = {}
    kingdoms_by_id: dict[int, dict] = {}
    capital_pos_by_kingdom: dict[int, tuple[int, int]] = {}
    city_centroids: list[tuple[int, int]] = []
    if {"context", "distances"} & set(sections):
        kingdoms_by_id = index_by_id(save.get("kingdoms") or [])
        cities = save.get("cities") or []
        cities_by_id = index_by_id(cities)
        for c in cities:
            zones = c.get("zones") or []
            if not zones:
                continue
            city_centroids.append(_zone_centroid(zones))
            for z in zones:
                if (zx := z.get("x")) is not None and (zy := z.get("y")) is not None:
                    city_by_pos[(zx, zy)] = c
        for k in save.get("kingdoms") or []:
            cap_zones = (cities_by_id.get(k.get("capitalID")) or {}).get("zones") or []
            if cap_zones:
                capital_pos_by_kingdom[k["id"]] = _zone_centroid(cap_zones)
    tile_to_island: dict[tuple[int, int], int] = {}
    frozen_set: set[tuple[int, int]] = set()
    if "tile_info" in sections:
        _, tile_to_island = compute_islands_cached(save, CURRENT_SAVE)
        # `frozen_tiles` are packed as `y * width + x` ints. Decode once into a position set for O(1) lookup.
        for idx in save.get("frozen_tiles") or []:
            frozen_set.add((idx % width, idx // width))
    water_dist: list[list[int]] = []
    if "distances" in sections:
        layer_by_id = [tile_layer(name) for name in tile_map]
        water_dist = _build_water_distance_grid(grid, layer_by_id, width, height)

    out: dict = {}
    for x, y in coords:
        cell: dict = {}
        if "actors" in sections:
            cell["actors"] = _actors_at(x, y, actors_by_pos)
        if "buildings" in sections:
            cell["buildings"] = _buildings_at(x, y, buildings_by_pos)
        if "context" in sections:
            cell["context"] = _context_at(x, y, city_by_pos, kingdoms_by_id)
        if "distances" in sections:
            cell["distances"] = _distances_at(x, y, water_dist, city_by_pos, capital_pos_by_kingdom, city_centroids)
        if "tile_info" in sections:
            cell["tile_info"] = _tile_info_at(x, y, grid, tile_map, tile_to_island, frozen_set)
        out[f"{x},{y}"] = cell
    emit(out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
