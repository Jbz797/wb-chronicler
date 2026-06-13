#!/usr/bin/env python3

# Reusable island detection — mirrors WB's `IslandsCalculator.countLandIslands`. Consumed by `geography/info.py` and `actor/info.py` (per-actor island_id).
#
# Algorithm (extracted from `Assembly-CSharp.dll`):
# 1. Each tile has a `TileLayerType` (Null/Ground/Ocean/Lava/Block/Goo) — Block covers mountains/summit/walls, NOT Ground.
# 2. `MapChunk.calculateRegions` splits each 16×16 chunk into `MapRegion`s — each region = an 8-conn component of same-`layer_type` tiles within the chunk.
# 3. `IslandsCalculator.findIslands` + `startFill` flood-fill regions across chunk borders via `region.neighbours` (same-type adjacency) into `TileIsland`s.
# 4. `countLandIslands`: `count = islands.count(i => i.type == Ground && i.regions.Count >= 4)` — at least 4 regions, not 4 tiles.

import pickle
from collections import Counter, deque
from pathlib import Path


# `TileTypeBase.block = true` tiles — block diagonal moves (`isDiagonalBlockedByCorners`), splitting regions in sync with WB.
_BLOCK_TILES = frozenset({"$wall$", "frozen_low", "mountains", "summit"})
_CACHE_DIR = Path(__file__).parent.parent / ".cache"  # Sibling of `actor/`, `kingdom/`, … — gitignored via root `.gitignore`.
_CHUNK_SIZE = 16  # WB's `CHUNK_SIZE` constant — regions live inside 16×16 chunks.
_DELTAS_4 = ((-1, 0), (1, 0), (0, -1), (0, 1))
_DELTAS_8 = ((-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1))
_GROUND_REGIONS_THRESHOLD = 4  # WB hard-codes `regions.Count >= 4` in `countLandIslands`.
# Tile name → layer type, extracted from `Assembly-CSharp.dll` (TileType init). Anything not listed defaults to Ground (lava* → Lava via prefix).
_LAYER_BY_TILE = {
    "$wall$": "Block",
    "close_ocean": "Ocean",
    "deep_ocean": "Ocean",
    "grey_goo": "Goo",
    "mountains": "Block",
    "shallow_waters": "Ocean",
    "summit": "Block",
}


# Cache key from save-file `mtime + size` — cheap stat, sufficient to detect WB overwrites. `None` when the file is missing (caller falls back to live compute).
def _cache_key(save_path: Path) -> str | None:
    try:
        stat = save_path.stat()
    except OSError:
        return None
    return f"{int(stat.st_mtime)}_{stat.st_size}"


# Build the islands list and a tile-to-island lookup keyed by WB actor coordinates (y axis grows north, so `actor_y = H - 1 - row`).
def _compute_islands(save: dict) -> tuple[list[dict], dict[tuple[int, int], int]]:
    tile_map = save.get("tileMap") or []
    layer_by_id = [_tile_layer(name) for name in tile_map]
    block_by_id = [name.split(":", 1)[0] in _BLOCK_TILES for name in tile_map]
    grid = _decode_tile_grid(save)
    if not grid:
        return [], {}
    height, width = len(grid), len(grid[0])
    # Phase 1: split each 16×16 chunk into MapRegions (same-layer 8-conn components within the chunk, respecting `isDiagonalBlockedByCorners`).
    region_grid: list[list[int]] = [[-1] * width for _ in range(height)]
    regions: list[dict] = []
    for cy0 in range(0, height, _CHUNK_SIZE):
        for cx0 in range(0, width, _CHUNK_SIZE):
            cy1, cx1 = min(cy0 + _CHUNK_SIZE, height), min(cx0 + _CHUNK_SIZE, width)
            for sy in range(cy0, cy1):
                for sx in range(cx0, cx1):
                    if region_grid[sy][sx] != -1:
                        continue
                    layer = layer_by_id[grid[sy][sx]]
                    region_id = len(regions)
                    tiles: list[tuple[int, int]] = []
                    biomes: Counter[str] = Counter()
                    queue = deque([(sx, sy)])
                    region_grid[sy][sx] = region_id
                    while queue:
                        x, y = queue.popleft()
                        tiles.append((x, y))
                        if layer == "Ground":
                            biomes[_tile_biome(tile_map[grid[y][x]])] += 1
                        for dx, dy in _DELTAS_8:
                            nx, ny = x + dx, y + dy
                            if not (cx0 <= nx < cx1 and cy0 <= ny < cy1):
                                continue
                            if region_grid[ny][nx] != -1 or layer_by_id[grid[ny][nx]] != layer:
                                continue
                            # `isDiagonalBlockedByCorners`: diagonal step blocked if either orthogonal corner is a `block` tile. Out-of-bounds counts as blocked.
                            if dx and dy:
                                blocked_h = not (0 <= x + dx < width) or block_by_id[grid[y][x + dx]]
                                blocked_v = not (0 <= y + dy < height) or block_by_id[grid[y + dy][x]]
                                if blocked_h or blocked_v:
                                    continue
                            region_grid[ny][nx] = region_id
                            queue.append((nx, ny))
                    regions.append({"layer": layer, "tiles": tiles, "biomes": biomes})
    # Phase 2: merge regions into TileIslands via cross-chunk neighbours of the same layer (4-conn between tiles).
    island_of_region: list[int] = [-1] * len(regions)
    component_regions: list[list[int]] = []
    for start in range(len(regions)):
        if island_of_region[start] != -1:
            continue
        cid = len(component_regions)
        component_regions.append([])
        queue = deque([start])
        island_of_region[start] = cid
        while queue:
            r_idx = queue.popleft()
            component_regions[cid].append(r_idx)
            layer = regions[r_idx]["layer"]
            for tx, ty in regions[r_idx]["tiles"]:
                for dx, dy in _DELTAS_4:
                    nx, ny = tx + dx, ty + dy
                    if not (0 <= nx < width and 0 <= ny < height):
                        continue
                    other = region_grid[ny][nx]
                    if other == r_idx or island_of_region[other] != -1 or regions[other]["layer"] != layer:
                        continue
                    island_of_region[other] = cid
                    queue.append(other)
    # Phase 3: keep only Ground islands with ≥ `_GROUND_REGIONS_THRESHOLD` regions (mirrors `countLandIslands`).
    kept: list[tuple[int, Counter[str], list[tuple[int, int]]]] = []
    for r_indices in component_regions:
        if regions[r_indices[0]]["layer"] != "Ground" or len(r_indices) < _GROUND_REGIONS_THRESHOLD:
            continue
        biomes = Counter()
        tiles = []
        for r_idx in r_indices:
            biomes.update(regions[r_idx]["biomes"])
            tiles.extend(regions[r_idx]["tiles"])
        kept.append((len(tiles), biomes, tiles))
    kept.sort(key=lambda c: -c[0])
    islands = []
    tile_to_id: dict[tuple[int, int], int] = {}
    seeds: deque[tuple[int, int]] = deque()
    for idx, (size, biomes, tiles) in enumerate(kept, start=1):
        cx = sum(t[0] for t in tiles) // size
        cy_grid = sum(t[1] for t in tiles) // size
        top_biomes = " | ".join(f"{round(n / size * 100)}% {name}" for name, n in biomes.most_common(3))
        islands.append({"biomes": top_biomes, "centroid": {"x": cx, "y": height - 1 - cy_grid}, "id": idx, "size": size})
        for gx, gy in tiles:
            tile_to_id[(gx, height - 1 - gy)] = idx
            seeds.append((gx, gy))
    # Chronicler-only: propagate id to adjacent Block/Lava (mountains/summit/lava) so actors there map to their host island. Ocean/Goo skipped.
    while seeds:
        x, y = seeds.popleft()
        iid = tile_to_id[(x, height - 1 - y)]
        for dx, dy in _DELTAS_4:
            nx, ny = x + dx, y + dy
            if not (0 <= nx < width and 0 <= ny < height):
                continue
            if (nx, height - 1 - ny) in tile_to_id or layer_by_id[grid[ny][nx]] not in ("Block", "Lava"):
                continue
            tile_to_id[(nx, height - 1 - ny)] = iid
            seeds.append((nx, ny))
    return islands, tile_to_id


# Expand the save's per-row RLE (`tileArray` = tile ids, `tileAmounts` = run lengths) into a 2D `grid[row][x]` of tile ids — row 0 is the northernmost.
def _decode_tile_grid(save: dict) -> list[list[int]]:
    grid = []
    for ids, runs in zip(save.get("tileArray") or [], save.get("tileAmounts") or []):
        row = []
        for tile_id, n in zip(ids, runs):
            row.extend([tile_id] * n)
        grid.append(row)
    return grid


# Reduce a tileMap entry to its semantic biome: drops the `soil_low:` / `soil_high:` elevation prefix and the trailing `_low`/`_high` suffix.
def _tile_biome(tile_name: str) -> str:
    name = tile_name.split(":", 1)[-1]
    for suffix in ("_high", "_low"):
        if name.endswith(suffix):
            return name[: -len(suffix)]
    return name


# Map a tileMap entry to its WB `TileLayerType`. Lava (`lava0`..`lava3`+) lumps under "Lava"; everything not flagged is Ground.
def _tile_layer(tile_name: str) -> str:
    base = tile_name.split(":", 1)[0]
    if base in _LAYER_BY_TILE:
        return _LAYER_BY_TILE[base]
    if base.startswith("lava"):
        return "Lava"
    return "Ground"


# Disk-cached `_compute_islands` — key = save `mtime+size`, pickle format, stale entries dropped on write (single-file cache).
def compute_islands_cached(save: dict, save_path: Path) -> tuple[list[dict], dict[tuple[int, int], int]]:
    key = _cache_key(save_path)
    if key is None:
        return _compute_islands(save)
    cache_file = _CACHE_DIR / f"islands_v5_{key}.pkl"
    if cache_file.exists():
        try:
            with cache_file.open("rb") as f:
                return pickle.load(f)
        except Exception:  # noqa: BLE001 — corrupt cache, fall through to recompute.
            cache_file.unlink(missing_ok=True)
    result = _compute_islands(save)
    _CACHE_DIR.mkdir(exist_ok=True)
    for old in _CACHE_DIR.glob("islands_*.pkl"):
        if old.name != cache_file.name:
            old.unlink(missing_ok=True)
    with cache_file.open("wb") as f:
        pickle.dump(result, f)
    return result
