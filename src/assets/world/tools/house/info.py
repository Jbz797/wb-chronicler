#!/usr/bin/env python3

# A single dwelling, reserved for the chronicler (not consumed by the UI). User-facing docs: `tools/tools.md`.
# The handle is a building id — `actor/info.py` prints it as `metadata.home`. WB keeps no name for a house, so `id` is all there is to address it by.

import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))

from islands import compute_islands_cached
from shared import (
    NON_FOOD_SPECIES,
    SATED_MIN_NUTRITION,
    ZONE_TILES,
    actor_age,
    emit,
    entity_age,
    entity_ref,
    index_by_id,
    light,
    load_save,
    parse_sections,
    resolve_profession,
    roster_ids,
    sex_label,
    take_chapter,
    wants_detail,
)

_ALL_SECTIONS = ("inventory", "metadata", "occupants")


# Stored like a city's, heaviest stack first: a dwelling doubling as a granary is worth a line, and WB lets any building hold resources.
def _build_inventory(house: dict) -> dict:
    stock: Counter = Counter()
    for resource in (house.get("resources") or {}).get("saved_resources") or []:
        stock[resource.get("id")] += resource.get("amount", 0)
    return dict(sorted(stock.items(), key=lambda kv: (-kv[1], kv[0])))


# The dwelling's identity card. `families` counts the lineages under the roof — a WB house beds whoever needs one; the headcount rides with `occupants`.
def _build_metadata(house: dict, residents: list[dict], ctx: dict) -> dict:
    city = ctx["cities_by_id"].get(house.get("cityID")) or {}
    eaters = [a for a in residents if (a.get("asset_id") or "") not in NON_FOOD_SPECIES]  # WB `needsFood`: the undead have no diet
    hx, hy = house.get("mainX"), house.get("mainY")
    island_id = zone = None

    # WB writes both coordinates or neither, so one guard serves the pair — and a wall torn mid-tick, left unsited, never pays for the island map at all.
    if hx is not None and hy is not None:
        island_id = ctx["island_lookup"]().get((int(hx), int(hy)))
        zone = {"x": hx // ZONE_TILES, "y": hy // ZONE_TILES}  # the `TileZone` it stands in, as cities claim them

    return {
        "age": entity_age(house, ctx["world_time"]),
        "asset_id": house.get("asset_id"),  # WB's dwelling asset (`house_orc_1`, `tent_orc`…) — the species and the tier of shelter both read off it.
        "city": entity_ref(house.get("cityID"), ctx["cities_by_id"]),
        "families": len({fid for a in residents if (fid := a.get("family"))}),
        # The roof's condition, read beside the stores `inventory` lists — an all-undead roof has no eaters and drops the key.
        **({"fed_pct": round(100 * sum(int(a.get("nutrition") or 0) >= SATED_MIN_NUTRITION for a in eaters) / len(eaters))} if eaters else {}),
        **({"health": int(health)} if (health := house.get("health")) is not None else {}),  # WB writes `health` only when hurt — absent means intact, not unknown.
        "island_id": island_id,
        "kingdom": entity_ref(city.get("kingdomID"), ctx["kingdoms_by_id"]),
        "x": hx,
        "y": hy,
        "zone": zone,
    }


# Who sleeps here, eldest first — WB's `homeBuildingID` points the other way, so the roster is rebuilt by walking the actors once. `total` rides with its list.
def _build_occupants(residents: list[dict], ctx: dict, save: dict, detailed: bool) -> dict:
    if not detailed:  # `full` keeps the chapter light: ids and a headcount, the roster itself only when the section is asked for by name
        return light({"ids": roster_ids(residents, ctx["world_time"]), "total": len(residents)}, "occupants")
    out = [
        {
            "age": actor_age(actor, ctx["world_time"]),
            "family": entity_ref(actor.get("family"), ctx["families_by_id"]),
            "gen": int(actor.get("generation") or 1),  # elder above child under one roof, the roster being sorted by age already
            "id": actor["id"],
            "job": resolve_profession(actor, save),
            "name": actor.get("name"),
            "sex": sex_label(actor),
        }
        for actor in residents
    ]
    return {"roster": sorted(out, key=lambda o: (-o["age"], o["id"])), "total": len(out)}


def main(argv: list[str]) -> int:
    save_path, argv, _ = take_chapter(argv)
    if not argv:
        print("usage: info.py <id> [sections] [C<n>] — see tools/tools.md", file=sys.stderr)
        return 2
    try:
        house_id = int(argv[0])
    except ValueError:
        print(f"invalid id: {argv[0]}", file=sys.stderr)
        return 1

    requested = argv[1] if len(argv) > 1 else None
    try:
        sections = parse_sections(requested, _ALL_SECTIONS)
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 2
    save = load_save(save_path)
    house = next((b for b in save.get("buildings") or [] if b.get("id") == house_id), None)  # one lookup, so a scan beats indexing all 16 k rows to read one
    if house is None:
        print(f"unknown building: {house_id}", file=sys.stderr)
        return 1

    residents = [a for a in save.get("actors_data") or [] if a.get("homeBuildingID") == house_id]
    ctx = {
        "cities_by_id": index_by_id(save.get("cities") or []),
        "families_by_id": index_by_id(save.get("families") or []),
        "island_lookup": lambda: compute_islands_cached(save, save_path)[1],  # called not stored: a cold island map costs tens of ms, and only `metadata` needs it
        "kingdoms_by_id": index_by_id(save.get("kingdoms") or []),
        "world_time": save["mapStats"]["world_time"],
    }

    out: dict = {}
    if "inventory" in sections:
        out["inventory"] = _build_inventory(house)
    if "metadata" in sections:
        out["metadata"] = _build_metadata(house, residents, ctx)
    if "occupants" in sections:
        out["occupants"] = _build_occupants(residents, ctx, save, detailed=wants_detail(requested, len(residents)))
    emit(out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
