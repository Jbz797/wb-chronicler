# Reusable island detection — mirrors WB's `IslandsCalculator.countLandIslands`. Consumed by `actor/`, `city/`, `geography/`, `kingdom/` and `tiles/` alike.
#
# Algorithm (extracted from `Assembly-CSharp.dll`):
# 1. Each tile has a `TileLayerType` (Null/Ground/Ocean/Lava/Block/Goo) — Block covers mountains/summit/walls, NOT Ground.
# 2. `MapChunk.calculateRegions` splits each 16×16 chunk into `MapRegion`s — each region = an 8-conn component of same-`layer_type` tiles within the chunk.
# 3. `IslandsCalculator.findIslands` + `startFill` flood-fill regions across chunk borders via `region.neighbours` (same-type adjacency) into `TileIsland`s.
# 4. A land mass is an island once it could hold a city: WB `Globals.CITY_MIN_ISLAND_TILES`. Its own `countLandIslands` counts regions instead, which
#    lets a compact islet straddling four chunks pass while a wider one inside two fails — a tally the game shows nowhere and no chronicle can use.

import pickle
from array import array
from collections import Counter, deque
from pathlib import Path

from grid import decode_tile_grid, tile_kind, tile_layer
from shared import CACHE_DIR, save_cache_key

_BLOCK_TILES = frozenset({"$wall$", "frozen_low", "mountains", "summit"})  # WB `TileTypeBase.block` tiles — block diagonals, which splits regions.
_CHUNK_SIZE = 16  # WB's `CHUNK_SIZE` constant — regions live inside 16×16 chunks.
_CITY_MIN_ISLAND_TILES = 300  # WB `Globals.CITY_MIN_ISLAND_TILES`: under it no city is ever founded, so the land bears no history worth a name.
_DELTAS_4 = ((-1, 0), (1, 0), (0, -1), (0, 1))
_DELTAS_8 = ((-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1))


# Tile → island id over a flat row-major grid, `0` for water (ids start at 1). The dict it replaces cost 32 ms to unpickle and 1.95 MB; this costs neither.
class _TileIslands:
    __slots__ = ("_grid", "_height", "_width")

    def __init__(self, tile_to_id: dict[tuple[int, int], int], width: int, height: int):
        self._grid, self._height, self._width = array("H", bytes(2 * width * height)), height, width
        for (x, y), island_id in tile_to_id.items():
            self._grid[y * width + x] = island_id

    # Same contract as the dict it replaces — `default` off-map or on water.
    def get(self, pos: tuple[int, int], default=None):
        x, y = pos
        if 0 <= x < self._width and 0 <= y < self._height and (island_id := self._grid[y * self._width + x]):
            return island_id
        return default

    # Every land tile and the island it belongs to, read straight off the flat grid: a sweep of the map would otherwise pay a `get` per tile, water included.
    def land(self):
        width = self._width
        for y in range(self._height):
            row = y * width
            for x in range(width):
                if island_id := self._grid[row + x]:
                    yield x, y, island_id


# Build the islands list and a tile-to-island lookup keyed by WB-actor coordinates (no y inversion — `row` IS the actor y, see `chronicler.md`).
def _compute_islands(save: dict) -> tuple[list[dict], _TileIslands]:
    tile_map = save.get("tileMap") or []
    layer_by_id = [tile_layer(name) for name in tile_map]
    block_by_id = [name.split(":", 1)[0] in _BLOCK_TILES for name in tile_map]

    # Precompute per-tile-id kind once — Phase 1 + Phase 4 BFSs touch ~10⁵ tiles, each function call would otherwise be repeated for the same id.
    kind_by_id = [tile_kind(name) for name in tile_map]
    grid = decode_tile_grid(save)
    if not grid:
        return [], _TileIslands({}, 0, 0)
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
                    kinds: list[str] = []  # tallied in one C-level pass below, where `counter[k] += 1` per tile would cost a bytecode round-trip each
                    queue = [(sx, sy)]  # a list popped from the tail, not a deque: the fill is order-agnostic
                    region_grid[sy][sx] = region_id
                    while queue:
                        x, y = queue.pop()
                        tiles.append((x, y))
                        tid = grid[y][x]
                        kinds.append(kind_by_id[tid])
                        inner = cx0 < x < cx1 - 1 and cy0 < y < cy1 - 1  # Off the chunk rim, four tiles in five, every neighbour is in: one test, not eight.
                        for dx, dy in _DELTAS_8:
                            nx, ny = x + dx, y + dy
                            if not inner and not (cx0 <= nx < cx1 and cy0 <= ny < cy1):
                                continue
                            if region_grid[ny][nx] != -1 or layer_by_id[grid[ny][nx]] != layer:
                                continue
                            # `isDiagonalBlockedByCorners`: blocked if either orthogonal corner is a `block` tile — never out of bounds, the chunk test pins both.
                            if dx and dy and (block_by_id[grid[y][x + dx]] or block_by_id[grid[y + dy][x]]):
                                continue
                            region_grid[ny][nx] = region_id
                            queue.append((nx, ny))
                    regions.append({"layer": layer, "tile_kinds": Counter(kinds), "tiles": tiles})

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

    # Phase 3: keep the Ground masses wide enough to ever carry a city. Block and Lava join in Phase 4, after the count, as WB's own Ground islands do.
    kept: list[tuple[int, Counter[str], list[tuple[int, int]]]] = []

    for r_indices in component_regions:
        # Measured before anything is built: nine land masses in ten fall under the floor, and gathering their tiles and kinds first cost a fifth of the run.
        if regions[r_indices[0]]["layer"] != "Ground" or sum(len(regions[i]["tiles"]) for i in r_indices) < _CITY_MIN_ISLAND_TILES:
            continue
        tile_kinds = Counter()
        tiles = []
        for r_idx in r_indices:
            tile_kinds.update(regions[r_idx]["tile_kinds"])
            tiles.extend(regions[r_idx]["tiles"])
        kept.append((len(tiles), tile_kinds, tiles))
    kept.sort(key=lambda c: -c[0])
    islands = []
    island_tile_kinds: dict[int, Counter[str]] = {}
    tile_to_id: dict[tuple[int, int], int] = {}
    seeds: deque[tuple[int, int]] = deque()

    # Centroid summed in the same walk that stamps the ids: three passes over the island's tiles would otherwise do the work of one.
    for idx, (size, tile_kinds, tiles) in enumerate(kept, start=1):
        sum_x = sum_y = 0
        for gx, gy in tiles:
            sum_x += gx
            sum_y += gy
            tile_to_id[(gx, gy)] = idx
            seeds.append((gx, gy))
        island_tile_kinds[idx] = tile_kinds  # `kept` is spent from here on, so Phase 4 may swell this counter in place
        islands.append({"centroid": {"x": sum_x // size, "y": sum_y // size}, "id": idx, "size": size})

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

    # Phase 5: finalize per-island `tiles` field — the ground it is made of, Block/Lava tiles from Phase 4 included. What grows on it is `geography biomes`.
    for island in islands:
        counter = island_tile_kinds[island["id"]]
        total = sum(counter.values())
        island["tiles"] = " | ".join(f"{pct}% {name}" for name, n in counter.most_common(3) if (pct := round(n / total * 100)) > 0)
    return islands, _TileIslands(tile_to_id, width, height)


# Disk-cached `_compute_islands` — key = save `mtime+size`, pickle format, stale entries dropped on write (single-file cache).
def compute_islands_cached(save: dict, save_path: Path) -> tuple[list[dict], _TileIslands]:
    key = save_cache_key(save_path)
    if key is None:
        return _compute_islands(save)
    cache_file = CACHE_DIR / f"islands_v11_{key}.pkl"
    if cache_file.exists():
        try:
            with cache_file.open("rb") as f:
                return pickle.load(f)
        except Exception:  # noqa: BLE001 — corrupt cache, fall through to recompute.
            cache_file.unlink(missing_ok=True)
    result = _compute_islands(save)
    CACHE_DIR.mkdir(exist_ok=True)
    for old in CACHE_DIR.glob("islands_*.pkl"):
        if old.name != cache_file.name:
            old.unlink(missing_ok=True)
    with cache_file.open("wb") as f:
        pickle.dump(result, f)
    return result
