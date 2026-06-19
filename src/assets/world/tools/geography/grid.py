#!/usr/bin/env python3

# Tile-level primitives shared across geography consumers (`islands.py`, `tiles/info.py`, …). No save-wide state, no caching — just functions over a tile name or grid.

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
# Tile name → WB `TileLayerType`, extracted from `Assembly-CSharp.dll` (TileType init). Unlisted bases default to Ground (lava* → Lava via prefix).
_LAYER_BY_TILE = {
    "$wall$": "Block",
    "close_ocean": "Ocean",
    "deep_ocean": "Ocean",
    "grey_goo": "Goo",
    "mountains": "Block",
    "shallow_waters": "Ocean",
    "summit": "Block",
}


# Expand the save's per-row RLE (`tileArray` + `tileAmounts`) into a 2D `grid[y][x]` of tile ids — `y` IS the WB-actor y (no inversion).
def decode_tile_grid(save: dict) -> list[list[int]]:
    grid = []
    for ids, runs in zip(save.get("tileArray") or [], save.get("tileAmounts") or []):
        row = []
        for tile_id, n in zip(ids, runs):
            row.extend([tile_id] * n)
        grid.append(row)
    return grid


# Vegetation biome (jungle/savanna/swamp/…). `None` for terrain-only tiles and overlays (`*:road`, `*:field`).
def tile_biome(tile_name: str) -> str | None:
    if ":" not in tile_name:
        return None
    suffix = tile_name.split(":", 1)[1]
    for marker in ("_high", "_low"):
        if suffix.endswith(marker):
            return suffix[: -len(marker)]
    return None


def tile_elevation(tile_name: str) -> str | None:
    return _ELEVATION_BY_BASE.get(tile_name.partition(":")[0])


# Structural terrain kind (mirrors WB UI). Overlay suffixes (`*:road`, `*:field`) win over the base.
def tile_kind(tile_name: str) -> str:
    base, _, suffix = tile_name.partition(":")
    if suffix == "road":
        return "road"
    if suffix == "field":
        return "field"
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
