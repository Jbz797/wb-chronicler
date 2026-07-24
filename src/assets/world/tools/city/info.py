#!/usr/bin/env python3

# User-facing docs (usage, sections) live in `tools/tools.md`. A city is a kingdom's constituent settlement — its own culture/religion/language, leader and founder.
# Notes below are for maintainers. Mirrors `kingdom/info.py` one tier down: per-city aggregates instead of per-kingdom; no diplomacy (relations/wars/alliance).

import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "actor"))
sys.path.insert(0, str(Path(__file__).parent.parent / "geography"))
from actor_stats import build_actor_stats_context, demographics
from islands import compute_islands_cached
from shared import (
    HAPPY_MIN_HAPPINESS,
    NON_FOOD_SPECIES,
    PROFESSION_KING,
    PROFESSION_LEADER,
    PROFESSION_WARRIOR,
    SATED_MIN_NUTRITION,
    SICK_TRAITS,
    UNITS_PER_YEAR,
    ZONE_TILES,
    civic_building_ids,
    competition_ranks,
    emit,
    entity_ref,
    food_resources,
    index_by_id,
    load_save,
    parse_sections,
    population_breakdown,
    settlement_rank_getters,
    take_chapter,
)

_ALL_SECTIONS = ("breakdown", "metadata", "population", "ranks")


# One pass over actors then buildings — every per-city tally the sections need, so no section rescans the save. Built whole whatever was asked for.
def _build_context(save: dict, save_path: Path) -> dict:
    captain_ids = {cap for army in save.get("armies", []) if (cap := army.get("id_captain"))}  # Captains have no `profession` value, but they rank as nobles.

    actors_by_city: dict[int, list[dict]] = {}
    actors_by_id: dict[int, dict] = {}
    eaters_by_city: Counter[int] = Counter()
    familyless_by_city: Counter[int] = Counter()
    fed_by_city: Counter[int] = Counter()
    happy_by_city: Counter[int] = Counter()
    homeless_by_city: Counter[int] = Counter()
    immortals_by_city: Counter[int] = Counter()
    infected_by_city: Counter[int] = Counter()
    money_by_city: Counter[int] = Counter()
    nobles_by_city: Counter[int] = Counter()
    populations_by_city: Counter[int] = Counter()
    renown_by_city: Counter[int] = Counter()
    sick_by_city: Counter[int] = Counter()
    warriors_by_city: Counter[int] = Counter()

    for actor in save.get("actors_data", []):
        actors_by_id[actor["id"]] = actor
        cid = actor.get("cityID")
        if not cid or (actor.get("asset_id") or "").startswith("boat_"):
            continue
        actors_by_city.setdefault(cid, []).append(actor)
        populations_by_city[cid] += 1
        money_by_city[cid] += int(actor.get("money") or 0)
        renown_by_city[cid] += int(actor.get("renown") or 0)
        if actor.get("asset_id") not in NON_FOOD_SPECIES:  # `needsFood`: undead (no diet) never count toward hunger
            eaters_by_city[cid] += 1
            if int(actor.get("nutrition") or 0) >= SATED_MIN_NUTRITION:
                fed_by_city[cid] += 1
        if actor.get("profession") == PROFESSION_WARRIOR:
            warriors_by_city[cid] += 1
        if actor.get("profession") in (PROFESSION_KING, PROFESSION_LEADER) or actor["id"] in captain_ids:  # king (the capital's), leader, or captain
            nobles_by_city[cid] += 1
        traits = actor.get("saved_traits") or []
        if "infected" in traits:
            infected_by_city[cid] += 1
        if not SICK_TRAITS.isdisjoint(traits):
            sick_by_city[cid] += 1
        if "immortal" in traits:
            immortals_by_city[cid] += 1
        if int(actor.get("happiness") or 0) >= HAPPY_MIN_HAPPINESS:
            happy_by_city[cid] += 1
        if not actor.get("homeBuildingID"):
            homeless_by_city[cid] += 1
        if not actor.get("family"):
            familyless_by_city[cid] += 1

    buildings_by_city: Counter[int] = Counter()
    civic = civic_building_ids()  # `houses` = the dwelling subset.
    food_ids = food_resources()
    food_by_city: Counter[int] = Counter()
    gold_by_city: Counter[int] = Counter()
    goods_by_city: Counter[int] = Counter()
    houses_by_city: Counter[int] = Counter()

    for b in save.get("buildings", []):
        cid = b.get("cityID")
        if not cid:
            continue
        # Storage split: `food` (eatable, WB `_current_total_food`), `gold` (ore), `goods` (the rest). All buildings count, not just civic.
        for r in (b.get("resources") or {}).get("saved_resources") or []:
            rid = r.get("id")
            amount = r.get("amount", 0)
            if rid in food_ids:
                food_by_city[cid] += amount
            elif rid == "gold":
                gold_by_city[cid] += amount
            else:
                goods_by_city[cid] += amount
        asset_id = b.get("asset_id")
        if asset_id in civic:
            buildings_by_city[cid] += 1
            if asset_id.startswith("house"):
                houses_by_city[cid] += 1

    return {
        **build_actor_stats_context(save),  # world_time, languages_by_id, subspecies_by_id, species_data…
        "actors_by_city": actors_by_city,
        "actors_by_id": actors_by_id,
        "buildings_by_city": buildings_by_city,
        "cultures_by_id": index_by_id(save.get("cultures", [])),
        "eaters_by_city": eaters_by_city,
        "familyless_by_city": familyless_by_city,
        "fed_by_city": fed_by_city,
        "food_by_city": food_by_city,
        "gold_by_city": gold_by_city,
        "goods_by_city": goods_by_city,
        "happy_by_city": happy_by_city,
        "homeless_by_city": homeless_by_city,
        "houses_by_city": houses_by_city,
        "immortals_by_city": immortals_by_city,
        "infected_by_city": infected_by_city,
        "kingdoms_by_id": index_by_id(save.get("kingdoms", [])),
        "money_by_city": money_by_city,
        "nobles_by_city": nobles_by_city,
        "populations_by_city": populations_by_city,
        "religions_by_id": index_by_id(save.get("religions", [])),
        "renown_by_city": renown_by_city,
        "save_path": save_path,  # islands cache key — the loaded save's real path (live or a chapter's map.wbox), not the module default.
        "sick_by_city": sick_by_city,
        "subspecies_base_cache": {},  # `compute_actor_stats` cache: heavy base computed once per subspecies, reused across actors.
        "warriors_by_city": warriors_by_city,
    }


# The city's identity card: WB's own lifetime counters (`total_deaths`/`total_kills`/`renown`) alongside the stocks and officialdom tallied in `_build_context`.
def _build_metadata(city: dict, ctx: dict, save: dict) -> dict:
    cid = city.get("id")
    age_units = ctx["world_time"] - float(city.get("created_time") or 0)
    _, island_lookup = compute_islands_cached(save, ctx["save_path"])

    # Chronicler-only: distinct island ids under the city's zones, sorted asc (1 = biggest) — probed at each zone's centre tile.
    centres = ((z["x"] * ZONE_TILES + ZONE_TILES // 2, z["y"] * ZONE_TILES + ZONE_TILES // 2) for z in city.get("zones") or [])
    islands = sorted({iid for pos in centres if (iid := island_lookup.get(pos)) is not None})

    kingdom = ctx["kingdoms_by_id"].get(city.get("kingdomID"))

    # Founder = the city's first settler (`founder_id`), emitted as `{id, name}` (dead or alive — the registry carries its visuals + tombstone).
    founder = None
    if fid := city.get("founder_id"):
        founder_actor = ctx["actors_by_id"].get(fid)
        name = founder_actor.get("name") if founder_actor else city.get("founder_name")
        founder = {"id": fid, "name": name or f"#{fid}"}

    return {
        "age": int(age_units / UNITS_PER_YEAR),
        "buildings": ctx["buildings_by_city"][cid],  # Civic buildings owned by the city (nature excluded); `houses` is the dwelling subset.
        **({"capital": True} if kingdom and kingdom.get("capitalID") == cid else {}),  # Omitted when False (absence = not its kingdom's seat).
        "culture": (ctx["cultures_by_id"].get(city.get("id_culture")) or {}).get("name"),  # Official culture (WB `id_culture`), not the population's majority.
        "deaths": int(city.get("total_deaths") or 0),  # Inhabitants lost over the city's lifetime (WB `total_deaths`).
        "food": ctx["food_by_city"][cid],  # Eatable resources stocked in the city's buildings.
        "founder": founder,
        "gold": ctx["gold_by_city"][cid],  # Gold ore in the city's buildings (mined + tribute). Not coins — see `population.money`.
        "goods": ctx["goods_by_city"][cid],  # Non-food, non-gold stock (materials, gems…).
        "houses": ctx["houses_by_city"][cid],  # Dwellings (subset of `buildings`).
        "id": cid,
        "islands": islands,
        "kills": int(city.get("total_kills") or 0),  # Enemies its inhabitants have slain over the city's lifetime (WB `total_kills`).
        "kingdom": entity_ref(city.get("kingdomID"), ctx["kingdoms_by_id"]),
        "language": (ctx["languages_by_id"].get(city.get("id_language")) or {}).get("name"),
        "leader": entity_ref(city.get("leaderID"), ctx["actors_by_id"]),  # The sitting mayor — `None` between leaders.
        "name": city.get("name"),
        "religion": (ctx["religions_by_id"].get(city.get("id_religion")) or {}).get("name"),
        "renown": city.get("renown", 0),
        "territory": len(city.get("zones") or []),  # Zone count (each = an 8-tile `TileZone`).
        "wealth": ctx["money_by_city"][cid] + ctx["gold_by_city"][cid],  # Everything it owns: its people's coins + the gold in its buildings.
    }


# Tiers/men/couples via `demographics`; `nobles` = leader/captains (+ the king in the capital); `sick`/`infected` = WB `calculateIsSick`.
def _build_population(city: dict, ctx: dict) -> dict:
    cid = city.get("id")

    actors = ctx["actors_by_city"].get(cid, [])
    demo = demographics(actors, ctx)
    men, stages = demo["men"], demo["stages"]
    total = len(actors)

    eaters = ctx["eaters_by_city"][cid]  # food-needing pop (undead excluded); denominator for `fed_pct`
    immortals = ctx["immortals_by_city"][cid]
    infected = ctx["infected_by_city"][cid]
    sick = ctx["sick_by_city"][cid]

    return {
        "adults": stages["adult"],
        "babies": stages["baby"],
        "children": stages["child"],
        "couples": demo["couples"],
        "elders": stages["elder"],
        "familyless": ctx["familyless_by_city"][cid],
        "fed_pct": round(100 * ctx["fed_by_city"][cid] / eaters) if eaters else 0,  # % of food-needing pop sated (nutrition ≥ 60).
        "food_per_capita": round(ctx["food_by_city"][cid] / total, 1) if total else 0,  # Eatable stock ÷ population.
        "happy": ctx["happy_by_city"][cid],
        "housed_pct": round((total - ctx["homeless_by_city"][cid]) / total * 100) if total else 0,
        **({"immortals": immortals} if immortals else {}),
        **({"infected": infected} if infected else {}),
        "men": men,
        "money": ctx["money_by_city"][cid],  # Total coins held across the city's population.
        "nobles": ctx["nobles_by_city"][cid],
        "renown_total": ctx["renown_by_city"][cid],  # Summed renown of all inhabitants (distinct from the city's own `metadata.renown`).
        **({"sick": sick} if sick else {}),
        "teens": stages["teen"],
        "total": total,
        "warriors": ctx["warriors_by_city"][cid],
        "wealth_per_capita": round((ctx["money_by_city"][cid] + ctx["gold_by_city"][cid]) / total, 1) if total else 0,  # `metadata.wealth` ÷ population.
        "women": total - men,
    }


def _compute_ranks(city: dict, ctx: dict, save: dict) -> dict:
    return competition_ranks(city, save.get("cities", []), settlement_rank_getters(ctx, "city"))


def main(argv: list[str]) -> int:
    save_path, argv, _ = take_chapter(argv)
    if not argv:
        print("usage: info.py <id> [sections] [C<n>] — see tools/tools.md", file=sys.stderr)
        return 2
    try:
        city_id = int(argv[0])
    except ValueError:
        print(f"invalid id: {argv[0]}", file=sys.stderr)
        return 1
    try:
        sections = parse_sections(argv[1] if len(argv) > 1 else None, _ALL_SECTIONS)
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 2
    save = load_save(save_path)
    city = index_by_id(save.get("cities", [])).get(city_id)
    if city is None:
        print(f"unknown city: {city_id}", file=sys.stderr)
        return 1
    ctx = _build_context(save, save_path)

    out: dict = {}
    if "breakdown" in sections:
        out["breakdown"] = population_breakdown(ctx["actors_by_city"].get(city_id, []), ctx)
    if "metadata" in sections:
        out["metadata"] = _build_metadata(city, ctx, save)
    if "population" in sections:
        out["population"] = _build_population(city, ctx)
    if "ranks" in sections:
        out["ranks"] = _compute_ranks(city, ctx, save)
    emit(out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
