#!/usr/bin/env python3

# One war: the two sides WB fields against each other, what each brings, and what the fighting has cost so far. Docs: `tools/tools.md`.
# A war is read from above rather than from a crown's side, so neither camp is `allies` or `opponents` here — they are `attackers` and `defenders`, as WB names them.
# No breakdown and no demography: pooling both camps would say a war of dwarves against dwarves, and `<kingdom>/info.py <id> breakdown` answers for each side apart.

import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))

from shared import (
    PROFESSION_WARRIOR,
    UNITS_PER_YEAR,
    emit,
    index_by_id,
    is_boat,
    load_save,
    meta_report,
    parse_sections,
    take_chapter,
)

_ALL_SECTIONS = ("attackers", "defenders", "metadata")


# WB's counters on the war, its origin and the verdict the fighting says of itself. No `identity`: a war swears to no culture or stock, and one line is no section.
def _build_metadata(war: dict, attackers: set[int], defenders: set[int], ctx: dict) -> dict:
    besieged = ctx["besieged_kingdoms"]
    deaths = int(war.get("total_deaths") or 0)
    started_by = ctx["started_by_actor"]  # WB stores the declaring kingdom's name but not the actor's, so a bare `{id}` is all a dead one leaves
    years = int((ctx["world_time"] - float(war.get("created_time") or 0)) / UNITS_PER_YEAR)
    state = {"age": years, "attackers_besieged": bool(attackers & besieged), "deaths": deaths, "defenders_besieged": bool(defenders & besieged)}
    return {
        "age": years,
        "deaths": deaths,  # the toll of the whole war, as every other tier counts its own; each camp keeps its share
        "id": war["id"],  # the block travels into `chapter.json`, detached from its command — the UI resolves the tag from this
        "name": war.get("name"),
        "renown_at_stake": war.get("renown", 0),
        **({"report": report} if (report := meta_report("war", state)) else {}),
        "started_by": {"id": war.get("started_by_actor_id"), **({"name": started_by["name"]} if started_by and started_by.get("name") else {})},
        "started_by_kingdom": {"id": war.get("started_by_kingdom_id"), "name": war.get("started_by_kingdom_name")},
        **({"war_type": kind} if (kind := war.get("war_type")) else {}),  # WB leaves it unset on most declarations, and an absent kind is not `none`
    }


# The realms on one side, weightiest first, with what they bring between them. The pact backing them is named where two of its members stand together.
def _build_side(kingdoms: set[int], deaths: int, alliances: list[dict], ctx: dict) -> dict:
    realms = [{"id": kid, "name": (ctx["kingdoms_by_id"].get(kid) or {}).get("name"), "population": ctx["populations_by_kingdom"][kid]} for kid in kingdoms]
    side = {
        "cities": sum(ctx["cities_by_kingdom"][kid] for kid in kingdoms),
        "deaths": deaths,
        "kingdoms": sorted(realms, key=lambda k: (-k["population"], k["id"])),
        "population": sum(realm["population"] for realm in realms),
        "warriors": sum(ctx["warriors_by_kingdom"][kid] for kid in kingdoms),
    }
    # WB backs a side with a pact only where two of its members field together — one realm alone answers for itself, whatever it has sworn elsewhere.
    for a in alliances:
        members = set(a.get("kingdoms") or [])
        if len(members & kingdoms) >= 2:
            side["alliance"] = {"id": a["id"], "name": a.get("name")}
            break
    return side


def main(argv: list[str]) -> int:
    save_path, argv, _ = take_chapter(argv)
    if not argv:
        print("usage: info.py <id> [sections] [C<n>] — see tools/tools.md", file=sys.stderr)
        return 2
    try:
        war_id = int(argv[0])
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
    war = index_by_id(save.get("wars") or []).get(war_id)
    if war is None:
        print(f"✗ unknown war: {war_id}", file=sys.stderr)
        return 1

    attackers = ({war.get("main_attacker")} | set(war.get("list_attackers") or [])) - {None}
    defenders = ({war.get("main_defender")} | set(war.get("list_defenders") or [])) - {None}
    started_by_id = war.get("started_by_actor_id")

    besieged: set[int] = set()  # a realm one of whose towns another army stands on: the two age-driven verdicts read it, and nothing else here does
    cities_by_kingdom: Counter[int] = Counter()
    populations_by_kingdom: Counter[int] = Counter()
    started_by_actor = None
    warriors_by_kingdom: Counter[int] = Counter()

    # The declaring king is picked up on the walk the tallies already make: indexing every soul alive would build thousands of entries to answer for one.
    for actor in save.get("actors_data") or []:
        if actor["id"] == started_by_id:
            started_by_actor = actor
        if is_boat(actor) or not (kid := actor.get("civ_kingdom_id")):
            continue
        populations_by_kingdom[kid] += 1
        warriors_by_kingdom[kid] += actor.get("profession") == PROFESSION_WARRIOR

    for city in save.get("cities") or []:
        if kid := city.get("kingdomID"):
            cities_by_kingdom[kid] += 1
            if city.get("besieged_by"):
                besieged.add(kid)

    # No `build_actor_stats_context` here: it loads every trait library, and a war asks nothing of a soul's stats — only the clock, read straight off the save.
    ctx = {
        "besieged_kingdoms": besieged,
        "cities_by_kingdom": cities_by_kingdom,
        "kingdoms_by_id": index_by_id(save.get("kingdoms") or []),
        "populations_by_kingdom": populations_by_kingdom,
        "started_by_actor": started_by_actor,
        "warriors_by_kingdom": warriors_by_kingdom,
        "world_time": float(save["mapStats"].get("world_time") or 0),
    }
    alliances = save.get("alliances") or []

    out: dict = {}
    if "attackers" in sections:
        out["attackers"] = _build_side(attackers, war.get("dead_attackers", 0), alliances, ctx)
    if "defenders" in sections:
        out["defenders"] = _build_side(defenders, war.get("dead_defenders", 0), alliances, ctx)
    if "metadata" in sections:
        out["metadata"] = _build_metadata(war, attackers, defenders, ctx)

    emit(out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
