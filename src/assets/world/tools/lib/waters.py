# The water a map holds: every enclosed stretch worth a name, and the narrowest crossing between each pair of lands, both read off one mask and cached per save.

import re
from collections import defaultdict
from collections.abc import Callable
from heapq import heappop, heappush
from pathlib import Path

from grid import tile_layer, tile_mask
from islands import compute_islands_cached
from shared import pickle_cached, union_root

_FARTHEST_SWIM = 512  # two tides make a crossing, so none past twice this is kept — breath then drowning carry a body far (`actor/info.py`), and the sweep 20 ms
_MIN_LAKE_TILES = 64  # WB knows no lake at all, so the floor is ours: WB `CITY_ZONE_TILES`, one city zone — under it no town could ever sit on the shore.
_OPEN_SEA = -1  # the one water body that reaches the map edge, standing apart from the lakes indexed from 0
_RUN = re.compile(rb"\x01+")  # a row's unbroken water, which the mask's dry border keeps from ever running on into the next row
_STEP = 10_000  # a tide counts a straight step in ten-thousandths of a tile, so its two costs stay whole and its depths can be walked in order
_STEP_SLANT = round(_STEP * 2**0.5)  # what a slanted stretch of sea costs a swimmer, against one for its straight neighbour
_UNREACHED = 1 << 40  # deeper than any tide runs, so the first to claim a tile always undercuts it


# Every land tile that touches water, with its island, for both sweeps — an inland tile rings no lake and raises no tide. Read off the edges, where all coasts lie.
def _coast(water: bytearray, stride: int, island_of) -> list[tuple[int, int]]:
    coast: list[tuple[int, int]] = []
    for x, y, island_id in island_of.edges():
        i = (y + 1) * stride + x + 1
        if water[i - stride] or water[i + stride] or water[i - 1] or water[i + 1]:
            coast.append((i, island_id))
    return coast


# The mask and its coast built once for both readings: the pools the land encloses make the lakes, the tides raised from every shore make the straits.
def _compute_waters(save: dict, save_path: Path) -> dict:
    _, island_of = compute_islands_cached(save, save_path)
    rows = _water_rows(save)
    # The sea as one flat mask ringed by a border of land: every neighbour of a map tile is a valid index, so no sweep below tests a bound or indexes a nested row.
    stride = len(rows[0]) + 2
    water = bytearray(stride) + b"".join(b"\x00" + row + b"\x00" for row in rows) + bytes(stride)
    coast = _coast(water, stride, island_of)
    pool_at, pools = _pool_map(water, stride)
    # What the two lists leave out, said in the data so that an absence never reads as a count: the pools under the floor, the crossings no body could swim.
    hidden = sum(1 for size, _, _, enclosed in pools if enclosed and size < _MIN_LAKE_TILES)
    return {
        "lakes": _lakes(pools, pool_at, coast, water, stride),
        "straits": _straits(water, stride, coast),
        "unlisted": {"lakes": {"count": hidden, "smaller_than": _MIN_LAKE_TILES}, "straits": {"wider_than": 2 * _FARTHEST_SWIM}},
    }


# An enclosed water is named by the shores that ring it, and holds as its own any land no other water touches — the isles a chronicle reaches last, or never.
def _lakes(pools: list[tuple[int, int, int, bool]], pool_at: list[int], coast: list[tuple[int, int]], water: bytearray, stride: int) -> list[dict]:
    # Numbered widest first, as WB numbers its islands: the id is what `places.json` keys a name on, so it must not shift from one chapter to the next.
    kept = [p for p in sorted((p for p, pool in enumerate(pools) if pool[3]), key=lambda p: -pools[p][0]) if pools[p][0] >= _MIN_LAKE_TILES]
    lakes = set(kept)
    pools_of_island: defaultdict[int, set[int]] = defaultdict(set)
    shores: defaultdict[int, set[int]] = defaultdict(set)

    for i, island_id in coast:
        for j in (i - stride, i + stride, i - 1, i + 1):
            if not water[j]:
                continue
            pool = pool_at[j] if pools[pool_at[j]][3] else _OPEN_SEA  # a shore on the open sea is no lake's own, however many lakes it also touches
            if pool != _OPEN_SEA and pool not in lakes:  # a puddle under the floor is no water at all here: it neither rings a land nor keeps it from a lake
                continue
            pools_of_island[island_id].add(pool)
            if pool != _OPEN_SEA:
                shores[pool].add(island_id)

    out = []
    for lake_id, index in enumerate(kept, start=1):
        size, cx, cy, _ = pools[index]
        islands = sorted(i for i, seen in pools_of_island.items() if seen == {index})
        out.append({"centroid": {"x": cx, "y": cy}, "id": lake_id, "islands": islands, "shores": sorted(shores[index] - set(islands)), "size": size})
    return out


# Every body of water with its size, centroid and whether land encloses it — the open sea reaches the map edge. `_lakes` keeps the enclosed ones worth a name.
def _pool_map(water: bytearray, stride: int) -> tuple[list[int], list[tuple[int, int, int, bool]]]:
    width, height = stride - 2, len(water) // stride - 2
    # Walked by the runs of each row rather than tile by tile: a run joins those it overlaps in the row above, and its size and sums are arithmetic.
    runs = [match.span() for match in _RUN.finditer(water)]
    parent = list(range(len(runs)))
    above = row_start = 0  # the first run of the row above still in reach, and the first of this row
    for k, (a, b) in enumerate(runs):
        if a // stride != runs[row_start][0] // stride:
            above, row_start = row_start, k
        while above < row_start and runs[above][1] <= a - stride:  # a row with no water between them leaves every run behind, as it should
            above += 1
        o = above
        while o < row_start and runs[o][0] < b - stride:
            ro, rk = union_root(parent, o), union_root(parent, k)
            parent[max(ro, rk)] = min(ro, rk)
            o += 1

    # Numbered as a sweep of the map meets them, each body by its first run: `_lakes` breaks ties between sizes on that order.
    pool_at, index_of, sums = [-1] * len(water), {}, []
    for k, (a, b) in enumerate(runs):
        if (index := index_of.get(root := union_root(parent, k))) is None:
            index = index_of[root] = len(sums)
            sums.append([0, 0, 0, False])
        pool_at[a:b] = [index] * (b - a)
        (y, x), n = divmod(a, stride), b - a
        pool = sums[index]
        pool[0], pool[1], pool[2] = pool[0] + n, pool[1] + (2 * x + n - 1) * n // 2, pool[2] + y * n
        pool[3] = pool[3] or x == 1 or x + n - 1 == width or y == 1 or y == height
    # Its tiles are not kept, `pool_at` already sites each one: only the size and the centroid, the border's column and row taken back off the mean.
    return pool_at, [(size, sum_x // size - 1, sum_y // size - 1, not open_sea) for size, sum_x, sum_y, open_sea in sums]


# The narrowest water between each pair of lands, in tiles swum: every coast floods the sea at once, and where two tides meet their depths add up to the crossing.
def _straits(water: bytearray, stride: int, coast: list[tuple[int, int]]) -> list[dict]:
    # The straight neighbours and the slanted ones, each at its own cost: the depth a step reaches is reckoned once for four neighbours, not once for each.
    moves = ((-stride, stride, -1, 1), _STEP), ((-stride - 1, -stride + 1, stride - 1, stride + 1), _STEP_SLANT)
    # Each tide carries the coast tile it rose from, so that where two meet their two sources are the crossing's banks: the strait sited, not only measured.
    depth, nearest, source = [_UNREACHED] * len(water), [0] * len(water), [0] * len(water)
    for i, island_id in coast:
        depth[i], nearest[i], source[i] = 0, island_id, i
    # Two costs only, so few depths are ever reached: a heap of them, each with its tiles, walks them in order — a count through every depth idles a million times.
    at_depth, pending = {0: [i for i, _ in coast]}, [0]
    farthest = _FARTHEST_SWIM * _STEP  # a tide reaching nobody is not worth raising: what it would still close, no body could swim

    gaps: dict[tuple[int, int], int] = {}
    banks: dict[tuple[int, int], tuple[int, int]] = {}  # the lower id's bank first, as `between` is
    while pending and (here := heappop(pending)) <= farthest:
        slot = at_depth.pop(here)
        while slot:
            i = slot.pop()
            if depth[i] != here:  # a cheaper tide claimed it since, leaving this entry behind
                continue
            own, origin = nearest[i], source[i]
            for steps, cost in moves:
                swum = here + cost
                bucket = at_depth.get(swum)
                for step in steps:
                    j = i + step
                    if not water[j]:
                        continue
                    if (reached := depth[j]) > swum:
                        depth[j], nearest[j], source[j] = swum, own, origin
                        if bucket is None:
                            bucket = at_depth[swum] = []
                            heappush(pending, swum)
                        bucket.append(j)
                    elif (rival := nearest[j]) != own:
                        pair = (own, rival) if own < rival else (rival, own)
                        if (span := swum + reached) < gaps.get(pair, span + 1):  # the narrowest the two ever leave
                            gaps[pair] = span
                            banks[pair] = (origin, source[j]) if own < rival else (source[j], origin)
    return [
        {"banks": [{"x": i % stride - 1, "y": i // stride - 1} for i in banks[pair]], "between": list(pair), "gap": round(span / _STEP)}
        for pair, span in sorted(gaps.items(), key=lambda kv: (kv[1], kv[0]))
    ]


# The map's water, a row of bytes each, read on the top as WB does: the one mask both the lakes of `waters_cached` and `water_bodies` must agree on.
def _water_rows(save: dict) -> list[bytes]:
    return tile_mask(save, [tile_layer(name) == "Ocean" for name in save.get("tileMap") or []])


# What water a tile lies in — `sea`, a listed `lake` by id, or `pond_tiles` for a pool under the lakes' floor — filled from the tile, never past the largest lake.
def water_bodies(save: dict, save_path: Path) -> Callable[[int, int], dict]:
    lakes = {(lake["size"], lake["centroid"]["x"], lake["centroid"]["y"]): lake["id"] for lake in waters_cached(save, save_path)["lakes"]}
    rows = _water_rows(save)
    width, height, cap = len(rows[0]), len(rows), max((size for size, _, _ in lakes), default=_MIN_LAKE_TILES)

    def body(x: int, y: int) -> dict:
        seen, todo, sum_x, sum_y = {(x, y)}, [(x, y)], 0, 0
        while todo:
            cx, cy = todo.pop()
            if cx in (0, width - 1) or cy in (0, height - 1) or len(seen) > cap:  # the edge, or more than any lake holds: an open sea, as `_pool_map` has it
                return {"sea": True}
            sum_x, sum_y = sum_x + cx, sum_y + cy
            for nx, ny in ((cx - 1, cy), (cx + 1, cy), (cx, cy - 1), (cx, cy + 1)):
                if (nx, ny) not in seen and rows[ny][nx]:
                    seen.add((nx, ny))
                    todo.append((nx, ny))
        size = len(seen)
        lake = lakes.get((size, sum_x // size, sum_y // size))  # sized and centred as `_pool_map` reckons them, which no two lakes share
        return {"lake": lake} if lake is not None else {"pond_tiles": size}

    return body


# Every stretch of sea the map encloses, and every land it holds apart — the map never moves, so what its water says is read once per save.
def waters_cached(save: dict, save_path: Path) -> dict:
    return pickle_cached("waters_v11", save_path, lambda: _compute_waters(save, save_path))
