# The places the chronicler named in `places.json`, read as the tools measure them: a name to the tiles it covers, for `actor … --to` and `tiles … --to` alike.

import difflib
import re
lazy from pathlib import Path

from grid import BARE, LazyTileGrid, patch_finder, tile_ground
from shared import building_footprint, gazetteer, place_point, walk_tiles
from waters import water_bodies, water_tiles
lazy from islands import TileIslands
lazy from walking import WalkMap

PLACE_REACH = 8  # tiles from a forged place's point its landmark may stand: the chronicler sets it on the cone he sees, not on the building's tile
_ARTICLE = re.compile(r"^(?:l'|(?:le|la|les|the)\s+)", re.IGNORECASE)  # the article a sentence contracts or drops: `du Lac`, `au Socle`
_LANDMARKS = ("geyser", "volcano")  # the words of the buildings a forged place names by its point: `acid_geyser` too, the world's own landmarks
_SEEDED_BOOKS = {"islands": "i", "lakes": "lake", "rivers": "river", "seas": "sea"}  # the gazetteer's counted lands and waters, by the prefix their ids take


# A name no tile answers, or answers wrongly: its message, the `✗` included, for the caller to tell as its own refusals.
class PlaceError(ValueError):
    pass


# A name `places.json` holds nowhere: a `--to` list of goals written as one, which a caller may read word by word.
class UnknownPlaceError(PlaceError):
    pass


# Of a place's `box`, the tiles that are its own: the water its point lies in, its point's patch of the ground it names (rock too), else its point's land.
def _boxed(name: str, spot: dict, point: tuple[int, int], save: dict, save_path: Path, island_of: TileIslands, walk_map: WalkMap) -> list[tuple[int, int]]:
    (x, y), box, height = point, spot["box"], len(save.get("tileArray") or [])
    (x0, x1), (y0, y1) = sorted((box["x0"], box["x1"])), sorted((box["y0"], box["y1"]))
    span = {(bx, by) for by in range(max(y0, 0), min(y1, height - 1) + 1) for bx in range(max(x0, 0), min(x1, walk_map.width - 1) + 1)}
    if ground := spot.get("ground"):  # the patch its point stands on, the range itself: a lone rock at its foot, a patch of its own, comes nearer
        grid, what = LazyTileGrid(save), ground
        if (tile_ground(save["tileMap"][grid[y][x]]) or "").removeprefix(BARE) != ground:
            raise PlaceError(f"✗ {name}'s point stands off its ground, {ground}")
        tiles = [tile for tile in patch_finder(save, grid, island_of)(x, y)[0] if tile in span]
    elif walk_map.wet(x, y):
        ((kind, water_id),) = water_bodies(save, save_path)(x, y).items()
        if kind == "pond_tiles":  # a pond has no id to name it by: its box is no gulf
            raise PlaceError(f"✗ {name}'s point lies in a pond — `--to {x},{y}`")
        what, tiles = f"{kind} {water_id}", [tile for tile in water_tiles(save, save_path, kind, water_id) if tile in span]
    else:
        what, land = "its point's land", island_of.get((x, y))
        tiles = [(bx, by) for bx, by in span if island_of.get((bx, by)) == land and not walk_map.wet(bx, by)]
    if not tiles:
        raise PlaceError(f"✗ {name}'s box holds none of {what}")
    return tiles


# The record a name of `places.json` stands for, article and case aside (`_key`), the exact name first: its book, key and entry — refused where none or two.
def _find(name: str) -> tuple[str, str, dict]:
    toponyms, wanted = gazetteer(), _key(name)
    every = [(book, key, entry, entry["name"]) for book in _SEEDED_BOOKS for key, entry in (toponyms.get(book) or {}).items() if entry.get("name")]
    every += [("places", key, spot, key) for key, spot in (toponyms.get("places") or {}).items()]
    found = [hit for hit in every if _key(hit[3]) == wanted]
    if len(found) > 1 and len(exact := [hit for hit in found if hit[3] == name]) == 1:
        found = exact
    if len(found) > 1:
        raise PlaceError(f"✗ {name} names {' and '.join(hit[3] for hit in found)} — write it whole")
    if not found:
        near = difflib.get_close_matches(name, [hit[3] for hit in every], n=3)
        raise UnknownPlaceError(f"✗ no place named {name} in places.json" + (f" — near it: {', '.join(near)}" if near else ""))
    return found[0][:3]


def _key(name: str) -> str:
    return _ARTICLE.sub("", name.strip().replace("\u2019", "'")).casefold()


def kind_word(word: str) -> bool:
    return word.replace("_", "").isalnum() and word.islower()


# A name of `places.json`, article and case aside (`_key`), to its tiles and `aimed`: a land its rim, a water all, a forged place its own — `None`: a kind.
def named_place(name: str, save: dict, save_path: Path, island_of: TileIslands, walk_map: WalkMap) -> tuple[list[tuple[int, int]], str] | None:
    if all(map(kind_word, name.split(","))):  # a kind's word, `sheep` or `iron_ore,gold_ore`, left to the kinds
        return None
    book, key, entry = _find(name)
    if book == "places":
        return place_tiles(key, entry, save, save_path, island_of, walk_map)
    prefix, entry_id = _SEEDED_BOOKS[book], int(key)
    tiles = [(x, y) for x, y, owner in island_of.edges() if owner == entry_id] if book == "islands" else water_tiles(save, save_path, prefix, entry_id)
    return tiles, f"{prefix}{key}"


def place_centre(name: str) -> tuple[int, int]:
    return place_point(_find(name)[2])


# A forged place's own tiles: its `box` first (`_boxed`), a gulf by a volcano being the gulf, then a landmark by its point before its islet, a cone in lava one.
def place_tiles(name: str, spot: dict, save: dict, save_path: Path, island_of: TileIslands, walk_map: WalkMap) -> tuple[list[tuple[int, int]], str]:
    x, y = place_point(spot)
    if spot.get("box"):
        return _boxed(name, spot, (x, y), save, save_path, island_of, walk_map), "box"
    landmarks = (site for site in save.get("buildings") or [] if any(word in (site.get("asset_id") or "") for word in _LANDMARKS))
    near = [(walk_tiles(tx - x, ty - y), site) for site in landmarks for tx, ty in building_footprint(site)]
    if near and (closest := min(near, key=lambda pair: pair[0]))[0] <= PLACE_REACH:
        return building_footprint(closest[1]), f"b{closest[1]['id']}"
    if islet := island_of.islet_tiles((x, y)):
        return islet, "islet"
    raise PlaceError(f"✗ {name} has no `box` in places.json: its extent is unknown, its point alone — `--to {x},{y}`")
