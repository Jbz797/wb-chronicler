#!/usr/bin/env python3

# User-facing docs (usage, available sections) live in `tools/tools.md`. Notes below are for maintainers — algorithm references, gotchas, source pointers.

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))

from actor_stats import build_actor_stats_context, compute_actor_stats
from islands import compute_islands_cached
from shared import (
    PROFESSION_KING,
    PROFESSION_LEADER,
    UNITS_PER_YEAR,
    actor_age,
    age_thresholds,
    build_trait_ids,
    build_trait_list,
    civic_building_ids,
    competition_ranks,
    emit,
    entity_ref,
    equipment_entry,
    equipment_rarity,
    has_emotions,
    index_by_id,
    is_aboard,
    life_stage,
    light,
    load_data,
    load_save,
    parse_sections,
    resolve_profession,
    sex_label,
    take_chapter,
)

_ALL_SECTIONS = ("companions", "equipment", "inventory", "metadata", "plot", "ranks_in_species", "stats", "traits")
_CLAN_CHIEF_ROLE = ("chief_id", "clans", "past_chiefs")  # Chieftainship is a role, not a profession (a king can be both) — hence its own tenure field.

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

_RARITY_POINTS = {"Epic": 3, "Legendary": 4, "Normal": 1, "Rare": 2}  # WB's own ladder, weighing a carried arsenal into the « puissance » gauge.

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
_UNITS_PER_MONTH = UNITS_PER_YEAR / 12  # WB counts 5 `world_time` units to the month, twelve to the year


# One home for every index the sections read, so no caller rolls its own. Actor loop = one pass: id, asset_id, children-per-parent (`get_current_children_count`).
def _build_context(save: dict, save_path: Path) -> dict:
    actors_by_asset: dict[str, list[dict]] = {}
    actors_by_id: dict[int, dict] = {}
    children_by_parent: dict[int, int] = {}
    for actor in save.get("actors_data") or []:
        actors_by_id[actor["id"]] = actor
        actors_by_asset.setdefault(actor.get("asset_id"), []).append(actor)
        # Unrolled: the pair literal rebuilt a tuple per actor. A `Counter` here would read cleaner but measures some 60 % slower than `dict.get` on this pattern.
        if parent := actor.get("parent_id_1"):
            children_by_parent[parent] = children_by_parent.get(parent, 0) + 1
        if parent := actor.get("parent_id_2"):
            children_by_parent[parent] = children_by_parent.get(parent, 0) + 1
    return {  # `subspecies_base_cache`: the per-subspecies base of `compute_actor_stats`, computed once, reused run-wide — it cuts a ranking four- to eightfold.
        **build_actor_stats_context(save),
        "actors_by_asset": actors_by_asset,
        "actors_by_id": actors_by_id,
        "alliances_by_id": index_by_id(save.get("alliances") or []),
        # Built structures only: WB files trees, wheat and vegetation under `buildings` too, and nobody steps « inside » a field.
        "buildings_by_tile": {(b.get("mainX"), b.get("mainY")): b for b in save.get("buildings") or [] if b.get("asset_id") in civic_building_ids()},
        "children_by_parent": children_by_parent,
        "cities_by_id": index_by_id(save.get("cities") or []),
        "cultures_by_id": index_by_id(save.get("cultures") or []),
        "families_by_id": index_by_id(save.get("families") or []),
        "kingdoms_by_id": index_by_id(save.get("kingdoms") or []),
        "pact_of": {kid: a["id"] for a in save.get("alliances") or [] for kid in a.get("kingdoms") or []},  # a realm sits in one pact at most
        "religions_by_id": index_by_id(save.get("religions") or []),
        "save_path": save_path,  # islands cache key — must be the loaded save's real path (live or a chapter's map.wbox), not the module default.
        "subspecies_base_cache": {},
    }


# Each carried item with provenance (`by`/`from`), wear, kill count and its aggregated stats — sorted by item id for stable output.
def _build_equipment_list(actor: dict, ctx: dict) -> list:
    item_stats = ctx["equipment"]["items"]
    mod_stats = ctx["equipment"]["modifiers"]
    world_time = ctx["world_time"]
    items = (ctx["items_by_id"].get(iid) for iid in actor.get("saved_items") or [])
    return sorted((equipment_entry(i, item_stats, mod_stats, world_time, described=True) for i in items if i is not None), key=lambda i: i["id"])


# Resource bag → `{resource_id: amount}`, heaviest stack first then alphabetical — the raw save nests it as `inventory.dict.<id>.amount`.
def _build_inventory(actor: dict) -> dict:
    items = ((actor.get("inventory") or {}).get("dict") or {}).items()
    return dict(sorted(((iid, entry.get("amount", 0)) for iid, entry in items), key=lambda kv: (-kv[1], kv[0])))


# The actor's identity card: civic ties (city/kingdom/culture/family…), body (age tier, mass), posts held and their tenure.
def _build_metadata(actor: dict, ctx: dict, save: dict) -> dict:
    snap = compute_actor_stats(actor, ctx, ctx["subspecies_base_cache"])

    lifespan = snap.get("lifespan", 0)

    age = actor_age(actor, ctx["world_time"])
    age_adult, age_breeding = age_thresholds(lifespan)
    ax, ay = actor.get("x"), actor.get("y")
    tile = (int(ax), int(ay)) if ax is not None and ay is not None else None  # WB writes both coordinates or neither, so one guard serves every lookup below
    profession = resolve_profession(actor, save)

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
        # A pact reaches him through his crown, WB tying one to a realm and never to a soul — the ref lets `new.py` fan out on it like any other body.
        "alliance": entity_ref(ctx["pact_of"].get(actor.get("civ_kingdom_id")), ctx["alliances_by_id"]),
        "asset_id": actor.get("asset_id"),
        "can_reproduce": can_reproduce,
        "city": entity_ref(actor.get("cityID"), ctx["cities_by_id"]),
        "clan": entity_ref(actor.get("clan"), ctx["clans_by_id"]),  # a ref, not a bare name: `clan/info.py <id>` can be called on it, as on `family`
        "clan_chief_years": _resolve_tenure(actor, _CLAN_CHIEF_ROLE, save, ctx["world_time"]),  # Chronicler-only: a role, so it stacks with `tenure_years`.
        "culture": entity_ref(actor.get("culture"), ctx["cultures_by_id"]),  # a ref like `clan`: `culture/info.py <id>` reads the customs it was raised in
        "family": entity_ref(actor.get("family"), ctx["families_by_id"]),  # a ref, not a bare name: `family/info.py <id>` can be called on it
        "favorite_food": actor.get("favorite_food"),
        "gen": int(actor.get("generation") or 1),  # WB counts a first child 2, so a parentless founder is its 1 — a default the save omits
        **({"home": home} if (home := actor.get("homeBuildingID")) else {}),  # Chronicler-only: WB names no roof — `ground/info.py <id>` takes the bare id
        "id": actor.get("id"),  # Actor id — lets the favourite's `<app-person-tag>` resolve its chip from the person registry like every other person ref.
        # Chronicler-only: enlistment is in the resident's own city army or nowhere, and never automatic — `false` marks a fighter left out.
        **({"in_army": bool(actor.get("army"))} if profession in ("army_captain", "warrior") or actor.get("army") else {}),
        # Standing on a building's own tile, which is as close as a save comes to saying « indoors »: WB keeps `is_inside_building` on the runtime actor alone.
        **({"in_building": {"asset_id": inside.get("asset_id"), "id": inside["id"]}} if (inside := ctx["buildings_by_tile"].get(tile)) else {}),
        "island_id": island_lookup.get(tile) if tile else None,  # Chronicler-only: land mass (geography/info.py).
        "job": profession,
        "kingdom": entity_ref(actor.get("civ_kingdom_id"), ctx["kingdoms_by_id"]),
        "language": entity_ref(actor.get("language"), ctx["languages_by_id"]),  # a ref, not a bare name: `language/info.py <id>` reads the tongue it answers in
        "life_stage": life_stage(age, age_adult, lifespan),
        "mass": _compute_mass(actor, ctx),
        "name": actor.get("name"),  # absent, not a placeholder, where WB never named them — `emit` strips it and the panels drop the row
        "personality": _compute_personality(actor, snap),
        "religion": entity_ref(actor.get("religion"), ctx["religions_by_id"]),  # a ref, not a bare name: `religion/info.py <id>` reads the creed it holds
        "roles": _compute_roles(actor, save),
        "sex": sex_label(actor),
        "subspecies": entity_ref(actor.get("subspecies"), ctx["subspecies_by_id"]),  # a ref, not a bare name: the chapter panel resolves its tag from the id
        "tenure_years": _resolve_tenure(actor, _TENURE_ROLES.get(profession or ""), save, ctx["world_time"]),
        # WB `isInsideSomething`: a save keeps the boat half, never the building. A plain ref, souls boarding transports alone — `boat/info.py <id>` spells it out.
        **({"transport": entity_ref(actor.get("transportID"), ctx["actors_by_id"])} if is_aboard(actor) else {}),
        "x": ax,
        "y": ay,
    }


# Actor's current plot — `actor.plot` points into `save.plots`. Returns `None` when no plot (most actors). Targets → kingdom/alliance names.
def _build_plot(actor: dict, ctx: dict, save: dict) -> dict | None:
    plot_id = actor.get("plot")
    if plot_id is None:
        return None
    plot = next((p for p in save.get("plots") or [] if p.get("id") == plot_id), None)
    if plot is None:
        return None
    type_id = plot.get("plot_type_id")
    kind = load_data("plots.json").get(type_id) or {}
    return {
        # Months, not years: a scheme ripens well inside one. WB never caps the gauge either, so a ripe plot reads past 100.
        "months": int((ctx["world_time"] - float(plot.get("created_time") or 0)) / _UNITS_PER_MONTH),
        "progress": round(float(plot.get("progress_current") or 0), 1),
        "target_alliance": entity_ref(plot.get("id_target_alliance"), ctx["alliances_by_id"]),
        "target_city": entity_ref(plot.get("id_target_city"), ctx["cities_by_id"]),  # the rites strike a settlement where a war strikes a crown
        "target_kingdom": entity_ref(plot.get("id_target_kingdom"), ctx["kingdoms_by_id"]),
        # The scheme's kind, as a book carries its genre: WB's English for the chronicler, the id for the panel — the save's own `name` is that label localised.
        "type": {"description": kind.get("description"), "id": type_id, "name": kind.get("name")},
    }


# What the soul was born with, off WB's creature library — summarised to each trait and its rarity, its effect and flavour only when the section is named.
def _build_traits(actor: dict, ctx: dict, detailed: bool) -> dict | list[dict]:
    sworn, library = actor.get("saved_traits") or [], ctx["creature_traits"]
    return build_trait_list(sworn, library) if detailed else light({"ids": build_trait_ids(sworn, library, "rarity")})


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
    peers = [_compute_stats(a, ctx) for a in same_species]
    own = next(s for a, s in zip(same_species, peers) if a["id"] == actor["id"])

    getters = {stat: lambda s, st=stat: s.get(st, 0) for stat in _RANKED_STATS if stat in own}  # `st=stat` binds now, else every lambda reads the last one
    ranks = competition_ranks(own, peers, getters)
    # Age is not in `_compute_stats` (derived from `created_time`) — ranked separately, against the raw actors.
    ranks.update(competition_ranks(actor, same_species, {"age": lambda a: actor_age(a, ctx["world_time"])}))
    return dict(sorted(ranks.items()))


# Active/historical roles in `_ROLE_ORDER` — each is a linear probe of its collection (all tiny).
def _compute_roles(actor: dict, save: dict) -> list[str]:
    actor_id = actor.get("id")
    checks = {
        "alliance_founder": any(a.get("founder_actor_id") == actor_id for a in save.get("alliances") or []),
        "clan_chief": any(c.get("chief_id") == actor_id for c in save.get("clans") or []),
        "clan_founder": any(c.get("founder_actor_id") == actor_id for c in save.get("clans") or []),
        "culture_creator": any(c.get("creator_id") == actor_id for c in save.get("cultures") or []),
        "family_alpha": any(f.get("alpha_id") == actor_id for f in save.get("families") or []),
        "family_founder": any(f.get("main_founder_id_1") == actor_id or f.get("main_founder_id_2") == actor_id for f in save.get("families") or []),
        "language_creator": any(lang.get("creator_id") == actor_id for lang in save.get("languages") or []),
        "religion_creator": any(r.get("creator_id") == actor_id for r in save.get("religions") or []),
        "village_founder": any(c.get("founder_id") == actor_id for c in save.get("cities") or []),
    }
    return [role for role in _ROLE_ORDER if checks[role]]


# `compute_actor_stats` returns the cleaned pipeline output — we append always-surface counters here (chronicler expects them even at 0).
def _compute_stats(actor: dict, ctx: dict) -> dict:
    cleaned = compute_actor_stats(actor, ctx, ctx["subspecies_base_cache"])
    if not cleaned:
        return {}
    cleaned.update(
        {
            # WB happiness runs -100..+100, surfaced as the 0-100 % the UI shows — and dropped whole where the biology has no `amygdala`, feeling nothing at all.
            **({"happiness": (int(actor.get("happiness") or 0) + 100) // 2} if has_emotions(actor, ctx["subspecies_by_id"]) else {}),
            "births": int(actor.get("births") or 0),
            "children": ctx["children_by_parent"].get(actor.get("id"), 0),
            "equipment_power": _equipment_power(actor, ctx),
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
    return cleaned  # left as inserted: `render` sorts every record-shaped dict on the way out, and a ranking's peers are only ever read by key


# Sum of `_RARITY_POINTS` over carried items — the « puissance d'équipement » gauge.
def _equipment_power(actor: dict, ctx: dict) -> int:
    items = ctx["items_by_id"]
    total = 0
    for iid in actor.get("saved_items") or []:
        item = items.get(iid)
        if item:
            total += _RARITY_POINTS[equipment_rarity(item.get("modifiers") or [])]
    return total


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
        print(f"✗ invalid id: {argv[0]}", file=sys.stderr)  # a malformed call, like a bad section — not an entity that happens to be missing
        return 2

    requested = argv[1] if len(argv) > 1 else None
    try:
        sections = parse_sections(requested, _ALL_SECTIONS)
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 2
    save = load_save(save_path)
    ctx = _build_context(save, save_path)
    actor = ctx["actors_by_id"].get(actor_id)
    if actor is None:
        print(f"✗ unknown actor: {actor_id}", file=sys.stderr)
        return 1
    if ctx["subspecies_by_id"].get(actor.get("subspecies")) is None:  # every stat is derived from the biology's base, so there is nothing to report without it
        print(f"✗ no subspecies for actor {actor_id}", file=sys.stderr)
        return 1

    out: dict = {}
    if "companions" in sections:  # both attachments as plain refs — `emit` drops whichever is unset or dead, and the section itself when the actor has neither
        by_id = ctx["actors_by_id"]
        out["companions"] = {"best_friend": entity_ref(actor.get("best_friend_id"), by_id), "lover": entity_ref(actor.get("lover"), by_id)}
    if "equipment" in sections:
        out["equipment"] = _build_equipment_list(actor, ctx)
    if "inventory" in sections:
        out["inventory"] = _build_inventory(actor)
    if "metadata" in sections:
        out["metadata"] = _build_metadata(actor, ctx, save)
    if "plot" in sections:
        out["plot"] = _build_plot(actor, ctx, save)
    if "ranks_in_species" in sections:
        out["ranks_in_species"] = _compute_ranks_in_species(actor, ctx)
    if "stats" in sections:
        out["stats"] = _compute_stats(actor, ctx)
    if "traits" in sections:
        out["traits"] = _build_traits(actor, ctx, detailed=requested not in (None, "full"))

    emit(out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
