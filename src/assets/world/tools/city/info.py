#!/usr/bin/env python3

# User-facing docs (usage, sections) live in `tools/tools.md`. A city is a kingdom's constituent settlement — its own culture/religion/language, leader and founder.
# Notes below are for maintainers. Mirrors `kingdom/info.py` one tier down: per-city aggregates instead of per-kingdom; no diplomacy (relations/wars/alliance).

import sys
from collections import Counter, defaultdict
from functools import cache
from operator import itemgetter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))

from actor_stats import actor_stat_totals, build_actor_stats_context, meta_ratios, settlement_population
from islands import compute_islands_cached
from shared import (
    EQUIPMENT_RACKS,
    NON_FOOD_SPECIES,
    PROFESSION_KING,
    PROFESSION_LEADER,
    PROFESSION_WARRIOR,
    SATED_MIN_NUTRITION,
    SICK_TRAITS,
    UNITS_PER_YEAR,
    ZONE_TILES,
    asset_set,
    besieging_kingdoms,
    books_held,
    children_by_id,
    city_score_dimensions,
    city_score_ranks,
    civic_building_ids,
    competition_ranks,
    emit,
    entity_age,
    entity_ref,
    equipment_entry,
    index_by_id,
    light,
    load_data,
    load_save,
    meta_report,
    parse_sections,
    population_breakdown,
    settlement_leaders,
    settlement_rank_getters,
    sex_label,
    succession_heir,
    take_chapter,
    wants_detail,
)

_ALL_SECTIONS = ("army", "books", "breakdown", "equipment", "identity", "inventory", "leaders", "loyalty", "metadata", "population", "ranks")

# WB `Kingdom.recalcBaseStats`: a tax trait overrides the crown's base rate. Emitted as a tier — the rates are WB's to change, the tier isn't.
_CITY_TAX_TRAITS = {
    "tax_rate_local_high": ("tax_local", "high"),
    "tax_rate_local_low": ("tax_local", "low"),
    "tax_rate_tribute_high": ("tax_tribute", "high"),
    "tax_rate_tribute_low": ("tax_tribute", "low"),
}


_CIV_BASE_CITIES = {"dwarf": 3, "elf": 3, "orc": 4}  # WB `ActorAsset.civ_base_cities`; every other civ keeps the `$civ_unit$` template's 5.
_ERA_LOYALTY = {"age_chaos": -10, "age_dark": -5, "age_hope": 15, "age_moon": -25, "age_sun": 5, "age_tears": -55}  # `WorldAgeAsset.bonus_loyalty`
_LOYALTY_WAVES = 30  # WB gives up after this many BFS waves when walking a kingdom's city graph looking for the capital.
_RANGED_ATTACKS = asset_set("ranged")  # WB `attack_type != 0`: every asset cloned from the `$range` template (`ItemLibrary`).
_TRAIT_MODS = load_data("opinion-constants.json")["actor_trait_opinion_mods"]  # `ActorTrait.same_trait_mod`/`opposite_trait_mod` — the kingdom reads it too.


# Untruncated on purpose — loyalty adds stats together before casting, exactly as WB does. See `actor_stat_totals`.
def _actor_stats(actor: dict | None, ctx: dict) -> dict:
    if actor is None:
        return {}
    cache, actor_id = ctx["stats_cache"], actor["id"]
    if actor_id not in cache:
        cache[actor_id] = actor_stat_totals(actor, ctx, ctx["subspecies_base_cache"])
    return cache[actor_id]


# The city's standing army — at most one, residents only, `None` where there is none. `captain_years`, `kills_per_death` and `total_captains` stay chronicler-only.
def _build_army(city: dict, ctx: dict) -> dict | None:
    army = ctx["armies_by_city"].get(city["id"])
    if army is None:
        return None
    cid, past = city["id"], army.get("past_captains") or []
    deaths, kills = int(army.get("total_deaths") or 0), int(army.get("total_kills") or 0)
    # The sitting captain's own term: WB appends them to `past_captains` on taking office and only stamps `timestamp_end` when they leave.
    reign = next((float(c["timestamp_ago"]) for c in reversed(past) if c.get("timestamp_end") is None and c.get("timestamp_ago") is not None), None)
    return {
        "age": entity_age(army, ctx["world_time"]),
        "captain": entity_ref(army.get("id_captain"), ctx["actors_by_id"]),
        **({"captain_years": _years_since(reign, ctx)} if reign is not None else {}),
        "deaths": deaths,
        "kills": kills,
        "kills_per_death": round(kills / deaths, 1) if deaths else float(kills),
        "melee": ctx["melee_by_city"][cid],
        "money": ctx["troop_money_by_city"][cid],
        "name": army.get("name"),
        "ranged": ctx["ranged_by_city"][cid],
        "renown": int(army.get("renown") or 0),
        "total_captains": len(past),  # every captain since the founding, the sitting one included — a succession count, never a headcount
    }


# The city's library: volumes on its shelves, whoever wrote them. `total` is the ranked stat, the section lists the titles, `book/info.py <id>` spells one out.
def _build_books(city: dict, ctx: dict, requested: str | None) -> dict:
    total = ctx["books_by_city"]()[city["id"]]
    if not wants_detail(requested, total):  # `full` keeps the chapter light — one count, the titles themselves only when the section is asked for by name
        return light({"total": total}, "books")
    return {"held": [{"id": b["id"], "name": b.get("name")} for b in ctx["shelved_by_city"]().get(city["id"], ())], "total": total}


# One pass over actors then buildings — every per-city tally the sections need, so no section rescans the save. Built whole whatever was asked for.
def _build_context(save: dict, save_path: Path) -> dict:
    captain_ids = {cap for army in save.get("armies") or [] if (cap := army.get("id_captain"))}  # Captains have no `profession` value, but they rank as nobles.

    actors_by_city: dict[int, list[dict]] = {}
    actors_by_army: dict[int, list[dict]] = {}
    actors_by_id: dict[int, dict] = {}
    eaters_by_city: Counter[int] = Counter()
    families_by_city: dict[int, set[int]] = {}
    fed_by_city: Counter[int] = Counter()
    homeless_by_city: Counter[int] = Counter()
    immortals_by_city: Counter[int] = Counter()
    infected_by_city: Counter[int] = Counter()
    inventory_by_city: defaultdict[int, Counter[str]] = defaultdict(Counter)
    leader_ids = {lid for c in save.get("cities") or [] if (lid := c.get("leaderID"))}  # Sitting mayors: nobles too, but their purse is reported on its own.
    melee_by_city: Counter[int] = Counter()
    money_by_city: Counter[int] = Counter()
    nobles_by_city: Counter[int] = Counter()
    nobles_money_by_city: Counter[int] = Counter()
    populations_by_city: Counter[int] = Counter()
    ranged_by_city: Counter[int] = Counter()
    renown_by_city: Counter[int] = Counter()
    sick_by_city: Counter[int] = Counter()
    troop_money_by_city: Counter[int] = Counter()
    warriors_by_city: Counter[int] = Counter()

    items_by_id = index_by_id(save.get("items") or [])

    for actor in save.get("actors_data") or []:
        actor_id = actor["id"]
        actors_by_id[actor_id] = actor
        cid = actor.get("cityID")
        asset_id = actor.get("asset_id") or ""  # read once, as the purse is below: the boat guard and the hunger tally both want it
        if not cid or asset_id.startswith("boat_"):  # `is_boat` inlined — it would re-read the field we already hold
            continue
        actors_by_city.setdefault(cid, []).append(actor)
        populations_by_city[cid] += 1
        # Read once (three tallies want the purse) and guarded: renown is zero on most inhabitants, and a `+= 0` still costs a hash and a store.
        coins = actor.get("money")
        if coins:
            money_by_city[cid] += int(coins)
        if renown := actor.get("renown"):
            renown_by_city[cid] += int(renown)
        if asset_id not in NON_FOOD_SPECIES:  # `needsFood`: undead (no diet) never count toward hunger
            eaters_by_city[cid] += 1
            if int(actor.get("nutrition") or 0) >= SATED_MIN_NUTRITION:
                fed_by_city[cid] += 1

        profession = actor.get("profession")
        # WB enlists only in the resident's own city, so `cityID` keys the army. `Army.countMelee`: ranged needs a `$range` weapon — carrying none counts as melee.
        if army_id := actor.get("army"):
            actors_by_army.setdefault(army_id, []).append(actor)
            if coins:
                troop_money_by_city[cid] += int(coins)
            if any((items_by_id.get(i) or {}).get("asset_id") in _RANGED_ATTACKS for i in actor.get("saved_items") or []):
                ranged_by_city[cid] += 1
            else:
                melee_by_city[cid] += 1
        if profession == PROFESSION_WARRIOR:
            warriors_by_city[cid] += 1
        if profession in (PROFESSION_KING, PROFESSION_LEADER) or actor_id in captain_ids:  # king (the capital's), leader, or captain
            nobles_by_city[cid] += 1
            if coins and actor_id not in leader_ids:
                nobles_money_by_city[cid] += int(coins)

        traits = actor.get("saved_traits") or []
        if "infected" in traits:
            infected_by_city[cid] += 1
        if not SICK_TRAITS.isdisjoint(traits):
            sick_by_city[cid] += 1
        if "immortal" in traits:
            immortals_by_city[cid] += 1
        if not actor.get("homeBuildingID"):
            homeless_by_city[cid] += 1
        if family_id := actor.get("family"):
            families_by_city.setdefault(cid, set()).add(family_id)

    buildings_by_city: Counter[int] = Counter()
    civic = civic_building_ids()  # `houses` = the dwelling subset.
    food_ids = asset_set("food")
    food_by_city: Counter[int] = Counter()
    gold_by_city: Counter[int] = Counter()
    goods_by_city: Counter[int] = Counter()
    houses_by_city: Counter[int] = Counter()

    for b in save.get("buildings") or []:
        cid = b.get("cityID")
        if not cid:
            continue
        if stock := b.get("resources"):  # Storage: `food` (eatable, WB `_current_total_food`), `gold` (ore), `goods` (rest) — every building, not just civic.
            for r in stock.get("saved_resources") or []:
                rid = r.get("id")
                amount = r.get("amount", 0)
                inventory_by_city[cid][rid] += amount  # WB's own « Inventaire » panel, itemising the three tallies below
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

    # Succession pool, per realm: WB walks the crown's cities, so a warrior in the field is out of the running. `isUnitFitToRule` = alive civ of a kingdom.
    king_ids = {kid for k in save.get("kingdoms") or [] if (kid := k.get("kingID"))}
    heirs_by_kingdom: dict[int, list[dict]] = {}
    for c in save.get("cities") or []:
        for actor in actors_by_city.get(c["id"], ()) if (kid := c.get("kingdomID")) else ():
            if actor.get("clan") and actor.get("civ_kingdom_id") and (aid := actor["id"]) not in king_ids and aid not in leader_ids:
                heirs_by_kingdom.setdefault(kid, []).append(actor)

    ctx = {
        **build_actor_stats_context(save),  # world_time, languages_by_id, subspecies_by_id, species_data…
        "actors_by_army": actors_by_army,
        "actors_by_city": actors_by_city,
        "actors_by_id": actors_by_id,
        "armies_by_city": {a["id_city"]: a for a in save.get("armies") or []},  # at most one per city, enforced by WB
        "besieging_by_city": cache(lambda: besieging_kingdoms(save)),  # a walk over every actor, and only `metadata` asks — resolved on demand, once
        "books_by_city": cache(lambda: books_held(save)[0]),  # custody, not authorship; called not stored, a 15 k-row walk few sections need
        "buildings_by_city": buildings_by_city,
        "centres": {},  # `_city_centre` memo — every town asks its capital's, over and over.
        "children_by_id": cache(lambda: children_by_id(save)),  # living offspring per parent, world-wide: a resident's child may live elsewhere
        "cities_by_id": index_by_id(save.get("cities") or []),
        "cultures_by_id": index_by_id(save.get("cultures") or []),
        "eaters_by_city": eaters_by_city,
        # Racked gear per city, the six `item_storage_*` lists summed — a stat of its own, and what `_build_equipment` details on request.
        "equipment_by_city": {c["id"]: sum(len((c.get("equipment") or {}).get(f) or []) for f in EQUIPMENT_RACKS.values()) for c in save.get("cities") or []},
        "families_by_city": families_by_city,
        "families_by_id": index_by_id(save.get("families") or []),
        "fed_by_city": fed_by_city,
        "food_by_city": food_by_city,
        "gold_by_city": gold_by_city,
        "goods_by_city": goods_by_city,
        "heirs_by_kingdom": heirs_by_kingdom,
        "homeless_by_city": homeless_by_city,
        "houses_by_city": houses_by_city,
        "immortals_by_city": immortals_by_city,
        "infected_by_city": infected_by_city,
        "inventory_by_city": inventory_by_city,
        "island_lookup": cache(lambda: compute_islands_cached(save, save_path)[1]),  # tile → island id, called not stored: 33 ms only `metadata` needs
        "kingdoms_by_id": index_by_id(save.get("kingdoms") or []),
        # The 29 modifiers per town, then the total the panel prints — defined in one place so the `loyalty` section and the `ranks` sort never drift.
        "loyalty_by_city": cache(lambda: {c["id"]: _city_loyalty(c, ctx) for c in save.get("cities") or []}),
        "loyalty_total_by_city": cache(lambda: {cid: sum(mods.values()) for cid, mods in ctx["loyalty_by_city"]().items()}),
        "melee_by_city": melee_by_city,
        "money_by_city": money_by_city,
        "nobles_by_city": nobles_by_city,
        "nobles_money_by_city": nobles_money_by_city,
        "populations_by_city": populations_by_city,
        "ranged_by_city": ranged_by_city,
        "realm": cache(lambda: _build_realm_context(save, warriors_by_city)),  # the crown, its peers, its wars — read by loyalty alone, called not stored
        "religions_by_id": index_by_id(save.get("religions") or []),
        "renown_by_city": renown_by_city,
        "score_dimensions": cache(lambda: city_score_dimensions(save)),  # the composite score's tallies, some sourced nowhere else; same two callers
        "shelved_by_city": cache(lambda: _shelved_by_city(save)),  # the records behind `books_by_city`, only the `books` section spells them out
        "sick_by_city": sick_by_city,
        "stats_cache": {},  # `_actor_stats` memo: loyalty asks the same handful of kings and mayors for their skills over and over.
        "subspecies_base_cache": {},  # `compute_actor_stats` cache: heavy base computed once per subspecies, reused across actors.
        "troop_money_by_city": troop_money_by_city,
        "warriors_by_city": warriors_by_city,
    }
    return ctx


# The city's armoury: gear on its racks, worn by nobody. `total` is the ranked stat; `full` counts each rack, naming the section spells every piece out.
def _build_equipment(city: dict, ctx: dict, requested: str | None) -> dict:
    storage = city.get("equipment") or {}
    total = ctx["equipment_by_city"].get(city["id"], 0)
    if not wants_detail(requested, total):  # `full` keeps the chapter light: a count per stocked rack, the pieces themselves only when the section is named
        return light({"racks": {rack: n for rack, field in EQUIPMENT_RACKS.items() if (n := len(storage.get(field) or []))}, "total": total}, "equipment")
    item_stats, mod_stats = ctx["equipment"]["items"], ctx["equipment"]["modifiers"]
    racks = {}
    for rack, field in EQUIPMENT_RACKS.items():
        stored = (ctx["items_by_id"].get(iid) for iid in storage.get(field) or [])
        racks[rack] = sorted((equipment_entry(i, item_stats, mod_stats, ctx["world_time"]) for i in stored if i is not None), key=lambda i: i["id"])
    return {"racks": racks, "total": total}


# Chronicler-only: what the city officially is, not what its people are (`breakdown`). A mayor can turn it over (`leader_change_city_culture`), conquest cannot.
def _build_identity(city: dict, ctx: dict) -> dict:
    return {
        "clan": entity_ref(_city_clan(city, ctx), ctx["clans_by_id"]),
        "culture": entity_ref(city.get("id_culture"), ctx["cultures_by_id"]),
        "language": entity_ref(city.get("id_language"), ctx["languages_by_id"]),
        "religion": entity_ref(city.get("id_religion"), ctx["religions_by_id"]),
        "subspecies": entity_ref(_main_subspecies(city, ctx), ctx["subspecies_by_id"]),
    }


# WB's « Inventaire »: what `metadata.food`, `gold` and `goods` add up. Heaviest stack first — a granary reads by what fills it, not by spelling.
def _build_inventory(city_id: int, ctx: dict) -> dict:
    return dict(sorted(ctx["inventory_by_city"][city_id].items(), key=lambda kv: (-kv[1], kv[0])))


# Its leading families and its most singular souls. `stat_of` walks the whole roster, so this rides behind the section: nobody else pays for it.
def _build_leaders(city: dict, ctx: dict) -> dict:
    actors = ctx["actors_by_city"].get(city["id"], [])
    return settlement_leaders(actors, ctx["families_by_id"], ctx["children_by_id"](), lambda a: _actor_stats(a, ctx))


# The city's hold on its crown — the panel prints `total`. Chronicler-only beside it: `drivers` is every modifier and sums to `total`, `top_drivers` does not.
def _build_loyalty(city_id: int, ctx: dict, detailed: bool) -> dict:
    mods = ctx["loyalty_by_city"]().get(city_id, {})
    total = ctx["loyalty_total_by_city"]().get(city_id, 0)
    if detailed:
        return {"drivers": mods, "total": total}  # already ordered like WB's tooltip, strongest bond first
    top_pos = max((kv for kv in mods.items() if kv[1] > 0), key=lambda kv: kv[1], default=None)
    top_neg = min((kv for kv in mods.items() if kv[1] < 0), key=lambda kv: kv[1], default=None)
    return {"top_drivers": dict(kv for kv in (top_pos, top_neg) if kv is not None), "total": total}


# The city's identity card: WB's own lifetime counters (`total_deaths`/`total_kills`/`renown`) alongside the stocks and officialdom tallied in `_build_context`.
def _build_metadata(city: dict, ctx: dict, save: dict) -> dict:
    cid = city["id"]
    island_lookup = ctx["island_lookup"]()

    # Chronicler-only: distinct island ids under the city's zones, sorted asc (1 = biggest) — probed at each zone's centre tile.
    centres = ((z["x"] * ZONE_TILES + ZONE_TILES // 2, z["y"] * ZONE_TILES + ZONE_TILES // 2) for z in city.get("zones") or [])
    islands = sorted({iid for pos in centres if (iid := island_lookup.get(pos)) is not None})

    dims = ctx["score_dimensions"]()
    besiegers = [ref for k in ctx["besieging_by_city"]().get(cid, ()) if (ref := entity_ref(k, ctx["kingdoms_by_id"]))]

    # WB weighs a settlement's stores beside its people — the one meta type whose list runs past the four moods, its `getPopulationPeople` being its own headcount.
    residents, stock = ctx["actors_by_city"].get(cid, []), ctx["inventory_by_city"][cid]
    stores = {**{r: stock[r] for r in ("common_metals", "gold", "stone", "wood")}, "food": ctx["food_by_city"][cid]}
    report = meta_report("city", {**meta_ratios(residents, ctx), **stores, "people": len(residents), "units": len(residents)})
    kingdom = ctx["kingdoms_by_id"].get(city.get("kingdomID"))

    # Founder = the city's first settler (`founder_id`), emitted as `{id, name}` (dead or alive — the registry carries its visuals + tombstone).
    founder = None
    if fid := city.get("founder_id"):
        founder_actor = ctx["actors_by_id"].get(fid)
        name = founder_actor.get("name") if founder_actor else city.get("founder_name")
        founder = {"id": fid, "name": name}

    return {
        **_city_taxes(kingdom),
        "age": entity_age(city, ctx["world_time"]),
        "attractivity": dims["attractivity"].get(cid, 0),  # `migrated - left` over the city's life — negative where it bleeds faster than it draws.
        "buildings": ctx["buildings_by_city"][cid],  # Civic buildings owned by the city (nature excluded); `houses` is the dwelling subset.
        "deaths": int(city.get("total_deaths") or 0),  # Inhabitants lost over the city's lifetime (WB `total_deaths`).
        "families": len(ctx["families_by_city"].get(cid, ())),  # Distinct family lineages among its residents; the `familyless` count is in `population`.
        "food": ctx["food_by_city"][cid],  # Eatable resources stocked in the city's buildings.
        "founder": founder,
        "gold": ctx["gold_by_city"][cid],  # Gold ore in the city's buildings (mined + tribute). Not coins — see `population.money`.
        "goods": ctx["goods_by_city"][cid],  # Non-food, non-gold stock (materials, gems…).
        "houses": ctx["houses_by_city"][cid],  # Dwellings (subset of `buildings`).
        "id": cid,
        "islands": islands,
        "kills": int(city.get("total_kills") or 0),  # Enemies its inhabitants have slain over the city's lifetime (WB `total_kills`).
        "kingdom": entity_ref(city.get("kingdomID"), ctx["kingdoms_by_id"]),
        "name": city.get("name"),
        "renown": city.get("renown", 0),
        "report": report,  # what WB has the settlement say of itself
        # The crowns storming the town, eldest id first. Sorting the refs themselves would raise the moment a second one shows up — two dicts never compare.
        **({"besieged_by": sorted(besiegers, key=itemgetter("id"))} if besiegers else {}),
        "score_rank": city_score_ranks(save, dims).get(cid),  # placement on the composite settlement score (1 = heaviest); the total stays internal
        "territory": len(city.get("zones") or []),  # Zone count (each = an 8-tile `TileZone`).
        "wealth": ctx["money_by_city"][cid] + ctx["gold_by_city"][cid],  # Everything it owns: its people's coins + the gold in its buildings.
        **({"book_reach": reach} if (reach := dims["book_reach"].get(cid, 0)) else {}),  # `_BOOK_POINTS` per book written here + how widely it's read
        **({"capital": True} if kingdom and kingdom.get("capitalID") == cid else {}),  # Omitted when False (absence = not its kingdom's seat).
        **({"heir": heir} if (heir := _resolve_heir(city, ctx)) else {}),  # Omitted when WB would draw the next mayor at random — see `_resolve_heir`.
        # The sitting mayor (`None` between leaders). `money` = his own purse: inside `population.money`, netted out of `subjects_money` so both show apart.
        **(
            {"leader": {"id": lead["id"], "money": int(lead.get("money") or 0), "name": lead.get("name")}}
            if (lead := ctx["actors_by_id"].get(city.get("leaderID")))
            else {}
        ),
        # Chronicler-only, years under the present banner: stamped on annexation, so no key means the city never changed hands. The save keeps no previous owner.
        **({"years_in_kingdom": _years_since(stamp, ctx)} if (stamp := city.get("timestamp_kingdom")) not in (None, -1.0) else {}),
    }


# The realm layer `_city_loyalty` needs: who holds what, who borders whom, who is at war, and where each crown stands among the others.
def _build_realm_context(save: dict, warriors_by_city: Counter) -> dict:
    cities_by_kingdom: dict[int, list[dict]] = {}
    for city in save.get("cities") or []:
        cities_by_kingdom.setdefault(city.get("kingdomID"), []).append(city)

    # WB `nearbyBorders`/`neighbours_cities_kingdom`: two settlements border when a zone of one touches a zone of the other, diagonals included.
    neighbours_by_city: dict[int, set[int]] = {}
    for peers in cities_by_kingdom.values():
        zones = {c["id"]: {(z["x"], z["y"]) for z in c.get("zones") or []} for c in peers}
        for city in peers:
            halo = {(x + dx, y + dy) for x, y in zones[city["id"]] for dx in (-1, 0, 1) for dy in (-1, 0, 1)}
            neighbours_by_city[city["id"]] = {other["id"] for other in peers if other["id"] != city["id"] and halo & zones[other["id"]]}

    enemies_by_kingdom: dict[int, set[int]] = {}
    for war in save.get("wars") or []:
        if war.get("winner"):  # WB stamps a winner the moment a war ends; only the ones still being fought make a realm feel besieged
            continue
        attackers = ({war.get("main_attacker")} | set(war.get("list_attackers") or [])) - {None}
        defenders = ({war.get("main_defender")} | set(war.get("list_defenders") or [])) - {None}
        for side, foes in ((attackers, defenders), (defenders, attackers)):
            for kid in side:
                enemies_by_kingdom.setdefault(kid, set()).update(foes)

    # `DiplomacyManager.findSupremeKingdom`: warriors weigh double, holdings quintuple. The top two get their own loyalty bonus.
    kingdoms = save.get("kingdoms") or []
    held = {k["id"]: cities_by_kingdom.get(k["id"], []) for k in kingdoms}
    power = {kid: sum(warriors_by_city[c["id"]] for c in cities) * 2 + len(cities) * 5 + 1 for kid, cities in held.items()}
    ranked = sorted(kingdoms, key=lambda k: -power[k["id"]])

    return {
        "cities_by_kingdom": cities_by_kingdom,
        "enemies_by_kingdom": enemies_by_kingdom,
        "kingdom_count": len(kingdoms),
        "kingdom_power": power,
        "neighbours_by_city": neighbours_by_city,
        "second_kingdom_id": ranked[1]["id"] if len(ranked) > 1 else None,
        "supreme_kingdom_id": ranked[0]["id"] if ranked else None,
        "world_age_id": save["mapStats"].get("world_age_id"),
    }


# The tile a city radiates from (WB `updateCityCenter`): the zone centre closest to their average, nudged 2 tiles north. Memoised — every town asks its capital's.
def _city_centre(city: dict, ctx: dict) -> tuple[float, float] | None:
    cid = city["id"]
    if cid not in ctx["centres"]:
        zones = [(z["x"] * ZONE_TILES + ZONE_TILES // 2, z["y"] * ZONE_TILES + ZONE_TILES // 2) for z in city.get("zones") or []]
        mean_x, mean_y = (sum(c) / len(zones) for c in zip(*zones)) if zones else (0, 0)
        closest = min(zones, key=lambda z: (z[0] - mean_x) ** 2 + (z[1] - mean_y) ** 2, default=None)
        ctx["centres"][cid] = None if closest is None else (closest[0], closest[1] + 2)
    return ctx["centres"][cid]


# WB `City.getRoyalClan`: the sitting mayor's clan, and the king's while the seat is vacant — a town keeps a royal house even between mayors.
def _city_clan(city: dict, ctx: dict) -> int | None:
    leader = ctx["actors_by_id"].get(city.get("leaderID"))
    if leader and (clan := leader.get("clan")):
        return clan
    king = ctx["actors_by_id"].get((ctx["kingdoms_by_id"].get(city.get("kingdomID")) or {}).get("kingID"))
    return king.get("clan") if king else None


# WB `LoyaltyLibrary`'s 29 modifiers, summed into `metadata.loyalty`, numbered in registration order — bar #8 `mood`, whose `MoodLibrary` WB never registers.
def _city_loyalty(city: dict, ctx: dict) -> dict:
    mods: dict[str, int] = {}
    kingdom = ctx["kingdoms_by_id"].get(city.get("kingdomID"))
    if kingdom is None:
        return mods  # WB zeroes the whole thing for a neutral realm; an unaffiliated settlement has no crown to be loyal to either.

    capital = ctx["cities_by_id"].get(kingdom.get("capitalID"))
    is_capital = capital is not None and capital["id"] == city["id"]
    king = ctx["actors_by_id"].get(kingdom.get("kingID"))
    leader = ctx["actors_by_id"].get(city.get("leaderID"))
    population = ctx["populations_by_city"]
    realm = ctx["realm"]()

    def add(name: str, value: float) -> None:
        if int(value):
            mods[name] = int(value)

    # 1-2. Statecraft: the crown's own skill binds, the mayor's pulls the other way — a capable local lord is a rival, not an asset.
    if king:
        add("king_diplomacy", _skill(king, ctx))
    if leader:
        add("leader_diplomacy", -_skill(leader, ctx))

    # 3. The mayor's character, plus what they make of the king's (WB `ActorTraitLibrary.checkTraitsMod`).
    if leader:
        add("leader_loyalty", _loyalty_traits(leader, ctx) + (_traits_mod(leader, king) if king else 0))

    if not is_capital and capital:
        # 4-5. Outgrowing the capital breeds ambition; trailing it breeds deference. Both capped, in people and in claimed zones.
        for name, own, seat, step, cap in (
            ("population", population[city["id"]], population[capital["id"]], 3, 30),
            ("zones", len(city.get("zones") or []), len(capital.get("zones") or []), 20, 5),
        ):
            gap = min(abs(own - seat) // step, cap)
            add(name, -gap if own > seat else gap)
        # 6. Distance to the throne, one point per ten tiles.
        own_centre, seat_centre = _city_centre(city, ctx), _city_centre(capital, ctx)
        if own_centre and seat_centre:
            add("distance", -(((own_centre[0] - seat_centre[0]) ** 2 + (own_centre[1] - seat_centre[1]) ** 2) ** 0.5 / 10))

    # 7. The seat of the crown is loyal to itself, and by a margin nothing else can touch.
    add("capital", 1000 * is_capital)

    # 9-10. Youth: a fresh settlement and a fresh realm both start out grateful.
    city_age = entity_age(city, ctx["world_time"])
    if city_age <= 15:
        add("new_city", (15 - city_age) * 5)
    realm_age = entity_age(kingdom, ctx["world_time"])
    if realm_age <= 5:
        add("new_kingdom", (5 - realm_age) * 5)

    # 11. Overreach: every holding past what the crown's species (and its king's `cities` stat) can govern costs the outlying towns 25.
    if not is_capital:
        allowed = max(_CIV_BASE_CITIES.get(_kingdom_species(kingdom, ctx), 5) + int(_actor_stats(king, ctx).get("cities", 0)), 1)  # raw key, before the rename
        held = len(realm["cities_by_kingdom"].get(kingdom["id"], []))
        if held > allowed:
            add("cities", (allowed - held) * 25)

    # 12. Rallying: facing foes that outweigh the realm closes ranks — worth up to 50, and never negative when the realm is the stronger one.
    if foes := realm["enemies_by_kingdom"].get(kingdom["id"]):
        power = realm["kingdom_power"]
        add("superior_enemies", min(max((sum(power[f] for f in foes if f in power) - power[kingdom["id"]]) // 2, 0), 50))
    if not is_capital and capital:
        # 13-14. Bordering the capital is worth 20; so is a land route to it, whose absence costs 35 — but only between towns of the same species.
        if capital["id"] in realm["neighbours_by_city"].get(city["id"], set()):
            add("close_to_capital", 20)
        same_species = _city_species(capital, ctx) == _city_species(city, ctx)
        if same_species:
            add("connected_to_capital", 20 if _connected_to_capital(city, capital, realm["neighbours_by_city"]) else -35)
        # 15-17. Shared institutions: agreement is always worth 15, dissent costs more the deeper the creed runs.
        for name, field, penalty in (("culture", "id_culture", -25), ("language", "id_language", -20), ("religion", "id_religion", -30)):
            if city.get(field) is not None:
                add(name, 15 if capital.get(field) == city.get(field) else penalty)
        # 18-19. Kin: a foreign-blooded seat costs 25 (5 under a xenophile mayor, 50 if he or his king is xenophobic); same blood then splits by subspecies.
        if not same_species:
            # WB weighs both cultures only through the mayor, so a vacant seat leaves even a xenophobic king's opinion out of it.
            xenophobe = leader is not None and (_has_culture_trait(leader, "xenophobic", ctx) or _has_culture_trait(king, "xenophobic", ctx))
            add("species", -50 if xenophobe else (-5 if _has_culture_trait(leader, "xenophiles", ctx) else -25))
        else:
            add("subspecies", 15 if _main_subspecies(capital, ctx) == _main_subspecies(city, ctx) else -15)
        # 20. Clan, weighed only between a mayor and a king of the same subspecies — otherwise the question doesn't arise.
        if leader and king and king.get("subspecies") == leader.get("subspecies"):
            add("clan", 30 if leader.get("clan") == king.get("clan") else -20)

    # 21-22. Fresh bonds fade over a decade: the realm's latest conquest, and this town's own years under the banner.
    conquest = kingdom.get("timestamp_new_conquest")
    if conquest is not None and float(conquest) != -1.0 and (years := _years_since(conquest, ctx)) <= 10:
        add("new_conquest", (10 - years) * 30)
    if (years := _years_since(city.get("timestamp_kingdom") or 0, ctx)) <= 10:
        add("part_of_kingdom", (10 - years) * 10)

    # 23-24. Standing among the realms — WB ranks them by warriors and holdings, and only the top two earn anything.
    if realm["kingdom_count"] > 1 and realm["supreme_kingdom_id"] == kingdom["id"]:
        add("supreme_kingdom", 100)
    if realm["kingdom_count"] > 2 and realm["second_kingdom_id"] == kingdom["id"]:
        add("second_best_kingdom", 50)

    # 25-27. The reign itself: one point per year past the fifth (capped at 40), the age's own temper, and a child on the throne.
    if king and (years := _years_since(kingdom.get("timestamp_king_rule") or 0, ctx)) >= 5:
        add("king_rule", min(years, 40))
    add("world_era", _ERA_LOYALTY.get(realm["world_age_id"], 0))
    if king and entity_age(king, ctx["world_time"]) < 18:
        add("baby_king", -50)

    # 28-29. A crown whose sex its own official culture rejects — only where town and realm share that culture.
    culture = ctx["cultures_by_id"].get(city.get("id_culture"))
    if king and culture and city.get("id_culture") == kingdom.get("id_culture"):
        traits = culture.get("saved_traits") or []
        add("patriarchy", -50 * ("patriarchy" in traits and sex_label(king) == "female"))
        add("matriarchy", -50 * ("matriarchy" in traits and sex_label(king) == "male"))

    return dict(sorted(mods.items(), key=lambda kv: -kv[1]))  # Ordered like WB's own tooltip: the strongest bonds first, the grievances last.


# WB `City.getSpecies` — the sitting mayor's own kind, or the founder's while the seat is vacant.
def _city_species(city: dict, ctx: dict) -> str | None:
    leader = ctx["actors_by_id"].get(city.get("leaderID"))
    return leader.get("asset_id") if leader else city.get("original_actor_asset")


# Chronicler-only, `BehActorGiveTax`: an inhabitant pays its mayor (`tax_local`), the mayor pays the crown (`tax_tribute`). The crown sets both rates.
def _city_taxes(kingdom: dict | None) -> dict:
    taxes = {"tax_local": "normal", "tax_tribute": "normal"}
    for trait in (kingdom or {}).get("saved_traits") or []:
        if spec := _CITY_TAX_TRAITS.get(trait):
            taxes[spec[0]] = spec[1]
    return taxes


# The shared settlement getters plus the ones this tier owns. Top 3 among the world's cities via `competition_ranks`, like every ranks section.
def _compute_ranks(city: dict, ctx: dict, save: dict) -> dict:
    books, loyalty = ctx["books_by_city"](), ctx["loyalty_total_by_city"]()  # resolved once, not inside getters `competition_ranks` fires per city
    dims = ctx["score_dimensions"]()
    armies = {c["id"]: _build_army(c, ctx) or {} for c in save.get("cities") or []}  # built once per city, not once per city and per stat
    getters = settlement_rank_getters(ctx, "city")
    getters.update(  # the score dimensions the panel surfaces and no other getter covers, plus the loyalty the crown's hold rests on
        {
            **{  # Prefixed: the city ranks `kills`/`deaths`/`renown` of its own already. `key=k` binds per entry — a bare closure would read the loop's last value.
                f"army_{k}": lambda c, key=k: armies.get(c.get("id"), {}).get(key, 0)
                for k in ("age", "captain_years", "kills", "kills_per_death", "money", "renown")
            },
            "attractivity": lambda c: dims["attractivity"].get(c.get("id"), 0),
            "book_reach": lambda c: dims["book_reach"].get(c.get("id"), 0),
            "books": lambda c: books[c.get("id")],
            "equipment": lambda c: ctx["equipment_by_city"].get(c.get("id"), 0),
            "loyalty": lambda c: loyalty.get(c.get("id"), 0),
        }
    )
    return competition_ranks(city, save.get("cities") or [], getters)


# WB `City.isConnectedToCapital`: flood the kingdom's city graph outward from the capital and see whether this town is reached before the wave count runs out.
def _connected_to_capital(city: dict, capital: dict, neighbours: dict[int, set[int]]) -> bool:
    seen: set[int] = set()
    wave = set(neighbours.get(capital["id"], set()))
    for _ in range(_LOYALTY_WAVES + 1):
        if city["id"] in wave:
            return True
        seen |= wave
        if not (wave := {n for w in wave for n in neighbours.get(w, set())} - seen):
            return False
    return False


# Whether an actor's own culture carries a trait — `None` actor included, since loyalty asks it of seats that may stand vacant.
def _has_culture_trait(actor: dict | None, trait: str, ctx: dict) -> bool:
    culture = ctx["cultures_by_id"].get(actor.get("culture")) if actor else None
    return bool(culture) and trait in (culture.get("saved_traits") or [])


# WB `Kingdom.getActorAsset` — the reigning king's kind, or the founder's between reigns. Sets how many holdings the crown can govern; `""` falls to the default 5.
def _kingdom_species(kingdom: dict, ctx: dict) -> str:
    king = ctx["actors_by_id"].get(kingdom.get("kingID"))
    return (king.get("asset_id") if king else kingdom.get("original_actor_asset")) or ""


# The `loyalty_traits` an actor carries. `_cleanup_stats` drops it (nothing else reads it), so the four trait tables are summed here instead.
def _loyalty_traits(actor: dict, ctx: dict) -> int:
    total = 0.0
    for table, ids in (
        ("clan_traits", (ctx["clans_by_id"].get(actor.get("clan")) or {}).get("saved_traits")),
        ("creature_traits", actor.get("saved_traits")),
        ("language_traits", (ctx["languages_by_id"].get(actor.get("language")) or {}).get("saved_traits")),
        ("subspecies_traits", (ctx["subspecies_by_id"].get(actor.get("subspecies")) or {}).get("saved_traits")),
    ):
        for trait_id in ids or []:
            total += (ctx[table].get(trait_id) or {}).get("stats", {}).get("loyalty_traits", 0)
    return int(total)


# WB `City.getMainSubspecies` — the mayor's, or the first inhabitant's when the seat is vacant.
def _main_subspecies(city: dict, ctx: dict) -> int | None:
    leader = ctx["actors_by_id"].get(city.get("leaderID"))
    if leader:
        return leader.get("subspecies")
    residents = ctx["actors_by_city"].get(city["id"]) or []
    return residents[0].get("subspecies") if residents else None


# WB `CityBehCheckLeader.tryGetClanLeader`: the realm's clanned subjects, royal house first, ranked by the city's culture. `None` where WB would roll dice instead.
def _resolve_heir(city: dict, ctx: dict) -> dict | None:
    pool = ctx["heirs_by_kingdom"].get(city.get("kingdomID")) or ()
    royal_clan = (ctx["kingdoms_by_id"].get(city.get("kingdomID")) or {}).get("royal_clan_id")
    candidates = [a for a in pool if a.get("clan") == royal_clan] or list(pool)
    traits = set((ctx["cultures_by_id"].get(city.get("id_culture")) or {}).get("saved_traits") or [])
    heir = succession_heir(candidates, traits, ctx["world_time"], lambda a: _actor_stats(a, ctx))
    return entity_ref(heir["id"], ctx["actors_by_id"]) if heir else None


# Books grouped by the town holding them, off `books_held`'s book → city map. The save lists every volume ever written, shelved or lost with its hall.
def _shelved_by_city(save: dict) -> dict[int, list[dict]]:
    city_of_book = books_held(save)[2]
    by_city: dict[int, list[dict]] = {}
    for book in sorted(save.get("books") or [], key=lambda b: b["id"]):
        if (cid := city_of_book.get(book.get("id"))) is not None:
            by_city.setdefault(cid, []).append(book)
    return by_city


# WB's statecraft score behind loyalty modifiers 1-2: `diplomacy + stewardship × 2`, summed raw then cast once — see `_actor_stats`.
def _skill(actor: dict, ctx: dict) -> int:
    stats = _actor_stats(actor, ctx)
    return int(stats.get("diplomacy", 0) + stats.get("stewardship", 0) * 2)


# WB `ActorTraitLibrary.checkTraitsMod`: what the mayor makes of the king, trait by trait — kinship for the shared ones, friction for the opposed.
def _traits_mod(leader: dict, king: dict) -> int:
    total = 0
    king_traits = set(king.get("saved_traits") or [])
    for trait_id in leader.get("saved_traits") or []:
        if spec := _TRAIT_MODS.get(trait_id):
            total += spec["same"] * (trait_id in king_traits) + spec["opposite"] * (spec["opposite_trait"] in king_traits)
    return total


def _years_since(timestamp: float, ctx: dict) -> int:
    return int((ctx["world_time"] - float(timestamp)) / UNITS_PER_YEAR)


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

    requested = argv[1] if len(argv) > 1 else None
    try:
        sections = parse_sections(requested, _ALL_SECTIONS)
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 2
    save = load_save(save_path)
    city = index_by_id(save.get("cities") or []).get(city_id)
    if city is None:
        print(f"unknown city: {city_id}", file=sys.stderr)
        return 1
    ctx = _build_context(save, save_path)

    out: dict = {}
    if "army" in sections:
        if army := _build_army(city, ctx):  # Here, not in `_build_army`: the ranks section builds one per city and would pay for a verdict no getter reads.
            troops = ctx["actors_by_army"].get(ctx["armies_by_city"][city["id"]]["id"], [])
            army = {**army, **({"report": report} if (report := meta_report("army", {"units": len(troops), **meta_ratios(troops, ctx)})) else {})}
        out["army"] = army
    if "books" in sections:
        out["books"] = _build_books(city, ctx, requested)
    if "breakdown" in sections:
        out["breakdown"] = population_breakdown(ctx["actors_by_city"].get(city_id, []), ctx)
    if "equipment" in sections:
        out["equipment"] = _build_equipment(city, ctx, requested)
    if "identity" in sections:
        out["identity"] = _build_identity(city, ctx)
    if "inventory" in sections:
        out["inventory"] = _build_inventory(city_id, ctx)
    if "leaders" in sections:
        out["leaders"] = _build_leaders(city, ctx)
    if "loyalty" in sections:
        out["loyalty"] = _build_loyalty(city_id, ctx, detailed=requested not in (None, "full"))  # Naming a section gives the full ledger, `full` the summary.
    if "metadata" in sections:
        out["metadata"] = _build_metadata(city, ctx, save)
    if "population" in sections:
        out["population"] = settlement_population(city, ctx, "city")
    if "ranks" in sections:
        out["ranks"] = _compute_ranks(city, ctx, save)
    emit(out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
