# The water a map holds: its seas, lakes and rivers worth a name, and the narrowest crossing between each pair of lands, read off one mask and cached per save.

import re
import zlib
from array import array
from collections import defaultdict
from collections.abc import Callable, Iterable
from functools import cache
from heapq import heappop, heappush
from pathlib import Path
from typing import NamedTuple

from grid import HEART_CELL, hearts, tile_block, tile_layer, tile_mask
from islands import compute_islands_cached
from shared import pickle_cached, union_root

_FARTHEST_SWIM = 512  # two tides make a crossing, so none past twice this is kept — breath then drowning carry a body far (`actor/info.py`), and the sweep 20 ms
_ID_BITS = 14  # a body's code on each of its tiles holds its kind above its id: sixteen thousand seas, lakes or rivers, which no map comes near
_KINDS = ("", "sea", "lake", "river")  # a code's kind, as `tile_info` names it
_MIN_LAKE_TILES = 64  # WB knows no lake at all, so the floor is ours: WB `CITY_ZONE_TILES`, one city zone — under it no town could ever sit on the shore.
_OPEN_SEA = -1  # any water that reaches the map edge, standing apart from the lakes indexed from 0
_RIVER_WIDTH = 3  # tiles of mean width, a water's size over its longer side, under which it is a ribbon — a stretch of river, where a lake as large is round
_RUN = re.compile(rb"\x01+")  # a row's unbroken water, which the mask's dry border keeps from ever running on into the next row
_STEP = 10_000  # a tide counts a straight step in ten-thousandths of a tile, so its two costs stay whole and its depths can be walked in order
_STEP_SLANT = round(_STEP * 2**0.5)  # what a slanted stretch of sea costs a swimmer, against one for its straight neighbour
_UNREACHED = 1 << 40  # deeper than any tide runs, so the first to claim a tile always undercuts it


# A water side by side: its size, its mean, whether land encloses it, the map edges it reaches — a bit for west, east, south and north —, its box, its longer side.
class _Pool(NamedTuple):
    size: int
    x: int
    y: int
    enclosed: bool
    edges: int
    box: tuple[int, int, int, int]  # west, east, south, north

    @property
    def span(self) -> int:
        return max(self.box[1] - self.box[0], self.box[3] - self.box[2]) + 1


# A pool's index to the id it goes by, read in C over a whole row: one slot more than there are pools, that the `-1` of a dry tile land on a `0` of its own.
def _by_pool(id_of: dict[int, int], pools: int) -> Callable[[int], int]:
    ids = [0] * (pools + 1)
    for index, given in id_of.items():
        ids[index] = given
    return ids.__getitem__


# Every land tile that touches water, with its island, for both sweeps — an inland tile rings no lake and raises no tide. Read off the edges, where all coasts lie.
def _coast(water: bytearray, stride: int, island_of) -> list[tuple[int, int]]:
    coast: list[tuple[int, int]] = []
    for x, y, island_id in island_of.edges():
        i = (y + 1) * stride + x + 1
        if water[i - stride] or water[i + stride] or water[i - 1] or water[i + 1]:
            coast.append((i, island_id))
    return coast


def _code(kind: str, given: int) -> int:
    return _KINDS.index(kind) << _ID_BITS | given


# The mask and its coast built once for every reading: the pools make the seas, the lakes and the rivers, the tides raised from every shore the straits.
def _compute_waters(save: dict, save_path: Path) -> dict:
    _, island_of = compute_islands_cached(save, save_path)
    rows, tile_map = _water_rows(save), save.get("tileMap") or []
    # The sea as one flat mask ringed by a border of land: every neighbour of a map tile is a valid index, so no sweep below tests a bound or indexes a nested row.
    stride = len(rows[0]) + 2
    water = bytearray(stride) + b"".join(b"\x00" + row + b"\x00" for row in rows) + bytes(stride)
    coast = _coast(water, stride, island_of)
    pool_at, pools = _pool_map(water, stride)

    # A water reaching the map's edge is a sea, a ribbon a stretch of river, any other a lake: each kind numbered apart, its thin pools left to the rivers.
    named = [p for p, pool in enumerate(pools) if pool.size >= _MIN_LAKE_TILES]
    sea_of = _numbered((p for p in named if not pools[p].enclosed), pools)
    thin = {p for p, pool in enumerate(pools) if p not in sea_of and pool.size / pool.span < _RIVER_WIDTH}
    lake_of = _numbered((p for p in named if pools[p].enclosed and p not in thin), pools)
    river_of, rivers = _rivers(pools, pool_at, stride, thin, sea_of, lake_of)
    code_of = {p: _code(kind, given) for kind, ids in (("sea", sea_of), ("lake", lake_of), ("river", river_of)) for p, given in ids.items()}
    code_at = _by_pool(code_of, len(pools))
    shores: defaultdict[int, set[int]] = defaultdict(set)
    for i, island_id in coast:
        for j in (i - stride, i + stride, i - 1, i + 1):
            if code := code_at(pool_at[j]):
                shores[code].add(island_id)
    for river in rivers:
        river["shores"] = sorted(shores[_code("river", river["id"])])

    # A tide rises only where a body can stand: off a rock, the narrowest water between two lands a crest joins would be the one tile at the crest's foot.
    blocks = tile_mask(save, [tile_block(name) is not None for name in tile_map])
    rock = bytes(stride) + b"".join(b"\x00" + row + b"\x00" for row in blocks) + bytes(stride)
    # Deep water pool by pool: a run of it lies within one run of water, so its first tile names the pool of them all.
    deep: defaultdict[int, int] = defaultdict(int)
    for y, row in enumerate(tile_mask(save, [tile_layer(name) == "Ocean" and name.startswith("deep_ocean") for name in tile_map]), start=1):
        for west, end in (run.span() for run in _RUN.finditer(row)):
            deep[pool_at[y * stride + west + 1]] += end - west
    # The map's own tiles alone, row by row, each body's code on its tiles and nothing elsewhere: folded, the runs of one code weigh next to nothing.
    marks = b"".join(array("H", map(code_at, pool_at[row + 1 : row + stride - 1])).tobytes() for row in range(stride, len(pool_at) - stride, stride))
    return {
        "body_at": zlib.compress(marks),
        "lakes": _lakes(pools, pool_at, coast, water, stride, lake_of, shores),
        "rivers": rivers,
        "seas": _seas(pools, pool_at, stride, sea_of, shores, deep),
        "straits": _straits(water, stride, [(i, island_id) for i, island_id in coast if not rock[i]]),
        # What the lists leave out, said in the data so that an absence never reads as a count: the waters under the floor, the crossings no body could swim.
        "unlisted": {"lakes": {"count": len(pools) - len(code_of), "smaller_than": _MIN_LAKE_TILES}, "straits": {"wider_than": 2 * _FARTHEST_SWIM}},
    }


# An enclosed water is named by the shores that ring it, and holds as its own any land no other water touches — the isles a chronicle reaches last, or never.
def _lakes(
    pools: list[_Pool], pool_at: list[int], coast: list[tuple[int, int]], water: bytearray, stride: int, lake_of: dict[int, int], shores: dict[int, set[int]]
) -> list[dict]:
    pools_of_island: defaultdict[int, set[int]] = defaultdict(set)
    for i, island_id in coast:
        for j in (i - stride, i + stride, i - 1, i + 1):
            if not water[j]:
                continue
            pool = pool_at[j] if pools[pool_at[j]].enclosed else _OPEN_SEA  # a shore on the open sea is no lake's own, however many lakes it also touches
            if pool == _OPEN_SEA or pool in lake_of:  # a puddle or a river is no water at all here: it neither rings a land nor keeps it from a lake
                pools_of_island[island_id].add(pool)

    # A heart tile by tile, a lake being small.
    lake_at = _by_pool(lake_of, len(pools))
    middles = hearts([list(map(lake_at, pool_at[row + 1 : row + stride - 1])) for row in range(stride, len(pool_at) - stride, stride)], 1)
    out = []
    for index, lake in lake_of.items():
        islands, (x, y) = sorted(i for i, seen in pools_of_island.items() if seen == {index}), middles[lake]
        shore = sorted(shores[_code("lake", lake)] - set(islands))
        out.append({"heart": {"x": x, "y": y}, "id": lake, "islands": islands, "shores": shore, "size": pools[index].size})
    return out


# Each pool its id, widest first as WB numbers its islands and ties as the sweep met them: what `places.json` keys a name on, and all a code can hold.
def _numbered(kept: Iterable[int], pools: list[_Pool]) -> dict[int, int]:
    return {index: given for given, index in enumerate(sorted(kept, key=lambda p: -pools[p].size)[: (1 << _ID_BITS) - 1], start=1)}


# Every body of water side by side, walked by the runs of each row rather than tile by tile, and the pool each tile belongs to.
def _pool_map(water: bytearray, stride: int) -> tuple[list[int], list[_Pool]]:
    width, height = stride - 2, len(water) // stride - 2
    # A run joins those it overlaps in the row above, and its size and sums are arithmetic.
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

    # Numbered as a sweep of the map meets them, each body by its first run: `_numbered` breaks ties between sizes on that order.
    pool_at, index_of, sums = [-1] * len(water), {}, []
    for k, (a, b) in enumerate(runs):
        (y, x), n = divmod(a, stride), b - a
        if (index := index_of.get(root := union_root(parent, k))) is None:
            index = index_of[root] = len(sums)
            sums.append([0, 0, 0, 0, x, x, y, y])
        pool_at[a:b] = [index] * n
        pool = sums[index]
        pool[0], pool[1], pool[2] = pool[0] + n, pool[1] + (2 * x + n - 1) * n // 2, pool[2] + y * n
        pool[3] |= (x == 1) | (x + n - 1 == width) << 1 | (y == 1) << 2 | (y == height) << 3
        pool[4], pool[5], pool[7] = min(pool[4], x), max(pool[5], x + n - 1), y  # the rows only climb, so the last run's is the northmost
    # Its tiles are not kept, `pool_at` already sites each one: the border's column and row taken back off the mean and the box.
    return pool_at, [
        _Pool(size, sum_x // size - 1, sum_y // size - 1, not edges, edges, (west - 1, east - 1, south - 1, north - 1))
        for size, sum_x, sum_y, edges, west, east, south, north in sums
    ]


# The rivers: thin waters chained wherever two touch by a corner, a river leaving the sea side by side then winding on slantwise — named from the lakes' floor up.
def _rivers(
    pools: list[_Pool], pool_at: list[int], stride: int, thin: set[int], sea_of: dict[int, int], lake_of: dict[int, int]
) -> tuple[dict[int, int], list[dict]]:
    parent = list(range(len(pools)))
    tiles: defaultdict[int, list[int]] = defaultdict(list)
    met: defaultdict[int, set[int]] = defaultdict(set)  # the seas and lakes a thin pool touches by a corner: a river's mouths and springs
    for run in _RUN.finditer(bytes(map(_by_pool(dict.fromkeys(thin, 1), len(pools)), pool_at))):
        for i in range(*run.span()):
            pool = pool_at[i]
            tiles[pool].append(i)
            for step in (stride + 1, stride - 1, 1 - stride, -stride - 1):
                if (other := pool_at[i + step]) < 0 or other == pool:
                    continue
                if other in thin:
                    root, own = union_root(parent, other), union_root(parent, pool)
                    parent[max(root, own)] = min(root, own)
                elif other in sea_of or other in lake_of:
                    met[pool].add(other)

    chains: defaultdict[int, list[int]] = defaultdict(list)
    for pool in sorted(thin):
        chains[union_root(parent, pool)].append(pool)
    sized = sorted(((sum(pools[p].size for p in chain), chain) for chain in chains.values()), key=lambda found: (-found[0], found[1][0]))
    river_of, rivers = {}, []
    for river, (size, chain) in enumerate(((size, chain) for size, chain in sized if size >= _MIN_LAKE_TILES), start=1):
        river_of |= dict.fromkeys(chain, river)
        own = [(i % stride - 1, i // stride - 1) for p in chain for i in tiles[p]]
        mean_x, mean_y = sum(x for x, _ in own) / size, sum(y for _, y in own) / size
        # Sited on its own tile nearest its mean — every tile of a ribbon lies as far from the shore — and ended at both tips of its longer side.
        heart = min(own, key=lambda tile: ((tile[0] - mean_x) ** 2 + (tile[1] - mean_y) ** 2, tile))
        (west, south), (east, north) = map(min, zip(*own)), map(max, zip(*own))
        tips = (min(own), max(own)) if east - west >= north - south else (min(own, key=lambda tile: tile[::-1]), max(own, key=lambda tile: tile[::-1]))
        touched = {other for p in chain for other in met[p]}
        rivers.append(
            {
                "ends": [{"x": x, "y": y} for x, y in tips],
                "heart": {"x": heart[0], "y": heart[1]},
                "id": river,
                "lakes": sorted(lake_of[other] for other in touched if other in lake_of),
                "seas": sorted(sea_of[other] for other in touched if other in sea_of),
                "size": size,
                "waters": len(chain),
            }
        )
    return river_of, rivers


# Every water that reaches the map's edge and is worth a name: the lands it washes, the edges it touches, its heart — its mean falls ashore of any gulf.
def _seas(pools: list[_Pool], pool_at: list[int], stride: int, sea_of: dict[int, int], shores: dict[int, set[int]], deep: dict[int, int]) -> list[dict]:
    cols, half = (stride - 2) // HEART_CELL, HEART_CELL // 2
    firsts = range((half + 1) * stride + half + 1, len(pool_at) - stride, HEART_CELL * stride)
    sea_at = _by_pool(sea_of, len(pools))
    middles = hearts([list(map(sea_at, pool_at[first : first + cols * HEART_CELL : HEART_CELL])) for first in firsts])  # one tile stands for its cell
    seas = []
    for index, sea in sea_of.items():
        x, y = middles.get(sea) or ((own := pool_at.index(index)) % stride - 1, own // stride - 1)  # too thin for any cell: the first of its tiles
        pool = pools[index]
        reached = sorted(side for bit, side in enumerate("WESN") if pool.edges >> bit & 1)
        seas.append(
            {
                "deep_pct": round(deep.get(index, 0) / pool.size * 100, 1) or None,
                "edges": reached,
                "heart": {"x": x, "y": y},
                "id": sea,
                "shores": sorted(shores[_code("sea", sea)]),
                "size": pool.size,
            }
        )
    return seas


# The narrowest water between two lands in `swim_tiles`: every coast floods at once, its first step weighing half, and two meeting tides add up to the crossing.
def _straits(water: bytearray, stride: int, coast: list[tuple[int, int]]) -> list[dict]:
    # The straight neighbours and the slanted ones, each at its own cost: the depth a step reaches is reckoned once for four neighbours, not once for each.
    moves = ((-stride, stride, -1, 1), _STEP), ((-stride - 1, -stride + 1, stride - 1, stride + 1), _STEP_SLANT)
    # Each tide carries the coast tile it rose from, so that where two meet their two sources are the crossing's banks: the strait sited, not only measured.
    depth, nearest, source = [_UNREACHED] * len(water), [0] * len(water), [0] * len(water)
    for i, island_id in coast:
        depth[i], nearest[i], source[i] = 0, island_id, i
    # Four costs only, two steps and their halves off a shore, so few depths are ever reached: a heap of them, each with its tiles, walks them in order.
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
                swum = here + (cost if here else cost // 2)  # both costs even, so the half stays whole
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
        {"banks": [{"x": i % stride - 1, "y": i // stride - 1} for i in banks[pair]], "between": list(pair), "swim_tiles": round(span / _STEP)}
        for pair, span in sorted(gaps.items(), key=lambda kv: (kv[1], kv[0]))
    ]


# The map's water, a row of bytes each, read on the top as WB does: the one mask `waters_cached` and `water_bodies` must agree on.
def _water_rows(save: dict) -> list[bytes]:
    return tile_mask(save, [tile_layer(name) == "Ocean" for name in save.get("tileMap") or []])


# Every stretch of water the map holds, read once per save since the map never moves — the bodies' mask with it, which only `water_bodies` reads.
def _waters(save: dict, save_path: Path) -> dict:
    return pickle_cached("waters_v15", save_path, lambda: _compute_waters(save, save_path))


# What water a tile lies in — a `sea`, a `lake` or a `river` by id, read off the mask — or `pond_tiles`, a water under their floor filled from the tile.
def water_bodies(save: dict, save_path: Path) -> Callable[[int, int], dict]:
    body_at = array("H", zlib.decompress(_waters(save, save_path)["body_at"]))
    height = len(save.get("tileArray") or [])
    width = len(body_at) // (height or 1)
    rows = cache(lambda: _water_rows(save))  # read for a pond alone: most water a tile is asked of is a sea, which the mask names at once

    def body(x: int, y: int) -> dict:
        if code := body_at[y * width + x]:
            return {_KINDS[code >> _ID_BITS]: code & ((1 << _ID_BITS) - 1)}
        seen, todo = {(x, y)}, [(x, y)]
        while todo:
            cx, cy = todo.pop()
            for nx, ny in ((cx - 1, cy), (cx + 1, cy), (cx, cy - 1), (cx, cy + 1)):
                if (nx, ny) not in seen and 0 <= nx < width and 0 <= ny < height and rows()[ny][nx]:
                    seen.add((nx, ny))
                    todo.append((nx, ny))
        return {"pond_tiles": len(seen)}

    return body


# The seas, the lakes, the rivers and the straits between the lands, as `geography … waters` prints them.
def waters_cached(save: dict, save_path: Path) -> dict:
    return {key: value for key, value in _waters(save, save_path).items() if key != "body_at"}
