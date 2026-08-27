#!/usr/bin/env python3

# Geographic stats reserved for the chronicler (not consumed by the UI). User-facing docs: `tools/tools.md`.

import argparse
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))

from grid import decode_tile_grid, tile_biome
from islands import compute_islands_cached
from shared import civic_building_ids, emit, load_data, load_save, parse_sections, take_chapter

_ALL_SECTIONS = ("biomes", "entity_types", "islands", "positions")
_COORDS = {"actors_data": ("x", "y"), "buildings": ("mainX", "mainY")}  # Collection → its coordinate fields. No `asset_id` sits in both, so a kind names its own.


# Every biome a land carries, marginal ones included — a paradox patch is a chapter's subject. Shares are of the whole island, sand and rock cutting them under 100.
def _build_biomes(save: dict, save_path: Path) -> dict:
    _, island_of = compute_islands_cached(save, save_path)
    grid = decode_tile_grid(save)
    biome_by_id = [tile_biome(name) for name in save.get("tileMap") or []]  # already merged: `soil_high:paradox_high` and its low twin both read `paradox`
    descriptions = load_data("biomes.json")
    tallies: defaultdict[int, Counter] = defaultdict(Counter)  # `setdefault` would mint a Counter per tile, three hundred thousand of them for one map
    sizes: Counter = Counter()
    island_at = island_of.get  # bound once: the lookup runs on every tile of the map

    for y, row in enumerate(grid):
        for x, tile_id in enumerate(row):
            if not (island_id := island_at((x, y))):
                continue
            sizes[island_id] += 1
            if biome := biome_by_id[tile_id]:
                tallies[island_id][biome] += 1

    per_island = {
        str(island_id): [{"biome": biome, "pct": pct, "tiles": n} for biome, n in counts.most_common() if (pct := round(n / sizes[island_id] * 100, 1)) > 0]
        for island_id, counts in sorted(tallies.items())
    }
    # Told once rather than on every land that carries the biome: a dozen descriptions would otherwise ride along some eighty times.
    named = {row["biome"] for rows in per_island.values() for row in rows}
    return {"descriptions": {b: text for b in sorted(named) if (text := (descriptions.get(b) or {}).get("description"))}, "islands": per_island}


# Every kind the save holds, grouped as WB groups them — its `buildings` collection also holds the flowers and the ore, so only the `civ_*` keep that name here.
def _build_entity_types(save: dict) -> dict:
    categories, civic = load_data("building-categories.json"), civic_building_ids()
    groups: dict[str, Counter] = {"actors": Counter(a["asset_id"] for a in save.get("actors_data") or [] if a.get("asset_id"))}
    for building in save.get("buildings") or []:
        if not (asset := building.get("asset_id")):
            continue
        group = "buildings" if asset in civic else categories.get(asset) or "other"  # `civic` knows the built kinds the manifest itself never declared
        groups.setdefault(group, Counter())[asset] += 1
    return {group: dict(counts) for group, counts in groups.items() if counts}


# Where every instance of one kind stands. Its `id` opens its own script; `island_id` names the land mass, absent over water — a hull at sea, a dock on shallows.
def _build_positions(save: dict, save_path: Path, asset_id: str) -> list[dict]:
    out = []
    for collection, (field_x, field_y) in _COORDS.items():
        for record in save.get(collection) or []:
            if record.get("asset_id") != asset_id:
                continue
            if (x := record.get(field_x)) is not None and (y := record.get(field_y)) is not None:
                out.append({"id": record.get("id"), "name": record.get("name"), "x": int(x), "y": int(y)})
        if out:  # what one collection holds, the other never does — no need to walk 16k buildings to find an orc
            break
    if out:  # the lookup costs half a second cold, so a kind nobody built never pays for it
        _, island_of = compute_islands_cached(save, save_path)
        for position in out:
            position["island_id"] = island_of.get((position["x"], position["y"]))
    return sorted(out, key=lambda r: (r["y"], r["x"]))


def main(argv: list[str]) -> int:
    save_path, argv, _ = take_chapter(argv)  # pop the `C<n>` token first — argparse has no such positional and would abort on it

    parser = argparse.ArgumentParser(prog="geography/info.py", description="Geographic stats reserved for the chronicler.")
    parser.add_argument("sections", help=f"Comma-separated sections. Valid: {', '.join(_ALL_SECTIONS)}")
    parser.add_argument("--type", "-t", help="Asset id `positions` reports every instance of — e.g. `volcano`, `orc`. `entity_types` lists what the save holds.")
    args = parser.parse_args(argv)

    if args.sections == "full":  # No `full` here, unlike the other tools: these sections answer unrelated questions, and no reading wants all three.
        print(f"geography has no `full` — name a section: {', '.join(_ALL_SECTIONS)}", file=sys.stderr)
        return 2
    try:
        sections = parse_sections(args.sections, _ALL_SECTIONS, allow_full=False)
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 2
    wanted: str | None = args.type
    if wanted is None and "positions" in sections:
        print("positions needs --type <asset_id> — run `entity_types` for the roll", file=sys.stderr)
        return 2

    save = load_save(save_path)
    out: dict = {}
    if "biomes" in sections:
        out["biomes"] = _build_biomes(save, save_path)
    if "entity_types" in sections:
        out["entity_types"] = _build_entity_types(save)
    if "islands" in sections:
        islands, _ = compute_islands_cached(save, save_path)
        out["islands"] = islands
    if "positions" in sections and wanted is not None:
        out["positions"] = _build_positions(save, save_path, wanted)

    emit(out)

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
