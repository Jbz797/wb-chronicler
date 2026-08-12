#!/usr/bin/env python3

# One clan: the band a founder gathered, its chiefs, its sworn traits and who still wears the name. User-facing docs: `tools/tools.md`.
# A clan is joined, not inherited — unlike a family, which is a bloodline. WB lets one actor hold both, so the two rosters overlap without matching.

import sys
from functools import cache
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))

from actor_stats import build_actor_stats_context, compute_actor_stats
from islands import compute_islands_cached
from shared import (
    UNITS_PER_YEAR,
    build_trait_list,
    competition_ranks,
    emit,
    entity_ref,
    index_by_id,
    load_data,
    load_save,
    parse_sections,
    population_breakdown,
    resolve_profession,
    sex_label,
    succession_heir,
    take_chapter,
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


# Everyone alive who wears the colours, eldest first — WB points the actor at its clan and never the reverse, so the roster is rebuilt by walking the actors.
def _build_members(members: list[dict], ctx: dict, save: dict) -> list[dict]:
    out = [
        {
            "age": int((ctx["world_time"] - float(actor.get("created_time") or 0)) / UNITS_PER_YEAR) + (actor.get("age_overgrowth") or 0),
            "city": entity_ref(actor.get("cityID"), ctx["cities_by_id"]),
            "family": entity_ref(actor.get("family"), ctx["families_by_id"]),  # a clansman keeps his own bloodline — `family/info.py <id>` on it
            "id": actor["id"],
            "island_id": ctx["island_lookup"]().get((int(actor["x"]), int(actor["y"]))),  # Chronicler-only: land mass (`geography/info.py islands`)
            "name": actor.get("name"),
            "profession": resolve_profession(actor, save),
            "sex": sex_label(actor),
        }
        for actor in members
    ]
    return sorted(out, key=lambda m: (-m["age"], m["id"]))


# The clan's identity card: WB's own lifetime counters beside what only a walk over the living can tell — how many answer the call, and from where.
def _build_metadata(clan: dict, members: list[dict], ctx: dict) -> dict:
    cities = {c for a in members if (c := a.get("cityID"))}
    # Each cause WB bothered to write, its prefix stripped; a clan that never lost anyone to fire carries no key rather than a zero.
    causes = {k[len(_DEATH_PREFIX) :]: v for k, v in sorted(clan.items()) if k.startswith(_DEATH_PREFIX) and v}

    return {
        "age": int((ctx["world_time"] - float(clan.get("created_time") or 0)) / UNITS_PER_YEAR),
        "chief": entity_ref(clan.get("chief_id"), ctx["actors_by_id"]),
        "cities": len(cities),  # settlements its members answer from — a clan crosses borders, WB never ties it to one town
        "founder": {"id": fid, "name": clan.get("founder_actor_name")} if (fid := clan.get("founder_actor_id")) is not None else None,
        "founding_city": entity_ref(clan.get("founder_city_id"), ctx["cities_by_id"]),
        "founding_kingdom": entity_ref(clan.get("founder_kingdom_id"), ctx["kingdoms_by_id"]),
        "heir": _resolve_heir(clan, members, ctx),
        "id": clan["id"],  # the block travels into `chapter.json`, detached from its command — the UI resolves the tag from this
        "members": len(members),
        "money": sum(int(a.get("money") or 0) for a in members),  # the purse the living carry between them — a clan owns nothing of its own, WB banks per actor
        "name": clan.get("name"),
        "past_chiefs": len(clan.get("past_chiefs") or []),  # the sitting chief included — WB appends him on accession
        "renown_total": sum(int(a.get("renown") or 0) for a in members),  # The living's worth beside the clan's own — famous names sit on nobodies, and the reverse.
        "renown": int(clan.get("renown") or 0),
        "traits": len(clan.get("saved_traits") or []),
        **({"births": births} if (births := int(clan.get("total_births") or 0)) else {}),
        **({"books_written": books} if (books := int(clan.get("books_written") or 0)) else {}),
        **({"deaths_by_cause": causes} if causes else {}),  # chronicler-only: how the clan has been dying, which its totals alone never say
        **({"deaths": deaths} if (deaths := int(clan.get("total_deaths") or 0)) else {}),
        **({"kills": kills} if (kills := int(clan.get("total_kills") or 0)) else {}),
    }


# WB `Clan.getClanCulture`: the chief's culture, else the clan's `culture_id` — not `identity`'s `name_culture_id`. Lazily resolved, so half the saves hold neither.
def _clan_culture(clan: dict, ctx: dict) -> int | None:
    chief = ctx["actors_by_id"].get(clan.get("chief_id")) or {}
    return chief.get("culture") or clan.get("culture_id")


# The rank getters, shared by the section and by `competition_ranks`. Living counts come off the roster, lifetime counters off WB's own fields.
def _rank_getters(members_by_clan: dict, world_time: float) -> dict:
    return {
        "age": lambda c: int((world_time - float(c.get("created_time") or 0)) / UNITS_PER_YEAR),
        "books_written": lambda c: int(c.get("books_written") or 0),
        "births": lambda c: int(c.get("total_births") or 0),
        "deaths": lambda c: int(c.get("total_deaths") or 0),
        "kills": lambda c: int(c.get("total_kills") or 0),
        "members": lambda c: len(members_by_clan.get(c["id"], ())),
        "money": lambda c: sum(int(a.get("money") or 0) for a in members_by_clan.get(c["id"], ())),
        "renown": lambda c: int(c.get("renown") or 0),
        "renown_total": lambda c: sum(int(a.get("renown") or 0) for a in members_by_clan.get(c["id"], ())),
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
    try:
        sections = parse_sections(argv[1] if len(argv) > 1 else None, _ALL_SECTIONS)
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 2
    save = load_save(save_path)
    clans_by_id = index_by_id(save.get("clans") or [])
    clan = clans_by_id.get(clan_id)
    if clan is None:
        print(f"unknown clan: {clan_id}", file=sys.stderr)
        return 1

    members_by_clan: dict[int, list[dict]] = {}
    for actor in save.get("actors_data") or []:
        if cid := actor.get("clan"):
            members_by_clan.setdefault(cid, []).append(actor)

    members = members_by_clan.get(clan_id, [])
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
        out["members"] = _build_members(members, ctx, save)
    if "metadata" in sections:
        out["metadata"] = _build_metadata(clan, members, ctx)
    if "ranks" in sections:
        out["ranks"] = competition_ranks(clan, list(clans_by_id.values()), _rank_getters(members_by_clan, ctx["world_time"]))
    if "traits" in sections:
        out["traits"] = build_trait_list(clan.get("saved_traits") or [], load_data("clan-traits.json"))
    emit(out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
