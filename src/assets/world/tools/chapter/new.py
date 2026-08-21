#!/usr/bin/env python3

# Bootstraps a new chapter from the live WorldBox save: archives it under `saves/C<n>/`, builds the registries (via `registries.py`) and a
# `chapter.json` skeleton. The chronicler then analyses (§III), writes `chapter.md`, and fills `title` + the favorite's `descriptor`. Docs: `tools/tools.md`.

import json
import shutil
import subprocess
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))

import registries
from shared import SAVES_DIR, UNITS_PER_YEAR, is_boat, load_data, load_save, render, take_chapter

_AGE_LABELS = load_data("world-ages.json")  # WB `WorldAgeLibrary` key → `{name, description}`; an unknown id falls back to the raw key.

# World-law alerts, each fired once ever (`chapter.json.tags` is the log). Adding one = an entry here + a row in `tags.md`; both args come from `_playable_kingdoms`.
_ALERTS = {
    "DISABLE_DROP_OF_THOUGHTS": {
        "condition": lambda kingdoms, present: all(kingdoms.get(species) for species in present),
        "message": "Tu peux désactiver la loi de monde Drop of Thoughts.",
    },
    "DISABLE_HANDSOME_MIGRANTS": {
        "condition": lambda kingdoms, present: all(any(pop >= _MIN_KINGDOM_POP for pop in kingdoms.get(species, ())) for species in present),
        "message": "Tu peux désactiver la loi de monde Handsome Migrants.",
    },
}

_CHRONICLER_ONLY = frozenset({"info", "report", "taxonomy"})  # no panel reads them; `report` is reworded per call, `taxonomy` derives from `identity.species`.
_HISTORY_S3DB = SAVES_DIR.parent / "history" / "map_stats.s3db"  # cumulative WB SQLite → one copy, overwritten each chapter, for the chronicler to browse
_LIVE_FILES = ("map.wbox", "preview.png")  # archived into the chapter dir under WB's own names; `map.wbox` alone regenerates everything for the chapter
_MIN_KINGDOM_POP = 4  # `DISABLE_HANDSOME_MIGRANTS` threshold — a kingdom of ≥ 4 inhabitants.
_RARITIES = ("epic", "legendary", "normal", "rare")
_TIERS = ("city", "clan", "culture", "family", "kingdom", "language", "subspecies")  # the favorite's bodies, unpacked in that order; each is optional
_TOOLS = Path(__file__).parent.parent
_WORLD_JSON = SAVES_DIR.parent / "history" / "world.json"  # world identity {name, description} — scaffolded empty at C1, chronicler-owned thereafter


# A chapter carries the values, not the way back to them nor WB's flavour — `_CHRONICLER_ONLY` names what goes, and why, at every depth of the tree.
def _drop_chronicler_keys(node):
    if isinstance(node, dict):
        return {key: _drop_chronicler_keys(value) for key, value in node.items() if key not in _CHRONICLER_ONLY}
    return [_drop_chronicler_keys(value) for value in node] if isinstance(node, list) else node


# The save's `favorite`-flagged actor (WB's in-game marker), detail folded; the chronicler's `descriptor` carries forward while it stays the same favorite.
def _featured_favorite(chapter: str, fav_id: int, prev_favorite: dict | None) -> dict | None:
    favorite = _run("actor/info.py", fav_id, "full", chapter)
    if favorite is None:
        return None
    _fold_favorite_detail(favorite)
    if prev_favorite and (prev_favorite.get("metadata") or {}).get("id") == fav_id and (descriptor := prev_favorite.get("descriptor")):
        favorite["descriptor"] = descriptor  # same favorite → keep the chronicler's epithet
    return favorite


# `(code, message)` of alerts whose condition holds now and that haven't fired in an earlier chapter (`already` = the tags those chapters carry).
def _fired_alerts(save: dict, already: set) -> list[tuple[str, str]]:
    kingdoms, present = _playable_kingdoms(save)
    if not present:  # no playable species yet → every `all(...)` would hold vacuously
        return []
    return [(code, spec["message"]) for code, spec in _ALERTS.items() if code not in already and spec["condition"](kingdoms, present)]


# Drops the loyalty summary and both stock lists, keeping their `total` — the panels print that alone, the sections still itemising each modifier and piece.
def _fold_city_detail(city: dict) -> None:
    city.get("loyalty", {}).pop("top_drivers", None)
    _fold_total(city, "books", "equipment")


# Folds the favorite's two heavy blocks: `creature_traits` becomes the rarity summary the panel renders, `equipment` goes — both stay whole in `actor/info.py`.
def _fold_favorite_detail(favorite: dict) -> None:
    favorite.pop("equipment", None)
    favorite["traits"] = _rarity_counts((favorite.pop("creature_traits", None) or {}).get("ids"))


# Keeps `opinion.top_drivers` on the ally/enemy ties only — a summary earns its place where it drives events. The `relations` section still gives the full ledger.
def _fold_kingdom_detail(kingdom: dict) -> None:
    for relation in kingdom.get("relations") or []:
        if relation.get("status") == "neutral":
            relation.get("opinion", {}).pop("top_drivers", None)
    _fold_total(kingdom, "equipment")


# Both libraries tallied per WB trait group, the panel's axis; `stats` goes too — dropped here, not in `_CHRONICLER_ONLY`, which would take the favorite's own block.
def _fold_subspecies_detail(subspecies: dict) -> None:
    subspecies.pop("stats", None)
    sworn = subspecies.pop("traits", None) or {}
    counts = Counter(g for lib in ("biology", "birth") if isinstance(block := sworn.get(lib), dict) for g in block.values())
    subspecies["traits"] = dict(sorted(counts.items()))


# The panels read nothing but the `total`, whichever form `full` handed over — nothing is lost, the chapter's own `map.wbox` replaying any section.
def _fold_total(entity: dict, *keys: str) -> None:
    for key in keys:
        if isinstance(block := entity.get(key), dict):
            entity[key] = {"total": block.get("total", 0)}


# Tallies a clan's sworn traits or a culture's held ones per WB group, the panel's axis — `full` summarises them to `{id: group}`, the section keeping each whole.
def _fold_trait_groups(entity: dict) -> None:
    counts = Counter((entity.pop("traits", None) or {}).get("ids", {}).values())
    entity["traits"] = dict(sorted(counts.items()))


# Playable species alive in the world (species.json `playable` flag) + {species: [kingdom populations]} keyed by each kingdom's dominant playable species.
def _playable_kingdoms(save: dict) -> tuple[dict, set]:
    playable = {species for species, data in load_data("species.json").items() if data.get("playable")}
    members_by_kingdom: dict[int, Counter] = {}
    species_seen: set = set()
    for actor in save.get("actors_data") or []:  # one pass gives both which species walk the world and each kingdom's species mix
        if is_boat(actor):
            continue
        asset = actor.get("asset_id")
        species_seen.add(asset)
        if kid := actor.get("civ_kingdom_id"):
            members_by_kingdom.setdefault(kid, Counter())[asset] += 1
    kingdoms: dict = {}
    for members in members_by_kingdom.values():
        if (dominant := members.most_common(1)[0][0]) in playable:
            kingdoms.setdefault(dominant, []).append(members.total())
    return kingdoms, species_seen & playable


# One scan of the prior chapters, for all they arbitrate: alert de-dup, descriptor carry-forward, a null→real favorite, a turned age, an unadvanced save.
def _prior_context(n: int) -> tuple[set, dict | None, dict]:
    tags: set = set()
    favorite, world = None, {}
    for prior in range(1, n):
        if not (prior_json := SAVES_DIR / f"C{prior}" / "chapter.json").exists():
            continue
        data = json.loads(prior_json.read_text())
        tags |= set(data.get("tags") or [])
        if prior == n - 1:
            favorite = data.get("favorite")
            world = (data.get("world") or {}).get("metadata") or {}
    return tags, favorite, world


# Creature traits tallied by rarity off the summarised `{id: rarity}` map, all four buckets at 0 — a missing key would blank the panel cell, not zero it.
def _rarity_counts(traits: dict | None) -> dict:
    counts = Counter(rarity.lower() for rarity in (traits or {}).values())
    return {rarity: counts.get(rarity, 0) for rarity in _RARITIES}


# Runs a sibling `info.py` → its parsed JSON stdout, `None` (stderr surfaced) on failure or empty output. `sys.executable` so a venv never forks children elsewhere.
def _run(rel_path: str, *args) -> dict | None:
    result = subprocess.run([sys.executable, str(_TOOLS / rel_path), *map(str, args)], capture_output=True, text=True, check=False)
    if result.returncode:
        print(f"  ⚠ {rel_path} {' '.join(map(str, args))}: {result.stderr.strip()[:200]}", file=sys.stderr)
        return None
    return json.loads(result.stdout) if result.stdout.strip() else None


# Runs `(callable, *args)` tuples at once, results in order (`None` call → `None`) — each `info.py` re-parses the whole save and only reads, so overlap is free.
def _run_together(*calls: tuple | None) -> list:
    with ThreadPoolExecutor(max_workers=max(len(calls), 1)) as pool:
        jobs = [pool.submit(*call) if call else None for call in calls]
    return [job.result() if job else None for job in jobs]


def main(argv: list[str]) -> int:
    live_wbox = take_chapter([])[0]  # no `C<n>` token → the live save path
    if not live_wbox.exists():
        print(f"no live save at {live_wbox}", file=sys.stderr)
        return 2
    n = max((int(p.name[1:]) for p in SAVES_DIR.glob("C*") if p.is_dir() and p.name[1:].isdigit()), default=0) + 1
    chapter, chapter_dir = f"C{n}", SAVES_DIR / f"C{n}"
    if chapter_dir.exists():
        print(f"{chapter} already exists — remove {chapter_dir} to regenerate", file=sys.stderr)
        return 1

    live = load_save(live_wbox)
    actors = live.get("actors_data") or []
    world_time = round(float(live["mapStats"].get("world_time", 0)), 2)
    fav_id = next((a["id"] for a in actors if a.get("favorite") is True), None)
    already, prev_favorite, prev_world = _prior_context(n)
    just_designated = fav_id is not None and prev_favorite is None  # favorite null→real: earns a chapter even at an unchanged timestamp + the NEW-FAVORITE tag

    # Read off the chapter before rather than by re-parsing its save for one field — `world/info.py` rounds it exactly as the line above does, to the digit.
    if (prev_time := prev_world.get("world_time")) is not None and world_time <= prev_time and not just_designated and "--force" not in argv:
        print(f"✗ save not advanced (world_time {world_time} ≤ C{n - 1} {prev_time}), no new favorite either — advance in WorldBox or --force", file=sys.stderr)
        return 1

    chapter_dir.mkdir(parents=True)
    live_dir = live_wbox.parent
    for name in _LIVE_FILES:
        if (src := live_dir / name).exists():
            shutil.copy2(src, chapter_dir / name)
    if (s3db := live_dir / "map_stats.s3db").exists():
        shutil.copy2(s3db, _HISTORY_S3DB)
    if not _WORLD_JSON.exists():  # C1 → scaffold the empty world-identity template for the chronicler to fill
        _WORLD_JSON.write_text(json.dumps({"description": "", "name": ""}, ensure_ascii=False, indent=2) + "\n")

    registries.ensure(chapter, live)  # `live` is handed over so it spares itself a re-parse of the save we already hold

    # Two waves rather than a call per tier: the favorite's metadata names the bodies it belongs to, so none of those can start until it has landed.
    world, favorite = _run_together(
        (_run, "world/info.py", chapter),
        (_featured_favorite, chapter, fav_id, prev_favorite) if fav_id is not None else None,
    )

    if world is None:
        print("✗ world/info.py failed — check the save", file=sys.stderr)
        return 1

    city = clan = culture = family = kingdom = language = subspecies = None
    if favorite:
        meta = favorite.get("metadata") or {}
        calls = [(_run, f"{tier}/info.py", tid, "full", chapter) if (tid := (meta.get(tier) or {}).get("id")) else None for tier in _TIERS]
        city, clan, culture, family, kingdom, language, subspecies = _run_together(*calls)
        folds = (  # A lineage has nothing of its own to fold, hence its absence here; every tier that does is folded alike.
            (city, _fold_city_detail),
            (clan, _fold_trait_groups),
            (culture, _fold_trait_groups),
            (kingdom, _fold_kingdom_detail),
            (language, _fold_trait_groups),
            (subspecies, _fold_subspecies_detail),
        )
        for block, fold in folds:
            if block:
                fold(block)
        # Rosters cut to their headcount, and the libraries of a custom and a tongue to their count as a town's is — the volumes stay in their own `books`.
        for tier, *keys in ((clan, "members"), (culture, "members", "books"), (family, "members"), (language, "speakers", "books"), (subspecies, "members")):
            if tier:
                _fold_total(tier, *keys)

    age_id = live["mapStats"].get("world_age_id") or ""
    # Mechanical event codes — `chapter.json.tags` is their single source of truth, no separate log.
    tags = ["NEW-FAVORITE"] if just_designated else []
    if (prev_age_id := prev_world.get("age_id")) and age_id != prev_age_id:
        tags.append("NEW_AGE")

    # First hull ever afloat — WB's boat techs leave no trace in the save, so the boat itself is the discovery. One-time, like the `DISABLE_*` alerts.
    if "NAVIGATION" not in already and any(is_boat(a) for a in actors):
        tags.append("NAVIGATION")
    new_alerts = _fired_alerts(live, already)
    tags += [code for code, _message in new_alerts]

    age_label = (_AGE_LABELS.get(age_id) or {}).get("name") or age_id

    # `title` stays empty — the chronicler writes it post-audit; everything else is script-generated.
    chapter_json = {
        "age_label": age_label,
        "city": city,
        "clan": clan,
        "culture": culture,
        "family": family,
        "favorite": favorite,
        "kingdom": kingdom,
        "language": language,
        "subspecies": subspecies,
        "tags": tags,
        "title": "",
        "world": world,
    }

    # `render`, not `json.dumps(indent=2)`: same tree, near a quarter fewer characters once branches inline. No `_strip_none` — `tags: []` and a `null` city belong.
    (chapter_dir / "chapter.json").write_text(render(_drop_chronicler_keys(chapter_json)) + "\n")

    year = int(world_time / UNITS_PER_YEAR)
    counts = " · ".join(  # The chronicler's own order: the map first, then who fills it. Each name pairs with its label here rather than twice below.
        f"{len(json.loads((chapter_dir / f'{name}.json').read_text()))} {label}"
        for name, label in (
            ("cities", "cités"),
            ("kingdoms", "royaumes"),
            ("clans", "clans"),
            ("families", "lignées"),
            ("subspecies", "sous-espèces"),
            ("persons", "personnes"),
        )
    )
    fav_name = ((favorite or {}).get("metadata") or {}).get("name")
    print(f"✓ {chapter} — an {year}, {age_label} (world_time {world_time})")
    print(f"  registres: {counts}")
    print(f"  favori: {fav_name or 'aucun (aucun acteur marqué favori dans la save)'}")
    for _code, message in new_alerts:
        print(f"  ⚠ {message}")
    todo = "analyse §III · chapter.md"
    if favorite and not favorite.get("descriptor"):  # new favorite → its epithet is the one favorite field the chronicler still writes
        todo += " · descriptor du favori"
    if new_alerts:
        todo += " · relayer l'alerte"
    print(f"  → chroniqueur: {todo}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
