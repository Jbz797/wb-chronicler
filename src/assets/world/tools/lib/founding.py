# Where a thinking soul could found a town, WB's `try_to_start_new_civilization` gate by gate — `actor … metadata`'s `settle`, `world … roster --settle`.

from collections import Counter

from actor_stats import is_baby
from grid import LAND_LAYERS, tile_kind, tile_layer
from shared import PROFESSION_KING, ZONE_TILES, actor_xy, is_sapient, zone_xy

# WB `TopTileLibrary`: the biomes any lineage may found on, and those only a meta tag opens — `corrupted` alone spelt apart from its tag.
_BUILD_FREE = (
    "birch",
    "candy",
    "celestial",
    "clover",
    "crystal",
    "enchanted",
    "flower",
    "garlic",
    "grass",
    "jungle",
    "lemon",
    "maple",
    "mushroom",
    "paradox",
    "rocklands",
    "savanna",
    "singularity",
)

_BUILD_TAGS = {"corrupted": "corruption", "desert": "desert", "infernal": "infernal", "permafrost": "permafrost", "swamp": "swamp", "wasteland": "wasteland"}
_CITY_WAVE = 3  # WB `CityPlaceFinder.startWave`: the zones a town keeps founders off, counted from its edge across its own land

# WB ground, all 64 of a zone's tiles for `canStartCityHere`: the hill left out, ground though it bars; a pit a dry hole (`liquid` 0) till the sea fills it.
_GROUND_BASES = frozenset({"pit_close_ocean", "pit_deep_ocean", "pit_shallow_waters", "sand", "soil_high", "soil_low"})

# WB `TopTileLibrary`: the tiles `checkCanSettleInThisBiomes` weighs, each with the meta tag a lineage must bear to build there — `None` where any may.
_SETTLE_BIOMES = {
    **dict.fromkeys(f"{biome}_{height}" for biome in _BUILD_FREE for height in ("high", "low")),
    **{f"{biome}_{height}": f"can_build_in_biome_{tag}" for biome, tag in _BUILD_TAGS.items() for height in ("high", "low")},
    **dict.fromkeys(("ice", "snow_block", "snow_hills", "snow_sand", "snow_summit"), "can_build_in_biome_permafrost"),  # permafrost's frosts, cloned off it
    "sand": None,
}

_SETTLE_SOIL = frozenset({"soil_high", "soil_low"})  # bare soil, which the weighing counts apart and then offsets by everything grown over it


def _zone_centre(zx: int, zy: int) -> tuple[int, int]:
    return zx * ZONE_TILES + ZONE_TILES // 2, zy * ZONE_TILES + ZONE_TILES // 2


# Every zone a town holds, with the land its first tile stands on — the one WB spreads its founders' wave across — and the town's name, to say which bars.
def city_zones(save: dict, island_of) -> list[tuple[int, int, int | None, str]]:
    zones = []
    for city in save.get("cities") or []:
        if held := city.get("zones") or []:
            land, name = island_of.get(_zone_centre(*zone_xy(held[0]))), city.get("name") or f"town {city.get('id')}"
            zones += [(*zone_xy(zone), land, name) for zone in held]
    return zones


# WB `try_to_start_new_civilization` for a thinker: `True` where every gate opens, else each that shuts it — the zone weighed for a child too, who founds once grown.
# `ctx` is `actor_stats`' own, widened with `city_zones`, `island_lookup`, `tile_grid`, `tile_map` and `world_laws`: `actor` and `world` each build it.
def settle_gates(actor: dict, ctx: dict) -> bool | list[str] | None:
    subspecies = ctx["subspecies_by_id"].get(actor.get("subspecies"))
    if not is_sapient(subspecies):
        return None
    # A trait that binds its bearer to a crown of its own (WB `is_forced_by_trait`), which `canStartNewCityCivilizationHere` turns away — named, as each gate is.
    binding = next((t for t in actor.get("saved_traits") or () if (ctx["creature_traits"].get(t) or {}).get("forced_kingdom")), None)
    gates = (
        ("child", is_baby(actor, ctx)),
        (f"trait {binding} binds to a crown", binding),
        ("has_city", actor.get("cityID")),
        ("king", actor.get("profession") == PROFESSION_KING),
    )
    shut = [gate for gate, holds in gates if holds]
    if not ctx["world_laws"].get("world_law_kingdom_expansion", True):
        shut.append("world_law_kingdom_expansion off")
    x, y = actor_xy(actor)
    zx, zy = x // ZONE_TILES, y // ZONE_TILES
    cx, cy = _zone_centre(zx, zy)
    land = ctx["island_lookup"]().get((cx, cy))  # WB reads the zone's centre tile
    names, grid = ctx["tile_map"], ctx["tile_grid"]()
    # Water or a rock at the zone's middle: no land for WB to weigh. Every counted land clears WB's own 300-tile floor, so this is the whole of that gate.
    if land is None:
        layer = tile_layer(names[grid[cy][cx]])
        shut.append(f"zone centre on {'water' if layer not in LAND_LAYERS else {'Block': 'rock', 'Lava': 'lava'}.get(layer, 'an islet')}")
    elif near := [(d, town) for tx, ty, on, town in ctx["city_zones"]() if on == land and (d := abs(tx - zx) + abs(ty - zy)) <= _CITY_WAVE]:
        zones, town = min(near)
        shut.append(f"town {zones} zone{'s' if zones != 1 else ''} away: {town}")
    tags = frozenset(tag for trait in subspecies.get("saved_traits") or () for tag in (ctx["subspecies_traits"].get(trait) or {}).get("tags") or ())
    ground = soil = fit = 0
    barred, wanted = Counter(), Counter()  # what each shut gate is made of: the ground a zone lacks, the adaptations its unfit biomes ask for
    for row in range(zy * ZONE_TILES, (zy + 1) * ZONE_TILES):
        for tile in grid[row][zx * ZONE_TILES : (zx + 1) * ZONE_TILES]:
            base, _, top = names[tile].partition(":")
            if base in _GROUND_BASES:
                ground += 1
            else:
                barred[tile_kind(base)] += 1
            for kind in (base, top):  # a zone weighs both layers of a tile, WB filing each under its own type
                if kind in _SETTLE_SOIL:
                    soil += 1
                elif kind in _SETTLE_BIOMES:
                    if (need := _SETTLE_BIOMES[kind]) is None or need in tags:
                        fit += 1
                    else:
                        wanted[need] += 1
    if ground < ZONE_TILES * ZONE_TILES:  # a zone is 8 × 8, and every tile of it must be ground: said with what stands in for the rest
        shut.append(f"ground {ground}/{ZONE_TILES * ZONE_TILES}: " + ", ".join(f"{n} {kind}" for kind, n in barred.most_common()))
    unfit = sum(wanted.values())
    soil -= fit + unfit  # WB `checkCanSettleInThisBiomes`: the bare soil left once every grown tile is offset
    if not (soil > unfit or unfit <= fit):  # named by the lineage trait that would lift it, off the adaptation granting the missing tag
        cures = sorted({trait for need in wanted for trait, entry in ctx["subspecies_traits"].items() if need in (entry.get("tags") or ())})
        bare = f", {soil} bare for {unfit} unfit" if soil > 0 else ""  # the other way through, told only where some bare soil stands at all
        # WB's first way is half the grown tiles fit: a share said floored, so 49.9 never reads as the 50 that would pass
        shut.append(f"biomes {fit * 100 // (fit + unfit)}% fit{bare}" + (f" — {', '.join(cures)}" if cures else ""))
    return shut or True
