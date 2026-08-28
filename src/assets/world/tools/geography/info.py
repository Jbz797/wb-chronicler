#!/usr/bin/env python3

# Geographic stats reserved for the chronicler (not consumed by the UI). User-facing docs: `tools/tools.md`.

import argparse
import pickle
import sys
from collections import Counter, defaultdict, deque
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))

from grid import decode_tile_grid, tile_biome, tile_layer
from islands import compute_islands_cached
from shared import CACHE_DIR, biome_lore, civic_building_ids, emit, load_data, load_save, parse_sections, save_cache_key, take_chapter

_ALL_SECTIONS = ("biomes", "entity_types", "islands", "positions", "waters")
_DELTAS_4 = ((-1, 0), (1, 0), (0, -1), (0, 1))
_OPEN_SEA = -1  # the one water body that reaches the map edge, standing apart from the lakes indexed from 0
_COORDS = {"actors_data": ("x", "y"), "buildings": ("mainX", "mainY")}  # Collection → its coordinate fields. No `asset_id` sits in both, so a kind names its own.


# Every biome a land carries, marginal ones included — a paradox patch is a chapter's subject. Shares are of the whole island, sand and rock cutting them under 100.
def _build_biomes(save: dict, save_path: Path) -> dict:
    _, island_of = compute_islands_cached(save, save_path)
    grid = decode_tile_grid(save)
    biome_by_id = [tile_biome(name) for name in save.get("tileMap") or []]  # already merged: `soil_high:paradox_high` and its low twin both read `paradox`
    tallies: defaultdict[int, Counter] = defaultdict(Counter)  # `setdefault` would mint a Counter per tile, three hundred thousand of them for one map
    sizes: Counter = Counter()
    island_at = island_of.get  # bound once: the lookup runs on every tile of the map

    for y, row in enumerate(grid):
        for x, tile_id in enumerate(row):
            if not (island_id := island_at((x, y))):
                continue
            sizes[island_id] += 1
            if biome := biome_by_id[tile_id]:
                tallies[island_id][biome] += 1

    per_island = {
        str(island_id): [{"biome": biome, "pct": pct, "tiles": n} for biome, n in counts.most_common() if (pct := round(n / sizes[island_id] * 100, 1)) > 0]
        for island_id, counts in sorted(tallies.items())
    }
    # Told once rather than on every land that carries the biome: a dozen descriptions would otherwise ride along some eighty times.
    named = {row["biome"] for rows in per_island.values() for row in rows}
    return {"descriptions": {b: text for b in sorted(named) if (text := biome_lore(b).get("description"))}, "islands": per_island}


# Every kind the save holds, grouped as WB groups them — its `buildings` collection also holds the flowers and the ore, so only the `civ_*` keep that name here.
def _build_entity_types(save: dict) -> dict:
    categories, civic = load_data("building-categories.json"), civic_building_ids()
    groups: dict[str, Counter] = {"actors": Counter(a["asset_id"] for a in save.get("actors_data") or [] if a.get("asset_id"))}
    for building in save.get("buildings") or []:
        if not (asset := building.get("asset_id")):
            continue
        group = "buildings" if asset in civic else categories.get(asset) or "other"  # `civic` knows the built kinds the manifest itself never declared
        groups.setdefault(group, Counter())[asset] += 1
    return {group: dict(counts) for group, counts in groups.items() if counts}


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
    key = save_cache_key(save_path)
    cache_file = CACHE_DIR / f"waters_v1_{key}.pkl" if key else None
    if cache_file and cache_file.exists():
        try:
            with cache_file.open("rb") as f:
                return pickle.load(f)
        except Exception:  # noqa: BLE001 — corrupt cache, fall through and recompute.
            cache_file.unlink(missing_ok=True)

    _, island_of = compute_islands_cached(save, save_path)
    grid = decode_tile_grid(save)
    sea = [tile_layer(name) == "Ocean" for name in save.get("tileMap") or []]
    lake_of, pools = _pool_map(grid, sea)
    waters = {"lakes": _lakes(pools, lake_of, island_of, grid, sea), "straits": _straits(grid, sea, island_of)}

    if cache_file:
        CACHE_DIR.mkdir(exist_ok=True)
        for old in CACHE_DIR.glob("waters_*.pkl"):
            if old.name != cache_file.name:
                old.unlink(missing_ok=True)
        with cache_file.open("wb") as f:
            pickle.dump(waters, f)
    return waters


# An enclosed water is named by the shores that ring it, and holds as an islet any land no other water touches — the isles a chronicle reaches last, or never.
def _lakes(pools: list[list[tuple[int, int]]], lake_of: dict, island_of, grid: list[list[int]], sea: list[bool]) -> list[dict]:
    pools_of_island: defaultdict[int, set[int]] = defaultdict(set)
    shores: defaultdict[int, set[int]] = defaultdict(set)
    height, width = len(grid), len(grid[0])

    for x, y, island_id in island_of.land():
        for dx, dy in _DELTAS_4:
            nx, ny = x + dx, y + dy
            if not (0 <= nx < width and 0 <= ny < height) or not sea[grid[ny][nx]]:
                continue
            pool = lake_of.get((nx, ny), _OPEN_SEA)  # a shore on the open sea is nobody's islet, however many lakes it also touches
            pools_of_island[island_id].add(pool)
            if pool != _OPEN_SEA:
                shores[pool].add(island_id)

    out = []
    # Numbered widest first, as WB numbers its islands: the id is what `places.json` keys a name on, so it must not shift from one chapter to the next.
    for lake_id, index in enumerate(sorted(range(len(pools)), key=lambda i: -len(pools[i])), start=1):
        tiles = pools[index]
        islets = sorted(i for i, seen in pools_of_island.items() if seen == {index})
        out.append(
            {
                "centroid": {"x": sum(t[0] for t in tiles) // len(tiles), "y": sum(t[1] for t in tiles) // len(tiles)},
                "id": lake_id,
                "islets": islets,
                "shores": sorted(shores[index] - set(islets)),
                "size": len(tiles),
            }
        )
    return out


# Water bodies that never reach the map edge. The open sea does, so it drops out — what is left is a lake, however wide.
def _pool_map(grid: list[list[int]], sea: list[bool]) -> tuple[dict[tuple[int, int], int], list[list[tuple[int, int]]]]:
    height, width = len(grid), len(grid[0])
    seen = [[False] * width for _ in range(height)]
    lake_of: dict[tuple[int, int], int] = {}
    pools: list[list[tuple[int, int]]] = []

    for sy in range(height):
        for sx in range(width):
            if seen[sy][sx] or not sea[grid[sy][sx]]:
                continue
            body, open_sea, queue = [], False, [(sx, sy)]
            seen[sy][sx] = True
            while queue:
                x, y = queue.pop()
                body.append((x, y))
                open_sea = open_sea or x in (0, width - 1) or y in (0, height - 1)
                for dx, dy in _DELTAS_4:
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < width and 0 <= ny < height and not seen[ny][nx] and sea[grid[ny][nx]]:
                        seen[ny][nx] = True
                        queue.append((nx, ny))
            if not open_sea:
                lake_of.update(dict.fromkeys(body, len(pools)))
                pools.append(body)
    return lake_of, pools


# The narrowest water between each pair of lands: every coast floods the sea at once, and where two tides meet their depths add up to the crossing.
def _straits(grid: list[list[int]], sea: list[bool], island_of) -> list[dict]:
    height, width = len(grid), len(grid[0])
    nearest = [[0] * width for _ in range(height)]
    depth = [[-1] * width for _ in range(height)]
    queue: deque[tuple[int, int]] = deque()

    for x, y, island_id in island_of.land():
        nearest[y][x], depth[y][x] = island_id, 0
        queue.append((x, y))

    gaps: dict[tuple[int, int], int] = {}
    while queue:
        x, y = queue.popleft()
        own, here = nearest[y][x], depth[y][x]
        for dx, dy in _DELTAS_4:
            nx, ny = x + dx, y + dy
            if not (0 <= nx < width and 0 <= ny < height) or not sea[grid[ny][nx]]:
                continue
            if depth[ny][nx] == -1:
                nearest[ny][nx], depth[ny][nx] = own, here + 1
                queue.append((nx, ny))
            elif nearest[ny][nx] != own:
                pair = (min(own, nearest[ny][nx]), max(own, nearest[ny][nx]))
                gaps[pair] = min(gaps.get(pair, here + depth[ny][nx]), here + depth[ny][nx])
    return [{"between": list(pair), "gap": gap} for pair, gap in sorted(gaps.items(), key=lambda kv: (kv[1], kv[0]))]


def main(argv: list[str]) -> int:
    save_path, argv, _ = take_chapter(argv)  # pop the `C<n>` token first — argparse has no such positional and would abort on it

    parser = argparse.ArgumentParser(prog="geography/info.py", description="Geographic stats reserved for the chronicler.")
    parser.add_argument("sections", help=f"Comma-separated sections. Valid: {', '.join(_ALL_SECTIONS)}")
    parser.add_argument("--type", "-t", help="Asset id `positions` reports every instance of — e.g. `volcano`, `orc`. `entity_types` lists what the save holds.")
    args = parser.parse_args(argv)

    if args.sections == "full":  # No `full` here, unlike the other tools: these sections answer unrelated questions, and no reading wants all three.
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
    if "entity_types" in sections:
        out["entity_types"] = _build_entity_types(save)
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
