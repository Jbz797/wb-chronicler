#!/usr/bin/env python3

# One religion: the creed a founder preached, the rites its faithful keep and everyone who still holds to them. User-facing docs: `tools/tools.md`.
# A religion is preached, not inherited — WB converts a soul who hears it, where a culture is handed down at birth and a clan answers to a chief.

import sys
from collections import Counter
from functools import cache
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))

from actor_stats import build_actor_stats_context, compute_actor_stats, meta_ratios, population_of
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
    light,
    load_data,
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

_ALL_SECTIONS = ("books", "breakdown", "identity", "leaders", "members", "metadata", "population", "ranks", "traits")


# Books grouped by the creed they were written under, off their own `religion_id` — the save lists every volume standing, its faith stamped on it.
def _books_by_religion(save: dict) -> dict[int, list[dict]]:
    by_religion: dict[int, list[dict]] = {}
    for book in sorted(save.get("books") or [], key=lambda b: b["id"]):
        if (rid := book.get("religion_id")) is not None:
            by_religion.setdefault(rid, []).append(book)
    return by_religion


# Every volume written under this faith, whoever holds it now — the mirror of a town's shelf. Titles alone; `book/info.py <id>` carries the volume.
def _build_books(religion: dict, ctx: dict, requested: str | None) -> dict:
    written = ctx["books_by_religion"]().get(religion["id"], ())
    if not wants_detail(requested, len(written)):
        return light({"total": len(written)})
    return {"total": len(written), "written": [{"id": b["id"], "name": b.get("name")} for b in written]}


# The founder's card, as WB's window lays it out. `name_culture` is the custom this creed borrows its onomastics from, where a culture holds a template set.
def _build_identity(religion: dict, ctx: dict) -> dict:
    return {
        "founder": {"id": fid, "name": religion.get("creator_name")} if (fid := religion.get("creator_id")) is not None else None,
        "founding_city": entity_ref(religion.get("creator_city_id"), ctx["cities_by_id"]),
        "founding_clan": entity_ref(religion.get("creator_clan_id"), ctx["clans_by_id"]),
        "founding_kingdom": entity_ref(religion.get("creator_kingdom_id"), ctx["kingdoms_by_id"]),
        "name_culture": entity_ref(religion.get("name_culture_id"), ctx["cultures_by_id"]),
        "species": religion.get("creator_species_id"),
        "subspecies": entity_ref(religion.get("creator_subspecies_id"), ctx["subspecies_by_id"]),
    }


# Everyone alive who still holds to it, eldest first — WB points the actor at its faith, never the reverse. `total` rides with the list it counts, not `metadata`.
def _build_members(members: list[dict], ctx: dict, save: dict, detailed: bool) -> dict:
    if not detailed:  # `full` keeps the chapter light: ids and a headcount, the roster itself only when the section is asked for by name
        return light({"total": len(members)})
    island_of = ctx["island_lookup"]()  # resolved once: the lookup is memoised, but a wide faith would still call through it hundreds of times
    out = [
        {
            "age": actor_age(actor, ctx["world_time"]),
            "city": entity_ref(actor.get("cityID"), ctx["cities_by_id"]),  # the roster's one entity — a second ref costs 42 chars and blows the inline budget
            "id": actor["id"],
            "island_id": island_of.get((int(actor["x"]), int(actor["y"]))),  # Chronicler-only: land mass (`geography/info.py islands`)
            "job": resolve_profession(actor, save),
            **({"level": level} if (level := int(actor.get("level") or 0)) > 1 else {}),  # WB leaves most souls at 1 — a rung above is earned, and unaggregated.
            "name": actor.get("name"),
            "sex": sex_label(actor),
        }
        for actor in members
    ]
    return {"roster": sorted(out, key=lambda m: (-m["age"], m["id"])), "total": len(out)}


# The creed's ledger: WB's lifetime counters beside the reach a walk over towns and crowns tells — the founder's card sits in `identity`. Counters drop at zero.
def _build_metadata(religion: dict, members: list[dict], ctx: dict, tallies: dict) -> dict:
    religion_id = religion["id"]
    report = meta_report("meta", {"units": len(members), **meta_ratios(members, ctx)})  # what WB has the faithful say of themselves

    return {
        "age": entity_age(religion, ctx["world_time"]),
        **({"cities": cities} if (cities := tallies["cities"][religion_id]) else {}),  # towns WB records as holding it, not merely housing a believer
        **({"deaths": deaths} if (deaths := int(religion.get("total_deaths") or 0)) else {}),
        "id": religion_id,  # the block travels into `chapter.json`, detached from its command — the UI resolves the panel from this
        **({"kills": kills} if (kills := int(religion.get("total_kills") or 0)) else {}),
        **({"kingdoms": kingdoms} if (kingdoms := tallies["kingdoms"][religion_id]) else {}),  # crowns that made it their own, the widest reach WB grants a creed
        "name": religion.get("name"),
        **({"renown": renown} if (renown := int(religion.get("renown") or 0)) else {}),  # WB's own field, where its living's worth now sits in `population`
        **({"report": report} if report else {}),
        **({"traits": traits} if (traits := len(religion.get("saved_traits") or [])) else {}),
    }


# What the living say of the body they belong to — the settlement block less its granary and its head, and less `total`, which the `members` section owns.
def _build_population(members: list[dict], ctx: dict) -> dict:
    return {key: value for key, value in population_of(members, ctx).items() if key != "total"}


# What the faith practises, off WB's religion library — summarised to each rite and its group at any size, the effect and flavour only when named.
def _build_traits(religion: dict, detailed: bool) -> dict | list[dict]:
    held, library = religion.get("saved_traits") or [], load_data("religion-traits.json")
    return build_trait_list(held, library) if detailed else light({"ids": build_trait_ids(held, library, "group")})


# The rank getters, shared with `competition_ranks`. Living counts read off the one actor pass: the podium weighs every creed, on every dimension below.
def _rank_getters(tallies: dict, world_time: float, books: dict[int, list[dict]]) -> dict:
    return {
        "age": lambda r: entity_age(r, world_time),
        "books": lambda r: len(books.get(r["id"], ())),
        "cities": lambda r: tallies["cities"][r["id"]],
        "deaths": lambda r: int(r.get("total_deaths") or 0),
        "fed_pct": lambda r: tallies["fed"][r["id"]] / n if (n := tallies["eaters"][r["id"]]) else 0.0,
        "housed_pct": lambda r: tallies["housed"][r["id"]] / n if (n := len(tallies["members"].get(r["id"], ()))) else 0.0,
        "kills": lambda r: int(r.get("total_kills") or 0),
        "kingdoms": lambda r: tallies["kingdoms"][r["id"]],
        "members": lambda r: len(tallies["members"].get(r["id"], ())),
        "money": lambda r: tallies["money"][r["id"]],
        "renown": lambda r: int(r.get("renown") or 0),
        "renown_total": lambda r: tallies["renown_total"][r["id"]],
        "traits": lambda r: len(r.get("saved_traits") or []),
        "warriors": lambda r: tallies["warriors"][r["id"]],
    }


def main(argv: list[str]) -> int:
    save_path, argv, _ = take_chapter(argv)
    if not argv:
        print("usage: info.py <id> [sections] [C<n>] — see tools/tools.md", file=sys.stderr)
        return 2
    try:
        religion_id = int(argv[0])
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
    religions_by_id = index_by_id(save.get("religions") or [])
    religion = religions_by_id.get(religion_id)
    if religion is None:
        print(f"unknown religion: {religion_id}", file=sys.stderr)
        return 1

    # One pass feeds every tally: WB points the actor at the faith it holds, never the reverse.
    tallies: dict = {
        "cities": Counter(c["id_religion"] for c in save.get("cities") or [] if c.get("id_religion")),
        "eaters": Counter(),
        "fed": Counter(),
        "housed": Counter(),
        "kingdoms": Counter(k["id_religion"] for k in save.get("kingdoms") or [] if k.get("id_religion")),
        "members": {},
        "money": Counter(),
        "renown_total": Counter(),
        "warriors": Counter(),
    }

    for actor in save.get("actors_data") or []:
        if not (rid := actor.get("religion")):
            continue
        tallies["members"].setdefault(rid, []).append(actor)
        tallies["money"][rid] += int(actor.get("money") or 0)
        if actor.get("asset_id") not in NON_FOOD_SPECIES:  # WB `needsFood`: undead have no diet, so they weigh on neither side of the hunger share
            tallies["eaters"][rid] += 1
            tallies["fed"][rid] += int(actor.get("nutrition") or 0) >= SATED_MIN_NUTRITION
        tallies["housed"][rid] += bool(actor.get("homeBuildingID"))
        tallies["warriors"][rid] += actor.get("profession") == PROFESSION_WARRIOR
        if fame := actor.get("renown"):
            tallies["renown_total"][rid] += int(fame)

    members = tallies["members"].get(religion_id, [])
    ctx = {
        **build_actor_stats_context(save),  # brings the trait libraries and `subspecies_by_id`, `languages_by_id`, `world_time` with them
        "actors_by_id": index_by_id(save.get("actors_data") or []),
        "books_by_religion": cache(lambda: _books_by_religion(save)),  # called not stored: the `books` section lists them, `ranks` only counts them
        "cities_by_id": index_by_id(save.get("cities") or []),
        "clans_by_id": index_by_id(save.get("clans") or []),
        "cultures_by_id": index_by_id(save.get("cultures") or []),
        "families_by_id": index_by_id(save.get("families") or []),
        "island_lookup": cache(lambda: compute_islands_cached(save, save_path)[1]),  # tile → island id, called not stored: only `members` needs it
        "kingdoms_by_id": index_by_id(save.get("kingdoms") or []),
        "religions_by_id": religions_by_id,
    }

    out: dict = {}
    base_cache: dict = {}  # `compute_actor_stats` computes one heavy base per biology and reuses it; the podium and every section after share this one
    if "books" in sections:
        out["books"] = _build_books(religion, ctx, requested)
    if "breakdown" in sections:  # The living against the founder's `identity`: a creed crosses blood and border by preaching, one conversion at a time.
        out["breakdown"] = {k: v for k, v in population_breakdown(members, ctx).items() if k != "religions"}
    if "identity" in sections:
        out["identity"] = _build_identity(religion, ctx)
    if "leaders" in sections:  # WB names no such podium — ours, and it drops below five faithful, where a champion among three names nobody
        out["leaders"] = settlement_leaders(members, ctx["families_by_id"], children_by_id(save), lambda a: compute_actor_stats(a, ctx, base_cache))
    if "members" in sections:
        out["members"] = _build_members(members, ctx, save, detailed=wants_detail(requested, len(members)))
    if "metadata" in sections:
        out["metadata"] = _build_metadata(religion, members, ctx, tallies)
    if "population" in sections:
        out["population"] = _build_population(members, ctx)
    if "ranks" in sections:
        out["ranks"] = competition_ranks(religion, list(religions_by_id.values()), _rank_getters(tallies, ctx["world_time"], ctx["books_by_religion"]()))
    if "traits" in sections:
        out["traits"] = _build_traits(religion, detailed=requested not in (None, "full"))
    emit(out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
