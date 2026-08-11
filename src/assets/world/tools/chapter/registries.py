#!/usr/bin/env python3

# Builds a chapter's `{cities,families,kingdoms,persons}.json` registries under `saves/C<n>/` — the tag visuals (+ last-known names) the UI and chronicler resolve
# `[c/k/p id]` tags from; the UI composes crowns and banners on canvas from them. Carried forward from C<n-1> (dead kept), rebuilt whole, reproducible.
# `ensure()` is what the bootstrap (`chapter/new.py`) calls; `registries.py C<n> [--force]` (re)builds one chapter standalone — a dev tool, not in `tools.md`.

import json
import sys
from collections import Counter, defaultdict
from functools import cache
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))

from shared import SAVES_DIR, city_score_ranks, index_by_id, is_boat, kingdom_score_ranks, load_data, load_save, resolve_profession, sex_label

_REALM_FALLBACK_HUE = "#B0B0B0"  # WB `Toolbox.color_grey` — worn by a realm whose palette WB never shipped, the only case the name hue can miss.
_REGISTRIES = ("cities", "families", "kingdoms", "persons")
_SIZE_TIERS = (5, 15, 40, 100, 200, 500)  # Population upper bounds → settlement tier 1-7 (foyer→métropole), mirrors the `chronicler.md` naming scale.


# The chapter's four registries: prev chapter merged with this save (live → period-accurate, gone → last-known `dead`, lost founders folded).
def _build_registries(save: dict, prev: dict) -> dict:
    actors = save.get("actors_data") or []
    cities = save.get("cities") or []
    kingdoms = save.get("kingdoms") or []
    captain_ids = {c for army in save.get("armies") or [] if (c := army.get("id_captain"))}  # O(1) captain lookup for `resolve_profession` in the per-actor loop
    items_by_id = index_by_id(save.get("items") or [])
    king_ids = {kid for k in kingdoms if (kid := k.get("kingID"))}  # the crowned only — a realm's banner set follows its king's species
    kingdoms_by_id = index_by_id(kingdoms)
    kings_by_id: dict = {}
    persons: dict[str, dict] = {}
    subspecies_by_id = index_by_id(save.get("subspecies") or [])

    # Entries only need a headcount and the dominant species, so tally asset_ids straight away rather than keeping every member around.
    members_by_family: Counter = Counter()  # WB points the actor at its lineage, never the reverse — the tally only exists once the roster is walked
    species_by_city: defaultdict[int, Counter] = defaultdict(Counter)
    species_by_kingdom: defaultdict[int, Counter] = defaultdict(Counter)

    for a in actors:
        if is_boat(a):
            continue
        if fid := a.get("family"):
            members_by_family[fid] += 1
        actor_id, species = a["id"], a.get("asset_id")  # both read three times below
        if actor_id in king_ids:
            kings_by_id[actor_id] = a
        if (cid := a.get("cityID")) is not None:
            species_by_city[cid][species] += 1
        if kid := a.get("civ_kingdom_id"):
            species_by_kingdom[kid][species] += 1
        # Every non-boat actor, kingdomless wilds included — the chronicler may tag any of them (species exemplars, lone notables…).
        persons[str(actor_id)] = _person_entry(a, resolve_profession(a, save, captain_ids), items_by_id, subspecies_by_id)

    cities_per_kingdom: Counter = Counter(kid for c in cities if (kid := c.get("kingdomID")) is not None)
    rank_by_city = {cid: rank for cid, rank in city_score_ranks(save).items() if rank <= 3}  # top-3 of the composite settlement weight → same medal as a realm's
    rank_by_kingdom = {kid: rank for kid, rank in kingdom_score_ranks(save).items() if rank <= 3}  # top-3 of the composite power score → gold/silver/bronze medal

    city_registry = {
        str(c["id"]): _city_entry(c, species_by_city.get(c["id"], Counter()), kingdoms_by_id.get(c.get("kingdomID")), rank_by_city.get(c["id"])) for c in cities
    }
    kingdom_registry = {
        str(k["id"]): _kingdom_entry(k, species_by_kingdom.get(k["id"], Counter()), cities_per_kingdom.get(k["id"], 0), rank_by_kingdom.get(k["id"]))
        | _kingdom_banner(k, kings_by_id, subspecies_by_id)
        for k in kingdoms
    }

    family_registry = {str(f["id"]): _family_entry(f, members_by_family.get(f["id"], 0)) for f in save.get("families") or []}

    out = {
        "cities": _merge(prev.get("cities") or {}, city_registry),
        "families": _merge(prev.get("families") or {}, family_registry),
        "kingdoms": _merge(prev.get("kingdoms") or {}, kingdom_registry),
        "persons": _merge(prev.get("persons") or {}, persons),
    }

    for record in (*cities, *kingdoms):  # dead founder never seen alive → only its founding species survives, on the record
        rulers = record.get("past_rulers") or []
        fid = record.get("founder_id") or (rulers[0].get("id") if rulers else None)
        if fid and str(fid) not in out["persons"] and (asset := record.get("original_actor_asset")):
            out["persons"][str(fid)] = {"asset_id": asset, "dead": True}

    return out


# City registry entry — what a `[c id Nom]` tag draws, plus the last-known name. Every hue it wears is its crown's, so `kingdom` stands in for all of them.
def _city_entry(city: dict, species: Counter, kingdom: dict | None, rank: int | None) -> dict:
    dominant = species.most_common(1)
    kingdom = kingdom or {}
    entry = {
        "crown": "capital" if kingdom.get("capitalID") == city.get("id") else "city",  # gold crown for the seat, stone rampart for the rest
        "name": city.get("name"),
        "species": dominant[0][0] if dominant else None,
    }
    if kingdom_id := kingdom.get("id"):  # its crown — the UI reads the name hue, the crown's ramp and the ring off it, and fallen realms stay registered
        entry["kingdom"] = kingdom_id
    if rank is not None:
        entry["rank"] = rank
    if (size := _size_tier(species.total())) > 1:  # a medallion reading `1` states the floor — every tag pill stays silent at its lowest tier
        entry["size"] = size
    return entry


# Family registry entry — the frame the tag wears as a border, the founding species' pip, the flattened backing hue and the living headcount, plus the last name.
def _family_entry(family: dict, members: int) -> dict:
    entry = {
        "frame": family.get("banner_frame_id") or 0,  # an absent banner id arrives as C#'s 0 — slot zero, not no slot
        "name": family.get("name"),
    }
    if members:  # dropped once the last member dies, as the city badge drops with its last citizen — a lineage carried over from an older chapter keeps none
        entry["members"] = members
    if (species := family.get("species_id")) is not None:  # the founding species' pip, right of the name as on every other tag
        entry["species"] = species
    # WB paints the backing sprite with `getColorMainSecond` (families borrow the realms' palette). Flattened to one hex: the tag fills rather than stacks.
    backing = load_data("family-backgrounds.json").get(f"{family.get('banner_background_id') or 0:02}")
    tint = _palette(family.get("color_id", "")).get("color_main_2")
    if backing and tint:
        entry["bg_color"] = _multiply(backing, tint)
    return {k: v for k, v in entry.items() if v is not None}


# WB `KingdomBanner.setupBanner` inputs, for the UI to compose on canvas: the species' background/icon slots the kingdom's two banner ids pick, each with its hue.
def _kingdom_banner(kingdom: dict, kings_by_id: dict, subspecies_by_id: dict) -> dict:
    lib = load_data("banner-icons.json")
    banner_id = lib["species_to_banner_id"].get(_kingdom_species(kingdom, kings_by_id, subspecies_by_id))
    bg_slots, icon_slots = lib["banner_id_backgrounds"].get(banner_id), lib["banner_id_icons"].get(banner_id)
    if not bg_slots or not icon_slots:  # species without a banner set (never seen in practice) → no fields, and the tag simply wears no heraldry
        return {}
    palette = _palette(kingdom.get("color_id", ""))
    return {
        "banner_bg": bg_slots[i if (i := kingdom.get("banner_background_id") or 0) < len(bg_slots) else 0],
        "banner_bg_color": palette.get("color_main_2"),
        "banner_icon": icon_slots[i if (i := kingdom.get("banner_icon_id") or 0) < len(icon_slots) else 0],
        "banner_icon_color": palette.get("color_banner"),
    }


# Kingdom entry, less the heraldry `_kingdom_banner` folds in and the merge's `dead`. It alone holds a hue — cities and subjects read theirs off it.
def _kingdom_entry(kingdom: dict, species: Counter, city_count: int, rank: int | None) -> dict:
    dominant, palette = species.most_common(1), _palette(kingdom.get("color_id", ""))
    entry: dict = {
        "color": palette.get("color_text") or _REALM_FALLBACK_HUE,  # the name hue, and the magenta ramp root once lightened; a `null` would break the UI type
        "color_main": palette.get("color_main"),
        "name": kingdom.get("name"),
        "species": dominant[0][0] if dominant else None,
    }
    if city_count > 1:  # a lone city (or none, for a realm just fallen) needs no badge — every tag pill stays silent at its lowest tier
        entry["cities"] = city_count
    if rank is not None:
        entry["rank"] = rank
    return entry


# The king's (or founder's) species — drives the banner set: living subspecies → its `species_id`, else the founding `original_actor_asset` (dead-founder fallback).
def _kingdom_species(kingdom: dict, kings_by_id: dict, subspecies_by_id: dict) -> str | None:
    king = kings_by_id.get(kingdom.get("kingID"))
    subspecies = subspecies_by_id.get(king.get("subspecies")) if king else None
    return (subspecies or {}).get("species_id") or kingdom.get("original_actor_asset")


def _load_registries(chapter_dir: Path) -> dict:
    return {name: json.loads(p.read_text()) if (p := chapter_dir / f"{name}.json").exists() else {} for name in _REGISTRIES}


# Carry each prior entry forward flagged dead (last-known visuals kept), then let live entities overwrite. `rank` and `members` go: neither survives the entity.
def _merge(prev: dict, live: dict) -> dict:
    carried = {}
    for entry_key, entry in prev.items():  # spread then pop beats filtering the items — most entries never held either key
        carried[entry_key] = fallen = {**entry, "dead": True}
        fallen.pop("members", None)
        fallen.pop("rank", None)
    return carried | live


# Unity's `set_color` is a multiply — the flat fill a tinted backing comes out as.
def _multiply(base: str, tint: str) -> str:
    channels = (int(base[i : i + 2], 16) * int(tint[i : i + 2], 16) // 255 for i in (1, 3, 5))
    return "#{:02X}{:02X}{:02X}".format(*channels)


# A realm's palette, verbatim — WB's own `checkIfColorTooDark` belongs to the sprite ramps alone, so the UI applies it. Empty when WB shipped no such palette.
@cache  # realms of one palette share the call, and every chapter rebuild replays it
def _palette(color_id) -> dict:
    return load_data("colors-all.json").get(str(color_id), {})


# Person registry entry — everything the UI composes an actor from, plus the last-known name. `dead` comes from the merge.
def _person_entry(actor: dict, profession: str | None, items_by_id: dict, subspecies_by_id: dict) -> dict:
    carried = [(items_by_id.get(iid) or {}).get("asset_id", "") for iid in actor.get("saved_items") or []]  # resolved once: head and weapon both read it
    entry = {"asset_id": actor.get("asset_id"), "sex": sex_label(actor)}
    for field in ("head", "phenotype_index", "phenotype_shade"):  # All three default to 0 in WB — omit then, the reader falls back to the same.
        if value := actor.get(field):
            entry[field] = value
    if kingdom := actor.get("civ_kingdom_id"):  # Their realm's hue dyes the clothes — kept as a ref so the palette lives in one place, the kingdom registry.
        entry["kingdom"] = kingdom
    if (level := max(int(actor.get("level") or 0), 1)) > 1:  # 93 % of a world sits at 1 — a medallion on every subject would say nothing, so it stays earned
        entry["level"] = level
    if name := actor.get("name"):  # Plenty of actors are unnamed — omit rather than store a placeholder; the tag's inline name stays the fallback.
        entry["name"] = name
    if profession and profession != "civilian":  # a civilian carries no badge — keep the registry lean.
        entry["profession"] = profession
    # WB `Subspecies.cacheSkins` picks the body sheet by the subspecies' `skin_id` — `warrior_6` rather than `warrior_1`. Absent means index 0, the reader's default.
    if skin := (subspecies_by_id.get(actor.get("subspecies")) or {}).get("skin_id"):
        entry["skin_id"] = skin
    if special := _special_head(actor, profession, carried):
        entry["special_head"] = special
    if weapon := _wielded_weapon(carried):
        entry["weapon"] = weapon
    return entry


# Settlement tier (1-7) from population — mirrors the `chronicler.md` naming scale (foyer → métropole). Drives the Civ-style size badge on the city tag.
def _size_tier(population: int) -> int:
    return next((tier for tier, cap in enumerate(_SIZE_TIERS, start=1) if population <= cap), len(_SIZE_TIERS) + 1)


# WB `Actor.checkSpriteHead`: a worn helmet, then a crown, then the white hair of the wise — each replaces the drawn head; failing all three, `head` picks it.
def _special_head(actor: dict, profession: str | None, carried: list[str]) -> str | None:
    if profession in ("army_captain", "warrior") and any(asset.startswith("helmet_") for asset in carried):
        return "head_warrior"
    if profession == "king":
        return "head_king"
    return "head_old" if "wise" in (actor.get("saved_traits") or []) else None


# Wieldable item asset_ids — `damage` is what tells a weapon from armor in `equipment.json`; the eight boat projectiles that share it never sit in an inventory.
@cache
def _weapon_assets() -> frozenset[str]:
    return frozenset(asset for asset, stats in load_data("equipment.json")["items"].items() if "damage" in stats)


# The weapon an actor holds — WB gives out at most one, so the first match is it.
def _wielded_weapon(carried: list[str]) -> str | None:
    assets = _weapon_assets()
    return next((asset for asset in carried if asset in assets), None)


# One line per entry, sorted by numeric id with fields alphabetical, so a changed entry shows up as a one-line diff rather than a reshuffled block.
def _write_registry(path: Path, registry: dict) -> None:
    # One dump per entry, not per field, and `sort_keys` rather than a pre-sorted copy — both push the work into C. Keys are ids, so they need no escaping.
    rows = [
        f'  "{entry_key}": {{ {json.dumps(entry, ensure_ascii=False, sort_keys=True)[1:-1]} }}'
        for entry_key, entry in sorted(registry.items(), key=lambda item: int(item[0]))
    ]
    path.write_text("{\n" + ",\n".join(rows) + "\n}\n")


# Builds this chapter's registries when missing (idempotent). Recurses to carry C<n-1> forward first, so the dead persist chapter to chapter.
def ensure(chapter: str, save: dict | None = None) -> None:
    chapter_dir = SAVES_DIR / chapter
    if all((chapter_dir / f"{name}.json").exists() for name in _REGISTRIES):
        return
    n = int(chapter[1:])
    prev = {}
    if n > 1:
        ensure(f"C{n - 1}")
        prev = _load_registries(SAVES_DIR / f"C{n - 1}")
    if save is None:  # the bootstrap already holds this chapter's save — reloading it would cost a full re-parse
        save = load_save(chapter_dir / "map.wbox")
    for name, registry in _build_registries(save, prev).items():
        _write_registry(chapter_dir / f"{name}.json", registry)


def main(argv: list[str]) -> int:
    chapter = next((a for a in argv if a.startswith("C") and a[1:].isdigit()), None)
    if chapter is None:
        print("usage: registries.py C<n> [--force] — (re)builds the saves/C<n>/ registries", file=sys.stderr)
        return 2
    if "--force" in argv:  # clear first so `ensure` rebuilds from scratch (e.g. after a py change to an entry's shape)
        for name in _REGISTRIES:
            (SAVES_DIR / chapter / f"{name}.json").unlink(missing_ok=True)
    ensure(chapter)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
