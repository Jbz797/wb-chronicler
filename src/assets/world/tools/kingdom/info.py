#!/usr/bin/env python3

# User-facing docs (usage, available sections) live in `tools/tools.md`. Notes below are for maintainers — algorithm references, gotchas, source pointers.

import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))

from actor_stats import build_actor_stats_context, compute_actor_stats, demographics
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
    is_boat,
    kingdom_score_dimensions,
    kingdom_score_ranks,
    load_data,
    load_save,
    parse_sections,
    population_breakdown,
    settlement_rank_getters,
    take_chapter,
)

_ADULT_AGE = 16  # WB's `age_adult` (uniform across civilized species): an actor is an adult at ≥ 16 in-game years.
_ALL_SECTIONS = ("alliance", "breakdown", "cities", "metadata", "population", "ranks", "relations", "wars")
_ASCENSION_STATS = {"diplomatic_ascension": "diplomacy", "warriors_ascension": "warfare"}  # Culture succession by that stat (else age/money/renown/sex).
_BABY_AGE_THRESHOLD_UNITS = _ADULT_AGE * UNITS_PER_YEAR  # WB considers actors non-adult below `age_adult` (expressed in world_time units).

# WB `KingdomTraitLibrary`: a tax trait overrides the base rate (`Kingdom.recalcBaseStats`). Emitted as a tier — the rates are WB's to change, the tier isn't.
_KINGDOM_TAX_TRAITS = {
    "tax_rate_local_high": ("tax_local", "high"),
    "tax_rate_local_low": ("tax_local", "low"),
    "tax_rate_tribute_high": ("tax_tribute", "high"),
    "tax_rate_tribute_low": ("tax_tribute", "low"),
}

_OPINION_CONSTANTS = load_data("opinion-constants.json")
_TRAIT_MODS = _OPINION_CONSTANTS["actor_trait_opinion_mods"]  # Read once per king trait in `_compute_opinion`, so it earns its own name (as in `city/info.py`).
_WORLDVIEW_NEUTRAL = "neutral"
_WORLDVIEWS = ("ethnocentric_guard", "xenophiles", "xenophobic")  # WB's `worldview` culture traits: mutually exclusive, often absent — hence our own fourth value.


# The kingdom's alliance and its other members (`None` if unaligned). `population`/`renown` sum the members (WB tracks neither), ranked top-3; `motto` often absent.
def _build_alliance(kingdom: dict, ctx: dict, save: dict) -> dict | None:
    kid = kingdom["id"]
    alliance = next((a for a in save.get("alliances", []) if kid in (a.get("kingdoms") or [])), None)

    if alliance is None:
        return None

    kingdoms_by_id = ctx["kingdoms_by_id"]
    populations = ctx["populations_by_kingdom"]

    def totals(members: list[int]) -> tuple[int, int]:
        return (sum(populations.get(m, 0) for m in members), sum(int((kingdoms_by_id.get(m) or {}).get("renown") or 0) for m in members))

    own = totals(alliance.get("kingdoms") or [])
    others = [totals(a.get("kingdoms") or []) for a in save.get("alliances", [])]
    ranks = competition_ranks(own, others, {"population": lambda t: t[0], "renown": lambda t: t[1]})

    return {
        "allies": sorted(
            ({"id": i, "name": kingdoms_by_id.get(i, {}).get("name") or f"#{i}"} for i in alliance.get("kingdoms") or [] if i != kid), key=lambda o: o["id"]
        ),
        "breakdown": population_breakdown([a for m in alliance.get("kingdoms") or [] for a in ctx["actors_by_kingdom"].get(m, [])], ctx),
        "motto": alliance.get("motto"),
        "name": alliance.get("name"),
        "population": own[0],
        "ranks": ranks,
        "renown": own[1],
    }


# Chronicler-only: the kingdom's settlements, most populous first.
def _build_cities(kingdom: dict, ctx: dict) -> list[dict]:
    kid = kingdom["id"]
    cities = [c for c in ctx["cities_by_id"].values() if c.get("kingdomID") == kid]
    out = [{"id": c["id"], "name": c.get("name") or f"#{c['id']}", "population": ctx["populations_by_city"][c["id"]]} for c in cities]
    return sorted(out, key=lambda c: (-c["population"], c["id"]))


# One pass over actors, cities then buildings — every per-kingdom tally the sections need, so no section rescans the save. Built whole whatever was asked for.
def _build_context(save: dict, save_path: Path) -> dict:

    actors_by_clan: dict[int, list[dict]] = {}
    actors_by_id: dict[int, dict] = {}
    actors_by_kingdom: dict[int, list[dict]] = {}
    boats_by_kingdom: Counter[int] = Counter()  # Boats are actors, skipped by every other tally — counted here for `metadata.boats`.
    captain_ids = {cap for army in save.get("armies", []) if (cap := army.get("id_captain"))}  # Captains have no `profession` value, but they rank as nobles.
    eaters_by_kingdom: Counter[int] = Counter()
    families_by_kingdom: dict[int, set[int]] = {}
    familyless_by_kingdom: Counter[int] = Counter()
    fed_by_kingdom: Counter[int] = Counter()
    happy_by_kingdom: Counter[int] = Counter()
    homeless_by_kingdom: Counter[int] = Counter()
    immortals_by_kingdom: Counter[int] = Counter()
    infected_by_kingdom: Counter[int] = Counter()
    king_ids = {kid for k in save.get("kingdoms", []) if (kid := k.get("kingID"))}  # Reigning kings: nobles too, but their purse is reported on its own.
    money_by_kingdom: Counter[int] = Counter()
    nobles_by_kingdom: Counter[int] = Counter()
    nobles_money_by_kingdom: Counter[int] = Counter()
    populations_by_city: Counter[int] = Counter()  # Same base as `city/info.py`: non-boat `cityID` holders, kingdom membership irrelevant.
    warriors_by_city: Counter[int] = Counter()
    populations_by_kingdom: Counter[int] = Counter()  # Mirrors `Kingdom.getPopulation`; `boat_*` PNJs are transient. Nobles = kings (3) + leaders (4) + captains.
    renown_by_kingdom: Counter[int] = Counter()
    sick_by_kingdom: Counter[int] = Counter()
    warriors_by_kingdom: Counter[int] = Counter()

    for actor in save.get("actors_data", []):
        actors_by_id[actor["id"]] = actor
        if is_boat(actor):
            if bkid := actor.get("civ_kingdom_id"):
                boats_by_kingdom[bkid] += 1
            continue
        if cid := actor.get("cityID"):
            populations_by_city[cid] += 1
            if actor.get("profession") == PROFESSION_WARRIOR:
                warriors_by_city[cid] += 1  # `countTotalWarriors` reaches them through the cities — a fighter between two homes counts for nobody.
        kid = actor.get("civ_kingdom_id")
        if not kid:
            continue
        actors_by_kingdom.setdefault(kid, []).append(actor)
        if clan_id := actor.get("clan"):
            actors_by_clan.setdefault(clan_id, []).append(actor)  # Heir lookup: a royal clan spans kingdoms, so `actors_by_kingdom` can't serve it.
        populations_by_kingdom[kid] += 1
        money_by_kingdom[kid] += int(actor.get("money") or 0)
        renown_by_kingdom[kid] += int(actor.get("renown") or 0)
        if actor.get("asset_id") not in NON_FOOD_SPECIES:  # `needsFood`: undead (no diet) never count toward hunger
            eaters_by_kingdom[kid] += 1
            if int(actor.get("nutrition") or 0) >= SATED_MIN_NUTRITION:
                fed_by_kingdom[kid] += 1
        if actor.get("profession") in (PROFESSION_KING, PROFESSION_LEADER) or actor["id"] in captain_ids:
            nobles_by_kingdom[kid] += 1
            if actor["id"] not in king_ids:
                nobles_money_by_kingdom[kid] += int(actor.get("money") or 0)
        traits = actor.get("saved_traits") or []
        if "infected" in traits:
            infected_by_kingdom[kid] += 1
        if not SICK_TRAITS.isdisjoint(traits):
            sick_by_kingdom[kid] += 1
        if "immortal" in traits:
            immortals_by_kingdom[kid] += 1
        if int(actor.get("happiness") or 0) >= HAPPY_MIN_HAPPINESS:
            happy_by_kingdom[kid] += 1
        if not actor.get("homeBuildingID"):
            homeless_by_kingdom[kid] += 1
        if fid := actor.get("family"):
            families_by_kingdom.setdefault(kid, set()).add(fid)
        else:
            familyless_by_kingdom[kid] += 1

    cities_by_id: dict[int, dict] = {}
    cities_by_kingdom: dict[int, int] = {}
    territory_by_kingdom: dict[int, int] = {}
    zones_by_kingdom: dict[int, list[tuple[int, int]]] = {}

    for city in save.get("cities", []):
        cities_by_id[city["id"]] = city
        kid = city.get("kingdomID")
        if not kid:
            continue
        cities_by_kingdom[kid] = cities_by_kingdom.get(kid, 0) + 1
        warriors_by_kingdom[kid] += warriors_by_city[city["id"]]
        zones = city.get("zones") or []
        territory_by_kingdom[kid] = territory_by_kingdom.get(kid, 0) + len(zones)
        zones_by_kingdom.setdefault(kid, []).extend((z["x"], z["y"]) for z in zones)

    buildings_by_kingdom: Counter[int] = Counter()
    civic = civic_building_ids()  # Tallied per kingdom below (tile inside a city zone); `houses` = the dwelling subset.
    food_ids = food_resources()
    food_by_kingdom: Counter[int] = Counter()
    gold_by_kingdom: Counter[int] = Counter()
    goods_by_kingdom: Counter[int] = Counter()
    houses_by_kingdom: Counter[int] = Counter()
    zone_to_kingdom = {zone: kid for kid, zone_list in zones_by_kingdom.items() for zone in zone_list}

    for b in save.get("buildings", []):
        bx, by = b.get("mainX"), b.get("mainY")
        if bx is None or by is None:
            continue
        # Storage per city's kingdom: `food` (eatable, WB `_current_total_food`), `gold` (ore), `goods` (rest) — gated on `resources`, held by 0.5 % of buildings.
        if (stock := b.get("resources")) and (city := cities_by_id.get(b.get("cityID"))) and (fkid := city.get("kingdomID")):
            for r in stock.get("saved_resources") or []:
                rid = r.get("id")
                amount = r.get("amount", 0)
                if rid in food_ids:
                    food_by_kingdom[fkid] += amount
                elif rid == "gold":
                    gold_by_kingdom[fkid] += amount
                else:
                    goods_by_kingdom[fkid] += amount
        kid = zone_to_kingdom.get((bx // ZONE_TILES, by // ZONE_TILES))
        asset_id = b.get("asset_id")
        if kid is not None and asset_id in civic:
            buildings_by_kingdom[kid] += 1
            if asset_id.startswith("house"):
                houses_by_kingdom[kid] += 1

    capitals_by_kingdom = {k["id"]: cities_by_id[k["capitalID"]] for k in save.get("kingdoms", []) if k.get("capitalID") in cities_by_id}

    # WB `DiplomacyManager.findSupremeKingdom`: `power = warriors × 2 + cities × 5 + 1`, highest wins — population plays no part, though we once ranked on it.
    power_by_kingdom = {k["id"]: warriors_by_kingdom[k["id"]] * 2 + cities_by_kingdom.get(k["id"], 0) * 5 + 1 for k in save.get("kingdoms", [])}
    supreme_kingdom_id = max(power_by_kingdom, key=lambda kid: power_by_kingdom[kid], default=None)

    return {
        **build_actor_stats_context(save),
        "actors_by_clan": actors_by_clan,
        "actors_by_id": actors_by_id,
        "actors_by_kingdom": actors_by_kingdom,
        "boats_by_kingdom": boats_by_kingdom,
        "buildings_by_kingdom": buildings_by_kingdom,
        "capitals_by_kingdom": capitals_by_kingdom,
        "island_lookup": compute_islands_cached(save, save_path)[1],  # tile → island id; `far_lands` asks it whether two capitals share a landmass
        "cities_by_id": cities_by_id,
        "cities_by_kingdom": cities_by_kingdom,
        "cultures_by_id": index_by_id(save.get("cultures", [])),
        "eaters_by_kingdom": eaters_by_kingdom,
        "families_by_kingdom": families_by_kingdom,
        "familyless_by_kingdom": familyless_by_kingdom,
        "fed_by_kingdom": fed_by_kingdom,
        "food_by_kingdom": food_by_kingdom,
        "gold_by_kingdom": gold_by_kingdom,
        "goods_by_kingdom": goods_by_kingdom,
        "happy_by_kingdom": happy_by_kingdom,
        "homeless_by_kingdom": homeless_by_kingdom,
        "houses_by_kingdom": houses_by_kingdom,
        "immortals_by_kingdom": immortals_by_kingdom,
        "infected_by_kingdom": infected_by_kingdom,
        "kingdoms_at_war": {kid for w in save.get("wars", []) if not w.get("winner") for side in _war_sides(w) for kid in side},
        "kingdoms_by_id": index_by_id(save.get("kingdoms", [])),
        "money_by_kingdom": money_by_kingdom,
        "nobles_by_kingdom": nobles_by_kingdom,
        "nobles_money_by_kingdom": nobles_money_by_kingdom,
        "populations_by_city": populations_by_city,
        "populations_by_kingdom": populations_by_kingdom,
        "religions_by_id": index_by_id(save.get("religions", [])),  # The other breakdown indexes (`cultures`/`languages`/`subspecies`) already ride in ctx.
        "renown_by_kingdom": renown_by_kingdom,
        "score_dimensions": kingdom_score_dimensions(save),  # the composite score's ten tallies; four of them have no other source
        "save_path": save_path,  # islands cache key — the loaded save's real path (live or a chapter's map.wbox), not the module default.
        "sick_by_kingdom": sick_by_kingdom,
        "subspecies_base_cache": {},  # `compute_actor_stats` cache: heavy base computed once per subspecies, reused across actors (≈8×).
        "supreme_kingdom_id": supreme_kingdom_id,
        "territory_by_kingdom": territory_by_kingdom,
        "warriors_by_kingdom": warriors_by_kingdom,
        "world_age_id": save["mapStats"].get("world_age_id"),
        "zones_by_kingdom": zones_by_kingdom,
    }


# The kingdom's identity card: WB's own lifetime counters (`total_deaths`/`total_kills`/`renown`) alongside the stocks and holdings tallied in `_build_context`.
def _build_metadata(kingdom: dict, ctx: dict, save: dict) -> dict:
    kid = kingdom["id"]
    culture_traits = set((ctx["cultures_by_id"].get(kingdom.get("id_culture")) or {}).get("saved_traits") or [])
    dims = ctx["score_dimensions"]
    age_units = ctx["world_time"] - float(kingdom.get("created_time") or 0)

    # Chronicler-only: island ids the kingdom's city zones touch, sorted asc (1 = biggest), probed at each zone centre. From ctx — recomputing re-reads the disk.
    island_lookup = ctx["island_lookup"]
    centres = ((zx * ZONE_TILES + ZONE_TILES // 2, zy * ZONE_TILES + ZONE_TILES // 2) for zx, zy in ctx["zones_by_kingdom"].get(kid, []))
    islands = sorted({iid for pos in centres if (iid := island_lookup.get(pos)) is not None})

    # Reigning king (`kingID`), emitted as `{id, name}` (+ his purse). `None` at interregnum.
    king_actor = ctx["actors_by_id"].get(kingdom.get("kingID"))
    king = None

    if king_actor:
        # `money` = his own purse: inside `population.money`, netted out of `subjects_money` so both show apart.
        king = {"id": king_actor.get("id"), "money": int(king_actor.get("money") or 0), "name": king_actor.get("name") or f"#{king_actor.get('id')}"}

    # Founder = first ruler (`past_rulers[0]`) — dead ones left `actors_by_id`, so fall back to the name kept in the record.
    founder = None
    past_rulers = kingdom.get("past_rulers") or []

    if past_rulers:
        fid = past_rulers[0].get("id")
        founder_actor = ctx["actors_by_id"].get(fid)
        name = founder_actor.get("name") if founder_actor else past_rulers[0].get("name")
        founder = {"id": fid, "name": name or f"#{fid}"}

    heir = _resolve_heir(kingdom, ctx)

    # Chronicler-only: what WB shows as « Hommage » (to the crown) and the local tax. `normal` = no tax trait, i.e. 15 of the 16 kingdoms here.
    taxes = {"tax_local": "normal", "tax_tribute": "normal"}
    for trait in kingdom.get("saved_traits") or []:
        if spec := _KINGDOM_TAX_TRAITS.get(trait):
            taxes[spec[0]] = spec[1]

    return {
        "age": int(age_units / UNITS_PER_YEAR),
        **({"book_reach": reach} if (reach := dims["book_reach"].get(kid, 0)) else {}),  # 10 per authored book + its reads
        "boats": ctx["boats_by_kingdom"][kid],  # Fishing/trading/transport hulls afloat — WB's boat techs leave no other trace in the save.
        "buildings": ctx["buildings_by_kingdom"][kid],  # Civic buildings in the kingdom's zones (nature excluded); `houses` is the dwelling subset.
        "capital": {"id": cap["id"], "name": cap.get("name") or f"#{cap['id']}"} if (cap := ctx["capitals_by_kingdom"].get(kid)) else None,
        "cities": ctx["cities_by_kingdom"].get(kid, 0),
        "culture": entity_ref(kingdom.get("id_culture"), ctx["cultures_by_id"]),  # The crown's official culture — `breakdown` holds what its subjects actually are.
        **({"culture_traits": traits} if (traits := dims["culture_traits"].get(kid, 0)) else {}),  # its culture + language + religion traits
        "deaths": int(kingdom.get("total_deaths") or 0),  # Members lost over the kingdom's lifetime (WB `total_deaths`).
        "families": len(ctx["families_by_kingdom"].get(kid, ())),  # Distinct family lineages; `familyless` count is in `population`.
        "food": ctx["food_by_kingdom"][kid],  # Eatable resources stocked across the kingdom's buildings (WB « nourriture »).
        "founder": founder,
        "gold": ctx["gold_by_kingdom"][kid],  # Gold ore in the kingdom's buildings: mined from `mineral_gold` + half of each taxpayer's loot. Not coins.
        "goods": ctx["goods_by_kingdom"][kid],  # Non-food, non-gold stock (materials, gems…) across the kingdom's buildings.
        "heir": heir,
        "houses": ctx["houses_by_kingdom"][kid],  # Dwellings (subset of `buildings`).
        "id": kid,
        "islands": islands,
        "king": king,
        "kills": int(kingdom.get("total_kills") or 0),  # Enemies its members have slain over the kingdom's lifetime (WB `total_kills`).
        "language": entity_ref(kingdom.get("id_language"), ctx["languages_by_id"]),
        "motto": kingdom.get("motto"),
        "name": kingdom.get("name"),
        **({"foundings": found} if (found := dims["foundings"].get(kid, 0)) else {}),
        **({"peace_time": peace} if (peace := _peace_years(kingdom, ctx)) is not None else {}),  # Years without a war; absent while one is being fought.
        "religion": entity_ref(kingdom.get("id_religion"), ctx["religions_by_id"]),
        "renown": kingdom.get("renown", 0),
        "score_rank": kingdom_score_ranks(save, dims).get(kid),  # placement on the composite score (1 = strongest); the total stays internal
        **taxes,
        "territory": ctx["territory_by_kingdom"].get(kid, 0),
        **({"wars_won": won} if (won := dims["wars_won"].get(kid, 0)) else {}),
        "wealth": ctx["money_by_kingdom"][kid] + ctx["gold_by_kingdom"][kid],  # Everything it owns: its people's coins + the gold in its buildings.
        "worldview": next((t for t in _WORLDVIEWS if t in culture_traits), _WORLDVIEW_NEUTRAL),  # Culture's stance on foreigners (opinion mods 22-24), always set.
    }


# Tiers/men/couples via `demographics`; `nobles` = kings + leaders + captains; `sick`/`infected` = WB `calculateIsSick` (`infected` ⊂ `sick`).
def _build_population(kingdom: dict, ctx: dict) -> dict:
    kid = kingdom["id"]

    actors = ctx["actors_by_kingdom"].get(kid, [])
    demo = demographics(actors, ctx)
    men, stages = demo["men"], demo["stages"]
    total = len(actors)

    eaters = ctx["eaters_by_kingdom"][kid]  # food-needing pop (undead excluded); denominator for `fed_pct`
    king_money = int((ctx["actors_by_id"].get(kingdom.get("kingID")) or {}).get("money") or 0)  # Netted out of `subjects_money`; the value rides in `metadata.king`.

    # `immortals`/`infected`/`sick` omitted when 0 (UI-gated on > 0; absence = none). The rest always emitted — an explicit 0 is a meaningful demographic signal.
    immortals = ctx["immortals_by_kingdom"][kid]
    infected = ctx["infected_by_kingdom"][kid]
    sick = ctx["sick_by_kingdom"][kid]

    return {
        "adults": stages["adult"],
        "babies": stages["baby"],
        "children": stages["child"],
        "couples": demo["couples"],
        "elders": stages["elder"],
        "familyless": ctx["familyless_by_kingdom"][kid],
        "fed_pct": round(100 * ctx["fed_by_kingdom"][kid] / eaters) if eaters else 0,  # % of food-needing pop sated (nutrition ≥ 60).
        "food_per_capita": round(ctx["food_by_kingdom"][kid] / total, 1) if total else 0,  # Eatable stock ÷ population — food security.
        "happy": ctx["happy_by_kingdom"][kid],
        "housed_pct": round((total - ctx["homeless_by_kingdom"][kid]) / total * 100) if total else 0,
        **({"immortals": immortals} if immortals else {}),
        **({"infected": infected} if infected else {}),
        "men": men,
        "money": ctx["money_by_kingdom"][kid],  # Total coins held across the kingdom's population.
        "nobles": ctx["nobles_by_kingdom"][kid],
        "nobles_money": ctx["nobles_money_by_kingdom"][kid],  # Coins of the leaders/captains, king excluded — his own purse sits in `metadata.king`.
        "renown_total": ctx["renown_by_kingdom"][kid],  # Summed renown of all inhabitants (distinct from the kingdom's own `metadata.renown`).
        **({"sick": sick} if sick else {}),
        "subjects_money": ctx["money_by_kingdom"][kid] - king_money - ctx["nobles_money_by_kingdom"][kid],  # Commoners' coins: `money` minus crown and nobility.
        "teens": stages["teen"],
        "total": total,
        "warriors": ctx["warriors_by_kingdom"][kid],
        "wealth_per_capita": round((ctx["money_by_kingdom"][kid] + ctx["gold_by_kingdom"][kid]) / total, 1) if total else 0,  # `metadata.wealth` ÷ population.
        "women": total - men,
    }


# Diplomatic ties involving this kingdom. Status derived from alliances/wars cross-ref (WB only persists pair + timestamps).
def _build_relations(kingdom: dict, ctx: dict, save: dict, detailed: bool = False) -> list[dict]:
    kid = kingdom["id"]
    alliances = save.get("alliances", [])
    ongoing_wars = [w for w in save.get("wars", []) if not w.get("winner")]
    war_sides = [_war_sides(w) for w in ongoing_wars]  # Built once, reused by the enemy set + every `_compute_opinion` below.

    # Our side's ties resolved once instead of per target: allies = anyone sharing an alliance with us, enemies = anyone facing us in an ongoing war.
    allies = {member for a in alliances if kid in (a.get("kingdoms") or []) for member in a.get("kingdoms") or []}
    enemies: set = set()
    for attackers, defenders in war_sides:
        if kid in attackers:
            enemies |= defenders
        elif kid in defenders:
            enemies |= attackers

    # `save.relations` only persists pairs WB tracked, yet WB scores every kingdom regardless — hence the loop over all below and the `r or {}` fallbacks.
    relations_by_other = {
        (r.get("kingdom2_id") if r.get("kingdom1_id") == kid else r.get("kingdom1_id")): r
        for r in save.get("relations", [])
        if kid in (r.get("kingdom1_id"), r.get("kingdom2_id"))
    }

    halo = _zone_halo(ctx["zones_by_kingdom"].get(kid, []))  # built once and probed against each rival, rather than rebuilt on every pair
    side = _opinion_side(kingdom, ctx, allies, war_sides)
    out = []

    for other in save.get("kingdoms", []):
        other_id = other.get("id")
        if other_id == kid:
            continue
        r = relations_by_other.get(other_id)
        status = "ally" if other_id in allies else "enemy" if other_id in enemies else "neutral"
        last_war_end = (r or {}).get("timestamp_last_war_ended")
        borders = not halo.isdisjoint(ctx["zones_by_kingdom"].get(other_id, ()))

        out.append(
            {
                "age_years": int((ctx["world_time"] - float((r or {}).get("created_time") or 0)) / UNITS_PER_YEAR) if r else None,
                **({"borders": True} if borders else {}),  # Chronicler-only, omitted when False: absence = kingdoms don't share a border.
                "kingdom": {"id": other_id, "name": other.get("name") or f"#{other_id}"},
                "opinion": _compute_opinion(kingdom, side, other, ctx, r, borders, detailed),
                "status": status,
                "years_since_last_war": int((ctx["world_time"] - float(last_war_end)) / UNITS_PER_YEAR) if last_war_end else None,
            }
        )

    return sorted(out, key=lambda x: x["kingdom"]["id"])


# Ongoing wars involving this kingdom (as attacker or defender). Concluded wars are skipped (`winner` is set when a war ends).
def _build_wars(kingdom: dict, ctx: dict, save: dict) -> list[dict]:
    kid = kingdom["id"]
    kingdoms_by_id = ctx["kingdoms_by_id"]
    alliances = save.get("alliances", [])

    # Alliance backing a side when ≥2 of its kingdoms (the main + at least one ally) sit in the same alliance.
    def alliance_for(main_id: int | None, side_list: list[int]) -> dict | None:
        if main_id is None:
            return None
        for a in alliances:
            members = a.get("kingdoms") or []
            if main_id in members and len((set(side_list) & set(members)) - {main_id}) >= 1:
                return {"id": a["id"], "name": a["name"]}
        return None

    cities = ctx["cities_by_kingdom"]
    populations = ctx["populations_by_kingdom"]
    warriors = ctx["warriors_by_kingdom"]
    out = []

    for w in save.get("wars", []):
        if w.get("winner"):
            continue
        attackers, defenders = _war_sides(w)
        if kid not in attackers and kid not in defenders:
            continue
        side = "attacker" if kid in attackers else "defender"
        opponent_kingdoms = [kingdoms_by_id[oid] for oid in (defenders if side == "attacker" else attackers) if oid in kingdoms_by_id]
        ally_kingdoms = [kingdoms_by_id[aid] for aid in (attackers if side == "attacker" else defenders) - {kid} if aid in kingdoms_by_id]

        duration_units = ctx["world_time"] - float(w.get("created_time") or 0)

        # Instigator: WB stores the kingdom name but not the actor's — resolved from the save when still alive, bare `{id}` otherwise (searchable in past chapters).
        sb_id = w.get("started_by_actor_id")
        sb_actor = ctx["actors_by_id"].get(sb_id)

        out.append(
            {
                "allies": sorted(
                    ({"id": a["id"], "name": a.get("name") or f"#{a['id']}"} for a in ally_kingdoms),
                    key=lambda o: o["id"],
                ),
                "attacker_alliance": alliance_for(w.get("main_attacker"), w.get("list_attackers") or []),
                "cities": {"attackers": sum(cities.get(aid, 0) for aid in attackers), "defenders": sum(cities.get(did, 0) for did in defenders)},
                "deaths": {"attackers": w.get("dead_attackers", 0), "defenders": w.get("dead_defenders", 0)},
                "defender_alliance": alliance_for(w.get("main_defender"), w.get("list_defenders") or []),
                "duration_years": int(duration_units / UNITS_PER_YEAR),
                "id": w.get("id"),
                **({"is_main": True} if kid == w.get(f"main_{side}") else {}),  # Omitted when False (absence = secondary ally, not this side's leader).
                "name": w.get("name"),
                "opponents": sorted(
                    ({"id": opp["id"], "name": opp.get("name") or f"#{opp['id']}"} for opp in opponent_kingdoms),
                    key=lambda o: o["id"],
                ),
                "populations": {"attackers": sum(populations.get(aid, 0) for aid in attackers), "defenders": sum(populations.get(did, 0) for did in defenders)},
                "renown_at_stake": w.get("renown", 0),
                "side": side,
                "started_by": {
                    "actor": {"id": sb_id, **({"name": sb_actor["name"]} if sb_actor and sb_actor.get("name") else {})},
                    "kingdom": {"id": w.get("started_by_kingdom_id"), "name": w.get("started_by_kingdom_name")},
                },
                "war_type": w.get("war_type"),
                "warriors": {
                    "attackers": sum(warriors.get(aid, 0) for aid in attackers),
                    "defenders": sum(warriors.get(did, 0) for did in defenders),
                },
            }
        )
    return sorted(out, key=lambda x: x["id"])


# The island its capital stands on, probed at the seat's first zone centre. `None` for a realm without a capital — which then borders nobody's land.
def _capital_island(kingdom: dict, ctx: dict) -> int | None:
    capital = ctx["capitals_by_kingdom"].get(kingdom["id"])
    zones = (capital or {}).get("zones") or []
    if not zones:
        return None
    z = zones[0]
    return ctx["island_lookup"].get((z["x"] * ZONE_TILES + ZONE_TILES // 2, z["y"] * ZONE_TILES + ZONE_TILES // 2))


# Mirror `DiplomacyRelation.recalculate` IL: each numbered modifier = a WB `OpinionAsset`. Runtime stats reconstructed via `actor_stats.compute_actor_stats`.
def _compute_opinion(main: dict, side: dict, target: dict, ctx: dict, relation: dict | None, close: bool, detailed: bool) -> dict:
    mod: dict[str, int] = {}
    mid, tid = main["id"], target["id"]

    main_king, war_sides = side["king"], side["war_sides"]
    target_king = ctx["actors_by_id"].get(target.get("kingID"))
    enemy = any((mid in att and tid in dfd) or (mid in dfd and tid in att) for att, dfd in war_sides)

    # 1. king: target's king's diplomacy stat. WB keeps stats at runtime only, so we rebuild them: species base + traits + level/2 (that last one screen-calibrated).
    if target_king:
        mod["king"] = _king_stat(target_king, ctx, "diplomacy")

    # 2. kings_mood: WB's name misleads — it reads main's own king's `opinion` stat, which comes from clan traits (`silver_tongues` grants +20).
    if side["charm"]:
        mod["kings_mood"] = side["charm"]

    # 3. is_supreme: -100 if target holds WB's `kingdom_supreme` slot (highest `power`, see `_build_context`) and the world has ≥3 kingdoms.
    if tid == ctx.get("supreme_kingdom_id") and len(ctx["kingdoms_by_id"]) >= 3:
        mod["is_supreme"] = -100

    # 4. borders: ±25. WB checks `areKingdomsClose` (any city pair within adjacency threshold). `close` = the caller's zone-proximity proxy, computed once per pair.
    mod["borders"] = -25 if close else 25

    # 5. far_lands: +60 when the realms do not border and their capitals sit on different islands (`WorldTile.isSameIsland`), read off the island map.
    target_island = _capital_island(target, ctx)
    if not close and side["island"] is not None and target_island is not None and side["island"] != target_island:
        mod["far_lands"] = 60

    # 6. in_war: -500 if currently fighting.
    if enemy:
        mod["in_war"] = -500

    # 7. same_wars: +50 if on same side in any ongoing war (and NOT enemies).
    if not enemy and any((mid in att and tid in att) or (mid in dfd and tid in dfd) for att, dfd in war_sides):
        mod["same_wars"] = 50

    # 8. species: ±15/-10 if both kings exist and main « can have prejudice » (assumed true).
    if main_king and target_king:
        main_sp = (ctx["subspecies_by_id"].get(main_king.get("subspecies")) or {}).get("species_id")
        target_sp = (ctx["subspecies_by_id"].get(target_king.get("subspecies")) or {}).get("species_id")
        if main_sp and target_sp:
            mod["species"] = 15 if main_sp == target_sp else -10

    # 9. zones: clamp((main_zones − target_zones) / 5, -20, 0), negative when we own the most. WB's C# division truncates toward 0, where Python's floors.
    diff = side["territory"] - ctx["territory_by_kingdom"].get(tid, 0)
    zones_val = min(0, max(-20, int(diff / 5)))
    if zones_val:
        mod["zones"] = zones_val

    # 10. peace_time: years since their last war, capped at 20, past `minimum_years_between_wars` — `getRelation` mints blanks, so never-paired realms get all 20.
    minimum_years = _OPINION_CONSTANTS.get("minimum_years_between_wars", 5)
    years_since = (ctx["world_time"] - float((relation or {}).get("timestamp_last_war_ended") or 0)) / UNITS_PER_YEAR
    if not enemy and years_since > minimum_years:
        mod["peace_time"] = min(int(years_since), 20)

    # 11. power: max(0, (target_power − main_power) / 10) where power = countCities * 5 + getPopulationPeople() (adults, boats excluded).
    power_diff = _opinion_power(tid, ctx) - side["power"]
    if power_diff > 0:
        mod["power"] = power_diff // 10

    # 12. traits: per target.king trait — +same_trait_mod if main.king has same, +opposite_trait_mod if main.king has opposite.
    if main_king and target_king:
        traits_total = 0
        main_traits = side["king_traits"]
        for t in target_king.get("saved_traits") or []:
            spec = _TRAIT_MODS.get(t)
            if not spec:
                continue
            if t in main_traits:
                traits_total += spec["same"]
            elif spec.get("opposite_trait") and spec["opposite_trait"] in main_traits:
                traits_total += spec["opposite"]
        if traits_total:
            mod["traits"] = traits_total

    # 13-15. culture / religion / language: ±15 same/diff (if target has the attribute).
    for key, field in [("culture", "id_culture"), ("religion", "id_religion"), ("language", "id_language")]:
        tval = target.get(field)
        if tval is None:
            continue
        mod[key] = 15 if main.get(field) == tval else -15

    # 16. subspecies: ±10. WB calc fires when SPECIES DIFFER (subspecies = secondary distinction), main has king + canHavePrejudice — i.e. exactly modifier 8 at -10.
    if mod.get("species") == -10:
        main_sub = main_king.get("subspecies")
        target_sub = target_king.get("subspecies")
        if main_sub is not None and target_sub is not None:
            mod["subspecies"] = 10 if main_sub == target_sub else -10

    # 17. clan: ±40 between two crowned kings of the SAME SUBSPECIES — same blood is the precondition, the clan then says friend or rival.
    if main_king and target_king and main_king.get("subspecies") == target_king.get("subspecies"):
        main_clan, target_clan = main.get("royal_clan_id"), target.get("royal_clan_id")
        if main_clan and target_clan:
            mod["clan"] = 40 if main_clan == target_clan else -40

    # 18. in_alliance: +30 if same alliance — `side["allies"]` already holds every kingdom sharing one with `main`.
    if tid in side["allies"]:
        mod["in_alliance"] = 30

    # 19. truce: +100 if not enemy, has a recent relation with last_war_ended within minimum_years.
    if not enemy and years_since <= minimum_years:
        mod["truce"] = 100

    # 20. world_era: bonus_opinion of the current world age.
    era = ctx.get("world_age_id")
    era_bonus = _OPINION_CONSTANTS.get("world_age_bonus_opinion", {}).get(era)
    if era_bonus:
        mod["world_era"] = era_bonus

    # 21. baby_king: -50 if main's king not baby, target's king IS baby. WB « baby » threshold ≈ 16y.
    if main_king and target_king:
        target_age = ctx["world_time"] - float(target_king.get("created_time") or 0)
        if side["king_age"] >= _BABY_AGE_THRESHOLD_UNITS and target_age < _BABY_AGE_THRESHOLD_UNITS:
            mod["baby_king"] = -50

    # 22-24. Main's culture vs the target's kin, on the dominant SUBSPECIES (`getMainSubspecies`), not species — `ethnocentric_guard` wants the culture to differ.
    culture_traits = side["culture_traits"]
    same_sub = side["subspecies"] == _main_subspecies(target, ctx)  # two kingdoms with no subspecies at all read as alike, as WB's null == null does
    if "ethnocentric_guard" in culture_traits and same_sub and main.get("id_culture") != target.get("id_culture"):
        mod["ethnocentric_guard"] = -50
    if "xenophobic" in culture_traits and not same_sub:
        mod["xenophobic"] = -50
    if "xenophiles" in culture_traits and same_sub:
        mod["xenophiles"] = 20

    # Chronicler-only, named apart on purpose: `drivers` is every modifier and sums to `total`, `top_drivers` only the heaviest each way and does not.
    non_zero = [(k, v) for k, v in mod.items() if v]
    if detailed:
        return {"drivers": dict(sorted(non_zero)), "total": sum(mod.values())}

    top_pos = max((kv for kv in non_zero if kv[1] > 0), key=lambda kv: kv[1], default=None)
    top_neg = min((kv for kv in non_zero if kv[1] < 0), key=lambda kv: kv[1], default=None)

    return {"top_drivers": dict(sorted([kv for kv in (top_pos, top_neg) if kv is not None])), "total": sum(mod.values())}


# City-tier getters + the kingdom-only metrics (city count, health tallies, the wealth split by rank). Top 3 via `competition_ranks`, like every ranks section.
def _compute_ranks(kingdom: dict, ctx: dict, save: dict) -> dict:
    dims = ctx["score_dimensions"]

    def king_money(k: dict) -> int:
        return int((ctx["actors_by_id"].get(k.get("kingID")) or {}).get("money") or 0)

    getters = settlement_rank_getters(ctx, "kingdom")
    getters.update(
        {
            "boats": lambda k: ctx["boats_by_kingdom"].get(k.get("id"), 0),
            "book_reach": lambda k: dims["book_reach"].get(k.get("id"), 0),
            "cities": lambda k: ctx["cities_by_kingdom"].get(k.get("id"), 0),
            "culture_traits": lambda k: dims["culture_traits"].get(k.get("id"), 0),
            "foundings": lambda k: dims["foundings"].get(k.get("id"), 0),
            "immortals": lambda k: ctx["immortals_by_kingdom"].get(k.get("id"), 0),
            "infected": lambda k: ctx["infected_by_kingdom"].get(k.get("id"), 0),
            "king_money": king_money,
            "nobles_money": lambda k: ctx["nobles_money_by_kingdom"].get(k.get("id"), 0),
            "sick": lambda k: ctx["sick_by_kingdom"].get(k.get("id"), 0),
            "subjects_money": lambda k: ctx["money_by_kingdom"].get(k.get("id"), 0) - king_money(k) - ctx["nobles_money_by_kingdom"].get(k.get("id"), 0),
            "territory": lambda k: ctx["territory_by_kingdom"].get(k.get("id"), 0),  # A kingdom record has no `zones` — the tally sums its cities'.
            "wars_won": lambda k: dims["wars_won"].get(k.get("id"), 0),
        }
    )

    return competition_ranks(kingdom, save.get("kingdoms", []), getters)


# One of a king's runtime stats, rebuilt through the whole `actor_stats` pipeline — WB reads them off the live actor, we recompute from the save.
def _king_stat(king: dict, ctx: dict, stat: str) -> int:
    return int(compute_actor_stats(king, ctx, ctx["subspecies_base_cache"]).get(stat, 0))


# WB `Kingdom.getMainSubspecies` — the reigning king's, or its first member's while the throne is empty. `None` for a realm with neither.
def _main_subspecies(kingdom: dict, ctx: dict) -> int | None:
    king = ctx["actors_by_id"].get(kingdom.get("kingID"))
    if king:
        return king.get("subspecies")
    members = ctx["actors_by_kingdom"].get(kingdom["id"]) or []
    return members[0].get("subspecies") if members else None


# WB opinion modifier 11's own notion of power — `countCities × 5 + getPopulationPeople()`. Not `_build_context`'s supreme power, which weighs warriors instead.
def _opinion_power(kingdom_id: int, ctx: dict) -> int:
    return ctx["cities_by_kingdom"].get(kingdom_id, 0) * 5 + ctx["populations_by_kingdom"].get(kingdom_id, 0)


# What the queried realm's opinions would otherwise recompute per rival — the king's stats above all, which walk `actor_stats`. Built once by `_build_relations`.
def _opinion_side(kingdom: dict, ctx: dict, allies: set, war_sides: list) -> dict:
    king = ctx["actors_by_id"].get(kingdom.get("kingID"))
    return {
        "allies": allies,
        "charm": _king_stat(king, ctx, "opinion") if king else 0,
        "culture_traits": set((ctx["cultures_by_id"].get(kingdom.get("id_culture")) or {}).get("saved_traits") or []),
        "island": _capital_island(kingdom, ctx),
        "king": king,
        "king_age": ctx["world_time"] - float((king or {}).get("created_time") or 0),
        "king_traits": set((king or {}).get("saved_traits") or []),
        "power": _opinion_power(kingdom["id"], ctx),
        "subspecies": _main_subspecies(kingdom, ctx),
        "territory": ctx["territory_by_kingdom"].get(kingdom["id"], 0),
        "war_sides": war_sides,
    }


# Years without a war: since the last one ended (`Kingdom.checkEndWar` stamps `timestamp_last_war`), or since founding if none. `None` while one runs.
def _peace_years(kingdom: dict, ctx: dict) -> int | None:
    if kingdom["id"] in ctx["kingdoms_at_war"]:
        return None
    stamp = kingdom.get("timestamp_last_war")
    since = float(stamp) if stamp is not None and float(stamp) != -1.0 else float(kingdom.get("created_time") or 0)
    return int((ctx["world_time"] - since) / UNITS_PER_YEAR)


# Next in line = eligible royal-clan member (alive civ, not the king), ranked by the culture's succession rule (WB `getKingFromRoyalClan`).
def _resolve_heir(kingdom: dict, ctx: dict) -> dict | None:
    royal_clan = kingdom.get("royal_clan_id")
    if not royal_clan:
        return None
    king_id = kingdom.get("kingID")
    candidates = [a for a in ctx["actors_by_clan"].get(royal_clan, ()) if a.get("id") != king_id]
    if not candidates:
        return None
    traits = set((ctx["cultures_by_id"].get(kingdom.get("id_culture")) or {}).get("saved_traits") or [])
    stat = next((s for t, s in _ASCENSION_STATS.items() if t in traits), None)

    def score(actor: dict) -> float:
        if stat is not None:
            return compute_actor_stats(actor, ctx, ctx["subspecies_base_cache"]).get(stat, 0)
        if "golden_rule" in traits:
            return int(actor.get("money") or 0)
        if "fames_crown" in traits:
            return int(actor.get("renown") or 0)
        age = ctx["world_time"] - float(actor.get("created_time") or 0)
        return -age if "ultimogeniture" in traits else age  # `ultimogeniture` = youngest inherits, else eldest

    def preferred_sex(actor: dict) -> int:
        if "patriarchy" in traits:
            return 0 if actor.get("sex") == 1 else 1
        if "matriarchy" in traits:
            return 1 if actor.get("sex") == 1 else 0
        return 0

    # Rank desc: preferred sex, then succession score, then lowest id (WB's stable tie-break among equals).
    heir = max(candidates, key=lambda a: (preferred_sex(a), score(a), -a.get("id", 0)))
    return {"id": heir.get("id"), "name": heir.get("name") or f"#{heir.get('id')}"}


# Both sides of a war as id sets (main + listed, `None` dropped). Precompute once when scoring many kingdoms against the same wars.
def _war_sides(war: dict) -> tuple[set, set]:
    attackers = ({war.get("main_attacker")} | set(war.get("list_attackers") or [])) - {None}
    defenders = ({war.get("main_defender")} | set(war.get("list_defenders") or [])) - {None}
    return attackers, defenders


# WB `areKingdomsClose` via `City.nearbyBorders`: zone abutting zone, diagonals included. Dilated once, each rival is a set test, not an O(a × b) all-pairs scan.
def _zone_halo(zones: list[tuple[int, int]]) -> set[tuple[int, int]]:
    return {(x + dx, y + dy) for x, y in zones for dx in (-1, 0, 1) for dy in (-1, 0, 1)}


def main(argv: list[str]) -> int:
    save_path, argv, _ = take_chapter(argv)
    if not argv:
        print("usage: info.py <id> [sections] [C<n>] — see tools/tools.md", file=sys.stderr)
        return 2
    try:
        kingdom_id = int(argv[0])
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
    kingdom = index_by_id(save.get("kingdoms", [])).get(kingdom_id)
    if kingdom is None:
        print(f"unknown kingdom: {kingdom_id}", file=sys.stderr)
        return 1
    ctx = _build_context(save, save_path)

    out: dict = {}
    if "alliance" in sections:
        out["alliance"] = _build_alliance(kingdom, ctx, save)
    if "breakdown" in sections:
        out["breakdown"] = population_breakdown(ctx["actors_by_kingdom"].get(kingdom_id, []), ctx)
    if "cities" in sections:
        out["cities"] = _build_cities(kingdom, ctx)
    if "metadata" in sections:
        out["metadata"] = _build_metadata(kingdom, ctx, save)
    if "population" in sections:
        out["population"] = _build_population(kingdom, ctx)
    if "ranks" in sections:
        out["ranks"] = _compute_ranks(kingdom, ctx, save)
    if "relations" in sections:
        # Naming a section is asking for it in depth, so its opinions come with the full ledger; `full` sweeps everything and keeps the two-line summary.
        out["relations"] = _build_relations(kingdom, ctx, save, detailed=requested not in (None, "full"))
    if "wars" in sections:
        out["wars"] = _build_wars(kingdom, ctx, save)

    emit(out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
