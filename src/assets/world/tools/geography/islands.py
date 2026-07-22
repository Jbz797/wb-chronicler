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

from grid import decode_tile_grid, tile_biome, tile_kind, tile_layer


_BLOCK_TILES = frozenset({"$wall$", "frozen_low", "mountains", "summit"})  # WB `TileTypeBase.block` tiles — block diagonals, which splits regions.
_CACHE_DIR = Path(__file__).parent.parent / ".cache"  # Sibling of `actor/`, `kingdom/`, … — gitignored via root `.gitignore`.
_CHUNK_SIZE = 16  # WB's `CHUNK_SIZE` constant — regions live inside 16×16 chunks.
_DELTAS_4 = ((-1, 0), (1, 0), (0, -1), (0, 1))
_DELTAS_8 = ((-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1))
_GROUND_REGIONS_THRESHOLD = 4  # WB hard-codes `regions.Count >= 4` in `countLandIslands`.


# Cache key from save-file `mtime + size` — cheap stat, sufficient to detect WB overwrites. `None` when the file is missing (caller falls back to live compute).
def _cache_key(save_path: Path) -> str | None:
    try:
        stat = save_path.stat()
    except OSError:
        return None
    return f"{int(stat.st_mtime)}_{stat.st_size}"


# Build the islands list and a tile-to-island lookup keyed by WB-actor coordinates (no y inversion — `row` IS the actor y, see `chronicler.md`).
def _compute_islands(save: dict) -> tuple[list[dict], dict[tuple[int, int], int]]:
    tile_map = save.get("tileMap") or []
    layer_by_id = [tile_layer(name) for name in tile_map]
    block_by_id = [name.split(":", 1)[0] in _BLOCK_TILES for name in tile_map]

    # Precompute per-tile-id biome/kind once — Phase 1 + Phase 4 BFSs touch ~10⁵ tiles, each function call would otherwise be repeated for the same id.
    biome_by_id = [tile_biome(name) for name in tile_map]
    kind_by_id = [tile_kind(name) for name in tile_map]
    grid = decode_tile_grid(save)
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
                    tile_kinds: Counter[str] = Counter()
                    queue = deque([(sx, sy)])
                    region_grid[sy][sx] = region_id
                    while queue:
                        x, y = queue.popleft()
                        tiles.append((x, y))
                        tid = grid[y][x]
                        tile_kinds[kind_by_id[tid]] += 1
                        if layer == "Ground" and (biome := biome_by_id[tid]):
                            biomes[biome] += 1
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
                    regions.append({"biomes": biomes, "layer": layer, "tile_kinds": tile_kinds, "tiles": tiles})

    # Phase 2: merge regions into TileIslands. Regions only meet across chunk borders — inside one, same-layer 4-neighbours already share a region.
    neighbours: list[set[int]] = [set() for _ in regions]

    for y in range(height):
        row = region_grid[y]
        for x in range(_CHUNK_SIZE, width, _CHUNK_SIZE):
            a, b = row[x - 1], row[x]
            if regions[a]["layer"] == regions[b]["layer"]:
                neighbours[a].add(b)
                neighbours[b].add(a)

    for y in range(_CHUNK_SIZE, height, _CHUNK_SIZE):
        row, above = region_grid[y], region_grid[y - 1]
        for x in range(width):
            a, b = above[x], row[x]
            if regions[a]["layer"] == regions[b]["layer"]:
                neighbours[a].add(b)
                neighbours[b].add(a)

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
            for other in neighbours[r_idx]:
                if island_of_region[other] == -1:
                    island_of_region[other] = cid
                    queue.append(other)
    # Phase 3: keep only Ground islands with ≥ `_GROUND_REGIONS_THRESHOLD` regions (mirrors `countLandIslands`).
    kept: list[tuple[int, Counter[str], Counter[str], list[tuple[int, int]]]] = []

    for r_indices in component_regions:
        if regions[r_indices[0]]["layer"] != "Ground" or len(r_indices) < _GROUND_REGIONS_THRESHOLD:
            continue
        biomes = Counter()
        tile_kinds = Counter()
        tiles = []
        for r_idx in r_indices:
            biomes.update(regions[r_idx]["biomes"])
            tile_kinds.update(regions[r_idx]["tile_kinds"])
            tiles.extend(regions[r_idx]["tiles"])
        kept.append((len(tiles), biomes, tile_kinds, tiles))
    kept.sort(key=lambda c: -c[0])
    islands = []
    island_tile_kinds: dict[int, Counter[str]] = {}
    tile_to_id: dict[tuple[int, int], int] = {}
    seeds: deque[tuple[int, int]] = deque()

    for idx, (size, biomes, tile_kinds, tiles) in enumerate(kept, start=1):
        cx = sum(t[0] for t in tiles) // size
        cy = sum(t[1] for t in tiles) // size
        top_biomes = " | ".join(f"{pct}% {name}" for name, n in biomes.most_common(3) if (pct := round(n / size * 100)) > 0)
        island_tile_kinds[idx] = Counter(tile_kinds)
        islands.append({"biomes": top_biomes, "centroid": {"x": cx, "y": cy}, "id": idx, "size": size})
        for gx, gy in tiles:
            tile_to_id[(gx, gy)] = idx
            seeds.append((gx, gy))

    # Phase 4: bleed the id into adjacent Block/Lava so actors on mountains/lava resolve to their host island. Ocean/Goo stay out — not landmass.
    while seeds:
        x, y = seeds.popleft()
        iid = tile_to_id[(x, y)]
        for dx, dy in _DELTAS_4:
            nx, ny = x + dx, y + dy
            if not (0 <= nx < width and 0 <= ny < height):
                continue
            if (nx, ny) in tile_to_id or layer_by_id[grid[ny][nx]] not in ("Block", "Lava"):
                continue
            tile_to_id[(nx, ny)] = iid
            island_tile_kinds[iid][kind_by_id[grid[ny][nx]]] += 1
            seeds.append((nx, ny))

    # Phase 5: finalize per-island `tiles` field — same `% kind` format as `biomes`, now including the Block/Lava tiles propagated in Phase 4.
    for island in islands:
        counter = island_tile_kinds[island["id"]]
        total = sum(counter.values())
        island["tiles"] = " | ".join(f"{pct}% {name}" for name, n in counter.most_common(3) if (pct := round(n / total * 100)) > 0)
    return islands, tile_to_id


# Disk-cached `_compute_islands` — key = save `mtime+size`, pickle format, stale entries dropped on write (single-file cache).
def compute_islands_cached(save: dict, save_path: Path) -> tuple[list[dict], dict[tuple[int, int], int]]:
    key = _cache_key(save_path)
    if key is None:
        return _compute_islands(save)
    cache_file = _CACHE_DIR / f"islands_v8_{key}.pkl"
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
