#!/usr/bin/env python3

# Emits the world sections (`cumulative`/`leaders`/`metadata`/`snapshot`) from the save alone — its `mapStats` is the dict `map.meta` mirrors — and generates the
# chapter's `{cities,kingdoms,persons}.json` registries (`_build_registries`). User-facing docs: `tools/tools.md`.
#
# ⚠️ Output keys must stay self-descriptive (chronicler reads them with no other context). Prefer disambiguated names (e.g. `wild_creatures` over `creatures`).
# Exception: WB-native names verbatim for raw-save fields (e.g. `relations`, `world_time`) — chronicler reads save directly, divergent names would cause friction.

import json
import sys
from collections import Counter
from functools import cache
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from shared import (
    SAVES_DIR,
    SICK_TRAITS,
    civic_building_ids,
    emit,
    index_by_id,
    load_data,
    load_save,
    parse_sections,
    resolve_profession,
    sex_label,
    take_chapter,
)
from visuals import lighten_if_dark, write_banners, write_crowns

_ALL_SECTIONS = ("cumulative", "leaders", "metadata", "snapshot")

# Chronicler key => WB `mapStats` counter — UI keys (`CUMULATIVE_STATS`) + churn a net snapshot hides; `_created` stored, `destroyed = created − snapshot.alive`.
_CUMULATIVE_COUNTERS = {
    "alliances_made": "alliancesMade",
    "armies_created": "armiesCreated",
    "books_burnt": "booksBurnt",
    "books_read": "booksRead",
    "buildings_built": "housesBuilt",  # WB `housesBuilt` counts all buildings, not dwellings (net ≈ `buildings`)
    "cities_conquered": "citiesConquered",
    "cities_created": "citiesCreated",
    "cities_rebelled": "citiesRebelled",
    "clans_created": "clansCreated",
    "creatures_born": "creaturesBorn",  # natural reproduction
    "creatures_created": "creaturesCreated",  # divine spawn + worldgen
    "cultures_created": "culturesCreated",
    "evolutions": "evolutions",
    "families_created": "familiesCreated",
    "kingdoms_created": "kingdomsCreated",
    "languages_created": "languagesCreated",
    "metamorphosis": "metamorphosis",
    "peaces_made": "peacesMade",
    "plots_started": "plotsStarted",
    "plots_succeeded": "plotsSucceeded",
    "religions_created": "religionsCreated",
    "subspecies_created": "subspeciesCreated",
    "wars_started": "warsStarted",
}

# Chronicler key => WB save fields (sum). Mirrors the 16 rows of WB's « Deaths » panel; `water` is hydrophobic damage (separate from `drowning`).
_DEATH_CAUSES = {
    "acid": ("deaths_acid",),
    "divine": ("deaths_divine",),
    "drowning": ("deaths_drowning",),
    "eaten": ("deaths_eaten",),
    "explosion": ("deaths_explosion",),
    "fire": ("deaths_fire",),
    "gravity": ("deaths_gravity",),
    "hunger": ("deaths_hunger",),
    "infection": ("deaths_infection",),
    "old_age": ("deaths_age",),
    "other": ("deaths_other",),
    "plague": ("deaths_plague",),
    "poison": ("deaths_poison",),
    "tumor": ("deaths_tumor",),
    "water": ("deaths_water",),
    "weapon": ("deaths_weapon",),
}

_SIZE_TIERS = (5, 15, 40, 100, 200, 500)  # Population upper bounds → settlement tier 1-7 (foyer→métropole), mirrors the `chronicler.md` naming scale.

# Chronicler key => save collection simply counted. The rest of the snapshot needs classifying (buildings) or filtering (actors), so it lives in `_build_snapshot`.
_SNAPSHOT_COLLECTIONS = {
    "alliances": "alliances",
    "books": "books",
    "cities": "cities",
    "clans": "clans",
    "cultures": "cultures",
    "equipment": "items",
    "families": "families",
    "kingdoms": "kingdoms",
    "languages": "languages",
    "religions": "religions",
    "subspecies": "subspecies",
    "wars": "wars",
}

_SPECIES = load_data("species.json")  # asset_id → {stats, name, description}. Here for the French `name`; falls back to the asset_id when absent.

_UNVEGETATED = {
    "geyser",
    "super_pumpkin",
    "volcano",
}  # Neither civ nor vegetation (`poop` = WB vegetation; `mineral_*` by prefix).


# 0-count entries (counters + per-cause deaths) are dropped — UI treats missing keys as 0. `or 0` also covers the few counters WB stores as null.
def _build_cumulative(map_stats: dict) -> dict:
    deaths = ((k, sum(int(map_stats.get(s, 0)) for s in srcs)) for k, srcs in _DEATH_CAUSES.items())
    out: dict = {k: v for k, src in _CUMULATIVE_COUNTERS.items() if (v := int(map_stats.get(src) or 0)) > 0}
    out["deaths"] = dict(sorted((k, v) for k, v in deaths if v > 0))
    return dict(sorted(out.items()))


# Top entity per category (populous village/kingdom, dominant culture/language/religion/subspecies, top renown) — mirrors WB's « Records » panel.
def _build_leaders(save: dict) -> dict:
    actors = save.get("actors_data") or []
    cities_by_id = index_by_id(save.get("cities") or [])
    cultures_by_id = index_by_id(save.get("cultures") or [])
    kingdoms_by_id = index_by_id(save.get("kingdoms") or [])
    languages_by_id = index_by_id(save.get("languages") or [])
    religions_by_id = index_by_id(save.get("religions") or [])
    subspecies_by_id = index_by_id(save.get("subspecies") or [])

    # Single pass over actors feeds every leader: category counts, top-renown civilian, and family renown sums (all gated the same way, no need to re-scan).
    counts: dict[str, Counter] = {k: Counter() for k in ("city", "culture", "kingdom", "language", "religion", "species", "subspecies")}
    family_renown: Counter[int] = Counter()
    top_person, top_renown = None, -1

    for a in actors:
        if (a.get("asset_id") or "").startswith("boat_"):
            continue
        if a.get("civ_kingdom_id"):  # civilian: non-boat, kingdom-bound. `species` is the « thinking population », not wild creatures.
            renown = int(a.get("renown") or 0)
            counts["species"][a.get("asset_id")] += 1
            if renown > top_renown:
                top_person, top_renown = a, renown
            if fid := a.get("family"):
                family_renown[fid] += renown
        for key, field in (
            ("city", "cityID"),
            ("culture", "culture"),
            ("kingdom", "civ_kingdom_id"),
            ("language", "language"),
            ("religion", "religion"),
            ("subspecies", "subspecies"),
        ):
            if (v := a.get(field)) is not None:
                counts[key][v] += 1

    # City/kingdom leaders are emitted as `{id, name, value}` — the UI reads the rest (palette, banner, size, species) from the cities/kingdoms registry.
    out: dict[str, dict] = {}
    for key, registry, dest in (
        ("city", cities_by_id, "most_populous_village"),
        ("culture", cultures_by_id, "dominant_culture"),
        ("kingdom", kingdoms_by_id, "most_populous_kingdom"),
        ("language", languages_by_id, "dominant_language"),
        ("religion", religions_by_id, "dominant_religion"),
        ("subspecies", subspecies_by_id, "dominant_subspecies"),
    ):
        if not counts[key]:
            continue
        top_id, value = counts[key].most_common(1)[0]
        entry = registry.get(top_id) or {}
        out[dest] = {"id": top_id, "name": entry.get("name") or f"#{top_id}", "value": value}

    if counts["species"]:  # `asset_id` is the UI icon key; `name` is its French label (falls back to the asset_id).
        top_species, value = counts["species"].most_common(1)[0]
        out["dominant_species"] = {"asset_id": top_species, "name": (_SPECIES.get(top_species) or {}).get("name") or top_species, "value": value}

    if top_person is not None:  # Top-renown civilian — emitted as `{id, name}` (+ renown); the UI's `<app-person-tag>` reads its visuals from the person registry.
        out["most_renowned_person"] = {"id": top_person.get("id"), "name": top_person.get("name") or f"#{top_person.get('id')}", "value": top_renown}

    clans = save.get("clans") or []
    if clans:
        top_clan = max(clans, key=lambda c: int(c.get("renown") or 0))
        out["most_renowned_clan"] = {"id": top_clan.get("id"), "name": top_clan.get("name") or f"#{top_clan.get('id')}", "value": int(top_clan.get("renown") or 0)}

    if family_renown:  # Families carry no native renown (unlike clans) — rank by their members' summed renown, tallied in the pass above.
        top_fid, value = family_renown.most_common(1)[0]
        family = next((f for f in save.get("families") or [] if f.get("id") == top_fid), {})  # single lookup → no full index alloc
        out["most_renowned_family"] = {"id": top_fid, "name": family.get("name") or f"#{top_fid}", "value": value}

    return dict(sorted(out.items()))


def _build_metadata(map_stats: dict) -> dict:
    age_duration = float(map_stats.get("current_world_ages_duration") or 0)
    age_progress = float(map_stats.get("current_age_progress") or 0)
    return {
        "age_id": map_stats.get("world_age_id") or "",  # WorldAgeLibrary key (e.g. `stone_age`)
        # Chronicler-only narrative hint, matches WB's UI counter « Lunes jusqu'au prochain âge ». Omitted when 0 / no current age.
        "months_until_next_age": int(age_duration * (1 - age_progress) / 5) if age_duration > 0 else 0,
        "world_time": round(float(map_stats.get("world_time", 0)), 2),
    }


# The chapter's cities/kingdoms/persons registries: prev chapter merged with this save (live → period-accurate, gone → last-known `dead`, lost founders folded).
def _build_registries(save: dict, prev: dict) -> dict:
    actors = save.get("actors_data") or []
    actors_by_city: dict[int, list] = {}
    actors_by_kingdom: dict[int, list] = {}
    captain_ids = {c for army in save.get("armies") or [] if (c := army.get("id_captain"))}  # O(1) captain lookup for `resolve_profession` in the per-actor loop
    kingdoms_by_id = index_by_id(save.get("kingdoms") or [])
    persons: dict[str, dict] = {}

    for a in actors:
        if (a.get("asset_id") or "").startswith("boat_"):
            continue
        if (cid := a.get("cityID")) is not None:
            actors_by_city.setdefault(cid, []).append(a)
        if kid := a.get("civ_kingdom_id"):
            actors_by_kingdom.setdefault(kid, []).append(a)
        # Every non-boat actor, kingdomless wilds included — the chronicler may tag any of them (species exemplars, lone notables…).
        if entry := _person_entry(a, resolve_profession(a, save, captain_ids)):
            persons[str(a["id"])] = entry

    cities_per_kingdom: Counter = Counter(kid for c in save.get("cities") or [] if (kid := c.get("kingdomID")) is not None)

    # Population rank across living kingdoms — only the top 3 earn a medal border on their tag (gold/silver/bronze); ties broken by id for a stable order.
    ranked = sorted(save.get("kingdoms") or [], key=lambda k: (-len(actors_by_kingdom.get(k["id"], [])), k["id"]))
    rank_by_kingdom = {k["id"]: i + 1 for i, k in enumerate(ranked[:3]) if actors_by_kingdom.get(k["id"])}

    cities = {str(c["id"]): _city_entry(c, actors_by_city.get(c["id"], []), kingdoms_by_id.get(c.get("kingdomID"))) for c in save.get("cities") or []}
    kingdoms = {
        str(k["id"]): _kingdom_visuals(k, actors_by_kingdom.get(k["id"], []), cities_per_kingdom.get(k["id"], 0), rank_by_kingdom.get(k["id"]))
        for k in save.get("kingdoms") or []
    }

    out = {
        "cities": _merge(prev.get("cities") or {}, cities),
        "kingdoms": _merge(prev.get("kingdoms") or {}, kingdoms),
        "persons": _merge(prev.get("persons") or {}, persons),
    }

    for record in (*(save.get("cities") or []), *(save.get("kingdoms") or [])):  # dead founder never seen alive → only its founding species survives, on the record
        rulers = record.get("past_rulers") or []
        fid = record.get("founder_id") or (rulers[0].get("id") if rulers else None)
        if fid and str(fid) not in out["persons"] and (asset := record.get("original_actor_asset")):
            out["persons"][str(fid)] = {"asset_id": asset, "dead": True}

    return out


# `population`/`wild_creatures` split on kingdom membership, so both drift ~2 from WB's own tally. `infected` = WB's `current_infected`.
def _build_snapshot(save: dict) -> dict:
    civic = civic_building_ids()
    asset_counts = Counter(b.get("asset_id") or "" for b in save.get("buildings", []))  # Count `asset_id`s once, classify distinct keys — avoids 3 scans.

    # Both omitted when 0 (outbreak-style, idle most chapters). `infected` ⊂ `sick`: a plague never shows up in `infected`, hence the two counters.
    infected = population = sick = 0
    for a in save.get("actors_data") or []:
        traits = a.get("saved_traits") or []
        infected += "infected" in traits
        population += a.get("civ_kingdom_id") is not None
        sick += not SICK_TRAITS.isdisjoint(traits)

    return dict(
        sorted(
            {
                **{k: len(save.get(coll) or []) for k, coll in _SNAPSHOT_COLLECTIONS.items()},
                "armies": len(save.get("armies") or []),
                "buildings": sum(n for aid, n in asset_counts.items() if aid in civic),  # Built structures worldwide (nature excluded); `houses` = dwellings.
                "frozen_tiles": len(save.get("frozen_tiles") or []),
                "houses": sum(n for aid, n in asset_counts.items() if aid.startswith("house")),
                **({"infected": infected} if infected else {}),
                "plots_active": len(save.get("plots") or []),
                "population": population,
                **({"sick": sick} if sick else {}),
                # `tree` substring catches every `Building_Tree` asset_id (pine/swamp/birch/…). ≤1% drift vs WB UI — counter moves between snapshots.
                "trees": sum(n for aid, n in asset_counts.items() if "tree" in aid),
                "vegetation": sum(
                    n for aid, n in asset_counts.items() if aid not in civic and aid not in _UNVEGETATED and not aid.startswith(("fishing_docks", "mineral"))
                ),
                "wild_creatures": len(save.get("actors_data") or []) - population,
            }.items()
        )
    )


# City registry entry (`[c id Nom]` tag visuals + last-known name): realm palette, size tier, dominant species; no capital flag — the crown PNG encodes it.
def _city_entry(city: dict, actors_of_city: list[dict], kingdom: dict | None) -> dict:
    color, ink = _kingdom_tag_colors(kingdom.get("color_id", "")) if kingdom else (None, None)
    species = Counter(a.get("asset_id") for a in actors_of_city).most_common(1)
    return {"color": color, "ink": ink, "name": city.get("name"), "size": _size_tier(len(actors_of_city)), "species": species[0][0] if species else None}


# Missing → build sequentially (this chapter carries the previous one forward, so the dead persist), then write the three files + `crowns/` under `saves/C<n>/`.
def _ensure_registries(chapter: str) -> None:
    chapter_dir = SAVES_DIR / chapter
    have_banners = (chapter_dir / "banners").is_dir()
    have_crowns = (chapter_dir / "crowns").is_dir()
    have_json = all((chapter_dir / f"{name}.json").exists() for name in ("cities", "kingdoms", "persons"))
    if have_banners and have_crowns and have_json:
        return
    n = int(chapter[1:])
    prev = {}
    if n > 1:
        _ensure_registries(f"C{n - 1}")
        prev = _load_registries(SAVES_DIR / f"C{n - 1}")
    save = load_save(chapter_dir / "map.wbox")
    if not have_json:
        for name, registry in _build_registries(save, prev).items():
            _write_registry(chapter_dir / f"{name}.json", registry)
    if not have_crowns:
        write_crowns(chapter_dir, save, SAVES_DIR / f"C{n - 1}" / "crowns" if n > 1 else None)
    if not have_banners:
        write_banners(chapter_dir, save, SAVES_DIR / f"C{n - 1}" / "banners" if n > 1 else None)


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
def _kingdom_visuals(kingdom: dict, actors_of_kingdom: list[dict], city_count: int, rank: int | None) -> dict:
    species = Counter(a.get("asset_id") for a in actors_of_kingdom).most_common(1)
    entry: dict = {"color": _kingdom_text_color(kingdom.get("color_id", "")), "name": kingdom.get("name"), "species": species[0][0] if species else None}
    if city_count:  # a defunct kingdom can momentarily hold none — omit the badge rather than show a `0`
        entry["cities"] = city_count
    if rank is not None:  # top-3 by population only — drives the gold/silver/bronze shimmering border
        entry["rank"] = rank
    return entry


def _load_registries(chapter_dir: Path) -> dict:
    return {name: json.loads(p.read_text()) if (p := chapter_dir / f"{name}.json").exists() else {} for name in ("cities", "kingdoms", "persons")}


# Carry each prior entry forward flagged dead (last-known visuals kept, `rank` dropped — a medal is meaningless once fallen), then let live entities overwrite.
def _merge(prev: dict, live: dict) -> dict:
    return {**{k: {**{f: val for f, val in v.items() if f != "rank"}, "dead": True} for k, v in prev.items()}, **live}


# Person registry entry (`[p id]` tag visuals): species + sex + non-unit profession. `dead` added by the merge; boats → None.
def _person_entry(actor: dict, profession: str | None) -> dict | None:
    if (actor.get("asset_id") or "").startswith("boat_"):
        return None
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


def main(argv: list[str]) -> int:
    save_path, argv, chapter = take_chapter(argv)
    try:
        sections = parse_sections(argv[0] if argv else None, _ALL_SECTIONS)
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 2
    if chapter:  # generate this chapter's registries (once) as a side effect — sequential carry-forward from C<n-1>
        _ensure_registries(chapter)
    save = load_save(save_path)
    map_stats = save.get("mapStats") or {}  # WB's own counters, period-accurate — the save carries the very dict `map.meta` duplicates.
    out: dict = {}
    if "cumulative" in sections:
        out["cumulative"] = _build_cumulative(map_stats)
    if "leaders" in sections:
        out["leaders"] = _build_leaders(save)
    if "metadata" in sections:
        out["metadata"] = _build_metadata(map_stats)
    if "snapshot" in sections:
        out["snapshot"] = _build_snapshot(save)
    emit(out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
