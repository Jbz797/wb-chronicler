#!/usr/bin/env python3

# Per-cell inspector at (x, y) with optional radius (0..2) — feeds the chronicler ad-hoc tile investigations (battle sites, neighbours, frontier scouting).
# Output: dict keyed by `"x,y"`, each value contains the requested sections for that tile.
# Coordinate convention: WB UI / actor coords; `grid[y][x]` (no inversion — y grows north and so does the row index).

import math
import re
import sys
from collections import Counter, defaultdict
from functools import cache
from heapq import heapify, heappop, heappush
from itertools import compress
from pathlib import Path
lazy from collections.abc import Callable, Iterable, Iterator

sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))

from grid import BARE, LazyTileGrid, listed_tiles, off_land, patch_finder, tile_biome, tile_block, tile_elevation, tile_frost, tile_ground, tile_kind, tile_layer
from islands import compute_islands_cached, islet_heart
from places import PlaceError, named_place, place_centre
from shared import (
    DIAGONAL_EXTRA,
    ZONE_TILES,
    absent_entity,
    actor_xy,
    arg_parser,
    bearing,
    body_ref,
    building_family,
    building_footprint,
    building_tile,
    chunks_apart,
    city_centre,
    emit,
    entity_born,
    entity_ref,
    gazetteer,
    index_by_id,
    is_boat,
    land_side,
    load_save,
    parse_sections,
    place_point,
    take_chapter,
    under_construction,
    walk_tiles,
    water_arg,
    xy_arg,
    zone_xy,
)
from walking import WalkMap, walk_way, walled_in
from waters import water_bodies, waters_cached

_ALL_SECTIONS = ("actors", "context", "distances", "ground", "islet", "tile_info")
_AXES = ("E–W", "NE–SW", "N–S", "NW–SE")  # the four lines a shape can lie along, every 45° from east, `y` growing north
_BARE = {"actors": "no body", "ground": "nothing built or grown"}  # what a tile lacks, said when `actors` or `ground` is all the call asked
_BRUTE_PAIRS = 20_000  # tile pairs two grounds are weighed by one by one: a building and a body, never a land and a lake
_BURNING = "burning"  # what `-g` takes for the fires, no ground: `geography … burning` names them so
_FARTHER = float("inf")  # the standing best before any land is seen, so the first tile of an island always takes its place
_LAND_REACH = 60  # past that, a tile is open sea and the nearest shore is no longer what isolates it — `strait_to_land` gives the reach, not a number
_LONG_SHAPE = 1.5  # length over breadth from which a shape lies along a line: rounder, it lies along none
_MAX_RADIUS = 2  # a 5×5 sweep, the most a reading can hold before the tiles drown what was being looked for
_NEAR_ISLANDS = 5  # the lands a reading names around a point: past five, the rest are the far side of the world whatever the tile
_PAIR_CELL = 16  # the side of the cells a large ground is hashed into for `_closest_pair`, a chunk's
_REFERENCE_SPEED = 10  # chronicler.md § Échelle's walker: a tile has no body, so its way is the one the scale's pace would take, never timed
_SPREAD = re.compile(r"i\d+|(?:lake|river|sea)\d+|box")  # what a place aimed at spreads over, edge and middle apart: a land, a water, a box

# The eight steps a tide takes, each with its length — a slanted one being longer than a straight one, the least water is not the nearest in rings.
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
        for b in save.get("buildings") or []:
            # The bare tuple sifts the whole world first and the helper reads only what lands in the window — both take WB's omitted coordinate as 0.
            if (b.get("mainX", 0), b.get("mainY", 0)) in wanted and (pos := building_tile(b)) is not None:
                ctx["ground_by_pos"][pos] = b

    if {"actors", "context", "distances"} & sections:  # the two id maps resolve refs for `actors` as well as `context`
        ctx["cities_by_id"] = index_by_id(save.get("cities") or [])
        ctx["kingdoms_by_id"] = index_by_id(save.get("kingdoms") or [])

    if {"distances", "islet", "tile_info"} & sections:
        ctx["grid"] = LazyTileGrid(save)

    if {"context", "distances"} & sections:
        _index_cities(ctx, {(x // ZONE_TILES, y // ZONE_TILES) for x, y in coords})

    # `distances` needs it too, to say how far a rock lies from a land a city could hold, and a walk what land it keeps to
    if walks or {"islet", "tile_info"} & sections:
        islands, ctx["tile_to_island"] = compute_islands_cached(save, save_path)
        ctx["island"], ctx["lands"] = island, {land["id"]: land for land in islands}

    if "tile_info" in sections:
        ctx["burning_set"] = wanted.intersection(listed_tiles(save, "fire"))
        ctx["frozen_set"] = wanted.intersection(listed_tiles(save, "frozen_tiles"))
        ctx["patch_at"] = patch_finder(save, ctx["grid"], ctx["tile_to_island"])

    if {"distances", "tile_info"} & sections:
        ctx["water_body"] = cache(lambda: water_bodies(save, save_path))  # called not stored: a tile on dry land never asks what water it lies in

    if "distances" in sections:
        ctx["layer_by_id"] = [tile_layer(name) for name in ctx["tile_map"]]

    if walks:  # called not stored: a walk is drawn only where both ends stand on one land
        ctx["walk_map"], ctx["width"] = cache(lambda: WalkMap(save)), sum(save["tileAmounts"][0])

    return ctx


# WB claims land by the zone, never by the tile — so a tile's town is its zone's, and both sections that ask read it the one way.
def _city_at(x: int, y: int, ctx: dict) -> dict | None:
    return ctx["city_by_pos"].get((x // ZONE_TILES, y // ZONE_TILES))


# The crow's nearest pair between two grounds, their rims alone: past `_BRUTE_PAIRS`, the larger hashed by `_PAIR_CELL`, searched ring by ring from the smaller.
def _closest_pair(first: list[tuple[int, int]], second: list[tuple[int, int]]) -> tuple[tuple[int, int], tuple[int, int]]:
    if shared := set(first) & set(second):
        return (tile := min(shared)), tile
    first, second = _rim(first), _rim(second)
    if len(first) * len(second) <= _BRUTE_PAIRS:
        return min(((a, b) for a in first for b in second), key=lambda ends: walk_tiles(ends[1][0] - ends[0][0], ends[1][1] - ends[0][1]))
    flip = len(first) > len(second)
    small, large = (second, first) if flip else (first, second)
    cells: defaultdict[tuple[int, int], list[tuple[int, int]]] = defaultdict(list)
    for x, y in large:
        cells[x // _PAIR_CELL, y // _PAIR_CELL].append((x, y))
    wide, high = (max(tile[axis] for tile in (*small, *large)) // _PAIR_CELL + 1 for axis in (0, 1))
    best, pair = math.inf, (small[0], large[0])
    for sx, sy in small:
        for r in range(max(wide, high)):
            if (r - 1) * _PAIR_CELL >= best:  # a cell r rings off holds no tile nearer than its inner edge: none can beat the best past it
                break
            for gx, gy in _ring_tiles(sx // _PAIR_CELL, sy // _PAIR_CELL, r, wide, high):
                for tx, ty in cells.get((gx, gy), ()):
                    if (crow := walk_tiles(tx - sx, ty - sy)) < best:
                        best, pair = crow, ((sx, sy), (tx, ty))
    return (pair[1], pair[0]) if flip else pair


# `{}` on unclaimed ground, which `emit` strips from the cell.
def _context_at(x: int, y: int, ctx: dict) -> dict:
    city = _city_at(x, y, ctx)
    if city is None:
        return {}
    return {"city": {"id": city["id"], "name": city.get("name")}, "kingdom": entity_ref(city.get("kingdomID"), ctx["kingdoms_by_id"])}


# Every reading counts steps, WB walking its eight directions — and the whole section answers for the queried tile, a neighbour two steps over reading the same.
def _distances_at(x: int, y: int, ctx: dict) -> dict:
    out: dict = {"to_water": _nearest_water(x, y, ctx)}
    if (land := _land_distance(x, y, ctx)) is not None:
        # A land owns its rock: a pocket of ground that rock shuts in touches the land with no water between, and a strait there would read as a way out.
        walk_map = ctx["walk_map"]()
        shut = "island_id" in land and not walk_map.wet(x, y) and walled_in(walk_map, walk_map.gait(_REFERENCE_SPEED, frozenset()), x, y)
        out |= {"walled_in": {"island_id": land["island_id"]}} if shut else {"strait_to_land": land}
    city = _city_at(x, y, ctx)
    if city is None:
        if towns := ctx["city_quarters"]:  # a quarter lies whole on the map, WB sizing a world in blocks its zones divide
            reach = {cid: _fabric_distance(x, y, quarters) for cid, quarters in towns.items()}
            near = min(reach, key=lambda cid: (reach[cid], cid))
            (cx, cy), width, span = ctx["city_centres"][near], ctx["width"], range(ZONE_TILES)
            fabric = ((qy + dy) * width + qx + dx for qx, qy in towns[near] for dy in span for dx in span)
            # The nearest town is the one whose ground comes first, and both ends of it are told: its `edge`, where a body stands at the gate, and its `centre`.
            out["to_nearest_city"] = {
                "centre": _measure(x, y, round(walk_tiles(x - cx, y - cy)), (cy * width + cx,), ctx),
                "city": entity_ref(near, ctx["cities_by_id"]),
                "edge": _measure(x, y, reach[near], fabric, ctx),
            }
    elif (kid := city.get("kingdomID")) and (seat := ctx["capital_pos_by_kingdom"].get(kid)) is not None:
        # A seat is a point, where a town is a fabric — the throne, not the capital's last house.
        out["to_capital"] = _measure(x, y, round(walk_tiles(x - seat[0], y - seat[1])), (seat[1] * ctx["width"] + seat[0],), ctx)
    lands = _island_distances(x, y, ctx)
    out |= _nearest_lands(lands)
    if (wanted := ctx["island"]) is not None:  # a named land, however far down the list: the tile's own reads 0, it stands on it
        out["to_island"] = {str(wanted): round(lands.get(wanted, 0))}
    if (water := ctx.get("aimed_water")) is not None:  # one water's shore, where `to_water` takes the nearest of all — a lake two rivers further off
        grid, layer_by_id, body = ctx["grid"], ctx["layer_by_id"], ctx["water_body"]()
        out["to_body"] = {**water, **(_nearest(x, y, ctx, lambda nx, ny: layer_by_id[grid[ny][nx]] == "Ocean" and body(nx, ny) == water) or {})}
    if (ground := ctx.get("aimed_ground")) is not None:  # a ground's nearest tile — the rock at a range's foot, a biome's edge, a fire's nearest flame
        grid, grounds, fires = ctx["grid"], ctx.get("ground_by_id", ()), ctx.get("fire_tiles", frozenset())
        hit = (lambda nx, ny: (nx, ny) in fires) if ground == _BURNING else (lambda nx, ny: grounds[grid[ny][nx]] == ground)
        out["to_ground"] = {"ground": ground, **(_nearest(x, y, ctx, hit) or {})}
    return out


# An end of `tiles`: a building `b<id>`, a town `c<id>`, a body `p<id>` or a name of `places.json`, kept as written till the save sites it; else a tile `x,y`.
def _end_arg(value: str) -> str | tuple[int, int]:
    return xy_arg(value) if body_ref(value) is None and re.fullmatch(r"-?\d+,-?\d+", value) else value


# A town is its fabric, not its centre, as `to_islands` takes a land's nearest tile: at the edge of a sprawling town a body stands at the gate, not a centre away.
def _fabric_distance(x: int, y: int, quarters: list[tuple[int, int]]) -> int:
    return round(min(walk_tiles(max(qx - x, x - qx - ZONE_TILES + 1, 0), max(qy - y, y - qy - ZONE_TILES + 1, 0)) for qx, qy in quarters))


# The tiles a named end stands on — a building's whole ground, a town's centre, a body's tile, a place's own as `actor … --to` reads it — and what a place
# aimed at, or the refusal that tells why it has none.
def _ground(end: str, save: dict, save_path: Path, chapter: str | None) -> tuple[list[tuple[int, int]], str | None] | str:
    if not re.fullmatch(r"[bcp]\d+", end):
        try:
            found = named_place(end, save, save_path, compute_islands_cached(save, save_path)[1], WalkMap(save))
        except PlaceError as e:
            return str(e)
        return found or f"✗ `{end}` is no end — a tile `x,y`, a building `b<id>`, a town `c<id>`, a body `p<id>` or a name of places.json"
    kind, ref = end[0], int(end[1:])
    if kind == "b":
        site = next((b for b in save.get("buildings") or [] if b.get("id") == ref), None)
        return (site and (building_footprint(site), None)) or absent_entity("ground", "buildings", ref, chapter, noun="building")
    if kind == "c":
        city = next((c for c in save.get("cities") or [] if c.get("id") == ref), None)
        return ([centre], None) if city and (centre := city_centre(city)) else absent_entity("city", "cities", ref, chapter)
    body = next((a for a in save.get("actors_data") or [] if a.get("id") == ref and not is_boat(a)), None)
    return ([actor_xy(body)], None) if body else absent_entity("actor", "actors_data", ref, chapter, lambda a: not is_boat(a))


# One object per tile, never two — WB's `buildings` holds the flowers and the ore too, hence the family; `dated` for the tile asked about, a sweep's rows kept short.
def _ground_at(x: int, y: int, ctx: dict, dated: bool) -> dict:
    if (b := ctx["ground_by_pos"].get((x, y))) is None:
        return {}
    asset = b.get("asset_id")
    family = building_family(asset)  # named as `geography` names them
    # `born` dates the laying, not the roof: a site still rising says so, on the tile asked about as on a sweep's.
    return {"asset_id": asset, **({"born": entity_born(b)} if dated else {}), "id": b.get("id"), "type": family, "under_construction": under_construction(b) or None}


# Quarters are held by their corner tile, a town being the ground they cover — while a crown's seat stays the one centre `city/info.py` sites a capital by.
def _index_cities(ctx: dict, wanted_zones: set[tuple[int, int]]) -> None:
    anchors: dict[int, tuple[int, int]] = {}
    ctx["capital_pos_by_kingdom"] = {}
    ctx["city_by_pos"] = {}
    ctx["city_centres"] = anchors
    ctx["city_quarters"] = {}

    for city in ctx["cities_by_id"].values():
        if (anchor := city_centre(city)) is None:  # a city holding no zone stands nowhere: nothing to site it by, nothing to measure towards
            continue
        anchors[city["id"]] = anchor
        for zone in city["zones"]:
            zx, zy = zone_xy(zone)
            ctx["city_quarters"].setdefault(city["id"], []).append((zx * ZONE_TILES, zy * ZONE_TILES))
            if (zx, zy) in wanted_zones:
                ctx["city_by_pos"][(zx, zy)] = city

    for kingdom in ctx["kingdoms_by_id"].values():
        if (seat := anchors.get(kingdom.get("capitalID"))) is not None:
            ctx["capital_pos_by_kingdom"][kingdom["id"]] = seat


# Every land by its nearest tile, as the crow flies — read at a queried tile alone.
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


# The islet whole, told as `geography … islands` tells a land, plus biomes, lie and lands from its nearest shore — a far one may stand a kilometre nearer.
def _islet_at(x: int, y: int, ctx: dict) -> dict:
    if not (tiles := ctx["tile_to_island"].islet_tiles((x, y))):
        return {}
    grid, tile_map, own = ctx["grid"], ctx["tile_map"], set(tiles)
    names = [tile_map[grid[ty][tx]] for tx, ty in tiles]
    kinds, biomes = Counter(map(tile_kind, names)), Counter(filter(None, map(tile_biome, names)))
    xs, ys = [tx for tx, _ in tiles], [ty for _, ty in tiles]
    mean_x, mean_y = sum(xs) / len(tiles), sum(ys) / len(tiles)
    cx, cy = islet_heart(tiles) or (x, y)
    out = {
        "biomes": _shares(biomes, sum(biomes.values())),
        "bounds": {"x": [min(xs), max(xs)], "y": [min(ys), max(ys)]},
        "ground": _shares(kinds, len(tiles)),
        "heart": {"x": cx, "y": cy},
        # The forged place whose point stands on it: an islet the chronicler named, as `actor … metadata`'s `place` names it
        "name": next((name for name, spot in (gazetteer().get("places") or {}).items() if place_point(spot) in own), None),
        "size": len(tiles),  # the rock whole, as a land's counts its own — the islets it touches in, where `islet_tiles` weighs one mass's ground
        **_lie(tiles, mean_x, mean_y),
    }
    shore = [(tx, ty) for tx, ty in tiles if any((tx + dx, ty + dy) not in own for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))]
    west, east, south, north = out["bounds"]["x"] + out["bounds"]["y"]
    nearest: dict[int, float] = {}
    for ex, ey, island in ctx["tile_to_island"].edges():
        # The islet's box never lies farther than the islet, so a land tile the box already sets past the standing best is dropped before the shore is walked.
        if walk_tiles(max(west - ex, ex - east, 0), max(south - ey, ey - north, 0)) >= nearest.get(island, _FARTHER):
            continue
        if (tiles_to := min(walk_tiles(ex - sx, ey - sy) for sx, sy in shore)) < nearest.get(island, _FARTHER):
            nearest[island] = tiles_to
    # The land it lies off, and on which side of it: past `_LAND_REACH`, open sea, an islet off no shore.
    land = min(nearest, key=lambda island: (nearest[island], island), default=None)
    if land is not None and nearest[land] <= _LAND_REACH:
        out["off"] = {"island_id": land, "side": land_side(cx, cy, ctx["lands"][land])}
    return out | _nearest_lands(nearest)


# The water cutting the tile's rock off a land a city could hold, and which: from the whole rock, swum as `swim_tiles` counts it, dry rock on the way free.
def _land_distance(x: int, y: int, ctx: dict) -> dict | None:
    island_at, grid, layer = ctx["tile_to_island"].get, ctx["grid"], ctx["layer_by_id"]
    height, width = grid.height, grid.width
    if island_at((x, y)) is not None:
        return None

    def wet(px: int, py: int) -> bool:
        return layer[grid[py][px]] == "Ocean"

    # Afloat the tile alone; on a rock the rock whole, whose far shore may reach a land its near one never would.
    seen, stack = {(x, y)}, [] if wet(x, y) else [(x, y)]
    while stack:
        cx, cy = stack.pop()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = cx + dx, cy + dy
            if 0 <= nx < width and 0 <= ny < height and (nx, ny) not in seen and not wet(nx, ny) and island_at((nx, ny)) is None:
                seen.add((nx, ny))
                stack.append((nx, ny))
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
            return {"island_id": island, "swim_tiles": max(round(here), 1)}  # afloat by a shore, the half step off his own tile still swum
        cx, cy = tile
        here_wet = wet(cx, cy)
        for (dx, dy), length in _WEIGHTED_DELTAS:
            nx, ny = cx + dx, cy + dy
            if 0 <= nx < width and 0 <= ny < height:
                reached = here + length * (here_wet + wet(nx, ny)) / 2
                if reached < swum.get((nx, ny), reached + 1):
                    swum[(nx, ny)] = reached
                    heappush(tide, (reached, (nx, ny)))
    return {"farther_than": _LAND_REACH}


# The line a shape lies along and its length by breadth, off its tiles' spread: `lie` said only past `_LONG_SHAPE`, a round rock lying along none.
def _lie(tiles: list[tuple[int, int]], mean_x: float, mean_y: float) -> dict:
    sxx = sum((tx - mean_x) ** 2 for tx, _ in tiles)
    syy = sum((ty - mean_y) ** 2 for _, ty in tiles)
    sxy = sum((tx - mean_x) * (ty - mean_y) for tx, ty in tiles)
    angle = 0.5 * math.atan2(2 * sxy, sxx - syy)
    cos, sin = math.cos(angle), math.sin(angle)
    along = [(tx - mean_x) * cos + (ty - mean_y) * sin for tx, ty in tiles]
    across = [(ty - mean_y) * cos - (tx - mean_x) * sin for tx, ty in tiles]
    long, wide = round(max(along) - min(along)) + 1, round(max(across) - min(across)) + 1
    out: dict = {"span_tiles": [long, wide]}
    if long >= _LONG_SHAPE * wide:
        out["lie"] = _AXES[round(math.degrees(angle) / 45) % 4]
    return out


# The crow's line beside the walk the reference pace takes, left out where no land joins them — `goals` are tile indices, read from a land alone.
def _measure(x: int, y: int, tiles: int, goals: Iterable[int], ctx: dict) -> dict:
    island_of = ctx["tile_to_island"]
    if (land := island_of.get((x, y))) is None or not (ends := set(compress(goals := list(goals), map(land.__eq__, island_of.listed_ids(goals))))):
        return {"crow_tiles": tiles}
    walk_map = ctx["walk_map"]()
    # A body no ground is home to, and that never swims: which body would, no tile says. A `speed` 10 picks the way, slowed by sand as any; no time comes out.
    if (way := walk_way(walk_map, walk_map.gait(_REFERENCE_SPEED, frozenset()), x, y, ends)) is None:
        return {"crow_tiles": tiles}
    return {"crow_tiles": tiles, "walk_tiles": round(way[3])}


# The lands nearest first, `_NEAR_ISLANDS` of them named — an order `render` keeps by way of `_VALUE_ORDERED` — and the cut said with its size, as `waters`
# tells the lakes it leaves out.
def _nearest_lands(nearest: dict[int, float]) -> dict:
    ranked, out = sorted(nearest.items(), key=lambda item: (item[1], item[0])), {}
    if near := ranked[:_NEAR_ISLANDS]:
        out["to_islands"] = {str(island): round(tiles) for island, tiles in near}
    if far := ranked[_NEAR_ISLANDS:]:
        out["unlisted"] = {"islands": {"count": len(far), "nearest": round(far[0][1])}}
    return out


# Rings widen until a tile `hit` takes is met, every cell walkable — a tile near its aim ends in two or three, where a BFS would carry a front. `None` where none is.
def _nearest(x: int, y: int, ctx: dict, hit: Callable[[int, int], bool]) -> dict | None:
    grid = ctx["grid"]
    height, width, best, at = grid.height, grid.width, None, (x, y)
    # A ring holds tiles worth `r` walked to `r * √2`, so the first tile met may still be beaten one ring out — the search stops once no ring left can.
    for r in range(max(width, height)):
        if best is not None and r >= best:
            break
        for nx, ny in _ring_tiles(x, y, r, width, height):
            if hit(nx, ny) and (walked := walk_tiles(nx - x, ny - y)) < (best if best is not None else walked + 1):
                best, at = walked, (nx, ny)
    if best is None:
        return None
    # Its tile, a goal `actor … --to` walks a body to: none on the very tile asked.
    spot = {"x": at[0], "y": at[1]} if at != (x, y) else {}
    return {**spot, "crow_tiles": round(best), "dir": bearing(at[0] - x, at[1] - y)}


# The nearest water of any kind, by the id `geography waters` lists it under: the first tile of it met, its shore.
def _nearest_water(x: int, y: int, ctx: dict) -> dict | None:
    grid, layer_by_id = ctx["grid"], ctx["layer_by_id"]
    if (reach := _nearest(x, y, ctx, lambda nx, ny: layer_by_id[grid[ny][nx]] == "Ocean")) is None:
        return None
    at = (reach.get("x", x), reach.get("y", y))
    return {**ctx["water_body"]()(*at), **reach}


def _radius_tiles(cx: int, cy: int, radius: int, width: int, height: int) -> list[tuple[int, int]]:
    return [(x, y) for dy in range(-radius, radius + 1) for dx in range(-radius, radius + 1) if 0 <= (x := cx + dx) < width and 0 <= (y := cy + dy) < height]


# The tiles of a ground touching its outside: two grounds meet nearest on their rims, which a land's edges already are.
def _rim(tiles: list[tuple[int, int]]) -> list[tuple[int, int]]:
    own = set(tiles)
    return [(x, y) for x, y in tiles if (x + 1, y) not in own or (x - 1, y) not in own or (x, y + 1) not in own or (x, y - 1) not in own]


# The square ring at Chebyshev radius `r` around a tile, clipped to the map — the shape an 8-way search grows by, whatever it then costs a body to walk.
def _ring_tiles(x: int, y: int, r: int, width: int, height: int) -> Iterator[tuple[int, int]]:
    x0, x1, y0, y1 = x - r, x + r, y - r, y + r
    for nx in range(max(0, x0), min(width - 1, x1) + 1):  # the two horizontal sides, corners included
        for ny in {y0, y1}:
            if 0 <= ny < height:
                yield nx, ny
    for ny in range(max(0, y0 + 1), min(height - 1, y1 - 1) + 1):  # and the two vertical ones, corners already walked
        for nx in {x0, x1}:
            if 0 <= nx < width:
                yield nx, ny


# A tally as `geography … islands` writes a land's ground: the three largest, in whole percents, a share rounding to nought left out — `None` for none.
def _shares(counter: Counter, total: int) -> str | None:
    return " | ".join(f"{pct}% {name}" for name, n in counter.most_common(3) if (pct := round(n / total * 100)) > 0) or None


# `block`, `burning`, `frozen` (passing frost), `islet_tiles` (a land too small to count) or `patch`, `snow`, `ice`, in water the body or `pond_tiles`: as they hold.
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
    if out["island_id"] is not None:
        out["patch"] = ctx["patch_at"](x, y)[1]
    elif off_land(name) == "islet":
        out["islet_tiles"] = ctx["tile_to_island"].islet_size((x, y))
    elif tile_layer(name) == "Ocean":
        out |= ctx["water_body"]()(x, y)
    return out


def main(argv: list[str]) -> int:
    save_path, argv, chapter = take_chapter(argv)  # pop the `C<n>` token first — argparse has no such positional and would abort on it

    parser = arg_parser(prog="tiles/info.py", description="Inspect tile(s) at (x, y) with optional radius. Output is keyed by `'x,y'`.")
    parser.add_argument(
        "xy", type=_end_arg, metavar="x,y|b<id>|c<id>|p<id>|<place>", help="Tile coords (WB UI, y grows north), e.g. `415,117` — a place or body by a lone `--to`."
    )
    parser.add_argument("sections", nargs="?", help=f"Comma-separated sections or `full` (default) — a lone `--to` answers alone. Valid: {', '.join(_ALL_SECTIONS)}")
    parser.add_argument("--ground", "-g", metavar="ground", help="A ground as `geography … biomes` names it, or `burning`: its nearest tile, in `distances`.")
    parser.add_argument("--island", "-i", type=int, metavar="id", help="A land by id, measured in `distances` as `to_islands` is — one past the nearest five.")
    parser.add_argument("--radius", "-r", type=int, default=0, help=f"Radius around (x, y) — 0..{_MAX_RADIUS} (default 0).")
    parser.add_argument(
        "--to",
        type=_end_arg,
        metavar="x,y|b<id>|c<id>|p<id>|<place>",
        help="A second end and a `to` key, the walk from the first to it — the tiles too once sections are named.",
    )
    parser.add_argument("--water", "-w", type=water_arg, metavar="lake<id>|river<id>|sea<id>", help="One water by its id, its shore measured in `distances`.")
    args = parser.parse_args(argv)

    try:
        # Membership only, never walked in order — the emitting `if`s below name each one. A `--to` alone answers alone, as `actor`'s does: the way, not the tiles.
        sections = set(parse_sections(args.sections or "full", _ALL_SECTIONS)) if args.sections or not args.to else set()
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 2

    if any(isinstance(end, str) for end in (args.xy, args.to)) and (sections or args.radius):  # a building lies on many tiles, a section reads one
        print(
            "✗ a building `b<id>`, a town `c<id>`, a body `p<id>` or a place's name ends a lone `--to`: sections and `--radius` read tiles — name them `x,y`",
            file=sys.stderr,
        )
        return 2
    if not 0 <= args.radius <= _MAX_RADIUS:  # past it, a count or a search answers better than a sheet per tile: said where to go, not merely that it is refused
        print(
            f"✗ `--radius` reads at most {_MAX_RADIUS} tiles around: past that, `world … roster --nearest x,y` finds bodies, "
            "`geography … positions -t <kind>` things, `map/show.py x,y --zoom <n>` the lay of the land",
            file=sys.stderr,
        )
        return 2
    if args.to and args.radius:  # refused before the save is read: a call that cannot be answered should not cost the load
        print("✗ `--to` reads two tiles and `--radius` a square around one: they don't combine", file=sys.stderr)
        return 2
    aimed = [flag for flag, given in (("--ground", args.ground), ("--island", args.island), ("--water", args.water)) if given is not None]
    if aimed and "distances" not in sections:
        print(f"✗ {', '.join(aimed)} answer{'s' if len(aimed) == 1 else ''} in `distances`: name that section, or `full`", file=sys.stderr)
        return 2
    if args.water is not None and args.water[1] is None:  # a family is `geography … waters`'s to list: a shore is one water's
        print(f"✗ --water {args.water[0]}: `distances` measures one water's shore — `{args.water[0]}<id>`, as `geography … waters` lists them", file=sys.stderr)
        return 2

    save = load_save(save_path)

    # The grid ships run-length encoded, so its shape reads off the header — no need to decode the whole map to bounds-check the query.
    height = len(save.get("tileArray") or [])
    width = sum((save.get("tileAmounts") or [[]])[0])

    if not (height and width):
        print("✗ empty grid", file=sys.stderr)
        return 2

    grounds, aimed = [], []
    for end in (args.xy, args.to or args.xy):
        if isinstance(found := ([end], None) if isinstance(end, tuple) else _ground(end, save, save_path, chapter), str):
            print(found, file=sys.stderr)
            return 1
        grounds.append(found[0])
        aimed.append(found[1])
    # A land is held by its rim: the other end standing on it meets it where it stands, no shore away
    for at, place in enumerate(aimed):
        if place and place[:1] == "i" and place[1:].isdigit():
            island_of = compute_islands_cached(save, save_path)[1]
            if inside := next((tile for tile in grounds[1 - at] if island_of.get(tile) == int(place[1:])), None):
                grounds[at] = [inside]
    # A building, a town or a place is met at its nearest tile, the walk setting off from the first's toward all the second's
    (cx, cy), (tx, ty) = _closest_pair(grounds[0], grounds[1])
    for x, y in ((cx, cy), (tx, ty)):
        if not (0 <= x < width and 0 <= y < height):
            print(f"✗ coords ({x}, {y}) out of bounds — map is {width}×{height}", file=sys.stderr)
            return 2

    coords = [(cx, cy), (tx, ty)] if args.to else _radius_tiles(cx, cy, args.radius, width, height)
    queried = set(coords) if args.to else {(cx, cy)}  # the tiles a reading is about: both ends of a `--to`, the centre of a sweep
    ctx = _build_context(save, save_path, sections, coords, args.island, "distances" in sections or args.to is not None)
    if args.island is not None and args.island not in ctx["lands"]:
        print(f"✗ no land with id {args.island} — `geography … islands` lists them", file=sys.stderr)
        return 2
    if args.water is not None:
        kind, ref = args.water
        if ref not in {body["id"] for body in waters_cached(save, save_path)[f"{kind}s"]}:
            print(f"✗ no {kind} {ref} — `geography … waters` lists them", file=sys.stderr)
            return 2
        ctx["aimed_water"] = {kind: ref}
    if args.ground == _BURNING:  # no ground's: the save lists the burning tiles apart
        ctx["fire_tiles"] = set(listed_tiles(save, "fire"))
        if not ctx["fire_tiles"]:
            print("✗ nothing burns in this world", file=sys.stderr)
            return 2
    elif args.ground is not None:
        ctx["ground_by_id"] = [(tile_ground(name) or "").removeprefix(BARE) for name in ctx["tile_map"]]
        if args.ground not in ctx["ground_by_id"]:
            print(f"✗ no {args.ground} in this world — `geography … biomes -i <land>` lists a land's grounds", file=sys.stderr)
            return 2
    ctx["aimed_ground"] = args.ground
    if sections == {"islet"} and not ctx["tile_to_island"].islet_size((cx, cy)):  # asked alone, an empty block would read as an islet with nothing on it
        land = ctx["tile_to_island"].get((cx, cy))
        print(f"✗ ({cx}, {cy}) is on no islet — {f'land {land}: `geography … islands -i {land}`' if land else 'water'}", file=sys.stderr)
        return 2
    # Asked alone, a sweep with no town in it would read as a failure rather than open ground — every tile weighed, a neighbour's town counting.
    if sections == {"context"} and not any(_context_at(x, y, ctx) for x, y in coords):
        print(f"✗ ({cx}, {cy}){' and the tiles around lie' if args.radius else ' lies'} in no town", file=sys.stderr)
        return 2

    # The same for what lives or stands there: asked with nothing else, a tile with neither says so, an empty answer reading as a tool gone wrong.
    if sections and sections <= _BARE.keys() and not any(ctx[f"{section}_by_pos"] for section in sections):  # each index holds the tiles asked alone
        print(f"✗ {' and '.join(_BARE[s] for s in sorted(sections))} on ({cx}, {cy}){' or the tiles around' if args.radius else ''}", file=sys.stderr)
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
            cell["ground"] = _ground_at(x, y, ctx, (x, y) in queried)
        if "islet" in sections and (x, y) in queried:  # the islet whole, said once for the tile asked about as `distances` is
            cell["islet"] = _islet_at(x, y, ctx)
        if "tile_info" in sections:
            cell["tile_info"] = _tile_info_at(x, y, ctx)
        out[f"{x},{y}"] = cell
    if args.to:  # a relation between the two ends, not a trait of either: its own key, the cap read from the first toward the second
        out["to"] = {
            "chunks_apart": chunks_apart(cx, cy, tx, ty),
            "dir": bearing(tx - cx, ty - cy),
            **({"from": {"aimed": aimed[0], "x": cx, "y": cy}} if aimed[0] else {}),
            **_measure(cx, cy, round(walk_tiles(tx - cx, ty - cy)), (gy * width + gx for gx, gy in grounds[1]), ctx),
            **({"reached": {"aimed": aimed[1], "x": tx, "y": ty}} if aimed[1] else {}),
        }
        # A place that spreads is read off its edge, and a sentence may read it off its middle: the second cap said wherever the two part
        centres = [place_centre(end) if place and _SPREAD.fullmatch(place) else None for end, place in zip((args.xy, args.to), aimed, strict=True)]
        if any(centres) and (cx, cy) != (tx, ty):
            (fx, fy), (gx, gy) = centres[0] or (cx, cy), centres[1] or (tx, ty)
            if (turn := bearing(gx - fx, gy - fy)) != out["to"]["dir"]:
                out["to"]["centre_dir"] = turn

    emit(out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
