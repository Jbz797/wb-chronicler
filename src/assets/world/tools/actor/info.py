#!/usr/bin/env python3

# User-facing docs (usage, available sections) live in `tools/tools.md`. Notes below are for maintainers — algorithm references, gotchas, source pointers.

import re
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "geography"))
from actor_stats import build_actor_stats_context, compute_actor_stats  # noqa: E402
from islands import compute_islands_cached  # noqa: E402
from shared import CURRENT_SAVE, MONTHS_PER_YEAR, emit, index_by_id, load_save, parse_sections, register_entity  # noqa: E402


_ALL_SECTIONS = ("best_friend", "creature_traits", "equipment", "inventory", "lover", "metadata", "plot", "ranks_in_species", "stats")
_LEVEL_RE = re.compile(r"(\d+)$")

# `Actor.getMassKG`: mass = (target_scale / 0.1) × mass_2 × (1 + Σ multiplier_mass). `target_scale`/`mass_2` not persisted, rebuilt from asset_id + saved_traits.
_MASS_BASE = {"dwarf": 75, "elf": 25, "humanoid": 65, "orc": 85}

_PROFESSION_KING = 3
_PROFESSION_LEADER = 4
_PROFESSIONS = {2: "unit", _PROFESSION_KING: "king", _PROFESSION_LEADER: "leader", 5: "warrior"}

# Competition rank (1,2,2,4) per stat among `asset_id` peers. Mostly maps to `RankedStatKind` (types.ts; UI: RankedStatComponent). `births` chronicler-only.
_RANKED_STATS = {
    "armor",
    "attack_speed",
    "birth_rate",
    "births",
    "children",
    "critical_chance",
    "damage",
    "damage_range",
    "diplomacy",
    "health_max",
    "intelligence",
    "kills",
    "level",
    "lifespan",
    "loot",
    "mana_max",
    "money",
    "renown",
    "speed",
    "stamina_max",
    "stewardship",
    "warfare",
}

_REGISTRY = Path(__file__).parent.parent.parent / "saves" / "persons.json"

# UI order: active roles first (can be lost — chief/alpha/captain by hierarchical rank), then historical foundations (irrevocable — creators before founders).
_ROLE_ORDER = (
    "clan_chief",
    "family_alpha",
    "army_captain",
    "culture_creator",
    "language_creator",
    "religion_creator",
    "alliance_founder",
    "clan_founder",
    "village_founder",
    "family_founder",
)

# Mass deltas from traits — only `fat`, `giant`, `tiny`, `agile` in the DLL.
_TRAIT_MASS_MODS = {
    "agile": {"scale": -0.01},
    "fat": {"multiplier_mass": 0.30, "scale": 0.02},
    "giant": {"scale": 0.05},
    "tiny": {"scale": -0.02},
}


def _build_companion(actor: dict, ctx: dict, save: dict, id_field: str) -> dict | None:
    companion_id = actor.get(id_field)
    if companion_id is None:
        return None
    companion = next((a for a in save["actors_data"] if a.get("id") == companion_id), None)
    if companion is None:
        return None
    snap = compute_actor_stats(companion, ctx)
    age_months = ctx["world_time"] - float(companion.get("created_time") or 0)
    return {
        "age": int(age_months / MONTHS_PER_YEAR) + (companion.get("age_overgrowth") or 0),
        "health_max": snap.get("health_max", 0),
        "id": companion_id,
        "level": snap.get("level", 0),
        "money": snap.get("money", 0),
        "name": companion.get("name"),
        "renown": snap.get("renown", 0),
        "sex": "female" if companion.get("sex") == 1 else "male",
    }


def _build_context(save: dict) -> dict:
    # Index of living children per parent — matches `Actor.get_current_children_count`.
    children_by_parent: dict[int, int] = {}
    for actor in save.get("actors_data", []):
        for parent_id in (actor.get("parent_id_1"), actor.get("parent_id_2")):
            if parent_id:
                children_by_parent[parent_id] = children_by_parent.get(parent_id, 0) + 1
    return {**build_actor_stats_context(save), "children_by_parent": children_by_parent}


def _build_equipment_list(actor: dict, ctx: dict) -> list:
    item_stats = ctx["equipment"]["items"]
    mod_stats = ctx["equipment"]["modifiers"]
    world_time = ctx["world_time"]
    out = []
    for iid in actor.get("saved_items") or []:
        item = ctx["items_by_id"].get(iid)
        if item is None:
            continue
        mods = item.get("modifiers") or []
        ct = item.get("created_time")
        out.append(
            {
                "age": int((world_time - ct) / MONTHS_PER_YEAR) if ct is not None else None,
                "asset_id": item["asset_id"],
                "by": item.get("by"),
                "durability": item.get("durability"),
                "from": item.get("from"),
                "id": iid,
                "kills": item.get("kills", 0),
                "modifiers": sorted(mods),
                "rarity": _equipment_rarity(mods),
                "stats": _equipment_stats(item["asset_id"], mods, item_stats, mod_stats),
            }
        )
    return sorted(out, key=lambda i: i["id"])


def _build_inventory(actor: dict) -> dict:
    items = ((actor.get("inventory") or {}).get("dict") or {}).items()
    return dict(sorted((iid, entry.get("amount", 0)) for iid, entry in items))


def _build_metadata(actor: dict, ctx: dict, save: dict) -> dict:
    sub = ctx["subspecies_by_id"].get(actor.get("subspecies")) or {}
    clan = ctx["clans_by_id"].get(actor.get("clan")) or {}
    language = ctx["languages_by_id"].get(actor.get("language")) or {}
    cities_by_id = index_by_id(save.get("cities", []))
    kingdoms_by_id = index_by_id(save.get("kingdoms", []))
    cultures_by_id = index_by_id(save.get("cultures", []))
    families_by_id = index_by_id(save.get("families", []))
    religions_by_id = index_by_id(save.get("religions", []))
    age_months = ctx["world_time"] - float(actor.get("created_time") or 0)
    ax, ay = actor.get("x"), actor.get("y")
    _, island_lookup = compute_islands_cached(save, CURRENT_SAVE)
    return {
        # `age_overgrowth` (years past lifespan cap) added on top of natural age — WB tooltip shows the sum, mirrored so chronicler sees the same.
        "age": int(age_months / MONTHS_PER_YEAR) + (actor.get("age_overgrowth") or 0),
        "asset_id": actor.get("asset_id"),
        "city": (cities_by_id.get(actor.get("cityID")) or {}).get("name"),
        "clan": clan.get("name"),
        "culture": (cultures_by_id.get(actor.get("culture")) or {}).get("name"),
        "family": (families_by_id.get(actor.get("family")) or {}).get("name"),
        "favorite_food": actor.get("favorite_food"),
        "generation": int(actor.get("generation") or 1),
        # Chronicler-only: id of the land mass (per `geography/info.py`) the actor stands on. `None` on open water, lava or unassigned sand patches.
        "island_id": island_lookup.get((int(ax), int(ay))) if ax is not None and ay is not None else None,
        "kingdom": _resolve_kingdom(actor.get("civ_kingdom_id"), kingdoms_by_id),
        "language": language.get("name"),
        "mass": _compute_mass(actor),
        "name": actor.get("name"),
        "personality": _compute_personality(actor, ctx),
        "profession": _PROFESSIONS.get(actor.get("profession") or 0),
        "religion": (religions_by_id.get(actor.get("religion")) or {}).get("name"),
        "roles": _compute_roles(actor, save),
        "sex": "female" if actor.get("sex") == 1 else "male",
        "subspecies": sub.get("name") or actor.get("subspecies"),
        "x": ax,
        "y": ay,
    }


# Actor's current plot — `actor.plot` points into `save.plots`. Returns `None` when no plot (most actors). Targets → kingdom/alliance names.
def _build_plot(actor: dict, save: dict) -> dict | None:
    plot_id = actor.get("plot")
    if plot_id is None:
        return None
    plot = next((p for p in save.get("plots", []) if p.get("id") == plot_id), None)
    if plot is None:
        return None
    kingdoms_by_id = index_by_id(save.get("kingdoms", []))
    alliances_by_id = index_by_id(save.get("alliances", []))
    return {
        "name": plot.get("name"),
        "progress": round(float(plot.get("progress_current", 0)), 1),
        "started_at": round(float(plot.get("created_time", 0)), 2),
        "target_alliance": (alliances_by_id.get(plot.get("id_target_alliance")) or {}).get("name"),
        "target_kingdom": (kingdoms_by_id.get(plot.get("id_target_kingdom")) or {}).get("name"),
        "type_id": plot.get("plot_type_id"),
    }


def _build_trait_list(trait_ids: list[str], traits_data: dict, narrative: bool) -> list:
    out = []
    for tid in trait_ids or []:
        entry = traits_data.get(tid) or {}
        item: dict = {"id": tid, "stats": entry.get("stats") or {}}
        if narrative:
            for k in ("description", "flavor", "rarity"):
                if k in entry:
                    item[k] = entry[k]
        out.append(dict(sorted(item.items())))
    return sorted(out, key=lambda t: t["id"])


def _compute_mass(actor: dict) -> int | None:
    base = _MASS_BASE.get(actor.get("asset_id") or "")
    if base is None:
        return None
    scale, mult_mass = 0.10, 0.0
    for trait in actor.get("saved_traits") or []:
        mods = _TRAIT_MASS_MODS.get(trait, {})
        scale += mods.get("scale", 0)
        mult_mass += mods.get("multiplier_mass", 0)
    return int((scale / 0.1) * base * (1 + mult_mass))


# `Actor.updateStats` personality: city leaders/kings only → diplomat/administrator/militarist/balanced (diplomacy/stewardship/warfare); `wildcard` never used.
def _compute_personality(actor: dict, ctx: dict) -> str | None:
    if actor.get("profession") not in (_PROFESSION_KING, _PROFESSION_LEADER):
        return None
    snap = compute_actor_stats(actor, ctx)
    diplo, stew, war = snap.get("diplomacy", 0), snap.get("stewardship", 0), snap.get("warfare", 0)
    p, max_val = "balanced", diplo
    if diplo > stew:
        p, max_val = "diplomat", diplo
    elif diplo < stew:
        p, max_val = "administrator", stew
    if war > max_val:
        p = "militarist"
    return p


# Top 3 only — UI hides the rest, no narrative use for "34th out of 114".
def _compute_ranks_in_species(actor: dict, ctx: dict, save: dict) -> dict:
    asset_id = actor.get("asset_id", "")
    cache: dict = {}
    same_species = [a for a in save["actors_data"] if a.get("asset_id") == asset_id]
    peers = [(a["id"], _compute_stats(a, ctx, cache)) for a in same_species]
    own = next(s for aid, s in peers if aid == actor["id"])
    ranks = {}
    for stat, value in sorted(own.items()):
        if stat not in _RANKED_STATS:
            continue
        rank = sum(1 for _, s in peers if s.get(stat, 0) > value) + 1
        if rank <= 3:
            ranks[stat] = rank

    # Age is not in _compute_stats (it's derived from created_time) — rank it separately.
    def actor_age(a: dict) -> int:
        return int((ctx["world_time"] - float(a.get("created_time") or 0)) / MONTHS_PER_YEAR) + (a.get("age_overgrowth") or 0)

    own_age = actor_age(actor)
    age_rank = sum(1 for a in same_species if actor_age(a) > own_age) + 1
    if age_rank <= 3:
        ranks["age"] = age_rank
    return dict(sorted(ranks.items()))


def _compute_roles(actor: dict, save: dict) -> list[str]:
    actor_id = actor.get("id")
    checks = {
        "alliance_founder": any(a.get("founder_actor_id") == actor_id for a in save.get("alliances", [])),
        "army_captain": any(army.get("id_captain") == actor_id for army in save.get("armies", [])),
        "clan_chief": any(c.get("chief_id") == actor_id for c in save.get("clans", [])),
        "clan_founder": any(c.get("founder_actor_id") == actor_id for c in save.get("clans", [])),
        "culture_creator": any(c.get("creator_id") == actor_id for c in save.get("cultures", [])),
        "family_alpha": any(f.get("alpha_id") == actor_id for f in save.get("families", [])),
        "family_founder": any(f.get("main_founder_id_1") == actor_id or f.get("main_founder_id_2") == actor_id for f in save.get("families", [])),
        "language_creator": any(lang.get("creator_id") == actor_id for lang in save.get("languages", [])),
        "religion_creator": any(r.get("creator_id") == actor_id for r in save.get("religions", [])),
        "village_founder": any(c.get("founder_id") == actor_id for c in save.get("cities", [])),
    }
    return [role for role in _ROLE_ORDER if checks[role]]


# `compute_actor_stats` returns the cleaned pipeline output — we append always-surface counters here (chronicler expects them even at 0).
def _compute_stats(actor: dict, ctx: dict, subspecies_base_cache: dict | None = None) -> dict:
    cleaned = compute_actor_stats(actor, ctx, subspecies_base_cache)
    if not cleaned:
        return {}
    cleaned.update(
        {
            "births": int(actor.get("births") or 0),
            "children": ctx["children_by_parent"].get(actor.get("id"), 0),
            # Current `health`/`mana`/`stamina` (vs `*_max`); `happiness`/`nutrition` live (no max). WB happiness: -100→+100, UI shows (raw+100)/2 as 0–100%.
            "happiness": (int(actor.get("happiness") or 0) + 100) * 100 // 200,
            "health": int(actor.get("health") or 0),
            "kills": int(actor.get("kills") or 0),
            # WB displays level 1 as the floor, even when the raw save field is absent / 0.
            "level": max(int(actor.get("level") or 0), 1),
            "loot": int(actor.get("loot") or 0),
            "mana": int(actor.get("mana") or 0),
            "money": int(actor.get("money") or 0),
            "nutrition": int(actor.get("nutrition") or 0),
            "renown": int(actor.get("renown") or 0),
            "stamina": int(actor.get("stamina") or 0),
        }
    )
    return dict(sorted(cleaned.items()))


def _equipment_rarity(modifiers: list[str]) -> str:
    max_level = max((int(m.group(1)) for m in (_LEVEL_RE.search(x) for x in modifiers) if m), default=0)
    if max_level >= 5:
        return "Legendary"
    if max_level >= 4:
        return "Epic"
    if max_level >= 3:
        return "Rare"
    return "Normal"


def _equipment_stats(asset_id: str, modifiers: list[str], item_stats: dict, mod_stats: dict) -> dict:
    out = dict(item_stats.get(asset_id, {}))
    for mod in modifiers:
        for k, v in mod_stats.get(mod, {}).items():
            out[k] = out.get(k, 0) + v
    result = {}
    for k, v in out.items():
        if isinstance(v, float):
            v = round(v, 4)
            if v.is_integer():
                v = int(v)
        if v:
            result[k] = v
    return dict(sorted(result.items()))


# Register this actor (species + sex) in the reader's person registry, for the `[p id Nom]` tag.
def _register_person(actor: dict) -> None:
    register_entity(
        _REGISTRY,
        str(actor.get("id")),
        {
            "asset_id": actor.get("asset_id"),
            "sex": "female" if actor.get("sex") == 1 else "male",
        },
    )


def _resolve_kingdom(kingdom_id: int | None, kingdoms_by_id: dict) -> dict | None:
    if kingdom_id is None:
        return None
    kingdom = kingdoms_by_id.get(kingdom_id)
    if kingdom is None:
        return None
    return {"id": kingdom_id, "name": kingdom.get("name")}


def main(argv: list[str]) -> int:
    if not argv:
        print("usage: info.py <id> [sections] — see tools/tools.md", file=sys.stderr)
        return 2
    try:
        actor_id = int(argv[0])
    except ValueError:
        print(f"invalid id: {argv[0]}", file=sys.stderr)
        return 1
    try:
        sections = parse_sections(argv[1] if len(argv) > 1 else None, _ALL_SECTIONS)
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 2
    save = load_save()
    actor = next((a for a in save["actors_data"] if a.get("id") == actor_id), None)
    if actor is None:
        print(f"unknown actor: {actor_id}", file=sys.stderr)
        return 1
    _register_person(actor)
    ctx = _build_context(save)
    sub = ctx["subspecies_by_id"].get(actor.get("subspecies"))
    if sub is None:
        print(f"no subspecies for actor {actor_id}", file=sys.stderr)
        return 1

    out: dict = {}
    if "best_friend" in sections:
        out["best_friend"] = _build_companion(actor, ctx, save, "best_friend_id")
    if "creature_traits" in sections:
        out["creature_traits"] = _build_trait_list(actor.get("saved_traits") or [], ctx["creature_traits"], narrative=True)
    if "equipment" in sections:
        out["equipment"] = _build_equipment_list(actor, ctx)
    if "inventory" in sections:
        out["inventory"] = _build_inventory(actor)
    if "lover" in sections:
        out["lover"] = _build_companion(actor, ctx, save, "lover")
    if "metadata" in sections:
        out["metadata"] = _build_metadata(actor, ctx, save)
    if "plot" in sections:
        out["plot"] = _build_plot(actor, save)
    if "ranks_in_species" in sections:
        out["ranks_in_species"] = _compute_ranks_in_species(actor, ctx, save)
    if "stats" in sections:
        out["stats"] = _compute_stats(actor, ctx)

    emit(out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
