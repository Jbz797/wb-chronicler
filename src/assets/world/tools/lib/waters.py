# The water a map holds: every enclosed stretch worth a name, and the narrowest crossing between each pair of lands, both read off one mask and cached per save.

from collections import defaultdict
from pathlib import Path

from grid import decode_tile_grid, tile_layer
from islands import compute_islands_cached
from shared import pickle_cached

_FARTHEST_SWIM = 128  # two tides make a crossing, so none past twice this is kept — no speed the game grants buys a swim that long
_MIN_LAKE_TILES = 64  # WB knows no lake at all, so the floor is ours: WB `CITY_ZONE_TILES`, one city zone — under it no town could ever sit on the shore.
_OPEN_SEA = -1  # the one water body that reaches the map edge, standing apart from the lakes indexed from 0
_STEP = 10_000  # a tide counts a straight step in ten-thousandths of a tile, so its two costs stay whole and its depths can be walked in order
_STEP_SLANT = round(_STEP * 2**0.5)  # what a slanted stretch of sea costs a swimmer, against one for its straight neighbour
_UNREACHED = 1 << 40  # deeper than any tide runs, so the first to claim a tile always undercuts it


# Every land tile that touches water, with its island, listed once for both sweeps: an inland tile neither rings a lake nor raises a tide, and most land is inland.
def _coast(water: bytearray, stride: int, island_of) -> list[tuple[int, int]]:
    coast: list[tuple[int, int]] = []
    push = coast.append
    for x, y, island_id in island_of.land():
        i = (y + 1) * stride + x + 1
        if water[i - stride] or water[i + stride] or water[i - 1] or water[i + 1]:
            push((i, island_id))
    return coast


# The mask and its coast built once for both readings: the pools the land encloses make the lakes, the tides raised from every shore make the straits.
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
    coast = _coast(water, stride, island_of)
    pool_at, pools = _pool_map(water, stride)
    return {"lakes": _lakes(pools, pool_at, coast, water, stride), "straits": _straits(water, stride, coast)}


# An enclosed water is named by the shores that ring it, and holds as an islet any land no other water touches — the isles a chronicle reaches last, or never.
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


# The narrowest water between each pair of lands, in tiles swum: every coast floods the sea at once, and where two tides meet their depths add up to the crossing.
def _straits(water: bytearray, stride: int, coast: list[tuple[int, int]]) -> list[dict]:
    straight = (-stride, stride, -1, 1)
    steps = (*((step, _STEP) for step in straight), *((step, _STEP_SLANT) for step in (-stride - 1, -stride + 1, stride - 1, stride + 1)))
    depth, nearest = [_UNREACHED] * len(water), [0] * len(water)
    # Two costs only, so the cheapest water is found by walking the depths in order rather than by a heap — a ring one slant deep holds every tide in flight.
    ring = _STEP_SLANT + 1
    buckets: list[list[int]] = [[] for _ in range(ring)]
    for i, island_id in coast:
        depth[i], nearest[i] = 0, island_id
        buckets[0].append(i)

    gaps: dict[tuple[int, int], int] = {}
    here, afloat = 0, len(coast)
    while afloat and here <= _FARTHEST_SWIM * _STEP:  # a tide reaching nobody is not worth raising: what it would still close, no body could swim
        slot = buckets[here % ring]
        while slot:
            i = slot.pop()
            afloat -= 1
            if depth[i] != here:  # a cheaper tide claimed it since, leaving this entry behind
                continue
            own = nearest[i]
            for step, cost in steps:
                j = i + step
                if not water[j]:
                    continue
                swum = here + cost
                if (reached := depth[j]) > swum:
                    depth[j], nearest[j] = swum, own
                    buckets[swum % ring].append(j)
                    afloat += 1
                elif (rival := nearest[j]) != own:
                    pair = (own, rival) if own < rival else (rival, own)
                    if (span := swum + reached) < gaps.get(pair, span + 1):  # the narrowest the two ever leave
                        gaps[pair] = span
        here += 1
    return [{"between": list(pair), "gap": round(gap / _STEP)} for pair, gap in sorted(gaps.items(), key=lambda kv: (kv[1], kv[0]))]


# Every stretch of sea the map encloses, and every land it holds apart — the map never moves, so what its water says is read once per save.
def waters_cached(save: dict, save_path: Path) -> dict:
    return pickle_cached("waters_v2", save_path, lambda: _compute_waters(save, save_path))
