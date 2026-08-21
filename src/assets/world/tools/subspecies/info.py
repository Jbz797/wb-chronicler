#!/usr/bin/env python3

# One subspecies: the biology a lineage of actors was born into, its sworn traits and who still carries it. User-facing docs: `tools/tools.md`.
# WB mutates one out of another as a world ages, so a species holds many — and a subspecies outlives every crown and clan its bearers ever joined.

import sys
from collections import Counter
from functools import cache, partial
from operator import itemgetter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))

from actor_stats import build_actor_stats_context, compute_actor_stats, meta_ratios, population_of, subspecies_stats
from islands import compute_islands_cached
from shared import (
    NON_FOOD_SPECIES,
    PROFESSION_WARRIOR,
    SATED_MIN_NUTRITION,
    actor_age,
    build_trait_ids,
    build_trait_list,
    children_by_id,
    competition_ranks,
    emit,
    entity_age,
    entity_ref,
    index_by_id,
    is_boat,
    light,
    load_data,
    load_save,
    meta_report,
    parse_sections,
    population_breakdown,
    resolve_profession,
    roster_ids,
    settlement_leaders,
    sex_label,
    take_chapter,
    wants_detail,
)

_ALL_SECTIONS = ("breakdown", "identity", "leaders", "members", "metadata", "population", "ranks", "species", "stats", "taxonomy", "traits")
_BIOME_ALIASES = {"pumpkin": "super_pumpkin", "singularity": "singularity_swamp"}  # WB names both shorter than the sheet does; without these they print raw ids.
_DEATH_PREFIX = "deaths_"  # WB spells each cause as its own field, the same narrow set a clan carries — old age answers to `natural`.
_EMPTY_SPECIES = {"cities": 0, "kingdoms": 0, "population": 0, "renown": 0, "subspecies": 0}  # What a species is ranked on; its keys double as the rank getters.
_TAXONOMY_RANKS = ("kingdom", "phylum", "class", "order", "family", "genus")  # WB's own order, broadest first — `render` keeps it, not alphabetical.


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
            "family": entity_ref(actor.get("family"), ctx["families_by_id"]),  # The roster's one entity: a biology runs in lines — 7 bearers a line, 25 a town.
            "id": actor["id"],
            "island_id": island_of.get((int(actor["x"]), int(actor["y"]))),  # Chronicler-only: land mass (`geography/info.py islands`)
            "job": resolve_profession(actor, save),
            **({"level": level} if (level := int(actor.get("level") or 0)) > 1 else {}),  # WB leaves most souls at 1 — as in `clan`, no aggregate here carries it.
            "name": actor.get("name"),
            "sex": sex_label(actor),
        }
        for actor in members
    ]
    return {"roster": sorted(out, key=lambda m: (-m["age"], m["id"])), "total": len(out)}


# The subspecies' identity card: WB's lifetime counters beside what a walk over the living tells. Every counter drops at zero — the panels read them through `?? 0`.
def _build_metadata(subspecies: dict, members: list[dict], ctx: dict) -> dict:
    causes = {k[len(_DEATH_PREFIX) :]: v for k, v in subspecies.items() if k.startswith(_DEATH_PREFIX) and v}
    cities = {c for a in members if (c := a.get("cityID"))}
    families = {f for a in members if (f := a.get("family"))}
    island_of = ctx["island_lookup"]()
    kingdoms = {k for a in members if (k := a.get("civ_kingdom_id"))}
    report = meta_report("meta", {"units": len(members), **meta_ratios(members, ctx)})  # what WB has the biology say of itself

    return {
        "age": entity_age(subspecies, ctx["world_time"]),
        **({"births": births} if (births := int(subspecies.get("total_births") or 0)) else {}),
        **({"cities": len(cities)} if cities else {}),  # settlements its bearers answer from — a biology spreads wherever its carriers walk
        **({"deaths": deaths} if (deaths := int(subspecies.get("total_deaths") or 0)) else {}),
        **({"deaths_by_cause": causes} if causes else {}),  # chronicler-only: how the biology has been dying, which its totals alone never say
        **({"families": len(families)} if families else {}),  # bloodlines carrying it — the count says whether the biology runs in one line or fans out over many
        "id": subspecies["id"],  # the block travels into `chapter.json`, detached from its command — the UI resolves the tag from this
        "islands": sorted({iid for a in members if (iid := island_of.get((int(a["x"]), int(a["y"])))) is not None}),  # 1 = biggest — presence, not weight.
        **({"kills": kills} if (kills := int(subspecies.get("total_kills") or 0)) else {}),
        **({"kingdoms": len(kingdoms)} if kingdoms else {}),  # crowns its bearers answer to — biology owes nothing to borders, so it crosses them freely
        "name": subspecies.get("name"),
        **({"renown": renown} if (renown := int(subspecies.get("renown") or 0)) else {}),  # WB's own tally, where the living's worth now sits in `population`
        **({"report": report} if report else {}),
    }


# What the living say of the body they belong to — the settlement block less its granary and its head, and less `total`, which the `members` section owns.
def _build_population(members: list[dict], ctx: dict) -> dict:
    return {key: value for key, value in population_of(members, ctx).items() if key != "total"}


# The stock's standing over every soul of that species, ranked against the others — its own section, like a realm's `alliance`: counts flat beside its `ranks`.
def _build_species(subspecies: dict, save: dict) -> dict:
    asset_id = subspecies.get("species_id") or ""
    totals = _species_totals(save)
    own = totals.get(asset_id) or _EMPTY_SPECIES.copy()
    ranks = competition_ranks(own, list(totals.values()), {key: itemgetter(key) for key in _EMPTY_SPECIES})
    description = (load_data("species.json").get(asset_id) or {}).get("description")  # chronicler-only: WB's English line, which the panel never prints

    # Counts drop at zero like the tier's own — a beast holds no town, and the podium is computed off the whole dict, so nothing is lost by not printing it.
    return {**{key: value for key, value in own.items() if value}, "description": description, **({"ranks": ranks} if ranks else {})}


# WB `ActorAsset.name_taxonomic_*`, lower-case in the DLL. Its `species` rank is dropped: `metadata.name` already carries it, mutated (`Banditus Nikonisum`).
def _build_taxonomy(subspecies: dict) -> dict:
    ranks = (load_data("species.json").get(subspecies.get("species_id")) or {}).get("taxonomy") or {}
    return {rank: name.capitalize() for rank in _TAXONOMY_RANKS if (name := ranks.get(rank))}


# Two libraries on one axis: `biology` what WB mutated the subspecies into, `birth` what its newborns inherit — both keyed by trait group, at any size.
def _build_traits(subspecies: dict, detailed: bool) -> dict:
    build = build_trait_list if detailed else partial(build_trait_ids, key="group")
    library, sworn = load_data("subspecies-traits.json"), subspecies.get("saved_traits") or []
    # WB derives a biology's own faculties from its traits (`Subspecies.cacheTags`): it feels through an `amygdala`, eats through a `stomach`, lays or bears.
    tags = sorted({tag for tid in sworn for tag in (library.get(tid) or {}).get("tags") or ()})
    carried = {
        "biology": build(sworn, library),
        "birth": build(subspecies.get("saved_actor_birth_traits") or [], load_data("creature-traits.json")),
        **({"tags": tags} if tags else {}),
    }
    return carried if detailed else light(carried, "traits")


# What a biology is ranked on among the world's others. Living counts read off the one actor pass: the podium weighs every biology, on each dimension.
def _rank_getters(tallies: dict, world_time: float) -> dict:
    return {
        "age": lambda s: entity_age(s, world_time),
        "births": lambda s: int(s.get("total_births") or 0),
        "deaths": lambda s: int(s.get("total_deaths") or 0),
        "fed_pct": lambda s: tallies["fed"][s["id"]] / n if (n := tallies["eaters"][s["id"]]) else 0.0,
        "housed_pct": lambda s: tallies["housed"][s["id"]] / n if (n := len(tallies["members"].get(s["id"], ()))) else 0.0,
        "kills": lambda s: int(s.get("total_kills") or 0),
        "members": lambda s: len(tallies["members"].get(s["id"], ())),
        "money": lambda s: tallies["money"][s["id"]],
        "renown": lambda s: int(s.get("renown") or 0),
        "renown_total": lambda s: tallies["renown_total"][s["id"]],
        "warriors": lambda s: tallies["warriors"][s["id"]],
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

    # One pass feeds every tally: WB points the actor at its biology, never the reverse.
    tallies: dict = {
        "eaters": Counter(),
        "fed": Counter(),
        "housed": Counter(),
        "members": {},
        "money": Counter(),
        "renown_total": Counter(),
        "warriors": Counter(),
    }

    for actor in save.get("actors_data") or []:
        if not (sid := actor.get("subspecies")):
            continue
        tallies["members"].setdefault(sid, []).append(actor)
        tallies["money"][sid] += int(actor.get("money") or 0)
        if actor.get("asset_id") not in NON_FOOD_SPECIES:  # WB `needsFood`: undead have no diet, so they weigh on neither side of the hunger share
            tallies["eaters"][sid] += 1
            tallies["fed"][sid] += int(actor.get("nutrition") or 0) >= SATED_MIN_NUTRITION
        tallies["housed"][sid] += bool(actor.get("homeBuildingID"))
        tallies["warriors"][sid] += actor.get("profession") == PROFESSION_WARRIOR
        if fame := actor.get("renown"):
            tallies["renown_total"][sid] += int(fame)

    members = tallies["members"].get(subspecies_id, [])
    ctx = {
        **build_actor_stats_context(save),  # brings the trait libraries and `languages_by_id`, `world_time` with them
        "actors_by_id": index_by_id(save.get("actors_data") or []),  # `population_of` pairs lovers through it, and only a mutual pair counts
        "cultures_by_id": index_by_id(save.get("cultures") or []),
        "families_by_id": index_by_id(save.get("families") or []),
        "island_lookup": cache(lambda: compute_islands_cached(save, save_path)[1]),  # tile → island id, called not stored: only `members` needs it
        "kingdoms_by_id": index_by_id(save.get("kingdoms") or []),  # `population_breakdown` alone reads it here — a biology answers to no crown of its own
        "religions_by_id": index_by_id(save.get("religions") or []),
        "subspecies_by_id": subspecies_by_id,  # the index the id was checked against, so the context's own copy never takes over
    }

    out: dict = {}
    base_cache: dict = ctx.setdefault("subspecies_base_cache", {})  # one heavy base per biology, shared by the podium and every section after
    if "breakdown" in sections:
        # The living against the biology they were born into. Species and subspecies both go: WB fixes them at birth, so each would read 100 % and say nothing.
        out["breakdown"] = {k: v for k, v in population_breakdown(members, ctx).items() if k not in ("species", "subspecies")}
    if "identity" in sections:
        out["identity"] = _build_identity(subspecies)
    if "leaders" in sections:  # WB names no such podium — ours, and it drops below five members, where a champion among three names nobody
        out["leaders"] = settlement_leaders(members, ctx["families_by_id"], children_by_id(save), lambda a: compute_actor_stats(a, ctx, base_cache))
    if "members" in sections:
        out["members"] = _build_members(members, ctx, save, detailed=wants_detail(requested, len(members)))
    if "metadata" in sections:
        out["metadata"] = _build_metadata(subspecies, members, ctx)
    if "population" in sections:
        out["population"] = _build_population(members, ctx)
    if "ranks" in sections:
        out["ranks"] = competition_ranks(subspecies, list(subspecies_by_id.values()), _rank_getters(tallies, ctx["world_time"]))
    if "species" in sections:
        out["species"] = _build_species(subspecies, save)
    if "stats" in sections:
        out["stats"] = subspecies_stats(subspecies, ctx)
    if "taxonomy" in sections:
        out["taxonomy"] = _build_taxonomy(subspecies)
    if "traits" in sections:
        out["traits"] = _build_traits(subspecies, detailed=requested not in (None, "full"))
    emit(out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
