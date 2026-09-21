# A body's walk over the map, as WB's pathfinder lets it — counted in tiles at a flat pace: a step costs its length, stretched by what slows the body there.
#
# The rules (extracted from `Assembly-CSharp.dll`):
# 1. `AStarFinder.FindPath` bars every `block` tile, lava, and on foot all that is not `ground` — goo. It pays 1 a straight step and 1.414 a slanted one,
#    over 8 neighbours — 4 beside a wall.
# 2. It never tests a corner, but it only walks the regions `MapBox.calcPath` chains first: a slanted step cuts past an open corner, while two closed ones
#    join only inside a 16×16 chunk, and past no rock (`isDiagonalBlockedByCorners`) — the very rule `islands` joins its lands by.
# 3. `Actor.precalcMovementSpeed` slows a body on a ground naming a tag it lacks (`ignore_walk_multiplier_if_tag`) — a ground without one slows none.
#    Entanglewood takes a fifth off the pace under a tree, the water nothing until the breath runs out. The speed is floored at 1 before WB's common 0.4.
# 4. `ActorMove.goTo` lets no body swim toward a spot of its own island — it walks round the bay —, and none the water burns at all: `Gait.ashore`.

from heapq import heappop, heappush
from math import inf

from grid import tile_block, tile_layer, tile_mask
from shared import DIAGONAL_EXTRA, building_tile, world_laws

_BARRED, _WATER, _OPEN = 0, 1, 2  # a tile's class: `_OPEN` and above walk, each slow ground past it holding its own
_CHUNK = 16  # WB's `CHUNK_SIZE`: its regions never span two chunks, and neither do the corners they join by
_DIAGONAL = 1 + DIAGONAL_EXTRA
_OUT_OF_BREATH = 0.4  # WB's pace for a swimmer whose stamina has run out

_SLOW_GROUNDS = {
    "desert_high": (0.7, "walk_adaptation_sand"),
    "desert_low": (0.7, "walk_adaptation_sand"),
    "frozen_high": (0.8, "walk_adaptation_snow"),
    "frozen_low": (0.8, "walk_adaptation_snow"),
    "permafrost_high": (0.8, "walk_adaptation_snow"),
    "permafrost_low": (0.8, "walk_adaptation_snow"),
    "sand": (0.5, "walk_adaptation_sand"),
    "snow_hills": (0.6, "walk_adaptation_snow"),
    "snow_sand": (0.6, "walk_adaptation_snow"),
    "swamp_high": (0.6, "walk_adaptation_swamp"),
    "swamp_low": (0.6, "walk_adaptation_swamp"),
}  # WB `walk_multiplier` of the grounds that name a tag: the road's 1.5, the tumor's 0.8 and the like name none, so no body ever feels them

_SLOW_CLASS = {name: _OPEN + 1 + rank for rank, name in enumerate(_SLOW_GROUNDS)}
_SWIFT_SWIM = 5.0  # WB's `fast_swimming` pace in the water, where such a body spends no breath either
_TANGLE = 0.8  # Entanglewood's pace on a tile a tree stands on (`FloraType.Tree`), for any body not aloft
_TREE_FOOTPRINT = (1, 1, 1, 0)  # WB `BuildingFundament` (left, right, top, bottom) of most trees: three tiles wide, two high, the trunk on the lower row

_TREES = frozenset(
    {
        "birch_tree",
        "cacti_tree",
        "candy_tree",
        "celestial_tree",
        "celestial_tree_small",
        "clover_tree",
        "corrupted_tree",
        "corrupted_tree_big",
        "crystal_tree",
        "desert_tree",
        "enchanted_tree",
        "garlic_tree",
        "infernal_tree",
        "infernal_tree_big",
        "infernal_tree_small",
        "jungle_tree",
        "lemon_tree",
        "maple_tree",
        "palm_tree",
        "paradox_tree",
        "pine_tree",
        "rocklands_tree",
        "savanna_tree_1",
        "savanna_tree_2",
        "savanna_tree_big_1",
        "savanna_tree_big_2",
        "singularity_tree",
        "swamp_tree",
        "tree_green_1",
        "tree_green_2",
        "tree_green_3",
        "wasteland_tree",
    }
)  # WB `BuildingLibrary.addTrees` bar `mushroom_tree` (a fungus) and the three `flower_tree_*` (plants): Entanglewood binds trees alone

_WALLED_DELTAS = tuple((dx, dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1))  # a wall's own tile and its eight neighbours, all walked straight

_WIDE_TREES = {
    "celestial_tree": (2, 2, 2, 0),
    "corrupted_tree_big": (2, 2, 1, 0),
    "infernal_tree_big": (2, 2, 1, 0),
    "infernal_tree_small": (0, 0, 1, 0),
    "savanna_tree_big_1": (2, 2, 1, 0),
    "savanna_tree_big_2": (2, 2, 1, 0),
}


# Each tile yielded once, cheapest first; a step costs its length times its two tiles' mean pace, both ways alike — water reached with less swum is searched again.
def _settle(walk_map: "WalkMap", gait: "Gait", x0: int, y0: int, limit: float, bound: float, aim: tuple[int, int, float] | None):
    classes, trees, walled, width, height = walk_map._classes, walk_map._trees, walk_map._walled, walk_map.width, walk_map._height
    land, tangled, swim, tired, breath, reach = gait._land, gait._tangled, gait._swim, gait._tired, gait._breath, gait.reach
    tireless = breath == inf  # nothing to keep of what was swum: every crossing is the same, and none is searched twice
    tx, ty, scale = aim or (0, 0, 0.0)
    start = y0 * width + x0
    best, swum_at, settled = {start: 0.0}, {start: 0.0}, set()
    heap = [(0.0, 0.0, start, 0.0)]
    while heap:
        _, cost, tile, swum = heappop(heap)
        kind = classes[tile]
        if cost > best[tile] and (kind != _WATER or swum > swum_at[tile]):  # a stale entry, unless it swam less to get there
            continue
        if tile not in settled:
            settled.add(tile)
            yield tile, cost
        if kind == _BARRED and tile != start:  # where the walk stops: the rock a body stands against, never a road through it
            continue
        here = (swim if swum <= breath else tired) if kind == _WATER else (tangled if trees[tile] else land)[kind] if kind else 1.0
        y, x = divmod(tile, width)
        straight = tile in walled
        for dx in (-1, 0, 1):
            nx = x + dx
            if not 0 <= nx < width:
                continue
            for dy in (-1, 0, 1):
                ny = y + dy
                if not (dx or dy) or not 0 <= ny < height:
                    continue
                if dx and dy:
                    if straight:
                        continue
                    side, other = classes[tile + dx], classes[tile + dy * width]
                    if side < _OPEN and other < _OPEN and not (side and other and nx // _CHUNK == x // _CHUNK and ny // _CHUNK == y // _CHUNK):
                        continue
                    length = _DIAGONAL
                else:
                    length = 1.0
                if bound < inf and max(abs(nx - x0), abs(ny - y0)) > bound:
                    continue
                step = ny * width + nx
                ground = classes[step]
                if ground == _WATER:
                    if (wet := 0.0 if tireless else swum + length) > reach:
                        continue
                    there = swim if wet <= breath else tired
                else:
                    wet, there = 0.0, (tangled if trees[step] else land)[ground] if ground else here
                total = cost + length * (here + there) / 2
                if total > limit:
                    continue
                if total < best.get(step, inf):
                    best[step] = total
                elif ground != _WATER or wet >= swum_at[step]:
                    continue
                if ground == _WATER:
                    swum_at[step] = min(wet, swum_at.get(step, inf))
                ahead = 0.0
                if scale:  # the crow's line still to go, at the cheapest pace: it steers the search toward a lone goal without ever misleading it
                    far, near = abs(tx - nx), abs(ty - ny)
                    ahead = (far + DIAGONAL_EXTRA * near if far > near else near + DIAGONAL_EXTRA * far) * scale
                heappush(heap, (total + ahead, total, step, wet))


# A tile's class, read on its top as WB does (`top_type ?? main_type`): rock, lava and goo barred, the sea and its ice swum, a ground that slows its own class.
def _tile_class(name: str) -> int:
    if tile_block(name) is not None or (layer := tile_layer(name)) in ("Goo", "Lava"):
        return _BARRED
    if layer == "Ocean":
        return _WATER
    base, _, top = name.partition(":")
    return _SLOW_CLASS.get(top or base, _OPEN)


# Every tile a tree stands on, as a byte per tile — the footprint WB fills around the trunk (`Building.fillTiles`), clipped to the map.
def _tree_tiles(save: dict, width: int, height: int) -> bytearray:
    trees = bytearray(width * height)
    for building in save.get("buildings") or []:
        if (asset := building.get("asset_id")) in _TREES and (tile := building_tile(building)) is not None:
            left, right, top, bottom = _WIDE_TREES.get(asset, _TREE_FOOTPRINT)
            x0, x1 = max(tile[0] - left, 0), min(tile[0] + right, width - 1) + 1
            fill = b"\x01" * (x1 - x0)
            for row in range(max(tile[1] - bottom, 0) * width, (min(tile[1] + top, height - 1) + 1) * width, width):
                trees[row + x0 : row + x1] = fill
    return trees


# The tiles a wall stands beside, where WB's search drops its slanted steps (`hasWallsAround`): none on most maps, walls being the player's own paint.
def _walled_tiles(save: dict, names: list[str], width: int, height: int) -> frozenset[int]:
    flags = [int((block := tile_block(name)) is not None and block.startswith("wall_")) for name in names]
    if not any(flags):
        return frozenset()
    walled = set()
    for y, row in enumerate(tile_mask(save, flags)):
        x = row.find(1)
        while x != -1:
            walled.update((y + dy) * width + x + dx for dx, dy in _WALLED_DELTAS if 0 <= x + dx < width and 0 <= y + dy < height)
            x = row.find(1, x + 1)
    return frozenset(walled)


# How a body goes, as a pace cost per tile class: what a step there costs over the same step on open ground — past its breath, the water costs more.
class Gait:
    __slots__ = ("_breath", "_land", "_swim", "_tangled", "_tired", "reach")

    def __init__(self, land: list[float], tangled: list[float], swim: float, tired: float, breath: float, reach: float):
        self._breath, self._land, self._swim, self._tangled, self._tired, self.reach = breath, land, swim, tangled, tired, reach

    def ashore(self) -> "Gait":
        return Gait(self._land, self._tangled, self._swim, self._tired, 0.0, 0.0)


# The map as a walker reads it, built once per save: a class byte per tile, the tiles under a tree when Entanglewood holds, those beside a wall.
class WalkMap:
    __slots__ = ("_classes", "_height", "_tangling", "_trees", "_walled", "width")

    # The classes off the runs, the grid never unfolded; the trees only where the law binds them, the walls only where a player painted some.
    def __init__(self, save: dict):
        names = save.get("tileMap") or []
        rows = tile_mask(save, [_tile_class(name) for name in names])
        self._height, self.width = len(rows), len(rows[0]) if rows else 0
        self._classes = b"".join(rows)
        self._tangling = world_laws(save).get("world_law_entanglewood", True)
        self._trees = _tree_tiles(save, self.width, self._height) if self._tangling else bytearray(len(self._classes))
        self._walled = _walled_tiles(save, names, self.width, self._height)

    # A body's gait: `speed` for WB's floor, `tags` for the grounds it strides; `aloft` hovers over all, `blind` walks every ground alike, `swift` swims fivefold.
    def gait(
        self, speed: float | None, tags: frozenset[str], *, aloft: bool = False, blind: bool = False, swift: bool = False, breath: float = 0.0, reach: float = 0.0
    ) -> Gait:
        flat = max(speed or 1.0, 1.0)

        def pace(factor: float) -> float:
            return flat / max(speed * factor, 1.0) if speed else 1 / factor

        grounds = [1.0 if aloft or blind or tag in tags else factor for factor, tag in _SLOW_GROUNDS.values()]
        land = [inf, inf, pace(1.0), *map(pace, grounds)]
        tangle = _TANGLE if self._tangling and not aloft else 1.0
        tangled = [inf, inf, pace(tangle), *(pace(factor * tangle) for factor in grounds)]
        swim = pace(_SWIFT_SWIM if swift else 1.0)
        return Gait(land, tangled, swim, swim if swift or aloft else pace(_OUT_OF_BREATH), breath, reach)

    def wet(self, x: int, y: int) -> bool:
        return self._classes[y * self.width + x] == _WATER


# Every tile reached within `limit`, by its cost, a barring tile too as where the walk stops — never past `limit` tiles out, which a swift swimmer alone outruns.
def walk_from(walk_map: WalkMap, gait: Gait, x: int, y: int, limit: float) -> dict[int, float]:
    return dict(_settle(walk_map, gait, x, y, limit, limit if gait._swim < 1 else inf, None))


# What a body walks from `(x, y)` to the nearest of `goals` (tile indices), or `None` where none is reached — a single goal steers the search toward it.
def walk_to(walk_map: WalkMap, gait: Gait, x: int, y: int, goals: set[int], limit: float = inf) -> float | None:
    aim = None
    if len(goals) == 1:  # the cheapest pace a step can take: open ground's, or a swift swimmer's in the water
        ty, tx = divmod(next(iter(goals)), walk_map.width)
        aim = (tx, ty, min(gait._swim, 1.0))
    return next((cost for tile, cost in _settle(walk_map, gait, x, y, limit, inf, aim) if tile in goals), None)
