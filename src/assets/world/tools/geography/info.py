#!/usr/bin/env python3

# Geographic stats reserved for the chronicler (not consumed by the UI). User-facing docs: `tools/tools.md`.

import argparse
import pickle
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))

from grid import LazyTileGrid, decode_tile_grid, listed_tiles, tile_biome, tile_kind, tile_layer
from islands import compute_islands_cached
from shared import (
    CACHE_DIR,
    biome_lore,
    civic_building_ids,
    emit,
    index_by_id,
    is_boat,
    load_data,
    load_save,
    parse_sections,
    save_cache_key,
    take_chapter,
)

_ALL_SECTIONS = ("biomes", "burning", "entity_types", "equipment", "frozen", "islands", "positions", "waters")
_COORDS = {"actors_data": ("x", "y"), "buildings": ("mainX", "mainY")}  # Collection → its coordinate fields. No `asset_id` sits in both, so a kind names its own.
_MAX_NAMED_CARRIERS = 5  # past a handful, naming them says less than counting them: on such a land, bearing arms is no longer the fact a chapter turns on
_MIN_LAKE_TILES = 64  # WB knows no lake at all, so the floor is ours: WB `CITY_ZONE_TILES`, one city zone — under it no town could ever sit on the shore.
_OPEN_SEA = -1  # the one water body that reaches the map edge, standing apart from the lakes indexed from 0


# Every biome a land carries, marginal ones included — a paradox patch is a chapter's subject. Shares are of the whole island, sand and rock cutting them under 100.
def _build_biomes(save: dict, save_path: Path) -> dict:
    return _cached("biomes_v1", save_path, lambda: _compute_biomes(save, save_path))


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


# Who bears what, land by land — an item carries no coordinates of its own: it exists through the hand that holds it, and a land with no bearer drops.
def _build_equipment(save: dict, save_path: Path) -> dict:
    items = index_by_id(save.get("items") or [])
    _, island_of = compute_islands_cached(save, save_path)
    by_island: defaultdict[int | None, list] = defaultdict(list)  # a factory, `setdefault` minting a list per bearer to drop it on all but the first
    for actor in save.get("actors_data") or []:
        if is_boat(actor) or not (worn := actor.get("saved_items")):
            continue
        by_island[island_of.get((int(actor["x"]), int(actor["y"])))].append(
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


# Where every instance of one kind stands. Its `id` opens its own script; `island_id` names the land mass, absent over water — a hull at sea, a dock on shallows.
def _build_positions(save: dict, save_path: Path, asset_id: str) -> list[dict]:
    out = []
    for collection, (field_x, field_y) in _COORDS.items():
        for record in save.get(collection) or []:
            if record.get("asset_id") != asset_id:
                continue
            if (x := record.get(field_x)) is not None and (y := record.get(field_y)) is not None:
                out.append({"id": record.get("id"), "name": record.get("name"), "x": int(x), "y": int(y)})
        if out:  # what one collection holds, the other never does — no need to walk 16k buildings to find an orc
            break
    if out:  # the lookup costs half a second cold, so a kind nobody built never pays for it
        _, island_of = compute_islands_cached(save, save_path)
        for position in out:
            position["island_id"] = island_of.get((position["x"], position["y"]))
    return sorted(out, key=lambda r: (r["y"], r["x"]))


# Every stretch of sea the map encloses, and every land it holds apart. Both fall out of one sweep of the water, and the map never moves — hence the cache.
def _build_waters(save: dict, save_path: Path) -> dict:
    return _cached("waters_v2", save_path, lambda: _compute_waters(save, save_path))


# A section's answer kept on disk under the save it was read from: the map never moves, so neither does what a sweep of it says. Stale slots go on the way past.
def _cached(name: str, save_path: Path, compute) -> dict:
    key = save_cache_key(save_path)
    cache_file = CACHE_DIR / f"{name}_{key}.pkl" if key else None
    if cache_file and cache_file.exists():
        try:
            with cache_file.open("rb") as f:
                return pickle.load(f)
        except Exception:  # noqa: BLE001 — corrupt cache, fall through and recompute.
            cache_file.unlink(missing_ok=True)
    out = compute()
    if cache_file:
        CACHE_DIR.mkdir(exist_ok=True)
        for old in CACHE_DIR.glob(f"{name.rsplit('_', 1)[0]}_*.pkl"):
            if old.name != cache_file.name:
                old.unlink(missing_ok=True)
        with cache_file.open("wb") as f:
            pickle.dump(out, f)
    return out


# The sweep itself, run once per save: six hundred thousand land tiles asked their biome, which is what the cache above is for.
def _compute_biomes(save: dict, save_path: Path) -> dict:
    _, island_of = compute_islands_cached(save, save_path)
    grid = decode_tile_grid(save)
    biome_by_id = [tile_biome(name) for name in save.get("tileMap") or []]  # already merged: `soil_high:paradox_high` and its low twin both read `paradox`
    # The lands alone, as (island, tile id) pairs `Counter` tallies in C — and in first-seen order, so ties between biomes fall as the sweep met them.
    pairs = Counter((island_id, grid[y][x]) for x, y, island_id in island_of.land())
    tallies: defaultdict[int, Counter] = defaultdict(Counter)
    sizes: Counter = Counter()
    for (island_id, tile), n in pairs.items():
        sizes[island_id] += n
        if biome := biome_by_id[tile]:
            tallies[island_id][biome] += n

    per_island = {
        str(island_id): [{"biome": biome, "pct": pct, "tiles": n} for biome, n in counts.most_common() if (pct := round(n / sizes[island_id] * 100, 1)) > 0]
        for island_id, counts in sorted(tallies.items())
    }

    # Told once rather than on every land that carries the biome: a dozen descriptions would otherwise ride along some eighty times.
    named = {row["biome"] for rows in per_island.values() for row in rows}
    return {"descriptions": {b: text for b in sorted(named) if (text := biome_lore(b).get("description"))}, "islands": per_island}


# One sweep of the water answers both: a pool the land encloses is a lake, and the land two pools hold apart makes a strait.
def _compute_waters(save: dict, save_path: Path) -> dict:
    _, island_of = compute_islands_cached(save, save_path)
    grid = decode_tile_grid(save)
    sea = [tile_layer(name) == "Ocean" for name in save.get("tileMap") or []]
    # The sea as one flat mask ringed by a border of land: every neighbour of a map tile is a valid index, so no sweep below tests a bound or indexes a nested row.
    height, width = len(grid), len(grid[0])
    stride = width + 2
    water = bytearray(stride * (height + 2))
    for y, row in enumerate(grid):
        start = (y + 1) * stride + 1
        water[start : start + width] = bytes(map(sea.__getitem__, row))
    pool_at, pools = _pool_map(water, stride)
    return {"lakes": _lakes(pools, pool_at, island_of, water, stride), "straits": _straits(water, stride, island_of)}


# An enclosed water is named by the shores that ring it, and holds as an islet any land no other water touches — the isles a chronicle reaches last, or never.
def _lakes(pools: list[tuple[int, int, int, bool]], pool_at: list[int], island_of, water: bytearray, stride: int) -> list[dict]:
    # Numbered widest first, as WB numbers its islands: the id is what `places.json` keys a name on, so it must not shift from one chapter to the next.
    kept = [p for p in sorted((p for p, pool in enumerate(pools) if pool[3]), key=lambda p: -pools[p][0]) if pools[p][0] >= _MIN_LAKE_TILES]
    lakes = set(kept)
    pools_of_island: defaultdict[int, set[int]] = defaultdict(set)
    shores: defaultdict[int, set[int]] = defaultdict(set)

    for x, y, island_id in island_of.land():
        i = (y + 1) * stride + x + 1
        for j in (i - stride, i + stride, i - 1, i + 1):
            if not water[j]:
                continue
            pool = pool_at[j] if pools[pool_at[j]][3] else _OPEN_SEA  # a shore on the open sea is nobody's islet, however many lakes it also touches
            if pool != _OPEN_SEA and pool not in lakes:  # a puddle under the floor is no water at all here: it neither rings a land nor bars it from being an islet
                continue
            pools_of_island[island_id].add(pool)
            if pool != _OPEN_SEA:
                shores[pool].add(island_id)

    out = []
    for lake_id, index in enumerate(kept, start=1):
        size, cx, cy, _ = pools[index]
        islets = sorted(i for i, seen in pools_of_island.items() if seen == {index})
        out.append({"centroid": {"x": cx, "y": cy}, "id": lake_id, "islets": islets, "shores": sorted(shores[index] - set(islets)), "size": size})
    return out


# Every body of water with its size, centroid and whether land encloses it — the open sea reaches the map edge. `_lakes` keeps the enclosed ones worth a name.
def _pool_map(water: bytearray, stride: int) -> tuple[list[int], list[tuple[int, int, int, bool]]]:
    width, height = stride - 2, len(water) // stride - 2
    todo, pool_at, pools = bytearray(water), [-1] * len(water), []
    pos = todo.find(1)  # the next water no body has claimed, found in C where a Python sweep would test every tile of the map
    while pos != -1:
        index, stack, size, sum_x, sum_y, open_sea = len(pools), [pos], 0, 0, 0, False
        todo[pos] = 0
        while stack:
            i = stack.pop()
            pool_at[i] = index
            y, x = divmod(i, stride)
            size, sum_x, sum_y = size + 1, sum_x + x, sum_y + y
            open_sea = open_sea or x == 1 or x == width or y == 1 or y == height
            for j in (i - stride, i + stride, i - 1, i + 1):
                if todo[j]:
                    todo[j] = 0
                    stack.append(j)
        # Its tiles are not kept, `pool_at` already sites each one: only the size and the centroid, the border's column and row taken back off the mean.
        pools.append((size, sum_x // size - 1, sum_y // size - 1, not open_sea))
        pos = todo.find(1, pos + 1)
    return pool_at, pools


# The narrowest water between each pair of lands: every coast floods the sea at once, and where two tides meet their depths add up to the crossing.
def _straits(water: bytearray, stride: int, island_of) -> list[dict]:
    depth, nearest, front = [-1] * len(water), [0] * len(water), []
    for x, y, island_id in island_of.land():
        nearest[i := (y + 1) * stride + x + 1], depth[i] = island_id, 0
        front.append(i)

    # A tide at a time, its whole ring swept before the next: a tile of sea met unclaimed joins the front, met claimed by another island it closes a gap.
    gaps: dict[tuple[int, int], int] = {}
    here = 0
    while front:
        ring: list[int] = []
        push = ring.append
        for i in front:
            own = nearest[i]
            for j in (i - stride, i + stride, i - 1, i + 1):
                if not water[j]:
                    continue
                if (reached := depth[j]) == -1:
                    nearest[j], depth[j] = own, here + 1
                    push(j)
                elif (rival := nearest[j]) != own:
                    pair = (own, rival) if own < rival else (rival, own)
                    if (span := here + reached) < gaps.get(pair, span + 1):  # the narrowest the two ever leave
                        gaps[pair] = span
        front, here = ring, here + 1
    return [{"between": list(pair), "gap": gap} for pair, gap in sorted(gaps.items(), key=lambda kv: (kv[1], kv[0]))]


def main(argv: list[str]) -> int:
    save_path, argv, _ = take_chapter(argv)  # pop the `C<n>` token first — argparse has no such positional and would abort on it

    parser = argparse.ArgumentParser(prog="geography/info.py", description="Geographic stats reserved for the chronicler.")
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
    if "equipment" in sections:
        out["equipment"] = _build_equipment(save, save_path)
    if "frozen" in sections:
        out["frozen"] = _build_flagged_tiles(save, save_path, "frozen_tiles")
    if "islands" in sections:
        islands, _ = compute_islands_cached(save, save_path)
        out["islands"] = islands
    if "positions" in sections and wanted is not None:
        out["positions"] = _build_positions(save, save_path, wanted)
    if "waters" in sections:
        out["waters"] = _build_waters(save, save_path)

    emit(out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
