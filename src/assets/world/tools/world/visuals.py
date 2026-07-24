# Per-chapter PNG visuals composed from raw sprite parts (`tools/sprites/`): city crowns + kingdom banners, kingdom-tinted à la WB. Invoked by `world/info.py`.
# Both writers carry the previous chapter's PNGs forward first, then overwrite the living entities — razed/destroyed entities keep their last-known art.

from pathlib import Path

from shared import index_by_id, load_data

_BANNERS_IMG = Path(__file__).parents[3] / "img" / "banners"  # White species banner-icon sprites (`banner_part_object`), the same set the UI tags reference.
_CROWN_DARK = (30, 30, 30)  # WB `ColorAsset.initColor` Lerp target for the shade ramp.
_CROWN_FALLBACK_TEXT = "#B0B0B0"  # Neutral tint when a city has no kingdom palette — keeps the per-city crown file guaranteed.

# Magenta placeholder pixels in the `bannertop_*` sprites → shade index (WB `Toolbox.color_magenta_0..4` / `checkSpecialColors`).
_CROWN_PLACEHOLDERS = {(0xFF, 0x00, 0xFF): 0, (0xDE, 0x00, 0xDE): 1, (0xA7, 0x00, 0xA7): 2, (0x7F, 0x00, 0x7F): 3, (0x58, 0x00, 0x58): 4}

_CROWN_SHADE_TS = (0.0, 0.13, 0.35, 0.51, 0.66)  # Lerp factors of `k_color_0..4` towards `_CROWN_DARK`.
_SPRITE_PARTS = Path(__file__).parent.parent / "sprites"  # Raw crown/banner sprite parts composed at generation — sibling of `datas/` (which holds JSON only).


# Fresh output dir seeded with the previous chapter's files — razed/destroyed entities keep their last-known art; the live loop overwrites the rest.
def _carry_forward(dest: Path, prev: Path | None, pattern: str) -> None:
    dest.mkdir()
    if prev is not None and prev.is_dir():
        for f in prev.glob(pattern):
            (dest / f.name).write_bytes(f.read_bytes())


# WB `ColorAsset.initColor` shade ramp: lighten a too-dark `color_text`, then Lerp towards `_CROWN_DARK` per `_CROWN_SHADE_TS`.
def _crown_shades(text_hex: str) -> list[tuple[int, int, int]]:
    r, g, b = lighten_if_dark(int(text_hex[i : i + 2], 16) for i in (1, 3, 5))
    return [(int(r + (_CROWN_DARK[0] - r) * t), int(g + (_CROWN_DARK[1] - g) * t), int(b + (_CROWN_DARK[2] - b) * t)) for t in _CROWN_SHADE_TS]


# The king's (or founder's) species — drives the banner set: living subspecies → its `species_id`, else the founding `original_actor_asset` (dead-founder fallback).
def _kingdom_species(kingdom: dict, actors_by_id: dict, subspecies_by_id: dict) -> str | None:
    king = actors_by_id.get(kingdom.get("kingID"))
    subspecies = subspecies_by_id.get(king.get("subspecies")) if king else None
    return (subspecies or {}).get("species_id") or kingdom.get("original_actor_asset")


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


# WB `KingdomBanner.setupBanner`: multiplicative tint of a white/greyscale sprite by a `#RRGGBB` colour (Unity `Image.color`). `None` colour → sprite untouched.
def _tint(sprite, hex_color: str | None):
    if not hex_color:
        return sprite
    r, g, b = (int(hex_color[i : i + 2], 16) for i in (1, 3, 5))
    out = sprite.copy()
    if (pixels := out.load()) is None:
        return out
    for y in range(out.height):
        for x in range(out.width):
            p = pixels[x, y]
            if isinstance(p, tuple) and p[3]:
                pixels[x, y] = (p[0] * r // 255, p[1] * g // 255, p[2] * b // 255, p[3])
    return out


# WB `MetaSpriteLibrary.checkIfColorTooDark`: +50 to each channel when all three sit below 128 — keeps near-black palettes legible, and feeds the registry name hue.
def lighten_if_dark(channels) -> tuple[int, int, int]:
    r, g, b = channels
    return (r + 50, g + 50, b + 50) if r < 128 and g < 128 and b < 128 else (r, g, b)


# Per-kingdom banners (WB `KingdomBanner.setupBanner`): bg tinted `color_main_2` + icon tinted `color_banner`, keyed via `banner_*_id` in `banner-icons.json`.
def write_banners(chapter_dir: Path, save: dict, prev_banners: Path | None) -> None:
    from PIL import Image  # lazy: only first-time registry generation pays the Pillow import

    banners = chapter_dir / "banners"
    _carry_forward(banners, prev_banners, "k*.png")
    actors_by_id = index_by_id(save.get("actors_data") or [])
    backgrounds_dir = _SPRITE_PARTS / "banner-backgrounds"
    colors_all = load_data("colors-all.json")
    banner_cache: dict = {}  # (bg slot, main2, icon slot, banner colour) → composed banner; kingdoms of one species+palette share it
    lib = load_data("banner-icons.json")
    subspecies_by_id = index_by_id(save.get("subspecies") or [])

    for kingdom in save.get("kingdoms") or []:
        banner_id = lib["species_to_banner_id"].get(_kingdom_species(kingdom, actors_by_id, subspecies_by_id))
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
def write_crowns(chapter_dir: Path, save: dict, prev_crowns: Path | None) -> None:
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
