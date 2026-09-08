#!/usr/bin/env python3

# One religion: the creed a founder preached, the rites its faithful keep and everyone who still holds to them. User-facing docs: `tools/tools.md`.
# A religion is preached, not inherited — WB converts a soul who hears it, where a culture is handed down at birth and a clan answers to a chief.

import sys
from collections import Counter, defaultdict
from functools import cache
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))

from actor_stats import build_actor_stats_context, compute_actor_stats, meta_ratios, population_of
from islands import compute_islands_cached
from shared import (
    MIN_PER_CAPITA_UNITS,
    PROFESSION_WARRIOR,
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
_NEEDS_ACTORS = frozenset({"breakdown", "leaders", "members", "metadata", "population", "ranks"})  # the rest read the creed's record, its shelf and its library


# Books grouped by the creed stamped on them, off their own `religion_id` — unsorted, since `ranks` only counts a shelf and the section printing it sorts its own.
def _books_by_religion(save: dict) -> dict[int, list[dict]]:
    by_religion: defaultdict[int, list[dict]] = defaultdict(list)  # a factory, `setdefault` costing a fresh list per volume to drop it on all but the first
    for book in save.get("books") or []:
        if (rid := book.get("religion_id")) is not None:
            by_religion[rid].append(book)
    return by_religion


# Every volume written under this faith, whoever holds it now — the mirror of a town's shelf. Titles alone; `book/info.py <id>` carries the volume.
def _build_books(religion: dict, ctx: dict, requested: str | None) -> dict:
    written = ctx["books_by_religion"]().get(religion["id"], ())
    if not wants_detail(requested, len(written)):
        return light({"total": len(written)})
    return {"total": len(written), "written": [{"id": b["id"], "name": b.get("name")} for b in sorted(written, key=lambda b: b["id"])]}


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


# The rank getters, shared with `competition_ranks`. Living counts come off the rosters that one actor pass built — the podium weighs every creed.
def _rank_getters(tallies: dict, world_time: float, books: dict[int, list[dict]]) -> dict:
    members = tallies["members"]  # the one container several getters read; the others answer a single lambda apiece and are reached where they are named
    return {
        "age": lambda r: entity_age(r, world_time),
        "books": lambda r: len(books.get(r["id"], ())),
        "cities": lambda r: tallies["cities"][r["id"]],
        "deaths": lambda r: int(r.get("total_deaths") or 0),
        "housed_pct": lambda r: tallies["housed"][r["id"]] / n if (n := len(members.get(r["id"], ()))) >= MIN_PER_CAPITA_UNITS else 0.0,
        "kills": lambda r: int(r.get("total_kills") or 0),
        # Per-head, so a small body can out-rank a wide one — floored at `MIN_PER_CAPITA_UNITS`, under which the divisor speaks louder than the body.
        "kills_per_capita": lambda r: int(r.get("total_kills") or 0) / n if (n := len(members.get(r["id"], ()))) >= MIN_PER_CAPITA_UNITS else 0.0,
        "kingdoms": lambda r: tallies["kingdoms"][r["id"]],
        "members": lambda r: len(members.get(r["id"], ())),
        "money": lambda r: tallies["money"][r["id"]],
        "renown": lambda r: int(r.get("renown") or 0),
        "renown_per_capita": lambda r: int(r.get("renown") or 0) / n if (n := len(members.get(r["id"], ()))) >= MIN_PER_CAPITA_UNITS else 0.0,
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
        print(f"✗ invalid id: {argv[0]}", file=sys.stderr)  # a malformed call, like a bad section — not an entity that happens to be missing
        return 2

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
        print(f"✗ unknown religion: {religion_id}", file=sys.stderr)
        return 1

    # Towns and crowns answer off their own records; the living are grouped below. Skipped whole where no section asked — `traits` reads a data file.
    tallies: dict = {
        "cities": Counter(c["id_religion"] for c in save.get("cities") or [] if c.get("id_religion")),
        "housed": Counter(),
        "kingdoms": Counter(k["id_religion"] for k in save.get("kingdoms") or [] if k.get("id_religion")),
        "members": defaultdict(list),
        "money": Counter(),
        "renown_total": Counter(),
        "warriors": Counter(),
    }

    # WB points the actor at the faith it holds, never the reverse, so the flocks are gathered in one walk.
    members_by_id = tallies["members"]
    for actor in (save.get("actors_data") or []) if not _NEEDS_ACTORS.isdisjoint(sections) else ():
        if rid := actor.get("religion"):
            members_by_id[rid].append(actor)

    # The four sums answer to the podium alone, so they are read off the rosters once those stand — a section that wants none of them pays for none of them.
    if "ranks" in sections:
        housed, money, renown, warriors = (tallies[k] for k in ("housed", "money", "renown_total", "warriors"))
        for rid, flock in members_by_id.items():
            roofs = coins = fame = fighters = 0
            for actor in flock:
                roofs += bool(actor.get("homeBuildingID"))
                coins += int(actor.get("money") or 0)
                fame += int(actor.get("renown") or 0)
                fighters += actor.get("profession") == PROFESSION_WARRIOR
            housed[rid], money[rid], renown[rid], warriors[rid] = roofs, coins, fame, fighters

    members = members_by_id.get(religion_id, [])
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
    if "books" in sections:
        out["books"] = _build_books(religion, ctx, requested)
    if "breakdown" in sections:  # The living against the founder's `identity`: a creed crosses blood and border by preaching, one conversion at a time.
        out["breakdown"] = {k: v for k, v in population_breakdown(members, ctx).items() if k != "religions"}
    if "identity" in sections:
        out["identity"] = _build_identity(religion, ctx)
    if "leaders" in sections:  # WB names no such podium — ours, and it drops below five faithful, where a champion among three names nobody
        out["leaders"] = settlement_leaders(members, ctx["families_by_id"], children_by_id(save), lambda a: compute_actor_stats(a, ctx))
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
