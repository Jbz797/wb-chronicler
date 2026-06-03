#!/usr/bin/env python3

import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).parent.parent))
from shared import MONTHS_PER_YEAR, emit, index_by_id, load_data, load_save, parse_sections, register_entity  # noqa: E402

_ALL_SECTIONS = ("metadata", "ranks", "wars")
_REGISTRY = Path(__file__).parent.parent.parent / "saves" / "kingdoms.json"


def _build_context(save: dict) -> dict:
    # Index of living actors per kingdom — mirrors `Kingdom.getPopulation`. `profession == 5` = warrior.
    # `boat_*` actors (fishing/trading/transport boats) are transient PNJs WB excludes from the kingdom population stat.
    populations_by_kingdom: dict[int, int] = {}
    warriors_by_kingdom: dict[int, int] = {}
    for actor in save.get("actors_data", []):
        kid = actor.get("civ_kingdom_id")
        if not kid or (actor.get("asset_id") or "").startswith("boat_"):
            continue
        populations_by_kingdom[kid] = populations_by_kingdom.get(kid, 0) + 1
        if actor.get("profession") == 5:
            warriors_by_kingdom[kid] = warriors_by_kingdom.get(kid, 0) + 1
    cities_by_kingdom: dict[int, int] = {}
    territory_by_kingdom: dict[int, int] = {}
    for city in save.get("cities", []):
        kid = city.get("kingdomID")
        if not kid:
            continue
        cities_by_kingdom[kid] = cities_by_kingdom.get(kid, 0) + 1
        territory_by_kingdom[kid] = territory_by_kingdom.get(kid, 0) + len(city.get("zones") or [])
    return {
        "cities_by_kingdom": cities_by_kingdom,
        "populations_by_kingdom": populations_by_kingdom,
        "territory_by_kingdom": territory_by_kingdom,
        "warriors_by_kingdom": warriors_by_kingdom,
        "world_time": float(save["mapStats"].get("world_time") or 0),
    }


def _build_metadata(kingdom: dict, ctx: dict) -> dict:
    age_months = ctx["world_time"] - float(kingdom.get("created_time") or 0)
    return {
        "age": int(age_months / MONTHS_PER_YEAR),
        "cities": ctx["cities_by_kingdom"].get(kingdom.get("id"), 0),
        "id": kingdom.get("id"),
        "motto": kingdom.get("motto"),
        "name": kingdom.get("name"),
        "population": ctx["populations_by_kingdom"].get(kingdom.get("id"), 0),
        "renown": kingdom.get("renown", 0),
        "territory": ctx["territory_by_kingdom"].get(kingdom.get("id"), 0),
        "warriors": ctx["warriors_by_kingdom"].get(kingdom.get("id"), 0),
    }


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
        populations = ctx["populations_by_kingdom"]
        warriors = ctx["warriors_by_kingdom"]
        duration_months = ctx["world_time"] - float(w.get("created_time") or 0)
        out.append({
            "allies": sorted(
                ({"id": a["id"], "name": a.get("name") or f"#{a['id']}"} for a in ally_kingdoms),
                key=lambda o: o["id"],
            ),
            "attacker_alliance": alliance_for(w.get("main_attacker"), w.get("list_attackers") or []),
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
            "warriors": {
                "attackers": sum(warriors.get(aid, 0) for aid in attackers),
                "defenders": sum(warriors.get(did, 0) for did in defenders),
            },
        })
    return sorted(out, key=lambda x: x["id"])


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
        out["metadata"] = _build_metadata(kingdom, ctx)
    if "ranks" in sections:
        out["ranks"] = _compute_ranks(kingdom, ctx, save)
    if "wars" in sections:
        out["wars"] = _build_wars(kingdom, ctx, save)

    emit(out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
