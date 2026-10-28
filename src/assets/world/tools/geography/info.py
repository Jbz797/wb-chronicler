#!/usr/bin/env python3

# Geographic stats reserved for the chronicler (not consumed by the UI). User-facing docs: `docs/tools.md`.

import math
import re
import statistics
import sys
from collections import Counter, defaultdict
from functools import partial
from heapq import heapify, heappop, heappush
from pathlib import Path
lazy from collections.abc import Callable, Collection, Iterable

sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))

from grid import (
    BARE,
    LAND_LAYERS,
    LazyTileGrid,
    frozen_tally,
    listed_tiles,
    off_land,
    shore_tally,
    tile_biome,
    tile_count,
    tile_frost,
    tile_ground,
    tile_kind,
    tile_layer,
    tile_mask,
)
from islands import TileIslands, compute_islands_cached
from shared import (
    DIAGONAL_EXTRA,
    MAX_LISTED,
    SAVES_DIR,
    actor_xy,
    arg_parser,
    asset_families,
    asset_kinds,
    asset_sites,
    biome_lore,
    dormant,
    emit,
    index_by_id,
    is_boat,
    is_sapient,
    land_arg,
    land_side,
    load_save,
    moved_between,
    parse_sections,
    pickle_cached,
    quiet_zeros,
    take_chapter,
    take_since,
    union_root,
    unsited_reason,
    water_arg,
)
from waters import water_bodies, waters_cached

_ALL_SECTIONS = ("biomes", "bodies", "burning", "entity_types", "frozen", "gear", "islands", "positions", "ridges", "totals", "waters")
_BIOME_RUN = re.compile(rb"([\x01-\xff])\1*")  # a row's unbroken stretch of one biome, its code one byte, `0` where the ground bears none
_BUCKETED = ("bodies", "burning", "frozen", "gear", "positions")  # the sections that also count the islets and the water, which `-i` may name
_BY_LAND = ("biomes", "bodies", "burning", "frozen", "gear", "islands", "positions", "ridges", "waters")  # what `-i` narrows: the rest is world-wide
_DETAIL = ("borders", "bounds")  # what `-t` alone tells of a patch, the wide view keeping to where it lies
_FIRE_REACH = 16  # tiles between two burning ones of a single fire: twice a volcano's longest throw (`spawn_drop_max_radius`), its lava falling all round it
_GROUND_SWING = 0.1  # a ground's own change past which `biomes --since` tells it, its land's share still: a field doubled, a tenth of a forest burnt
_MAX_NAMED_CARRIERS = 5  # past a handful, naming them says less than counting them: on such a land, bearing arms is no longer the fact a chapter turns on

_NONE = {  # what an empty section is said to lack: a bare `{}` reads as a fault, or as a word mistyped
    "biomes": "biome",
    "bodies": "body",
    "burning": "fire",
    "entity_types": "entity of any kind",
    "frozen": "frost",
    "gear": "gear borne",
    "islands": "land",
    "ridges": "ridge",
}

_PERMAFROST_RUN = re.compile(rb"\x03+")  # a row's unbroken permafrost in the frost mask
_SHORE_REACH = 60  # tiles past which a fire is off every water, as `tiles` holds the open sea
_STEPS = tuple((dx, dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1) if dx or dy)  # the eight ways a crow-flown search widens
_SURVEY_PCT = 1  # the share of its land under which a ground is only named in the world-wide `biomes`: half its rows weigh less, and `-i` has them all
_TOP_PATCHES = 5  # the patches `biomes -t` sites of one ground — a second massif, a frost in two halves: past a handful, the row's count says the rest
_TOP_STRAITS = 10  # the narrowest crossings `waters` keeps past `MAX_LISTED`, the ones a tale swims: `-i <land>` lists a land's every one


# Every biome's patches, land by land: each row's runs of one biome joined to those they touch above, corners included, never across lands — C walks the map.
def _biome_patches(save: dict, island_of: TileIslands, biome_by_id: list[str | None]) -> tuple[dict[tuple[int | None, str], list[list]], list[bytes], list[str]]:
    names = sorted({biome for biome in biome_by_id if biome})
    code_of = {biome: k + 1 for k, biome in enumerate(names)}
    rows: list[list[tuple[int, int, int, int]]] = []  # each row's runs, as `(west, east + 1, land << 8 | biome code, run index)`
    count, grounds = 0, tile_mask(save, [code_of.get(biome or "", 0) for biome in biome_by_id])
    for marks in grounds:
        lands, row = island_of.row(len(rows)), []
        for match in _BIOME_RUN.finditer(marks):
            west, end = match.span()
            # Side by side, two ground tiles are one land; rock is where two lands meet, so a run of it is cut wherever the land changes under it.
            while west < end:
                land, east = lands[west], end
                if lands[west:end].count(land) != end - west:
                    east = next(x for x in range(west + 1, end) if lands[x] != land)
                row.append((west, east, land << 8 | marks[west], count))
                count, west = count + 1, east
        rows.append(row)

    parent = list(range(count))
    for y in range(1, len(rows)):
        above, first = rows[y - 1], 0
        for a, b, key, k in rows[y]:
            while first < len(above) and above[first][1] < a:  # ends a column short of this run's corner, and of every later one's
                first += 1
            for o in range(first, len(above)):
                oa, _, okey, q = above[o]
                if oa > b:
                    break
                if okey == key:
                    rq, rk = union_root(parent, q), union_root(parent, k)
                    parent[max(rq, rk)] = min(rq, rk)

    # Per patch, `[size, sum_x, sum_y, runs]`, arithmetic over its runs — a run's columns sum as a series. Keys come in the order the sweep first meets them.
    found: dict[int, list] = {}
    for y, row in enumerate(rows):
        for a, b, key, k in row:
            if (patch := found.get(root := union_root(parent, k))) is None:
                patch = found[root] = [key, 0, 0, 0, []]
            patch[1], patch[2], patch[3] = patch[1] + b - a, patch[2] + (a + b - 1) * (b - a) // 2, patch[3] + y * (b - a)
            patch[4].append((y, a, b))
    by_key: dict[tuple[int | None, str], list[list]] = {}
    for key, *patch in found.values():
        by_key.setdefault((key >> 8 or None, names[(key & 255) - 1]), []).append(patch)
    return by_key, grounds, names  # the patches, the map they were cut from — a code per tile — and the names those codes count from 1: what `_borders` reads


# The sweep kept on disk, with every ground's largest patches, which only `_patch_detail` reads.
def _biomes(save: dict, save_path: Path) -> dict:
    return pickle_cached("biomes_v18", save_path, lambda: _compute_biomes(save, save_path))


# What lies along a patch's outline, side by side: its three first neighbours, each its share of that outline — its own ground is none, nor the map's edge.
def _borders(runs: list[tuple[int, int, int]], grounds: list[bytes], kinds: list[str]) -> str | None:
    last, met = len(grounds) - 1, []
    for y, a, b in runs:
        met.append(grounds[y][a - 1 : a] + grounds[y][b : b + 1])  # an empty slice at either edge of the map
        if y:
            met.append(grounds[y - 1][a:b])
        if y < last:
            met.append(grounds[y + 1][a:b])
    counts = Counter(b"".join(met))
    del counts[grounds[runs[0][0]][runs[0][1]]]  # the tiles above and below that are the patch's own
    total = sum(counts.values())
    return " | ".join(f"{pct}% {kinds[code]}" for code, n in counts.most_common(3) if (pct := round(n / total * 100)) > 0) or None


# Every biome a land carries, marginal ones included — a paradox patch is a chapter's subject — then the ground none grows on: the shares add up to the land.
def _build_biomes(save: dict, save_path: Path) -> dict:
    return {key: value for key, value in _biomes(save, save_path).items() if key != "patches"}


# Who lives where, land by land, then on the islets and in the water: the living bodies and how many of them think — a hull carries, it is no body.
def _build_bodies(save: dict, save_path: Path) -> dict:
    _, island_of = compute_islands_cached(save, save_path)
    grid, tile_map = LazyTileGrid(save), save.get("tileMap") or []  # rows decoded only for a body off every land, on an islet or in the water
    thinking = index_by_id(save.get("subspecies") or [])
    by_land: defaultdict[str, list[int]] = defaultdict(lambda: [0, 0])
    for actor in save.get("actors_data") or []:
        if is_boat(actor):
            continue
        tally = by_land[_site_key(actor_xy(actor), island_of, grid, tile_map)]
        tally[0] += 1
        tally[1] += is_sapient(thinking.get(actor.get("subspecies")))
    return {
        key: f"{n} bod{'y' if n == 1 else 'ies'}" + (f" · {sapient} sapient" if sapient else "") for key, (n, sapient) in sorted(by_land.items(), key=_land_order)
    }


# A fire WB saves tile by tile, counted land by land, then on the islets and on the water — each tile by its biome, else by its ground as `islands` names it.
def _build_burning(save: dict, save_path: Path, island: int | str | None, before: dict[tuple[int, int], tuple[str, str]] | None = None) -> dict:
    if not (burning := _burning_tiles(save, save_path)) and not before:  # nothing listed, nothing to site: the islands are never unpickled
        return {}
    islands, grid, tile_map = compute_islands_cached(save, save_path)[0], LazyTileGrid(save), save.get("tileMap") or []
    by_land: defaultdict[str, list[str]] = defaultdict(list)
    for key, ground in burning.values():
        by_land[key].append(ground)
    # Counts, not the shares `islands` gives: a few dozen tiles read better whole than as percentages of themselves.
    out: dict[str, str | dict] = {key: _tally(grounds) for key, grounds in sorted(by_land.items(), key=_land_order)}
    # `-i` alone tells its land's fires apart, the world count staying one line a land — under `--since`, a land whose fires all went out too
    if island is not None and ((key := str(island)) in by_land or any(land == key for land, _ in (before or {}).values())):
        wet, bodies = [tile_layer(name) == "Ocean" for name in tile_map], water_bodies(save, save_path)
        water = partial(_water_near, grid=grid, wet=wet, bodies=bodies)  # handed down, so `_fires` needs no save
        fires = _fires(burning, key, next((row for row in islands if str(row["id"]) == key), None), water, before)
        lone = len(fires["fires"]) == 1 and fires["fires"][0]["grounds"] == out.get(key)  # one fire holding the land's whole burning: its line says it once
        out[key] = {"grounds": None if lone else out.get(key), **fires}
    return out


# Every kind the save holds, by family: `shared.asset_families`, which `actor … --to` and `positions -t` read, so that a name listed here is one they take.
def _build_entity_types(save: dict) -> dict:
    return {family: dict(counts) for family, counts in asset_families(save).items()}


# A land's frost, share first — the `permafrost` WB keeps frozen for good (`isFrozen`), the map's `snow` and `ice`, the passing `frost` — no tile ever counted twice.
def _build_frozen(save: dict, save_path: Path) -> dict:
    code = {"ice": 2, "permafrost": 3, "snow": 1}
    flags = [code.get(tile_frost(name) or tile_biome(name) or "", 0) for name in save.get("tileMap") or []]
    if not (passing := save.get("frozen_tiles") or []) and not any(flags):
        return {}
    islands, island_of = compute_islands_cached(save, save_path)
    sizes = {str(island["id"]): island["size"] for island in islands}
    by_land: defaultdict[str, Counter] = defaultdict(Counter)
    frost = Counter(island_of.listed_ids(passing))
    for island_id, n in frost.items():
        if island_id:
            by_land[str(island_id)]["frost"] += n
    if frost[0]:  # a passing frost off every land may lie on a rock or on the water: only these few are sited tile by tile
        grid, tile_map = LazyTileGrid(save), save.get("tileMap") or []
        for x, y in listed_tiles(save, "frozen_tiles"):
            if not island_of.get((x, y)):
                by_land[_land_key(None, tile_map[grid[y][x]])]["frost"] += 1
    # Ice is water and lies on no land; a run of permafrost is ground, one land all along; only snow, rock at times, is sited tile by tile — off a land, on a rock.
    for y, marks in enumerate(tile_mask(save, flags) if any(flags) else ()):
        if ice := marks.count(2):
            by_land["water"]["ice"] += ice
        lands, x = island_of.row(y), marks.find(1)
        while x != -1:
            by_land[str(lands[x] or "islets")]["snow"] += 1
            x = marks.find(1, x + 1)
        for match in _PERMAFROST_RUN.finditer(marks):
            by_land[str(lands[match.start()] or "islets")]["permafrost"] += match.end() - match.start()
    if {"islets", "water"} & by_land.keys():  # off every land, the share is of all the islets or of all the water, as `totals` counts them
        land, _, water = _surfaces(save)
        sizes |= {"islets": land - sum(island["size"] for island in islands), "water": water}
    # The share of what holds it, left out where it rounds to nothing.
    return {
        key: (f"{pct:g}% · " if key in sizes and (pct := round(sum(counts.values()) / sizes[key] * 100, 1)) else "")
        + " | ".join(f"{n} {kind}" for kind, n in counts.most_common())
        for key, counts in sorted(by_land.items(), key=_land_order)
    }


# Who bears what, land by land — an item carries no coordinates of its own: it exists through the hand that holds it, and a land with no bearer drops.
def _build_gear(save: dict, save_path: Path) -> dict:
    items = index_by_id(save.get("items") or [])
    _, island_of = compute_islands_cached(save, save_path)
    grid, tile_map = LazyTileGrid(save), save.get("tileMap") or []  # rows decoded only for a bearer off every land, on a rock or in the water
    by_land: defaultdict[str, list] = defaultdict(list)  # a factory, `setdefault` minting a list per bearer to drop it on all but the first
    for actor in save.get("actors_data") or []:
        if is_boat(actor) or not (worn := actor.get("saved_items")):
            continue
        by_land[_site_key(actor_xy(actor), island_of, grid, tile_map)].append(
            # An id the collection never resolves names nothing, so it is dropped rather than sorted against the rest as a `None`.
            {"id": actor["id"], "items": sorted(a for i in worn if (a := (items.get(i) or {}).get("asset_id"))), "name": actor.get("name")},
        )
    out = {}
    for key, bearers in sorted(by_land.items(), key=_land_order):
        block: dict = {"carriers": len(bearers), "items": sum(len(b["items"]) for b in bearers)}  # annotated: the roster below widens it past its two counts
        if len(bearers) < _MAX_NAMED_CARRIERS:  # no `light()` here: naming them is all this section could ever hand over, so there is no fuller form to call
            block["roster"] = sorted(bearers, key=lambda b: b["id"])
        out[key] = block
    return out


# Up to `MAX_LISTED`, or all on `-i`'s land, each by `id`, land else islet else water, `asset_id` if kinds mix; past it, by land and `total`. `only`: `--since`'s.
def _build_positions(
    save: dict, save_path: Path, kinds: set[str], land: int | str | None, only: Collection[int] | None = None
) -> list[dict] | dict[str, str | int] | None:
    sites = [(record, tile) for record, tile in asset_sites(save, kinds) if only is None or record.get("id") in only]
    if not sites:  # the lookup below costs 0.2 s cold, so a kind nobody built never pays for it
        return None
    _, island_of = compute_islands_cached(save, save_path)
    grid, tile_map = LazyTileGrid(save), save.get("tileMap") or []
    if land is not None:
        # A land by the lookup alone; only `islets` or `water` read the tile, which a sweep over the lands would otherwise decode for every site off them
        sites = [(r, tile) for r, tile in sites if (island_of.get(tile) == land if isinstance(land, int) else _site_key(tile, island_of, grid, tile_map) == land)]
    elif len(sites) > MAX_LISTED:
        by_land: defaultdict[str, Counter] = defaultdict(Counter)
        for record, tile in sites:
            by_land[_site_key(tile, island_of, grid, tile_map)][record.get("asset_id")] += 1
        tally = {key: " | ".join(f"{n} {kind}" for kind, n in counts.most_common()) for key, counts in sorted(by_land.items(), key=_land_order)}
        return {**tally, "info": f"past {MAX_LISTED} sites, a count by land — `-i <land>` or one kind lists each by id", "total": len(sites)}
    # `dormant` as `ground … metadata` tells it, so that a roll of volcanoes or geysers says which sleep without a call per mouth.
    mixed = len(kinds) > 1
    out = [
        {
            "asset_id": record.get("asset_id") if mixed else None,
            "dormant": dormant(record),
            "id": record.get("id"),
            "name": record.get("name"),
            "x": x,
            "y": y,
        }
        for record, (x, y) in sites
    ]
    for position in out:
        x, y = position["x"], position["y"]
        if (island_id := island_of.get((x, y))) is not None:
            position["island_id"] = island_id if land is None else None  # a land `-i` named goes unsaid on each of its sites
        elif off_land(tile_map[grid[y][x]]) == "islet":  # silent in the water, as `island_id` is: a hull at sea, a dock on shallows
            position["islet_tiles"] = island_of.islet_size((x, y))
    return sorted(out, key=lambda r: (r["y"], r["x"]))


# The map's own sums, which no list adds up: its water, its land split between the counted lands and the islets too small to be one, its shore.
def _build_totals(save: dict, save_path: Path) -> dict:
    islands, island_of = compute_islands_cached(save, save_path)
    # `(size, x, y)` each, the largest first and ties to the lower `(x, y)`: counted here so that no reader sweeps the map for a tally of rocks.
    rocks = sorted(island_of.islets(), key=lambda rock: (-rock[0], rock[1], rock[2]))
    frozen, tiles = frozen_tally(save)
    (land, goo, water), counted, tiles = _surfaces(save), sum(island["size"] for island in islands), tiles or 1
    shore, beach = shore_tally(save)
    # Each share of what holds it: the land, water and frozen of the map, the counted lands and islets of the land, the beach of the shore. Goo where it spread.
    return {
        "frozen": {"pct": round(frozen / tiles * 100, 1), "tiles": frozen},
        "goo": {"pct": round(goo / tiles * 100, 1), "tiles": goo} if goo else None,
        "land": {
            "islets": {
                "count": len(rocks),
                "largest": {"tiles": rocks[0][0], "x": rocks[0][1], "y": rocks[0][2]} if rocks else None,
                "median": statistics.median(size for size, *_ in rocks) if rocks else None,
                "pct": round((land - counted) / (land or 1) * 100, 1),
                "tiles": land - counted,
            },
            "lands": {"count": len(islands), "pct": round(counted / (land or 1) * 100, 1), "tiles": counted},
            "pct": round(land / tiles * 100, 1),
            "tiles": land,
        },
        "shore": {"beach": {"pct": round(beach / (shore or 1) * 100, 1), "tiles": beach} if beach else None, "tiles": shore},
        "water": {"pct": round(water / tiles * 100, 1), "tiles": water},
    }


# The map's burning tiles, each with its land and ground — the whole fire: a blaze spans a shore, never a land alone.
def _burning_tiles(save: dict, save_path: Path) -> dict[tuple[int, int], tuple[str, str]]:
    if not (positions := list(listed_tiles(save, "fire"))):
        return {}
    island_of, grid, tile_map = compute_islands_cached(save, save_path)[1], LazyTileGrid(save), save.get("tileMap") or []
    return {(x, y): (_land_key(island_of.get((x, y)), name := tile_map[grid[y][x]]), tile_biome(name) or tile_kind(name)) for x, y in positions}


# Every section asked of one save, as `main` prints it — `positions` left `None` where nothing answers, for `main` to refuse or `--since` to read as none.
def _collect(save: dict, save_path: Path, sections: tuple[str, ...], kinds: set[str] | None, island: int | str | None) -> dict:
    out: dict = {}
    if "biomes" in sections:
        out["biomes"] = _build_biomes(save, save_path)
    if "bodies" in sections:
        out["bodies"] = _build_bodies(save, save_path)
    if "burning" in sections:
        out["burning"] = _build_burning(save, save_path, island)
    if "entity_types" in sections:
        out["entity_types"] = _build_entity_types(save)
    if "frozen" in sections:
        out["frozen"] = _build_frozen(save, save_path)
    if "gear" in sections:
        out["gear"] = _build_gear(save, save_path)
    if "islands" in sections:
        out["islands"] = compute_islands_cached(save, save_path)[0]
    if "positions" in sections and kinds is not None:
        out["positions"] = _build_positions(save, save_path, kinds, island)
    if "ridges" in sections:
        out["ridges"] = compute_islands_cached(save, save_path)[1].ridges()
    if "totals" in sections:
        out["totals"] = _build_totals(save, save_path)
    if "waters" in sections:
        out["waters"] = waters_cached(save, save_path)
    return out


# The sweep itself, run once per save: every land tile of the map asked its biome, which is why `_build_biomes` keeps the answer on disk.
def _compute_biomes(save: dict, save_path: Path) -> dict:
    islands, island_of = compute_islands_cached(save, save_path)
    # Biomes come already merged, `soil_high:paradox_high` and its low twin both reading `paradox`; a tile with none is told by its ground, patched alike.
    biome_by_id = [tile_ground(name) for name in save.get("tileMap") or []]
    # The patches tally the biomes too, land by land, in the order the sweep first meets each — so ties between biomes fall as met. Islets go under `None`.
    patches, grounds, names = _biome_patches(save, island_of, biome_by_id)
    tallies: defaultdict[int | None, Counter] = defaultdict(Counter)
    for (island_id, biome), found in patches.items():
        tallies[island_id][biome] = sum(size for size, *_ in found)
    sizes: dict[int | None, int] = {island["id"]: island["size"] for island in islands}
    if None in tallies:  # off every land, the share is of all the islets, as `totals`, `burning` and `frozen` count them
        sizes[None] = _surfaces(save)[0] - sum(sizes.values())
    frames = {island["id"]: island for island in islands}  # each land's centroid and bounds, that a biome's patches be placed on it
    kinds = ["water", *(name.removeprefix(BARE) for name in names)]  # a code's name as the rows print it, and `0` what bears no ground at all
    tops = {key: _top_patches(found, frames.get(key[0]), grounds, kinds) for key, found in patches.items()}

    # No share where it rounds to nothing: the tiles say it, and a lone `paradox` tile is still a subject. A lone patch is the whole biome, whose size the row says.
    lands = sorted(tallies.items(), key=lambda kv: (kv[0] is None, kv[0] or 0))
    per_island = {
        _land_name(island_id): [
            {
                **({"ground": biome[1:]} if biome.startswith(BARE) else {"biome": biome}),
                "largest": {k: v for k, v in tops[(island_id, biome)][0].items() if k not in _DETAIL and (k != "tiles" or len(patches[(island_id, biome)]) > 1)},
                "patches": len(patches[(island_id, biome)]),
                "pct": round(n / sizes[island_id] * 100, 1) or None,
                "tiles": n,
            }
            for biome, n in counts.most_common()
        ]
        for island_id, counts in lands
    }
    # Beside a ground's largest patches, the box of them all: where the lesser ones lie, which no list names — none for a lone patch, whose own box says it.
    top_patches = {
        _land_name(island_id): {
            biome.removeprefix(BARE): {"bounds": _whole_bounds(patches[(island_id, biome)]), "largest_patches": tops[(island_id, biome)]} for biome in counts
        }
        for island_id, counts in lands
    }

    # Told once rather than on every land that carries the biome: a dozen descriptions would otherwise ride along some eighty times.
    named = {row["biome"] for rows in per_island.values() for row in rows if "biome" in row}
    return {"descriptions": {b: text for b in sorted(named) if (text := biome_lore(b).get("description"))}, "islands": per_island, "patches": top_patches}


# Each fire's tiles by square of `_FIRE_REACH`, to the fire's index in `clusters`: a tile's kin lie in its 9 squares.
def _fire_cells(clusters: list[list[tuple[int, int]]]) -> dict[tuple[int, int], list[tuple[tuple[int, int], int]]]:
    cells: defaultdict[tuple[int, int], list[tuple[tuple[int, int], int]]] = defaultdict(list)
    for index, fire in enumerate(clusters):
        for x, y in fire:
            cells[x // _FIRE_REACH, y // _FIRE_REACH].append(((x, y), index))
    return cells


# The burning tiles as fires, those within `_FIRE_REACH` of one another one fire, each in its tiles' order.
def _fire_clusters(burning: Collection[tuple[int, int]]) -> list[list[tuple[int, int]]]:
    cells: defaultdict[tuple[int, int], list[tuple[int, int]]] = defaultdict(list)
    for x, y in burning:
        cells[x // _FIRE_REACH, y // _FIRE_REACH].append((x, y))
    clusters, seen = [], set()
    for start in sorted(burning):
        if start in seen:
            continue
        seen.add(start)
        stack, fire = [start], []
        while stack:
            x, y = stack.pop()
            fire.append((x, y))
            cx, cy = x // _FIRE_REACH, y // _FIRE_REACH
            for near in (tile for dx in (-1, 0, 1) for dy in (-1, 0, 1) for tile in cells.get((cx + dx, cy + dy), ())):
                if near not in seen and max(abs(near[0] - x), abs(near[1] - y)) <= _FIRE_REACH:
                    seen.add(near)
                    stack.append(near)
        clusters.append(fire)
    return clusters


# The land a fire is told under, the one holding most of it — a tie to the first land, so no fire is told twice.
def _fire_home(fire: list[tuple[int, int]], burning: dict[tuple[int, int], tuple[str, str]]) -> str:
    lands = Counter(burning[tile][0] for tile in fire)
    return min(lands, key=lambda land_key: (-lands[land_key], _land_order((land_key, None))))


# A fire's line, sited on its own land's tile nearest its middle, where the heading is read; the rest of it is `spills`.
def _fire_row(fire: list[tuple[int, int]], burning: dict[tuple[int, int], tuple[str, str]], key: str, land: dict | None) -> dict:
    home = [tile for tile in fire if burning[tile][0] == key]
    mean_x, mean_y = sum(x for x, _ in home) / len(home), sum(y for _, y in home) / len(home)
    x, y = min(home, key=lambda tile: ((tile[0] - mean_x) ** 2 + (tile[1] - mean_y) ** 2, tile))
    spills = Counter(burning[tile][0] for tile in fire if burning[tile][0] != key)
    side = {"dir": land_side(x, y, land)} if land else {}
    return {"x": x, "y": y, **side, "grounds": _tally(burning[tile][1] for tile in fire), "spills": dict(spills) or None, "tiles": len(fire)}


# What burned between two saves, land by land: the tiles caught since (`caught`) and those gone out (`out`) — two instants, a tile out and caught again unseen.
def _fire_turnover(then: dict[tuple[int, int], tuple[str, str]], now: dict[tuple[int, int], tuple[str, str]], island: int | str | None) -> dict[str, dict]:
    counts: defaultdict[str, Counter] = defaultdict(Counter)
    for side, tiles, land_of in (("caught", now.keys() - then.keys(), now), ("out", then.keys() - now.keys(), then)):
        for tile in tiles:
            counts[land_of[tile][0]][side] += 1
    return {key: {"tiles": dict(sides)} for key, sides in counts.items() if island is None or key == str(island)}


# The map's burning tiles as fires, those within `_FIRE_REACH` of one another one fire, each told under the land holding most of it: the rest is `spills`.
def _fires(
    burning: dict[tuple[int, int], tuple[str, str]],
    key: str,
    land: dict | None,
    water: Callable[[list], dict | None],
    before: dict[tuple[int, int], tuple[str, str]] | None,
) -> dict:
    clusters = _fire_clusters(burning)
    homed = sorted((i for i, fire in enumerate(clusters) if _fire_home(fire, burning) == key), key=lambda i: (-len(clusters[i]), min(clusters[i])))
    told = [{**_fire_row(clusters[i], burning, key, land), "to_water": water(clusters[i])} for i in homed[:_TOP_PATCHES]]
    rest, gone = [clusters[i] for i in homed[_TOP_PATCHES:]], None
    if before is not None:  # `--since`: an earlier fire's tiles gone out held by the fire now nearest it, else that earlier fire gone out whole
        owner, held, out = _fire_cells(clusters), Counter(), []
        for earlier in _fire_clusters(before):
            if reaches := [found for tile in earlier if (found := _nearest_fire(tile, owner)) is not None]:
                held[min(reaches)[1]] += sum(tile not in burning for tile in earlier)
            elif _fire_home(earlier, before) == key:
                out.append(earlier)
        for row, i in zip(told, homed, strict=False):
            caught = sum(tile not in before for tile in clusters[i])
            row["since"] = quiet_zeros({"caught": caught, "out": held[i], "still": len(clusters[i]) - caught})
        gone = [_fire_row(fire, before, key, land) for fire in sorted(out, key=lambda fire: (-len(fire), min(fire)))[:_TOP_PATCHES]] or None
    return {"fires": told, "gone": gone, "unlisted": {"fires": len(rest), "tiles": sum(map(len, rest))} if rest else None}


# `biomes --since`: each land's grounds by name, a ground told where it gained or lost tiles — its share where that moved, else its tiles past `_GROUND_SWING`.
def _ground_balance(then: dict, now: dict) -> dict | None:
    def grounds(biomes: dict) -> dict[str, dict[str, dict]]:
        return {land: {row.get("biome") or row.get("ground") or "others": row for row in rows} for land, rows in (biomes.get("islands") or {}).items()}

    before, after, lands = grounds(then), grounds(now), {}
    for land in sorted({*before, *after}, key=lambda key: _land_order((key, None))):
        old, new, kept = before.get(land, {}), after.get(land, {}), {}
        for ground in sorted({*old, *new}):
            was, came = old.get(ground) or {}, new.get(ground) or {}
            tiles = [was.get("tiles") or 0, came.get("tiles") or 0]
            pct = [was.get("pct") or 0, came.get("pct") or 0]  # a share under a tenth goes unwritten: it is 0
            if tiles[0] == tiles[1]:  # a share that moves with the land's total alone, the ground's own tiles still, is no balance of it
                continue
            if pct[0] != pct[1]:
                kept[ground] = {"pct": pct}
            elif abs(tiles[1] - tiles[0]) >= _GROUND_SWING * max(tiles[0], 1):
                kept[ground] = {"tiles": tiles}
        if kept:
            lands[land] = kept
    return {"islands": lands} if lands else None


# One ground the world over: every land that bears it, the islets too, each with its row — the whole of it, which a « nowhere else » stands on. `None` for none.
def _ground_lands(biomes: dict, kind: str) -> dict | None:
    lands, name = {}, "ground"
    for land, rows in biomes["islands"].items():
        if row := _ground_row(rows, kind):
            name = "biome" if "biome" in row else "ground"
            lands[land] = {key: value for key, value in row.items() if key != name}
    return {name: kind, "islands": lands} if lands else None


# The row of one ground among a land's, asked by its biome or its bare ground alike — `None` where the land bears none.
def _ground_row(rows: Iterable[dict], kind: str) -> dict | None:
    return next((row for row in rows if kind in (row.get("biome"), row.get("ground"))), None)


# A counted land by its id; off every one, the place itself — `islets`, the rocks too small to count, or `water` — so that a bearer on a rock reads as no swimmer.
def _land_key(island_id: int | None, tile_name: str) -> str:
    return str(island_id) if island_id else "islets" if off_land(tile_name) == "islet" else "water"


def _land_name(island_id: int | None) -> str:
    return "islets" if island_id is None else str(island_id)


# The counted lands by id, then the islets, then the water: a land-by-land section always ends on what lies off every land.
def _land_order(item: tuple[str, object]) -> tuple[bool, int, str]:
    key = item[0]
    return (not key.isdigit(), int(key) if key.isdigit() else 0, key)


# The sections cut to one land: its row, biomes, frost, fire and gear, and the waters and ridges it borders — new dicts all, the cached ones left as they are.
def _narrowed(out: dict, land: int | str) -> dict:
    key, narrowed = str(land), dict(out)
    if "biomes" in out:
        rows = out["biomes"]["islands"].get(key) or []
        grown = {row.get("biome") for row in rows}
        narrowed["biomes"] = {"descriptions": {b: text for b, text in out["biomes"]["descriptions"].items() if b in grown}, "islands": {key: rows} if rows else {}}
    for section in ("bodies", "burning", "frozen", "gear"):
        if section in out:
            narrowed[section] = {key: out[section][key]} if key in out[section] else {}
    if "islands" in out:
        narrowed["islands"] = [row for row in out["islands"] if row["id"] == land]
    if "ridges" in out:
        narrowed["ridges"] = [ridge for ridge in out["ridges"] if land in ridge["between"]]
    if "waters" in out:
        waters = out["waters"]
        narrowed["waters"] = {
            **waters,
            **{kind: [body for body in waters[kind] if land in body["shores"]] for kind in ("lakes", "rivers", "seas")},
            # The ponds are counted world-wide, none sited on a land: their floor alone holds for one
            "unlisted": {**waters["unlisted"], "lakes": {key: value for key, value in waters["unlisted"]["lakes"].items() if key != "count"}},
            "necks": [{key: value for key, value in neck.items() if key != "island"} for neck in waters["necks"] if neck["island"] == land],
            "straits": [strait for strait in waters["straits"] if land in strait["between"]],
        }
    return narrowed


# The fire nearest `tile` within `_FIRE_REACH`, as its reach and its index in the clusters `owner` was built from — none past that reach.
def _nearest_fire(tile: tuple[int, int], owner: dict[tuple[int, int], list[tuple[tuple[int, int], int]]]) -> tuple[int, int] | None:
    x, y = tile
    cx, cy = x // _FIRE_REACH, y // _FIRE_REACH
    cells = (found for dx in (-1, 0, 1) for dy in (-1, 0, 1) for found in owner.get((cx + dx, cy + dy), ()))
    return min(((reach, index) for (fx, fy), index in cells if (reach := max(abs(fx - x), abs(fy - y))) <= _FIRE_REACH), default=None)


# The `waters` block cut by `-w`: one water's row, or one family with the count it leaves unlisted — `None` where this reading holds none.
def _one_water(waters: dict, water: tuple[str, int | None]) -> dict | None:
    family, water_id = f"{water[0]}s", water[1]
    if water_id is None:
        held = waters[family]
        return {family: held, **({"unlisted": {family: unlisted}} if (unlisted := waters["unlisted"].get(family)) else {})} if held else None
    return next((body for body in waters[family] if body["id"] == water_id), None)


# One ground of a land told whole: its row, the one `largest` giving way to its largest patches, and what they leave unlisted — `None` where the land bears none.
def _patch_detail(save: dict, save_path: Path, land: int | str, kind: str) -> dict | None:
    biomes = _biomes(save, save_path)
    if (row := _ground_row(biomes["islands"].get(str(land), ()), kind)) is None:
        return None
    told = biomes["patches"][str(land)][kind]
    rest = {"patches": row["patches"] - len(told["largest_patches"]), "tiles": row["tiles"] - sum(patch["tiles"] for patch in told["largest_patches"])}
    return {**{key: value for key, value in row.items() if key != "largest"}, **told, "unlisted": rest if rest["patches"] else None}


# A patch's own tile nearest its middle, ties to the lower `(x, y)` — a mean alone could fall on another ground, or at sea. Each run offers its nearest column.
def _site(mean_x: float, mean_y: float, runs: list[tuple[int, int, int]]) -> dict:
    column, offers = math.ceil(mean_x - 0.5), []  # the column nearest the mean, a tie going west as `(x, y)` orders it
    for y, a, b in runs:
        x = min(max(column, a), b - 1)
        offers.append(((x - mean_x) ** 2 + (y - mean_y) ** 2, (x, y)))
    x, y = min(offers)[1]
    return {"x": x, "y": y}


# The land a tile lies on, as every land-by-land section keys it — the grid decoded for a tile off every land alone, whose row tells an islet from the water.
def _site_key(tile: tuple[int, int], island_of: TileIslands, grid: LazyTileGrid, tile_map: list) -> str:
    x, y = tile
    return str(island_id) if (island_id := island_of.get((x, y))) else _land_key(None, tile_map[grid[y][x]])


# The map's land and goo counted off the runs, its water the rest of a grid the header sizes — one count, that `totals` and `frozen` never disagree over.
def _surfaces(save: dict) -> tuple[int, int, int]:
    layers = [tile_layer(name) for name in save.get("tileMap") or []]
    land, goo = tile_count(save, [layer in LAND_LAYERS for layer in layers]), tile_count(save, [layer == "Goo" for layer in layers])
    return land, goo, len(save.get("tileArray") or []) * sum((save.get("tileAmounts") or [[]])[0]) - land - goo


# The world-wide `biomes`: each land's grounds from `_SURVEY_PCT` up, the lesser ones named in one row — a rare biome still shows, `-i` then tells it whole.
def _surveyed(biomes: dict) -> dict:
    lands = {}
    for land, rows in biomes["islands"].items():
        kept = [row for row in rows if (row.get("pct") or 0) >= _SURVEY_PCT]
        minor = rows[len(kept) :]  # the rows come largest first, so the lesser ones close the list
        others = {"others": sorted(row.get("biome") or row["ground"] for row in minor), "tiles": sum(row["tiles"] for row in minor)}
        lands[land] = kept + ([others] if minor else [])
    return {"islands": lands}


def _tally(grounds: Iterable[str]) -> str:
    return " | ".join(f"{n} {ground}" for ground, n in Counter(grounds).most_common())


# A ground's `_TOP_PATCHES` largest patches placed on its land, ties in size to the lower `(x, y)`, each with its box as a land's `bounds` — the rest is a count.
def _top_patches(found: list[list], land: dict | None, grounds: list[bytes], kinds: list[str]) -> list[dict]:
    floor = sorted((size for size, *_ in found), reverse=True)[:_TOP_PATCHES][-1]  # only those that may make the list are sited
    sited = [(size, _site(sum_x / size, sum_y / size, runs), runs) for size, sum_x, sum_y, runs in found if size >= floor]
    return [
        {
            **site,
            **({"dir": land_side(site["x"], site["y"], land)} if land else {}),
            "borders": _borders(runs, grounds, kinds),
            "bounds": {"x": [min(a for _, a, _ in runs), max(b for *_, b in runs) - 1], "y": [runs[0][0], runs[-1][0]]},  # the runs come south to north
            "tiles": size,
        }
        for size, site, runs in sorted(sited, key=lambda p: (-p[0], p[1]["x"], p[1]["y"]))[:_TOP_PATCHES]
    ]


# The water nearest a fire's edge, crow-flown from its every tile at once and named as `tiles … distances` names it — none past `_SHORE_REACH`.
def _water_near(fire: list[tuple[int, int]], grid: LazyTileGrid, wet: list[bool], bodies: Callable[[int, int], dict]) -> dict | None:
    best = dict.fromkeys(fire, 0.0)
    heap = [(0.0, x, y) for x, y in fire]
    heapify(heap)
    while heap:
        cost, x, y = heappop(heap)
        if cost > best[x, y]:
            continue
        if wet[grid[y][x]]:
            return {**bodies(x, y), "crow_tiles": round(cost)}
        for dx, dy in _STEPS:
            nx, ny = x + dx, y + dy
            step = cost + (DIAGONAL_EXTRA + 1 if dx and dy else 1.0)
            if 0 <= nx < grid.width and 0 <= ny < grid.height and step <= _SHORE_REACH and step < best.get((nx, ny), math.inf):
                best[nx, ny] = step
                heappush(heap, (step, nx, ny))
    return None


# The box of every patch of one ground on a land, as a land's `bounds` — `None` for a lone patch.
def _whole_bounds(found: list[list]) -> dict | None:
    if len(found) < 2:
        return None
    _, wests, ends = zip(*(run for *_, runs in found for run in runs), strict=True)  # the columns unzipped for C to weigh; a patch's runs come south to north
    return {"x": [min(wests), max(ends) - 1], "y": [min(runs[0][0] for *_, runs in found), max(runs[-1][0] for *_, runs in found)]}


def main(argv: list[str]) -> int:
    try:
        since, argv = take_since(argv)
    except ValueError as e:
        print(f"✗ {e}", file=sys.stderr)
        return 2
    save_path, argv, _ = take_chapter(argv)  # pop the `C<n>` token first — argparse has no such positional and would abort on it

    parser = arg_parser(prog="geography/info.py", description="Geographic stats reserved for the chronicler.")
    parser.add_argument("sections", nargs="?", help=f"Comma-separated sections. Valid: {', '.join(_ALL_SECTIONS)}")
    parser.add_argument(
        "--type",
        "-t",
        help=f"What `positions` sites, bodies aside: an asset id, a family (`trees`), a resource (`wood`) or a comma list; past {MAX_LISTED}, a count by land. "
        f"Under `biomes`, one biome or ground: the lands it lies on, or with `-i <land>` its {_TOP_PATCHES} largest patches.",
    )
    parser.add_argument("--island", "-i", type=land_arg, metavar="id", help="One land alone in the sections that go land by land, or `islets` or `water`.")
    parser.add_argument(
        "--water", "-w", type=water_arg, metavar="lake<id>|lake|…", help="`waters` cut to one water by its id, or to one family: `lake`, `river`, `sea`."
    )
    args = parser.parse_args(argv)

    if args.sections in (None, "full"):  # No `full` here, nor its silent default: these sections answer unrelated questions, and no reading wants them all.
        print(f"✗ geography has no `full` — name a section: {', '.join(_ALL_SECTIONS)}", file=sys.stderr)
        return 2
    try:
        sections = parse_sections(args.sections, _ALL_SECTIONS, allow_full=False)

    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 2
    wanted: str | None = args.type

    if wanted is None and "positions" in sections:
        print("✗ positions needs --type, a kind, a family or a resource — `entity_types` lists the kinds", file=sys.stderr)
        return 2

    if args.island is not None and not set(_BY_LAND) & set(sections):  # refused before the save is read
        print(f"✗ `--island` narrows {', '.join(_BY_LAND)}: name one of them", file=sys.stderr)
        return 2

    if args.water is not None and "waters" not in sections:
        print("✗ `--water` narrows `waters`: name that section", file=sys.stderr)
        return 2

    bucketed = {*_BUCKETED, "biomes"} if args.island == "islets" else set(_BUCKETED)  # the islets bear grounds too, the water none
    if isinstance(args.island, str) and (unbucketed := sorted(set(sections) & set(_BY_LAND) - bucketed)):
        print(f"✗ {', '.join(unbucketed)}: no {args.island} to narrow to — `-i {args.island}` narrows {', '.join(sorted(bucketed))}", file=sys.stderr)
        return 2

    if wanted is not None and "biomes" in sections and ("positions" in sections or since):
        print("✗ `biomes -t <ground>` tells one ground of one chapter: ask `positions` and `--since` apart", file=sys.stderr)
        return 2

    then_path = SAVES_DIR / since / "map.wbox" if since else None
    if then_path and not then_path.exists():
        print(f"✗ no save for {since}", file=sys.stderr)
        return 2
    save = load_save(save_path)

    if isinstance(args.island, int) and args.island not in {land["id"] for land in compute_islands_cached(save, save_path)[0]}:
        print(f"✗ no land with id {args.island} — `geography … islands` lists them", file=sys.stderr)
        return 2
    kinds, families = None, asset_families(save) if "positions" in sections else {}

    if "positions" in sections and wanted is not None:
        kinds, bodies = asset_kinds(families, wanted), {a.get("asset_id") for a in save.get("actors_data") or [] if not is_boat(a)}  # hulls stay sited here
        if said := [word for word in wanted.split(",") if asset_kinds(families, word) & bodies]:  # a body's roll is `roster`'s, with its sex and dates
            print(f"✗ {', '.join(said)}: bodies are listed by `world … roster -t`, `positions` sites the rest", file=sys.stderr)
            return 2

    # `positions` is weighed apart under `--since`, an instance at a time: its two forms, a roll or a tally by land, would be held against each other.
    out = _collect(save, save_path, tuple(s for s in sections if s != "positions") if then_path else sections, kinds, args.island)

    if then_path:  # both chapters read alike, then only what moved between them: a section that holds still says so, never a silent `{}`
        earlier = load_save(then_path)
        then = _collect(earlier, then_path, tuple(out), kinds, args.island)
        if args.island is not None:
            out, then = _narrowed(out, args.island), _narrowed(then, args.island)
        if args.water is not None:  # a water the earlier reading lacks came since: every field of it new
            out["waters"], then["waters"] = _one_water(out["waters"], args.water) or {}, _one_water(then["waters"], args.water) or {}
        balance = _ground_balance(then.pop("biomes"), out.pop("biomes")) if "biomes" in out else None  # its own balance, ground by ground
        moved = found if isinstance(found := moved_between(then, out), dict) else {}  # both readings are dicts, so what moved is one, or nothing
        if balance:
            moved = {**moved, "biomes": balance}
        then_fire, now_fire = (_burning_tiles(earlier, then_path), _burning_tiles(save, save_path)) if "burning" in sections else ({}, {})
        if "burning" in sections and (turnover := _fire_turnover(then_fire, now_fire, args.island)):  # the balance alone hides what went out
            fires: dict[str, dict] = moved.get("burning") or {}
            lands = sorted({*fires, *turnover}, key=lambda key: _land_order((key, None)))
            moved = {**moved, "burning": {key: {**(fires.get(key) or {}), **turnover.get(key, {})} for key in lands}}
            # Under `-i`, a fire is one line, its own balance on it — never a row gone and one new for a blaze that only grew
            if args.island is not None and (key := str(args.island)) in moved["burning"]:
                told = _build_burning(save, save_path, args.island, then_fire).get(key)
                kept = {part: told[part] for part in ("fires", "gone", "unlisted") if isinstance(told, dict) and told.get(part)}
                # The land's grounds off its tiles, both sides: a lone fire's line holds them in its reading, which would weigh as a land gone out
                grounds = (_tally(ground for land, ground in tiles.values() if land == key) for tiles in (then_fire, now_fire))
                moved["burning"][key] = {"grounds": moved_between(*grounds), "tiles": moved["burning"][key].get("tiles"), **kept}
        if "positions" in sections and kinds is not None:
            was, now = ({record["id"] for record, _ in asset_sites(reading, kinds)} for reading in (earlier, save))
            gone, came = _build_positions(earlier, then_path, kinds, args.island, was - now), _build_positions(save, save_path, kinds, args.island, now - was)
            if came_or_went := {side: sites for side, sites in (("gone", gone), ("new", came)) if sites}:
                moved = {**moved, "positions": came_or_went}
        if not moved:
            print(f"✗ nothing moved in {', '.join(sections)} since {since}", file=sys.stderr)
            return 1
        emit(moved)
        return 0

    if "positions" in out and out["positions"] is None:  # a word nothing answers to, never a silent `{}`
        none = unsited_reason(families, wanted or "") or f"no {wanted} in this world"
        print(f"✗ {none} — `entity_types` lists every kind, and the families: {', '.join(sorted(families))}", file=sys.stderr)
        return 1

    where = "in this world" if args.island is None else f"on land {args.island}" if isinstance(args.island, int) else f"on the {args.island}"
    if "positions" in out and not out["positions"]:
        print(f"✗ no {wanted} {where} — without `-i`, `positions` says which lands hold one", file=sys.stderr)
        return 1

    shown = out if args.island is None else _narrowed(out, args.island)
    if args.water is not None:
        if (one := _one_water(shown["waters"], args.water)) is None:
            print(f"✗ no {' '.join(map(str, filter(None, args.water)))} {where} — `geography … waters` lists them", file=sys.stderr)
            return 1
        shown = shown | {"waters": one}
    elif "waters" in shown and args.island is None and len(straits := shown["waters"]["straits"]) > MAX_LISTED:  # already narrowest first
        more = f"past {MAX_LISTED} straits, the {_TOP_STRAITS} narrowest, {len(straits) - _TOP_STRAITS} more — `-i <land>` lists a land's every one"
        shown = shown | {"waters": {**shown["waters"], "info": more, "straits": straits[:_TOP_STRAITS]}}
    # An empty section says so, the command failing only where all asked are, as `positions` does — a dict of empty blocks counts: `biomes` on a bare land.
    bare = [s for s in sections if s in _NONE and not (any(shown[s].values()) if isinstance(shown[s], dict) else shown[s])]

    for section in bare:
        print(f"✗ no {_NONE[section]} {where if section in _BY_LAND else 'in this world'}", file=sys.stderr)  # `-i` narrows a land's sections alone

    if len(bare) == len(sections):
        return 1

    if "biomes" in shown and "biomes" not in bare:
        if wanted is None:
            if args.island is None:  # `-i` alone keeps its land whole
                shown = shown | {"biomes": _surveyed(shown["biomes"])}
        elif args.island is None:
            if (found := _ground_lands(shown["biomes"], wanted)) is None:
                print(f"✗ no {wanted} in this world — `biomes -i <land>` lists a land's grounds", file=sys.stderr)
                return 1
            shown = shown | {"biomes": found}
        elif detail := _patch_detail(save, save_path, args.island, wanted):
            shown = shown | {"biomes": detail}
        else:
            print(f"✗ no {wanted} {where} — `biomes -i {args.island}` lists the grounds there", file=sys.stderr)
            return 1

    emit(shown)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
