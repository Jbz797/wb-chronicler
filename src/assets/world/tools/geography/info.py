#!/usr/bin/env python3

# Geographic stats reserved for the chronicler (not consumed by the UI). User-facing docs: `tools/tools.md`.

import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))

from grid import LazyTileGrid, decode_tile_grid, listed_tiles, tile_biome, tile_kind, tile_layer, tile_mask
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
)
from waters import waters_cached

_ALL_SECTIONS = ("biomes", "burning", "entity_types", "frozen", "gear", "islands", "positions", "totals", "waters")
_COORDS = {"actors_data": actor_xy, "buildings": building_tile}  # Collection → the helper that sites a record, WB's omitted zero read as 0. No kind sits in both.
_DELTAS_8 = ((-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1))  # a patch holds together as WB's own regions do, corners included
_MAX_NAMED_CARRIERS = 5  # past a handful, naming them says less than counting them: on such a land, bearing arms is no longer the fact a chapter turns on
_PATCH_SHARE = 1  # percent of its land a biome must stay under to be sited, however few its tiles
_PATCH_TILES = 50  # at most this many tiles of a biome on one land, it is a place rather than a landscape: each patch is sited, as a share alone could not find it


# Every biome a land carries, marginal ones included — a paradox patch is a chapter's subject. Shares are of the whole island, sand and rock cutting them under 100.
def _build_biomes(save: dict, save_path: Path) -> dict:
    return pickle_cached("biomes_v5", save_path, lambda: _compute_biomes(save, save_path))


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
    _, island_of = compute_islands_cached(save, save_path)
    grid = decode_tile_grid(save)
    biome_by_id = [tile_biome(name) for name in save.get("tileMap") or []]  # already merged: `soil_high:paradox_high` and its low twin both read `paradox`
    # Every tile as an (island, tile id) pair, `0` off the counted lands, tallied in C a row at a time — in first-seen order, so ties between biomes fall as met.
    pairs: Counter = Counter()
    for y, row in enumerate(grid):
        pairs.update(zip(island_of.row(y), row))
    tallies: defaultdict[int | None, Counter] = defaultdict(Counter)
    sizes: Counter = Counter()
    for (island_id, tile), n in pairs.items():
        if island_id:
            sizes[island_id] += n
            if biome := biome_by_id[tile]:
                tallies[island_id][biome] += n
    # What lies on no counted land, a rock too small to be one, is island `0`'s: taken in the order the whole map first meets each tile, as its lands are.
    for tile in dict.fromkeys(tile for _, tile in pairs):
        if (biome := biome_by_id[tile]) and (rest := pairs[(0, tile)]):
            tallies[None][biome] += rest

    # A place rather than a landscape: few tiles, and few for its land too — on a small one, fifty tiles of desert are the landscape. Sited in one more sweep.
    small = {
        (island_id, biome)
        for island_id, counts in tallies.items()
        for biome, n in counts.items()
        if n <= _PATCH_TILES and (island_id is None or n / sizes[island_id] * 100 < _PATCH_SHARE)
    }
    small_biomes = {biome for _, biome in small}
    spots: defaultdict[tuple[int | None, str | None], list[tuple[int, int]]] = defaultdict(list)
    # Only the tiles of a biome small somewhere are asked their land, found in C off a mask of the runs, where the sweep once walked every tile of the map.
    for y, marks in enumerate(tile_mask(save, [biome in small_biomes for biome in biome_by_id]) if small else ()):
        lands, row, x = island_of.row(y), grid[y], marks.find(1)
        while x != -1:
            if (key := (lands[x] or None, biome_by_id[row[x]])) in small:
                spots[key].append((x, y))
            x = marks.find(1, x + 1)

    # No share where it rounds to nothing, nor off the counted lands (as `burning`, `frozen`): the tiles say it, and a lone `paradox` tile is still a subject.
    per_island = {
        "adrift" if island_id is None else str(island_id): [
            {
                "biome": biome,
                "patches": _patches(spots[(island_id, biome)]) if (island_id, biome) in small else None,
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


# A small biome's tiles split into the patches they form, each sited on its own tile nearest its middle — a mean alone could fall on another ground, or at sea.
def _patches(tiles: list[tuple[int, int]]) -> list[dict]:
    left, patches = set(tiles), []
    while left:
        stack, patch = [left.pop()], []
        while stack:
            x, y = stack.pop()
            patch.append((x, y))
            for dx, dy in _DELTAS_8:
                if (near := (x + dx, y + dy)) in left:
                    left.remove(near)
                    stack.append(near)
        mx, my = sum(x for x, _ in patch) / len(patch), sum(y for _, y in patch) / len(patch)
        x, y = min(patch, key=lambda t: ((t[0] - mx) ** 2 + (t[1] - my) ** 2, t))
        patches.append({"tiles": len(patch), "x": x, "y": y})
    patches.sort(key=lambda p: (-p["tiles"], p["x"], p["y"]))
    if len(patches) == 1:  # a lone patch is the whole biome on its land: the row already says its size
        del patches[0]["tiles"]
    return patches


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
