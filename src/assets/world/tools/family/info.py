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
    UNITS_PER_YEAR,
    competition_ranks,
    emit,
    entity_ref,
    index_by_id,
    load_save,
    parse_sections,
    population_breakdown,
    resolve_profession,
    sex_label,
    take_chapter,
)

_ALL_SECTIONS = ("breakdown", "identity", "members", "metadata", "ranks")


# Chronicler-only: what the lineage officially is, stamped at its founding — not what its living carry, which drifts (77 % share a culture, 94 % a subspecies).
def _build_identity(family: dict, ctx: dict) -> dict:
    return {
        "culture": entity_ref(family.get("name_culture_id"), ctx["cultures_by_id"]),  # the culture that minted the name, not the members' own
        "species": family.get("species_id"),
        "subspecies": entity_ref(family.get("subspecies_id"), ctx["subspecies_by_id"]),
    }


# Everyone alive who carries the name, eldest first — the roster WB never stores, rebuilt by walking the actors once.
def _build_members(members: list[dict], ctx: dict, save: dict) -> list[dict]:
    out = []
    for actor in members:
        out.append(
            {
                "age": int((ctx["world_time"] - float(actor.get("created_time") or 0)) / UNITS_PER_YEAR) + (actor.get("age_overgrowth") or 0),
                "city": entity_ref(actor.get("cityID"), ctx["cities_by_id"]),
                "generation": int(actor.get("generation") or 1),
                **({"home": home} if (home := actor.get("homeBuildingID")) else {}),  # `house/info.py <id>` — who shares a roof with whom
                "id": actor["id"],
                "island_id": ctx["island_lookup"]().get((int(actor["x"]), int(actor["y"]))),  # Chronicler-only: land mass (`geography/info.py islands`)
                "name": actor.get("name"),
                "profession": resolve_profession(actor, save),
                "sex": sex_label(actor),
            }
        )
    return sorted(out, key=lambda m: (-m["age"], m["id"]))


# The lineage's identity card: WB's own lifetime counters beside what only a walk over the living can tell — how many remain, and how far they spread.
def _build_metadata(family: dict, members: list[dict], ctx: dict) -> dict:
    houses = {h for a in members if (h := a.get("homeBuildingID"))}
    cities = {c for a in members if (c := a.get("cityID"))}
    housed = sum(1 for a in members if a.get("homeBuildingID"))

    # WB stores the founding pair as loose name/id fields rather than refs; the second is absent wherever a lone settler started the line.
    founders = [{"id": fid, "name": family.get(f"founder_actor_name_{n}")} for n in (1, 2) if (fid := family.get(f"main_founder_id_{n}")) is not None]

    return {
        "age": int((ctx["world_time"] - float(family.get("created_time") or 0)) / UNITS_PER_YEAR),
        **({"alpha": entity_ref(family.get("alpha_id"), ctx["actors_by_id"])} if family.get("alpha_id") else {}),  # its head, on the few clans WB gave one
        **({"births": births} if (births := int(family.get("total_births") or 0)) else {}),
        "cities": len(cities),  # settlements its living members inhabit — a lineage spreads across a realm, WB never ties it to one town
        **({"deaths": deaths} if (deaths := int(family.get("total_deaths") or 0)) else {}),
        "founders": founders,
        "founding_city": entity_ref(family.get("founder_city_id"), ctx["cities_by_id"]),
        "founding_kingdom": entity_ref(family.get("founder_kingdom_id"), ctx["kingdoms_by_id"]),
        "housed_pct": round(housed / len(members) * 100) if members else 0,  # share of the living with a roof; the rest sleep rough, which WB never states outright
        "houses": len(houses),  # roofs they sleep under: a lineage under one roof is rare, most scatter over three or four
        "id": family["id"],  # the block travels into `chapter.json`, detached from its command — the UI resolves the tag from this
        **({"kills": kills} if (kills := int(family.get("total_kills") or 0)) else {}),
        "members": len(members),
        "money": sum(int(a.get("money") or 0) for a in members),  # the purse the living carry between them — a lineage owns nothing of its own, WB banks per actor
        "name": family.get("name"),
        # The two lineages this one split from, when WB recorded them — a family is born of a couple, so it inherits a name from each side.
        **({"parents": parents} if (parents := [ref for n in (1, 2) if (ref := entity_ref(family.get(f"original_family_{n}"), ctx["families_by_id"]))]) else {}),
        "renown": ctx["renown_by_family"][family["id"]],
    }


# Share of the living who sleep under a roof of their own. Ranked as a share, not a count, so a lineage of four fully housed outranks twenty half in the open.
def _housed_pct(family_id: int, tallies: dict) -> int:
    roster = tallies["members"].get(family_id, ())
    return round(tallies["housed"][family_id] / len(roster) * 100) if roster else 0


# The rank getters, shared by the section and by `competition_ranks`. Living counts come off the roster, lifetime counters off WB's own fields.
def _rank_getters(tallies: dict, world_time: float) -> dict:
    return {
        "age": lambda f: int((world_time - float(f.get("created_time") or 0)) / UNITS_PER_YEAR),
        "births": lambda f: int(f.get("total_births") or 0),
        "deaths": lambda f: int(f.get("total_deaths") or 0),
        "housed_pct": lambda f: _housed_pct(f["id"], tallies),
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
    try:
        sections = parse_sections(argv[1] if len(argv) > 1 else None, _ALL_SECTIONS)
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
    tallies: dict = {"housed": Counter(), "houses": {}, "members": {}, "money": Counter(), "renown": Counter()}

    for actor in save.get("actors_data") or []:
        if not (fid := actor.get("family")):
            continue
        tallies["members"].setdefault(fid, []).append(actor)
        tallies["money"][fid] += int(actor.get("money") or 0)
        if fame := actor.get("renown"):
            tallies["renown"][fid] += int(fame)
        if home := actor.get("homeBuildingID"):
            tallies["houses"].setdefault(fid, set()).add(home)
            tallies["housed"][fid] += 1

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
        "renown_by_family": tallies["renown"],
        "subspecies_by_id": index_by_id(save.get("subspecies") or []),
        "world_time": save["mapStats"]["world_time"],
    }

    out: dict = {}
    if "breakdown" in sections:
        # The living against the `identity` stamped at founding — one in five is culturally split. Species goes (WB inherits it: always 100 %), subspecies drifts.
        out["breakdown"] = {k: v for k, v in population_breakdown(members, ctx).items() if k != "species"}
    if "identity" in sections:
        out["identity"] = _build_identity(family, ctx)
    if "members" in sections:
        out["members"] = _build_members(members, ctx, save)
    if "metadata" in sections:
        out["metadata"] = _build_metadata(family, members, ctx)
    if "ranks" in sections:
        getters = _rank_getters(tallies, ctx["world_time"])
        out["ranks"] = competition_ranks(family, list(families_by_id.values()), getters)
    emit(out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
