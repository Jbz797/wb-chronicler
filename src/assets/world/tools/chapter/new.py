#!/usr/bin/env python3

# Bootstraps a new chapter from the live WorldBox save: archives it under `saves/C<n>/`, builds the registries/crowns/banners (via `registries.py`) and a
# `chapter.json` skeleton. The chronicler then analyses (§III), writes `chapter.md`, and fills `title` + the favorite's `descriptor`. Docs: `tools/tools.md`.

import json
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
import alerts
import registries
from shared import SAVES_DIR, UNITS_PER_YEAR, load_data, load_save, take_chapter

_AGE_LABELS = load_data("world-ages.json")  # WB `WorldAgeLibrary` key → its French title (the game's `locales/fr/world_ages`); unknown ids fall back to the raw id.
_HISTORY_S3DB = SAVES_DIR.parent / "history" / "map_stats.s3db"  # cumulative WB SQLite → one copy, overwritten each chapter, for the chronicler to browse
_LIVE_FILES = ("map.wbox", "preview.png")  # archived into the chapter dir under WB's own names; `map.wbox` alone regenerates everything for the chapter
_RARITIES = ("epic", "legendary", "normal", "rare")
_TOOLS = Path(__file__).parent.parent
_WORLD_JSON = SAVES_DIR.parent / "history" / "world.json"  # world identity {name, description} — scaffolded empty at C1, chronicler-owned thereafter


# The save's `favorite`-flagged actor (WB's in-game marker), UI-slimmed; the chronicler's `descriptor` carries forward while it stays the same favorite.
def _featured_favorite(chapter: str, fav_id: int, prev_favorite: dict | None) -> dict | None:
    favorite = _run("actor/info.py", fav_id, "full", chapter)
    if favorite is None:
        return None
    _slim_favorite(favorite)
    if prev_favorite and (prev_favorite.get("metadata") or {}).get("id") == fav_id and (descriptor := prev_favorite.get("descriptor")):
        favorite["descriptor"] = descriptor  # same favorite → keep the chronicler's epithet
    return favorite


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


# Runs a sibling `info.py`, returning its parsed JSON stdout — `None` (stderr surfaced) on failure or empty output.
def _run(rel_path: str, *args) -> dict | None:
    result = subprocess.run(["python3", str(_TOOLS / rel_path), *map(str, args)], capture_output=True, text=True, check=False)
    if result.returncode:
        print(f"  ⚠ {rel_path} {' '.join(map(str, args))}: {result.stderr.strip()[:200]}", file=sys.stderr)
        return None
    return json.loads(result.stdout) if result.stdout.strip() else None


# UI projection of a favorite: the rich `creature_traits`/`equipment` (chronicler-only, in `actor/info.py`) collapse to the rarity summary the panel renders.
def _slim_favorite(favorite: dict) -> None:
    counts = Counter(trait.get("rarity", "").lower() for trait in favorite.pop("creature_traits", []))
    favorite.pop("equipment", None)
    favorite["traits"] = {rarity: counts.get(rarity, 0) for rarity in _RARITIES}


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
    world_time = round(float(live["mapStats"].get("world_time", 0)), 2)
    prev_dir = SAVES_DIR / f"C{n - 1}"
    fav_id = next((a["id"] for a in live.get("actors_data") or [] if a.get("favorite") is True), None)
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

    registries.ensure(chapter)  # builds this chapter's registries/crowns/banners (carry-forward from C<n-1>)
    world = _run("world/info.py", chapter)  # the world panel (emit only)
    if world is None:
        print("✗ world/info.py failed — check the save", file=sys.stderr)
        return 1

    favorite = _featured_favorite(chapter, fav_id, prev_favorite) if fav_id is not None else None
    city = kingdom = None
    if favorite:
        meta = favorite.get("metadata") or {}
        if cid := (meta.get("city") or {}).get("id"):
            city = _run("city/info.py", cid, "full", chapter)
        if kid := (meta.get("kingdom") or {}).get("id"):
            kingdom = _run("kingdom/info.py", kid, "full", chapter)

    # tags = mechanical event codes (favorite designation, new age, world-law alerts) — `chapter.json.tags` is their single source of truth, no separate log.
    age_id = live["mapStats"].get("world_age_id") or ""
    tags = ["NEW-FAVORITE"] if just_designated else []
    if prev_age_id and age_id != prev_age_id:  # the world turned to a new age this chapter
        tags.append("NEW_AGE")
    new_alerts = alerts.fired(live, already)
    tags += [code for code, _message in new_alerts]
    if not _WORLD_JSON.exists():  # C1 → scaffold the empty world-identity template for the chronicler to fill
        _WORLD_JSON.write_text(json.dumps({"description": "", "name": ""}, ensure_ascii=False, indent=2) + "\n")

    age_label = _AGE_LABELS.get(age_id, age_id)
    # `title` stays empty — the chronicler writes it post-audit; everything else is script-generated.
    chapter_json = {"age_label": age_label, "city": city, "favorite": favorite, "kingdom": kingdom, "tags": tags, "title": "", "world": world}
    (chapter_dir / "chapter.json").write_text(json.dumps(chapter_json, ensure_ascii=False, indent=2) + "\n")

    year = int(world_time / UNITS_PER_YEAR)
    counts = {name: len(json.loads((chapter_dir / f"{name}.json").read_text())) for name in ("cities", "kingdoms", "persons")}
    fav_name = (favorite or {}).get("metadata", {}).get("name")
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
