#!/usr/bin/env python3

# User-facing docs (usage, available sections) live in `tools/tools.md`. Notes below are for maintainers — algorithm references, gotchas, source pointers.

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "geography"))
from actor_stats import build_actor_stats_context, compute_actor_stats
from islands import compute_islands_cached
from shared import (
    PROFESSION_KING,
    PROFESSION_LEADER,
    UNITS_PER_YEAR,
    age_thresholds,
    competition_ranks,
    emit,
    entity_ref,
    index_by_id,
    life_stage,
    load_save,
    parse_sections,
    resolve_profession,
    sex_label,
    take_chapter,
)

_ALL_SECTIONS = ("best_friend", "creature_traits", "equipment", "inventory", "lover", "metadata", "plot", "ranks_in_species", "stats")
_CLAN_CHIEF_ROLE = ("chief_id", "clans", "past_chiefs")  # Chieftainship is a role, not a profession (a king can be both) — hence its own tenure field.
_LEVEL_RE = re.compile(r"(\d+)$")

# Competition rank (1,2,2,4) per stat among `asset_id` peers. Mostly maps to `RankedStatKind` (types.ts; UI: RankedStatComponent). `births` chronicler-only.
_RANKED_STATS = {
    "armor",
    "attack_speed",
    "birth_rate",
    "births",
    "children",
    "critical_chance",
    "damage",
    "diplomacy",
    "equipment_power",
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

_RARITY_POINTS = {"Epic": 3, "Legendary": 4, "Normal": 1, "Rare": 2}  # Rarity weights for equipment power (Normal 1 → Legendary 4).

# UI order: active roles (chief, alpha) before historical foundations (creators before founders). `army_captain` is a `profession`, not a role.
_ROLE_ORDER = (
    "clan_chief",
    "family_alpha",
    "culture_creator",
    "language_creator",
    "religion_creator",
    "alliance_founder",
    "clan_founder",
    "village_founder",
    "family_founder",
)

# Profession → (current-holder field, save collection, history list). Every post keeps a `past_*` history whose last entry is the sitting holder's start.
_TENURE_ROLES = {
    "army_captain": ("id_captain", "armies", "past_captains"),
    "king": ("kingID", "kingdoms", "past_rulers"),
    "leader": ("leaderID", "cities", "past_rulers"),
}

# Mass deltas from traits — only `fat`, `giant`, `tiny`, `agile` in the DLL.
_TRAIT_MASS_MODS = {
    "agile": {"scale": -0.01},
    "fat": {"multiplier_mass": 0.30, "scale": 0.02},
    "giant": {"scale": 0.05},
    "tiny": {"scale": -0.02},
}

_UNDEAD_SPECIES = frozenset({"skeleton"})  # Fail `isAlive`/`needsFood`: never breed, never hunger (no diet).


# Lover / best friend snapshot — the handful of fields the companion card shows. `None` when unset or when the companion has died.
def _build_companion(actor: dict, ctx: dict, id_field: str) -> dict | None:
    companion_id = actor.get(id_field)
    if companion_id is None:
        return None
    companion = ctx["actors_by_id"].get(companion_id)
    if companion is None:
        return None
    snap = compute_actor_stats(companion, ctx, ctx["subspecies_base_cache"])
    age_units = ctx["world_time"] - float(companion.get("created_time") or 0)
    return {
        "age": int(age_units / UNITS_PER_YEAR) + (companion.get("age_overgrowth") or 0),
        "health_max": snap.get("health_max", 0),
        "id": companion_id,
        "level": snap.get("level", 0),
        "money": snap.get("money", 0),
        "name": companion.get("name") or f"#{companion_id}",
        "renown": snap.get("renown", 0),
        "sex": sex_label(companion),
    }


# Single pass over actors: id / asset_id lookups + children-per-parent (matches `Actor.get_current_children_count`).
def _build_context(save: dict, save_path: Path) -> dict:
    actors_by_asset: dict[str, list[dict]] = {}
    actors_by_id: dict[int, dict] = {}
    children_by_parent: dict[int, int] = {}
    for actor in save.get("actors_data", []):
        actors_by_id[actor["id"]] = actor
        actors_by_asset.setdefault(actor.get("asset_id"), []).append(actor)
        for parent_id in (actor.get("parent_id_1"), actor.get("parent_id_2")):
            if parent_id:
                children_by_parent[parent_id] = children_by_parent.get(parent_id, 0) + 1
    # `subspecies_base_cache`: heavy `compute_actor_stats` base computed once per subspecies, reused run-wide.
    return {
        **build_actor_stats_context(save),
        "actors_by_asset": actors_by_asset,
        "actors_by_id": actors_by_id,
        "children_by_parent": children_by_parent,
        "save_path": save_path,  # islands cache key — must be the loaded save's real path (live or a chapter's map.wbox), not the module default.
        "subspecies_base_cache": {},
    }


# Each carried item with provenance (`by`/`from`), wear, kill count and its aggregated stats — sorted by item id for stable output.
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
                "age": int((world_time - ct) / UNITS_PER_YEAR) if ct is not None else None,
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


# Resource bag → `{resource_id: amount}`, sorted — the raw save nests it as `inventory.dict.<id>.amount`.
def _build_inventory(actor: dict) -> dict:
    items = ((actor.get("inventory") or {}).get("dict") or {}).items()
    return dict(sorted((iid, entry.get("amount", 0)) for iid, entry in items))


# The actor's identity card: civic ties (city/kingdom/culture/family…), body (age tier, mass), posts held and their tenure.
def _build_metadata(actor: dict, ctx: dict, save: dict) -> dict:
    snap = compute_actor_stats(actor, ctx, ctx["subspecies_base_cache"])

    age_units = ctx["world_time"] - float(actor.get("created_time") or 0)
    lifespan = snap.get("lifespan", 0)

    age = int(age_units / UNITS_PER_YEAR) + (actor.get("age_overgrowth") or 0)  # `age_overgrowth` (years past the lifespan cap) added on top, like the WB tooltip.
    age_adult, age_breeding = age_thresholds(lifespan)
    ax, ay = actor.get("x"), actor.get("y")
    cities_by_id = index_by_id(save.get("cities", []))
    clan = ctx["clans_by_id"].get(actor.get("clan")) or {}
    cultures_by_id = index_by_id(save.get("cultures", []))
    families_by_id = index_by_id(save.get("families", []))
    kingdoms_by_id = index_by_id(save.get("kingdoms", []))
    language = ctx["languages_by_id"].get(actor.get("language")) or {}
    profession = resolve_profession(actor, save)
    religions_by_id = index_by_id(save.get("religions", []))
    sub = ctx["subspecies_by_id"].get(actor.get("subspecies")) or {}

    # `canBreed`/`canMakeBabies` gates: alive, breeding age, not infertile, below offspring cap, fed. Transients (pregnancy, afterglow) aren't in the save.
    can_reproduce = (
        actor.get("asset_id") not in _UNDEAD_SPECIES
        and age >= age_breeding
        and "infertile" not in (actor.get("saved_traits") or [])
        and ctx["children_by_parent"].get(actor.get("id"), 0) < int(snap.get("max_children") or 0)
        and int(actor.get("nutrition") or 0) > 0
    )

    _, island_lookup = compute_islands_cached(save, ctx["save_path"])

    return {
        "age": age,
        "asset_id": actor.get("asset_id"),
        "can_reproduce": can_reproduce,
        "city": entity_ref(actor.get("cityID"), cities_by_id),
        "clan": clan.get("name"),
        "clan_chief_years": _resolve_tenure(actor, _CLAN_CHIEF_ROLE, save, ctx["world_time"]),  # Chronicler-only: a role, so it stacks with `tenure_years`.
        "culture": (cultures_by_id.get(actor.get("culture")) or {}).get("name"),
        "family": (families_by_id.get(actor.get("family")) or {}).get("name"),
        "favorite_food": actor.get("favorite_food"),
        "generation": int(actor.get("generation") or 1),
        "id": actor.get("id"),  # Actor id — lets the favourite's `<app-person-tag>` resolve its chip from the person registry like every other person ref.
        "island_id": island_lookup.get((int(ax), int(ay))) if ax is not None and ay is not None else None,  # Chronicler-only: land mass (geography/info.py).
        "kingdom": entity_ref(actor.get("civ_kingdom_id"), kingdoms_by_id),
        "language": language.get("name"),
        "life_stage": life_stage(age, age_adult, lifespan),
        "mass": _compute_mass(actor, ctx),
        "name": actor.get("name") or f"#{actor.get('id')}",  # `#id` fallback like every other name field — WB leaves plenty of actors unnamed.
        "personality": _compute_personality(actor, snap),
        "profession": profession,
        "religion": (religions_by_id.get(actor.get("religion")) or {}).get("name"),
        "roles": _compute_roles(actor, save),
        "sex": sex_label(actor),
        "subspecies": sub.get("name") or actor.get("subspecies"),
        "tenure_years": _resolve_tenure(actor, _TENURE_ROLES.get(profession or ""), save, ctx["world_time"]),
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
        "target_alliance": entity_ref(plot.get("id_target_alliance"), alliances_by_id),
        "target_kingdom": entity_ref(plot.get("id_target_kingdom"), kingdoms_by_id),
        "type_id": plot.get("plot_type_id"),
    }


# Trait entries with their stats + narrative fields (description/flavor/rarity) when the data carries them — sorted by trait id.
def _build_trait_list(trait_ids: list[str], traits_data: dict) -> list:
    out = []
    for tid in trait_ids or []:
        entry = traits_data.get(tid) or {}
        item: dict = {"id": tid, "stats": entry.get("stats") or {}}
        for k in ("description", "flavor", "rarity"):
            if k in entry:
                item[k] = entry[k]
        out.append(dict(sorted(item.items())))
    return sorted(out, key=lambda t: t["id"])


# `Actor.getMassKG`: (target_scale / 0.1) × base mass × (1 + Σ trait multiplier_mass). Base mass = the asset's `mass_2` (kg) from `species.json`; `None` if massless.
def _compute_mass(actor: dict, ctx: dict) -> int | None:
    base = ((ctx["species_data"].get(actor.get("asset_id")) or {}).get("stats") or {}).get("mass_2")
    if base is None:
        return None
    scale, mult_mass = 0.10, 0.0
    for trait in actor.get("saved_traits") or []:
        mods = _TRAIT_MASS_MODS.get(trait, {})
        scale += mods.get("scale", 0)
        mult_mass += mods.get("multiplier_mass", 0)
    return int((scale / 0.1) * base * (1 + mult_mass))


# `Actor.updateStats` personality: city leaders/kings only → diplomat/administrator/militarist/balanced (diplomacy/stewardship/warfare); `wildcard` never used.
def _compute_personality(actor: dict, snap: dict) -> str | None:
    if actor.get("profession") not in (PROFESSION_KING, PROFESSION_LEADER):
        return None
    diplo, stew, war = snap.get("diplomacy", 0), snap.get("stewardship", 0), snap.get("warfare", 0)
    p, max_val = "balanced", diplo
    if diplo > stew:
        p, max_val = "diplomat", diplo
    elif diplo < stew:
        p, max_val = "administrator", stew
    if war > max_val:
        p = "militarist"
    return p


# Top 3 only — UI hides the rest, no narrative use for "34th out of 114". Zero-skip like the city/kingdom ranks: no podium for a stat the actor has none of.
def _compute_ranks_in_species(actor: dict, ctx: dict) -> dict:
    same_species = ctx["actors_by_asset"].get(actor.get("asset_id"), [])
    peers = [_compute_stats(a, ctx, ctx["subspecies_base_cache"]) for a in same_species]
    own = next(s for a, s in zip(same_species, peers) if a["id"] == actor["id"])

    def actor_age(a: dict) -> int:
        return int((ctx["world_time"] - float(a.get("created_time") or 0)) / UNITS_PER_YEAR) + (a.get("age_overgrowth") or 0)

    getters = {stat: (lambda st: lambda s: s.get(st, 0))(stat) for stat in _RANKED_STATS if stat in own}
    ranks = competition_ranks(own, peers, getters)
    # Age is not in `_compute_stats` (derived from `created_time`) — ranked separately, against the raw actors.
    ranks.update(competition_ranks(actor, same_species, {"age": actor_age}))
    return dict(sorted(ranks.items()))


# Active/historical roles in `_ROLE_ORDER` — each is a linear probe of its collection (all tiny).
def _compute_roles(actor: dict, save: dict) -> list[str]:
    actor_id = actor.get("id")
    checks = {
        "alliance_founder": any(a.get("founder_actor_id") == actor_id for a in save.get("alliances", [])),
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
            "equipment_power": _equipment_power(actor, ctx),
            "happiness": (int(actor.get("happiness") or 0) + 100) // 2,  # WB happiness runs -100..+100; surfaced as the 0-100% the UI shows.
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


# Sum of `_RARITY_POINTS` over carried items — the « puissance d'équipement » gauge.
def _equipment_power(actor: dict, ctx: dict) -> int:
    items = ctx["items_by_id"]
    total = 0
    for iid in actor.get("saved_items") or []:
        item = items.get(iid)
        if item:
            total += _RARITY_POINTS[_equipment_rarity(item.get("modifiers") or [])]
    return total


# Rarity = the highest numbered suffix among an item's modifiers (`…_5` ⇒ Legendary) — mirrors WB's enchant tiers.
def _equipment_rarity(modifiers: list[str]) -> str:
    max_level = max((int(m.group(1)) for m in (_LEVEL_RE.search(x) for x in modifiers) if m), default=0)
    if max_level >= 5:
        return "Legendary"
    if max_level >= 4:
        return "Epic"
    if max_level >= 3:
        return "Rare"
    return "Normal"


# Item base stats + its modifiers' bonuses, floats trimmed to 4 decimals (ints when whole), zeros dropped.
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


# Years the actor has held `role` = (holder field, collection, history). `None` unless the history's last entry still names them.
def _resolve_tenure(actor: dict, role: tuple[str, str, str] | None, save: dict, world_time: float) -> int | None:
    if role is None:
        return None
    holder_field, collection, history = role
    actor_id = actor.get("id")
    for record in save.get(collection, []):
        if record.get(holder_field) != actor_id:
            continue
        entries = record.get(history) or []
        if entries and entries[-1].get("id") == actor_id:
            return int((world_time - float(entries[-1].get("timestamp_ago") or 0)) / UNITS_PER_YEAR)
    return None


def main(argv: list[str]) -> int:
    save_path, argv, _ = take_chapter(argv)
    if not argv:
        print("usage: info.py <id> [sections] [C<n>] — see tools/tools.md", file=sys.stderr)
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
    save = load_save(save_path)
    ctx = _build_context(save, save_path)
    actor = ctx["actors_by_id"].get(actor_id)
    if actor is None:
        print(f"unknown actor: {actor_id}", file=sys.stderr)
        return 1
    sub = ctx["subspecies_by_id"].get(actor.get("subspecies"))
    if sub is None:
        print(f"no subspecies for actor {actor_id}", file=sys.stderr)
        return 1

    out: dict = {}
    if "best_friend" in sections:
        out["best_friend"] = _build_companion(actor, ctx, "best_friend_id")
    if "creature_traits" in sections:
        out["creature_traits"] = _build_trait_list(actor.get("saved_traits") or [], ctx["creature_traits"])
    if "equipment" in sections:
        out["equipment"] = _build_equipment_list(actor, ctx)
    if "inventory" in sections:
        out["inventory"] = _build_inventory(actor)
    if "lover" in sections:
        out["lover"] = _build_companion(actor, ctx, "lover")
    if "metadata" in sections:
        out["metadata"] = _build_metadata(actor, ctx, save)
    if "plot" in sections:
        out["plot"] = _build_plot(actor, save)
    if "ranks_in_species" in sections:
        out["ranks_in_species"] = _compute_ranks_in_species(actor, ctx)
    if "stats" in sections:
        out["stats"] = _compute_stats(actor, ctx, ctx["subspecies_base_cache"])

    emit(out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
