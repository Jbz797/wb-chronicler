# Tile-level primitives. No save-wide state, no module cache — just functions over a tile name, the rows the save folds away as runs, or the tiles it lists by id.

from collections.abc import Iterator
from itertools import chain, compress, repeat

LAND_LAYERS = frozenset({"Block", "Ground", "Lava"})  # what a foot stands on, and all `totals` counts as land: off it, the rare goo included, a tile is water

# The tile types WB marks `block` (`TileLibrary`, `TopTileLibrary`): rock of the `Block` layer no body crosses on foot, from mountains to the walls a player paints.
_BLOCKS = frozenset(
    {"mountains", "snow_block", "snow_summit", "summit", "wall_ancient", "wall_evil", "wall_green", "wall_iron", "wall_light", "wall_order", "wall_wild"}
)

# Soil gradients (`low`/`high`) and water depths (`shallow`/`coastal`/`deep`). Other kinds encode their verticality in the kind itself.
_ELEVATION_BY_BASE = {
    "close_ocean": "coastal",
    "deep_ocean": "deep",
    "shallow_waters": "shallow",
    "soil_high": "high",
    "soil_low": "low",
}

# WB's frozen forms, what each tile turns to when it freezes (`TileLibrary`, `freeze_to_id`) — snow and ice, never a biome (`TopTileLibrary.setSnow`).
_FROST_BY_TOP = {
    "frozen_high": "snow",
    "frozen_low": "snow",
    "ice": "ice",
    "snow_block": "snow",
    "snow_hills": "snow",
    "snow_sand": "snow",
    "snow_summit": "snow",
}

# Base tile names whose `tile_kind` doesn't follow a prefix rule (`soil_*` → plain, `lava*` → lava) or a suffix rule (`*:road`, `*:field`).
_KIND_BY_BASE = {
    "close_ocean": "water",
    "deep_ocean": "water",
    "grey_goo": "goo",
    "hills": "hill",
    "mountains": "mountain",
    "sand": "sand",
    "shallow_waters": "water",
    "summit": "summit",
}

# Tile name → WB `TileLayerType`, extracted from `Assembly-CSharp.dll` (TileType init).
_LAYER_BY_TILE = {
    "close_ocean": "Ocean",
    "deep_ocean": "Ocean",
    "grey_goo": "Goo",
    "mountains": "Block",
    "shallow_waters": "Ocean",
    "summit": "Block",
}


# Each row's RLE, its tile ids paired with its run lengths — the module's one and only reading of the grid's own shape.
def _tile_rows(save: dict) -> Iterator[tuple[list[int], list[int]]]:
    return zip(save.get("tileArray") or [], save.get("tileAmounts") or [])


def _unfold(ids: list[int], runs: list[int]) -> list[int]:
    return list(chain.from_iterable(map(repeat, ids, runs)))


# The grid unfolded a row at a time, on first read: a caller that looks at a few tiles never pays for the whole map, some thirty-five milliseconds of it.
class LazyTileGrid(dict):
    __slots__ = ("_rows", "height", "width")

    # Nothing is decoded here — the runs are only indexed, so that `grid[y]` can reach its own.
    def __init__(self, save: dict):
        super().__init__()
        self._rows = list(_tile_rows(save))
        self.height, self.width = len(self._rows), sum(self._rows[0][1]) if self._rows else 0

    # `dict` calls it once per row, on its first read: every later `grid[y][x]` is a plain lookup.
    def __missing__(self, y: int) -> list[int]:
        row = self[y] = _unfold(*self._rows[y])
        return row


# The save's runs unfolded into a 2D `grid[y][x]` of tile ids — `y` IS the WB-actor y, north-growing, so no caller has to flip it.
def decode_tile_grid(save: dict) -> list[list[int]]:
    return [_unfold(ids, runs) for ids, runs in _tile_rows(save)]


# The map's frozen tiles, and all its tiles: permafrost, frozen for good in WB's eyes, the map's snow and ice, the passing frost a save lists — never one twice.
def frozen_tally(save: dict) -> tuple[int, int]:
    frozen = tile_count(save, [bool(tile_frost(name) or tile_biome(name) == "permafrost") for name in save.get("tileMap") or []])
    return frozen + len(save.get("frozen_tiles") or []), sum(chain.from_iterable(runs for _, runs in _tile_rows(save)))


# What WB `SavedMap.create` lists by `tile_id` rather than on the grid — `fire`, `frozen_tiles` — packed row-major as `y * width + x`, unpacked into `(x, y)`.
def listed_tiles(save: dict, key: str) -> Iterator[tuple[int, int]]:
    width = sum(next(_tile_rows(save), ((), ()))[1])
    return ((i % width, i // width) for i in save.get(key) or [])


# Off every counted land, where a tile lies: on an `islet` too small to count, or in the `water` — two places, never one bucket, a body on a rock being no swimmer.
def off_land(tile_name: str) -> str:
    return "islet" if tile_layer(tile_name) in LAND_LAYERS else "water"


# Vegetation biome (jungle/savanna/swamp/…). `None` for terrain-only tiles, overlays (`*:road`, `*:field`) and snow or ice, whose `frozen_low` is none either.
def tile_biome(tile_name: str) -> str | None:
    top = tile_name.partition(":")[2]
    biome, sep, tier = top.rpartition("_")
    return biome if sep and tier in ("high", "low") and top not in _FROST_BY_TOP else None


# What bars the way on a tile, named as WB types it — its top, else its base: none crosses it on foot. `None` where the way is open.
def tile_block(tile_name: str) -> str | None:
    base, _, top = tile_name.partition(":")
    return kind if (kind := top or base) in _BLOCKS else None


# How many tiles have `flags[tile id]` set, counted off the runs in C, each weighing its length: no tile unfolded, nor any mask built for a mere count.
def tile_count(save: dict, flags: list[bool]) -> int:
    if not any(flags):  # goo, most maps: nothing to count, so not a run is read
        return 0
    runs = chain.from_iterable(runs for _, runs in _tile_rows(save))
    return sum(compress(runs, map(flags.__getitem__, chain.from_iterable(ids for ids, _ in _tile_rows(save)))))


def tile_elevation(tile_name: str) -> str | None:
    return _ELEVATION_BY_BASE.get(tile_name.partition(":")[0])


# `snow` or `ice` where the ground lies frozen for good — the map's own frost, beside the passing one a save lists as `frozen_tiles`.
def tile_frost(tile_name: str) -> str | None:
    return _FROST_BY_TOP.get(tile_name.partition(":")[2])


# Structural terrain kind (mirrors WB UI), off the base: overlays (`*:road`, `*:field`) win, while snow and walls are told apart (`tile_frost`, `tile_block`).
def tile_kind(tile_name: str) -> str:
    base, _, suffix = tile_name.partition(":")
    if suffix in ("road", "field"):
        return suffix
    if base.startswith("lava"):
        return "lava"
    if base.startswith("soil_"):
        return "plain"
    return _KIND_BY_BASE.get(base, base)


# The top rules, as WB reads a tile (`top_type ?? main_type`): a blocking top is rock, ice water, any other ground; else the base, `lava*` Lava, the unlisted Ground.
def tile_layer(tile_name: str) -> str:
    base, _, top = tile_name.partition(":")
    if top:
        return "Block" if top in _BLOCKS else "Ocean" if top == "ice" else "Ground"
    if base.startswith("lava"):
        return "Lava"
    return _LAYER_BY_TILE.get(base, "Ground")


# Each row as a byte per tile, `flags[tile id]` — built off the runs, a map's tiles never unfolded: a mask for C to search, three times faster than from the grid.
def tile_mask(save: dict, flags: list[int]) -> list[bytes]:
    unit = [bytes((flag,)) for flag in flags]
    return [b"".join([unit[tile] * n for tile, n in zip(ids, runs)]) for ids, runs in _tile_rows(save)]


# The same rows `decode_tile_grid` unfolds, left folded as `(tile id, run length)` — a caller that only tallies never pays for the tiles themselves.
def tile_runs(save: dict) -> Iterator[tuple[int, int]]:
    return chain.from_iterable(zip(ids, runs) for ids, runs in _tile_rows(save))
