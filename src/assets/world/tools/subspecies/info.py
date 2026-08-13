#!/usr/bin/env python3

# One subspecies: the biology a lineage of actors was born into, its sworn traits and who still carries it. User-facing docs: `tools/tools.md`.
# WB mutates one out of another as a world ages, so a species holds many — and a subspecies outlives every crown and clan its bearers ever joined.

import sys
from functools import cache
from operator import itemgetter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))

from islands import compute_islands_cached
from shared import (
    actor_age,
    build_trait_ids,
    build_trait_list,
    competition_ranks,
    emit,
    entity_age,
    entity_ref,
    index_by_id,
    is_boat,
    light,
    load_data,
    load_save,
    parse_sections,
    population_breakdown,
    resolve_profession,
    roster_ids,
    sex_label,
    take_chapter,
    wants_detail,
)

_ALL_SECTIONS = ("breakdown", "identity", "members", "metadata", "ranks", "species", "traits")
_BIOME_ALIASES = {"pumpkin": "super_pumpkin", "singularity": "singularity_swamp"}  # WB names both shorter than the sheet does; without these they print raw ids.
_DEATH_PREFIX = "deaths_"  # WB spells each cause as its own field, the same narrow set a clan carries — old age answers to `natural`.
_EMPTY_SPECIES = {"cities": 0, "kingdoms": 0, "population": 0, "renown": 0, "subspecies": 0}  # What a species is ranked on; its keys double as the rank getters.


# The stock WB mutated this one out of and the biome that shaped it — bare keys, and WB's `default_color` being no biome at all, the panel drops the row.
def _build_identity(subspecies: dict) -> dict:
    raw_biome = (subspecies.get("biome_variant") or "").removeprefix("biome_")
    biome_id = _BIOME_ALIASES.get(raw_biome, raw_biome)
    return {
        "biome": biome_id if load_data("biomes.json").get(biome_id) else None,
        "species": subspecies.get("species_id"),
    }


# Everyone alive who carries the biology, eldest first — WB points the actor at its subspecies, never the reverse. `total` rides with the list it counts.
def _build_members(members: list[dict], ctx: dict, save: dict, detailed: bool) -> dict:
    if not detailed:  # `full` keeps the chapter light: ids and a headcount, since a widespread biology rosters hundreds and no panel ever names one
        return light({"ids": roster_ids(members, ctx["world_time"]), "total": len(members)}, "members")
    island_of = ctx["island_lookup"]()  # resolved once: the lookup is memoised, but a widespread biology would still call through it hundreds of times
    out = [
        {
            "age": actor_age(actor, ctx["world_time"]),
            "city": entity_ref(actor.get("cityID"), ctx["cities_by_id"]),
            "id": actor["id"],
            "island_id": island_of.get((int(actor["x"]), int(actor["y"]))),  # Chronicler-only: land mass (`geography/info.py islands`)
            "kingdom": entity_ref(actor.get("civ_kingdom_id"), ctx["kingdoms_by_id"]),
            "name": actor.get("name"),
            "profession": resolve_profession(actor, save),
            "sex": sex_label(actor),
        }
        for actor in members
    ]
    return {"roster": sorted(out, key=lambda m: (-m["age"], m["id"])), "total": len(out)}


# The subspecies' identity card: WB's own lifetime counters beside what only a walk over the living can tell — how far the biology spread and what it carries.
def _build_metadata(subspecies: dict, members: list[dict], ctx: dict) -> dict:
    cities = {c for a in members if (c := a.get("cityID"))}
    island_of = ctx["island_lookup"]()
    kingdoms = {k for a in members if (k := a.get("civ_kingdom_id"))}
    causes = {k[len(_DEATH_PREFIX) :]: v for k, v in subspecies.items() if k.startswith(_DEATH_PREFIX) and v}

    return {
        "age": entity_age(subspecies, ctx["world_time"]),
        "id": subspecies["id"],  # the block travels into `chapter.json`, detached from its command — the UI resolves the tag from this
        # Chronicler-only: land masses its bearers stand on, sorted asc (1 = biggest). Presence, not weight — one wanderer on an islet earns it a place here.
        "islands": sorted({iid for a in members if (iid := island_of.get((int(a["x"]), int(a["y"])))) is not None}),
        "name": subspecies.get("name"),
        # Every counter below drops at zero, as WB's own already do: a beast holds no town and swears no trait, and the panels read them through `?? 0`.
        **({"birth_traits": birth} if (birth := len(subspecies.get("saved_actor_birth_traits") or [])) else {}),  # what every newborn inherits
        **({"births": births} if (births := int(subspecies.get("total_births") or 0)) else {}),
        **({"cities": len(cities)} if cities else {}),  # settlements its bearers answer from — a biology spreads wherever its carriers walk
        **({"deaths_by_cause": causes} if causes else {}),  # chronicler-only: how the biology has been dying, which its totals alone never say
        **({"deaths": deaths} if (deaths := int(subspecies.get("total_deaths") or 0)) else {}),
        **({"kills": kills} if (kills := int(subspecies.get("total_kills") or 0)) else {}),
        **({"kingdoms": len(kingdoms)} if kingdoms else {}),  # crowns its bearers answer to — biology owes nothing to borders, so it crosses them freely
        **({"money": money} if (money := sum(int(a.get("money") or 0) for a in members)) else {}),  # the purse the living carry; WB banks per actor
        **({"renown_total": total} if (total := sum(int(a.get("renown") or 0) for a in members)) else {}),  # the living's worth beside WB's lifetime tally
        **({"renown": renown} if (renown := int(subspecies.get("renown") or 0)) else {}),
        **({"traits": traits} if (traits := len(subspecies.get("saved_traits") or [])) else {}),
    }


# The stock's standing over every soul of that species, ranked against the others — its own section, like a realm's `alliance`: counts flat beside its `ranks`.
def _build_species(subspecies: dict, save: dict) -> dict:
    asset_id = subspecies.get("species_id") or ""
    totals = _species_totals(save)
    own = totals.get(asset_id) or _EMPTY_SPECIES.copy()
    ranks = competition_ranks(own, list(totals.values()), {key: itemgetter(key) for key in _EMPTY_SPECIES})
    description = (load_data("species.json").get(asset_id) or {}).get("description")  # chronicler-only: WB's English line, which the panel never prints

    # Counts drop at zero like the tier's own — a beast holds no town, and the podium is computed off the whole dict, so nothing is lost by not printing it.
    return {**{key: value for key, value in own.items() if value}, "description": description, **({"ranks": ranks} if ranks else {})}


# Two libraries: `biology` what WB mutated the subspecies into, `birth` what its newborns inherit — summarised to ids and rarity at any size, standing alone.
def _build_traits(subspecies: dict, detailed: bool) -> dict:
    build = build_trait_list if detailed else build_trait_ids
    sworn = {
        "biology": build(subspecies.get("saved_traits") or [], load_data("subspecies-traits.json")),
        "birth": build(subspecies.get("saved_actor_birth_traits") or [], load_data("creature-traits.json")),
    }
    return sworn if detailed else light(sworn, "traits")


# What a biology is ranked on among the world's others — living counts come off the roster it was handed, lifetime counters off WB's own fields.
def _rank_getters(members_by_subspecies: dict, world_time: float) -> dict:
    return {
        "age": lambda s: entity_age(s, world_time),
        "births": lambda s: int(s.get("total_births") or 0),
        "deaths": lambda s: int(s.get("total_deaths") or 0),
        "kills": lambda s: int(s.get("total_kills") or 0),
        "members": lambda s: len(members_by_subspecies.get(s["id"], ())),
        "money": lambda s: sum(int(a.get("money") or 0) for a in members_by_subspecies.get(s["id"], ())),
        "renown": lambda s: int(s.get("renown") or 0),
        "renown_total": lambda s: sum(int(a.get("renown") or 0) for a in members_by_subspecies.get(s["id"], ())),
        "traits": lambda s: len(s.get("saved_traits") or []),
    }


# Every species alive, each with the standing the panel ranks it on: one pass over the actors, so a subspecies costs the same whichever stock it sprang from.
def _species_totals(save: dict) -> dict[str, dict]:
    cities: dict[str, set] = {}
    kingdoms: dict[str, set] = {}
    totals: dict[str, dict] = {}
    for actor in save.get("actors_data") or []:
        if is_boat(actor) or not (asset_id := actor.get("asset_id")):
            continue
        entry = totals.setdefault(asset_id, _EMPTY_SPECIES.copy())
        entry["population"] += 1
        entry["renown"] += int(actor.get("renown") or 0)
        if city := actor.get("cityID"):
            cities.setdefault(asset_id, set()).add(city)
        if kingdom := actor.get("civ_kingdom_id"):
            kingdoms.setdefault(asset_id, set()).add(kingdom)
    for entry_id, entry in totals.items():
        entry["cities"] = len(cities.get(entry_id, ()))
        entry["kingdoms"] = len(kingdoms.get(entry_id, ()))
    for sub in save.get("subspecies") or []:  # how many biologies WB has mutated out of the stock, the one count that is the species' alone
        if (sid := sub.get("species_id")) in totals:
            totals[sid]["subspecies"] += 1
    return totals


def main(argv: list[str]) -> int:
    save_path, argv, _ = take_chapter(argv)
    if not argv:
        print("usage: info.py <id> [sections] [C<n>] — see tools/tools.md", file=sys.stderr)
        return 2
    try:
        subspecies_id = int(argv[0])
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
    subspecies_by_id = index_by_id(save.get("subspecies") or [])
    subspecies = subspecies_by_id.get(subspecies_id)
    if subspecies is None:
        print(f"unknown subspecies: {subspecies_id}", file=sys.stderr)
        return 1

    members_by_subspecies: dict[int, list[dict]] = {}
    for actor in save.get("actors_data") or []:
        if sid := actor.get("subspecies"):
            members_by_subspecies.setdefault(sid, []).append(actor)

    members = members_by_subspecies.get(subspecies_id, [])
    ctx = {
        "cities_by_id": index_by_id(save.get("cities") or []),
        "cultures_by_id": index_by_id(save.get("cultures") or []),
        "island_lookup": cache(lambda: compute_islands_cached(save, save_path)[1]),  # tile → island id, called not stored: only `members` needs it
        "kingdoms_by_id": index_by_id(save.get("kingdoms") or []),
        "languages_by_id": index_by_id(save.get("languages") or []),
        "religions_by_id": index_by_id(save.get("religions") or []),
        "subspecies_by_id": subspecies_by_id,
        "world_time": save["mapStats"]["world_time"],
    }

    out: dict = {}
    if "breakdown" in sections:
        # The living against the biology they were born into. Species and subspecies both go: WB fixes them at birth, so each would read 100 % and say nothing.
        out["breakdown"] = {k: v for k, v in population_breakdown(members, ctx).items() if k not in ("species", "subspecies")}
    if "identity" in sections:
        out["identity"] = _build_identity(subspecies)
    if "members" in sections:
        out["members"] = _build_members(members, ctx, save, detailed=wants_detail(requested, len(members)))
    if "metadata" in sections:
        out["metadata"] = _build_metadata(subspecies, members, ctx)
    if "ranks" in sections:
        peers = list(subspecies_by_id.values())
        out["ranks"] = competition_ranks(subspecies, peers, _rank_getters(members_by_subspecies, ctx["world_time"]))
    if "species" in sections:
        out["species"] = _build_species(subspecies, save)
    if "traits" in sections:
        out["traits"] = _build_traits(subspecies, detailed=requested not in (None, "full"))
    emit(out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
