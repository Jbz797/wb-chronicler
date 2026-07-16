#!/usr/bin/env python3

# User-facing docs (usage, available sections) live in `tools/tools.md`. Notes below are for maintainers — algorithm references, gotchas, source pointers.

import sys
from collections import Counter
from pathlib import Path


sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "actor"))
sys.path.insert(0, str(Path(__file__).parent.parent / "geography"))
from actor_stats import build_actor_stats_context, compute_actor_stats
from islands import compute_islands_cached

from shared import (
    CURRENT_SAVE,
    SICK_TRAITS,
    UNITS_PER_YEAR,
    age_thresholds,
    civic_building_ids,
    emit,
    index_by_id,
    life_stage,
    load_data,
    load_save,
    parse_sections,
    register_entity,
    resolve_profession,
)

_ADULT_AGE = 16  # WB's `age_adult` (uniform across civilized species): an actor is an adult at ≥ 16 in-game years.
_ALL_SECTIONS = ("alliance", "metadata", "population", "ranks", "relations", "wars")
_ASCENSION_STATS = {"diplomatic_ascension": "diplomacy", "warriors_ascension": "warfare"}  # Culture succession by that stat (else age/money/renown/sex).
_BABY_AGE_THRESHOLD_UNITS = _ADULT_AGE * UNITS_PER_YEAR  # WB considers actors non-adult below `age_adult` (expressed in world_time units).
_BORDERS_ZONE_DISTANCE = 3  # `areKingdomsClose` proxy: kingdoms are « close » if any pair of their zones are within this Manhattan distance.
_FAR_LANDS_CAPITAL_DISTANCE = 18  # `!isSameIsland` proxy: capitals further apart than this are treated as on different lands.
_FOOD_RESOURCES = frozenset(load_data("food-resources.json"))  # WB eatable resource ids (`initFood` + `initFoodRecipes`) — raw + cooked/drinks.
_HAPPY_MIN_HAPPINESS = 20  # WB `Actor.isHappy`: `getHappinessRatio ≥ 0.6` ⟺ raw happiness ≥ 20. (Emotionless non-civ actors also count — ignored.)

# WB `KingdomTraitLibrary`: a tax trait overrides the base rate (`Kingdom.recalcBaseStats`). Emitted as a tier — the rates themselves are WB's to change, the tier isn't.
_KINGDOM_TAX_TRAITS = {
    "tax_rate_local_high": ("tax_local", "high"),
    "tax_rate_local_low": ("tax_local", "low"),
    "tax_rate_tribute_high": ("tax_tribute", "high"),
    "tax_rate_tribute_low": ("tax_tribute", "low"),
}

_NON_FOOD_SPECIES = frozenset({"skeleton"})  # WB `needsFood`=false (undead have no diet ⇒ never hungry); excluded from `fed_pct`.
_OPINION_CONSTANTS = load_data("opinion-constants.json")
_REGISTRY = Path(__file__).parent.parent.parent / "saves" / "kingdoms.json"
_SATED_MIN_NUTRITION = 60  # `fed_pct` threshold: nutrition ratio ≥ 0.6 (like `tier-high`) — stricter than WB's own `isHungry` (≤ 50).
_SPECIES = load_data("species.json")  # asset_id → {stats, name, description}. Here for the French `name`; falls back to the asset_id.


# Alliance civ population per dimension: each one's top-3 shares (like `geography/islands.py`). Species = `asset_id` (icon) + French name; the rest a registry name.
def _alliance_breakdown(members: list[int], ctx: dict, save: dict) -> dict:
    species, cultures, languages, religions = Counter(), Counter(), Counter(), Counter()
    for m in members:
        for a in ctx["actors_by_kingdom"].get(m, []):  # boats already excluded when the context was built
            species[a.get("asset_id")] += 1
            for counter, field in ((cultures, "culture"), (languages, "language"), (religions, "religion")):
                if (v := a.get(field)) is not None:
                    counter[v] += 1

    def top3(counter: Counter, names: dict) -> list[dict]:
        total = sum(counter.values())
        return [
            {"name": (names.get(k) or {}).get("name") or f"#{k}", "pct": pct} for k, n in counter.most_common(3) if total and (pct := round(n / total * 100)) > 0
        ]

    species_total = sum(species.values())

    return {
        "cultures": top3(cultures, index_by_id(save.get("cultures", []))),
        "languages": top3(languages, index_by_id(save.get("languages", []))),
        "religions": top3(religions, index_by_id(save.get("religions", []))),
        "species": [  # Species carries `asset_id` (icon key) alongside the French `name`; the others need only their registry name.
            {"asset_id": k, "name": (_SPECIES.get(k) or {}).get("name") or k, "pct": pct}
            for k, n in species.most_common(3)
            if species_total and (pct := round(n / species_total * 100)) > 0
        ],
    }


# The kingdom's alliance and its other members (`None` if unaligned). `population`/`renown` sum the members (WB tracks neither), ranked top-3; `motto` often absent.
def _build_alliance(kingdom: dict, ctx: dict, save: dict) -> dict | None:
    kid = kingdom.get("id")
    alliance = next((a for a in save.get("alliances", []) if kid in (a.get("kingdoms") or [])), None)

    if alliance is None:
        return None

    kingdoms_by_id = {k["id"]: k for k in save.get("kingdoms", [])}
    populations = ctx["populations_by_kingdom"]

    def totals(members: list[int]) -> tuple[int, int]:
        return (sum(populations.get(m, 0) for m in members), sum(int((kingdoms_by_id.get(m) or {}).get("renown") or 0) for m in members))

    own = totals(alliance.get("kingdoms") or [])
    others = [totals(a.get("kingdoms") or []) for a in save.get("alliances", [])]
    ranks = {}
    for key, value, idx in (("population", own[0], 0), ("renown", own[1], 1)):
        if value:
            rank = sum(1 for o in others if o[idx] > value) + 1
            if rank <= 3:
                ranks[key] = rank

    return {
        "allies": sorted(
            ({"id": i, "name": kingdoms_by_id.get(i, {}).get("name") or f"#{i}"} for i in alliance.get("kingdoms") or [] if i != kid), key=lambda o: o["id"]
        ),
        "breakdown": _alliance_breakdown(alliance.get("kingdoms") or [], ctx, save),
        "motto": alliance.get("motto"),
        "name": alliance.get("name"),
        "population": own[0],
        "ranks": ranks,
        "renown": own[1],
    }


def _build_context(save: dict) -> dict:

    actors_by_clan: dict[int, list[dict]] = {}
    actors_by_id: dict[int, dict] = {}
    actors_by_kingdom: dict[int, list[dict]] = {}
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
    populations_by_kingdom: Counter[int] = Counter()  # Mirrors `Kingdom.getPopulation`; `boat_*` PNJs are transient. Nobles = kings (3) + leaders (4) + captains.
    renown_by_kingdom: Counter[int] = Counter()
    sick_by_kingdom: Counter[int] = Counter()
    subspecies_counts: dict[int, dict[int, int]] = {}
    warriors_by_kingdom: Counter[int] = Counter()

    for actor in save.get("actors_data", []):
        actors_by_id[actor["id"]] = actor
        kid = actor.get("civ_kingdom_id")
        if not kid or (actor.get("asset_id") or "").startswith("boat_"):
            continue
        actors_by_kingdom.setdefault(kid, []).append(actor)
        if clan_id := actor.get("clan"):
            actors_by_clan.setdefault(clan_id, []).append(actor)  # Heir lookup: a royal clan spans kingdoms, so `actors_by_kingdom` can't serve it.
        populations_by_kingdom[kid] += 1
        money_by_kingdom[kid] += int(actor.get("money") or 0)
        renown_by_kingdom[kid] += int(actor.get("renown") or 0)
        if actor.get("asset_id") not in _NON_FOOD_SPECIES:  # `needsFood`: undead (no diet) never count toward hunger
            eaters_by_kingdom[kid] += 1
            if int(actor.get("nutrition") or 0) >= _SATED_MIN_NUTRITION:
                fed_by_kingdom[kid] += 1
        if actor.get("profession") == 5:
            warriors_by_kingdom[kid] += 1
        if actor.get("profession") in (3, 4) or actor["id"] in captain_ids:
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
        if int(actor.get("happiness") or 0) >= _HAPPY_MIN_HAPPINESS:
            happy_by_kingdom[kid] += 1
        if not actor.get("homeBuildingID"):
            homeless_by_kingdom[kid] += 1
        if fid := actor.get("family"):
            families_by_kingdom.setdefault(kid, set()).add(fid)
        else:
            familyless_by_kingdom[kid] += 1
        sub_id = actor.get("subspecies")
        if sub_id is not None:
            subspecies_counts.setdefault(kid, {})
            subspecies_counts[kid][sub_id] = subspecies_counts[kid].get(sub_id, 0) + 1

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
        zones = city.get("zones") or []
        territory_by_kingdom[kid] = territory_by_kingdom.get(kid, 0) + len(zones)
        zones_by_kingdom.setdefault(kid, []).extend((z["x"], z["y"]) for z in zones)

    buildings_by_kingdom: Counter[int] = Counter()
    civic = civic_building_ids()  # Tallied per kingdom below (tile inside a city zone); `houses` = the dwelling subset.
    food_by_kingdom: Counter[int] = Counter()
    gold_by_kingdom: Counter[int] = Counter()
    goods_by_kingdom: Counter[int] = Counter()
    houses_by_kingdom: Counter[int] = Counter()
    zone_to_kingdom = {zone: kid for kid, zone_list in zones_by_kingdom.items() for zone in zone_list}

    for b in save.get("buildings", []):
        bx, by = b.get("mainX"), b.get("mainY")
        if bx is None or by is None:
            continue
        # Building-storage resources summed per city's kingdom: `food` (eatable, mirrors WB's `_current_total_food`), `gold` (ore), `goods` (other materials/gems).
        city = cities_by_id.get(b.get("cityID"))
        if city and (fkid := city.get("kingdomID")):
            for r in (b.get("resources") or {}).get("saved_resources") or []:
                rid = r.get("id")
                amount = r.get("amount", 0)
                if rid in _FOOD_RESOURCES:
                    food_by_kingdom[fkid] += amount
                elif rid == "gold":
                    gold_by_kingdom[fkid] += amount
                else:
                    goods_by_kingdom[fkid] += amount
        kid = zone_to_kingdom.get((bx // 8, by // 8))
        asset_id = b.get("asset_id")
        if kid is not None and asset_id in civic:
            buildings_by_kingdom[kid] += 1
            if asset_id.startswith("house"):
                houses_by_kingdom[kid] += 1

    capitals_by_kingdom = {k["id"]: cities_by_id[k["capitalID"]] for k in save.get("kingdoms", []) if k.get("capitalID") in cities_by_id}

    # Main subspecies = the most-counted one per kingdom (fallback used by `Kingdom.getMainSubspecies`).
    main_subspecies = {kid: max(counts.items(), key=lambda kv: kv[1])[0] for kid, counts in subspecies_counts.items()}

    # Supreme kingdom = the one with the largest adult population. WB picks the « most powerful » kingdom — population is the most consistent metric across screens.
    supreme_kingdom_id = max(populations_by_kingdom.items(), key=lambda kv: kv[1])[0] if populations_by_kingdom else None

    return {
        **build_actor_stats_context(save),
        "actors_by_clan": actors_by_clan,
        "actors_by_id": actors_by_id,
        "actors_by_kingdom": actors_by_kingdom,
        "buildings_by_kingdom": buildings_by_kingdom,
        "capitals_by_kingdom": capitals_by_kingdom,
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
        "main_subspecies": main_subspecies,
        "money_by_kingdom": money_by_kingdom,
        "nobles_by_kingdom": nobles_by_kingdom,
        "nobles_money_by_kingdom": nobles_money_by_kingdom,
        "populations_by_kingdom": populations_by_kingdom,
        "renown_by_kingdom": renown_by_kingdom,
        "sick_by_kingdom": sick_by_kingdom,
        "subspecies_base_cache": {},  # `compute_actor_stats` cache: heavy base computed once per subspecies, reused across actors (≈8×).
        "supreme_kingdom_id": supreme_kingdom_id,
        "territory_by_kingdom": territory_by_kingdom,
        "warriors_by_kingdom": warriors_by_kingdom,
        "world_age_id": save["mapStats"].get("world_age_id"),
        "zones_by_kingdom": zones_by_kingdom,
    }


def _build_metadata(kingdom: dict, ctx: dict, save: dict) -> dict:
    kid = kingdom.get("id")
    age_units = ctx["world_time"] - float(kingdom.get("created_time") or 0)
    _, island_lookup = compute_islands_cached(save, CURRENT_SAVE)

    # Chronicler-only: distinct island ids touched by the kingdom's city zones, sorted asc (1 = biggest). Zones are WB `TileZone`s of 8 tiles — probe centre.
    islands = sorted({iid for zx, zy in ctx["zones_by_kingdom"].get(kid, []) if (iid := island_lookup.get((zx * 8 + 4, zy * 8 + 4))) is not None})

    king_actor = ctx["actors_by_id"].get(kingdom.get("kingID"))  # Reigning king (`kingID`): `asset_id`+`sex` feed the UI `<app-person-tag>`. `None` at interregnum.
    king = None
    if king_actor:
        king = {
            "asset_id": king_actor.get("asset_id"),
            "id": king_actor.get("id"),
            "money": int(king_actor.get("money") or 0),  # His own purse: inside `population.money`, and netted out of `subjects_money` so both can be shown apart.
            "name": king_actor.get("name") or f"#{king_actor.get('id')}",
            "sex": "female" if king_actor.get("sex") == 1 else "male",
        }

    # Founder = first ruler (`past_rulers[0]`). Alive → live actor (may have abdicated/mutated); dead → name + founding species only, UI shows a tombstone.
    founder = None
    past_rulers = kingdom.get("past_rulers") or []
    if past_rulers:
        fid = past_rulers[0].get("id")
        founder_actor = ctx["actors_by_id"].get(fid)
        if founder_actor is not None:
            founder = {
                "asset_id": founder_actor.get("asset_id"),
                "dead": False,
                "id": fid,
                "name": founder_actor.get("name") or f"#{fid}",
                "profession": resolve_profession(founder_actor, save),
                "sex": "female" if founder_actor.get("sex") == 1 else "male",
            }
        else:
            founder = {"asset_id": kingdom.get("original_actor_asset"), "dead": True, "id": fid, "name": past_rulers[0].get("name") or f"#{fid}"}

    heir = _resolve_heir(kingdom, ctx, save)

    # Chronicler-only: what WB shows as « Hommage » (to the crown) and the local tax. `normal` = no tax trait, i.e. 15 of the 16 kingdoms here.
    taxes = {"tax_local": "normal", "tax_tribute": "normal"}
    for trait in kingdom.get("saved_traits") or []:
        if spec := _KINGDOM_TAX_TRAITS.get(trait):
            taxes[spec[0]] = spec[1]

    return {
        "age": int(age_units / UNITS_PER_YEAR),
        "buildings": ctx["buildings_by_kingdom"][kid],  # Civic buildings in the kingdom's zones (nature excluded); `houses` is the dwelling subset.
        "capital": (ctx["capitals_by_kingdom"].get(kid) or {}).get("name"),
        "cities": ctx["cities_by_kingdom"].get(kid, 0),
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
        "motto": kingdom.get("motto"),
        "name": kingdom.get("name"),
        "renown": kingdom.get("renown", 0),
        **taxes,
        "territory": ctx["territory_by_kingdom"].get(kid, 0),
        "wealth": ctx["money_by_kingdom"][kid] + ctx["gold_by_kingdom"][kid],  # Everything it owns: its people's coins + the gold in its buildings.
    }


# Age tiers from `life_stage`; `couples` = mutual lovers; `nobles` = kings + leaders + captains; `sick`/`infected` from WB `calculateIsSick` (`infected` ⊂ `sick`).
def _build_population(kingdom: dict, ctx: dict) -> dict:
    kid = kingdom.get("id")

    actors = ctx["actors_by_kingdom"].get(kid, [])
    by_id = ctx["actors_by_id"]
    ids = {a["id"] for a in actors}
    men = couples = 0
    paired: set[int] = set()
    stages: Counter[str] = Counter()
    world_time = ctx["world_time"]

    for a in actors:
        age = int((world_time - float(a.get("created_time") or 0)) / UNITS_PER_YEAR) + (a.get("age_overgrowth") or 0)
        lifespan = compute_actor_stats(a, ctx, ctx["subspecies_base_cache"]).get("lifespan", 0)
        stages[life_stage(age, age_thresholds(lifespan)[0], lifespan)] += 1
        if a.get("sex") != 1:
            men += 1
        lover = a.get("lover")
        if lover in ids and a["id"] not in paired and by_id.get(lover, {}).get("lover") == a["id"]:
            couples += 1
            paired.update((a["id"], lover))
    total = len(actors)

    eaters = ctx["eaters_by_kingdom"][kid]  # food-needing pop (undead excluded); denominator for `fed_pct`
    king_money = int((by_id.get(kingdom.get("kingID")) or {}).get("money") or 0)  # Netted out of `subjects_money`; the value itself rides in `metadata.king`.

    # `immortals`/`infected`/`sick` omitted when 0 (UI-gated on > 0; absence = none). The rest always emitted — an explicit 0 is a meaningful demographic signal.
    immortals = ctx["immortals_by_kingdom"][kid]
    infected = ctx["infected_by_kingdom"][kid]
    sick = ctx["sick_by_kingdom"][kid]

    return {
        "adults": stages["adult"],
        "babies": stages["baby"],
        "children": stages["child"],
        "couples": couples,
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
def _build_relations(kingdom: dict, ctx: dict, save: dict) -> list[dict]:
    kid = kingdom.get("id")
    alliances = save.get("alliances", [])
    ongoing_wars = [w for w in save.get("wars", []) if not w.get("winner")]
    war_sides = [_war_sides(w) for w in ongoing_wars]  # Built once, reused by `is_enemy` + every `_compute_opinion` below.

    # Other kingdom is an ally if both share an alliance.
    def is_ally(other_id: int) -> bool:
        return any(kid in (a.get("kingdoms") or []) and other_id in (a.get("kingdoms") or []) for a in alliances)

    # Other kingdom is an enemy when it stands on the opposite side of an ongoing war.
    def is_enemy(other_id: int) -> bool:
        return any((kid in att and other_id in dfd) or (kid in dfd and other_id in att) for att, dfd in war_sides)

    # `save.relations` only persists pairs WB tracked, yet WB scores every kingdom regardless — hence the loop over all below and the `r or {}` fallbacks.
    relations_by_other = {
        (r.get("kingdom2_id") if r.get("kingdom1_id") == kid else r.get("kingdom1_id")): r
        for r in save.get("relations", [])
        if kid in (r.get("kingdom1_id"), r.get("kingdom2_id"))
    }

    kid_zones = ctx["zones_by_kingdom"].get(kid, [])
    out = []
    for other in save.get("kingdoms", []):
        other_id = other.get("id")
        if other_id == kid:
            continue
        _register_kingdom(other, ctx)
        r = relations_by_other.get(other_id)
        status = "ally" if is_ally(other_id) else "enemy" if is_enemy(other_id) else "neutral"
        last_war_end = (r or {}).get("timestamp_last_war_ended")
        borders = _zones_within(kid_zones, ctx["zones_by_kingdom"].get(other_id, []), _BORDERS_ZONE_DISTANCE)
        out.append(
            {
                "age_years": int((ctx["world_time"] - float((r or {}).get("created_time") or 0)) / UNITS_PER_YEAR) if r else None,
                **({"borders": True} if borders else {}),  # Chronicler-only, omitted when False: absence = kingdoms don't share a border.
                "kingdom": {"id": other_id, "name": other.get("name") or f"#{other_id}"},
                "opinion": _compute_opinion(kingdom, other, save, ctx, alliances, war_sides, r),
                "status": status,
                "years_since_last_war": int((ctx["world_time"] - float(last_war_end)) / UNITS_PER_YEAR) if last_war_end else None,
            }
        )
    return sorted(out, key=lambda x: x["kingdom"]["id"])


# Ongoing wars involving this kingdom (as attacker or defender). Concluded wars are skipped (`winner` is set when a war ends).
def _build_wars(kingdom: dict, ctx: dict, save: dict) -> list[dict]:
    kid = kingdom.get("id")
    kingdoms_by_id = index_by_id(save.get("kingdoms", []))
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
        starter_kingdom = kingdoms_by_id.get(w.get("started_by_kingdom_id"))

        # Register opposing/ally kingdoms (and the war's instigator) so the UI's `app-kingdom-tag` can resolve their banner + colours.
        for k in [*opponent_kingdoms, *ally_kingdoms, *([starter_kingdom] if starter_kingdom else [])]:
            _register_kingdom(k, ctx)
        duration_units = ctx["world_time"] - float(w.get("created_time") or 0)

        out.append(
            {
                "allies": sorted(
                    ({"id": a["id"], "name": a.get("name") or f"#{a['id']}"} for a in ally_kingdoms),
                    key=lambda o: o["id"],
                ),
                "attacker_alliance": alliance_for(w.get("main_attacker"), w.get("list_attackers") or []),
                "cities": {
                    "attackers": sum(cities.get(aid, 0) for aid in attackers),
                    "defenders": sum(cities.get(did, 0) for did in defenders),
                },
                "deaths": {
                    "attackers": w.get("dead_attackers", 0),
                    "defenders": w.get("dead_defenders", 0),
                },
                "defender_alliance": alliance_for(w.get("main_defender"), w.get("list_defenders") or []),
                "duration_years": int(duration_units / UNITS_PER_YEAR),
                "id": w.get("id"),
                **({"is_main": True} if kid == w.get(f"main_{side}") else {}),  # Omitted when False (absence = secondary ally, not this side's leader).
                "name": w.get("name"),
                "opponents": sorted(
                    ({"id": opp["id"], "name": opp.get("name") or f"#{opp['id']}"} for opp in opponent_kingdoms),
                    key=lambda o: o["id"],
                ),
                "populations": {
                    "attackers": sum(populations.get(aid, 0) for aid in attackers),
                    "defenders": sum(populations.get(did, 0) for did in defenders),
                },
                "renown_at_stake": w.get("renown", 0),
                "side": side,
                "started_by": {
                    "actor_id": w.get("started_by_actor_id"),
                    "kingdom": {
                        "id": w.get("started_by_kingdom_id"),
                        "name": w.get("started_by_kingdom_name"),
                    },
                },
                "war_type": w.get("war_type"),
                "warriors": {
                    "attackers": sum(warriors.get(aid, 0) for aid in attackers),
                    "defenders": sum(warriors.get(did, 0) for did in defenders),
                },
            }
        )
    return sorted(out, key=lambda x: x["id"])


# Centroid of a city's zone tiles (cities don't carry a centre field — averaged from `zones`).
def _city_centroid(city: dict | None) -> tuple[float, float] | None:
    if not city:
        return None
    zones = city.get("zones") or []
    if not zones:
        return None
    return (sum(z["x"] for z in zones) / len(zones), sum(z["y"] for z in zones) / len(zones))


# Reconstructs `Actor.stats["diplomacy"]` via the full `actor_stats` pipeline (species + chromosome tiers + traits + equipment + custom_data_float + multipliers + level scaling).
def _compute_king_diplomacy(king: dict, ctx: dict) -> int:
    return int(compute_actor_stats(king, ctx, ctx["subspecies_base_cache"]).get("diplomacy", 0))


# Mirror `DiplomacyRelation.recalculate` IL: each numbered modifier = a WB `OpinionAsset`. Runtime stats reconstructed via `actor_stats.compute_actor_stats`.
def _compute_opinion(main: dict, target: dict, save: dict, ctx: dict, alliances: list, war_sides: list, relation: dict | None) -> dict:
    mod: dict[str, int] = {}
    mid, tid = main["id"], target["id"]

    main_king = ctx["actors_by_id"].get(main.get("kingID"))
    target_king = ctx["actors_by_id"].get(target.get("kingID"))
    main_pos = _city_centroid(ctx["capitals_by_kingdom"].get(mid))
    target_pos = _city_centroid(ctx["capitals_by_kingdom"].get(tid))
    main_zones = ctx["zones_by_kingdom"].get(mid, [])
    target_zones = ctx["zones_by_kingdom"].get(tid, [])

    def is_enemy() -> bool:
        return any((mid in att and tid in dfd) or (mid in dfd and tid in att) for att, dfd in war_sides)

    def is_in_war_on_same_side() -> bool:
        return any((mid in att and tid in att) or (mid in dfd and tid in dfd) for att, dfd in war_sides)

    enemy = is_enemy()

    # 1. king: target's king's diplomacy stat. Stats are runtime-only in WB, so we reconstruct: species base + trait bonuses + level/2 (level scaling is empirical from screen calibration).
    if target_king:
        mod["king"] = _compute_king_diplomacy(target_king, ctx)

    # 2. kings_mood: main's king's runtime mood — not serialised. Skipped.

    # 3. is_supreme: -100 if target is the « most powerful » kingdom (= largest adult population) and world has ≥3 kingdoms.
    if tid == ctx.get("supreme_kingdom_id") and len(save.get("kingdoms") or []) >= 3:
        mod["is_supreme"] = -100

    # 4. borders: ±25. WB checks `areKingdomsClose` (any city pair within adjacency threshold). Proxy: any zone pair within _BORDERS_ZONE_DISTANCE (Manhattan).
    close = _zones_within(main_zones, target_zones, _BORDERS_ZONE_DISTANCE)
    mod["borders"] = -25 if close else 25

    # 5. far_lands: +60 if not « close » and both capitals exist and are « on different islands ». Proxy: capital Manhattan distance > _FAR_LANDS_CAPITAL_DISTANCE.
    if not close and main_pos and target_pos and (abs(main_pos[0] - target_pos[0]) + abs(main_pos[1] - target_pos[1])) > _FAR_LANDS_CAPITAL_DISTANCE:
        mod["far_lands"] = 60

    # 6. in_war: -500 if currently fighting.
    if enemy:
        mod["in_war"] = -500

    # 7. same_wars: +50 if on same side in any ongoing war (and NOT enemies).
    if not enemy and is_in_war_on_same_side():
        mod["same_wars"] = 50

    # 8. species: ±15/-10 if both kings exist and main « can have prejudice » (assumed true).
    if main_king and target_king:
        main_sp = (ctx["subspecies_by_id"].get(main_king.get("subspecies")) or {}).get("species_id")
        target_sp = (ctx["subspecies_by_id"].get(target_king.get("subspecies")) or {}).get("species_id")
        if main_sp and target_sp:
            mod["species"] = 15 if main_sp == target_sp else -10

    # 9. zones: clamp((main_zones − target_zones) / 5, -20, 0). Negative when we own more territory than them. WB uses C# int division (truncate toward 0), not Python floor.
    diff = ctx["territory_by_kingdom"].get(mid, 0) - ctx["territory_by_kingdom"].get(tid, 0)
    zones_val = min(0, max(-20, int(diff / 5)))
    if zones_val:
        mod["zones"] = zones_val

    # 10. peace_time: years since last war > minimum_years_between_wars → min(years, 20). WB treats absent `timestamp_last_war_ended` as 0 (= « forever ago »).
    last_war_end = float(relation.get("timestamp_last_war_ended") or 0) if relation else None
    years_since = (ctx["world_time"] - last_war_end) / UNITS_PER_YEAR if last_war_end is not None else None
    minimum_years = _OPINION_CONSTANTS.get("minimum_years_between_wars", 5)
    if not enemy and years_since is not None and years_since > minimum_years:
        mod["peace_time"] = min(int(years_since), 20)

    # 11. power: max(0, (target_power − main_power) / 10) where power = countCities * 5 + getPopulationPeople() (adults, boats excluded).
    def power_of(k: dict) -> int:
        return ctx["cities_by_kingdom"].get(k["id"], 0) * 5 + ctx["populations_by_kingdom"].get(k["id"], 0)

    power_diff = power_of(target) - power_of(main)
    if power_diff > 0:
        mod["power"] = power_diff // 10

    # 12. traits: per target.king trait — +same_trait_mod if main.king has same, +opposite_trait_mod if main.king has opposite.
    if main_king and target_king:
        traits_total = 0
        main_traits = set(main_king.get("saved_traits") or [])
        for t in target_king.get("saved_traits") or []:
            spec = _OPINION_CONSTANTS["actor_trait_opinion_mods"].get(t)
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

    # 16. subspecies: ±10. WB calc fires when SPECIES DIFFER (subspecies = secondary distinction), main has king + canHavePrejudice.
    if main_king and target_king:
        main_sp = (ctx["subspecies_by_id"].get(main_king.get("subspecies")) or {}).get("species_id")
        target_sp = (ctx["subspecies_by_id"].get(target_king.get("subspecies")) or {}).get("species_id")
        if main_sp and target_sp and main_sp != target_sp:
            main_sub = main_king.get("subspecies")
            target_sub = target_king.get("subspecies")
            if main_sub is not None and target_sub is not None:
                mod["subspecies"] = 10 if main_sub == target_sub else -10

    # 17. clan: ±40 if both kings exist, same species, both have clan.
    if mod.get("species") == 15:
        main_clan = main.get("royal_clan_id")
        target_clan = target.get("royal_clan_id")
        if main_clan and target_clan:
            mod["clan"] = 40 if main_clan == target_clan else -40

    # 18. in_alliance: +30 if same alliance.
    main_alliance = next((a for a in alliances if mid in (a.get("kingdoms") or [])), None)
    target_alliance = next((a for a in alliances if tid in (a.get("kingdoms") or [])), None)
    if main_alliance and target_alliance and main_alliance["id"] == target_alliance["id"]:
        mod["in_alliance"] = 30

    # 19. truce: +100 if not enemy, has a recent relation with last_war_ended within minimum_years.
    if not enemy and years_since is not None and years_since <= minimum_years:
        mod["truce"] = 100

    # 20. world_era: bonus_opinion of the current world age.
    era = ctx.get("world_age_id")
    era_bonus = _OPINION_CONSTANTS.get("world_age_bonus_opinion", {}).get(era)
    if era_bonus:
        mod["world_era"] = era_bonus

    # 21. baby_king: -50 if main's king not baby, target's king IS baby. WB « baby » threshold ≈ 16y.
    if main_king and target_king:
        main_age = ctx["world_time"] - float(main_king.get("created_time") or 0)
        target_age = ctx["world_time"] - float(target_king.get("created_time") or 0)
        if main_age >= _BABY_AGE_THRESHOLD_UNITS and target_age < _BABY_AGE_THRESHOLD_UNITS:
            mod["baby_king"] = -50

    # 22-24. ethnocentric_guard / xenophobic / xenophiles: need main.culture.saved_traits. Check below.
    culture_traits = set((ctx["cultures_by_id"].get(main.get("id_culture")) or {}).get("saved_traits") or [])
    same_species = mod.get("species") == 15
    if "ethnocentric_guard" in culture_traits and not same_species and main.get("id_culture") != target.get("id_culture"):
        mod["ethnocentric_guard"] = -50
    if "xenophobic" in culture_traits and not same_species:
        mod["xenophobic"] = -50
    if "xenophiles" in culture_traits and same_species:
        mod["xenophiles"] = 20

    # Chronicler-only: top + and top - drivers — the « pourquoi » is enough, full ledger bloats tokens.
    non_zero = [(k, v) for k, v in mod.items() if v]
    top_pos = max((kv for kv in non_zero if kv[1] > 0), key=lambda kv: kv[1], default=None)
    top_neg = min((kv for kv in non_zero if kv[1] < 0), key=lambda kv: kv[1], default=None)
    drivers = dict(sorted([kv for kv in (top_pos, top_neg) if kv is not None]))
    return {"drivers": drivers, "total": sum(mod.values())}


# Standard competition rank (1,2,2,4) per stat among all kingdoms. Top 3 only — UI hides the rest.
def _compute_ranks(kingdom: dict, ctx: dict, save: dict) -> dict:
    kingdoms = save.get("kingdoms", [])

    buildings = ctx["buildings_by_kingdom"]
    cities = ctx["cities_by_kingdom"]
    eaters = ctx["eaters_by_kingdom"]
    fed = ctx["fed_by_kingdom"]
    food = ctx["food_by_kingdom"]
    gold = ctx["gold_by_kingdom"]
    goods = ctx["goods_by_kingdom"]
    homeless = ctx["homeless_by_kingdom"]
    houses = ctx["houses_by_kingdom"]
    immortals = ctx["immortals_by_kingdom"]
    infected = ctx["infected_by_kingdom"]
    money = ctx["money_by_kingdom"]
    nobles = ctx["nobles_by_kingdom"]
    nobles_money = ctx["nobles_money_by_kingdom"]
    populations = ctx["populations_by_kingdom"]
    renown_total = ctx["renown_by_kingdom"]
    sick = ctx["sick_by_kingdom"]
    territory = ctx["territory_by_kingdom"]
    warriors = ctx["warriors_by_kingdom"]

    def fed_ratio(k: dict) -> float:
        eat = eaters.get(k.get("id"), 0)
        return fed.get(k.get("id"), 0) / eat if eat else 0.0

    def food_per_capita(k: dict) -> float:
        pop = populations.get(k.get("id"), 0)
        return food.get(k.get("id"), 0) / pop if pop else 0.0

    def housed_ratio(k: dict) -> float:
        pop = populations.get(k.get("id"), 0)
        return (pop - homeless.get(k.get("id"), 0)) / pop if pop else 0.0

    def king_money(k: dict) -> int:
        return int((ctx["actors_by_id"].get(k.get("kingID")) or {}).get("money") or 0)

    def kingdom_age(k: dict) -> int:
        return int((ctx["world_time"] - float(k.get("created_time") or 0)) / UNITS_PER_YEAR)

    def subjects_money(k: dict) -> int:
        return money.get(k.get("id"), 0) - king_money(k) - nobles_money.get(k.get("id"), 0)

    def wealth_per_capita(k: dict) -> float:
        pop = populations.get(k.get("id"), 0)
        return (money.get(k.get("id"), 0) + gold.get(k.get("id"), 0)) / pop if pop else 0.0

    getters = {
        "age": kingdom_age,
        "buildings": lambda k: buildings.get(k.get("id"), 0),
        "cities": lambda k: cities.get(k.get("id"), 0),
        "deaths": lambda k: k.get("total_deaths", 0),
        "fed_pct": fed_ratio,
        "food": lambda k: food.get(k.get("id"), 0),
        "food_per_capita": food_per_capita,
        "gold": lambda k: gold.get(k.get("id"), 0),
        "goods": lambda k: goods.get(k.get("id"), 0),
        "housed_pct": housed_ratio,
        "houses": lambda k: houses.get(k.get("id"), 0),
        "immortals": lambda k: immortals.get(k.get("id"), 0),
        "infected": lambda k: infected.get(k.get("id"), 0),
        "kills": lambda k: k.get("total_kills", 0),
        "king_money": king_money,
        "money": lambda k: money.get(k.get("id"), 0),
        "nobles": lambda k: nobles.get(k.get("id"), 0),
        "nobles_money": lambda k: nobles_money.get(k.get("id"), 0),
        "population": lambda k: populations.get(k.get("id"), 0),
        "renown": lambda k: k.get("renown", 0),
        "renown_total": lambda k: renown_total.get(k.get("id"), 0),
        "sick": lambda k: sick.get(k.get("id"), 0),
        "subjects_money": subjects_money,
        "territory": lambda k: territory.get(k.get("id"), 0),
        "warriors": lambda k: warriors.get(k.get("id"), 0),
        "wealth": lambda k: money.get(k.get("id"), 0) + gold.get(k.get("id"), 0),
        "wealth_per_capita": wealth_per_capita,
    }
    ranks = {}
    for stat, getter in sorted(getters.items()):
        own = getter(kingdom)
        # No podium for a metric the kingdom has none of (avoids a meaningless « rank 1 » when every kingdom sits at 0).
        if own == 0:
            continue
        rank = sum(1 for k in kingdoms if getter(k) > own) + 1
        if rank <= 3:
            ranks[stat] = rank
    return ranks


# Relative luminance (WCAG) of a "#RRGGBB" colour — used to pick the darkest / lightest of a palette.
def _luminance(color: str) -> float:
    channels = [int(color[i : i + 2], 16) / 255 for i in (1, 3, 5)]
    linear = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


# Upsert reader registry with per-kingdom visuals (icon + colours). Display name comes from the caller (markdown token or chapter.json), not stored here.
def _register_kingdom(kingdom: dict, ctx: dict) -> None:
    # Background = darkest of colour's 4 game hues, ink (icon/text/border) = lightest — max contrast within kingdom's real palette (colors-all.json).
    palette = [h for h in load_data("colors-all.json").get(str(kingdom.get("color_id", "")), {}).values() if h]
    register_entity(
        _REGISTRY,
        str(kingdom.get("id")),
        {
            "banner_icon": _resolve_banner_sprite(kingdom, ctx),
            "color": min(palette, key=_luminance) if palette else None,
            "ink": max(palette, key=_luminance) if palette else None,
        },
    )


# Mirrors `Kingdom.getElementIcon`: index `banner_icon_id` (null → 0, out-of-range → 0) into the king's species banner set (founder species if no living king).
# CLAUDE: `banner-icons.json` is generated from *BannerLibrary assets, covers every species — don't hand-patch, regenerate from game files for new species.
def _resolve_banner_sprite(kingdom: dict, ctx: dict) -> int:
    king = ctx["actors_by_id"].get(kingdom.get("kingID"))
    subspecies = ctx["subspecies_by_id"].get(king.get("subspecies")) if king else None
    species = (subspecies or {}).get("species_id") or kingdom.get("original_actor_asset")
    banners = load_data("banner-icons.json")
    icons = banners["banner_id_icons"][banners["species_to_banner_id"][species]]
    index = kingdom.get("banner_icon_id") or 0
    return icons[index if index < len(icons) else 0]


# Next in line = eligible royal-clan member (alive civ, not the king), ranked by the culture's succession rule (WB `getKingFromRoyalClan`).
def _resolve_heir(kingdom: dict, ctx: dict, save: dict) -> dict | None:
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
    return {
        "asset_id": heir.get("asset_id"),
        "id": heir.get("id"),
        "name": heir.get("name") or f"#{heir.get('id')}",
        "profession": resolve_profession(heir, save),
        "sex": "female" if heir.get("sex") == 1 else "male",
    }


# Both sides of a war as id sets (main + listed, `None` dropped). Precompute once when scoring many kingdoms against the same wars.
def _war_sides(war: dict) -> tuple[set, set]:
    attackers = ({war.get("main_attacker")} | set(war.get("list_attackers") or [])) - {None}
    defenders = ({war.get("main_defender")} | set(war.get("list_defenders") or [])) - {None}
    return attackers, defenders


# True if any zone pair is within `max_distance` (Manhattan). Set-probe the distance diamond + early-exit — avoids the O(len_a × len_b) all-pairs min.
def _zones_within(zones_a: list[tuple[int, int]], zones_b: list[tuple[int, int]], max_distance: int) -> bool:
    if not zones_a or not zones_b:
        return False
    if len(zones_a) > len(zones_b):
        zones_a, zones_b = zones_b, zones_a
    b_set = set(zones_b)
    for ax, ay in zones_a:
        for dx in range(-max_distance, max_distance + 1):
            reach = max_distance - abs(dx)
            if any((ax + dx, ay + dy) in b_set for dy in range(-reach, reach + 1)):
                return True
    return False


def main(argv: list[str]) -> int:
    if not argv:
        print("usage: info.py <id> [sections] — see tools/tools.md", file=sys.stderr)
        return 2
    try:
        kingdom_id = int(argv[0])
    except ValueError:
        print(f"invalid id: {argv[0]}", file=sys.stderr)
        return 1
    try:
        sections = parse_sections(argv[1] if len(argv) > 1 else None, _ALL_SECTIONS)
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 2
    save = load_save()
    kingdom = index_by_id(save.get("kingdoms", [])).get(kingdom_id)
    if kingdom is None:
        print(f"unknown kingdom: {kingdom_id}", file=sys.stderr)
        return 1
    ctx = _build_context(save)
    _register_kingdom(kingdom, ctx)

    out: dict = {}
    if "alliance" in sections:
        out["alliance"] = _build_alliance(kingdom, ctx, save)
    if "metadata" in sections:
        out["metadata"] = _build_metadata(kingdom, ctx, save)
    if "population" in sections:
        out["population"] = _build_population(kingdom, ctx)
    if "ranks" in sections:
        out["ranks"] = _compute_ranks(kingdom, ctx, save)
    if "relations" in sections:
        out["relations"] = _build_relations(kingdom, ctx, save)
    if "wars" in sections:
        out["wars"] = _build_wars(kingdom, ctx, save)

    emit(out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
