#!/usr/bin/env python3

# A single hull, reserved for the chronicler (not consumed by the UI). User-facing docs: `tools/tools.md`.
# The handle is an actor id — WB models boats as actors, so a world's `boats` section and a realm's both print it beside the kind, leaving the hull itself here.

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))

from shared import (
    build_trait_ids,
    build_trait_list,
    civic_building_ids,
    emit,
    entity_age,
    entity_ref,
    index_by_id,
    is_boat,
    light,
    load_data,
    load_save,
    parse_sections,
    resolve_profession,
    take_chapter,
    wants_detail,
)

_ALL_SECTIONS = ("combat", "crew", "identity", "inventory", "metadata", "traits")
_LEVEL_HEALTH_MOD = 0.05  # WB `_LEVEL_MOD["health"]`: every level lifts the cap by a twentieth, and leaves damage alone
_MASS_SCALE_UNIT = 0.1  # WB `Actor.getMassKG` weighs a hull as `mass_2 × (scale / this)`, every boat sharing the one `scale` `$boat$` declares


# Moored on a quay's own tile — rare, a hull riding two tiles offshore at best, and never necessarily its own: WB lets one tie up at a rival's dock.
def _berth(boat: dict, ctx: dict) -> dict | None:
    quay = ctx["buildings_by_tile"].get((boat.get("x"), boat.get("y")))
    return {"asset_id": quay.get("asset_id"), "id": quay["id"]} if quay else None


# WB arms a hull off its species' shipyard, not its trade — 30 to 65 damage; `damage_range` gives the « min-max » pair. `targets` goes, four on every munition.
def _build_combat(boat: dict, ctx: dict) -> dict:
    assets, kind = load_data("boat-assets.json"), _kind_of(boat)
    weapon_id = assets.get("weapons", {}).get(boat.get("asset_id"))
    weapon = (ctx["equipment"].get("items", {}).get(weapon_id) or {}).get("stats", {})
    if not weapon:  # a fishing skiff carries no weapon at all — WB gives its asset none
        return {}
    bonus = _trait_stats(boat, ctx)
    damage = weapon.get("damage", 0) * (1 + bonus.get("multiplier_damage", 0)) + bonus.get("warfare", 0) / 5  # WB `_apply_damage_finalize`
    return {
        "area_of_effect": weapon.get("area_of_effect", 0),
        "attack_speed": assets.get("kinds", {}).get(kind, {}).get("attack_speed", 0),
        "critical_chance": round((weapon.get("critical_chance", 0) + bonus.get("critical_chance", 0)) * 100),
        "damage": {"max": round(damage), "min": round(damage * weapon.get("damage_range", 0))},
        "projectiles": weapon.get("projectiles", 0),
        "range": weapon.get("range", 0),
        "weapon": weapon_id,
    }


# Everyone WB has aboard right now — `transportID` is the only link, a passenger keeping their city and kingdom while at sea. A fishing skiff sails with nobody.
def _build_crew(boat: dict, save: dict, requested: str | None) -> dict:
    aboard = [a for a in save.get("actors_data") or [] if a.get("transportID") == boat["id"]]
    if not wants_detail(requested, len(aboard)):  # `full` keeps the chapter light — one count, the souls themselves only when the section is asked for by name
        return light({"total": len(aboard)})
    return {"roster": [{"id": a["id"], "job": resolve_profession(a, save), "name": a.get("name")} for a in aboard], "total": len(aboard)}


# What the hull is, read off its `asset_id`: WB names barely a tenth of a world's boats, so the asset carries the identity a name would.
def _build_identity(boat: dict, ctx: dict) -> dict:
    kind, _, species = (boat.get("asset_id") or "").removeprefix("boat_").partition("_")
    return {
        "city": entity_ref(boat.get("cityID"), ctx["cities_by_id"]),
        "kind": kind,  # `fishing`, `trading` or `transport` — WB boards souls onto the last alone
        "kingdom": entity_ref(boat.get("civ_kingdom_id"), ctx["kingdoms_by_id"]),
        "name": boat.get("name"),
        "species": species or None,  # the stock whose docks laid the keel, WB's own key as biomes are emitted — a fishing skiff names none
    }


# The hull as WB's panel reads it, its « Statuts » being `traits`. WB writes `level`, `kills` and `renown` only once it has fought: an unblooded hull reads level 1.
def _build_metadata(boat: dict, ctx: dict) -> dict:
    home = ctx["buildings_by_id"].get(boat.get("homeBuildingID"))
    level = max(int(boat.get("level") or 0), 1)  # WB scales from level 1 even where the field is absent, as `Actor.updateStats` does
    return {
        "age": entity_age(boat, ctx["world_time"]),
        "health": boat.get("health"),
        "health_max": _health_max(boat, ctx, level),
        "home": home["id"] if home else None,  # the dock it answers to — a handle, `building/info.py <id>` spelling out its age, health, city and zone
        **({"in_building": quay} if (quay := _berth(boat, ctx)) else {}),
        "kills": boat.get("kills", 0),
        "level": level,
        "loot": boat.get("loot", 0),  # coin plundered from what it sank, WB's own word
        "mass_kg": _mass_kg(boat),
        "renown": boat.get("renown", 0),
        "speed": load_data("boat-assets.json").get("kinds", {}).get(_kind_of(boat), {}).get("speed", 0),  # the trade sets it: a skiff dawdles where a trader races
        "x": boat.get("x"),
        "y": boat.get("y"),
    }


# Off WB's creature library as an actor's are: every boat swears `boat`, most light a lamp, a few won merits. Grouped, not by rarity — WB grades all five `Rare`.
def _build_traits(boat: dict, detailed: bool) -> dict | list[dict]:
    sworn, library = boat.get("saved_traits") or [], load_data("creature-traits.json")
    return build_trait_list(sworn, library) if detailed else light({"ids": build_trait_ids(sworn, library, "group")})


# WB `BaseSimObject.getMaxHealth` reads the finished `health` stat: the template's, lifted a twentieth per level, then multiplied by whatever the traits grant.
def _health_max(boat: dict, ctx: dict, level: int) -> int:
    base = load_data("boat-assets.json").get("kinds", {}).get(_kind_of(boat), {}).get("health", 0)
    return round(base * (1 + level * _LEVEL_HEALTH_MOD) * (1 + _trait_stats(boat, ctx).get("multiplier_health", 0)))


def _kind_of(boat: dict) -> str:
    return (boat.get("asset_id") or "").removeprefix("boat_").partition("_")[0]


# WB `Actor.getMassKG`: the template's `mass_2`, scaled by how large the hull is drawn. A baby multiplier follows in WB — no boat is ever one.
def _mass_kg(boat: dict) -> int:
    assets = load_data("boat-assets.json")
    return int(assets.get("kinds", {}).get(_kind_of(boat), {}).get("mass_2", 0) * (assets.get("scale", 0) / _MASS_SCALE_UNIT))


# Every stat the hull's traits grant, summed as WB stacks them — a merit won at sea (`veteran`, `kingslayer`) is what parts two coques of the same shipyard.
def _trait_stats(boat: dict, ctx: dict) -> dict:
    totals: dict = {}
    for trait in boat.get("saved_traits") or []:
        for stat, value in ((ctx["creature_traits"].get(trait) or {}).get("stats") or {}).items():
            totals[stat] = totals.get(stat, 0) + value
    return totals


def main(argv: list[str]) -> int:
    save_path, argv, _ = take_chapter(argv)
    if not argv:
        print("usage: info.py <id> [sections] [C<n>] — see tools/tools.md", file=sys.stderr)
        return 2
    try:
        boat_id = int(argv[0])
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
    boat = next((a for a in save.get("actors_data") or [] if a.get("id") == boat_id and is_boat(a)), None)
    if boat is None:
        print(f"unknown boat: {boat_id}", file=sys.stderr)
        return 1

    ctx = {
        "buildings_by_id": index_by_id(save.get("buildings") or []),
        # Built structures only: WB files trees, wheat and vegetation under `buildings` too, and nobody steps « inside » a field.
        "buildings_by_tile": {(b.get("mainX"), b.get("mainY")): b for b in save.get("buildings") or [] if b.get("asset_id") in civic_building_ids()},
        "cities_by_id": index_by_id(save.get("cities") or []),
        "creature_traits": load_data("creature-traits.json"),
        "equipment": load_data("equipment.json"),
        "kingdoms_by_id": index_by_id(save.get("kingdoms") or []),
        "world_time": save["mapStats"]["world_time"],
    }

    out: dict = {}
    if "combat" in sections:
        out["combat"] = _build_combat(boat, ctx)
    if "crew" in sections:
        out["crew"] = _build_crew(boat, save, requested)
    if "identity" in sections:
        out["identity"] = _build_identity(boat, ctx)
    if "inventory" in sections:  # what the hull carries: a skiff's catch, a trader's coin and hides — WB stores it as it does a town's storehouse
        out["inventory"] = {k: v.get("amount", 0) for k, v in ((boat.get("inventory") or {}).get("dict") or {}).items()}
    if "metadata" in sections:
        out["metadata"] = _build_metadata(boat, ctx)
    if "traits" in sections:
        out["traits"] = _build_traits(boat, detailed=requested not in (None, "full"))

    emit(out)

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
