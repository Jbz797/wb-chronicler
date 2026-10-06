#!/usr/bin/env python3

# Bootstraps a new chapter from the live WorldBox save: archives it under `saves/C<n>/`, builds its registries (`registries.py`) and `chapter.json` (`fold.py`).
# The recap steers the chronicler's analysis; `--finalize` then lays out step 5 and hands the audit to `docs/review.md`, `--deliver` the delivery.

import json
import os
import random
import re
import shutil
import sqlite3
import subprocess
import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from contextlib import suppress
from datetime import datetime, timezone
from functools import cache
from math import inf
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))

import registries
from actor_stats import adult_age, build_actor_stats_context, is_egg
from echo import echoes
from fold import drop_chronicler_keys, fold_bodies, fold_favorite_detail, fold_world
from founding import city_zones, settle_gates
from grid import LazyTileGrid, tile_layer, tile_runs
from islands import compute_islands_cached
from shared import (
    CHAPTER_CAP,
    CHAPTER_FLOOR,
    HISTORY_S3DB,
    SAVES_DIR,
    UNITS_PER_YEAR,
    actor_age,
    chapter_length,
    chapter_world_time,
    index_by_id,
    is_boat,
    is_sapient,
    latest_chapter,
    life_stage,
    live_save,
    load_data,
    load_save,
    log_entries,
    render,
    rounded_world_time,
    world_laws,
    worldbox_running,
    write_save,
)

# The chapter's own tongue, for the audit account the player reads beside the chapter.
_ACCOUNT = {
    "en": {
        "facts": "Fact check: {} gaps fixed",
        "none": "not applicable",
        "reaudit": "Re-audit: {} gaps fixed",
        "story": "Story check: {} gaps fixed",
    },
    "fr": {
        "facts": "Vérification des faits : {} écarts corrigés",
        "none": "non applicable",
        "reaudit": "Réaudit : {} écarts corrigés",
        "story": "Vérification du récit : {} écarts corrigés",
    },
}

_AGE_LABELS = load_data("world-ages.json")  # WB `WorldAgeLibrary` key → `{name, description}`; an unknown id falls back to the raw key.
_AGE_SLOTS = ("age_hope", *("age_unknown",) * 7)  # WB resolves them one at a time; a world always opens on the first

_ALERTS = {"DISABLE_DROP_OF_THOUGHTS": "world_law_drop_of_thoughts"}  # each alert by the law it asks the player to cut — a state while that law stays on

# What a baptism's check weighs — in no doc, a world being named once: handed to the audit with its target, as a chapter's asks are.
_BAPTISM = "a world's name and description are checked as a chapter is, and the name is worth what it says of the ground"

_CHOICE = (  # what a pick weighs, said where the pick is made: needed at a world's start and at a favorite's death alone, in no doc
    "a thinking body only: `sapient: true` in `actor … metadata`",
    "weighed in depth: traits, political standing, narrative promise, age, where it stands, what surrounds it…",
    "the world's first favorite also needs room for a homestead — a fitting biome around it, resources, obstacles at a distance; later ones, while nothing is built",
)
# What the chapter owes a favorite just dead — in no doc, a death being rare: the recap says it, the targets hand it to the audit.
_DEATH = "the death section opens the chapter: how he died, pieced together as far as the data allow (§ Déduction des meurtres), what he leaves, the handover"

_DESCRIPTOR_CAP = 64

_DESIGNATION = (  # putting the chosen favorite to the player — an exchange no chapter shows, so it is said where it is acted on
    "announce it to the player with `tools/map/show.py <x,y>`: only the map finds it among a thousand",
    "his word given (you will embody it), have him close WorldBox: `tools/chapter/favorite.py <id>` rebuilds this chapter around it",
    "refused: another if one is worth it, never of the kind turned down — else the chapter goes without, the question returning next save",
)

_DEV_NOTE = (  # what a developer's closing note may hold — flagged, never done by the chronicler's own hand
    "doc adjustment: a passage of docs/ unclear, contradictory, out of date, or a term to harmonise — flagged, never corrected by your hand",
    "script improvement spotted on the way: a bug, a field misread, a wrong formula, an awkward output — name the file; no code change of your own",
    "doc and recap at odds: the recap is right for now, but one of the two needs fixing — say which",
    "obscure field: one whose meaning stays uncertain, the wiki included",
    "costly reading: a step that ate the context — say what you read and what you sought — or a passage, an output section, costing without serving: say which",
    "new tag: an important kind of event that no code in docs/tags.md covers",
    "missing tool: a recurring analysis that deserves its own script",
    "and any other observation within your remit",
)

_DRAFT_HEADINGS = {"en": "Draft", "fr": "Brouillon"}  # one per language the settings panel offers: a language added there owes its word here

# Everything a reset sweeps away. `tiles` holds the ticking ones (fires, melting ice), not the ground — that lives in `tileMap`/`tileArray`/`tileAmounts`.
_EMPTIED = (
    "actors_data",
    "alliances",
    "armies",
    "books",
    "cities",
    "clans",
    "conwayCreator",
    "conwayEater",
    "cultures",
    "families",
    "fire",
    "frozen_tiles",
    "items",
    "kingdoms",
    "languages",
    "plots",
    "relations",
    "religions",
    "subspecies",
    "tiles",
    "wars",
)

_EVENT = "an event the chapter owes its reader, glossed in docs/tags.md"  # said to the chronicler at the recap, and to his auditors with their targets
_FLAGS = frozenset({"--deliver", "--description", "--finalize", "--name", "--reset", "--reset-asked"})  # all `main` reads — others are refused as typos
_GEO_ASSETS = re.compile(r"(volcano|geyser)", re.IGNORECASE)  # WB's three natural landmarks, `acid_geyser` included — all a bare world keeps of `buildings`
_GROWN = frozenset({"adult", "teen"})  # the stages a kind may be counted on: past childhood, an elder read as the adult it is — its span is not asked
_H1_CAP = 68  # in no doc: `--finalize` gives it as the H1 falls due, and holds the audit on it
_INDEX_JSON = SAVES_DIR / "index.json"  # the chapter list the reader's nav reads, so it need not open every `chapter.json` to name them
_KINGDOM_FLOOR = 2  # even a Tiny map must raise two crowns before it stands alone: one war would else leave a single people
_LAND_PER_KINGDOM = 52_044  # a quarter of what a map carries once grown — measured at ~12k land tiles per crown on two worlds
_LAW_NAMES = load_data("world-laws.json")  # WB's own English title of each law, the label a wiki row goes by

# A trial, in no doc: what a lineage's summary skips of `subspecies … traits` — the four WB makes it think by, every favorite's lot, and what its bodies wear.
_LINEAGE = "a lineage's summary leaves out its `advanced_brain` group, which every thinking lineage bears, and its `birth` block, told by the body's own"

_LIVE_FILES = ("map.wbox", "preview.png")  # archived into the chapter dir under WB's own names; `map.wbox` alone regenerates everything for the chapter
_LONG_AGE_YEARS = (35, 55)  # WB draws an age's span when it opens; only the two bleak ones run shorter
_MAP_BLOCK = 64  # WB sizes a world in blocks of this many tiles, every stock size over: Tiny 2×2 = 128, Iceberg 9×9 = 576. Not `ZONE_TILES`, the city grid.

# The two mods of `mods/`, each by the key it stamps a save with: the world's time as it wrote it, in the world's own custom data.
_MODS = {"Faithful Saves": "faithful_saved_at", "Wandering Clouds": "wandering_clouds_saved_at"}

_MODS_DIR = "../../../mods"  # from the chronicler's own directory, where he runs this script

# What a place's check weighs — in no doc: handed to the audit with the names a chapter gave, which no auditor was sent to before.
_PLACE = "a place named this chapter is checked as the chapter is: its point falls on what its kind names, and its kind and sign say what the chapter says of it"

_PLACES_JSON = SAVES_DIR.parent / "history" / "places.json"  # the toponyms the chronicler coins — seeded with the world's isles at C1, his thereafter
_PLAIN = "plain text with no tag"  # what a field of `chapter.json` is written in: its panel prints it as it stands, brackets and all
_RECAP_RULE = "  " + "─" * 40  # closes each block of the recap's report — the chapter's state, what fired, the journal — the last two only where they print

# Put to the player at the first chapter, before a line is written. The three commands answer it, and the naming brief rides with the third.
_RESET_PROMPT = (
    "? first chapter — nothing is written until the player has answered. Put this to him, in one go:",
    "  « Do you want to start over from a bare map — relief, biomes, volcanoes and geysers kept, everything else erased (creatures, trees, plants, ores,",
    "    buildings, kingdoms…), back to year 1 of the Age of Hope with a new genetic seed? And if so, shall I name it too? »",
    "  → no: `tools/chapter/new.py --reset-asked`",
    "  → reset alone: `tools/chapter/new.py --reset`, and the world keeps the name and description it carries",
    '  → reset and naming: `tools/chapter/new.py --reset --name "…" --description "…"`',
    "    the name is forged after a survey of its geography, the one thing the reset spares: in the chronicle's own voice, on the ground,",
    "    the mood or whatever outlasts the ages, never the age itself. Yours alone to choose — his yes was the agreement.",
)

_SEEDED = ("islands", "lakes", "rivers", "seas")  # the gazetteer's books the survey seeds by id, `places` being the chronicler's own
_SETTINGS_JSON = SAVES_DIR.parent / "history" / "settings.json"  # the reader's settings, where the player's workshop switch sits beside the live save's path
_SHORT_AGES = frozenset({"age_despair", "age_ice"})
_SHORT_AGE_YEARS = (30, 40)
_STAMP_SLACK = 1  # seconds a mod's stamp may stray from the save's own time: WB stores it less finely, a save from before lies years off
_SUBAGENT_GRACE = 120  # seconds: a transcript written this lately may be a sub-agent still at work, not to be pulled from under it

# What a trait summary is — in no doc: said to the chronicler as one falls due, and handed to the audit with the targets that name one.
_SUMMARY = f"what those traits make of the body, {_PLAIN}; never a list, a tally of traits or a figure that ages — read alone, it may echo the chapter"

_SUMMARY_CAP = 400
_SUMMARY_CAPS = {"subspecies": 500}  # a lineage's alone is given more room: a biology is born whole, where the other tiers gather their traits one by one
_TAG = re.compile(r"\[[a-z] [^\s\]]+(?: ([^\]]+))?\]")  # a marker as a title shows it, and as its cap counts it: its text alone, a bare one nothing
_TIERS = ("alliance", "city", "clan", "culture", "family", "kingdom", "language", "religion", "subspecies")  # the favorite's bodies; each is optional
_TOOLS = Path(__file__).parent.parent

# Where each tier keeps its traits in the raw save — read straight from both `map.wbox` files, so no digest need ride along in the chapter to spot a change.
_TRAIT_SOURCES = {
    "clan": ("clans", ("saved_traits",)),
    "culture": ("cultures", ("saved_traits",)),
    "favorite": ("actors_data", ("saved_traits",)),
    "language": ("languages", ("saved_traits",)),
    "religion": ("religions", ("saved_traits",)),
    "subspecies": ("subspecies", ("saved_actor_birth_traits", "saved_traits")),
}

_WORLD_ONLY = (  # the chapter while no favorite stands — in no doc, a world having one most of its life: the recap says it, the targets hand it to the audit
    "the world's news: its lands, beasts and plants, the thinking kinds' first steps and meetings, deaths, births…",
    "the thinking kinds: the most promising if they are many, and why none carries the chronicle yet",
    "no circles: a single `---`, before the closing paragraph",
)

_WORLD_JSON = SAVES_DIR.parent / "history" / "world.json"  # world identity and span, off the save each chapter — the reader shows the name, the chronicler the rest


# A body half-read is a chapter half-told, and its folder would push the next run on to C<n+1>: it goes, so a rerun lands on the same chapter.
def _abandon(chapter_dir: Path, failed: list[str]) -> int:
    shutil.rmtree(chapter_dir)
    print(f"✗ {', '.join(failed)} failed — nothing written, report the error above and run again once it answers", file=sys.stderr)
    return 1


# The bare world's own age, drawn as WB draws it — the span is random, so two resets of the same map never run to the same calendar.
def _age_duration(age_id: str) -> float:
    low, high = _SHORT_AGE_YEARS if age_id in _SHORT_AGES else _LONG_AGE_YEARS
    return float(random.randint(low, high) * UNITS_PER_YEAR)


# The chapter and what it wrote into `chapter.json`, with what the recap asked of this chapter alone between brackets: the auditors never see the recap.
def _audit_targets(n: int, facts: dict) -> str:
    asked = [
        *([] if facts["favorite"] else [f"no favorite: {' / '.join(_WORLD_ONLY)}"]),
        *([f"favorite dead: {_DEATH}"] if facts["mourned"] else []),
        *([f"events: {', '.join(facts['events'])}, each {_EVENT}"] if facts["events"] else []),
        *([f"trait summaries: {_SUMMARY}"] if any(field.endswith(".traits") for field in facts["audited"]) else []),
        *([_LINEAGE] if "subspecies.traits" in facts["audited"] else []),
    ]
    shape = f" [{' — '.join(asked)}]" if asked else ""
    written = f", saves/C{n}/chapter.json ({', '.join(facts['audited'])})" if facts["audited"] else ""
    named = f", history/places.json ({', '.join(f'« {name} »' for name in facts['named'])}) [{_PLACE}]" if facts["named"] else ""
    return f"saves/C{n}/chapter.md{shape}{written}{named}"


# The whole rewind, in the order WB's fields depend on one another: survivors first, `id_building` counting from them. Of `buildings`, only landmarks stand.
def _bare_world(save: dict, name: str, description: str) -> None:
    save["buildings"] = [b for b in save.get("buildings") or [] if _GEO_ASSETS.search(b.get("asset_id") or "")]
    for landmark in save["buildings"]:  # stamped afresh: the clock restarts below, and a peak left on the old one would read older than the world it stands in
        landmark["created_time"] = 0.0
    for key in _EMPTIED:
        save[key] = []

    stats = save["mapStats"]
    stats.pop("is_world_ages_paused", None)  # WB's own « running »: the player's wheel alone writes it, so a pause carried over would still the new world's ages
    _reset_counters(stats)
    stats["current_world_ages_duration"] = _age_duration(_AGE_SLOTS[0])
    stats["description"] = description or stats.get("description") or ""
    stats["id_building"] = max((b["id"] for b in save["buildings"]), default=0) + 1  # the landmarks keep their high ids, and 1 would collide with them
    stats["life_dna"] = _life_dna()
    stats["name"] = name or stats.get("name") or ""
    stats["player_mood"] = stats.get("player_mood") or "serene"  # WB's own default, which it writes back over an empty one anyway
    stats["world_age_id"] = _AGE_SLOTS[0]
    stats["world_age_slot_index"] = 0
    stats["world_ages_slots"] = list(_AGE_SLOTS)


# Carries last chapter's trait summaries over wherever neither the entity nor its traits moved — what stays bare is owed, and `--finalize` names it.
def _carry_trait_summaries(n: int, blocks: dict, live: dict) -> None:
    prior_dir = SAVES_DIR / f"C{n - 1}"
    prior = json.loads(path.read_text()) if (path := prior_dir / "chapter.json").exists() else {}
    # A chapter from before the summaries holds a tally there, which is no summary to carry. The save behind it is parsed only to date what is worth carrying.
    written = {tier: text.strip() for tier in blocks if isinstance(text := (prior.get(tier) or {}).get("traits"), str) and text.strip()}
    prior_save = load_save(wbox) if written and (wbox := prior_dir / "map.wbox").exists() else {}
    for tier, block in blocks.items():
        if not block:
            continue
        # Both saves are walked only where a summary stands to be carried — a tier with nothing written is owed whether or not its traits moved.
        if tier in written and _trait_fingerprint(live, tier, _entity_id(block)) == _trait_fingerprint(prior_save, tier, _entity_id(prior.get(tier) or {})):
            block["traits"] = written[tier]  # same entity, same traits: what the chronicler wrote still holds


# The chapter's event codes, `chapter.json.tags` their only log. The order is a priority, the nav badging the first three: the rarest first, the alerts last.
def _chapter_tags(live: dict, path: Path, blocks: dict, boat: dict | None, favorite: dict | None, just_designated: bool, prior: tuple, age_id: str) -> list[str]:
    already, _prev_favorite, prev_world, sworn = prior
    tags = ["NEW_FAVORITE"] if just_designated else []

    # The favorite's first crown, once a soul and not once a world — a successor designated already inside a realm joined nothing the chronicle saw.
    if blocks.get("kingdom") and not just_designated and ((favorite or {}).get("metadata") or {}).get("id") not in sworn:
        tags.append("FAVORITE_FIRST_KINGDOM")

    if (prev_age_id := prev_world.get("age_id")) and age_id != prev_age_id:
        tags.append("NEW_AGE")

    # First hull ever afloat — WB's boat techs leave no trace in the save, so the boat itself is the discovery. Once in a chronicle.
    if "NAVIGATION" not in already and any(is_boat(a) for a in live.get("actors_data") or []):
        tags.append("NAVIGATION")

    # The world's first birth (an egg as soon as laid), town and death, once a chronicle: WB's counters leaving 0 — a metamorphosis, counted in its deaths, is none.
    stats = live["mapStats"]
    died = int(stats.get("deaths") or 0) - int(stats.get("metamorphosis") or 0)
    for tag, count in (("FIRST_BIRTH", stats.get("creaturesBorn")), ("FIRST_CITY", stats.get("citiesCreated")), ("FIRST_DEATH", died)):
        if tag not in already and count:
            tags.append(tag)

    # A war the favorite's crown found itself in since the chapter before, whoever declared it — the first chapter having no before, it owes none.
    if (realm := _entity_id(blocks.get("kingdom") or {})) is not None and (since := prev_world.get("world_time")) is not None and _entered_war(live, realm, since):
        tags.append("FAVORITE_KINGDOM_NEW_WAR")

    if boat:  # a chapter caught at sea — the favorite is aboard right now, which the panel badges and the chronicler owes a scene
        tags.append("FAVORITE_ABOARD")

    # A scheme afoot under the favorite's own hand. Read after the fold, which leaves the type's key behind: a plot ripens in months, so it may be gone next chapter.
    if (favorite or {}).get("plot"):
        tags.append("FAVORITE_PLOTTING")
    return tags + _fired_alerts(live, path)


# A seeded land or water the chronicler has just named takes this chapter for its own → the names dated: his to give, the date the map shows them from ours.
def _dated_places(n: int) -> list[str]:
    places = _gazetteer()
    fresh = [entry for book in _SEEDED for entry in (places.get(book) or {}).values() if entry.get("name") and not entry.get("chapter")]
    for entry in fresh:
        entry["chapter"] = f"C{n}"
    if fresh:
        _PLACES_JSON.write_text(render(places) + "\n")
    return [entry["name"] for entry in fresh]


# The close of the audit, once its last round is settled: step 5 checked again and the chapter's floor, the audit having maybe moved both, then the hand-back.
def _deliver() -> int:
    if not (n := latest_chapter()):
        print("✗ no chapter yet — run `tools/chapter/new.py` first", file=sys.stderr)
        return 1
    settings = _settings()
    _tidy_cards(n)
    facts = _step_five_facts(n, settings.get("lang", ""))
    length = facts["length"]
    short, long = length < CHAPTER_FLOOR, length > CHAPTER_CAP
    if short or long or not facts["done"]:
        print(f"✗ C{n} — not yet deliverable")
        _print_step_five(n, facts)
        if short:
            print(f"  ✗ chapter.md, {length} characters of {CHAPTER_FLOOR} at least, blanks folded — what the tale gains goes to the audit as new")
        elif long:
            print(f"  ✗ chapter.md, {length} characters of {CHAPTER_CAP} at most, blanks folded — cut whole passages, the least-borne first, never a correction")
        print("  → set these right, then run `tools/chapter/new.py --deliver` again")
        return 1
    print(f"✓ C{n} — delivery")
    labels = _ACCOUNT.get(settings.get("lang", ""), _ACCOUNT["en"])
    detail = "each line details its gaps" if settings.get("dev") else "no comment beside them"
    account = ", ".join(f"« {labels[key].format('N')} »" for key in ("facts", "story"))
    # The compliance verdicts are the chronicler's own tally, as the counts are: only he knows what he corrected, round after round.
    verdicts = f"a line per part of docs/chronicler.md, § I to § V: `§ N : ` then `✓`, `✓ (N corrections)` or « {labels['none']} »"
    rounds = f"« {labels['reaudit'].format('N')} » for all later rounds, the rest counting the first"
    print(f"  → with the chapter, the audit's account: {verdicts}, then {account}, {rounds} — {detail}")

    # The workshop switch is the player's, and it decides who he is here: a reader is owed the chapter and its account, nothing more.
    if settings.get("dev"):
        # The auditors walk the docs and the outputs claim by claim: their snags are the dev's to hear too, asked once the audit is settled.
        print(
            "  → mode: developer — ask the auditors whether anything got in their way, then you may close on a brief note of the frictions met,"
            " theirs and yours, crossed where they meet — none at all if there are none. What may go in it:"
        )
        _print_bullets(_DEV_NOTE)
        # Asked at every delivery, not once for all: a wrong only one fact auditor saw is what a lone one would have published.
        print(
            "  → then your verdict, with its figures: are two fact auditors still worth it? The wrongs only one of the two saw, counted apart"
            " — on a line you had flagged as unmeasured, on any other line —, then your call"
        )
    else:
        print("  → mode: player — the chapter and that account, nothing else")
    # A world law's alert asks the player at the close, where the errand is due: raised at step 2, it would have to outlast the whole audit to be remembered.
    laws = [_LAW_NAMES[_ALERTS[code]] for code in json.loads((SAVES_DIR / f"C{n}" / "chapter.json").read_text()).get("tags") or [] if code in _ALERTS]
    off = f"to turn the {' and '.join(laws)} world law{'s' if len(laws) > 1 else ''} off, and " if laws else ""
    print(f"  → then hand back: tell the player the chapter is closed, and ask him {off}to say when the save has moved on")
    return 0


# The places this chapter baptised on the very point of another name: two signs on one spot of the map, which the reader could only pull apart at random.
def _doubled_places(n: int) -> list[tuple[str, int, int, str]]:
    gazetteer = _gazetteer()
    held: dict[tuple[int, int], list[str]] = {}
    for book in ("places", *_SEEDED):
        for key, entry in (gazetteer.get(book) or {}).items():
            centroid = entry.get("centroid") or {}
            if name := key if book == "places" else entry.get("name"):  # a seeded land or water goes by its id until it is named, and shows nothing till then
                held.setdefault((int(centroid.get("x") or 0), int(centroid.get("y") or 0)), []).append(name)
    fresh = {name for name, spot in (gazetteer.get("places") or {}).items() if spot.get("chapter") == f"C{n}"}
    return [(name, x, y, other) for (x, y), names in held.items() for name in names if name in fresh for other in names if other != name]


# Whether the crown was drawn into a war begun after `since`, on either side and ended or not — the declaration is the event the chapter owes, not the fighting.
def _entered_war(save: dict, kingdom_id: int, since: float) -> bool:
    return any(
        float(war.get("created_time") or 0) > since
        and kingdom_id in {war.get("main_attacker"), war.get("main_defender"), *(war.get("list_attackers") or []), *(war.get("list_defenders") or [])}
        for war in save.get("wars") or []
    )


def _entity_id(block: dict) -> int | None:
    return (block.get("metadata") or {}).get("id")


# The tags a chapter owes a telling of: an alert waits for `--deliver`, a state the prose may not name, and `NEW_FAVORITE` is the chronicler's own pick.
def _events(tags: list[str]) -> list[str]:
    return [code for code in tags if code not in _ALERTS and code != "NEW_FAVORITE"]


# The save's `favorite`-flagged actor (WB's in-game marker), detail folded; the chronicler's `descriptor` carries forward while it stays the same favorite.
def _featured_favorite(chapter: str, fav_id: int, prev_favorite: dict | None) -> dict | None:
    favorite = _run("actor/info.py", fav_id, "full", chapter)
    if favorite is None:
        return None
    fold_favorite_detail(favorite)
    if prev_favorite and (prev_favorite.get("metadata") or {}).get("id") == fav_id and (descriptor := prev_favorite.get("descriptor")):
        favorite["descriptor"] = descriptor  # same favorite → keep the chronicler's epithet
    return favorite


# Step 5, reprinted from the chapter's own files on demand: what is left to write, what already holds, then what the audit is to be handed.
def _finalize() -> int:
    if not (n := latest_chapter()):
        print("✗ no chapter yet — run `tools/chapter/new.py` first", file=sys.stderr)
        return 1
    lang = _settings().get("lang", "")
    _tidy_cards(n)
    dated = _dated_places(n)  # once the gazetteer is known to parse
    facts = _step_five_facts(n, lang)
    print(f"✓ C{n} — step 5")
    if dated:
        print(f"  ✓ places.json: {', '.join(dated)} dated C{n}")
    _print_step_five(n, facts)
    # Counted before the audit reads the chapter, so the chronicler weighs his own repeats first.
    if counts := {key: len(rows) for key, rows in (echoes(n) or {}).items() if rows}:
        said = ", ".join(f"{count} {key}" for key, count in counts.items())
        print(f"  → said again: {said} — `tools/chapter/echo.py C{n}` points, you judge each: only a repeat goes — the language, a term and a refrain meant stay")
    # The targets name what this chapter wrote, so they wait for it: printed on the first pass, a descriptor rewritten after them would slip past the audit.
    if not facts["done"]:
        print("  → once nothing above is left, run `tools/chapter/new.py --finalize` again: it then hands the audit over")
        return 0
    # The run of the audit is `docs/review.md`'s, kept from the auditors: only the targets, which change with each chapter, are said here.
    print(f"  → the audit, until delivery: docs/review.md — its <cibles> are {_audit_targets(n, facts)}")
    return 0


# The alerts whose law is on and whose condition holds: thinking kinds able to raise a crown, as many as the dry ground can bear — no more need fall from the clouds.
def _fired_alerts(save: dict, save_path: Path) -> list[str]:
    laws = world_laws(save)
    standing = [code for code, law in _ALERTS.items() if laws.get(law, True)]  # the laws first: once they are off, the world is not walked at all
    return standing if standing and _founding_kinds(save, save_path) >= _kingdom_quota(save) else []


# Deletes the transcripts of the sub-agents this session spawned → how many: Claude Code dismisses none, and one stays wakeable while its transcript stands.
def _forget_subagents() -> int:
    session = os.environ.get("CLAUDE_CODE_SESSION_ID")
    home = Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude")
    # Claude Code files a session under its launch directory, every character but letters and digits dashed: a session opened elsewhere keeps its own.
    folder = home / "projects" / re.sub(r"[^A-Za-z0-9]", "-", str(SAVES_DIR.parent.resolve())) / (session or "") / "subagents"
    if not session or not folder.is_dir():
        return 0
    now, gone = time.time(), 0
    for transcript in folder.glob("agent-*.jsonl"):
        with suppress(OSError):  # one that will not go is left there: this runs inside the build, where a fault would tear the chapter down
            if now - transcript.stat().st_mtime > _SUBAGENT_GRACE:
                transcript.unlink()
                transcript.with_name(f"{transcript.stem}.meta.json").unlink(missing_ok=True)
                gone += 1
    return gone


# The thinking kinds that hold a founder: a body past childhood that could found a town where it stands, its youth set aside — or one that has a town already.
def _founding_kinds(save: dict, save_path: Path) -> int:
    island_of, grid = compute_islands_cached(save, save_path)[1], LazyTileGrid(save)
    ctx = build_actor_stats_context(save) | {
        "city_zones": cache(lambda: city_zones(save, island_of)),
        "island_lookup": lambda: island_of,
        "tile_grid": lambda: grid,
        "tile_map": save["tileMap"],
        "world_laws": world_laws(save),
    }
    kinds: set[str] = set()
    for actor in save.get("actors_data") or []:  # a kind once counted is asked no more: the ground is weighed for its first founder alone
        if (kind := actor.get("asset_id")) in kinds or is_boat(actor) or not is_sapient(ctx["subspecies_by_id"].get(actor.get("subspecies"))):
            continue
        grown = life_stage(actor_age(actor, ctx["world_time"]), adult_age(actor, ctx), 0, is_egg(actor, ctx)) in _GROWN
        if grown and (actor.get("cityID") or settle_gates(actor, ctx) in (True, ["child"])):
            kinds.add(kind)
    return len(kinds)


# `places.json` as it stands, read afresh at each call: the chronicler writes it between two runs, and `--finalize` itself dates it on the way.
def _gazetteer() -> dict:
    return json.loads(_PLACES_JSON.read_text()) if _PLACES_JSON.exists() else {}


# How many crowns a world must raise before it feeds itself: one per `_LAND_PER_KINGDOM` of dry ground, never under the floor. Ocean is no one's to rule.
def _kingdom_quota(save: dict) -> int:
    sea = [tile_layer(name) == "Ocean" for name in save.get("tileMap") or []]
    land = sum(length for tile, length in tile_runs(save) if not sea[tile])  # counted off the runs: a map holds five times more tiles than it does runs
    return max(_KINGDOM_FLOOR, int(land / _LAND_PER_KINGDOM + 0.5))  # nearest, not ceiling — `round` breaks ties to the even number


# WB's `life_dna` seeds a world's genetics, redrawn on the hour so a reused map never repopulates with the lineages before it. WB's format: `YYYYMMDDHH`, UTC.
def _life_dna() -> int:
    return int(datetime.now(timezone.utc).strftime("%Y%m%d%H"))


# The places this chapter baptised whose centroid stands off the land their `island_id` names — none named means off every counted land: the sea, or an islet.
def _misplaced_places(n: int) -> list[tuple[str, int, int, int | None, int | None]]:
    spots = _gazetteer().get("places") or {}
    if not (fresh := [(name, spot) for name, spot in spots.items() if spot.get("chapter") == f"C{n}"]):
        return []  # nothing baptised here, and so no save to open
    save_path = SAVES_DIR / f"C{n}" / "map.wbox"
    _, land_of = compute_islands_cached(load_save(save_path), save_path)
    misplaced = []
    for name, spot in fresh:
        centroid = spot.get("centroid") or {}
        x, y, declared = int(centroid.get("x") or 0), int(centroid.get("y") or 0), spot.get("island_id")
        if (found := land_of.get((x, y))) != declared:
            misplaced.append((name, x, y, found, declared))
    return misplaced


# The mods this save was written without: its stamp missing, or left by an older save — the time it holds is then not this save's.
def _mods_off(save: dict) -> list[str]:
    stats = save.get("mapStats") or {}
    stamps = (stats.get("custom_data") or {}).get("custom_data_float") or {}
    return [name for name, key in _MODS.items() if abs(float(stamps.get(key, -inf)) - float(stats.get("world_time") or 0)) > _STAMP_SLACK]


# The names this chapter put on the map, a land's or a water's as a place's own: what `--finalize` dated, and what the chronicler wrote `chapter` on himself.
def _named_places(n: int) -> list[str]:
    gazetteer = _gazetteer()
    named = (
        key if book == "places" else entry.get("name")
        for book in ("places", *_SEEDED)
        for key, entry in (gazetteer.get(book) or {}).items()
        if entry.get("chapter") == f"C{n}"
    )
    return sorted(filter(None, named))


def _print_bullets(lines: tuple[str, ...]) -> None:
    print("\n".join(f"    · {line}" for line in lines))


# The recap's closing lines: a favorite's choice first, then step 3's commands and files, step 4's bounds — its shape while no favorite stands — and step 5.
def _print_next_step(n: int, live: dict, favorite: dict | None, forgotten: int) -> None:
    # No favorite while a thinking soul stands: the pick comes first, `favorite.py` erasing the chapter, prose and all, to rebuild it around the one chosen.
    thinking = index_by_id(live.get("subspecies") or [])
    if forgotten:
        print(f"  → chronicler: {forgotten} sub-agents of earlier work deleted — forget their ids")
    if favorite is None and any(is_sapient(thinking.get(a.get("subspecies"))) for a in live.get("actors_data") or [] if not is_boat(a)):
        print("  → chronicler: choose a favorite before a single word — your pick, not the player's:")
        _print_bullets(_CHOICE)
        print("  → then put it to the player:")
        _print_bullets(_DESIGNATION)
        print("  → without one, step 3, the analysis, before the first word and not to be hurried:")
    else:
        print("  → chronicler: step 3, the analysis, before the first word and not to be hurried:")
    fav_id = ((favorite or {}).get("metadata") or {}).get("id")
    if n > 1:
        order = ", the favorite first, then circle by circle:" if fav_id else ","  # the chapter's own order, so the analysis lands already sorted by tier
        print(f"    · the deltas since C{n - 1}{order} what moved as much as what held — `geography bodies C{n}` shows a land newly peopled")
    print("    · the thresholds just crossed: the first times, the levels reached")
    if fav_id:
        if n > 1:
            print(f"    · what changed on the favorite: `actor {fav_id} --since C{n - 1} C{n}` — its walk and its gates, read before a word of it")
        print(f"    · who lives around the favorite: `actor {fav_id} surroundings C{n}`, each by its id: names repeat")
    if n > 1:
        print(f"    · the chapter before, reread: `saves/C{n - 1}/chapter.md`, and the open watches to settle or carry: `history/watches.md`")
    told = "" if fav_id else " — no favorite, so the world itself, in two parts and no circle:"
    print(f"  → step 4, the writing: {CHAPTER_FLOOR} to {CHAPTER_CAP} characters, blanks folded, counted at delivery, past the audit{told}")
    if not fav_id:
        _print_bullets(_WORLD_ONLY)
    # In no doc: the cycle is the script's to tell, step by step. A chapter still under its draft title reads as unfinished, to the reader and to `--finalize`.
    draft = _DRAFT_HEADINGS.get(_settings().get("lang", ""), "Draft")
    print(f"  → step 5, once written under the H1 `# {draft}`, kept till then: `tools/chapter/new.py --finalize`, followed to delivery")


# The recap's first half: where the world stands, what fired, and what the journal logged since the chapter before.
def _print_report(n: int, live: dict, age_id: str, favorite: dict | None, regime: str, tags: list[str], prev_world: dict) -> None:
    age_label = (_AGE_LABELS.get(f"age_{age_id}") or {}).get("name") or age_id  # recap line only, the chapter carrying the id alone
    year = int(rounded_world_time(live["mapStats"]) / UNITS_PER_YEAR) + 1  # WB `Date.getYear`: the displayed year is 1-based, `getYear0` alone lags a year behind
    fav_name = ((favorite or {}).get("metadata") or {}).get("name")
    print(f"✓ C{n} — year {year}, {age_label}")
    print(f"  favorite: {fav_name or 'none'}{f' — {regime}' if regime else ''}")
    print(_RECAP_RULE)
    if events := _events(tags):  # a tag in `chapter.json` alone never reaches the chronicler
        for code in events:
            print(f"  ⚑ {code}")
        print(f"  → each ⚑ is {_EVENT}")
        print(_RECAP_RULE)
    # A law the player turned since the chapter before changes what the world may do, and `world … laws` is no part of `full`: nothing else would say it.
    then = prev_world.get("laws") or {}
    if turned := sorted(f"{_LAW_NAMES.get(law, law)} {'on' if on else 'off'}" for law, on in world_laws(live).items() if law in then and then[law] != on):
        print(f"  ⚖ world laws turned since C{n - 1}: {', '.join(turned)} — `tools/wiki/info.py World_Laws --row <law>` says what each rules")
        print(_RECAP_RULE)
    # The one source naming a killer, printed so a king's fall needn't wait on the file; none at C1, whose whole past would pour out: `history log`'s to give.
    journal = log_entries(float(prev_world.get("world_time") or 0)) if n > 1 else []
    for entry in journal:  # the killer named as such, `special1..3` shifting meaning from one message to the next — a meteorite names no one
        told = [f"{role} {entry[role]}" for role in ("favorite", "king", "killer") if entry.get(role)] or (entry.get("names") or [])
        print(f"  ✎ {' · '.join((entry['date'], entry['event'], *told))} ({entry['x']},{entry['y']})")
    if journal:
        print(_RECAP_RULE)


# Step 5's lines, one per errand: a task left (→) or a check failed (✗), a length that holds going unsaid. A carried descriptor is quoted: its standing ages.
def _print_step_five(n: int, facts: dict) -> None:
    carrying = facts["carried"] and not facts["h1"]  # keep or rewrite is the first pass's call: once the H1 is in, a carried descriptor reads as checked
    sized = not facts["h1"] or (facts["favorite"] and (not facts["descriptor"] or carrying)) or facts["owed"]  # any length still to write
    if not facts["h1"]:
        print(f"  → the final H1, alone and in place of « # {facts['draft']} »: {_H1_CAP} characters at most")
    elif facts["h1_length"] > _H1_CAP:
        print(f"  ✗ H1, {facts['h1_length']} characters of {_H1_CAP}")
    if facts["favorite"]:
        if not (text := facts["descriptor"]):
            print(
                "  → `favorite.descriptor` in chapter.json, yet to be written: one line on where the favorite stands now, made of what the chapter already says"
                f" — {_PLAIN}, {_DESCRIPTOR_CAP} characters at most"
            )
        elif carrying:
            print(
                f"  → `favorite.descriptor`, carried from C{n - 1}: « {text} » — it may stand while every fact in it still holds, an age never does;"
                f" else rewrite it, {_PLAIN}, {_DESCRIPTOR_CAP} characters at most"
            )
        elif len(text) > _DESCRIPTOR_CAP:
            print(f"  ✗ descriptor, {len(text)} characters of {_DESCRIPTOR_CAP}")
    if owed := facts["owed"]:
        reads = ", ".join(f"`{'actor' if tier == 'favorite' else tier} {entity} traits C{n}`" for tier, entity in owed.items())
        print(f"  → trait summaries owed ({', '.join(owed)}): one string each under the block's own `traits` key, read off {reads}")
        lineage = f", a lineage's {_SUMMARY_CAPS['subspecies']} — {_LINEAGE}" if "subspecies" in owed else ""
        print(f"    {_SUMMARY}; {_SUMMARY_CAP} characters at most{lineage}")
    if long := facts["long"]:
        print(f"  ✗ trait summaries, in characters: {', '.join(f'{tier} {told}' for tier, told in long.items())}")
    if sized:
        print("  → every length above counts spaces and markup too")
    for name, x, y, other in facts["doubled"]:
        print(f"  ✗ places.json « {name} »: ({x},{y}) is the very point of « {other} » — its sign needs a point of its own on the map")
    for name, x, y, found, declared in facts["misplaced"]:
        print(f"  ✗ places.json « {name} »: ({x},{y}) lies on {f'land {found}' if found else 'no counted land'}, its `island_id` saying {declared or 'none'}")
    if facts["doubled"] or facts["misplaced"]:
        print("  → set these right in history/places.json")


# One scan of prior chapters for all they arbitrate: a first hull, descriptor carry-forward, a new favorite, a turned age, a stale save, a new war, a first crown.
def _prior_context(n: int) -> tuple[set, dict | None, dict, set]:
    tags: set = set()
    sworn: set = set()
    favorite, world = None, {}
    for prior in range(1, n):
        if not (prior_json := SAVES_DIR / f"C{prior}" / "chapter.json").exists():
            continue
        data = json.loads(prior_json.read_text())
        tags |= set(data.get("tags") or [])
        if data.get("kingdom") and (sworn_id := ((data.get("favorite") or {}).get("metadata") or {}).get("id")) is not None:
            sworn.add(sworn_id)
        if prior == n - 1:
            favorite = data.get("favorite")
            # That chapter's own save, read once for its hour and its laws — the age switches left to `age_id`. Gone, it leaves neither.
            then = load_save(archived) if (archived := SAVES_DIR / f"C{prior}" / "map.wbox").exists() else None
            laws = {law: on for law, on in world_laws(then or {}).items() if law.startswith("world_law_")}
            hour = rounded_world_time(then.get("mapStats") or {}) if then else None
            world = {**((data.get("world") or {}).get("metadata") or {}), "laws": laws, "world_time": hour}
    return tags, favorite, world, sworn


# Empties a world's own chronicle, table by table, leaving the schema WB expects. `VACUUM` hands the megabytes back rather than leaving a hollow file.
def _purge_history(s3db: Path) -> None:
    if not s3db.exists():
        return
    s3db.chmod(0o644)  # WB leaves it read-only often enough that a bare `connect` would fail
    with sqlite3.connect(s3db) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        for (table,) in cursor.fetchall():
            cursor.execute(f'DELETE FROM "{table}"')  # interpolated, but the name comes from the file's own schema a line above
        conn.commit()
        cursor.execute("VACUUM")


# What the favorite line adds, so the chronicler need not deduce it — a favorite gone from `actors_data` is dead, and nothing else says so. Silent when it holds.
def _regime(n: int, actors: list, fav_id: int | None, prev_fav_id: int | None) -> str:
    if n == 1:
        return "first chapter"
    if prev_fav_id is not None and not any(a.get("id") == prev_fav_id for a in actors):  # WB drops the dead from `actors_data`: an absent favorite is a dead one
        # The pick itself is the closing block's, printed only while a thinking soul is left to pick.
        return f"{'the favorite has' if fav_id is None else 'successor to one who has'} left the world — {_DEATH}"
    return "yet to be designated" if fav_id is None else ""


# Rewrites the world's name or blurb in the live save and on its card, the other left as it stands: what the check after the naming mends.
def _rename_world(live_wbox: Path, name: str, description: str) -> int:
    if not (name or description):
        print("✗ --name, --description: neither carries its words", file=sys.stderr)
        return 2
    if worldbox_running():
        print("✗ WorldBox is running — quit the game before renaming, or its next save writes the old words back", file=sys.stderr)
        return 1

    save = load_save(live_wbox)
    stats = save["mapStats"]
    stats["description"], stats["name"] = description or stats.get("description") or "", name or stats.get("name") or ""
    write_save(live_wbox, save)
    _write_world(save)
    (live_wbox.parent / "map.meta").unlink(missing_ok=True)  # as at the reset: WB rebuilds it from the save on opening
    print(f"✓ world named {stats['name'] or '—'}, {'described anew' if description else 'its description kept'}")
    return 0


# Zeroed by type rather than by name: WB adds counters between versions, and a hardcoded list would leave the new ones running. `id_*` restarts at 1, the rest at 0.
def _reset_counters(stats: dict) -> None:
    for key, value in stats.items():
        if isinstance(value, bool):  # `bool` subclasses `int`, so it has to be spared before the number test, not after
            continue
        if isinstance(value, int):
            stats[key] = 1 if key.startswith("id_") else 0
        elif isinstance(value, float):
            stats[key] = 0.0


# Unmakes the world the player asked to be rid of, its map alone left standing. No chapter is written here: the bare world it hands back is what C1 opens on.
def _reset_world(live_wbox: Path, name: str, description: str) -> int:
    if worldbox_running():
        print("✗ WorldBox is running — quit the game before resetting, or it will write its own save back over this one", file=sys.stderr)
        return 1

    save = load_save(live_wbox)
    _bare_world(save, name, description)
    stats = save["mapStats"]
    write_save(live_wbox, save)
    _write_world(save)  # off the save, not off the arguments: a world that kept its name keeps it here too
    _purge_history(live_wbox.parent / "map_stats.s3db")
    (live_wbox.parent / "map.meta").unlink(missing_ok=True)  # WB rebuilds it from the save on opening; writing it ourselves would guess at a format we only read

    landmarks = ", ".join(f"{count} {asset}" for asset, count in sorted(Counter(b["asset_id"] for b in save["buildings"]).items()))
    print(f"✓ world reset — year 1 of the Age of Hope, {stats['current_world_ages_duration'] / UNITS_PER_YEAR:.0f} years long")
    print(f"  map kept, {f'with its landmarks: {landmarks}' if landmarks else 'no landmark on it'}")
    print(f"  named: {stats['name'] or '—'}")
    if name or description:  # his own words, written before any audit stood and read by none after: checked here, the game still closed for the mending
        target = f"history/world.json (description, name) [{_BAPTISM}]"
        print(f"  → chronicler, first, the game still closed: a fresh sub-agent checks them — `Lis docs/audit/facts.md — {target}`")
        print('    a gap is fixed with `tools/chapter/new.py --name "…" --description "…"`, either alone leaving the other; the first chapter deletes the sub-agent')

    # The game alone redraws preview.png and has the mods stamp the save: hence the re-save, which is the one the chapter archives.
    print("  → player: reopen the save in WorldBox and save again — the chapter then archives the world as it now stands")
    print("  → chronicler: once he has, `tools/chapter/new.py --reset-asked` writes the first chapter, on the bare world as it stands")
    return 0


# Runs a sibling `info.py` → its parsed JSON stdout, `None` (stderr surfaced) on failure or empty output. `sys.executable` so a venv never forks children elsewhere.
def _run(rel_path: str, *args) -> dict | None:
    result = subprocess.run([sys.executable, str(_TOOLS / rel_path), *map(str, args)], capture_output=True, text=True, check=False)
    if result.returncode:
        cause = (result.stderr.strip().splitlines() or [f"exit {result.returncode}"])[-1]  # a traceback's last line names the fault, its head only the call stack
        print(f"  ⚠ tools/{rel_path} {' '.join(map(str, args))}: {cause}", file=sys.stderr)
        return None
    return json.loads(result.stdout) if result.stdout.strip() else None


# Runs `(callable, *args)` tuples at once, results in order (`None` call → `None`) — each `info.py` re-parses the whole save and only reads, so overlap is free.
def _run_together(*calls: tuple | None) -> list:
    with ThreadPoolExecutor(max_workers=max(len(calls), 1)) as pool:
        jobs = [pool.submit(*call) if call else None for call in calls]
    return [job.result() if job else None for job in jobs]


# The chapter's folder and what surrounds it: the save, the history the chronicler browses, the world card, the C1 toponyms, the registries → a failed command.
def _scaffold(chapter: str, chapter_dir: Path, live_wbox: Path, live: dict) -> str | None:
    live_dir = live_wbox.parent
    for name in _LIVE_FILES:
        if (src := live_dir / name).exists():
            shutil.copy2(src, chapter_dir / name)
    if (s3db := live_dir / "map_stats.s3db").exists():
        shutil.copy2(s3db, HISTORY_S3DB)
    _write_world(live)
    # His toponyms, the lands and waters seeded by id — each already numbered, so only their names are left to forge. A book an older gazetteer lacks joins it.
    places = _gazetteer()
    if missing := [book for book in _SEEDED if book not in places]:
        if (surveyed := _run("geography/info.py", "islands,waters", chapter)) is None:  # seeded once and never again: an empty survey would stay empty
            return "geography/info.py islands,waters"
        found = {**(surveyed.get("waters") or {}), "islands": surveyed.get("islands")}
        places = {"places": {}, **places, **{book: _unnamed(found.get(book) or []) for book in missing}}
        _PLACES_JSON.write_text(render(places) + "\n")

    registries.ensure(chapter, live)  # `live` is handed over so it spares itself a re-parse of the save we already hold
    return None


# The reader's settings: the player's workshop switch and the chronicle's language. A missing or broken file reads as a player who never opened the panel.
def _settings() -> dict:
    try:
        return json.loads(_SETTINGS_JSON.read_text())
    except (OSError, ValueError):
        return {}


# Step 5 off the chapter's files: its H1 and length, the favorite's descriptor and if carried, the summaries owed or too long, places astray, prose new since C<n-1>.
def _step_five_facts(n: int, lang: str) -> dict:
    chapter_dir, prior_path = SAVES_DIR / f"C{n}", SAVES_DIR / f"C{n - 1}" / "chapter.json"
    chapter = json.loads((chapter_dir / "chapter.json").read_text())
    prior = json.loads(prior_path.read_text()) if prior_path.exists() else {}
    prose = (chapter_dir / "chapter.md").read_text()
    headings = [line[2:] for line in prose.splitlines() if line.startswith("# ")]
    draft = _DRAFT_HEADINGS.get(lang, "Draft")
    favorite, before = chapter.get("favorite") or {}, prior.get("favorite") or {}
    descriptor = favorite.get("descriptor")
    same = (before.get("metadata") or {}).get("id") == (favorite.get("metadata") or {}).get("id")  # a favorite stays so until death: another, or none, mourns him
    carried = bool(descriptor) and same and descriptor == before.get("descriptor")
    written = {tier: summary for tier in _TRAIT_SOURCES if isinstance(summary := (chapter.get(tier) or {}).get("traits"), str)}
    h1 = headings[0] if len(headings) == 1 and headings[0] != draft else None
    h1_length = len(_TAG.sub(lambda m: m[1] or "", h1 or ""))  # as read: a tag in the title shows its name alone, never its markup
    owed = {tier: _entity_id(chapter[tier]) for tier in sorted(_TRAIT_SOURCES) if chapter.get(tier) and tier not in written}
    long = {tier: f"{size} of {cap}" for tier, text in sorted(written.items()) if (size := len(text)) > (cap := _SUMMARY_CAPS.get(tier, _SUMMARY_CAP))}
    doubled, misplaced = _doubled_places(n), _misplaced_places(n)
    # A summary carried word for word was audited when written, so only a new one goes; the descriptor always, an age in it stale by the next chapter.
    fresh = [f"{tier}.traits" for tier in sorted(_TRAIT_SOURCES) if chapter.get(tier) and written.get(tier) != (prior.get(tier) or {}).get("traits")]
    return {
        "audited": sorted(fresh + (["favorite.descriptor"] if favorite else [])),
        "carried": carried,
        "descriptor": descriptor,
        "done": 0 < h1_length <= _H1_CAP and (not favorite or 0 < len(descriptor or "") <= _DESCRIPTOR_CAP) and not (doubled or owed or long or misplaced),
        "doubled": doubled,
        "draft": draft,
        "events": _events(chapter.get("tags") or []),
        "favorite": bool(favorite),
        "h1": h1,
        "h1_length": h1_length,
        "length": chapter_length(prose),
        "long": long,
        "misplaced": misplaced,
        "mourned": bool(before) and not same,
        "named": _named_places(n),
        "owed": owed,
    }


# The chronicler writes into `chapter.json` and `places.json` by hand, with whatever encoder comes to him: each put back in the project's layout, no word moved.
def _tidy(card: Path) -> None:
    raw = card.read_text()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:  # a hand edit gone astray: said where, rather than a traceback the chronicler has to read through
        sys.exit(f"✗ {card.relative_to(SAVES_DIR.parent)} is no longer valid JSON — {e.msg}, line {e.lineno}: mend it, then run the command again")
    if (tidy := render(data) + "\n") != raw:
        card.write_text(tidy)


# The two files the chronicler writes into by hand, tidied before step 5 reads them — `places.json` only once the first chapter has seeded it.
def _tidy_cards(n: int) -> None:
    for card in (SAVES_DIR / f"C{n}" / "chapter.json", _PLACES_JSON):
        if card.exists():
            _tidy(card)


# An entity's traits as the save spells them, id included so a change of clan reads like a change of traits — both mean the summary must be written afresh.
def _trait_fingerprint(save: dict, tier: str, entity_id: int | None) -> tuple | None:
    if entity_id is None:
        return None
    collection, fields = _TRAIT_SOURCES[tier]
    record = next((r for r in save.get(collection) or [] if r.get("id") == entity_id), None)
    return None if record is None else (entity_id, *(tuple(sorted(record.get(field) or [])) for field in fields))


# A surveyed feature stripped to what a toponym needs: where its name sits — its heart, else its mean —, its size, and the two fields the chronicler fills.
def _unnamed(features: list[dict]) -> dict:
    return {str(f["id"]): {"centroid": f.get("heart") or f["centroid"], "chapter": "", "name": "", "size": f["size"]} for f in features}


def _value(argv: list[str], flag: str) -> str:
    return argv[i] if flag in argv and (i := argv.index(flag) + 1) < len(argv) else ""


# Every chapter in one file: what the nav prints beside a slug, and nothing else. Rewritten whole each time, so a chapter deleted by hand drops out on the next run.
def _write_index(fresh: int, world_time: float) -> None:
    # Each hour is kept from the index before, the chapter just built given its own: an archived save is opened only for one the index has lost.
    hours = {row["n"]: row["world_time"] for row in (json.loads(_INDEX_JSON.read_text()) if _INDEX_JSON.exists() else [])} | {fresh: world_time}
    entries = []
    for chapter_json in sorted(SAVES_DIR.glob("C*/chapter.json"), key=lambda f: int(f.parent.name[1:])):
        n = int(chapter_json.parent.name[1:])
        hour = hours[n] if n in hours else chapter_world_time(n) or 0
        entries.append({"n": n, "tags": json.loads(chapter_json.read_text()).get("tags") or [], "world_time": hour})
    _INDEX_JSON.write_text(render(entries) + "\n")


# Name, blurb and span, rewritten each chapter rather than seeded once: a rename reaches the reader alone, and nothing else says how far the world stretches.
def _write_world(save: dict) -> None:
    stats = save.get("mapStats") or {}
    world = {
        "description": stats.get("description") or "",
        "height": int(save.get("height") or 0) * _MAP_BLOCK,
        "name": stats.get("name") or "",
        "width": int(save.get("width") or 0) * _MAP_BLOCK,
    }
    _WORLD_JSON.write_text(render(world) + "\n")  # `render` like every other file the bootstrap writes, so a short blurb would inline as they do


def main(argv: list[str]) -> int:
    if unknown := [a for a in argv if a.startswith("--") and a not in _FLAGS]:  # `--rest` would else read as « no reset asked » and put the question again
        print(f"✗ unknown flag {', '.join(unknown)} — new.py knows {', '.join(sorted(_FLAGS))}", file=sys.stderr)
        return 2
    if "--finalize" in argv:  # step 5 of the chapter under way, off its own files, its archived save among them: nothing is built, the live save never read
        return _finalize()
    if "--deliver" in argv:  # the close of the audit, off the same files
        return _deliver()
    live_wbox = live_save()
    if not live_wbox.exists():
        print(f"✗ no live save at {live_wbox} — ask the player to update the path, from the Settings button below the map", file=sys.stderr)
        return 2

    # A world's name and blurb are set at its reset; alone, the two flags mend what the check that follows faults in them, and nothing past the first chapter.
    resetting = "--reset" in argv
    n = latest_chapter() + 1
    if not resetting and (lone := [flag for flag in ("--description", "--name") if flag in argv]):
        if n > 2:
            print(f"✗ {', '.join(lone)}: past the first chapter the world keeps the words its chapters tell it by", file=sys.stderr)
            return 2
        return _rename_world(live_wbox, _value(argv, "--name"), _value(argv, "--description"))

    chapter, chapter_dir = f"C{n}", SAVES_DIR / f"C{n}"
    if resetting:  # the player said yes, and only he can: nothing but this flag ever reaches the branch below
        if n > 1:  # `n` already counted the chapters a moment ago, and a chronicle past its first cannot afford the world it tells of being unmade
            print("✗ the chronicle has begun — a reset would erase the world its chapters tell of", file=sys.stderr)
            print("  → player: to start over, from the New game button below the map", file=sys.stderr)
            return 1
        return _reset_world(live_wbox, _value(argv, "--name"), _value(argv, "--description"))

    if n == 1 and "--reset-asked" not in argv:  # a reset would throw away whatever is written here, so nothing is, until the player has had his say
        print("\n".join(_RESET_PROMPT))
        return 0

    live = load_save(live_wbox)
    # A world the mods do not run on is not the one the chronicle follows: clouds seed it elsewhere, and every load unmakes what its bodies were at.
    if off := _mods_off(live):
        if not live["mapStats"].get("world_time"):  # a reset zeroes the clock and leaves the old stamps: no game has written this save since
            print("✗ the world has not been saved since its reset — player: reopen it in WorldBox and save again", file=sys.stderr)
            return 1
        print(f"✗ the save was written without {' and '.join(off)} — no chapter is written on such a save", file=sys.stderr)
        print("  → player: its README tells how to install it — or the chronicler can install it for you, just ask", file=sys.stderr)
        print("  → player: then restart the game (a mod only loads when it starts), load the world and save again", file=sys.stderr)
        readmes = ", ".join(f"`{_MODS_DIR}/{name.replace(' ', '')}/README.md`" for name in off)
        print(f"  → chronicler: {readmes}", file=sys.stderr)
        return 1
    actors = live.get("actors_data") or []
    world_time = rounded_world_time(live["mapStats"])
    fav_id = next((a["id"] for a in actors if a.get("favorite") is True), None)
    prior = _prior_context(n)
    _, prev_favorite, prev_world, _ = prior
    prev_fav_id = ((prev_favorite or {}).get("metadata") or {}).get("id")
    # A favorite the chapter before did not carry — the world's first, or a successor to one who died. Both earn a chapter at an unchanged timestamp, and the tag.
    just_designated = fav_id is not None and fav_id != prev_fav_id

    # Held against the hour the chapter before archived in its own save, both through the same `rounded_world_time`.
    if (prev_time := prev_world.get("world_time")) is not None and world_time <= prev_time and not just_designated:
        print(
            f"✗ save not advanced (world_time {world_time} ≤ C{n - 1} {prev_time}), and no new favorite either — ask the player to play on, then save again",
            file=sys.stderr,
        )
        return 1

    chapter_dir.mkdir(parents=True)  # outside the guard: a folder this run did not make, it never removes
    try:
        if failed := _scaffold(chapter, chapter_dir, live_wbox, live):
            return _abandon(chapter_dir, [failed])

        # Two waves rather than a call per tier: the favorite's metadata names the bodies it belongs to, so none of those can start until it has landed.
        world, favorite = _run_together(
            (_run, "world/info.py", chapter),
            (_featured_favorite, chapter, fav_id, prev_favorite) if fav_id is not None else None,
        )

        lost_favorite = fav_id is not None and favorite is None
        if world is None or lost_favorite:  # the two ran together, so both may have failed
            return _abandon(chapter_dir, [name for name, lost in (("world/info.py", world is None), (f"actor/info.py {fav_id} full", lost_favorite)) if lost])

        blocks: dict = dict.fromkeys(_TIERS)  # `None` where the favorite belongs to no such body — the chapter carries the key either way
        boat = None
        if favorite:
            meta = favorite.get("metadata") or {}
            calls = [(_run, f"{tier}/info.py", tid, "full", chapter) if (tid := (meta.get(tier) or {}).get("id")) else None for tier in _TIERS]
            # The hull rides the same wave, `transport` being a ref like the tiers. Popped, not read: the `boat` block replaces it, `actor/info.py` keeping the ref.
            boat_id = (meta.pop("transport", None) or {}).get("id")
            calls.append((_run, "boat/info.py", boat_id, "full", chapter) if boat_id else None)
            results = _run_together(*calls)
            if failed := [f"{call[1]} {call[2]} full" for call, block in zip(calls, results) if call and block is None]:
                return _abandon(chapter_dir, failed)
            *bodies, boat = results
            blocks = dict(zip(_TIERS, bodies))
            fold_bodies(blocks, boat)

        # A third wave, the only one a tier opens — popped as `transport` is, the blocks it returns holding the names the crown's list would otherwise say twice.
        wars = [w for w in ((blocks.get("kingdom") or {}).pop("wars", None) or []) if w.get("id") is not None]
        if wars:
            fought = _run_together(*((_run, "war/info.py", w["id"], "full", chapter) for w in wars))
            if failed := [f"war/info.py {w['id']} full" for w, war in zip(wars, fought) if war is None]:
                return _abandon(chapter_dir, failed)
            wars = fought

        summaries = {tier: favorite if tier == "favorite" else blocks[tier] for tier in _TRAIT_SOURCES}  # a tier is summarised the day it gains a trait source
        _carry_trait_summaries(n, summaries, live)
        fold_world(world)
        age_id = (live["mapStats"].get("world_age_id") or "").removeprefix("age_")  # short form, as `world/info.py` emits it — `prev_world` carries that one
        tags = _chapter_tags(live, chapter_dir / "map.wbox", blocks, boat, favorite, just_designated, prior, age_id)

        # No `age_label`: the panel translates `world.metadata.age_id`. No `title` either: the H1 of `chapter.md` is the title, and nothing reads a copy of it.
        chapter_json = {
            **blocks,  # `render` sorts a record's keys, so the tiers need no place of their own here
            "boat": boat,
            "favorite": favorite,
            "tags": tags,
            "wars": wars,
            "world": world,
        }

        # `render`, not `json.dumps(indent=2)`: same tree, a quarter fewer characters once branches inline. `drop_chronicler_keys` strips the empties as it cuts.
        (chapter_dir / "chapter.json").write_text(render(drop_chronicler_keys(chapter_json)) + "\n")
        settings = _settings()

        # The draft's H1, in the language the chronicler writes the chapter in: the reader has a page, and it reads unfinished.
        (chapter_dir / "chapter.md").write_text(f"# {_DRAFT_HEADINGS.get(settings.get('lang', ''), 'Draft')}\n")
        _write_index(n, world_time)

        _print_report(n, live, age_id, favorite, _regime(n, actors, fav_id, prev_fav_id), tags, prev_world)
        _print_next_step(n, live, favorite, _forget_subagents())
        return 0
    except BaseException as fault:  # a crash or a Ctrl-C halfway, which `_abandon` never sees: the half-built folder goes the same way, the fault still surfacing
        shutil.rmtree(chapter_dir, ignore_errors=True)
        if isinstance(fault, Exception):  # a Ctrl-C or an exit is no crash, and an exit has said its own ✗ already
            print("✗ new.py crashed — nothing written, report the traceback below", file=sys.stderr)
        raise


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
