#!/usr/bin/env python3

# Geographic stats reserved for the chronicler (not consumed by the UI). User-facing docs: `docs/tools.md`.

import math
import re
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))

from grid import LAND_LAYERS, LazyTileGrid, frozen_tally, listed_tiles, off_land, tile_biome, tile_count, tile_frost, tile_kind, tile_layer, tile_mask
from islands import compute_islands_cached
from shared import (
    actor_xy,
    arg_parser,
    asset_families,
    asset_kinds,
    asset_sites,
    bearing,
    biome_lore,
    emit,
    index_by_id,
    is_boat,
    is_sapient,
    load_save,
    parse_sections,
    pickle_cached,
    take_chapter,
    union_root,
)
from waters import waters_cached

_ALL_SECTIONS = ("biomes", "bodies", "burning", "entity_types", "frozen", "gear", "islands", "positions", "ridges", "totals", "waters")
_BIOME_RUN = re.compile(rb"([\x01-\xff])\1*")  # a row's unbroken stretch of one biome, its code one byte, `0` where the ground bears none
_BY_LAND = ("biomes", "bodies", "burning", "frozen", "gear", "islands", "positions", "ridges", "waters")  # what `-i` narrows: the rest is world-wide
_CENTRE_SHARE = 0.25  # how near its land's centroid, in halves of that land's span, a patch still reads as its centre rather than a side
_MAX_LISTED = 10  # past so many, `positions` counts land by land: a roll that long is read for where they stand, not for which is which
_MAX_NAMED_CARRIERS = 5  # past a handful, naming them says less than counting them: on such a land, bearing arms is no longer the fact a chapter turns on
_PERMAFROST_RUN = re.compile(rb"\x03+")  # a row's unbroken permafrost in the frost mask


# Every biome's patches, land by land: each row's runs of one biome joined to those they touch above, corners included, never across lands — C walks the map.
def _biome_patches(save: dict, island_of, biome_by_id: list[str | None]) -> dict[tuple[int | None, str], list[list]]:
    names = sorted({biome for biome in biome_by_id if biome})
    code_of = {biome: k + 1 for k, biome in enumerate(names)}
    rows: list[list[tuple[int, int, int, int]]] = []  # each row's runs, as `(west, east + 1, land << 8 | biome code, run index)`
    count = 0
    for marks in tile_mask(save, [code_of.get(biome or "", 0) for biome in biome_by_id]):
        lands, row = island_of.row(len(rows)), []
        for match in _BIOME_RUN.finditer(marks):
            west, end = match.span()
            row.append((west, end, lands[west] << 8 | marks[west], count))  # side by side, two ground tiles are one land: a run never straddles two
            count += 1
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
    return by_key


# Every biome a land carries, marginal ones included — a paradox patch is a chapter's subject. Shares are of the whole island, sand and rock cutting them under 100.
def _build_biomes(save: dict, save_path: Path) -> dict:
    return pickle_cached("biomes_v13", save_path, lambda: _compute_biomes(save, save_path))


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
def _build_burning(save: dict, save_path: Path) -> dict:
    if not (positions := list(listed_tiles(save, "fire"))):  # nothing listed, nothing to site: the islands are never unpickled
        return {}
    _, island_of = compute_islands_cached(save, save_path)
    grid, tile_map = LazyTileGrid(save), save.get("tileMap") or []
    by_land: defaultdict[str, Counter] = defaultdict(Counter)
    for x, y in positions:
        name = tile_map[grid[y][x]]
        by_land[_land_key(island_of.get((x, y)), name)][tile_biome(name) or tile_kind(name)] += 1
    # Counts, not the shares `islands` gives: a few dozen tiles read better whole than as percentages of themselves.
    return {key: " | ".join(f"{n} {ground}" for ground, n in counts.most_common()) for key, counts in sorted(by_land.items(), key=_land_order)}


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


# Up to `_MAX_LISTED`, or all on the `-i` land, each instance by `id`, `island_id` else `islet_tiles` else water, `asset_id` if kinds mix; past it, a tally by land.
def _build_positions(save: dict, save_path: Path, kinds: set[str], land: int | None) -> list[dict] | dict[str, str] | None:
    if not (sites := asset_sites(save, kinds)):  # the lookup costs 0.2 s cold, so a kind nobody built never pays for it
        return None
    _, island_of = compute_islands_cached(save, save_path)
    grid, tile_map = LazyTileGrid(save), save.get("tileMap") or []
    if land is not None:
        sites = [(record, tile) for record, tile in sites if island_of.get(tile) == land]
    elif len(sites) > _MAX_LISTED:
        by_land: defaultdict[str, Counter] = defaultdict(Counter)
        for record, tile in sites:
            by_land[_site_key(tile, island_of, grid, tile_map)][record.get("asset_id")] += 1
        tally = {key: " | ".join(f"{n} {kind}" for kind, n in counts.most_common()) for key, counts in sorted(by_land.items(), key=_land_order)}
        return {**tally, "info": f"{len(sites)} in all — `-i <id>` lists one land's one by one"}
    # `dormant` as `ground … metadata` tells it, so that a roll of volcanoes or geysers says which sleep without a call per mouth.
    mixed = len(kinds) > 1
    out = [
        {
            "asset_id": record.get("asset_id") if mixed else None,
            "dormant": "stop_spawn_drops" in (record.get("custom_data_flags") or ()) or None,
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
            position["island_id"] = island_id
        elif off_land(tile_map[grid[y][x]]) == "islet":  # silent in the water, as `island_id` is: a hull at sea, a dock on shallows
            position["islet_tiles"] = island_of.islet_size((x, y))
    return sorted(out, key=lambda r: (r["y"], r["x"]))


# The map's own sums, which no list adds up: its water, its land, and that land split between the counted lands and the islets too small to be one.
def _build_totals(save: dict, save_path: Path) -> dict:
    islands, island_of = compute_islands_cached(save, save_path)
    # `(size, x, y)` each, the largest first and ties to the lower `(x, y)`: counted here so that no reader sweeps the map for a tally of rocks.
    rocks = sorted(island_of.islets(), key=lambda rock: (-rock[0], rock[1], rock[2]))
    frozen, tiles = frozen_tally(save)
    (land, goo, water), counted, tiles = _surfaces(save), sum(island["size"] for island in islands), tiles or 1
    # Each share of what holds it: the land, the water and the frozen of the map, the counted lands and the islets of the land. Goo, its own layer, where it spread.
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
        "water": {"pct": round(water / tiles * 100, 1), "tiles": water},
    }


# The sweep itself, run once per save: every land tile of the map asked its biome, which is why `_build_biomes` keeps the answer on disk.
def _compute_biomes(save: dict, save_path: Path) -> dict:
    islands, island_of = compute_islands_cached(save, save_path)
    biome_by_id = [tile_biome(name) for name in save.get("tileMap") or []]  # already merged: `soil_high:paradox_high` and its low twin both read `paradox`
    # The patches tally the biomes too, land by land, in the order the sweep first meets each — so ties between biomes fall as met. Islets go under `None`.
    patches = _biome_patches(save, island_of, biome_by_id)
    tallies: defaultdict[int | None, Counter] = defaultdict(Counter)
    for (island_id, biome), found in patches.items():
        tallies[island_id][biome] = sum(size for size, *_ in found)
    sizes: dict[int | None, int] = {island["id"]: island["size"] for island in islands}
    if None in tallies:  # off every land, the share is of all the islets, as `totals`, `burning` and `frozen` count them
        sizes[None] = _surfaces(save)[0] - sum(sizes.values())
    frames = {island["id"]: island for island in islands}  # each land's centroid and bounds, that a biome's largest patch be placed on it

    # No share where it rounds to nothing: the tiles say it, and a lone `paradox` tile is still a subject.
    per_island = {
        "islets" if island_id is None else str(island_id): [
            {
                **_patch_fields(patches[(island_id, biome)], frames.get(island_id)),
                "biome": biome,
                "pct": round(n / sizes[island_id] * 100, 1) or None,
                "tiles": n,
            }
            for biome, n in counts.most_common()
        ]
        for island_id, counts in sorted(tallies.items(), key=lambda kv: (kv[0] is None, kv[0] or 0))
    }

    # Told once rather than on every land that carries the biome: a dozen descriptions would otherwise ride along some eighty times.
    named = {row["biome"] for rows in per_island.values() for row in rows}
    return {"descriptions": {b: text for b in sorted(named) if (text := biome_lore(b).get("description"))}, "islands": per_island}


# A counted land by its id; off every one, the place itself — `islets`, the rocks too small to count, or `water` — so that a bearer on a rock reads as no swimmer.
def _land_key(island_id: int | None, tile_name: str) -> str:
    return str(island_id) if island_id else "islets" if off_land(tile_name) == "islet" else "water"


# The counted lands by id, then the islets, then the water: a land-by-land section always ends on what lies off every land.
def _land_order(item: tuple[str, object]) -> tuple[bool, int, str]:
    key = item[0]
    return (not key.isdigit(), int(key) if key.isdigit() else 0, key)


# The sections cut to one land: its row, biomes, frost, fire and gear, and the waters and ridges it borders — new dicts all, the cached ones left as they are.
def _narrowed(out: dict, land: int) -> dict:
    key, narrowed = str(land), dict(out)
    if "biomes" in out:
        rows = out["biomes"]["islands"].get(key) or []
        grown = {row["biome"] for row in rows}
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
            "lakes": [lake for lake in waters["lakes"] if land in lake["shores"]],
            "straits": [strait for strait in waters["straits"] if land in strait["between"]],
        }
    return narrowed


# How many patches a biome breaks into, and its largest placed on its land — a count, never the list: a lone patch is the whole biome, whose size the row says.
def _patch_fields(found: list[list], land: dict | None) -> dict:
    top = max(size for size, *_ in found)
    # Only the largest sited, ties in size to the lower `(x, y)`.
    largest = min((_site(sum_x / size, sum_y / size, runs) for size, sum_x, sum_y, runs in found if size == top), key=lambda p: (p["x"], p["y"]))
    if len(found) > 1:
        largest["tiles"] = top
    return {"largest": {**largest, **_side(largest, land)} if land else largest, "patches": len(found)}


# Where a patch lies on its land (« the desert covers its north-east »): its heading from the land's centroid, `centre` within a quarter of each half-span
def _side(patch: dict, land: dict) -> dict:
    (west, east), (south, north), middle = land["bounds"]["x"], land["bounds"]["y"], land["centroid"]
    dx, dy = patch["x"] - middle["x"], patch["y"] - middle["y"]
    if math.hypot(dx / max((east - west) / 2, 1), dy / max((north - south) / 2, 1)) < _CENTRE_SHARE:
        return {"dir": "centre"}
    return {"dir": bearing(dx, dy)}


# A patch's own tile nearest its middle, ties to the lower `(x, y)` — a mean alone could fall on another ground, or at sea. Each run offers its nearest column.
def _site(mean_x: float, mean_y: float, runs: list[tuple[int, int, int]]) -> dict:
    column, offers = math.ceil(mean_x - 0.5), []  # the column nearest the mean, a tie going west as `(x, y)` orders it
    for y, a, b in runs:
        x = min(max(column, a), b - 1)
        offers.append(((x - mean_x) ** 2 + (y - mean_y) ** 2, (x, y)))
    x, y = min(offers)[1]
    return {"x": x, "y": y}


# The land a tile lies on, as every land-by-land section keys it — the grid decoded for a tile off every land alone, whose row tells an islet from the water.
def _site_key(tile: tuple[int, int], island_of, grid: LazyTileGrid, tile_map: list) -> str:
    x, y = tile
    return str(island_id) if (island_id := island_of.get((x, y))) else _land_key(None, tile_map[grid[y][x]])


# The map's land and goo counted off the runs, its water the rest of a grid the header sizes — one count, that `totals` and `frozen` never disagree over.
def _surfaces(save: dict) -> tuple[int, int, int]:
    layers = [tile_layer(name) for name in save.get("tileMap") or []]
    land, goo = tile_count(save, [layer in LAND_LAYERS for layer in layers]), tile_count(save, [layer == "Goo" for layer in layers])
    return land, goo, len(save.get("tileArray") or []) * sum((save.get("tileAmounts") or [[]])[0]) - land - goo


def main(argv: list[str]) -> int:
    save_path, argv, _ = take_chapter(argv)  # pop the `C<n>` token first — argparse has no such positional and would abort on it

    parser = arg_parser(prog="geography/info.py", description="Geographic stats reserved for the chronicler.")
    parser.add_argument("sections", help=f"Comma-separated sections. Valid: {', '.join(_ALL_SECTIONS)}")
    parser.add_argument("--type", "-t", help="What `positions` sites: an asset id, a family (`trees`) or a comma list — each one up to 10, past it a count by land.")
    parser.add_argument("--island", "-i", type=int, metavar="id", help="One land alone in the sections that go land by land — the whole list without it.")
    args = parser.parse_args(argv)

    if args.sections == "full":  # No `full` here, unlike the other tools: these sections answer unrelated questions, and no reading wants them all.
        print(f"✗ geography has no `full` — name a section: {', '.join(_ALL_SECTIONS)}", file=sys.stderr)
        return 2
    try:
        sections = parse_sections(args.sections, _ALL_SECTIONS, allow_full=False)
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 2
    wanted: str | None = args.type
    if wanted is None and "positions" in sections:
        print("✗ positions needs --type <asset_id> — run `entity_types` for the roll", file=sys.stderr)
        return 2

    if args.island is not None and not set(_BY_LAND) & set(sections):  # refused before the save is read
        print(f"✗ `--island` narrows {', '.join(_BY_LAND)}: name one of them", file=sys.stderr)
        return 2

    save = load_save(save_path)
    if args.island is not None and args.island not in {land["id"] for land in compute_islands_cached(save, save_path)[0]}:
        print(f"✗ no land with id {args.island} — `geography … islands` lists them", file=sys.stderr)
        return 2
    out: dict = {}
    if "biomes" in sections:
        out["biomes"] = _build_biomes(save, save_path)
    if "bodies" in sections:
        out["bodies"] = _build_bodies(save, save_path)
    if "burning" in sections:
        out["burning"] = _build_burning(save, save_path)
    if "entity_types" in sections:
        out["entity_types"] = _build_entity_types(save)
    if "frozen" in sections:
        out["frozen"] = _build_frozen(save, save_path)
    if "gear" in sections:
        out["gear"] = _build_gear(save, save_path)
    if "islands" in sections:
        islands, _ = compute_islands_cached(save, save_path)
        out["islands"] = islands
    if "positions" in sections and wanted is not None:
        families = asset_families(save)
        if (positions := _build_positions(save, save_path, asset_kinds(families, wanted), args.island)) is None:  # a word nothing answers to, never a silent `{}`
            print(f"✗ no {wanted} in this world — `entity_types` lists every kind, and the families: {', '.join(sorted(families))}", file=sys.stderr)
            return 1
        if not positions:
            print(f"✗ no {wanted} on land {args.island} — without `-i`, `positions` says which lands hold one", file=sys.stderr)
            return 1
        out["positions"] = positions
    if "ridges" in sections:
        out["ridges"] = compute_islands_cached(save, save_path)[1].ridges()
    if "totals" in sections:
        out["totals"] = _build_totals(save, save_path)
    if "waters" in sections:
        out["waters"] = waters_cached(save, save_path)

    emit(out if args.island is None else _narrowed(out, args.island))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
