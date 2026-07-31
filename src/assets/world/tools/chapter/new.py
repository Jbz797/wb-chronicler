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

_AGE_LABELS = load_data("world-ages.json")  # WB `WorldAgeLibrary` key → its French title (the game's `locales/fr/world_ages`); unknown ids fall back to the raw id.

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

_HISTORY_S3DB = SAVES_DIR.parent / "history" / "map_stats.s3db"  # cumulative WB SQLite → one copy, overwritten each chapter, for the chronicler to browse
_LIVE_FILES = ("map.wbox", "preview.png")  # archived into the chapter dir under WB's own names; `map.wbox` alone regenerates everything for the chapter
_MIN_KINGDOM_POP = 4  # `DISABLE_HANDSOME_MIGRANTS` threshold — a kingdom of ≥ 4 inhabitants.
_RARITIES = ("epic", "legendary", "normal", "rare")
_TOOLS = Path(__file__).parent.parent
_WORLD_JSON = SAVES_DIR.parent / "history" / "world.json"  # world identity {name, description} — scaffolded empty at C1, chronicler-owned thereafter


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


# Drops the loyalty summary, keeping only its `total` — the panel prints that alone, and `city/info.py <id> loyalty` still itemises every modifier.
def _fold_city_detail(city: dict) -> None:
    city.get("loyalty", {}).pop("top_drivers", None)


# Folds the favorite's two heavy blocks: `creature_traits` becomes the rarity summary the panel renders, `equipment` goes — both stay whole in `actor/info.py`.
def _fold_favorite_detail(favorite: dict) -> None:
    counts = Counter(trait.get("rarity", "").lower() for trait in favorite.pop("creature_traits", []))
    favorite.pop("equipment", None)
    favorite["traits"] = {rarity: counts.get(rarity, 0) for rarity in _RARITIES}


# Keeps `opinion.top_drivers` on the ally/enemy ties only — a summary earns its place where it drives events. The `relations` section still gives the full ledger.
def _fold_kingdom_detail(kingdom: dict) -> None:
    for relation in kingdom.get("relations") or []:
        if relation.get("status") == "neutral":
            relation.get("opinion", {}).pop("top_drivers", None)


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


# One scan of the prior chapters → `(all tags ever set, previous favorite, previous age id)`: alert de-dup, descriptor carry-forward, null→real + new-age checks.
def _prior_context(n: int) -> tuple[set, dict | None, str | None]:
    tags: set = set()
    favorite = age_id = None
    for prior in range(1, n):
        if not (prior_json := SAVES_DIR / f"C{prior}" / "chapter.json").exists():
            continue
        data = json.loads(prior_json.read_text())
        tags |= set(data.get("tags") or [])
        if prior == n - 1:
            favorite = data.get("favorite")
            age_id = ((data.get("world") or {}).get("metadata") or {}).get("age_id")
    return tags, favorite, age_id


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
    prev_dir = SAVES_DIR / f"C{n - 1}"
    fav_id = next((a["id"] for a in actors if a.get("favorite") is True), None)
    already, prev_favorite, prev_age_id = _prior_context(n)
    just_designated = fav_id is not None and prev_favorite is None  # favorite null→real: earns a chapter even at an unchanged timestamp + the NEW-FAVORITE tag
    if n > 1 and (prev_dir / "map.wbox").exists():
        prev_time = round(float(load_save(prev_dir / "map.wbox")["mapStats"].get("world_time", 0)), 2)
        if world_time <= prev_time and not just_designated and "--force" not in argv:
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

    # Two waves rather than four calls in a row: the favorite's metadata names the city and kingdom, so those two can only start once it has landed.
    world, favorite = _run_together(
        (_run, "world/info.py", chapter),
        (_featured_favorite, chapter, fav_id, prev_favorite) if fav_id is not None else None,
    )

    if world is None:
        print("✗ world/info.py failed — check the save", file=sys.stderr)
        return 1

    city = kingdom = None
    if favorite:
        meta = favorite.get("metadata") or {}
        cid, kid = (meta.get("city") or {}).get("id"), (meta.get("kingdom") or {}).get("id")
        city, kingdom = _run_together(
            (_run, "city/info.py", cid, "full", chapter) if cid else None,
            (_run, "kingdom/info.py", kid, "full", chapter) if kid else None,
        )
        if city:
            _fold_city_detail(city)
        if kingdom:
            _fold_kingdom_detail(kingdom)

    age_id = live["mapStats"].get("world_age_id") or ""
    # Mechanical event codes — `chapter.json.tags` is their single source of truth, no separate log.
    tags = ["NEW-FAVORITE"] if just_designated else []
    if prev_age_id and age_id != prev_age_id:
        tags.append("NEW_AGE")

    # First hull ever afloat — WB's boat techs leave no trace in the save, so the boat itself is the discovery. One-time, like the `DISABLE_*` alerts.
    if "NAVIGATION" not in already and any(is_boat(a) for a in actors):
        tags.append("NAVIGATION")
    new_alerts = _fired_alerts(live, already)
    tags += [code for code, _message in new_alerts]

    age_label = _AGE_LABELS.get(age_id, age_id)

    # `title` stays empty — the chronicler writes it post-audit; everything else is script-generated.
    chapter_json = {"age_label": age_label, "city": city, "favorite": favorite, "kingdom": kingdom, "tags": tags, "title": "", "world": world}

    # `render`, not `json.dumps(indent=2)`: same tree, a third fewer characters once branches inline. No `_strip_none` — `tags: []` and a `null` city belong here.
    (chapter_dir / "chapter.json").write_text(render(chapter_json) + "\n")

    year = int(world_time / UNITS_PER_YEAR)
    counts = {name: len(json.loads((chapter_dir / f"{name}.json").read_text())) for name in ("cities", "kingdoms", "persons")}
    fav_name = ((favorite or {}).get("metadata") or {}).get("name")
    print(f"✓ {chapter} — an {year}, {age_label} (world_time {world_time})")
    print(f"  registres: {counts['cities']} cités · {counts['kingdoms']} royaumes · {counts['persons']} personnes")
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
