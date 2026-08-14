#!/usr/bin/env python3

# One clan: the band a founder gathered, its chiefs, its sworn traits and who still wears the name. User-facing docs: `tools/tools.md`.
# A clan is joined, not inherited — unlike a family, which is a bloodline. WB lets one actor hold both, so the two rosters overlap without matching.

import sys
from collections import Counter
from functools import cache
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))

from actor_stats import build_actor_stats_context, compute_actor_stats
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
    light,
    load_data,
    load_save,
    parse_sections,
    population_breakdown,
    resolve_profession,
    roster_ids,
    sex_label,
    succession_heir,
    take_chapter,
    wants_detail,
)

_ALL_SECTIONS = ("breakdown", "identity", "members", "metadata", "ranks", "traits")
_DEATH_PREFIX = "deaths_"  # WB spells each cause as its own field; the clan's set is narrower than the world's and names old age `natural`.


# Chronicler-only: what the clan was founded as — the creator's own stock — plus the culture it currently answers to, which its later members need not share.
def _build_identity(clan: dict, ctx: dict) -> dict:
    return {
        "culture": entity_ref(_clan_culture(clan, ctx), ctx["cultures_by_id"]),
        "motto": clan.get("motto"),  # WB writes one on roughly half of them — the clan's own words, worth quoting verbatim
        "species": clan.get("creator_species_id"),
        "subspecies": entity_ref(clan.get("creator_subspecies_id"), ctx["subspecies_by_id"]),
    }


# Everyone alive who wears the colours, eldest first — WB points the actor at its clan, never the reverse. `total` rides with the list it counts, not in `metadata`.
def _build_members(members: list[dict], ctx: dict, save: dict, detailed: bool) -> dict:
    if not detailed:  # `full` keeps the chapter light: ids and a headcount, the roster itself only when the section is asked for by name
        return light({"ids": roster_ids(members, ctx["world_time"]), "total": len(members)}, "members")
    island_of = ctx["island_lookup"]()  # resolved once: the lookup is memoised, but a wide band would still call through it hundreds of times
    out = [
        {
            "age": actor_age(actor, ctx["world_time"]),
            "city": entity_ref(actor.get("cityID"), ctx["cities_by_id"]),
            "family": entity_ref(actor.get("family"), ctx["families_by_id"]),  # a clansman keeps his own bloodline — `family/info.py <id>` on it
            "id": actor["id"],
            "island_id": island_of.get((int(actor["x"]), int(actor["y"]))),  # Chronicler-only: land mass (`geography/info.py islands`)
            "name": actor.get("name"),
            "profession": resolve_profession(actor, save),
            "sex": sex_label(actor),
        }
        for actor in members
    ]
    return {"roster": sorted(out, key=lambda m: (-m["age"], m["id"])), "total": len(out)}


# The clan's identity card: WB's own lifetime counters beside what only a walk over the living can tell — where they answer from, and what they carry.
def _build_metadata(clan: dict, members: list[dict], ctx: dict) -> dict:
    tallies, clan_id = ctx["tallies"], clan["id"]  # coins and renown came off the one actor pass — resumming them here would walk the roster twice over
    cities = {c for a in members if (c := a.get("cityID"))}
    kingdoms = {k for a in members if (k := a.get("civ_kingdom_id"))}
    # Each cause WB bothered to write, its prefix stripped; a clan that never lost anyone to fire carries no key rather than a zero.
    causes = {k[len(_DEATH_PREFIX) :]: v for k, v in clan.items() if k.startswith(_DEATH_PREFIX) and v}

    return {
        "age": entity_age(clan, ctx["world_time"]),
        "chief": entity_ref(clan.get("chief_id"), ctx["actors_by_id"]),
        "founder": {"id": fid, "name": clan.get("founder_actor_name")} if (fid := clan.get("founder_actor_id")) is not None else None,
        "founding_city": entity_ref(clan.get("founder_city_id"), ctx["cities_by_id"]),
        "founding_kingdom": entity_ref(clan.get("founder_kingdom_id"), ctx["kingdoms_by_id"]),
        "heir": _resolve_heir(clan, members, ctx),
        "id": clan["id"],  # the block travels into `chapter.json`, detached from its command — the UI resolves the tag from this
        "name": clan.get("name"),
        "past_chiefs": len(clan.get("past_chiefs") or []),  # the sitting chief included — WB appends him on accession, so it never reads zero
        # Every counter below drops at zero, as WB's own already do: a band holding no town and swearing no trait carries no key, and the panels read them as 0.
        **({"births": births} if (births := int(clan.get("total_births") or 0)) else {}),
        **({"books_written": books} if (books := int(clan.get("books_written") or 0)) else {}),
        **({"cities": len(cities)} if cities else {}),  # settlements its members answer from — a clan crosses borders, WB never ties it to one town
        **({"deaths_by_cause": causes} if causes else {}),  # chronicler-only: how the clan has been dying, which its totals alone never say
        **({"deaths": deaths} if (deaths := int(clan.get("total_deaths") or 0)) else {}),
        **({"kills": kills} if (kills := int(clan.get("total_kills") or 0)) else {}),
        **({"kingdoms": len(kingdoms)} if kingdoms else {}),  # crowns its members answer to — a clan is sworn, not granted, so it spans realms freely
        **({"money": money} if (money := tallies["money"][clan_id]) else {}),  # the purse the living carry; WB banks per actor, never per band
        **({"renown_total": total} if (total := tallies["renown_total"][clan_id]) else {}),  # famous names sit on nobodies, and the reverse
        **({"renown": renown} if (renown := int(clan.get("renown") or 0)) else {}),
        **({"traits": traits} if (traits := len(clan.get("saved_traits") or [])) else {}),
    }


# What the band swore itself to, off WB's clan library — summarised to each trait and its group at any size, the effect and flavour only when named.
def _build_traits(clan: dict, detailed: bool) -> dict | list[dict]:
    sworn, library = clan.get("saved_traits") or [], load_data("clan-traits.json")
    return build_trait_list(sworn, library) if detailed else light({"ids": build_trait_ids(sworn, library, "group")}, "traits")


# WB `Clan.getClanCulture`: the chief's culture, else the clan's `culture_id` — not `identity`'s `name_culture_id`. Lazily resolved, so half the saves hold neither.
def _clan_culture(clan: dict, ctx: dict) -> int | None:
    chief = ctx["actors_by_id"].get(clan.get("chief_id")) or {}
    return chief.get("culture") or clan.get("culture_id")


# The rank getters, shared with `competition_ranks`. Living counts read off the one actor pass: the podium weighs every band, on each of the ten dimensions.
def _rank_getters(tallies: dict, world_time: float) -> dict:
    return {
        "age": lambda c: entity_age(c, world_time),
        "books_written": lambda c: int(c.get("books_written") or 0),
        "births": lambda c: int(c.get("total_births") or 0),
        "deaths": lambda c: int(c.get("total_deaths") or 0),
        "kills": lambda c: int(c.get("total_kills") or 0),
        "members": lambda c: len(tallies["members"].get(c["id"], ())),
        "money": lambda c: tallies["money"][c["id"]],
        "renown": lambda c: int(c.get("renown") or 0),
        "renown_total": lambda c: tallies["renown_total"][c["id"]],
        "traits": lambda c: len(c.get("saved_traits") or []),
    }


# WB `Clan.getNextChief`: the living ranked by `sortUnitsSortedByAgeAndTraits` under `_clan_culture`, sitting chief skipped — the same rule a crown follows.
def _resolve_heir(clan: dict, members: list[dict], ctx: dict) -> dict | None:
    chief_id = clan.get("chief_id")
    traits = set((ctx["cultures_by_id"].get(_clan_culture(clan, ctx)) or {}).get("saved_traits") or [])
    candidates = [a for a in members if a["id"] != chief_id]
    heir = succession_heir(candidates, traits, ctx["world_time"], lambda a: compute_actor_stats(a, ctx, ctx["subspecies_base_cache"]))
    return entity_ref(heir["id"], ctx["actors_by_id"]) if heir else None


def main(argv: list[str]) -> int:
    save_path, argv, _ = take_chapter(argv)
    if not argv:
        print("usage: info.py <id> [sections] [C<n>] — see tools/tools.md", file=sys.stderr)
        return 2
    try:
        clan_id = int(argv[0])
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
    clans_by_id = index_by_id(save.get("clans") or [])
    clan = clans_by_id.get(clan_id)
    if clan is None:
        print(f"unknown clan: {clan_id}", file=sys.stderr)
        return 1

    tallies: dict = {"members": {}, "money": Counter(), "renown_total": Counter()}  # One pass feeds every tally: WB points the actor at its clan, never the reverse

    for actor in save.get("actors_data") or []:
        if not (cid := actor.get("clan")):
            continue
        tallies["members"].setdefault(cid, []).append(actor)
        tallies["money"][cid] += int(actor.get("money") or 0)
        if fame := actor.get("renown"):
            tallies["renown_total"][cid] += int(fame)

    members = tallies["members"].get(clan_id, [])
    ctx = {
        "actors_by_id": index_by_id(save.get("actors_data") or []),
        "cities_by_id": index_by_id(save.get("cities") or []),
        "cultures_by_id": index_by_id(save.get("cultures") or []),
        "families_by_id": index_by_id(save.get("families") or []),
        "island_lookup": cache(lambda: compute_islands_cached(save, save_path)[1]),  # tile → island id, called not stored: only `members` needs it
        "kingdoms_by_id": index_by_id(save.get("kingdoms") or []),
        "languages_by_id": index_by_id(save.get("languages") or []),
        "religions_by_id": index_by_id(save.get("religions") or []),
        "subspecies_base_cache": {},  # `compute_actor_stats` cache: heavy base computed once per subspecies, reused across actors
        "subspecies_by_id": index_by_id(save.get("subspecies") or []),
        "tallies": tallies,  # the one actor pass, handed whole: `metadata` reads two of its three, `ranks` all three
        "world_time": save["mapStats"]["world_time"],
        **build_actor_stats_context(save),  # the heir's ascension stat, on the cultures that crown by one
    }

    out: dict = {}
    if "breakdown" in sections:
        # The living against the founder's `identity`, drifting harder than a lineage's — species goes, `ClanManager.newClan` seeding the roster from his bloodline.
        out["breakdown"] = {k: v for k, v in population_breakdown(members, ctx).items() if k != "species"}
    if "identity" in sections:
        out["identity"] = _build_identity(clan, ctx)
    if "members" in sections:
        out["members"] = _build_members(members, ctx, save, detailed=wants_detail(requested, len(members)))
    if "metadata" in sections:
        out["metadata"] = _build_metadata(clan, members, ctx)
    if "ranks" in sections:
        out["ranks"] = competition_ranks(clan, list(clans_by_id.values()), _rank_getters(tallies, ctx["world_time"]))
    if "traits" in sections:
        out["traits"] = _build_traits(clan, detailed=requested not in (None, "full"))
    emit(out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
