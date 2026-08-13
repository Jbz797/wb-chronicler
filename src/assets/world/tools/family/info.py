#!/usr/bin/env python3

# One lineage: its founding couple, its living members and where they scattered. User-facing docs: `tools/tools.md`.
# A WorldBox family is a bloodline, not a household — see `metadata.houses`, which counts the roofs its members sleep under.

import sys
from collections import Counter
from functools import cache
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))

from islands import compute_islands_cached
from shared import (
    actor_age,
    competition_ranks,
    emit,
    entity_age,
    entity_ref,
    index_by_id,
    light,
    load_save,
    parse_sections,
    population_breakdown,
    resolve_profession,
    roster_ids,
    sex_label,
    take_chapter,
    wants_detail,
)

_ALL_SECTIONS = ("breakdown", "identity", "members", "metadata", "ranks")


# Chronicler-only: what the lineage officially is, stamped at its founding — not what its living carry, which drifts (77 % share a culture, 94 % a subspecies).
def _build_identity(family: dict, ctx: dict) -> dict:
    return {
        "culture": entity_ref(family.get("name_culture_id"), ctx["cultures_by_id"]),  # the culture that minted the name, not the members' own
        "species": family.get("species_id"),
        "subspecies": entity_ref(family.get("subspecies_id"), ctx["subspecies_by_id"]),
    }


# Everyone alive who carries the name, eldest first — the roster WB never stores. `total` rides with the list it counts rather than drifting in `metadata`.
def _build_members(members: list[dict], ctx: dict, save: dict, detailed: bool) -> dict:
    if not detailed:  # `full` keeps the chapter light: ids and a headcount, the roster itself only when the section is asked for by name
        return light({"ids": roster_ids(members, ctx["world_time"]), "total": len(members)}, "members")
    island_of = ctx["island_lookup"]()  # resolved once: the lookup is memoised, but a wide lineage would still call through it hundreds of times
    out = []
    for actor in members:
        out.append(
            {
                "age": actor_age(actor, ctx["world_time"]),
                "city": entity_ref(actor.get("cityID"), ctx["cities_by_id"]),
                "generation": int(actor.get("generation") or 1),
                **({"home": home} if (home := actor.get("homeBuildingID")) else {}),  # `house/info.py <id>` — who shares a roof with whom
                "id": actor["id"],
                "island_id": island_of.get((int(actor["x"]), int(actor["y"]))),  # Chronicler-only: land mass (`geography/info.py islands`)
                "name": actor.get("name"),
                "profession": resolve_profession(actor, save),
                "sex": sex_label(actor),
            }
        )
    return {"roster": sorted(out, key=lambda m: (-m["age"], m["id"])), "total": len(out)}


# The lineage's identity card: WB's own lifetime counters beside what only a walk over the living can tell — how many remain, and how far they spread.
def _build_metadata(family: dict, members: list[dict], ctx: dict) -> dict:
    tallies, family_id = ctx["tallies"], family["id"]  # roofs, coins and renown all came off the one actor pass — recounting them here would walk it twice

    # WB stores the founding pair as loose name/id fields rather than refs; the second is absent wherever a lone settler started the line.
    founders = [{"id": fid, "name": family.get(f"founder_actor_name_{n}")} for n in (1, 2) if (fid := family.get(f"main_founder_id_{n}")) is not None]

    return {
        "age": entity_age(family, ctx["world_time"]),
        "founders": founders,
        "founding_city": entity_ref(family.get("founder_city_id"), ctx["cities_by_id"]),
        "founding_kingdom": entity_ref(family.get("founder_kingdom_id"), ctx["kingdoms_by_id"]),
        "housed_pct": _housed_pct(members),  # share of the living with a roof; the rest sleep rough, which WB never states outright
        "id": family["id"],  # the block travels into `chapter.json`, detached from its command — the UI resolves the tag from this
        "name": family.get("name"),
        **({"alpha": entity_ref(family.get("alpha_id"), ctx["actors_by_id"])} if family.get("alpha_id") else {}),  # its head, on the few clans WB gave one
        # Every counter below drops at zero, as WB's own already do: a line sleeping rough and worth nothing carries no key, and the panels read them through `?? 0`.
        **({"births": births} if (births := int(family.get("total_births") or 0)) else {}),
        **({"deaths": deaths} if (deaths := int(family.get("total_deaths") or 0)) else {}),
        **({"houses": len(houses)} if (houses := tallies["houses"].get(family_id)) else {}),  # roofs they sleep under: most lineages scatter over three or four
        **({"kills": kills} if (kills := int(family.get("total_kills") or 0)) else {}),
        **({"money": money} if (money := tallies["money"][family_id]) else {}),  # the purse the living carry between them; WB banks per actor, never per line
        **({"renown": renown} if (renown := tallies["renown"][family_id]) else {}),
        # The two lineages this one split from, when WB recorded them — a family is born of a couple, so it inherits a name from each side.
        **({"parents": parents} if (parents := [ref for n in (1, 2) if (ref := entity_ref(family.get(f"original_family_{n}"), ctx["families_by_id"]))]) else {}),
    }


# Share of the living who sleep under a roof of their own. Ranked as a share, not a count, so a lineage of four fully housed outranks twenty half in the open.
def _housed_pct(roster: list[dict]) -> int:
    return round(sum(1 for a in roster if a.get("homeBuildingID")) / len(roster) * 100) if roster else 0


# The rank getters, shared by the section and by `competition_ranks`. Living counts come off the roster, lifetime counters off WB's own fields.
def _rank_getters(tallies: dict, world_time: float) -> dict:
    return {
        "age": lambda f: entity_age(f, world_time),
        "births": lambda f: int(f.get("total_births") or 0),
        "deaths": lambda f: int(f.get("total_deaths") or 0),
        "housed_pct": lambda f: _housed_pct(tallies["members"].get(f["id"], ())),
        "houses": lambda f: len(tallies["houses"].get(f["id"], ())),
        "kills": lambda f: int(f.get("total_kills") or 0),
        "members": lambda f: len(tallies["members"].get(f["id"], ())),
        "money": lambda f: tallies["money"][f["id"]],
        "renown": lambda f: tallies["renown"][f["id"]],
    }


def main(argv: list[str]) -> int:
    save_path, argv, _ = take_chapter(argv)
    if not argv:
        print("usage: info.py <id> [sections] [C<n>] — see tools/tools.md", file=sys.stderr)
        return 2
    try:
        family_id = int(argv[0])
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
    families_by_id = index_by_id(save.get("families") or [])  # built once: `ctx` hands the same index to every `entity_ref` below
    family = families_by_id.get(family_id)
    if family is None:
        print(f"unknown family: {family_id}", file=sys.stderr)
        return 1

    # One pass over the actors feeds every tally: WB points each actor at its lineage and never the reverse, so nothing here can be read off the family record.
    tallies: dict = {"houses": {}, "members": {}, "money": Counter(), "renown": Counter()}

    for actor in save.get("actors_data") or []:
        if not (fid := actor.get("family")):
            continue
        tallies["members"].setdefault(fid, []).append(actor)
        tallies["money"][fid] += int(actor.get("money") or 0)
        if fame := actor.get("renown"):
            tallies["renown"][fid] += int(fame)
        if home := actor.get("homeBuildingID"):
            tallies["houses"].setdefault(fid, set()).add(home)

    members = tallies["members"].get(family_id, [])
    ctx = {
        "actors_by_id": index_by_id(save.get("actors_data") or []),
        "cities_by_id": index_by_id(save.get("cities") or []),
        "cultures_by_id": index_by_id(save.get("cultures") or []),
        "families_by_id": families_by_id,
        "island_lookup": cache(lambda: compute_islands_cached(save, save_path)[1]),  # tile → island id, called not stored: only `members` needs it
        "kingdoms_by_id": index_by_id(save.get("kingdoms") or []),
        "languages_by_id": index_by_id(save.get("languages") or []),
        "religions_by_id": index_by_id(save.get("religions") or []),
        "subspecies_by_id": index_by_id(save.get("subspecies") or []),
        "tallies": tallies,  # the one actor pass, handed whole: `metadata` reads three of its four, `ranks` all four
        "world_time": save["mapStats"]["world_time"],
    }

    out: dict = {}
    if "breakdown" in sections:
        # The living against the `identity` stamped at founding — one in five is culturally split. Species goes (WB inherits it: always 100 %), subspecies drifts.
        out["breakdown"] = {k: v for k, v in population_breakdown(members, ctx).items() if k != "species"}
    if "identity" in sections:
        out["identity"] = _build_identity(family, ctx)
    if "members" in sections:
        out["members"] = _build_members(members, ctx, save, detailed=wants_detail(requested, len(members)))
    if "metadata" in sections:
        out["metadata"] = _build_metadata(family, members, ctx)
    if "ranks" in sections:
        getters = _rank_getters(tallies, ctx["world_time"])
        out["ranks"] = competition_ranks(family, list(families_by_id.values()), getters)
    emit(out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
