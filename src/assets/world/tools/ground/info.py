#!/usr/bin/env python3

# A single thing standing on a tile — a roof, a tree, a vein. Reserved for the chronicler (not consumed by the UI). User-facing docs: `tools/tools.md`.
# The handle is a building id — a roof (`actor/info.py` prints it as `metadata.home`) or a dock (`boat/info.py`). WB names none of them: the id is the handle.

import sys
from collections import Counter
from functools import cache
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))

from islands import compute_islands_cached
from shared import (
    actor_age,
    civic_building_ids,
    emit,
    entity_age,
    entity_ref,
    index_by_id,
    is_boat,
    light,
    load_save,
    parse_sections,
    resolve_profession,
    sex_label,
    take_chapter,
    wants_detail,
)

_ALL_SECTIONS = ("boats", "inventory", "metadata", "occupants")


# Absent off a shipyard, `in_building` telling a moored hull from a visiting one. `boat/info.py <id>` spells one out.
def _build_boats(moored: list[dict], house: dict, civic: bool, requested: str | None) -> dict:
    if not moored:
        return {}
    if not wants_detail(requested, len(moored)):  # `full` keeps it light — one count, the hulls themselves only when the section is asked for by name
        return light({"total": len(moored)})
    afloat = [{"asset_id": b.get("asset_id"), "id": b["id"], "name": b.get("name"), **_here(b, house, civic)} for b in moored]
    return {"afloat": afloat, "total": len(moored)}


# Heaviest stack first, as a city's: WB lets any building hold resources, and a dwelling doubling as a granary is worth a line.
def _build_inventory(house: dict) -> dict:
    stock: Counter = Counter()
    for resource in (house.get("resources") or {}).get("saved_resources") or []:
        stock[resource.get("id")] += resource.get("amount", 0)
    return dict(sorted(stock.items(), key=lambda kv: (-kv[1], kv[0])))


# `families` answers for the dwellers alone — a bonfire keeps no hearth. Hunger is a people's measure, not a roof's: the tiers own `fed_pct`.
def _build_metadata(house: dict, dwellers: list[dict], ctx: dict) -> dict:
    city = ctx["cities_by_id"].get(house.get("cityID")) or {}
    hx, hy = house.get("mainX"), house.get("mainY")
    island_id = None

    # WB writes both coordinates or neither, so one guard serves the pair — and a wall torn mid-tick, left unsited, never pays for the island map at all.
    if hx is not None and hy is not None:
        island_id = ctx["island_lookup"]().get((int(hx), int(hy)))

    return {
        # Dropped where it reads under zero: a reset before landmarks were stamped left them older than the world, and no age beats one counting backwards.
        **({"age": age} if (age := entity_age(house, ctx["world_time"])) >= 0 else {}),
        "asset_id": house.get("asset_id"),  # WB's dwelling asset (`house_orc_1`, `tent_orc`…) — the species and the tier of shelter both read off it.
        "city": entity_ref(house.get("cityID"), ctx["cities_by_id"]),
        # Answers for the souls under the roof, so it goes where there are none: a dock, a mine, a bonfire house nobody, whoever stands in them.
        **({"families": len({fid for a in dwellers if (fid := a.get("family"))})} if dwellers else {}),
        **({"health": int(health)} if (health := house.get("health")) is not None else {}),  # WB writes `health` only when hurt — absent means intact, not unknown.
        "island_id": island_id,
        "kingdom": entity_ref(city.get("kingdomID"), ctx["kingdoms_by_id"]),
        "x": hx,
        "y": hy,
    }


# WB's `homeBuildingID` points the other way, so the roster is rebuilt by walking the actors once. Eldest first, `total` riding with its list.
def _build_occupants(residents: list[dict], house: dict, ctx: dict, save: dict, detailed: bool) -> dict:
    if not detailed:  # `full` keeps the chapter light: ids and a headcount, the roster itself only when the section is asked for by name
        return light({"total": len(residents)})
    out = [
        {
            "age": actor_age(actor, ctx["world_time"]),
            "family": entity_ref(actor.get("family"), ctx["families_by_id"]),
            "gen": int(actor.get("generation") or 1),  # elder above child under one roof, the roster being sorted by age already
            "id": actor["id"],
            "job": resolve_profession(actor, save),
            "name": actor.get("name"),
            "sex": sex_label(actor),
            **_here(actor, house, ctx["civic"]),
            # Their own roof, named only when it is not this one — a guest by the fire, a miner at the seam, a soul WB left homeless keeping the key away.
            **({"home": home} if (home := actor.get("homeBuildingID")) and home != house["id"] else {}),
        }
        for actor in residents
    ]
    return {"roster": sorted(out, key=lambda o: (-o["age"], o["id"])), "total": len(out)}


# WB keeps `is_inside_building` on the runtime `Actor`, never on the `ActorData` a save writes — the very tile is all a chronicler can read. Absent unless true.
def _here(actor: dict, house: dict, civic: bool) -> dict:
    if not civic:  # nobody steps « inside » a field
        return {}
    return {"in_building": True} if (actor.get("x"), actor.get("y")) == (house.get("mainX"), house.get("mainY")) else {}


def main(argv: list[str]) -> int:
    save_path, argv, _ = take_chapter(argv)
    if not argv:
        print("usage: info.py <id> [sections] [C<n>] — see tools/tools.md", file=sys.stderr)
        return 2
    try:
        house_id = int(argv[0])
    except ValueError:
        print(f"✗ invalid id: {argv[0]}", file=sys.stderr)  # a malformed call, like a bad section — not an entity that happens to be missing
        return 2

    requested = argv[1] if len(argv) > 1 else None
    try:
        sections = parse_sections(requested, _ALL_SECTIONS)
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 2
    save = load_save(save_path)
    house = next((b for b in save.get("buildings") or [] if b.get("id") == house_id), None)  # one lookup, so a scan beats indexing every building to read one
    if house is None:
        print(f"✗ unknown building: {house_id}", file=sys.stderr)
        return 1

    tile = (house.get("mainX"), house.get("mainY"))
    civic = house.get("asset_id") in civic_building_ids()  # WB files trees and wheat under `buildings` too, and nobody stands « inside » a field
    dwellers: list[dict] = []
    visitors: list[dict] = []
    moored: list[dict] = []

    # WB moors a hull to its dock through the same `homeBuildingID` a soul sleeps under, so one walk sorts both — and none at all when no section asks.
    if {"boats", "metadata", "occupants"} & set(sections):
        for actor in save.get("actors_data") or []:
            here = (actor.get("x"), actor.get("y")) == tile
            home = actor.get("homeBuildingID") == house_id
            if is_boat(actor):  # a hull may moor at a rival's dock, and only the tile says which are there right now
                if home or here:
                    moored.append(actor)
            elif home:
                dwellers.append(actor)
            elif civic and here:  # a guest by the fire is nobody's dweller, yet a mine and a windmill do hold people
                visitors.append(actor)
    residents = dwellers + visitors
    ctx = {
        "cities_by_id": index_by_id(save.get("cities") or []),
        "civic": civic,
        "families_by_id": index_by_id(save.get("families") or []),
        "island_lookup": cache(lambda: compute_islands_cached(save, save_path)[1]),  # called not stored: half a second cold, and only `metadata` needs it
        "kingdoms_by_id": index_by_id(save.get("kingdoms") or []),
        "world_time": save["mapStats"]["world_time"],
    }

    out: dict = {}
    if "boats" in sections:
        out["boats"] = _build_boats(moored, house, civic, requested)
    if "inventory" in sections:
        out["inventory"] = _build_inventory(house)
    if "metadata" in sections:
        out["metadata"] = _build_metadata(house, dwellers, ctx)
    if "occupants" in sections and civic:  # nobody lodges in a tree: the section only means something where someone can
        out["occupants"] = _build_occupants(residents, house, ctx, save, detailed=wants_detail(requested, len(residents)))

    emit(out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
