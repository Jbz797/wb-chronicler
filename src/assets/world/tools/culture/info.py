#!/usr/bin/env python3

# One culture: the customs a founder set down, the traits its people swear by and everyone who still lives by them. User-facing docs: `tools/tools.md`.
# A culture is inherited, not joined — WB hands it down at birth and a conquest converts a town whole, where a clan wins one soul at a time and answers to a chief.

import sys
from collections import Counter
from functools import cache
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))

from actor_stats import build_actor_stats_context, compute_actor_stats, meta_ratios, population_of
from islands import compute_islands_cached
from shared import (
    MIN_PER_CAPITA_UNITS,
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


# Books grouped by the custom they were written under, off their own `culture_id` — the save lists every volume ever written, its author's culture stamped on it.
def _books_by_culture(save: dict) -> dict[int, list[dict]]:
    by_culture: dict[int, list[dict]] = {}
    for book in sorted(save.get("books") or [], key=lambda b: b["id"]):
        if (cid := book.get("culture_id")) is not None:
            by_culture.setdefault(cid, []).append(book)
    return by_culture


# Every volume written under this custom, whoever holds it now — the mirror of a town's `books`. Titles alone; `book/info.py <id>` carries the volume.
def _build_books(culture: dict, ctx: dict, requested: str | None) -> dict:
    written = ctx["books_by_culture"]().get(culture["id"], ())
    if not wants_detail(requested, len(written)):
        return light({"total": len(written)})
    return {"total": len(written), "written": [{"id": b["id"], "name": b.get("name")} for b in written]}


# The founder's card, as WB's window lays it out. `name_template_set` sheds `_set` then `_default`, leaving the species unless the set departs: `dwarf_nordic`.
def _build_identity(culture: dict, ctx: dict) -> dict:
    return {
        "founder": {"id": fid, "name": culture.get("creator_name")} if (fid := culture.get("creator_id")) is not None else None,
        "founding_city": entity_ref(culture.get("creator_city_id"), ctx["cities_by_id"]),
        "founding_clan": entity_ref(culture.get("creator_clan_id"), ctx["clans_by_id"]),
        "founding_kingdom": entity_ref(culture.get("creator_kingdom_id"), ctx["kingdoms_by_id"]),
        "name_template_set": (culture.get("name_template_set") or "").removesuffix("_set").removesuffix("_default") or None,
        "species": culture.get("creator_species_id"),
        "subspecies": entity_ref(culture.get("creator_subspecies_id"), ctx["subspecies_by_id"]),
    }


# Everyone alive who keeps the customs, eldest first — WB points the actor at its culture, never the reverse. `total` rides with the list it counts, not `metadata`.
def _build_members(members: list[dict], ctx: dict, save: dict, detailed: bool) -> dict:
    if not detailed:  # `full` keeps the chapter light: ids and a headcount, the roster itself only when the section is asked for by name
        return light({"total": len(members)})
    island_of = ctx["island_lookup"]()  # resolved once: the lookup is memoised, but a wide following would still call through it hundreds of times
    out = [
        {
            "age": actor_age(actor, ctx["world_time"]),
            "city": entity_ref(actor.get("cityID"), ctx["cities_by_id"]),  # the roster's one entity — a second ref costs some 40 chars and blows the inline budget
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


# The culture's ledger: WB's lifetime counters beside the reach a walk over towns and crowns tells — the founder's card sits in `identity`. Counters drop at zero.
def _build_metadata(culture: dict, members: list[dict], ctx: dict, tallies: dict) -> dict:
    culture_id = culture["id"]
    report = meta_report("meta", {"units": len(members), **meta_ratios(members, ctx)})  # what WB has the following say of itself

    return {
        "age": entity_age(culture, ctx["world_time"]),
        **({"cities": cities} if (cities := tallies["cities"][culture_id]) else {}),  # WB's own reach: towns holding it as their main culture, not merely housing it
        **({"deaths": deaths} if (deaths := int(culture.get("total_deaths") or 0)) else {}),
        "id": culture_id,  # the block travels into `chapter.json`, detached from its command — the UI resolves the panel from this
        **({"kills": kills} if (kills := int(culture.get("total_kills") or 0)) else {}),
        **({"kingdoms": kingdoms} if (kingdoms := tallies["kingdoms"][culture_id]) else {}),  # crowns that made it their own, the widest reach WB grants a custom
        "name": culture.get("name"),
        **({"renown": renown} if (renown := int(culture.get("renown") or 0)) else {}),  # WB's own field, where its living's worth now sits in `population`
        **({"report": report} if report else {}),
        **({"traits": traits} if (traits := len(culture.get("saved_traits") or [])) else {}),
    }


# What the living say of the body they belong to — the settlement block less its granary and its head, and less `total`, which the `members` section owns.
def _build_population(members: list[dict], ctx: dict) -> dict:
    return {key: value for key, value in population_of(members, ctx).items() if key != "total"}


# What the custom holds to, off WB's culture library — summarised to each trait and its group at any size, the effect and flavour only when named.
def _build_traits(culture: dict, detailed: bool) -> dict | list[dict]:
    held, library = culture.get("saved_traits") or [], load_data("culture-traits.json")
    return build_trait_list(held, library) if detailed else light({"ids": build_trait_ids(held, library, "group")})


# The rank getters, shared with `competition_ranks`. Living counts read off the one actor pass: the podium weighs every custom, on every dimension below.
def _rank_getters(tallies: dict, world_time: float, books: dict[int, list[dict]]) -> dict:
    return {
        "age": lambda c: entity_age(c, world_time),
        "books": lambda c: len(books.get(c["id"], ())),
        "cities": lambda c: tallies["cities"][c["id"]],
        "deaths": lambda c: int(c.get("total_deaths") or 0),
        "fed_pct": lambda c: tallies["fed"][c["id"]] / n if (n := tallies["eaters"][c["id"]]) else 0.0,
        "housed_pct": lambda c: tallies["housed"][c["id"]] / n if (n := len(tallies["members"].get(c["id"], ()))) else 0.0,
        "kills": lambda c: int(c.get("total_kills") or 0),
        # Per-head, so a small body can out-rank a wide one — floored at `MIN_PER_CAPITA_UNITS`, under which the divisor speaks louder than the body.
        "kills_per_capita": lambda c: int(c.get("total_kills") or 0) / n if (n := len(tallies["members"].get(c["id"], ()))) >= MIN_PER_CAPITA_UNITS else 0.0,
        "kingdoms": lambda c: tallies["kingdoms"][c["id"]],
        "members": lambda c: len(tallies["members"].get(c["id"], ())),
        "money": lambda c: tallies["money"][c["id"]],
        "renown": lambda c: int(c.get("renown") or 0),
        "renown_per_capita": lambda c: int(c.get("renown") or 0) / n if (n := len(tallies["members"].get(c["id"], ()))) >= MIN_PER_CAPITA_UNITS else 0.0,
        "renown_total": lambda c: tallies["renown_total"][c["id"]],
        "traits": lambda c: len(c.get("saved_traits") or []),
        "warriors": lambda c: tallies["warriors"][c["id"]],
    }


def main(argv: list[str]) -> int:
    save_path, argv, _ = take_chapter(argv)
    if not argv:
        print("usage: info.py <id> [sections] [C<n>] — see tools/tools.md", file=sys.stderr)
        return 2
    try:
        culture_id = int(argv[0])
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
    cultures_by_id = index_by_id(save.get("cultures") or [])
    culture = cultures_by_id.get(culture_id)
    if culture is None:
        print(f"✗ unknown culture: {culture_id}", file=sys.stderr)
        return 1

    # One pass feeds every tally: WB points the actor at the customs it was raised in, never the reverse.
    tallies: dict = {
        "cities": Counter(c["id_culture"] for c in save.get("cities") or [] if c.get("id_culture")),
        "eaters": Counter(),
        "fed": Counter(),
        "housed": Counter(),
        "kingdoms": Counter(k["id_culture"] for k in save.get("kingdoms") or [] if k.get("id_culture")),
        "members": {},
        "money": Counter(),
        "renown_total": Counter(),
        "warriors": Counter(),
    }

    for actor in save.get("actors_data") or []:
        if not (cid := actor.get("culture")):
            continue
        tallies["members"].setdefault(cid, []).append(actor)
        tallies["money"][cid] += int(actor.get("money") or 0)
        if actor.get("asset_id") not in NON_FOOD_SPECIES:  # WB `needsFood`: undead have no diet, so they weigh on neither side of the hunger share
            tallies["eaters"][cid] += 1
            tallies["fed"][cid] += int(actor.get("nutrition") or 0) >= SATED_MIN_NUTRITION
        tallies["housed"][cid] += bool(actor.get("homeBuildingID"))
        tallies["warriors"][cid] += actor.get("profession") == PROFESSION_WARRIOR
        if fame := actor.get("renown"):
            tallies["renown_total"][cid] += int(fame)

    members = tallies["members"].get(culture_id, [])
    ctx = {
        **build_actor_stats_context(save),  # brings the trait libraries and `subspecies_by_id`, `languages_by_id`, `world_time` with them
        "actors_by_id": index_by_id(save.get("actors_data") or []),
        "books_by_culture": cache(lambda: _books_by_culture(save)),  # called not stored: the `books` section lists them, `ranks` only counts them
        "cities_by_id": index_by_id(save.get("cities") or []),
        "clans_by_id": index_by_id(save.get("clans") or []),
        "cultures_by_id": cultures_by_id,
        "families_by_id": index_by_id(save.get("families") or []),
        "island_lookup": cache(lambda: compute_islands_cached(save, save_path)[1]),  # tile → island id, called not stored: only `members` needs it
        "kingdoms_by_id": index_by_id(save.get("kingdoms") or []),
        "religions_by_id": index_by_id(save.get("religions") or []),
    }

    out: dict = {}
    base_cache: dict = {}  # `compute_actor_stats` computes one heavy base per biology and reuses it; the podium and every section after share this one

    if "books" in sections:
        out["books"] = _build_books(culture, ctx, requested)
    if "breakdown" in sections:  # The living against the founder's `identity`, the widest drift of any tier: a child takes its city's customs, not its blood.
        out["breakdown"] = {k: v for k, v in population_breakdown(members, ctx).items() if k != "cultures"}
    if "identity" in sections:
        out["identity"] = _build_identity(culture, ctx)
    if "leaders" in sections:  # WB names no such podium — ours, and it drops below five followers, where a champion among three names nobody
        out["leaders"] = settlement_leaders(members, ctx["families_by_id"], children_by_id(save), lambda a: compute_actor_stats(a, ctx, base_cache))
    if "members" in sections:
        out["members"] = _build_members(members, ctx, save, detailed=wants_detail(requested, len(members)))
    if "metadata" in sections:
        out["metadata"] = _build_metadata(culture, members, ctx, tallies)
    if "population" in sections:
        out["population"] = _build_population(members, ctx)
    if "ranks" in sections:
        out["ranks"] = competition_ranks(culture, list(cultures_by_id.values()), _rank_getters(tallies, ctx["world_time"], ctx["books_by_culture"]()))
    if "traits" in sections:
        out["traits"] = _build_traits(culture, detailed=requested not in (None, "full"))

    emit(out)

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
