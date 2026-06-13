#!/usr/bin/env python3

# User-facing docs (usage, available sections) live in `tools/tools.md`. Notes below are for maintainers — algorithm references, gotchas, source pointers.

import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "actor"))
sys.path.insert(0, str(Path(__file__).parent.parent / "geography"))
from actor_stats import build_actor_stats_context, compute_actor_stats  # noqa: E402
from islands import compute_islands_cached  # noqa: E402
from shared import CURRENT_SAVE, MONTHS_PER_YEAR, emit, index_by_id, load_data, load_save, parse_sections, register_entity  # noqa: E402

_ALL_SECTIONS = ("metadata", "ranks", "relations", "wars")
_BABY_AGE_THRESHOLD_MONTHS = 16 * MONTHS_PER_YEAR  # WB considers actors « baby » below ~16 in-game years.
_BORDERS_ZONE_DISTANCE = 3  # `areKingdomsClose` proxy: kingdoms are « close » if any pair of their zones are within this Manhattan distance.
_FAR_LANDS_CAPITAL_DISTANCE = 18  # `!isSameIsland` proxy: capitals further apart than this are treated as on different lands.
_OPINION_CONSTANTS = load_data("opinion-constants.json")
_REGISTRY = Path(__file__).parent.parent.parent / "saves" / "kingdoms.json"


def _build_context(save: dict) -> dict:
    # Index of living actors per kingdom (mirrors `Kingdom.getPopulation`, excludes `boat_*` transient PNJs). `profession == 5` = warrior.
    populations_by_kingdom: dict[int, int] = {}
    warriors_by_kingdom: dict[int, int] = {}
    subspecies_counts: dict[int, dict[int, int]] = {}
    actors_by_id: dict[int, dict] = {}
    for actor in save.get("actors_data", []):
        actors_by_id[actor["id"]] = actor
        kid = actor.get("civ_kingdom_id")
        if not kid or (actor.get("asset_id") or "").startswith("boat_"):
            continue
        populations_by_kingdom[kid] = populations_by_kingdom.get(kid, 0) + 1
        if actor.get("profession") == 5:
            warriors_by_kingdom[kid] = warriors_by_kingdom.get(kid, 0) + 1
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
    capitals_by_kingdom = {k["id"]: cities_by_id[k["capitalID"]] for k in save.get("kingdoms", []) if k.get("capitalID") in cities_by_id}
    # Main subspecies = the most-counted one per kingdom (fallback used by `Kingdom.getMainSubspecies`).
    main_subspecies = {kid: max(counts.items(), key=lambda kv: kv[1])[0] for kid, counts in subspecies_counts.items()}
    # Supreme kingdom = the one with the largest adult population. WB picks the « most powerful » kingdom — population is the most consistent metric across screens.
    supreme_kingdom_id = max(populations_by_kingdom.items(), key=lambda kv: kv[1])[0] if populations_by_kingdom else None
    return {
        **build_actor_stats_context(save),
        "actors_by_id": actors_by_id,
        "capitals_by_kingdom": capitals_by_kingdom,
        "cities_by_kingdom": cities_by_kingdom,
        "main_subspecies": main_subspecies,
        "populations_by_kingdom": populations_by_kingdom,
        "supreme_kingdom_id": supreme_kingdom_id,
        "territory_by_kingdom": territory_by_kingdom,
        "warriors_by_kingdom": warriors_by_kingdom,
        "world_age_id": save["mapStats"].get("world_age_id"),
        "zones_by_kingdom": zones_by_kingdom,
    }


def _build_metadata(kingdom: dict, ctx: dict, save: dict) -> dict:
    kid = kingdom.get("id")
    age_months = ctx["world_time"] - float(kingdom.get("created_time") or 0)
    _, island_lookup = compute_islands_cached(save, CURRENT_SAVE)
    # Chronicler-only: distinct island ids touched by the kingdom's city zones, sorted asc (1 = biggest). Zones are WB `TileZone`s of 8 tiles — probe centre.
    islands = sorted({iid for zx, zy in ctx["zones_by_kingdom"].get(kid, []) if (iid := island_lookup.get((zx * 8 + 4, zy * 8 + 4))) is not None})
    return {
        "age": int(age_months / MONTHS_PER_YEAR),
        "cities": ctx["cities_by_kingdom"].get(kid, 0),
        "id": kid,
        "islands": islands,
        "motto": kingdom.get("motto"),
        "name": kingdom.get("name"),
        "population": ctx["populations_by_kingdom"].get(kid, 0),
        "renown": kingdom.get("renown", 0),
        "territory": ctx["territory_by_kingdom"].get(kid, 0),
        "warriors": ctx["warriors_by_kingdom"].get(kid, 0),
    }


# Diplomatic ties involving this kingdom. Status derived from alliances/wars cross-ref (WB only persists pair + timestamps).
def _build_relations(kingdom: dict, ctx: dict, save: dict) -> list[dict]:
    kid = kingdom.get("id")
    alliances = save.get("alliances", [])
    ongoing_wars = [w for w in save.get("wars", []) if not w.get("winner")]

    # Other kingdom is an ally if both share an alliance.
    def is_ally(other_id: int) -> bool:
        return any(kid in (a.get("kingdoms") or []) and other_id in (a.get("kingdoms") or []) for a in alliances)

    # Other kingdom is an enemy if both stand on opposite sides of an ongoing war.
    def is_enemy(other_id: int) -> bool:
        for w in ongoing_wars:
            attackers = ({w.get("main_attacker")} | set(w.get("list_attackers") or [])) - {None}
            defenders = ({w.get("main_defender")} | set(w.get("list_defenders") or [])) - {None}
            if (kid in attackers and other_id in defenders) or (kid in defenders and other_id in attackers):
                return True
        return False

    # Optional pair record (`save.relations` only persists pairs WB has explicitly tracked) — drives `age_years`, `years_since_last_war`, and the `peace_time`/`truce` modifiers via `_compute_opinion`. WB still computes opinion for every other kingdom regardless, so we iterate ALL kingdoms here.
    relations_by_other = {
        (r.get("kingdom2_id") if r.get("kingdom1_id") == kid else r.get("kingdom1_id")): r
        for r in save.get("relations", [])
        if kid in (r.get("kingdom1_id"), r.get("kingdom2_id"))
    }

    out = []
    for other in save.get("kingdoms", []):
        other_id = other.get("id")
        if other_id == kid:
            continue
        _register_kingdom(other, save)
        r = relations_by_other.get(other_id)
        status = "ally" if is_ally(other_id) else "enemy" if is_enemy(other_id) else "neutral"
        last_war_end = (r or {}).get("timestamp_last_war_ended")
        out.append(
            {
                "age_years": int((ctx["world_time"] - float((r or {}).get("created_time") or 0)) / MONTHS_PER_YEAR) if r else None,
                "kingdom": {"id": other_id, "name": other.get("name") or f"#{other_id}"},
                "opinion": _compute_opinion(kingdom, other, save, ctx, alliances, ongoing_wars, r),
                "status": status,
                "years_since_last_war": int((ctx["world_time"] - float(last_war_end)) / MONTHS_PER_YEAR) if last_war_end else None,
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

    out = []
    for w in save.get("wars", []):
        if w.get("winner"):
            continue
        attackers = ({w.get("main_attacker")} | set(w.get("list_attackers") or [])) - {None}
        defenders = ({w.get("main_defender")} | set(w.get("list_defenders") or [])) - {None}
        if kid not in attackers and kid not in defenders:
            continue
        side = "attacker" if kid in attackers else "defender"
        opponent_kingdoms = [kingdoms_by_id[oid] for oid in (defenders if side == "attacker" else attackers) if oid in kingdoms_by_id]
        ally_kingdoms = [kingdoms_by_id[aid] for aid in (attackers if side == "attacker" else defenders) - {kid} if aid in kingdoms_by_id]
        starter_kingdom = kingdoms_by_id.get(w.get("started_by_kingdom_id"))
        # Register opposing/ally kingdoms (and the war's instigator) so the UI's `app-kingdom-tag` can resolve their banner + colours.
        for k in [*opponent_kingdoms, *ally_kingdoms, *([starter_kingdom] if starter_kingdom else [])]:
            _register_kingdom(k, save)
        cities = ctx["cities_by_kingdom"]
        populations = ctx["populations_by_kingdom"]
        warriors = ctx["warriors_by_kingdom"]
        duration_months = ctx["world_time"] - float(w.get("created_time") or 0)
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
                "duration_years": int(duration_months / MONTHS_PER_YEAR),
                "id": w.get("id"),
                "is_main": kid == w.get(f"main_{side}"),
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
    return int(compute_actor_stats(king, ctx).get("diplomacy", 0))


# Mirror `DiplomacyRelation.recalculate` IL: each numbered modifier = a WB `OpinionAsset`. Runtime stats reconstructed via `actor_stats.compute_actor_stats`.
def _compute_opinion(main: dict, target: dict, save: dict, ctx: dict, alliances: list, ongoing_wars: list, relation: dict | None) -> dict:
    mod: dict[str, int] = {}
    mid, tid = main["id"], target["id"]

    main_king = ctx["actors_by_id"].get(main.get("kingID"))
    target_king = ctx["actors_by_id"].get(target.get("kingID"))
    main_pos = _city_centroid(ctx["capitals_by_kingdom"].get(mid))
    target_pos = _city_centroid(ctx["capitals_by_kingdom"].get(tid))
    main_zones = ctx["zones_by_kingdom"].get(mid, [])
    target_zones = ctx["zones_by_kingdom"].get(tid, [])

    def is_enemy() -> bool:
        for w in ongoing_wars:
            a = ({w.get("main_attacker")} | set(w.get("list_attackers") or [])) - {None}
            d = ({w.get("main_defender")} | set(w.get("list_defenders") or [])) - {None}
            if (mid in a and tid in d) or (mid in d and tid in a):
                return True
        return False

    def is_in_war_on_same_side() -> bool:
        for w in ongoing_wars:
            a = ({w.get("main_attacker")} | set(w.get("list_attackers") or [])) - {None}
            d = ({w.get("main_defender")} | set(w.get("list_defenders") or [])) - {None}
            if (mid in a and tid in a) or (mid in d and tid in d):
                return True
        return False

    enemy = is_enemy()

    # 1. king: target's king's diplomacy stat. Stats are runtime-only in WB, so we reconstruct: species base + trait bonuses + level/2 (level scaling is empirical from screen calibration).
    if target_king:
        mod["king"] = _compute_king_diplomacy(target_king, ctx)

    # 2. kings_mood: main's king's runtime mood — not serialised. Skipped.

    # 3. is_supreme: -100 if target is the « most powerful » kingdom (= largest adult population) and world has ≥3 kingdoms.
    if tid == ctx.get("supreme_kingdom_id") and len(save.get("kingdoms") or []) >= 3:
        mod["is_supreme"] = -100

    # 4. borders: ±25. WB checks `areKingdomsClose` (any city pair within adjacency threshold). Proxy: min zone-pair Manhattan distance ≤ _BORDERS_ZONE_DISTANCE.
    close = _min_zone_distance(main_zones, target_zones) <= _BORDERS_ZONE_DISTANCE
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
    years_since = (ctx["world_time"] - last_war_end) / MONTHS_PER_YEAR if last_war_end is not None else None
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
        if main_age >= _BABY_AGE_THRESHOLD_MONTHS and target_age < _BABY_AGE_THRESHOLD_MONTHS:
            mod["baby_king"] = -50

    # 22-24. ethnocentric_guard / xenophobic / xenophiles: need main.culture.saved_traits. Check below.
    main_culture = next((c for c in save.get("cultures", []) if c.get("id") == main.get("id_culture")), None)
    culture_traits = set((main_culture or {}).get("saved_traits") or [])
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
    cities = ctx["cities_by_kingdom"]
    populations = ctx["populations_by_kingdom"]
    territory = ctx["territory_by_kingdom"]
    warriors = ctx["warriors_by_kingdom"]

    def kingdom_age(k: dict) -> int:
        return int((ctx["world_time"] - float(k.get("created_time") or 0)) / MONTHS_PER_YEAR)

    getters = {
        "age": kingdom_age,
        "cities": lambda k: cities.get(k.get("id"), 0),
        "population": lambda k: populations.get(k.get("id"), 0),
        "renown": lambda k: k.get("renown", 0),
        "territory": lambda k: territory.get(k.get("id"), 0),
        "warriors": lambda k: warriors.get(k.get("id"), 0),
    }
    ranks = {}
    for stat, getter in sorted(getters.items()):
        own = getter(kingdom)
        rank = sum(1 for k in kingdoms if getter(k) > own) + 1
        if rank <= 3:
            ranks[stat] = rank
    return ranks


# Relative luminance (WCAG) of a "#RRGGBB" colour — used to pick the darkest / lightest of a palette.
def _luminance(color: str) -> float:
    channels = [int(color[i : i + 2], 16) / 255 for i in (1, 3, 5)]
    linear = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


# Min Manhattan distance between any pair of zones from two kingdoms. Returns `inf` when either side has no zones.
def _min_zone_distance(zones_a: list[tuple[int, int]], zones_b: list[tuple[int, int]]) -> float:
    if not zones_a or not zones_b:
        return float("inf")
    return min(abs(a[0] - b[0]) + abs(a[1] - b[1]) for a in zones_a for b in zones_b)


# Upsert reader registry with per-kingdom visuals (icon + colours). Display name comes from the caller (markdown token or chapter.json), not stored here.
def _register_kingdom(kingdom: dict, save: dict) -> None:
    # Background = darkest of colour's 4 game hues, ink (icon/text/border) = lightest — max contrast within kingdom's real palette (colors-all.json).
    palette = [h for h in load_data("colors-all.json").get(str(kingdom.get("color_id", "")), {}).values() if h]
    register_entity(
        _REGISTRY,
        str(kingdom.get("id")),
        {
            "banner_icon": _resolve_banner_sprite(kingdom, save),
            "color": min(palette, key=_luminance) if palette else None,
            "ink": max(palette, key=_luminance) if palette else None,
        },
    )


# Mirrors `Kingdom.getElementIcon`: index `banner_icon_id` (null → 0, out-of-range → 0) into the king's species banner set (founder species if no living king).
# CLAUDE: `banner-icons.json` is generated from *BannerLibrary assets, covers every species — don't hand-patch, regenerate from game files for new species.
def _resolve_banner_sprite(kingdom: dict, save: dict) -> int:
    king = next((a for a in save.get("actors_data", []) if a.get("id") == kingdom.get("kingID")), None)
    subspecies = index_by_id(save.get("subspecies", [])).get(king.get("subspecies")) if king else None
    species = (subspecies or {}).get("species_id") or kingdom.get("original_actor_asset")
    banners = load_data("banner-icons.json")
    icons = banners["banner_id_icons"][banners["species_to_banner_id"][species]]
    index = kingdom.get("banner_icon_id") or 0
    return icons[index if index < len(icons) else 0]


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
    _register_kingdom(kingdom, save)
    ctx = _build_context(save)

    out: dict = {}
    if "metadata" in sections:
        out["metadata"] = _build_metadata(kingdom, ctx, save)
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
