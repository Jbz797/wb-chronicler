#!/usr/bin/env python3

# Builds a chapter's `{cities,kingdoms,persons}.json` registries + `crowns/`/`banners/` PNGs under `saves/C<n>/` — the tag visuals (+ last-known names)
# the UI and chronicler resolve `[c/k/p id]` tags from. Carried forward from C<n-1> (dead entities kept), rebuilt whole from the save, reproducible.
# `ensure()` is what the bootstrap (`chapter/new.py`) calls; `registries.py C<n> [--force]` (re)builds one chapter standalone — a dev tool, not in `tools.md`.

import json
import shutil
import sys
from collections import Counter, defaultdict
from functools import cache
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))

from shared import SAVES_DIR, index_by_id, is_boat, kingdom_score_ranks, load_data, load_save, resolve_profession, sex_label

_BANNERS_IMG = Path(__file__).parents[3] / "img" / "banners"  # White species banner-icon sprites (`banner_part_object`), the same set the UI tags reference.
_CROWN_DARK = (30, 30, 30)  # WB `ColorAsset.initColor` Lerp target for the shade ramp.
_CROWN_FALLBACK_TEXT = "#B0B0B0"  # Neutral tint when a city has no kingdom palette — keeps the per-city crown file guaranteed.

# Magenta placeholder pixels in the `bannertop_*` sprites → shade index (WB `Toolbox.color_magenta_0..4` / `checkSpecialColors`).
_CROWN_PLACEHOLDERS = {(0xFF, 0x00, 0xFF): 0, (0xDE, 0x00, 0xDE): 1, (0xA7, 0x00, 0xA7): 2, (0x7F, 0x00, 0x7F): 3, (0x58, 0x00, 0x58): 4}

_CROWN_SHADE_TS = (0.0, 0.13, 0.35, 0.51, 0.66)  # Lerp factors of `k_color_0..4` towards `_CROWN_DARK`.
_SIZE_TIERS = (5, 15, 40, 100, 200, 500)  # Population upper bounds → settlement tier 1-7 (foyer→métropole), mirrors the `chronicler.md` naming scale.
_SPRITE_PARTS = Path(__file__).parent.parent / "sprites"  # Raw crown/banner sprite parts composed at generation — sibling of `datas/` (which holds JSON only).


# The chapter's cities/kingdoms/persons registries: prev chapter merged with this save (live → period-accurate, gone → last-known `dead`, lost founders folded).
def _build_registries(save: dict, prev: dict) -> dict:
    actors = save.get("actors_data") or []
    cities = save.get("cities") or []
    kingdoms = save.get("kingdoms") or []
    captain_ids = {c for army in save.get("armies") or [] if (c := army.get("id_captain"))}  # O(1) captain lookup for `resolve_profession` in the per-actor loop
    items_by_id = index_by_id(save.get("items") or [])
    kingdoms_by_id = index_by_id(kingdoms)
    persons: dict[str, dict] = {}

    # Entries only need a headcount and the dominant species, so tally asset_ids straight away rather than keeping every member around.
    species_by_city: defaultdict[int, Counter] = defaultdict(Counter)
    species_by_kingdom: defaultdict[int, Counter] = defaultdict(Counter)

    for a in actors:
        if is_boat(a):
            continue
        if (cid := a.get("cityID")) is not None:
            species_by_city[cid][a.get("asset_id")] += 1
        if kid := a.get("civ_kingdom_id"):
            species_by_kingdom[kid][a.get("asset_id")] += 1
        # Every non-boat actor, kingdomless wilds included — the chronicler may tag any of them (species exemplars, lone notables…).
        if entry := _person_entry(a, resolve_profession(a, save, captain_ids), items_by_id):
            persons[str(a["id"])] = entry

    cities_per_kingdom: Counter = Counter(kid for c in cities if (kid := c.get("kingdomID")) is not None)
    rank_by_kingdom = {kid: rank for kid, rank in kingdom_score_ranks(save).items() if rank <= 3}  # top-3 of the composite power score → gold/silver/bronze medal

    city_registry = {str(c["id"]): _city_entry(c, species_by_city.get(c["id"], Counter()), kingdoms_by_id.get(c.get("kingdomID"))) for c in cities}
    kingdom_registry = {
        str(k["id"]): _kingdom_visuals(k, species_by_kingdom.get(k["id"], Counter()), cities_per_kingdom.get(k["id"], 0), rank_by_kingdom.get(k["id"]))
        for k in kingdoms
    }

    out = {
        "cities": _merge(prev.get("cities") or {}, city_registry),
        "kingdoms": _merge(prev.get("kingdoms") or {}, kingdom_registry),
        "persons": _merge(prev.get("persons") or {}, persons),
    }

    for record in (*cities, *kingdoms):  # dead founder never seen alive → only its founding species survives, on the record
        rulers = record.get("past_rulers") or []
        fid = record.get("founder_id") or (rulers[0].get("id") if rulers else None)
        if fid and str(fid) not in out["persons"] and (asset := record.get("original_actor_asset")):
            out["persons"][str(fid)] = {"asset_id": asset, "dead": True}

    return out


# Fresh output dir seeded with the previous chapter's files — razed/destroyed entities keep their last-known art; the live loop overwrites the rest.
def _carry_forward(dest: Path, prev: Path | None, pattern: str) -> None:
    dest.mkdir()
    if prev is not None and prev.is_dir():
        for f in prev.glob(pattern):
            shutil.copyfile(f, dest / f.name)


# City registry entry (`[c id Nom]` tag visuals + last-known name): realm palette, size tier, dominant species; no capital flag — the crown PNG encodes it.
def _city_entry(city: dict, species: Counter, kingdom: dict | None) -> dict:
    color, ink = _kingdom_tag_colors(kingdom.get("color_id", "")) if kingdom else (None, None)
    dominant = species.most_common(1)
    return {"color": color, "ink": ink, "name": city.get("name"), "size": _size_tier(species.total()), "species": dominant[0][0] if dominant else None}


# WB `ColorAsset.initColor` shade ramp: lighten a too-dark `color_text`, then Lerp towards `_CROWN_DARK` per `_CROWN_SHADE_TS`.
def _crown_shades(text_hex: str) -> list[tuple[int, int, int]]:
    r, g, b = _lighten_if_dark(int(text_hex[i : i + 2], 16) for i in (1, 3, 5))
    return [(int(r + (_CROWN_DARK[0] - r) * t), int(g + (_CROWN_DARK[1] - g) * t), int(b + (_CROWN_DARK[2] - b) * t)) for t in _CROWN_SHADE_TS]


# The king's (or founder's) species — drives the banner set: living subspecies → its `species_id`, else the founding `original_actor_asset` (dead-founder fallback).
def _kingdom_species(kingdom: dict, kings_by_id: dict, subspecies_by_id: dict) -> str | None:
    king = kings_by_id.get(kingdom.get("kingID"))
    subspecies = subspecies_by_id.get(king.get("subspecies")) if king else None
    return (subspecies or {}).get("species_id") or kingdom.get("original_actor_asset")


# Kingdom tag palette: bg = darkest of 4 hues, ink = lightest (contrast, `colors-all.json`), else `(None, None)`. Cached — a kingdom's cities share one `color_id`.
@cache
def _kingdom_tag_colors(color_id) -> tuple[str | None, str | None]:
    palette = [h for h in load_data("colors-all.json").get(str(color_id), {}).values() if h]
    if not palette:
        return None, None
    return min(palette, key=_relative_luminance), max(palette, key=_relative_luminance)


# WB `getColorText` = the palette's `color_text`, lightened if too dark — the hue WB prints a kingdom's name in. `None` when the palette is missing.
def _kingdom_text_color(color_id) -> str | None:
    text = load_data("colors-all.json").get(str(color_id), {}).get("color_text")
    return "#{:02X}{:02X}{:02X}".format(*_lighten_if_dark(int(text[i : i + 2], 16) for i in (1, 3, 5))) if text else None


# Kingdom registry entry: name colour (`getColorText`), city-count badge, top-3 `rank`, species — banner in `banners/k<id>.png`, `dead` from the merge.
def _kingdom_visuals(kingdom: dict, species: Counter, city_count: int, rank: int | None) -> dict:
    dominant = species.most_common(1)
    entry: dict = {"color": _kingdom_text_color(kingdom.get("color_id", "")), "name": kingdom.get("name"), "species": dominant[0][0] if dominant else None}
    if city_count:  # a defunct kingdom can momentarily hold none — omit the badge rather than show a `0`
        entry["cities"] = city_count
    if rank is not None:  # top-3 by composite power score (`kingdom_score_ranks`) — drives the gold/silver/bronze podium medal
        entry["rank"] = rank
    return entry


# WB `MetaSpriteLibrary.checkIfColorTooDark`: +50 to each channel when all three sit below 128 — keeps near-black palettes legible, and feeds the registry name hue.
def _lighten_if_dark(channels) -> tuple[int, int, int]:
    r, g, b = channels
    return (r + 50, g + 50, b + 50) if r < 128 and g < 128 and b < 128 else (r, g, b)


def _load_registries(chapter_dir: Path) -> dict:
    return {name: json.loads(p.read_text()) if (p := chapter_dir / f"{name}.json").exists() else {} for name in ("cities", "kingdoms", "persons")}


# Carry each prior entry forward flagged dead (last-known visuals kept, `rank` dropped — a medal is meaningless once fallen), then let live entities overwrite.
def _merge(prev: dict, live: dict) -> dict:
    return {**{k: {**{f: val for f, val in v.items() if f != "rank"}, "dead": True} for k, v in prev.items()}, **live}


# Person registry entry: everything needed to draw the actor — species, sex, head, skin phenotype, wielded weapon, non-unit profession. `dead` comes from the merge.
def _person_entry(actor: dict, profession: str | None, items_by_id: dict) -> dict:
    carried = [(items_by_id.get(iid) or {}).get("asset_id", "") for iid in actor.get("saved_items") or []]  # resolved once: head and weapon both read it
    entry = {"asset_id": actor.get("asset_id"), "sex": sex_label(actor)}
    for field in ("head", "phenotype_index", "phenotype_shade"):  # All three default to 0 in WB — omit then, the reader falls back to the same.
        if value := actor.get(field):
            entry[field] = value
    if kingdom := actor.get("civ_kingdom_id"):  # Their realm's hue dyes the clothes — kept as a ref so the palette lives in one place, the kingdom registry.
        entry["kingdom"] = kingdom
    if name := actor.get("name"):  # Plenty of actors are unnamed — omit rather than store a placeholder; the tag's inline name stays the fallback.
        entry["name"] = name
    if profession and profession != "unit":  # `unit` carries no badge — keep the registry lean.
        entry["profession"] = profession
    if special := _special_head(actor, profession, carried):
        entry["special_head"] = special
    if weapon := _wielded_weapon(carried):
        entry["weapon"] = weapon
    return entry


# Swap the magenta placeholder pixels of a `bannertop_*` copy for the kingdom shade ramp — WB `MetaSpriteLibrary.checkSpecialColors`, port exact.
def _recolor_crown(base, shades: list[tuple[int, int, int]]):
    icon = base.copy()
    if (pixels := icon.load()) is None:  # `load()` is typed Optional — never None for an in-memory RGBA copy
        return icon
    for y in range(icon.height):
        for x in range(icon.width):
            p = pixels[x, y]
            if isinstance(p, tuple) and p[3] and (i := _CROWN_PLACEHOLDERS.get((p[0], p[1], p[2]))) is not None:  # narrows `PixelAccess`'s float | tuple
                pixels[x, y] = (*shades[i], p[3])
    return icon


# Relative luminance (WCAG) of a "#RRGGBB" colour — used to pick the darkest / lightest of a palette.
def _relative_luminance(color: str) -> float:
    channels = [int(color[i : i + 2], 16) / 255 for i in (1, 3, 5)]
    linear = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


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


# WB `KingdomBanner.setupBanner`: multiplicative `#RRGGBB` tint, `None` leaving the sprite alone — a lookup per band beats walking pixels, alpha mapping to itself.
def _tint(sprite, hex_color: str | None):
    if not hex_color:
        return sprite
    lut = [c * int(hex_color[i : i + 2], 16) // 255 for i in (1, 3, 5) for c in range(256)]
    return sprite.point([*lut, *range(256)])


# Wieldable item asset_ids — `damage` is what tells a weapon from armor in `equipment.json`; the eight boat projectiles that share it never sit in an inventory.
@cache
def _weapon_assets() -> frozenset[str]:
    return frozenset(asset for asset, stats in load_data("equipment.json")["items"].items() if "damage" in stats)


# The weapon an actor holds — WB gives out at most one, so the first match is it.
def _wielded_weapon(carried: list[str]) -> str | None:
    assets = _weapon_assets()
    return next((asset for asset in carried if asset in assets), None)


# Per-kingdom banners (WB `KingdomBanner.setupBanner`): bg tinted `color_main_2` + icon tinted `color_banner`, keyed via `banner_*_id` in `banner-icons.json`.
def _write_banners(chapter_dir: Path, save: dict, prev_banners: Path | None) -> None:
    from PIL import Image  # lazy: only first-time registry generation pays the Pillow import

    banners = chapter_dir / "banners"
    _carry_forward(banners, prev_banners, "k*.png")
    king_ids = {kid for k in save.get("kingdoms") or [] if (kid := k.get("kingID"))}  # only the crowned matter here — indexing every actor would be 100× the dict
    kings_by_id = {a["id"]: a for a in save.get("actors_data") or [] if a["id"] in king_ids}
    backgrounds_dir = _SPRITE_PARTS / "banner-backgrounds"
    colors_all = load_data("colors-all.json")
    banner_cache: dict = {}  # (bg slot, main2, icon slot, banner colour) → composed banner; kingdoms of one species+palette share it
    lib = load_data("banner-icons.json")
    subspecies_by_id = index_by_id(save.get("subspecies") or [])

    for kingdom in save.get("kingdoms") or []:
        banner_id = lib["species_to_banner_id"].get(_kingdom_species(kingdom, kings_by_id, subspecies_by_id))
        bg_slots, icon_slots = lib["banner_id_backgrounds"].get(banner_id), lib["banner_id_icons"].get(banner_id)
        if not bg_slots or not icon_slots:  # species without a banner set (never seen in practice) → no file; the tag falls back gracefully
            continue
        pal = colors_all.get(str(kingdom.get("color_id", "")), {})
        bg_slot = bg_slots[i if (i := kingdom.get("banner_background_id") or 0) < len(bg_slots) else 0]
        icon_slot = icon_slots[i if (i := kingdom.get("banner_icon_id") or 0) < len(icon_slots) else 0]
        key = (bg_slot, pal.get("color_main_2"), icon_slot, pal.get("color_banner"))
        if (banner := banner_cache.get(key)) is None:
            bg = _tint(Image.open(backgrounds_dir / f"{bg_slot}.png").convert("RGBA"), pal.get("color_main_2"))
            icon = _tint(Image.open(_BANNERS_IMG / f"{icon_slot}.png").convert("RGBA"), pal.get("color_banner"))
            banner = banner_cache[key] = bg.copy()
            banner.alpha_composite(icon, ((bg.width - icon.width) // 2, max(1, (bg.width - icon.height) // 2)))  # centre the icon on the shield face
        banner.save(banners / f"k{kingdom['id']}.png")


# Per-city crowns (WB `CityBanner.setupBanner`): capital → gold crown, village → stone rampart, kingdom-tinted; prev chapter copied first — razed cities keep theirs.
def _write_crowns(chapter_dir: Path, save: dict, prev_crowns: Path | None) -> None:
    from PIL import Image  # lazy: only first-time registry generation pays the Pillow import

    crowns = chapter_dir / "crowns"
    _carry_forward(crowns, prev_crowns, "c*.png")
    bases = {capital: Image.open(_SPRITE_PARTS / f"bannertop_{'capital' if capital else 'city'}.png").convert("RGBA") for capital in (False, True)}
    colors_all = load_data("colors-all.json")
    icon_cache: dict = {}  # (text colour, capital?) → recoloured sprite; the cities of one kingdom share their crown
    kingdoms_by_id = index_by_id(save.get("kingdoms") or [])

    for city in save.get("cities") or []:
        kingdom = kingdoms_by_id.get(city.get("kingdomID")) or {}
        text = colors_all.get(str(kingdom.get("color_id", "")), {}).get("color_text") or _CROWN_FALLBACK_TEXT
        key = (text, kingdom.get("capitalID") == city.get("id"))
        if (icon := icon_cache.get(key)) is None:
            icon = icon_cache[key] = _recolor_crown(bases[key[1]], _crown_shades(text))
        icon.save(crowns / f"c{city['id']}.png")


# Serialize a registry to disk: one line per entry, sorted by numeric id, fields alphabetical — single-line diffs.
def _write_registry(path: Path, registry: dict) -> None:
    rows = []
    for entry_key, entry_value in sorted(registry.items(), key=lambda item: int(item[0])):
        fields = ", ".join(f"{json.dumps(k)}: {json.dumps(v, ensure_ascii=False)}" for k, v in sorted(entry_value.items()))
        rows.append(f"  {json.dumps(entry_key)}: {{ {fields} }}")
    path.write_text("{\n" + ",\n".join(rows) + "\n}\n")


# Builds this chapter's registries + crowns/ + banners/ when missing (idempotent). Recurses to carry C<n-1> forward first, so the dead persist chapter to chapter.
def ensure(chapter: str, save: dict | None = None) -> None:
    chapter_dir = SAVES_DIR / chapter
    have_banners = (chapter_dir / "banners").is_dir()
    have_crowns = (chapter_dir / "crowns").is_dir()
    have_json = all((chapter_dir / f"{name}.json").exists() for name in ("cities", "kingdoms", "persons"))
    if have_banners and have_crowns and have_json:
        return
    n = int(chapter[1:])
    prev = {}
    if n > 1:
        ensure(f"C{n - 1}")
        prev = _load_registries(SAVES_DIR / f"C{n - 1}")
    if save is None:  # the bootstrap already holds this chapter's save — reloading it would cost a full re-parse
        save = load_save(chapter_dir / "map.wbox")
    if not have_json:
        for name, registry in _build_registries(save, prev).items():
            _write_registry(chapter_dir / f"{name}.json", registry)
    if not have_crowns:
        _write_crowns(chapter_dir, save, SAVES_DIR / f"C{n - 1}" / "crowns" if n > 1 else None)
    if not have_banners:
        _write_banners(chapter_dir, save, SAVES_DIR / f"C{n - 1}" / "banners" if n > 1 else None)


def main(argv: list[str]) -> int:
    chapter = next((a for a in argv if a.startswith("C") and a[1:].isdigit()), None)
    if chapter is None:
        print("usage: registries.py C<n> [--force] — (re)builds saves/C<n>/ registries + crowns + banners", file=sys.stderr)
        return 2
    if "--force" in argv:  # clear first so `ensure` rebuilds from scratch (e.g. after a py change to an entry's shape)
        chapter_dir = SAVES_DIR / chapter
        for name in ("cities", "kingdoms", "persons"):
            (chapter_dir / f"{name}.json").unlink(missing_ok=True)
        for sub in ("banners", "crowns"):
            shutil.rmtree(chapter_dir / sub, ignore_errors=True)
    ensure(chapter)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
