#!/usr/bin/env python3

# Per-tile inspector at (x, y), or both ends of a `--to` — feeds the chronicler ad-hoc tile investigations (battle sites, neighbours, frontier scouting).
# Output: dict keyed by `"x,y"`, each value contains the requested sections for that tile; a lone tile comes out bare.
# Coordinate convention: WB UI / actor coords; `grid[y][x]` (no inversion — y grows north and so does the row index).

import math
import re
import sys
from collections import Counter, defaultdict
from functools import cache, partial
from heapq import heapify, heappop, heappush
from itertools import compress, count
from pathlib import Path
lazy from collections.abc import Callable, Iterable, Iterator

sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))

from grid import (
    BARE,
    LazyTileGrid,
    frozen_tiles,
    listed_tiles,
    off_land,
    patch_finder,
    tile_biome,
    tile_block,
    tile_elevation,
    tile_frost,
    tile_ground,
    tile_kind,
    tile_layer,
    tile_mask,
)
from islands import compute_islands_cached, islet_heart
from places import PlaceError, end_text, named_place, place_centre
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
    civic_building_ids,
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
    point_xy,
    run,
    take_chapter,
    tile_text,
    under_construction,
    walk_tiles,
    water_ref,
    xy_arg,
    zone_xy,
)
from walking import WalkMap, walk_way, walled_in
from waters import river_ends_near, water_bodies, water_tiles, waters_cached

_ALL_SECTIONS = ("actors", "distances", "ground", "islet", "owner", "rays", "tile_info")
_AXES = ("E–W", "NE–SW", "N–S", "NW–SE")  # the four lines a shape can lie along, every 45° from east, `y` growing north
_BARE = {"actors": "no body", "ground": "nothing built or grown", "owner": "no town"}  # what a tile lacks, said when these are all the call asked
_BRUTE_PAIRS = 20_000  # tile pairs two grounds are weighed by one by one: a building and a body, never a land and a lake
_BURNING = "burning"  # the end of the fires, no ground: `geography … burning` names them so
_END = "x,y|b<id>|c<id>|p<id>|i<land>|lake<id>|burning|frozen|g:<ground>|<place>"  # what either end of a reading takes, as `--help` shows it
_FARTHER = float("inf")  # the standing best before any land is seen, so the first tile of an island always takes its place
_FROZEN = "frozen"  # the end of every frost, no ground: snow, ice, permafrost and the passing frost, as `geography … frozen` counts them
_GROUND_PREFIX = "g:"  # `--to g:rock`: a ground by its `biomes` name, as `actor … --to` takes one
_LAND = re.compile(r"i\d+")  # a land by its id, as `geography … islands` lists it
_LAND_REACH = 60  # past that, a tile is open sea and the nearest shore is no longer what isolates it — `strait_to_land` gives the reach, not a number
_LONG_SHAPE = 1.5  # length over breadth from which a shape lies along a line: rounder, it lies along none
_NEAR_ENDS = 3  # a river's ends `to_river_ends` names from a tile, nearest along its water: where it runs out from here, a delta's dozens left to the map
_NEAR_ISLANDS = 5  # the lands a reading names around a point: past five, the rest are the far side of the world whatever the tile
_PAIR_CELL = 16  # the side of the cells a large ground is hashed into for `_closest_pair`, a chunk's
_REFERENCE_SPEED = 10  # chronicler.md § Échelle's walker: a tile has no body, so its way is the one the scale's pace would take, never timed
_RELIEF = {"mountains": "mountain", "snow_block": "mountain", "snow_summit": "mountain", "summit": "mountain"}  # a wall and its peak, one relief
_SPREAD = re.compile(r"i\d+|(?:lake|river|sea)\d+|box")  # what a place aimed at spreads over, edge and middle apart: a land, a water, a box

# The eight steps a tide takes, each with its length — a slanted one being longer than a straight one, the least water is not the nearest in rings.
_WEIGHTED_DELTAS = tuple(((dx, dy), 1.0 if dx == 0 or dy == 0 else 1 + DIAGONAL_EXTRA) for dx in (-1, 0, 1) for dy in (-1, 0, 1) if dx or dy)


# Identity and allegiance only — the chronicler follows up with `actor/info.py <id>` for the rest, so a reading stays short.
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


# A tile's biome as `rays` reads it, else the bare ground `biomes` names, a water by its id as its relief is.
def _biome_of(x: int, y: int, ctx: dict) -> str:
    return (tile_ground(ctx["tile_map"][ctx["grid"][y][x]]) or "").removeprefix(BARE) or _water_named(x, y, ctx)


# One home for every index, each built only for the sections that asked — every building and actor in the world, for the handful of tiles queried.
# `walks`: whether anything is walked — `distances`, or a `--to` whatever the sections, its two ends being measured either way.
def _build_context(save: dict, save_path: Path, sections: set[str], coords: list[tuple[int, int]], walks: bool) -> dict:
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

    if {"actors", "distances", "owner"} & sections:  # the two id maps resolve refs for `actors` as well as `owner`
        ctx["cities_by_id"] = index_by_id(save.get("cities") or [])
        ctx["kingdoms_by_id"] = index_by_id(save.get("kingdoms") or [])

    if {"distances", "islet", "rays", "tile_info"} & sections:
        ctx["grid"] = LazyTileGrid(save)
    if "rays" in sections:  # each tile named once, though two tiles' rays cross it
        ctx["biome_of"], ctx["relief_of"] = cache(lambda tx, ty: _biome_of(tx, ty, ctx)), cache(lambda tx, ty: _relief_of(tx, ty, ctx))
        ctx["map_size"] = sum((save.get("tileAmounts") or [[]])[0]), len(save.get("tileArray") or [])

    if {"distances", "owner"} & sections:
        _index_cities(ctx, {(x // ZONE_TILES, y // ZONE_TILES) for x, y in coords})

    # `distances` needs it too, to say how far a rock lies from a land a city could hold, and a walk what land it keeps to
    if walks or {"islet", "tile_info"} & sections:
        islands, ctx["tile_to_island"] = compute_islands_cached(save, save_path)
        ctx["lands"] = {land["id"]: land for land in islands}

    if "tile_info" in sections:
        ctx["burning_set"] = wanted.intersection(listed_tiles(save, "fire"))
        ctx["frozen_set"] = wanted.intersection(listed_tiles(save, "frozen_tiles"))
        ctx["patch_at"] = patch_finder(save, ctx["grid"], ctx["tile_to_island"])

    if {"distances", "rays", "tile_info"} & sections:
        ctx["water_body"] = cache(lambda: water_bodies(save, save_path))  # called not stored: a tile on dry land never asks what water it lies in

    if "distances" in sections:
        ctx["layer_by_id"] = [tile_layer(name) for name in ctx["tile_map"]]
        ctx["river_ends"] = partial(river_ends_near, save, save_path)

    if walks:  # called not stored: a walk is drawn only where both ends stand on one land
        ctx["walk_map"], ctx["width"] = cache(lambda: WalkMap(save)), sum(save["tileAmounts"][0])

    return ctx


# The middle of an end that spreads: a land or a water named by its id at its `heart`, as `geography` sites it; any other by its point in `places.json`.
def _centre(end: str, save: dict, save_path: Path) -> tuple[int, int]:
    if _LAND.fullmatch(end):
        return point_xy(next(land["heart"] for land in compute_islands_cached(save, save_path)[0] if land["id"] == int(end[1:])))
    if not (water := water_ref(end)):
        return place_centre(end)
    return point_xy(next(body["heart"] for body in waters_cached(save, save_path)[f"{water[0]}s"] if body["id"] == water[1]))


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


# Every reading counts steps, WB walking its eight directions.
def _distances_at(x: int, y: int, ctx: dict) -> dict:
    out: dict = {"to_water": _nearest_water(x, y, ctx)}
    # A river winds where a ray runs straight: on one, its ends nearest along its water, an arm's dead end too — none a source, WB keeps no flow
    if (here := out["to_water"]) and here.get("crow_tiles") == 0 and (river := here.get("river")) is not None:
        ends = ctx["river_ends"](river, (x, y), _NEAR_ENDS)
        out["to_river_ends"] = [{"dir": bearing(ex - x, ey - y), "water_tiles": steps, "x": ex, "y": ey} for (ex, ey), steps in ends] or None
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
    return out | _nearest_lands(_island_distances(x, y, ctx))


# An end of `tiles`: any of `_END` but the tile, its quotes off; else a tile `x,y`.
def _end_arg(value: str) -> str | tuple[int, int]:
    value = end_text(value, "an end")  # argparse names which of the two
    return xy_arg(value) if body_ref(value) is None and re.fullmatch(r"-?\d+,-?\d+", value) else value


# A town is its fabric, not its centre, as `to_islands` takes a land's nearest tile: at the edge of a sprawling town a body stands at the gate, not a centre away.
def _fabric_distance(x: int, y: int, quarters: list[tuple[int, int]]) -> int:
    return round(min(walk_tiles(max(qx - x, x - qx - ZONE_TILES + 1, 0), max(qy - y, y - qy - ZONE_TILES + 1, 0)) for qx, qy in quarters))


# A named end's tiles — any of `_END` but the tile, as `actor … --to` reads them —, what it aimed at, else why none.
def _ground(end: str, save: dict, save_path: Path, chapter: str | None) -> tuple[list[tuple[int, int]], str | None] | str:
    if end in (_BURNING, _FROZEN):  # no ground's: the save lists the burning tiles apart, the frost partly
        tiles = list(listed_tiles(save, "fire")) if end == _BURNING else list(frozen_tiles(save))
        return (tiles, end) if tiles else f"✗ nothing {'burns' if end == _BURNING else 'is frozen'} in this world"
    if (ground := end.removeprefix(_GROUND_PREFIX)) != end:  # the rock at a range's foot, a biome's edge
        names = [(tile_ground(name) or "").removeprefix(BARE) for name in save["tileMap"]]
        if ground not in names:
            return f"✗ no {ground} in this world — `geography … biomes --filter i<land>` lists a land's grounds"
        return [(x, y) for y, row in enumerate(tile_mask(save, [own == ground for own in names])) for x, held in enumerate(row) if held], end
    if _LAND.fullmatch(end):  # a land by its id, held by its rim as one `places.json` names
        tiles = [(x, y) for x, y, owner in compute_islands_cached(save, save_path)[1].edges() if owner == int(end[1:])]
        return (tiles, end) if tiles else f"✗ no land {end[1:]} — `geography … islands` lists them"
    if water := water_ref(end):  # by its id, as its name in `places.json` would: a water yet unnamed is measured all the same
        tiles = water_tiles(save, save_path, *water)
        return (tiles, end) if tiles else f"✗ no {water[0]} {water[1]} — `geography … waters` lists them"
    if not re.fullmatch(r"[bcp]\d+", end):
        try:
            found = named_place(end, save, save_path, compute_islands_cached(save, save_path)[1], WalkMap(save))
        except PlaceError as e:
            return str(e)
        return found or f"✗ `{end}` is no end — {_END.replace('|', ', ')}"
    kind, ref = end[0], int(end[1:])
    if kind == "b":
        site = next((b for b in save.get("buildings") or [] if b.get("id") == ref), None)
        return (site and (building_footprint(site), end)) or absent_entity("ground", "buildings", ref, chapter, noun="building")
    if kind == "c":
        city = next((c for c in save.get("cities") or [] if c.get("id") == ref), None)
        return ([centre], None) if city and (centre := city_centre(city)) else absent_entity("city", "cities", ref, chapter)
    body = next((a for a in save.get("actors_data") or [] if a.get("id") == ref and not is_boat(a)), None)
    return ([actor_xy(body)], None) if body else absent_entity("actor", "actors_data", ref, chapter, lambda a: not is_boat(a))


# One object per tile, never two — WB's `buildings` holds the flowers and the ore too, hence the family.
def _ground_at(x: int, y: int, ctx: dict) -> dict:
    if (b := ctx["ground_by_pos"].get((x, y))) is None:
        return {}
    asset = b.get("asset_id")
    family = building_family(asset)  # named as `geography` names them
    dated = "laid" if asset in civic_building_ids() else "born"  # a town's building is laid, a tree or an ore grows
    return {"asset_id": asset, dated: entity_born(b), "id": b.get("id"), "type": family, "under_construction": under_construction(b) or None}


def _holds(section: str, coords: list[tuple[int, int]], ctx: dict) -> bool:
    return any(_owner_at(x, y, ctx) for x, y in coords) if section == "owner" else bool(ctx[f"{section}_by_pos"])  # each index holds the tiles asked alone


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
        "heart": tile_text(cx, cy),
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


# What a ground's end says of the tile met: its patch, as `biomes -t` cuts it, or the sort of frost.
def _met(place: str | None, x: int, y: int, save: dict, ctx: dict) -> dict:
    if place == _FROZEN:
        return {"frozen": frozen_tiles(save)[x, y]}
    if place and place.startswith(_GROUND_PREFIX):
        return {"patch": patch_finder(save, LazyTileGrid(save), ctx["tile_to_island"])(x, y)[1]["tiles"]}
    return {}


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


# The town holding a tile, and its crown — `{}` on unclaimed ground, which `emit` strips from the cell.
def _owner_at(x: int, y: int, ctx: dict) -> dict:
    city = _city_at(x, y, ctx)
    if city is None:
        return {}
    return {"city": {"id": city["id"], "name": city.get("name")}, "kingdom": entity_ref(city.get("kingdomID"), ctx["kingdoms_by_id"])}


# What each of the eight headings runs into, as the crow flies to the tile reached: the relief's change, after the biome's if sooner — a wall seen from its foot.
def _rays_at(x: int, y: int, ctx: dict) -> dict:
    (width, height), relief, biome = ctx["map_size"], ctx["relief_of"], ctx["biome_of"]
    here, own, rays = relief(x, y), biome(x, y), {}
    for dx, dy in ((0, 1), (1, 1), (1, 0), (1, -1), (0, -1), (-1, -1), (-1, 0), (-1, 1)):
        stops: list[int | str] = []
        for k in count(1):  # never past the map's rim, which stops a ray as a ground does
            tx, ty = x + k * dx, y + k * dy
            if (met := relief(tx, ty) if 0 <= tx < width and 0 <= ty < height else "edge") != here:
                stops += [round(walk_tiles(k * dx, k * dy)), met]  # a diagonal step its 1.41
                break
            if not stops and (other := biome(tx, ty)) != own:
                stops += [round(walk_tiles(k * dx, k * dy)), other]
        rays[bearing(dx, dy)] = stops
    return rays


# A tile's relief as `rays` reads it, mountain and summit one, a water by its id as `waters` names it: the river a ray runs along, the lake it falls into.
def _relief_of(x: int, y: int, ctx: dict) -> str:
    if tile_layer(name := ctx["tile_map"][ctx["grid"][y][x]]) == "Ocean":
        return _water_named(x, y, ctx)
    return _RELIEF.get(block, block) if (block := tile_block(name)) else tile_kind(name)


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


# A water by its id, as `geography … waters` lists it; a pond, numbered by none, as such.
def _water_named(x: int, y: int, ctx: dict) -> str:
    ((kind, ref),) = ctx["water_body"]()(x, y).items()
    return "pond" if kind == "pond_tiles" else f"{kind}{ref}"


def main(argv: list[str]) -> int:
    save_path, argv, chapter = take_chapter(argv)  # pop the `C<n>` token first — argparse has no such positional and would abort on it

    parser = arg_parser(prog="tiles/info.py", taken="[C<n>]")
    parser.add_argument("xy", type=_end_arg, metavar=_END)
    parser.add_argument("sections", nargs="?")
    parser.add_argument("--to", type=_end_arg, metavar=_END, action="append")  # every one measured, as `actor`'s are
    args = parser.parse_args(argv)

    try:
        # Membership only, never walked in order — the emitting `if`s below name each one. A `--to` alone answers alone, as `actor`'s does: the way, not the tiles.
        sections = set(parse_sections(args.sections or "full", _ALL_SECTIONS)) if args.sections or not args.to else set()
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 2

    targets: list[str | tuple[int, int]] = args.to or []
    ends = [args.xy, *targets]
    if any(isinstance(end, str) for end in ends) and sections:  # a building lies on many tiles, a section reads one
        print("✗ sections read tiles, `x,y`: any other end answers a lone `--to`", file=sys.stderr)
        return 2

    save = load_save(save_path)

    # The grid ships run-length encoded, so its shape reads off the header — no need to decode the whole map to bounds-check the query.
    height = len(save.get("tileArray") or [])
    width = sum((save.get("tileAmounts") or [[]])[0])

    if not (height and width):
        print("✗ empty grid", file=sys.stderr)
        return 2

    found: list[tuple[list[tuple[int, int]], str | None]] = []
    for end in ends:
        if isinstance(told := ([end], None) if isinstance(end, tuple) else _ground(end, save, save_path, chapter), str):
            print(told, file=sys.stderr)
            return 1
        found.append(told)
    # A land is held by its rim: the other end standing on it meets it where it stands, no shore away — the map's lands read once for every pair
    island_of = compute_islands_cached(save, save_path)[1] if any(place and _LAND.fullmatch(place) for _, place in found) else None
    pairs = []  # each `--to` met from the first end, or the first end alone
    for ground, place in found[1:] or found[:1]:
        grounds, aimed = [found[0][0], ground], [found[0][1], place]
        for at, land in enumerate(aimed):
            if island_of and land and _LAND.fullmatch(land) and (inside := next((t for t in grounds[1 - at] if island_of.get(t) == int(land[1:])), None)):
                grounds[at] = [inside]
        # A building, a town or a place is met at its nearest tile, the walk setting off from the first's toward all the second's
        (cx, cy), (tx, ty) = _closest_pair(grounds[0], grounds[1])
        for x, y in ((cx, cy), (tx, ty)):
            if not (0 <= x < width and 0 <= y < height):
                print(f"✗ coords ({x}, {y}) out of bounds — map is {width}×{height}", file=sys.stderr)
                return 2
        pairs.append(((cx, cy), (tx, ty), grounds, aimed))

    cx, cy = pairs[0][0]  # sections read `x,y` ends alone, so every pair sets off from this one tile
    coords = [(cx, cy), *(reached for _, reached, _, _ in pairs)] if args.to else [(cx, cy)]
    ctx = _build_context(save, save_path, sections, coords, "distances" in sections or args.to is not None)
    if sections == {"islet"} and not ctx["tile_to_island"].islet_size((cx, cy)):  # asked alone, an empty block would read as an islet with nothing on it
        land = ctx["tile_to_island"].get((cx, cy))
        print(f"✗ ({cx}, {cy}) is on no islet — {f'land {land}: `geography … islands --filter i{land}`' if land else 'water'}", file=sys.stderr)
        return 2
    # Its town, what lives or stands there: asked with nothing else, a tile with none of them says so, an empty answer reading as a tool gone wrong.
    if sections and sections <= _BARE.keys() and not any(_holds(section, coords, ctx) for section in sections):
        *rest, last = (_BARE[section] for section in sorted(sections))
        print(f"✗ {', '.join(rest)}{' and ' if rest else ''}{last} on ({cx}, {cy})", file=sys.stderr)
        return 2

    out: dict = {}
    for x, y in coords if sections else ():
        cell: dict = {}
        if "actors" in sections:
            cell["actors"] = _actors_at(x, y, ctx)
        if "distances" in sections:
            cell["distances"] = _distances_at(x, y, ctx)
        if "ground" in sections:
            cell["ground"] = _ground_at(x, y, ctx)
        if "islet" in sections:
            cell["islet"] = _islet_at(x, y, ctx)
        if "owner" in sections:
            cell["owner"] = _owner_at(x, y, ctx)
        if "rays" in sections:
            cell["rays"] = _rays_at(x, y, ctx)
        if "tile_info" in sections:
            cell["tile_info"] = _tile_info_at(x, y, ctx)
        out[f"{x},{y}"] = cell
    # A place that spreads is read off its edge, and a sentence may read it off its middle: the second cap said wherever the two part
    start = _centre(args.xy, save, save_path) if isinstance(args.xy, str) and (place := found[0][1]) and _SPREAD.fullmatch(place) else None
    relations = {}  # a relation between the two ends, not a trait of either: its own key, the cap read from the first toward the second
    for end, ((cx, cy), (tx, ty), grounds, aimed) in zip(targets, pairs, strict=False):
        relation = {
            "chunks_apart": chunks_apart(cx, cy, tx, ty),
            "dir": bearing(tx - cx, ty - cy),
            **({"from": {"aimed": aimed[0], "x": cx, "y": cy, **_met(aimed[0], cx, cy, save, ctx)}} if aimed[0] else {}),
            **_measure(cx, cy, round(walk_tiles(tx - cx, ty - cy)), (gy * width + gx for gx, gy in grounds[1]), ctx),
            **({"reached": {"aimed": aimed[1], "x": tx, "y": ty, **_met(aimed[1], tx, ty, save, ctx)}} if aimed[1] else {}),
        }
        aim = _centre(end, save, save_path) if isinstance(end, str) and aimed[1] and _SPREAD.fullmatch(aimed[1]) else None
        if (start or aim) and (cx, cy) != (tx, ty):
            (fx, fy), (gx, gy) = start or (cx, cy), aim or (tx, ty)
            if (turn := bearing(gx - fx, gy - fy)) != relation["dir"]:
                relation["centre_dir"] = turn
        relations[end if isinstance(end, str) else tile_text(*end)] = relation
    if relations:  # one target told bare, several under the name each was given, as `actor --to` keys them
        out["to"] = relations if len(relations) > 1 else next(iter(relations.values()))

    emit(out)
    return 0


if __name__ == "__main__":
    sys.exit(run(main))
