#!/usr/bin/env python3

# Builds a chapter's `{cities,kingdoms,persons}.json` registries + `crowns/`/`banners/` PNGs under `saves/C<n>/` — the tag visuals (+ last-known names)
# the UI and chronicler resolve `[c/k/p id]` tags from. Carried forward from C<n-1> (dead entities kept), rebuilt whole from the save, reproducible.
# `ensure()` is what the bootstrap (`chapter/new.py`) calls; `registries.py C<n> [--force]` (re)builds one chapter standalone. Docs: `tools/tools.md`.

import json
import shutil
import sys
from collections import Counter
from functools import cache
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from shared import SAVES_DIR, index_by_id, is_boat, kingdom_score_ranks, load_data, load_save, resolve_profession, sex_label
from visuals import lighten_if_dark, write_banners, write_crowns

_SIZE_TIERS = (5, 15, 40, 100, 200, 500)  # Population upper bounds → settlement tier 1-7 (foyer→métropole), mirrors the `chronicler.md` naming scale.


# The chapter's cities/kingdoms/persons registries: prev chapter merged with this save (live → period-accurate, gone → last-known `dead`, lost founders folded).
def _build_registries(save: dict, prev: dict) -> dict:
    actors = save.get("actors_data") or []
    cities = save.get("cities") or []
    kingdoms = save.get("kingdoms") or []
    captain_ids = {c for army in save.get("armies") or [] if (c := army.get("id_captain"))}  # O(1) captain lookup for `resolve_profession` in the per-actor loop
    kingdoms_by_id = index_by_id(kingdoms)
    persons: dict[str, dict] = {}

    # Entries only need a headcount and the dominant species, so tally asset_ids straight away rather than keeping every member around.
    species_by_city: dict[int, Counter] = {}
    species_by_kingdom: dict[int, Counter] = {}

    for a in actors:
        if is_boat(a):
            continue
        if (cid := a.get("cityID")) is not None:
            species_by_city.setdefault(cid, Counter())[a.get("asset_id")] += 1
        if kid := a.get("civ_kingdom_id"):
            species_by_kingdom.setdefault(kid, Counter())[a.get("asset_id")] += 1
        # Every non-boat actor, kingdomless wilds included — the chronicler may tag any of them (species exemplars, lone notables…).
        if entry := _person_entry(a, resolve_profession(a, save, captain_ids)):
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


# City registry entry (`[c id Nom]` tag visuals + last-known name): realm palette, size tier, dominant species; no capital flag — the crown PNG encodes it.
def _city_entry(city: dict, species: Counter, kingdom: dict | None) -> dict:
    color, ink = _kingdom_tag_colors(kingdom.get("color_id", "")) if kingdom else (None, None)
    dominant = species.most_common(1)
    return {"color": color, "ink": ink, "name": city.get("name"), "size": _size_tier(species.total()), "species": dominant[0][0] if dominant else None}


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
    return "#{:02X}{:02X}{:02X}".format(*lighten_if_dark(int(text[i : i + 2], 16) for i in (1, 3, 5))) if text else None


# Kingdom registry entry: name colour (`getColorText`), city-count badge, top-3 `rank`, species — banner in `banners/k<id>.png`, `dead` from the merge.
def _kingdom_visuals(kingdom: dict, species: Counter, city_count: int, rank: int | None) -> dict:
    dominant = species.most_common(1)
    entry: dict = {"color": _kingdom_text_color(kingdom.get("color_id", "")), "name": kingdom.get("name"), "species": dominant[0][0] if dominant else None}
    if city_count:  # a defunct kingdom can momentarily hold none — omit the badge rather than show a `0`
        entry["cities"] = city_count
    if rank is not None:  # top-3 by composite power score (`kingdom_score_ranks`) — drives the gold/silver/bronze podium medal
        entry["rank"] = rank
    return entry


def _load_registries(chapter_dir: Path) -> dict:
    return {name: json.loads(p.read_text()) if (p := chapter_dir / f"{name}.json").exists() else {} for name in ("cities", "kingdoms", "persons")}


# Carry each prior entry forward flagged dead (last-known visuals kept, `rank` dropped — a medal is meaningless once fallen), then let live entities overwrite.
def _merge(prev: dict, live: dict) -> dict:
    return {**{k: {**{f: val for f, val in v.items() if f != "rank"}, "dead": True} for k, v in prev.items()}, **live}


# Person registry entry (`[p id]` tag visuals): species + sex + non-unit profession. `dead` is added by the merge; the caller has already filtered boats out.
def _person_entry(actor: dict, profession: str | None) -> dict:
    entry = {"asset_id": actor.get("asset_id"), "sex": sex_label(actor)}
    if name := actor.get("name"):  # Plenty of actors are unnamed — omit rather than store a placeholder; the tag's inline name stays the fallback.
        entry["name"] = name
    if profession and profession != "unit":  # `unit` carries no badge — keep the registry lean.
        entry["profession"] = profession
    return entry


# Relative luminance (WCAG) of a "#RRGGBB" colour — used to pick the darkest / lightest of a palette.
def _relative_luminance(color: str) -> float:
    channels = [int(color[i : i + 2], 16) / 255 for i in (1, 3, 5)]
    linear = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


# Settlement tier (1-7) from population — mirrors the `chronicler.md` naming scale (foyer → métropole). Drives the Civ-style size badge on the city tag.
def _size_tier(population: int) -> int:
    return next((tier for tier, cap in enumerate(_SIZE_TIERS, start=1) if population <= cap), len(_SIZE_TIERS) + 1)


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
        write_crowns(chapter_dir, save, SAVES_DIR / f"C{n - 1}" / "crowns" if n > 1 else None)
    if not have_banners:
        write_banners(chapter_dir, save, SAVES_DIR / f"C{n - 1}" / "banners" if n > 1 else None)


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
