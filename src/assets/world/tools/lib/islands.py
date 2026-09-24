# Reusable island detection — mirrors WB's `IslandsCalculator.countLandIslands`. Consumed by every tool that sites a body or a place, and by `lib/waters.py`.
#
# Algorithm (extracted from `Assembly-CSharp.dll`):
# 1. Each tile has a `TileLayerType` (Null/Ground/Ocean/Lava/Block/Goo) — Block covers mountains/summit/walls, NOT Ground.
# 2. `MapChunk.calculateRegions` splits each 16×16 chunk into `MapRegion`s — each region = an 8-conn component of same-`layer_type` tiles within the chunk.
# 3. `IslandsCalculator.findIslands` + `startFill` flood-fill regions across chunk borders via `region.neighbours` (same-type adjacency) into `TileIsland`s.
# 4. A land mass is an island once it could hold a city: WB `Globals.CITY_MIN_ISLAND_TILES`. Its own `countLandIslands` counts regions instead, which
#    lets a compact islet straddling four chunks pass while a wider one inside two fails — a tally the game shows nowhere and no chronicle can use.

import re
import sys
from array import array
from collections import Counter, defaultdict, deque
from collections.abc import Iterator
from pathlib import Path

from grid import decode_tile_grid, tile_block, tile_kind, tile_layer
from shared import pickle_cached, union_root

_CHUNK_SIZE = 16  # WB's `CHUNK_SIZE` constant — regions live inside 16×16 chunks.
_CITY_MIN_ISLAND_TILES = 300  # WB `Globals.CITY_MIN_ISLAND_TILES`: under it no city is ever founded, so the land bears no history worth a name.
_DELTAS_4 = ((-1, 0), (1, 0), (0, -1), (0, 1))
_LAND = bytes([0] + [255] * 255)  # a land id, one byte, read as a full byte and water as none: the mask the edges are cut to
_ROCK = bytes.maketrans(b"\x01\x02", b"\x00\x01")  # the tile codes read for rock alone, ground cleared
_RUN = re.compile(rb"\x01+")  # a run of ground, sought between a row's own bounds so that it never runs on into the next
_SET = re.compile(rb"[^\x00]")  # a byte the mask kept


# Tile → island id over a flat row-major grid, `0` for water (ids start at 1). The dict it replaces cost 32 ms to unpickle and 1.95 MB; this costs neither.
class _TileIslands:
    __slots__ = ("_edges", "_grid", "_height", "_islets", "_width")

    # Wraps what the phases filled — handed over, not copied: already the shape this class reads from. `None` edges: every land tile stands in.
    def __init__(self, id_grid: array, width: int, height: int, edges: array | None = None, islets: dict[int, int] | None = None):
        self._edges, self._grid, self._height, self._islets, self._width = edges, id_grid, height, islets, width

    # Every land tile and its island, a row at a time off the flat grid: what `edges` hands out where one byte could not hold the ids.
    def _land(self):
        for y in range(self._height):
            for x, island_id in enumerate(self.row(y)):
                if island_id:
                    yield x, y, island_id

    # The land tiles with a neighbour off their own land, corners counting: a land's nearest tile to a point off it is one — a step toward the point leaves it.
    def edges(self):
        if self._edges is None:
            yield from self._land()
            return
        for i in self._edges:
            y, x = divmod(i, self._width)
            yield x, y, self._grid[i]

    # Same contract as the dict it replaces — `default` off-map or on water.
    def get(self, pos: tuple[int, int], default=None):
        x, y = pos
        if 0 <= x < self._width and 0 <= y < self._height and (island_id := self._grid[y * self._width + x]):
            return island_id
        return default

    # How much ground the islet under `pos` holds, lent to its rock as a land's is — `0` on a counted land, on water, or on rock that touches no ground.
    def islet_size(self, pos: tuple[int, int]) -> int:
        x, y = pos
        return self._islets.get(y * self._width + x, 0) if self._islets is not None and 0 <= x < self._width and 0 <= y < self._height else 0

    # The island ids of tiles listed row-major, as WB lists `fire` and `frozen_tiles`, read in C where a `get` per tile tests its bounds; `0` off the lands.
    def listed_ids(self, indices: list[int]) -> Iterator[int]:
        return map(self._grid.__getitem__, indices)

    # Lands that touch with no water between, a crest no body crosses on foot: the border's length and its middle tile, off the edges, each pair of tiles met once.
    def ridges(self) -> list[dict]:
        rows = [self.row(y) for y in range(self._height)]
        sides: defaultdict[tuple[int, int], tuple[set, set]] = defaultdict(lambda: (set(), set()))
        for x, y, own in self.edges():
            for nx, ny in ((x + 1, y), (x - 1, y + 1), (x, y + 1), (x + 1, y + 1)):
                if 0 <= nx < self._width and ny < self._height and (other := rows[ny][nx]) and other != own:
                    low, high = sides[(own, other) if own < other else (other, own)]
                    (low if own < other else high).add((x, y))
                    (high if own < other else low).add((nx, ny))
        out = []
        for pair, (low, high) in sides.items():
            tiles = low | high
            mean_x, mean_y = sum(x for x, _ in tiles) / len(tiles), sum(y for _, y in tiles) / len(tiles)
            x, y = min(tiles, key=lambda t: ((t[0] - mean_x) ** 2 + (t[1] - mean_y) ** 2, t))
            out.append({"at": {"x": x, "y": y}, "between": list(pair), "length": max(len(low), len(high))})
        return sorted(out, key=lambda r: (-r["length"], r["between"]))

    # One row's island ids, `0` on water or a rock too small to count: a sweep that already walks the grid reads them by index rather than asking `get` per tile.
    def row(self, y: int) -> array:
        return self._grid[y * self._width : (y + 1) * self._width]


# Build the islands list and a tile-to-island lookup keyed by WB-actor coordinates (no y inversion — `row` IS the actor y, see `chronicler.md`).
def _compute_islands(save: dict) -> tuple[list[dict], _TileIslands]:
    tile_map = save.get("tileMap") or []
    layer_by_id = [tile_layer(name) for name in tile_map]
    block_by_id = [tile_block(name) is not None for name in tile_map]  # a `block` tile bars diagonals, which splits regions
    kind_by_id = [tile_kind(name) for name in tile_map]
    grid = decode_tile_grid(save)
    if not grid:
        return [], _TileIslands(array("H"), 0, 0)
    height, width = len(grid), len(grid[0])
    # A byte per tile, 1 on ground and 2 on rock, so that C does the finding: a regex the runs of ground, a shift the ground beside rock.
    code_by_id = [1 if layer == "Ground" else 2 if layer in ("Block", "Lava") else 0 for layer in layer_by_id]
    codes = b"".join(bytes(map(code_by_id.__getitem__, row)) for row in grid)
    rock = codes.translate(_ROCK)

    # Phase 1: WB's Ground masses off each row's runs — side by side tiles join, by a corner only within a chunk and past no `block` (`isDiagonalBlockedByCorners`).
    runs: list[tuple[int, int, int]] = []  # `(y, west, east + 1)`, row-major
    rows: list[list[tuple[int, int, int]]] = []  # each row's runs, as `(west, east + 1, run index)`
    for y in range(height):
        base, row = y * width, []
        for match in _RUN.finditer(codes, base, base + width):
            west, end = match.start() - base, match.end() - base
            row.append((west, end, len(runs)))
            runs.append((y, west, end))
        rows.append(row)

    parent = list(range(len(runs)))
    for y in range(1, height):
        above, one_chunk = rows[y - 1], y % _CHUNK_SIZE != 0
        first = 0
        for a, b, k in rows[y]:
            while first < len(above) and above[first][1] < a:  # wholly west of this run and of every one after it: not even a corner touches
                first += 1
            for o in range(first, len(above)):
                oa, ob, q = above[o]
                if oa > b:
                    break
                if oa < b and a < ob:
                    joined = True
                elif not one_chunk:
                    joined = False
                elif ob == a:  # the run above stops just west of this one's start: they touch by a corner
                    joined = a % _CHUNK_SIZE != 0 and not (block_by_id[grid[y - 1][a]] or block_by_id[grid[y][a - 1]])
                else:  # it starts just east of this one's end
                    joined = oa % _CHUNK_SIZE != 0 and not (block_by_id[grid[y - 1][oa - 1]] or block_by_id[grid[y][oa]])
                if joined:
                    rq, rk = union_root(parent, q), union_root(parent, k)
                    parent[max(rq, rk)] = min(rq, rk)

    # Per mass, its size, its runs, and where WB's chunk sweep first meets it — chunk by chunk, row by row: its regions were numbered so, and ties in size fall so.
    chunks_across = -(-width // _CHUNK_SIZE)
    masses: dict[int, list] = {}
    for k, (y, a, b) in enumerate(runs):
        met = ((y // _CHUNK_SIZE * chunks_across + a // _CHUNK_SIZE) * _CHUNK_SIZE + y % _CHUNK_SIZE) * _CHUNK_SIZE + a % _CHUNK_SIZE
        if (mass := masses.get(root := union_root(parent, k))) is None:
            masses[root] = [b - a, met, [(y, a, b)]]
        else:
            mass[0] += b - a
            mass[1] = min(mass[1], met)
            mass[2].append((y, a, b))

    # Phase 3: keep the Ground masses wide enough to ever carry a city. Block and Lava join in Phase 4, after the count, as WB's own Ground islands do.
    kept = sorted((mass for mass in masses.values() if mass[0] >= _CITY_MIN_ISLAND_TILES), key=lambda m: (-m[0], m[1]))  # the id still provisional: see Phase 4
    island_tile_kinds: dict[int, Counter[str]] = {}
    # Phase 4 grows from ground beside rock alone, found in C by the rock mask shifted a tile each way: a shift wrapping a row seeds a tile that claims nothing.
    wall = int.from_bytes(rock, "little")
    beside_rock = ((wall >> 8) | (wall << 8) | (wall >> 8 * width) | (wall << 8 * width)).to_bytes(len(rock) + width, "little")
    seeds: deque[tuple[int, int]] = deque()

    # Per provisional id, `[size, sum_x, sum_y, west, east, south, north]`: arithmetic over the runs, a run's columns summing as a series.
    frames: list[list[int]] = [[]]
    for idx, (size, _, own_runs) in enumerate(kept, start=1):
        by_id: Counter[int] = Counter()
        sum_x = sum_y = 0
        for y, a, b in own_runs:
            by_id.update(grid[y][a:b])
            sum_x += (a + b - 1) * (b - a) // 2
            sum_y += y * (b - a)
            seeds.extend((i, idx) for i in filter(beside_rock.__getitem__, range(y * width + a, y * width + b)))
        kinds: Counter[str] = Counter()
        for tile_id, n in by_id.items():
            kinds[kind_by_id[tile_id]] += n
        island_tile_kinds[idx] = kinds
        west, east = min(a for _, a, _ in own_runs), max(b for _, _, b in own_runs) - 1
        frames.append([size, sum_x, sum_y, west, east, own_runs[0][0], own_runs[-1][0]])

    # Phase 4: the id bleeds into nearby Block/Lava so a body on a mountain has a land, in size and frame too; a rock two lands reach at once takes the lower id.
    lent: dict[int, int] = {}
    while seeds:
        i, iid = seeds.popleft()
        y, x = divmod(i, width)
        for dx, dy in _DELTAS_4:
            nx, ny = x + dx, y + dy
            if not (0 <= nx < width and 0 <= ny < height) or not rock[j := i + dy * width + dx] or j in lent:
                continue
            lent[j] = iid
            island_tile_kinds[iid][kind_by_id[grid[ny][nx]]] += 1
            frame = frames[iid]
            frame[0] += 1
            frame[1] += nx
            frame[2] += ny
            frame[3], frame[4], frame[5], frame[6] = min(frame[3], nx), max(frame[4], nx), min(frame[5], ny), max(frame[6], ny)
            seeds.append((j, iid))

    # Dealt again by the whole land, largest first, so the ids keep following size — ties hold the ground's order. Only then stamped: no grid to renumber.
    order = sorted(range(1, len(frames)), key=lambda i: -frames[i][0])
    final = [0] * len(frames)
    for new_id, old_id in enumerate(order, start=1):
        final[old_id] = new_id
    # Flat and row-major: a `{(x, y): id}` dict would hash a tuple on every read, and `row` hands a caller its slice as is.
    id_grid = array("H", bytes(2 * width * height))
    for old_id, (_, _, own_runs) in enumerate(kept, start=1):
        stamp = array("H", [final[old_id]])
        for y, a, b in own_runs:
            id_grid[y * width + a : y * width + b] = stamp * (b - a)
    for j, iid in lent.items():
        id_grid[j] = final[iid]

    # Each ground mass too small to count stamps its size, lent to the rock no land took: an islet reads how much of it there is, where a bare flag read as a rock
    islets: dict[int, int] = {}  # sparse, flat index → size: a grid of the map would pickle two bytes a tile for the few thousand an islet holds
    islet_seeds: deque[tuple[int, int]] = deque()
    for size, _, own_runs in masses.values():
        if size < _CITY_MIN_ISLAND_TILES:
            for y, a, b in own_runs:
                islets.update(dict.fromkeys(range(y * width + a, y * width + b), int(size)))
                islet_seeds.extend((i, size) for i in filter(beside_rock.__getitem__, range(y * width + a, y * width + b)))
    while islet_seeds:
        i, size = islet_seeds.popleft()
        y, x = divmod(i, width)
        for dx, dy in _DELTAS_4:
            nx, ny = x + dx, y + dy
            if 0 <= nx < width and 0 <= ny < height and rock[j := i + dy * width + dx] and j not in lent and j not in islets:
                islets[j] = size
                islet_seeds.append((j, size))

    # Phase 5: the islands, with their `tiles` field — the ground they are made of, Block/Lava tiles from Phase 4 included. What grows on it is `geography biomes`.
    islands = []
    for new_id, old_id in enumerate(order, start=1):
        size, sum_x, sum_y, west, east, south, north = frames[old_id]
        counter = island_tile_kinds[old_id]
        made_of = " | ".join(f"{pct}% {name}" for name, n in counter.most_common(3) if (pct := round(n / size * 100)) > 0)
        # `size` against the box says how ragged a land is: both of the whole land, mountains in, as the centroid is.
        bounds = {"x": [west, east], "y": [south, north]}
        islands.append({"bounds": bounds, "centroid": {"x": sum_x // size, "y": sum_y // size}, "id": new_id, "size": size, "tiles": made_of})

    return islands, _TileIslands(id_grid, width, height, _edge_tiles(id_grid, width), islets)


# Edge tiles, flat, found in C: a byte per land id, the grid one integer, a tile kept where a neighbour differs, a wrapped shift keeping more. `None` past 255 lands.
def _edge_tiles(id_grid: array, width: int) -> array | None:
    raw = id_grid.tobytes()
    low, high = (0, 1) if sys.byteorder == "little" else (1, 0)
    if raw[high::2].strip(b"\x00"):
        return None
    ids = raw[low::2]
    whole, differs = int.from_bytes(ids, "little"), 0
    for shift in (8, 8 * (width - 1), 8 * width, 8 * (width + 1)):
        differs |= (whole ^ (whole >> shift)) | (whole ^ (whole << shift))
    kept = (differs & int.from_bytes(ids.translate(_LAND), "little")).to_bytes(len(ids) + width + 2, "little")[: len(ids)]
    return array("I", (match.start() for match in _SET.finditer(kept)))


# Disk-cached `_compute_islands`, one slot per save like every sweep of the map: `actor … --since` weighs two saves, which a single slot would evict in turn.
def compute_islands_cached(save: dict, save_path: Path) -> tuple[list[dict], _TileIslands]:
    return pickle_cached("islands_v17", save_path, lambda: _compute_islands(save))
