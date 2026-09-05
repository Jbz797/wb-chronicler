#!/usr/bin/env python3

# One alliance: the pact a crown opened and others joined, its member realms, and everything their subjects amount to once pooled. Docs: `tools/tools.md`.
# WB holds a realm in at most one pact, and a pact outlives the crown that founded it — so its counters are its own, never the sum of its members'.

import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))

from actor_stats import build_actor_stats_context, compute_actor_stats, meta_ratios, population_of
from shared import (
    MIN_PER_CAPITA_UNITS,
    PROFESSION_WARRIOR,
    ZONE_TILES,
    children_by_id,
    civic_building_ids,
    competition_ranks,
    emit,
    entity_age,
    entity_ref,
    index_by_id,
    is_boat,
    load_save,
    meta_report,
    parse_sections,
    population_breakdown,
    settlement_leaders,
    take_chapter,
)

_ALL_SECTIONS = ("breakdown", "identity", "kingdoms", "leaders", "metadata", "population", "ranks", "wars")
_NEEDS_ACTORS = frozenset({"breakdown", "kingdoms", "leaders", "metadata", "population", "ranks"})  # `identity` reads the record, `wars` the war list

# The two that weigh the pact's ground. Its buildings outnumber its subjects several times over in a grown world, so the walk is worth skipping on its own.
_NEEDS_GROUND = frozenset({"metadata", "ranks"})


# Chronicler-only: what the pact was sworn as — the crown that opened it and the soul who signed, both of whom it may long outlive.
def _build_identity(alliance: dict, ctx: dict) -> dict:
    return {
        "founder": entity_ref(alliance.get("founder_actor_id"), ctx["actors_by_id"]),
        "founding_kingdom": entity_ref(alliance.get("founder_kingdom_id"), ctx["kingdoms_by_id"]),
        "motto": alliance.get("motto"),  # the pact's own words, worth quoting verbatim
    }


# The realms bound by it, weightiest first. Always named in full: four crowns at most in practice, and each is a tag the chronicler will want.
def _build_kingdoms(members: set[int], ctx: dict) -> list[dict]:
    out = [
        {
            "id": kid,
            "name": (ctx["kingdoms_by_id"].get(kid) or {}).get("name"),
            "population": ctx["populations_by_kingdom"][kid],
        }
        for kid in members
    ]
    return sorted(out, key=lambda k: (-k["population"], k["id"]))


# The pact's identity card: WB's own lifetime counters, which it keeps apart from its members', beside what a walk over the pooled living tells.
def _build_metadata(alliance: dict, subjects: list[dict], members: set[int], ctx: dict) -> dict:
    report = meta_report("meta", {"units": len(subjects), **meta_ratios(subjects, ctx)})  # WB gives a pact the same four verdicts it gives a realm
    return {
        "age": entity_age(alliance, ctx["world_time"]),
        **({"births": births} if (births := int(alliance.get("total_births") or 0)) else {}),
        **({"buildings": built} if (built := ctx["pooled"]["buildings"][alliance["id"]]) else {}),  # civic only, houses included; nature is not built
        "cities": sum(1 for c in ctx["cities_by_id"].values() if c.get("kingdomID") in members),
        **({"deaths": deaths} if (deaths := int(alliance.get("total_deaths") or 0)) else {}),
        "id": alliance["id"],  # the block travels into `chapter.json`, detached from its command — the UI resolves the tag from this
        **({"kills": kills} if (kills := int(alliance.get("total_kills") or 0)) else {}),
        "kingdoms": len(members),
        "name": alliance.get("name"),
        **({"renown": renown} if (renown := int(alliance.get("renown") or 0)) else {}),  # WB's own field, apart from the sum its realms carry
        **({"report": report} if report else {}),
        **({"territory": land} if (land := ctx["pooled"]["territory"][alliance["id"]]) else {}),  # zones its realms hold between them, as a crown counts its own
    }


# The wars its members are drawn into, named and nothing more — `war/info.py <id>` fields both camps, what each brings and what the fighting has cost.
def _build_wars(members: set[int], save: dict) -> list[dict]:
    out = []
    for war in save.get("wars") or []:
        if war.get("winner"):
            continue
        sides = ({war.get("main_attacker")} | set(war.get("list_attackers") or [])) | ({war.get("main_defender")} | set(war.get("list_defenders") or []))
        if members & (sides - {None}):
            out.append({"id": war["id"], "name": war.get("name")})
    return sorted(out, key=lambda w: w["id"])


# The rank getters, weighed against the other pacts. Pooled tallies ride off the one actor pass; WB's own counters are read straight off the record.
def _rank_getters(pooled: dict, world_time: float) -> dict:
    return {
        "age": lambda a: entity_age(a, world_time),
        "births": lambda a: int(a.get("total_births") or 0),
        "buildings": lambda a: pooled["buildings"][a["id"]],
        "cities": lambda a: pooled["cities"][a["id"]],
        "deaths": lambda a: int(a.get("total_deaths") or 0),
        "kills": lambda a: int(a.get("total_kills") or 0),
        # Per-head, so a tight pact can out-rank a wide one — floored at `MIN_PER_CAPITA_UNITS`, under which the divisor speaks louder than the body.
        "kills_per_capita": lambda a: int(a.get("total_kills") or 0) / n if (n := pooled["population"][a["id"]]) >= MIN_PER_CAPITA_UNITS else 0.0,
        "kingdoms": lambda a: len(a.get("kingdoms") or []),
        "money": lambda a: pooled["money"][a["id"]],
        "population": lambda a: pooled["population"][a["id"]],
        "renown": lambda a: int(a.get("renown") or 0),
        "renown_total": lambda a: pooled["renown_total"][a["id"]],
        "territory": lambda a: pooled["territory"][a["id"]],
        "warriors": lambda a: pooled["warriors"][a["id"]],
    }


def main(argv: list[str]) -> int:
    save_path, argv, _ = take_chapter(argv)
    if not argv:
        print("usage: info.py <id> [sections] [C<n>] — see tools/tools.md", file=sys.stderr)
        return 2
    try:
        alliance_id = int(argv[0])
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
    alliances_by_id = index_by_id(save.get("alliances") or [])
    alliance = alliances_by_id.get(alliance_id)
    if alliance is None:
        print(f"✗ unknown alliance: {alliance_id}", file=sys.stderr)
        return 1

    # A realm sits in one pact at most, so a single map carries every membership — and one actor pass then pools every tally by pact.
    pact_of = {kid: a["id"] for a in alliances_by_id.values() for kid in a.get("kingdoms") or []}
    populations_by_kingdom: Counter[int] = Counter()
    pooled: dict = {
        "buildings": Counter(),
        "cities": Counter(),
        "money": Counter(),
        "population": Counter(),
        "renown_total": Counter(),
        "subjects": defaultdict(list),
        "territory": Counter(),
        "warriors": Counter(),
    }

    for actor in (save.get("actors_data") or []) if _NEEDS_ACTORS.intersection(sections) else ():
        if not (kid := actor.get("civ_kingdom_id")) or is_boat(actor):  # the crown first: a soul owing none never pays for the hull test
            continue
        populations_by_kingdom[kid] += 1
        if (pact := pact_of.get(kid)) is None:
            continue
        pooled["subjects"][pact].append(actor)
        pooled["money"][pact] += int(actor.get("money") or 0)
        pooled["population"][pact] += 1
        pooled["warriors"][pact] += actor.get("profession") == PROFESSION_WARRIOR
        if fame := actor.get("renown"):
            pooled["renown_total"][pact] += int(fame)

    ground = save.get("cities") or [] if _NEEDS_GROUND.intersection(sections) else ()  # the zones only serve the building walk right below
    zone_to_pact: dict[tuple[int, int], int] = {}
    for city in ground:
        if (pact := pact_of.get(city.get("kingdomID"))) is None:
            continue
        pooled["cities"][pact] += 1
        zones = city.get("zones") or []
        pooled["territory"][pact] += len(zones)
        for z in zones:
            zone_to_pact[(z["x"], z["y"])] = pact

    # Civic buildings standing on the pact's ground, as a crown counts its own — `civic` gates first, one building in twenty passing it.
    civic = civic_building_ids()
    for b in save.get("buildings") or [] if ground else ():
        if b.get("asset_id") not in civic:
            continue
        bx, by = b.get("mainX"), b.get("mainY")
        if bx is not None and by is not None and (pact := zone_to_pact.get((bx // ZONE_TILES, by // ZONE_TILES))) is not None:
            pooled["buildings"][pact] += 1

    members = set(alliance.get("kingdoms") or [])
    subjects = pooled["subjects"].get(alliance_id, [])
    ctx = {
        **build_actor_stats_context(save),  # brings the trait libraries and `subspecies_by_id`, `languages_by_id`, `world_time` with them
        "actors_by_id": index_by_id(save.get("actors_data") or []),
        "cities_by_id": index_by_id(save.get("cities") or []),
        "cultures_by_id": index_by_id(save.get("cultures") or []),
        "families_by_id": index_by_id(save.get("families") or []),
        "kingdoms_by_id": index_by_id(save.get("kingdoms") or []),
        "pooled": pooled,
        "populations_by_kingdom": populations_by_kingdom,
        "religions_by_id": index_by_id(save.get("religions") or []),
    }

    out: dict = {}
    if "breakdown" in sections:
        out["breakdown"] = population_breakdown(subjects, ctx)
    if "identity" in sections:
        out["identity"] = _build_identity(alliance, ctx)
    if "kingdoms" in sections:
        out["kingdoms"] = _build_kingdoms(members, ctx)
    if "leaders" in sections:
        podium = settlement_leaders(subjects, ctx["families_by_id"], children_by_id(save), lambda a: compute_actor_stats(a, ctx))
        out["leaders"] = {key: value for key, value in podium.items() if key != "families"}  # a lineage answers to a crown, never to the pact above it
    if "metadata" in sections:
        out["metadata"] = _build_metadata(alliance, subjects, members, ctx)
    if "population" in sections:
        out["population"] = population_of(subjects, ctx)  # `total` kept, as a town and a crown keep theirs: the pact pools subjects, it enrols none
    if "ranks" in sections:
        out["ranks"] = competition_ranks(alliance, list(alliances_by_id.values()), _rank_getters(pooled, ctx["world_time"]))
    if "wars" in sections:
        out["wars"] = _build_wars(members, save)

    emit(out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
