#!/usr/bin/env python3

# Geographic stats reserved for the chronicler (not consumed by the UI). User-facing docs: `tools/tools.md`.

import math
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))

from grid import LazyTileGrid, listed_tiles, tile_biome, tile_kind, tile_layer, tile_mask
from islands import compute_islands_cached
from shared import (
    actor_xy,
    arg_parser,
    biome_lore,
    building_tile,
    civic_building_ids,
    emit,
    index_by_id,
    is_boat,
    load_data,
    load_save,
    parse_sections,
    pickle_cached,
    take_chapter,
    union_root,
)
from waters import waters_cached

_ALL_SECTIONS = ("biomes", "burning", "entity_types", "frozen", "gear", "islands", "positions", "totals", "waters")
_BIOME_RUN = re.compile(rb"([\x01-\xff])\1*")  # a row's unbroken stretch of one biome, its code one byte, `0` where the ground bears none
_COORDS = {"actors_data": actor_xy, "buildings": building_tile}  # Collection → the helper that sites a record, WB's omitted zero read as 0. No kind sits in both.
_MAX_NAMED_CARRIERS = 5  # past a handful, naming them says less than counting them: on such a land, bearing arms is no longer the fact a chapter turns on
_PATCH_SHARE = 1  # percent of its land a biome must stay under to be sited, however few its tiles
_PATCH_TILES = 50  # at most this many tiles of a biome on one land, it is a place rather than a landscape: each patch is sited, as a share alone could not find it


# Every biome a land carries, marginal ones included — a paradox patch is a chapter's subject. Shares are of the whole island, sand and rock cutting them under 100.
def _build_biomes(save: dict, save_path: Path) -> dict:
    return pickle_cached("biomes_v7", save_path, lambda: _compute_biomes(save, save_path))


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


# Every kind the save holds, grouped as WB groups them — its `buildings` collection also holds the flowers and the ore, so only the `civ_*` keep that name here.
def _build_entity_types(save: dict) -> dict:
    categories, civic = load_data("building-categories.json"), civic_building_ids()
    seed = {"actors": Counter(a["asset_id"] for a in save.get("actors_data") or [] if a.get("asset_id"))}
    groups: defaultdict[str, Counter] = defaultdict(Counter, seed)  # a factory, `setdefault` minting a `Counter` per building to keep the first
    for building in save.get("buildings") or []:
        if not (asset := building.get("asset_id")):
            continue
        group = "buildings" if asset in civic else categories.get(asset) or "other"  # `civic` knows the built kinds the manifest itself never declared
        groups[group][asset] += 1
    return {group: dict(counts) for group, counts in groups.items() if counts}


# A fire or a frost WB saves tile by tile, counted land by land and at sea under `adrift` — each tile by its biome, else by its ground as `islands` names it.
def _build_flagged_tiles(save: dict, save_path: Path, key: str) -> dict:
    if not (positions := list(listed_tiles(save, key))):  # nothing listed, nothing to site: the islands are never unpickled
        return {}
    _, island_of = compute_islands_cached(save, save_path)
    grid, tile_map = LazyTileGrid(save), save.get("tileMap") or []
    by_island: defaultdict[int | None, Counter] = defaultdict(Counter)
    for x, y in positions:
        name = tile_map[grid[y][x]]
        by_island[island_of.get((x, y))][tile_biome(name) or tile_kind(name)] += 1
    # Counts, not the shares `islands` gives: a few dozen tiles read better whole than as percentages of themselves.
    return {
        "adrift" if island_id is None else str(island_id): " | ".join(f"{n} {ground}" for ground, n in counts.most_common())
        for island_id, counts in sorted(by_island.items(), key=lambda kv: (kv[0] is None, kv[0] or 0))
    }


# Who bears what, land by land — an item carries no coordinates of its own: it exists through the hand that holds it, and a land with no bearer drops.
def _build_gear(save: dict, save_path: Path) -> dict:
    items = index_by_id(save.get("items") or [])
    _, island_of = compute_islands_cached(save, save_path)
    by_island: defaultdict[int | None, list] = defaultdict(list)  # a factory, `setdefault` minting a list per bearer to drop it on all but the first
    for actor in save.get("actors_data") or []:
        if is_boat(actor) or not (worn := actor.get("saved_items")):
            continue
        by_island[island_of.get(actor_xy(actor))].append(
            # An id the collection never resolves names nothing, so it is dropped rather than sorted against the rest as a `None`.
            {"id": actor["id"], "items": sorted(a for i in worn if (a := (items.get(i) or {}).get("asset_id"))), "name": actor.get("name")},
        )
    out = {}
    for island_id, bearers in sorted(by_island.items(), key=lambda kv: (kv[0] is None, kv[0] or 0)):  # the landless last, and `None` never reaches a `<`
        block: dict = {"carriers": len(bearers), "items": sum(len(b["items"]) for b in bearers)}  # annotated: the roster below widens it past its two counts
        if len(bearers) < _MAX_NAMED_CARRIERS:  # no `light()` here: naming them is all this section could ever hand over, so there is no fuller form to call
            block["roster"] = sorted(bearers, key=lambda b: b["id"])
        out["adrift" if island_id is None else str(island_id)] = block  # a bearer at sea or on a rock too small to count belongs to no land
    return out


# Where every instance of one kind stands. Its `id` opens its own script; `island_id` names the land mass, absent over water — a hull at sea, a dock on shallows.
def _build_positions(save: dict, save_path: Path, asset_id: str) -> list[dict]:
    out = []
    for collection, site in _COORDS.items():
        for record in save.get(collection) or []:
            if record.get("asset_id") == asset_id and (tile := site(record)) is not None:
                # `dormant` as `ground … metadata` tells it, so that a roll of volcanoes or geysers says which sleep without a call per mouth.
                asleep = "stop_spawn_drops" in (record.get("custom_data_flags") or ())
                out.append({"dormant": asleep or None, "id": record.get("id"), "name": record.get("name"), "x": tile[0], "y": tile[1]})
        if out:  # what one collection holds, the other never does — no need to walk 16k buildings to find an orc
            break
    if out:  # the lookup costs 0.2 s cold, so a kind nobody built never pays for it
        _, island_of = compute_islands_cached(save, save_path)
        for position in out:
            position["island_id"] = island_of.get((position["x"], position["y"]))
    return sorted(out, key=lambda r: (r["y"], r["x"]))


# The map's own sums, which no list adds up: its water, its land, and that land split between the counted lands and the islets too small to be one.
def _build_totals(save: dict, save_path: Path) -> dict:
    islands, _ = compute_islands_cached(save, save_path)
    layers = (tile_layer(name) for name in save.get("tileMap") or [])
    # A byte per tile, 1 on land and 2 on goo, counted in C: the rest of the map is its water.
    tally = b"".join(tile_mask(save, [1 if layer in ("Block", "Ground", "Lava") else 2 if layer == "Goo" else 0 for layer in layers]))
    land, goo = tally.count(1), tally.count(2)
    tiles, water, counted = len(tally) or 1, len(tally) - land - goo, sum(island["size"] for island in islands)
    # Each share of what holds it: the land and the water of the map, the counted lands and the islets of the land. Goo, a layer of its own, only where it spread.
    return {
        "goo": {"pct": round(goo / tiles * 100, 1), "tiles": goo} if goo else None,
        "land": {
            "islets": {"pct": round((land - counted) / (land or 1) * 100, 1), "tiles": land - counted},
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
    sizes = {island["id"]: island["size"] for island in islands}

    # A place rather than a landscape: few tiles, and few for its land too — on a small one, fifty tiles of desert are the landscape. Each patch of it sited.
    small = {
        (island_id, biome)
        for island_id, counts in tallies.items()
        for biome, n in counts.items()
        if n <= _PATCH_TILES and (island_id is None or n / sizes[island_id] * 100 < _PATCH_SHARE)
    }

    # No share where it rounds to nothing, nor off the counted lands (as `burning`, `frozen`): the tiles say it, and a lone `paradox` tile is still a subject.
    per_island = {
        "adrift" if island_id is None else str(island_id): [
            {
                **_patch_fields(patches[(island_id, biome)], (island_id, biome) in small),
                "biome": biome,
                "pct": None if island_id is None else round(n / sizes[island_id] * 100, 1) or None,
                "tiles": n,
            }
            for biome, n in counts.most_common()
        ]
        for island_id, counts in sorted(tallies.items(), key=lambda kv: (kv[0] is None, kv[0] or 0))
    }

    # Told once rather than on every land that carries the biome: a dozen descriptions would otherwise ride along some eighty times.
    named = {row["biome"] for rows in per_island.values() for row in rows}
    return {"descriptions": {b: text for b in sorted(named) if (text := biome_lore(b).get("description"))}, "islands": per_island}


# A place lists every patch it makes; a landscape, how many it breaks into and its largest — a lone patch is the whole biome, whose size the row already says.
def _patch_fields(found: list[list], small: bool) -> dict:
    top = max(size for size, *_ in found)
    # Sited only where shown — every patch of a place, a landscape's largest alone — then sorted, ties in size to the lower `(x, y)`.
    shown = [{**_site(sum_x / size, sum_y / size, runs), "tiles": size} for size, sum_x, sum_y, runs in found if small or size == top]
    shown.sort(key=lambda p: (-p["tiles"], p["x"], p["y"]))
    if len(found) == 1:
        del shown[0]["tiles"]
    return {"patches": shown} if small else {"largest": shown[0], "patches": len(found)}


# A patch's own tile nearest its middle, ties to the lower `(x, y)` — a mean alone could fall on another ground, or at sea. Each run offers its nearest column.
def _site(mean_x: float, mean_y: float, runs: list[tuple[int, int, int]]) -> dict:
    column, offers = math.ceil(mean_x - 0.5), []  # the column nearest the mean, a tie going west as `(x, y)` orders it
    for y, a, b in runs:
        x = min(max(column, a), b - 1)
        offers.append(((x - mean_x) ** 2 + (y - mean_y) ** 2, (x, y)))
    x, y = min(offers)[1]
    return {"x": x, "y": y}


def main(argv: list[str]) -> int:
    save_path, argv, _ = take_chapter(argv)  # pop the `C<n>` token first — argparse has no such positional and would abort on it

    parser = arg_parser(prog="geography/info.py", description="Geographic stats reserved for the chronicler.")
    parser.add_argument("sections", help=f"Comma-separated sections. Valid: {', '.join(_ALL_SECTIONS)}")
    parser.add_argument("--type", "-t", help="Asset id `positions` reports every instance of — e.g. `volcano`, `orc`. `entity_types` lists what the save holds.")
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

    save = load_save(save_path)
    out: dict = {}
    if "biomes" in sections:
        out["biomes"] = _build_biomes(save, save_path)
    if "burning" in sections:
        out["burning"] = _build_flagged_tiles(save, save_path, "fire")
    if "entity_types" in sections:
        out["entity_types"] = _build_entity_types(save)
    if "frozen" in sections:
        out["frozen"] = _build_flagged_tiles(save, save_path, "frozen_tiles")
    if "gear" in sections:
        out["gear"] = _build_gear(save, save_path)
    if "islands" in sections:
        islands, _ = compute_islands_cached(save, save_path)
        out["islands"] = islands
    if "positions" in sections and wanted is not None:
        out["positions"] = _build_positions(save, save_path, wanted)
    if "totals" in sections:
        out["totals"] = _build_totals(save, save_path)
    if "waters" in sections:
        out["waters"] = waters_cached(save, save_path)

    emit(out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
