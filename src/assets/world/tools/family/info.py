#!/usr/bin/env python3

# One family: its founding couple, its living members and where they scattered. User-facing docs: `tools/tools.md`.
# A WorldBox family is a bloodline, not a household — see `metadata.houses`, which counts the roofs its members sleep under.

import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))

from actor_stats import build_actor_stats_context, compute_actor_stats, meta_ratios, population_of
from shared import (
    MIN_PER_CAPITA_UNITS,
    PROFESSION_WARRIOR,
    actor_age,
    children_by_id,
    competition_ranks,
    emit,
    entity_age,
    entity_ref,
    index_by_id,
    light,
    load_save,
    meta_report,
    parse_sections,
    population_breakdown,
    resolve_profession,
    settlement_leaders,
    sex_label,
    take_chapter,
    wants_detail,
)

_ALL_SECTIONS = ("breakdown", "identity", "leaders", "members", "metadata", "population", "ranks")
_NEEDS_ACTORS = frozenset({"breakdown", "leaders", "members", "metadata", "population", "ranks"})  # `identity` alone reads the founding record and nothing else


# Chronicler-only: what the family was stamped as at its founding, not what its living carry — most still share both, the `breakdown` section telling how many.
def _build_identity(family: dict, ctx: dict) -> dict:
    # WB stores the founding pair as loose name/id fields rather than refs; the second is absent wherever a lone settler started the line.
    founders = [{"id": fid, "name": family.get(f"founder_actor_name_{n}")} for n in (1, 2) if (fid := family.get(f"main_founder_id_{n}")) is not None]
    return {
        "culture": entity_ref(family.get("name_culture_id"), ctx["cultures_by_id"]),  # the culture that minted the name, not the members' own
        "founders": founders,
        "founding_city": entity_ref(family.get("founder_city_id"), ctx["cities_by_id"]),
        "founding_kingdom": entity_ref(family.get("founder_kingdom_id"), ctx["kingdoms_by_id"]),
        "species": family.get("species_id"),
        "subspecies": entity_ref(family.get("subspecies_id"), ctx["subspecies_by_id"]),
    }


# Everyone alive who carries the name, eldest first — the roster WB never stores. `total` rides with the list it counts rather than drifting in `metadata`.
def _build_members(members: list[dict], ctx: dict, save: dict, detailed: bool) -> dict:
    if not detailed:  # `full` keeps the chapter light: ids and a headcount, the roster itself only when the section is asked for by name
        return light({"total": len(members)})
    out = [
        {
            "age": actor_age(actor, ctx["world_time"]),
            "city": entity_ref(actor.get("cityID"), ctx["cities_by_id"]),  # the named ref, the roster's one entity — a second would blow the inline budget
            "gen": int(actor.get("generation") or 1),  # a founder reads 1, the value WB assumes without ever writing it
            **({"home": home} if (home := actor.get("homeBuildingID")) else {}),  # `ground/info.py <id>` — who shares a roof with whom
            "id": actor["id"],
            "job": resolve_profession(actor, save),
            "name": actor.get("name"),
            "sex": sex_label(actor),
        }
        for actor in members
    ]
    return {"roster": sorted(out, key=lambda m: (-m["age"], m["id"])), "total": len(out)}


# The family's identity card: WB's lifetime counters beside what a walk over the living tells. Every counter drops at zero — the panels read them through `?? 0`.
def _build_metadata(family: dict, members: list[dict], ctx: dict) -> dict:
    report = meta_report("meta", {"units": len(members), **meta_ratios(members, ctx)})  # what WB has the line say of itself
    houses = {home for a in members if (home := a.get("homeBuildingID"))}  # its own roster alone: a handful of souls, where the podium's pass walks the world

    return {
        "age": entity_age(family, ctx["world_time"]),
        **({"alpha": entity_ref(family.get("alpha_id"), ctx["actors_by_id"])} if family.get("alpha_id") else {}),  # its head, on the few clans WB gave one
        **({"births": births} if (births := int(family.get("total_births") or 0)) else {}),
        # Towns and crowns its living answer from. A family almost always holds to one of each — which is what makes the line that says otherwise worth reading.
        **({"cities": len(cities)} if (cities := {cid for a in members if (cid := a.get("cityID"))}) else {}),
        **({"deaths": deaths} if (deaths := int(family.get("total_deaths") or 0)) else {}),
        **({"houses": len(houses)} if houses else {}),  # roofs they sleep under: two or three for most
        "id": family["id"],  # the block travels into `chapter.json`, detached from its command — the UI resolves the tag from this
        **({"kills": kills} if (kills := int(family.get("total_kills") or 0)) else {}),
        **({"kingdoms": len(kingdoms)} if (kingdoms := {kid for a in members if (kid := a.get("civ_kingdom_id"))}) else {}),
        "name": family.get("name"),
        # A family is born of a couple, so WB writes up to two parent lines — but a ref drops when that line has since died out and been purged from the save.
        **({"parents": parents} if (parents := [ref for n in (1, 2) if (ref := entity_ref(family.get(f"original_family_{n}"), ctx["families_by_id"]))]) else {}),
        **({"report": report} if report else {}),
    }


# What the living say of the body they belong to — the settlement block less its granary and its head, and less `total`, which the `members` section owns.
def _build_population(members: list[dict], ctx: dict) -> dict:
    return {key: value for key, value in population_of(members, ctx).items() if key != "total"}


# What a family is ranked on among the world's others. Living counts read off the rosters one actor pass built: the podium weighs every line, on each below.
def _rank_getters(tallies: dict, world_time: float) -> dict:
    return {
        "age": lambda f: entity_age(f, world_time),
        "births": lambda f: int(f.get("total_births") or 0),
        "births_per_death": lambda f: int(f.get("total_births") or 0) / d if (d := int(f.get("total_deaths") or 0)) else 0.0,
        "cities": lambda f: len({cid for a in tallies["members"].get(f["id"], ()) if (cid := a.get("cityID"))}),
        "deaths": lambda f: int(f.get("total_deaths") or 0),
        # No `housed_pct` here nor on a clan: a family runs a handful of souls, and a share capped at one ties most of the field — `population` says the share.
        "houses": lambda f: len(tallies["houses"].get(f["id"], ())),
        "kills": lambda f: int(f.get("total_kills") or 0),
        # Per-head, so a small body can out-rank a wide one — floored at `MIN_PER_CAPITA_UNITS`, under which the divisor speaks louder than the body.
        "kills_per_capita": lambda f: int(f.get("total_kills") or 0) / n if (n := len(tallies["members"].get(f["id"], ()))) >= MIN_PER_CAPITA_UNITS else 0.0,
        "kingdoms": lambda f: len({kid for a in tallies["members"].get(f["id"], ()) if (kid := a.get("civ_kingdom_id"))}),
        "members": lambda f: len(tallies["members"].get(f["id"], ())),
        "money": lambda f: tallies["money"][f["id"]],
        "renown_total": lambda f: tallies["renown_total"][f["id"]],  # a family has no renown of its own, unlike a clan — only what its members carry
        "warriors": lambda f: tallies["warriors"][f["id"]],
    }


def main(argv: list[str]) -> int:
    save_path, argv, _ = take_chapter(argv)
    if not argv:
        print("✗ usage: info.py <id> [sections] [C<n>] — see tools/tools.md", file=sys.stderr)
        return 2
    try:
        family_id = int(argv[0])
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
    families_by_id = index_by_id(save.get("families") or [])  # built once: `ctx` hands the same index to every `entity_ref` below
    family = families_by_id.get(family_id)
    if family is None:
        print(f"✗ unknown family: {family_id}", file=sys.stderr)
        return 1

    tallies: dict = {"houses": {}, "members": defaultdict(list), "money": Counter(), "renown_total": Counter(), "warriors": Counter()}

    # WB points each actor at its family and never the reverse, so the lines are gathered in one walk — skipped whole where no section wants the living.
    members_by_id = tallies["members"]
    for actor in (save.get("actors_data") or []) if _NEEDS_ACTORS.intersection(sections) else ():
        if fid := actor.get("family"):
            members_by_id[fid].append(actor)

    # The four sums answer to the podium alone, so they are read off the rosters once those stand — a section that wants none of them pays for none of them.
    if "ranks" in sections:
        houses, money, renown, warriors = (tallies[k] for k in ("houses", "money", "renown_total", "warriors"))
        for fid, line in members_by_id.items():
            roofs, coins, fame, fighters = set(), 0, 0, 0
            for actor in line:
                if home := actor.get("homeBuildingID"):  # a roof only where there is one, the set being keyed on the building itself
                    roofs.add(home)
                coins += int(actor.get("money") or 0)
                fame += int(actor.get("renown") or 0)
                fighters += actor.get("profession") == PROFESSION_WARRIOR
            houses[fid], money[fid], renown[fid], warriors[fid] = roofs, coins, fame, fighters

    members = tallies["members"].get(family_id, [])
    ctx = {
        **build_actor_stats_context(save),  # brings the trait libraries and `subspecies_by_id`, `languages_by_id`, `world_time` with them
        "actors_by_id": index_by_id(save.get("actors_data") or []),
        "cities_by_id": index_by_id(save.get("cities") or []),
        "cultures_by_id": index_by_id(save.get("cultures") or []),
        "families_by_id": families_by_id,
        "kingdoms_by_id": index_by_id(save.get("kingdoms") or []),
        "religions_by_id": index_by_id(save.get("religions") or []),
    }

    out: dict = {}
    if "breakdown" in sections:
        # The living against the `identity` stamped at founding. Species goes: WB has a child inherit it whole, so it reads 100 % everywhere; a subspecies drifts.
        out["breakdown"] = {k: v for k, v in population_breakdown(members, ctx).items() if k != "species"}
    if "identity" in sections:
        out["identity"] = _build_identity(family, ctx)
    if "leaders" in sections:  # its own family would win every family row, so only the souls stand — and the podium drops below four, naming nobody among three
        podium = settlement_leaders(members, ctx["families_by_id"], children_by_id(save), lambda a: compute_actor_stats(a, ctx), ctx["world_time"])
        out["leaders"] = {key: value for key, value in podium.items() if key != "families"}
    if "members" in sections:
        out["members"] = _build_members(members, ctx, save, detailed=wants_detail(requested, len(members)))
    if "metadata" in sections:
        out["metadata"] = _build_metadata(family, members, ctx)
    if "population" in sections:
        out["population"] = _build_population(members, ctx)
    if "ranks" in sections:
        getters = _rank_getters(tallies, ctx["world_time"])
        out["ranks"] = competition_ranks(family, list(families_by_id.values()), getters)

    emit(out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
