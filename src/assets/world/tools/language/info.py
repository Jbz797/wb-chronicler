#!/usr/bin/env python3

# One language: the tongue a founder coined, the traits its script carries and everyone who still speaks it. User-facing docs: `tools/tools.md`.
# A language is caught, not inherited — WB converts a neighbour who hears it spoken, where a culture is handed down at birth and a clan is sworn to a chief.

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

_ALL_SECTIONS = ("books", "breakdown", "identity", "leaders", "metadata", "population", "ranks", "speakers", "traits")


# Books grouped by the tongue they were written in, off their own `language_id` — the save lists every volume still standing, its script stamped on it.
def _books_by_language(save: dict) -> dict[int, list[dict]]:
    by_language: dict[int, list[dict]] = {}
    for book in sorted(save.get("books") or [], key=lambda b: b["id"]):
        if (lid := book.get("language_id")) is not None:
            by_language.setdefault(lid, []).append(book)
    return by_language


# Every volume still written in this script — `written` counts the standing ones, `metadata.written` WB's lifetime tally. `book/info.py <id>` carries the volume.
def _build_books(language: dict, ctx: dict, requested: str | None) -> dict:
    standing = ctx["books_by_language"]().get(language["id"], ())
    if not wants_detail(requested, len(standing)):
        return light({"total": len(standing)})
    return {"total": len(standing), "written": [{"id": b["id"], "name": b.get("name")} for b in standing]}


# The founder's card, as WB's window lays it out. `name_culture` is the custom this tongue borrows its onomastics from, where a culture holds a template set.
def _build_identity(language: dict, ctx: dict) -> dict:
    return {
        "founder": {"id": fid, "name": language.get("creator_name")} if (fid := language.get("creator_id")) is not None else None,
        "founding_city": entity_ref(language.get("creator_city_id"), ctx["cities_by_id"]),
        "founding_clan": entity_ref(language.get("creator_clan_id"), ctx["clans_by_id"]),
        "founding_kingdom": entity_ref(language.get("creator_kingdom_id"), ctx["kingdoms_by_id"]),
        "name_culture": entity_ref(language.get("name_culture_id"), ctx["cultures_by_id"]),
        "species": language.get("creator_species_id"),
        "subspecies": entity_ref(language.get("creator_subspecies_id"), ctx["subspecies_by_id"]),
    }


# The tongue's ledger: WB's lifetime counters beside the reach a walk over towns and crowns tells — the founder's card sits in `identity`. Counters drop at zero.
def _build_metadata(language: dict, speakers: list[dict], ctx: dict, tallies: dict) -> dict:
    language_id = language["id"]
    report = meta_report("meta", {"units": len(speakers), **meta_ratios(speakers, ctx)})  # what WB has the speakers say of themselves

    return {
        "age": entity_age(language, ctx["world_time"]),
        **({"cities": cities} if (cities := tallies["cities"][language_id]) else {}),  # towns WB records as speaking it, not merely housing a speaker
        **({"converted": converted} if (converted := int(language.get("speakers_converted") or 0)) else {}),  # won from another tongue, a WB lifetime tally
        **({"deaths": deaths} if (deaths := int(language.get("total_deaths") or 0)) else {}),
        "id": language_id,  # the block travels into `chapter.json`, detached from its command — the UI resolves the panel from this
        **({"kills": kills} if (kills := int(language.get("total_kills") or 0)) else {}),
        **({"kingdoms": kingdoms} if (kingdoms := tallies["kingdoms"][language_id]) else {}),  # crowns that made it their own, the widest reach WB grants a tongue
        **({"lost": lost} if (lost := int(language.get("speakers_lost") or 0)) else {}),  # gone over to another tongue, the mirror of `converted`
        "name": language.get("name"),
        **({"native": native} if (native := int(language.get("speakers_new") or 0)) else {}),  # born to it, WB `speakers_new` — never converts
        **({"renown": renown} if (renown := int(language.get("renown") or 0)) else {}),  # WB's own field, where its living's worth now sits in `population`
        **({"report": report} if report else {}),
        **({"traits": traits} if (traits := len(language.get("saved_traits") or [])) else {}),
        **({"written": written} if (written := int(language.get("books_written") or 0)) else {}),  # every volume ever penned in it, burnt ones counted
    }


# What the living say of the body they belong to — the settlement block less its granary and its head, and less `total`, which the `speakers` section owns.
def _build_population(speakers: list[dict], ctx: dict) -> dict:
    return {key: value for key, value in population_of(speakers, ctx).items() if key != "total"}


# Everyone alive who still speaks it, eldest first — WB points the actor at its tongue, never the reverse. `total` rides with the list it counts, not `metadata`.
def _build_speakers(speakers: list[dict], ctx: dict, save: dict, detailed: bool) -> dict:
    if not detailed:  # `full` keeps the chapter light: ids and a headcount, the roster itself only when the section is asked for by name
        return light({"total": len(speakers)})
    island_of = ctx["island_lookup"]()  # resolved once: the lookup is memoised, but a wide tongue would still call through it hundreds of times
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
        for actor in speakers
    ]
    return {"roster": sorted(out, key=lambda m: (-m["age"], m["id"])), "total": len(out)}


# What the script carries, off WB's language library — summarised to each trait and its group at any size, the effect and flavour only when named.
def _build_traits(language: dict, detailed: bool) -> dict | list[dict]:
    held, library = language.get("saved_traits") or [], load_data("language-traits.json")
    return build_trait_list(held, library) if detailed else light({"ids": build_trait_ids(held, library, "group")})


# The rank getters, shared with `competition_ranks`. Living counts read off the one actor pass: the podium weighs every tongue, on every dimension below.
def _rank_getters(tallies: dict, world_time: float, books: dict[int, list[dict]]) -> dict:
    return {
        "age": lambda l: entity_age(l, world_time),
        "books": lambda l: len(books.get(l["id"], ())),
        "cities": lambda l: tallies["cities"][l["id"]],
        "converted": lambda l: int(l.get("speakers_converted") or 0),
        "deaths": lambda l: int(l.get("total_deaths") or 0),
        "fed_pct": lambda l: tallies["fed"][l["id"]] / n if (n := tallies["eaters"][l["id"]]) else 0.0,
        "housed_pct": lambda l: tallies["housed"][l["id"]] / n if (n := len(tallies["speakers"].get(l["id"], ()))) else 0.0,
        "kills": lambda l: int(l.get("total_kills") or 0),
        "kingdoms": lambda l: tallies["kingdoms"][l["id"]],
        "lost": lambda l: int(l.get("speakers_lost") or 0),
        "money": lambda l: tallies["money"][l["id"]],
        "native": lambda l: int(l.get("speakers_new") or 0),
        "renown": lambda l: int(l.get("renown") or 0),
        "renown_total": lambda l: tallies["renown_total"][l["id"]],
        "speakers": lambda l: len(tallies["speakers"].get(l["id"], ())),
        "traits": lambda l: len(l.get("saved_traits") or []),
        "warriors": lambda l: tallies["warriors"][l["id"]],
        "written": lambda l: int(l.get("books_written") or 0),
    }


def main(argv: list[str]) -> int:
    save_path, argv, _ = take_chapter(argv)
    if not argv:
        print("usage: info.py <id> [sections] [C<n>] — see tools/tools.md", file=sys.stderr)
        return 2
    try:
        language_id = int(argv[0])
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
    languages_by_id = index_by_id(save.get("languages") or [])
    language = languages_by_id.get(language_id)
    if language is None:
        print(f"unknown language: {language_id}", file=sys.stderr)
        return 1

    # One pass feeds every tally: WB points the actor at the tongue it answers in, never the reverse.
    tallies: dict = {
        "cities": Counter(c["id_language"] for c in save.get("cities") or [] if c.get("id_language")),
        "eaters": Counter(),
        "fed": Counter(),
        "housed": Counter(),
        "kingdoms": Counter(k["id_language"] for k in save.get("kingdoms") or [] if k.get("id_language")),
        "money": Counter(),
        "renown_total": Counter(),
        "speakers": {},
        "warriors": Counter(),
    }

    for actor in save.get("actors_data") or []:
        if not (lid := actor.get("language")):
            continue
        tallies["speakers"].setdefault(lid, []).append(actor)
        tallies["money"][lid] += int(actor.get("money") or 0)
        if actor.get("asset_id") not in NON_FOOD_SPECIES:  # WB `needsFood`: undead have no diet, so they weigh on neither side of the hunger share
            tallies["eaters"][lid] += 1
            tallies["fed"][lid] += int(actor.get("nutrition") or 0) >= SATED_MIN_NUTRITION
        tallies["housed"][lid] += bool(actor.get("homeBuildingID"))
        tallies["warriors"][lid] += actor.get("profession") == PROFESSION_WARRIOR
        if fame := actor.get("renown"):
            tallies["renown_total"][lid] += int(fame)

    speakers = tallies["speakers"].get(language_id, [])
    ctx = {
        **build_actor_stats_context(save),  # brings the trait libraries and `languages_by_id`, `subspecies_by_id`, `world_time` with them
        "actors_by_id": index_by_id(save.get("actors_data") or []),
        "books_by_language": cache(lambda: _books_by_language(save)),  # called not stored: the `books` section lists them, `ranks` only counts them
        "cities_by_id": index_by_id(save.get("cities") or []),
        "clans_by_id": index_by_id(save.get("clans") or []),
        "cultures_by_id": index_by_id(save.get("cultures") or []),
        "families_by_id": index_by_id(save.get("families") or []),
        "island_lookup": cache(lambda: compute_islands_cached(save, save_path)[1]),  # tile → island id, called not stored: only `speakers` needs it
        "kingdoms_by_id": index_by_id(save.get("kingdoms") or []),
        "religions_by_id": index_by_id(save.get("religions") or []),
    }

    out: dict = {}
    base_cache: dict = {}  # `compute_actor_stats` computes one heavy base per biology and reuses it; the podium and every section after share this one

    if "books" in sections:
        out["books"] = _build_books(language, ctx, requested)
    if (
        "breakdown" in sections
    ):  # The living against the founder's `identity`: a tongue crosses blood and border faster than any other body, conversion by conversion.
        out["breakdown"] = {k: v for k, v in population_breakdown(speakers, ctx).items() if k != "languages"}
    if "identity" in sections:
        out["identity"] = _build_identity(language, ctx)
    if "leaders" in sections:  # WB names no such podium — ours, and it drops below five speakers, where a champion among three names nobody
        out["leaders"] = settlement_leaders(speakers, ctx["families_by_id"], children_by_id(save), lambda a: compute_actor_stats(a, ctx, base_cache))
    if "metadata" in sections:
        out["metadata"] = _build_metadata(language, speakers, ctx, tallies)
    if "population" in sections:
        out["population"] = _build_population(speakers, ctx)
    if "ranks" in sections:
        out["ranks"] = competition_ranks(language, list(languages_by_id.values()), _rank_getters(tallies, ctx["world_time"], ctx["books_by_language"]()))
    if "speakers" in sections:
        out["speakers"] = _build_speakers(speakers, ctx, save, detailed=wants_detail(requested, len(speakers)))
    if "traits" in sections:
        out["traits"] = _build_traits(language, detailed=requested not in (None, "full"))

    emit(out)

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
