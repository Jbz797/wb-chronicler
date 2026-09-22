#!/usr/bin/env python3

# Per-cell inspector at (x, y) with optional radius (0..2) — feeds the chronicler ad-hoc tile investigations (battle sites, neighbours, frontier scouting).
# Output: dict keyed by `"x,y"`, each value contains the requested sections for that tile.
# Coordinate convention: WB UI / actor coords; `grid[y][x]` (no inversion — y grows north and so does the row index).

import argparse
import sys
from collections import defaultdict
from collections.abc import Iterable
from functools import cache
from heapq import heapify, heappop, heappush
from itertools import compress
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))

from grid import LazyTileGrid, listed_tiles, tile_biome, tile_block, tile_elevation, tile_frost, tile_kind, tile_layer
from islands import compute_islands_cached
from shared import (
    DIAGONAL_EXTRA,
    ZONE_TILES,
    actor_xy,
    arg_parser,
    bearing,
    building_tile,
    city_centre,
    civic_building_ids,
    emit,
    entity_ref,
    index_by_id,
    load_data,
    load_save,
    parse_sections,
    take_chapter,
    walk_tiles,
    zone_xy,
)
from walking import WalkMap, walk_to

_ALL_SECTIONS = ("actors", "context", "distances", "ground", "tile_info")
_FARTHER = float("inf")  # the standing best before any land is seen, so the first tile of an island always takes its place
_LAND_REACH = 60  # past that, a tile is open sea and the nearest shore is no longer what isolates it — `to_land` gives the reach, not a number
_MAX_RADIUS = 2  # a 5×5 sweep, the most a reading can hold before the tiles drown what was being looked for
_NEAR_ISLANDS = 5  # the lands a reading names around a point: past five, the rest are the far side of the world whatever the tile
# The eight steps a tide takes, each with what it costs — a slanted one being longer than a straight one, the cheapest water is not the nearest in rings.
_WEIGHTED_DELTAS = tuple(((dx, dy), 1.0 if dx == 0 or dy == 0 else 1 + DIAGONAL_EXTRA) for dx in (-1, 0, 1) for dy in (-1, 0, 1) if dx or dy)


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


# One home for every index, each built only for the sections that asked — every building and actor in the world, for the handful of tiles queried.
# `walks`: whether anything is walked — `distances`, or a `--to` whatever the sections, its two ends being measured either way.
def _build_context(save: dict, save_path: Path, sections: set[str], coords: list[tuple[int, int]], island: int | None, walks: bool) -> dict:
    wanted = set(coords)

    # `actors_by_pos` alone takes a factory: it is the one filled per actor, where the others are assigned whole once their section asks for them.
    ctx: dict = {
        "actors_by_pos": defaultdict(list),
        "cities_by_id": {},
        "grid": {},
        "ground_by_pos": {},
        "kingdoms_by_id": {},
        "tile_map": save["tileMap"],
    }

    if "actors" in sections:
        for a in save.get("actors_data") or []:
            if (pos := actor_xy(a)) in wanted:
                ctx["actors_by_pos"][pos].append(a)

    if "ground" in sections:
        ctx["categories"], ctx["civic"] = load_data("building-categories.json"), civic_building_ids()
        for b in save.get("buildings") or []:
            # The bare tuple sifts the whole world first and the helper reads only what lands in the window — both take WB's omitted coordinate as 0.
            if (b.get("mainX", 0), b.get("mainY", 0)) in wanted and (pos := building_tile(b)) is not None:
                ctx["ground_by_pos"][pos] = b

    if {"actors", "context", "distances"} & sections:  # the two id maps resolve refs for `actors` as well as `context`
        ctx["cities_by_id"] = index_by_id(save.get("cities") or [])
        ctx["kingdoms_by_id"] = index_by_id(save.get("kingdoms") or [])

    if {"distances", "tile_info"} & sections:
        ctx["grid"] = LazyTileGrid(save)

    if {"context", "distances"} & sections:
        _index_cities(ctx, {(x // ZONE_TILES, y // ZONE_TILES) for x, y in coords})

    if walks or "tile_info" in sections:  # `distances` needs it too, to say how far a rock lies from a land a city could hold, and a walk what land it keeps to
        islands, ctx["tile_to_island"] = compute_islands_cached(save, save_path)
        ctx["island"], ctx["island_ids"] = island, {land["id"] for land in islands}

    if "tile_info" in sections:
        ctx["burning_set"] = wanted.intersection(listed_tiles(save, "fire"))
        ctx["frozen_set"] = wanted.intersection(listed_tiles(save, "frozen_tiles"))

    if "distances" in sections:
        ctx["layer_by_id"] = [tile_layer(name) for name in ctx["tile_map"]]

    if walks:  # called not stored: a walk is drawn only where both ends stand on one land
        ctx["walk_map"], ctx["width"] = cache(lambda: WalkMap(save)), sum(save["tileAmounts"][0])

    return ctx


# WB claims land by the zone, never by the tile — so a tile's town is its zone's, and both sections that ask read it the one way.
def _city_at(x: int, y: int, ctx: dict) -> dict | None:
    return ctx["city_by_pos"].get((x // ZONE_TILES, y // ZONE_TILES))


# `{}` on unclaimed ground, which `emit` strips from the cell.
def _context_at(x: int, y: int, ctx: dict) -> dict:
    city = _city_at(x, y, ctx)
    if city is None:
        return {}
    return {"city": {"id": city["id"], "name": city.get("name")}, "kingdom": entity_ref(city.get("kingdomID"), ctx["kingdoms_by_id"])}


# Every reading counts steps, WB walking its eight directions — and the whole section answers for the queried tile, a neighbour two steps over reading the same.
def _distances_at(x: int, y: int, ctx: dict) -> dict:
    out: dict = {"to_water": _water_distance(x, y, ctx["grid"], ctx["layer_by_id"])}
    if (land := _land_distance(x, y, ctx)) is not None:
        out["to_land"] = land
    city = _city_at(x, y, ctx)
    if city is None:
        if quarters := ctx["city_quarters"]:  # a quarter lies whole on the map, WB sizing a world in blocks its zones divide
            width, span = ctx["width"], range(ZONE_TILES)
            fabric = ((qy + dy) * width + qx + dx for qx, qy in quarters for dy in span for dx in span)
            out["to_nearest_city"] = _measure(x, y, _fabric_distance(x, y, quarters), fabric, ctx)
    elif (kid := city.get("kingdomID")) and (seat := ctx["capital_pos_by_kingdom"].get(kid)) is not None:
        # A seat is a point, where a town is a fabric — the throne, not the capital's last house.
        out["to_capital"] = _measure(x, y, round(walk_tiles(x - seat[0], y - seat[1])), (seat[1] * ctx["width"] + seat[0],), ctx)
    lands = _island_distances(x, y, ctx)
    if ranked := sorted(lands.items(), key=lambda item: (item[1], item[0]))[:_NEAR_ISLANDS]:
        out["to_islands"] = {str(island): round(tiles) for island, tiles in ranked}  # nearest first, an order `render` keeps by way of `_VALUE_ORDERED`
    if (wanted := ctx["island"]) is not None:  # a named land, however far down the list: the tile's own reads 0, it stands on it
        out["to_island"] = {str(wanted): round(lands.get(wanted, 0))}
    return out


# A town is its fabric, not its centre, as `to_land` takes a shore: at the edge of a sprawling town a body stands at the gate, not a centre away.
def _fabric_distance(x: int, y: int, quarters: list[tuple[int, int]]) -> int:
    return round(min(walk_tiles(max(qx - x, x - qx - ZONE_TILES + 1, 0), max(qy - y, y - qy - ZONE_TILES + 1, 0)) for qx, qy in quarters))


# One object per tile, never two. WB's `buildings` collection holds the flowers and the ore too, hence the family, named as `geography` names them.
def _ground_at(x: int, y: int, ctx: dict) -> dict:
    if (b := ctx["ground_by_pos"].get((x, y))) is None:
        return {}
    asset = b.get("asset_id")
    return {"asset_id": asset, "id": b.get("id"), "type": "buildings" if asset in ctx["civic"] else ctx["categories"].get(asset) or "other"}


# Quarters are held by their corner tile, a town being the ground they cover — while a crown's seat stays the one centre `city/info.py` sites a capital by.
def _index_cities(ctx: dict, wanted_zones: set[tuple[int, int]]) -> None:
    anchors: dict[int, tuple[int, int]] = {}
    ctx["capital_pos_by_kingdom"] = {}
    ctx["city_by_pos"] = {}
    ctx["city_quarters"] = []

    for city in ctx["cities_by_id"].values():
        if (anchor := city_centre(city)) is None:  # a city holding no zone stands nowhere: nothing to site it by, nothing to measure towards
            continue
        anchors[city["id"]] = anchor
        for zone in city["zones"]:
            zx, zy = zone_xy(zone)
            ctx["city_quarters"].append((zx * ZONE_TILES, zy * ZONE_TILES))
            if (zx, zy) in wanted_zones:
                ctx["city_by_pos"][(zx, zy)] = city

    for kingdom in ctx["kingdoms_by_id"].values():
        if (seat := anchors.get(kingdom.get("capitalID"))) is not None:
            ctx["capital_pos_by_kingdom"][kingdom["id"]] = seat


# Every land by its nearest tile, walked as `to_land` measures — read at a queried tile alone.
def _island_distances(cx: int, cy: int, ctx: dict) -> dict[int, float]:
    own = ctx["tile_to_island"].get((cx, cy))
    nearest: dict[int, float] = {}
    for x, y, island in ctx["tile_to_island"].edges():  # a land's nearest tile lies on its edge, so the rest is never walked
        if island == own:  # its own shore is where it stands, and `tile_info` already names that land
            continue
        ax, ay = abs(x - cx), abs(y - cy)
        far, near = (ax, ay) if ax > ay else (ay, ax)
        # The octile never falls under the wider leg, so a tile losing on that leg alone is dropped before the multiply — the world's land, bar a handful.
        if (best := nearest.get(island, _FARTHER)) <= far:
            continue
        if (tiles := far + DIAGONAL_EXTRA * near) < best:
            nearest[island] = tiles
    return nearest


# How far the tile's rock lies from a land a city could hold, and which one — measured whole, a castaway being isolated by his island's strait, not his footing.
def _land_distance(x: int, y: int, ctx: dict) -> dict | None:
    island_at, grid, layer = ctx["tile_to_island"].get, ctx["grid"], ctx["layer_by_id"]
    height, width = grid.height, grid.width
    if island_at((x, y)) is not None:
        return None

    # Afloat the source is the tile alone, so the search grows by square rings — whose tiles cost `r` to `r√2`, hence the sweep carried past the first land seen.
    if layer[grid[y][x]] == "Ocean":
        found: tuple[float, int] | None = None
        for r in range(_LAND_REACH + 1):
            if found is not None and r >= found[0]:
                break
            for nx, ny in _ring_tiles(x, y, r, width, height):
                if (island := island_at((nx, ny))) is not None and (swum := walk_tiles(nx - x, ny - y)) < (found[0] if found else swum + 1):
                    found = (swum, island)
        return {"island_id": found[1], "tiles": round(found[0])} if found else {"farther_than": _LAND_REACH}

    def dry(px: int, py: int) -> bool:  # the uncounted rock and nothing else — take the sea in and the fill would run to the map's end
        return layer[grid[py][px]] != "Ocean" and island_at((px, py)) is None

    seen, stack = {(x, y)}, [(x, y)]  # a rock carries the wave whole: its far shore may reach a land its near one never would
    while stack:
        cx, cy = stack.pop()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = cx + dx, cy + dy
            if 0 <= nx < width and 0 <= ny < height and (nx, ny) not in seen and dry(nx, ny):
                seen.add((nx, ny))
                stack.append((nx, ny))
    # One tide off the whole rock rather than a ring per tile, and the cheapest water always taken first: a slanted stretch costs more than a straight one.
    swum = dict.fromkeys(seen, 0.0)
    tide = [(0.0, tile) for tile in seen]
    heapify(tide)
    while tide:
        here, tile = heappop(tide)
        if here > _LAND_REACH:
            break
        if here > swum[tile]:
            continue
        if (island := island_at(tile)) is not None:
            return {"island_id": island, "tiles": round(here)}
        cx, cy = tile
        for (dx, dy), cost in _WEIGHTED_DELTAS:
            nx, ny = cx + dx, cy + dy
            if 0 <= nx < width and 0 <= ny < height and (reached := here + cost) < swum.get((nx, ny), reached + 1):
                swum[(nx, ny)] = reached
                heappush(tide, (reached, (nx, ny)))
    return {"farther_than": _LAND_REACH}


# The crow's line beside the walk, left out where no land joins them — `goals` are tile indices, read from a land alone and sifted to it: WB walks none off its own.
def _measure(x: int, y: int, tiles: int, goals: Iterable[int], ctx: dict) -> dict:
    island_of = ctx["tile_to_island"]
    if (land := island_of.get((x, y))) is None or not (ends := set(compress(goals := list(goals), map(land.__eq__, island_of.listed_ids(goals))))):
        return {"tiles": tiles}
    walk_map = ctx["walk_map"]()
    # A body no ground is home to, and that never swims: which body would, no tile says.
    walked = walk_to(walk_map, walk_map.gait(None, frozenset()), x, y, ends)
    return {"tiles": tiles} if walked is None else {"tiles": tiles, "walked": round(walked)}


def _radius_tiles(cx: int, cy: int, radius: int, width: int, height: int) -> list[tuple[int, int]]:
    return [(x, y) for dy in range(-radius, radius + 1) for dx in range(-radius, radius + 1) if 0 <= (x := cx + dx) < width and 0 <= (y := cy + dy) < height]


# The square ring at Chebyshev radius `r` around a tile, clipped to the map — the shape an 8-way search grows by, whatever it then costs a body to walk.
def _ring_tiles(x: int, y: int, r: int, width: int, height: int):
    x0, x1, y0, y1 = x - r, x + r, y - r, y + r
    for nx in range(max(0, x0), min(width - 1, x1) + 1):  # the two horizontal sides, corners included
        for ny in {y0, y1}:
            if 0 <= ny < height:
                yield nx, ny
    for ny in range(max(0, y0 + 1), min(height - 1, y1 - 1) + 1):  # and the two vertical ones, corners already walked
        for nx in {x0, x1}:
            if 0 <= nx < width:
                yield nx, ny


# `block`, `burning`, `frozen` (passing frost), `islet` (land too small to count: without it and `island_id`, water) and `snow` or `ice` only where they hold.
def _tile_info_at(x: int, y: int, ctx: dict) -> dict:
    name = ctx["tile_map"][ctx["grid"][y][x]]
    out: dict = {"biome": tile_biome(name), "elevation": tile_elevation(name), "island_id": ctx["tile_to_island"].get((x, y)), "kind": tile_kind(name)}
    if (x, y) in ctx["burning_set"]:
        out["burning"] = True
    if (x, y) in ctx["frozen_set"]:
        out["frozen"] = True
    if frost := tile_frost(name):
        out[frost] = True
    if block := tile_block(name):
        out["block"] = block
    if out["island_id"] is None and tile_layer(name) in ("Block", "Ground", "Lava"):
        out["islet"] = True
    return out


# Rings widen until the sea is met, every cell walkable — a coastal tile ends in two or three, where a BFS would carry a front. `-1` where no water is found.
def _water_distance(x: int, y: int, grid: LazyTileGrid, layer_by_id: list[str]) -> int:
    height, width, best = grid.height, grid.width, None
    # A ring holds tiles worth `r` walked to `r * √2`, so the first water met may still be beaten one ring out — the search stops once no ring left can.
    for r in range(max(width, height)):
        if best is not None and r >= best:
            break
        for nx, ny in _ring_tiles(x, y, r, width, height):
            if layer_by_id[grid[ny][nx]] == "Ocean" and (walked := walk_tiles(nx - x, ny - y)) < (best if best is not None else walked + 1):
                best = walked
    return round(best) if best is not None else -1


# argparse type converter — raising `ArgumentTypeError` is what makes it print the usage line rather than a traceback.
def _xy(value: str) -> tuple[int, int]:
    try:
        x_str, y_str = value.split(",", 1)
        return int(x_str), int(y_str)
    except ValueError as e:
        raise argparse.ArgumentTypeError(f"expected `x,y` (e.g. `415,117`), got {value!r}") from e


def main(argv: list[str]) -> int:
    save_path, argv, _ = take_chapter(argv)  # pop the `C<n>` token first — argparse has no such positional and would abort on it

    parser = arg_parser(prog="tiles/info.py", description="Inspect tile(s) at (x, y) with optional radius. Output is keyed by `'x,y'`.")
    parser.add_argument("xy", type=_xy, metavar="x,y", help="Tile coords (WB UI, y grows north), comma-separated — e.g. `415,117`.")
    parser.add_argument("sections", nargs="?", help=f"Comma-separated sections or `full` (default) — a lone `--to` answers alone. Valid: {', '.join(_ALL_SECTIONS)}")
    parser.add_argument("--island", "-i", type=int, metavar="id", help="A land by id, measured in `distances` as `to_islands` is — one past the nearest five.")
    parser.add_argument("--radius", "-r", type=int, default=0, choices=range(_MAX_RADIUS + 1), help=f"Radius around (x, y) — 0..{_MAX_RADIUS} (default 0).")
    parser.add_argument("--to", type=_xy, metavar="x,y", help="A second tile and a `to` key, the walk from the first to it — the tiles too once sections are named.")
    args = parser.parse_args(argv)
    cx, cy = args.xy

    try:
        # Membership only, never walked in order — the emitting `if`s below name each one. A `--to` alone answers alone, as `actor`'s does: the way, not the tiles.
        sections = set(parse_sections(args.sections or "full", _ALL_SECTIONS)) if args.sections or not args.to else set()
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 2

    if args.to and args.radius:  # refused before the save is read: a call that cannot be answered should not cost the load
        print("✗ `--to` reads two tiles and `--radius` a square around one: they don't combine", file=sys.stderr)
        return 2
    if args.island is not None and "distances" not in sections:
        print("✗ `--island` answers in `distances`: name that section, or `full`", file=sys.stderr)
        return 2

    save = load_save(save_path)

    # The grid ships run-length encoded, so its shape reads off the header — no need to decode the whole map to bounds-check the query.
    height = len(save.get("tileArray") or [])
    width = sum((save.get("tileAmounts") or [[]])[0])

    if not (height and width):
        print("✗ empty grid", file=sys.stderr)
        return 2

    for x, y in ((cx, cy), args.to or (cx, cy)):
        if not (0 <= x < width and 0 <= y < height):
            print(f"✗ coords ({x}, {y}) out of bounds — map is {width}×{height}", file=sys.stderr)
            return 2

    coords = [(cx, cy), args.to] if args.to else _radius_tiles(cx, cy, args.radius, width, height)
    queried = set(coords) if args.to else {(cx, cy)}  # the tiles a reading is about: both ends of a `--to`, the centre of a sweep
    ctx = _build_context(save, save_path, sections, coords, args.island, "distances" in sections or args.to is not None)
    if args.island is not None and args.island not in ctx["island_ids"]:
        print(f"✗ no land with id {args.island} — `geography … islands` lists them", file=sys.stderr)
        return 2

    out: dict = {}
    for x, y in coords if sections else ():
        cell: dict = {}
        if "actors" in sections:
            cell["actors"] = _actors_at(x, y, ctx)
        if "context" in sections:
            cell["context"] = _context_at(x, y, ctx)
        if "distances" in sections and (x, y) in queried:  # what a sweep's neighbours would repeat to the tile, said once for the tile asked about
            cell["distances"] = _distances_at(x, y, ctx)
        if "ground" in sections:
            cell["ground"] = _ground_at(x, y, ctx)
        if "tile_info" in sections:
            cell["tile_info"] = _tile_info_at(x, y, ctx)
        out[f"{x},{y}"] = cell
    if args.to:  # a relation between the two ends, not a trait of either: its own key, the cap read from the first toward the second
        tx, ty = args.to
        out["to"] = {"dir": bearing(tx - cx, ty - cy), **_measure(cx, cy, round(walk_tiles(tx - cx, ty - cy)), (ty * width + tx,), ctx)}

    emit(out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
