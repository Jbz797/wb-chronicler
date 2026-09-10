# Tile-level primitives. No save-wide state, no module cache — just functions over a tile name, the rows the save folds away as runs, or the tiles it lists by id.

from collections.abc import Iterator
from itertools import chain, repeat

# Soil gradients (`low`/`high`) and water depths (`shallow`/`coastal`/`deep`). Other kinds encode their verticality in the kind itself.
_ELEVATION_BY_BASE = {
    "close_ocean": "coastal",
    "deep_ocean": "deep",
    "shallow_waters": "shallow",
    "soil_high": "high",
    "soil_low": "low",
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
    "$wall$": "Block",
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


# What WB `SavedMap.create` lists by `tile_id` rather than on the grid — `fire`, `frozen_tiles` — packed row-major as `y * width + x`, unpacked into `(x, y)`.
def listed_tiles(save: dict, key: str) -> Iterator[tuple[int, int]]:
    width = sum(next(_tile_rows(save), ((), ()))[1])
    return ((i % width, i // width) for i in save.get(key) or [])


# Vegetation biome (jungle/savanna/swamp/…). `None` for terrain-only tiles and overlays (`*:road`, `*:field`).
def tile_biome(tile_name: str) -> str | None:
    biome, sep, tier = tile_name.partition(":")[2].rpartition("_")
    return biome if sep and tier in ("high", "low") else None


def tile_elevation(tile_name: str) -> str | None:
    return _ELEVATION_BY_BASE.get(tile_name.partition(":")[0])


# Structural terrain kind (mirrors WB UI). Overlay suffixes (`*:road`, `*:field`) win over the base.
def tile_kind(tile_name: str) -> str:
    base, _, suffix = tile_name.partition(":")
    if suffix in ("road", "field"):
        return suffix
    if base.startswith("lava"):
        return "lava"
    if base.startswith("soil_"):
        return "plain"
    return _KIND_BY_BASE.get(base, base)


# Lava (`lava0`..`lava3`+) lumps under "Lava"; everything unlisted defaults to Ground.
def tile_layer(tile_name: str) -> str:
    base = tile_name.partition(":")[0]
    if base.startswith("lava"):
        return "Lava"
    return _LAYER_BY_TILE.get(base, "Ground")


# The same rows `decode_tile_grid` unfolds, left folded as `(tile id, run length)` — a caller that only tallies never pays for the tiles themselves.
def tile_runs(save: dict) -> Iterator[tuple[int, int]]:
    return chain.from_iterable(zip(ids, runs) for ids, runs in _tile_rows(save))
