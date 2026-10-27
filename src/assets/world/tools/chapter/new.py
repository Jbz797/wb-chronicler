#!/usr/bin/env python3

# Bootstraps a new chapter from the live WorldBox save: archives it under `saves/C<n>/`, builds its registries (`registries.py`) and `chapter.json` (`fold.py`).
# The recap steers the chronicler's analysis; `--finalize` then lays out step 5 and hands the audit to `docs/review.md`, `--deliver` the delivery,
# `--retouch` a round for the delivered chapters reworked since.

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
from contextlib import closing, suppress
from datetime import UTC, datetime
from functools import cache
from math import inf
from pathlib import Path
lazy from collections.abc import Collection

sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))

import registries
from actor_stats import adult_age, build_actor_stats_context, is_egg, kept_task, kept_task_target
from echo import echoes
from fold import drop_chronicler_keys, fold_bodies, fold_favorite_detail, fold_world
from founding import city_zones, settle_gates
from grid import LazyTileGrid, shore_tally, tile_layer, tile_runs
from islands import compute_islands_cached
from shared import (
    CHAPTER_CAP,
    COUNTED_AS,
    HISTORY_S3DB,
    PLACES_JSON,
    SAVES_DIR,
    UNITS_PER_YEAR,
    actor_age,
    asset_set,
    chapter_floor,
    chapter_length,
    chapter_world_time,
    chronicle_git,
    i18n,
    is_boat,
    is_sapient,
    latest_chapter,
    life_stage,
    live_save,
    load_data,
    load_save,
    log_entries,
    named_body,
    place_point,
    reader_settings,
    render,
    rounded_world_time,
    short_dialogues,
    thinking_souls,
    under_construction,
    unmarked,
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

_AGE_SLOTS = ("age_hope", *("age_unknown",) * 7)  # WB resolves them one at a time; a world always opens on the first

_ALERTS = {"DISABLE_DROP_OF_THOUGHTS": "world_law_drop_of_thoughts"}  # each alert by the law it asks the player to cut — a state while that law stays on

# What a baptism's check weighs — in no doc, a world being named once: handed to the audit with its target, as a chapter's asks are.
_BAPTISM = (
    "a world's name and description are checked as a chapter is, and the name is worth what it says of the ground;"
    " what the description takes from the player's lore is told as belief where the ground does not show it"
)

_CHOICE = (  # what a pick weighs, said where the pick is made: needed at a world's start and at a favorite's death alone, in no doc
    "a thinking body only: `sapient: true` in `actor … metadata`",
    "weighed in depth: traits, political standing, narrative promise, age, where it stands, what surrounds it…",
    "the world's first favorite also needs room for a homestead — a fitting biome around it, resources, obstacles at a distance; later ones, while nothing is built",
)

# What the chronicle's own git keeps (`shared.chronicle_git`): each chapter's prose and the chronicler's fields — never a save, a picture or a registry.
_CHRONICLE_KEPT = "*\n!*/\n!C*/chapter.md\n!C*/chapter.json\n!watches.md\n"

# The story auditor's counsel before a word, its sheet standing by it as by a target's brackets — in no doc; the same sub-agent audits the text after.
_COUNSEL = (
    "Read docs/audit/story.md — before C{n} is written: <the turning points and the major changes of your analysis{measured}>. Answer short: the turning point that "
    "carries the chapter, the watch it settles or tips, the angle, what must not be dropped; directions, never prose. At the audit you will judge the text "
    "as it stands, not its faithfulness to your counsel; the register moves only at the audit."
)

# What the chapter owes a favorite just dead — in no doc, a death being rare: the recap says it, the targets hand it to the audit.
_DEATH = "the death section opens the chapter: how he died, pieced together as far as the data allow (§ Déduction des meurtres), what he leaves, the handover"

_DESCRIPTOR_CAP = 64

_DESIGNATION = (  # putting the chosen favorite to the player — an exchange no chapter shows, so it is said where it is acted on
    "announce it to the player with `tools/map/show.py <x,y>`: only the map finds it among a thousand",
    "his word given (you will embody it), have him close WorldBox: `tools/chapter/favorite.py <id>` rebuilds this chapter around it",
    "refused: the next best, never of a kind turned down, until one is taken — the world has enough thinking souls, so the chapter never goes without",
)

_DEV_NOTE = (  # what a developer's note may hold, before a pick as at delivery — flagged, never done by the chronicler's own hand
    "doc adjustment: a passage of docs/ unclear, contradictory, out of date, or a term to harmonise — flagged, never corrected by your hand",
    "script improvement spotted on the way: a bug, a field misread, a wrong formula, an awkward output — name the file; no code change of your own",
    "doc and recap at odds: the recap is right for now, but one of the two needs fixing — say which",
    "obscure field: one whose meaning stays uncertain, the wiki included",
    "costly reading: a step that ate the context — say what you read and what you sought — or a passage, an output section, costing without serving: say which",
    "new tag: an important kind of event that no code in docs/tags.md covers",
    "new word: one the tale keeps reaching for — imposed, banned or by a scale — that docs/lexicon.md lacks",
    "missing tool: a recurring analysis that deserves its own script",
    "and any other observation within your remit",
)

_DIALOGUE = "chronicler.md § V, « Un dialogue quand le favori parle »"  # what the audit judges a dialogue by, in the rule's own words
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
_FLAGS = frozenset({"--deliver", "--description", "--erosion", "--finalize", "--name", "--reset", "--reset-asked", "--retouch"})  # all `main` reads
_GEO_ASSETS = re.compile(r"(volcano|geyser)", re.IGNORECASE)  # WB's three natural landmarks, `acid_geyser` included — all a bare world keeps of `buildings`
_GROWN = frozenset({"adult", "teen"})  # the stages a kind may be counted on: past childhood, an elder read as the adult it is — its span is not asked
_H1_CAP = 68  # in no doc: `--finalize` gives it as the H1 falls due, and holds the audit on it
_INDEX_JSON = SAVES_DIR / "index.json"  # the chapter list the reader's nav reads, so it need not open every `chapter.json` to name them
_KINGDOM_FLOOR = 2  # even a Tiny map must raise two crowns before it stands alone: one war would else leave a single people
_LAND_PER_KINGDOM = 56_222  # above a quarter of a grown map's crowns (~12k land tiles each on two worlds): at that, too many rose before the alert
_LAND_PER_THINKER = 53_410  # dry ground per thinking soul a world raises before a favorite is picked: ten on a world of half a million land tiles
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
_PLACE = (
    "a place named this chapter: the facts check that its point falls on what its kind names, a spreading one's `box` on its extent;"
    " its kind and sign say what the chapter says of it"
)

_PLAIN = "plain text with no tag"  # what a field of `chapter.json` is written in: its panel prints it as it stands, brackets and all
_README = Path(__file__).resolve().parents[5] / "README.md"  # its World laws table, the player's guide and the reset's alike: one table, no copy
_RECAP_RULE = "  " + "─" * 40  # closes each block of the recap's report — the chapter's state, what fired, the journal — the last two only where they print

# Put to the player at the first chapter, before a line is written. Three commands answer it, the naming brief riding with the third, erosion a flag on either reset.
_RESET_PROMPT = (
    "? first chapter — nothing is written until the player has answered. Put this to him, in one go:",
    "  « Do you want to start over from a bare map — relief, biomes, volcanoes — some woken — and geysers kept, everything else erased (creatures,",
    "    trees, plants, ores, buildings, kingdoms…), back to year 1 of the Age of Hope with a new genetic seed and the README's world laws?",
    "    And if so, shall I name it too? And turn erosion on? {beach}% of its shore is beach: erosion slowly lays one along the rest, a tile deep, each",
    "    tile losing its biome. »",
    "  → no: `tools/chapter/new.py --reset-asked`",
    "  → reset alone: `tools/chapter/new.py --reset`, and the world keeps the name and description it carries",
    '  → reset and naming: `tools/chapter/new.py --reset --name "…" --description "…"`',
    "    then a second question, before a word is forged: « Would you add a few lines of lore of your own — its myths, its gods, its mood — for it to carry? »",
    "    The name is forged after a survey of its geography, the one thing the reset spares, by `tools/geography/info.py` — the picture only places what it says,",
    "    a bare summit showing white as snow does. In the chronicle's own voice, on the ground, the mood or whatever outlasts the ages, never the age itself;",
    "    a name with the ring of an old tongue, coined or compounded, never a plain word for the shape it sees. Yours alone to choose — his yes was the agreement —",
    "    unless his lore already names the world: that name then stands, and you offer to forge another.",
    "    The description is written as ever, after that survey, his lore woven in if he wrote some.",
    "  → erosion, if he wants it: `--erosion` added to the reset, either kind — without it, erosion stays off",
)

_SEEDED = ("islands", "lakes", "rivers", "seas")  # the gazetteer's books the survey seeds by id, `places` being the chronicler's own
_SHORT_AGES = frozenset({"age_despair", "age_ice"})
_SHORT_AGE_YEARS = (30, 40)
_STAMP_SLACK = 1  # seconds a mod's stamp may stray from the save's own time: WB stores it less finely, a save from before lies years off
_SUBAGENT_GRACE = 120  # seconds: a transcript written this lately may be a sub-agent still at work, not to be pulled from under it

# What a trait summary is — in no doc: said to the chronicler as one falls due, and handed to the audit with the targets that name one.
_SUMMARY = f"what those traits make of the body, {_PLAIN}; never a list, a tally of traits or a figure that ages — read alone, it may echo the chapter"

_SUMMARY_CAP = 400
_SUMMARY_CAPS = {"subspecies": 500}  # a lineage's alone is given more room: a biology is born whole, where the other tiers gather their traits one by one
_TAG_ID = re.compile(r"\[([a-z]) ([^\s\]]+)[^\]]*\]")  # a marker by its letter and its id, for what the id answers to

# Where an entity's tag reads its id, in the chapter's own registries — a hull (`o`) and a war (`w`) have none, and go unweighed.
_TAG_REGISTRIES = {
    "a": "languages",
    "b": "books",
    "c": "cities",
    "e": "religions",
    "f": "families",
    "i": "alliances",
    "k": "kingdoms",
    "l": "clans",
    "p": "persons",
    "t": "cultures",
    "u": "subspecies",
}

_TALKS = frozenset({"socialize_do_talk", "socialize_receiving"})  # WB's two talking tasks: the favorite speaking, the favorite spoken to
_THINKER_FLOOR = 3  # thinking souls a pick waits for even on the smallest map: with fewer, the choice is made before the world has one to offer
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

_WATCHES = SAVES_DIR / "watches.md"  # the story auditor's register of open threads: the world's, as its chapters are, and kept with them in the chronicle's Git
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
        *([f"dialogue owed: {facts['talk']} — {_DIALOGUE}"] if facts["talk"] else []),
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


# The share of the shore already beach, `grid.shore_tally`'s, whole for the player — the figure the reset's question quotes.
def _beach_pct(save: dict) -> str:
    shore, beach = shore_tally(save)
    pct = round(beach / shore * 100) if shore else 0
    return "under 1" if beach and not pct else str(pct)  # a trace of sand never rounded to none


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

    # The world's first birth (an egg once laid), first two towns and first death, once a chronicle, off WB's counters — a metamorphosis is no death.
    stats = live["mapStats"]
    died = int(stats.get("deaths") or 0) - int(stats.get("metamorphosis") or 0)
    towns = int(stats.get("citiesCreated") or 0)

    # Its first house is read off the map, once it stands: WB's `housesBuilt` takes a fire and a stockpile for one, and counts a site the day it is laid.
    housed = any((b.get("asset_id") or "").startswith("house") and not under_construction(b) for b in live.get("buildings") or [])

    # The first migrants a fire called in, off each crown's `migrated` (`Kingdom.increaseMigrants`): a realm gone takes its count along, a rare miss.
    migrated = sum(int(k.get("migrated") or 0) for k in live.get("kingdoms") or [])
    firsts = (
        ("FIRST_BIRTH", stats.get("creaturesBorn")),
        ("FIRST_CITY", towns),
        ("FIRST_DEATH", died),
        ("FIRST_HOUSE", housed),
        ("FIRST_MIGRANTS", migrated),
        ("SECOND_CITY", towns >= 2),  # a town beside the first: the world has a neighbour, a crown's or a rival's
    )

    for tag, count in firsts:
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


# Commits the chapters named and the register beside them, the Git told what it keeps: one round's own text, never another chapter's retouch swept along.
def _commit(message: str, *chapters: str) -> None:
    if not (kept := SAVES_DIR / ".gitignore").exists() or kept.read_text() != _CHRONICLE_KEPT:  # a Git made before the register joined it
        kept.write_text(_CHRONICLE_KEPT)
    chronicle_git("add", "-A", "--", *chapters, *([_WATCHES.name] if _WATCHES.exists() else []))
    if chronicle_git("diff", "--cached", "--quiet").returncode:
        chronicle_git("commit", "-q", "-m", message)


# The crowns held or within reach: each realm, then each kind wearing none whose grown body could found where it stands. A crown is its king's kind's, no subject's.
def _crowns_in_reach(save: dict, save_path: Path) -> int:
    island_of, grid = compute_islands_cached(save, save_path)[1], LazyTileGrid(save)
    ctx = build_actor_stats_context(save) | {
        "city_zones": cache(lambda: city_zones(save, island_of)),
        "island_lookup": lambda: island_of,
        "tile_grid": lambda: grid,
        "tile_map": save["tileMap"],
        "world_laws": world_laws(save),
    }
    realms, actors = save.get("kingdoms") or [], save.get("actors_data") or []
    kings = {realm.get("kingID") for realm in realms}
    kind_of = {actor["id"]: actor.get("asset_id") for actor in actors if actor["id"] in kings}
    crowned = {kind_of.get(realm.get("kingID")) or realm.get("original_actor_asset") for realm in realms}
    free: set[str] = set()
    for actor in actors:  # a kind once counted is asked no more: the ground is weighed for its first founder alone
        if (kind := actor.get("asset_id")) in crowned or kind in free or actor.get("cityID") or is_boat(actor):
            continue
        if not is_sapient(ctx["subspecies_by_id"].get(actor.get("subspecies"))):
            continue
        grown = life_stage(actor_age(actor, ctx["world_time"]), adult_age(actor, ctx), 0, is_egg(actor, ctx)) in _GROWN
        if grown and settle_gates(actor, ctx) in (True, ["child"]):
            free.add(kind)
    return len(realms) + len(free)


# A seeded land or water the chronicler has just named takes this chapter for its own → the names dated: his to give, the date the map shows them from ours.
def _dated_places(n: int) -> list[str]:
    places = _gazetteer()
    fresh = [entry for book in _SEEDED for entry in (places.get(book) or {}).values() if entry.get("name") and not entry.get("chapter")]
    for entry in fresh:
        entry["chapter"] = f"C{n}"
    if fresh:
        PLACES_JSON.write_text(render(places) + "\n")
    return [entry["name"] for entry in fresh]


# The close of the audit, once its last round is settled: step 5 checked again and the chapter's floor, the audit having maybe moved both, then the hand-back.
def _deliver() -> int:
    if not (n := latest_chapter()):
        print("✗ no chapter yet — run `tools/chapter/new.py` first", file=sys.stderr)
        return 1
    settings = reader_settings()
    _tidy_cards(n)
    facts = _step_five_facts(n, settings.get("lang", ""))
    length = facts["length"]
    floor = chapter_floor(n)
    short, long = length < floor, length > CHAPTER_CAP
    if short or long or not facts["done"]:
        print(f"✗ C{n} — not yet deliverable")
        _print_step_five(n, facts)
        if short:
            print(f"  ✗ chapter.md, {length} characters of {floor} at least, {COUNTED_AS} — what the tale gains goes back to the audit")
        elif long:
            print(f"  ✗ chapter.md, {length} characters of {CHAPTER_CAP} at most, {COUNTED_AS} — cut whole passages, the least-borne first, never a correction")
        print("  → set these right, then run `tools/chapter/new.py --deliver` again")
        return 1
    print(f"✓ C{n} — delivery")
    if _snapshot(n) is not None:  # what a retouch after delivery is weighed against, `echo.py` weighing those lines alone
        chronicle_git("tag", "-f", f"C{n}-delivered")
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
            " theirs and yours not yet raised, crossed where they meet — none at all if there are none. What may go in it:"
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
            if name := key if book == "places" else entry.get("name"):  # a seeded land or water goes by its id until it is named, and shows nothing till then
                held.setdefault(place_point(entry), []).append(name)
    fresh = {name for name, spot in (gazetteer.get("places") or {}).items() if spot.get("chapter") == f"C{n}"}
    return [(name, x, y, other) for (x, y), names in held.items() for name in names if name in fresh for other in names if other != name]


# The H1 a chapter is born under, in the chronicle's language — the settings' own unless `lang` is already in hand.
def _draft_heading(lang: str | None = None) -> str:
    return _DRAFT_HEADINGS.get(reader_settings().get("lang", "") if lang is None else lang, "Draft")


# The tiles of dry ground a world holds, ocean aside: what its crowns and its thinking souls are weighed against — summed off its runs, a fifth of its tiles.
def _dry_land(save: dict) -> int:
    sea = [tile_layer(name) == "Ocean" for name in save.get("tileMap") or []]
    return sum(length for tile, length in tile_runs(save) if not sea[tile])


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


# The favorite's talk at the save's instant, as `chapter.json` drops its task: who speaks with whom, `None` while it does anything else.
def _favorite_talk(n: int, favorite: dict) -> str | None:
    if (favorite_id := (favorite.get("metadata") or {}).get("id")) is None or not (wbox := SAVES_DIR / f"C{n}" / "map.wbox").exists():
        return None
    bodies = {actor["id"]: actor for actor in load_save(wbox).get("actors_data") or []}
    if (actor := bodies.get(favorite_id)) is None or (task := kept_task(actor)) not in _TALKS:
        return None
    other = bodies.get((kept_task_target(actor) or {}).get("actor"))
    name = other.get("name") or other.get("asset_id") if other else "another"
    return f"the favorite talks with {name}" if task == "socialize_do_talk" else f"{name} talks to the favorite"


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
    lang = reader_settings().get("lang", "")
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
    # The text tagged as this round reads it, so a relaunch hands over what moved since the auditor's own round rather than a list, or a memory.
    if (rounds := _snapshot(n)) is not None:
        tag, before = rounds
        print(f"  → this text is round {tag}{f' — {_relaunch(n, tag, before)}' if before else ''}")
    return 0


# The alerts whose law is on and whose condition holds: crowns standing or within reach, as many as the dry ground can bear — no more need fall from the clouds.
def _fired_alerts(save: dict, save_path: Path) -> list[str]:
    laws = world_laws(save)
    standing = [code for code, law in _ALERTS.items() if laws.get(law, True)]  # the laws first: once they are off, the world is not walked at all
    return standing if standing and _crowns_in_reach(save, save_path) >= _kingdom_quota(save) else []


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


# `places.json` as it stands, read afresh at each call: the chronicler writes it between two runs, and `--finalize` itself dates it on the way.
def _gazetteer() -> dict:
    return json.loads(PLACES_JSON.read_text()) if PLACES_JSON.exists() else {}


# How many crowns a world must raise before it feeds itself: one per `_LAND_PER_KINGDOM` of dry ground, never under the floor. Ocean is no one's to rule.
def _kingdom_quota(save: dict) -> int:
    return max(_KINGDOM_FLOOR, int(_dry_land(save) / _LAND_PER_KINGDOM + 0.5))  # nearest, not ceiling — `round` breaks ties to the even number


# WB's `life_dna` seeds a world's genetics, redrawn on the hour so a reused map never repopulates with the lineages before it. WB's format: `YYYYMMDDHH`, UTC.
def _life_dna() -> int:
    return int(datetime.now(UTC).strftime("%Y%m%d%H"))


# The places this chapter baptised whose heart stands off the land their `island_id` names — none named means off every counted land: the sea, or an islet.
def _misplaced_places(n: int) -> list[tuple[str, int, int, int | None, int | None]]:
    spots = _gazetteer().get("places") or {}
    if not (fresh := [(name, spot) for name, spot in spots.items() if spot.get("chapter") == f"C{n}"]):
        return []  # nothing baptised here, and so no save to open
    save_path = SAVES_DIR / f"C{n}" / "map.wbox"
    _, land_of = compute_islands_cached(load_save(save_path), save_path)
    misplaced = []
    for name, spot in fresh:
        (x, y), declared = place_point(spot), spot.get("island_id")
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
    # No favorite while enough thinking souls stand: the pick comes first, `favorite.py` erasing the chapter, prose and all, to rebuild it around the one chosen.
    if forgotten:
        print(f"  → chronicler: {forgotten} sub-agents of earlier work deleted — forget their ids")
    # A pick waits for a people to choose from, the world told alone meanwhile; a favorite standing, there is no pick to weigh.
    thinkers, wanted = (thinking_souls(live), _thinkers_wanted(live)) if favorite is None else (0, 0)
    if 0 < thinkers < wanted:
        print(f"  → no favorite yet: {thinkers} thinking souls of the {wanted} this world's ground wants before one is picked")
    if favorite is None and thinkers >= wanted:
        if reader_settings().get("dev"):  # a misread would steer the pick, so his snags are heard before it — his alone, no draft having met an auditor yet
            print("  → mode: developer — first, a brief note of your own frictions so far, none at all if there are none. What may go in it:")
            _print_bullets(_DEV_NOTE)
            print("    a note given, wait for the player's word before the pick: what he clears up may change it")
        print("  → chronicler: choose a favorite before a single word, the best of those there are — your pick, not the player's:")
        _print_bullets(_CHOICE)
        print("  → then put it to the player:")
        _print_bullets(_DESIGNATION)
        print("  → once he is marked, step 3, the analysis, before the first word and not to be hurried:")
    else:
        print("  → chronicler: step 3, the analysis, before the first word and not to be hurried:")
    fav_id = ((favorite or {}).get("metadata") or {}).get("id")
    if n > 1:
        order = ", the favorite first, then thread by thread:" if fav_id else ","  # the chapter's own order, so the analysis lands already sorted by thread
        print(f"    · the deltas since C{n - 1}{order} what moved as much as what held — `geography bodies C{n}` shows a land newly peopled")
    print("    · the thresholds just crossed: the first times, the levels reached")
    since = f"since C{n - 1}" if n > 1 else "since the world began"
    print(f"    · the turning points, what tipped {since} — a death, a crown, a first time, a watch the world settled: one at least becomes a scene")
    if fav_id:
        if n > 1:
            print(f"    · what changed on the favorite: `actor {fav_id} --since C{n - 1} C{n}` — its walk and its gates, read before a word of it")
        print(f"    · who lives around the favorite: `actor {fav_id} surroundings C{n}`, each by its id: names repeat")
    if n > 1:
        print(f"    · the chapter before, reread: `saves/C{n - 1}/chapter.md`, and the open watches to settle or carry: `saves/watches.md`")
    print("  → then, before a word, the story auditor's counsel — a sub-agent launched now, its id kept for the audit:")
    # Each place the brief names measured from the favorite, lest a counsel be built on a north that is a south: a world with no favorite has none to measure from
    measured = f', each place named with its measure from the favorite (actor {fav_id} --to "<place>")' if fav_id else ""
    print(f"    `{_COUNSEL.format(n=n, measured=measured)}`")
    told = "" if fav_id else " — no favorite, so the world itself, in two parts and no circle:"
    print(f"  → step 4, the writing: {chapter_floor(n)} to {CHAPTER_CAP} characters, {COUNTED_AS}, counted at delivery, past the audit{told}")
    if not fav_id:
        _print_bullets(_WORLD_ONLY)
    # In no doc: the cycle is the script's to tell, step by step. A chapter still under its draft title reads as unfinished, to the reader and to `--finalize`.
    print(f"  → step 5, once written under the H1 `# {_draft_heading()}`, kept till then: `tools/chapter/new.py --finalize`, followed to delivery")


# The recap's first half: where the world stands, what fired, and what the journal logged since the chapter before.
def _print_report(n: int, live: dict, age_id: str, favorite: dict | None, regime: str, tags: list[str], prev_world: dict) -> None:
    age_label = i18n("ages.json").get(age_id) or age_id  # recap line only, in the chronicle's own words — the chapter carries the id alone
    year = int(rounded_world_time(live["mapStats"]) / UNITS_PER_YEAR) + 1  # WB `Date.getYear`: the displayed year is 1-based, `getYear0` alone lags a year behind
    fav = (favorite or {}).get("metadata")  # by `named_body`: a favorite WB never named, the chronicler's own epithet aside, goes by its kind and id
    print(f"✓ C{n} — year {year}, {age_label}")
    print(f"  favorite: {named_body(fav) if fav else 'none'}{f' — {regime}' if regime else ''}")
    print(_RECAP_RULE)
    if events := _events(tags):  # a tag in `chapter.json` alone never reaches the chronicler
        for code in events:
            print(f"  ⚑ {code}")
        print(f"  → each ⚑ is {_EVENT}")
        print(_RECAP_RULE)
    # A law the player turned since the chapter before changes what the world may do, and `world … laws` is no part of `full`: nothing else would say it.
    then = prev_world.get("laws") or {}
    if turned := sorted(f"{_LAW_NAMES.get(law, law)} {'on' if on else 'off'}" for law, on in world_laws(live).items() if law in then and then[law] != on):
        print(f"  ⚖ world laws turned since C{n - 1}: {', '.join(turned)} — `tools/wiki/info.py World_Laws --entry <law>` says what each rules")
        print(_RECAP_RULE)
    # The one source naming a killer, printed so a king's fall needn't wait on the file; none at C1, whose whole past would pour out: `history log`'s to give.
    journal = log_entries(float(prev_world.get("world_time") or 0)) if n > 1 else []
    for entry in journal:  # the killer named as such, `special1..3` shifting meaning, the point by whose place it is — a meteorite names no one, its point its own
        told = [f"{role} {entry[role]}" for role in ("favorite", "king", "killer") if entry.get(role)] or (entry.get("names") or [])
        print(f"  ✎ {' · '.join((entry['date'], entry['event'], *told))} ({entry['point'] or 'at'} {entry['x']},{entry['y']})")
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
        print("  → every length above counts spaces too, a tag by its name alone")
    for name, x, y, other in facts["doubled"]:
        print(f"  ✗ places.json « {name} »: ({x},{y}) is the very point of « {other} » — its sign needs a point of its own on the map")
    for name, x, y, found, declared in facts["misplaced"]:
        print(f"  ✗ places.json « {name} »: ({x},{y}) lies on {f'land {found}' if found else 'no counted land'}, its `island_id` saying {declared or 'none'}")
    if facts["doubled"] or facts["misplaced"]:
        print("  → set these right in history/places.json")
    for fault in facts["dialogues"]:
        print(f"  {fault}")
    if stray := facts["stray"]:
        tags = ", ".join(f"l.{line} {tag}" for line, tag in stray)
        print(f"  ✗ tags whose id answers nothing: {tags} — an id made up, or one only `history` knows, shows a blank where its icon goes")


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
    with closing(sqlite3.connect(s3db)) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        for (table,) in cursor.fetchall():
            cursor.execute(f'DELETE FROM "{table}"')  # interpolated, but the name comes from the file's own schema a line above
        conn.commit()
        cursor.execute("VACUUM")


# The README's World laws table by law id, on or off, and the titles in it WB knows no law by — a typo that must refuse the reset, not pass unset.
def _readme_laws() -> tuple[dict[str, bool], list[str]]:
    text = _README.read_text()
    table = text[text.index("## World laws") :].split("\n## ", 1)[0]
    ids = {title: law for law, title in _LAW_NAMES.items()}
    laws, unknown = {}, []
    for row in re.findall(r"^\|[^|\n]+\|([^|\n]+)\|([^|\n]+)\|$", table, re.MULTILINE)[2:]:  # the header and its rule first
        for cell, on in zip(row, (True, False), strict=True):
            for title in map(str.strip, cell.split(",")):
                if title in ids:
                    laws[ids[title]] = on
                elif title not in {"", "—"}:
                    unknown.append(title)
    return laws, unknown


# Whether the prose a delivered chapter's record carries has moved since its last commit: a descriptor or a summary is audited, a panel's data never.
def _record_prose_moved(n: int) -> bool:
    committed = chronicle_git("show", f"HEAD:C{n}/chapter.json")
    path = SAVES_DIR / f"C{n}" / "chapter.json"
    before = json.loads(committed.stdout) if not committed.returncode else {}
    return path.exists() and _written_prose(json.loads(path.read_text())) != _written_prose(before)


# What the favorite line adds, so the chronicler need not deduce it — a favorite gone from `actors_data` is dead, and nothing else says so. Silent when it holds.
def _regime(n: int, actors: list, fav_id: int | None, prev_fav_id: int | None) -> str:
    if n == 1:
        return "first chapter"
    if prev_fav_id is not None and not any(a.get("id") == prev_fav_id for a in actors):  # WB drops the dead from `actors_data`: an absent favorite is a dead one
        # The pick itself is the closing block's, printed only while enough thinking souls are left to pick from.
        return f"{'the favorite has' if fav_id is None else 'successor to one who has'} left the world — {_DEATH}"
    return "yet to be designated" if fav_id is None else ""


def _relaunch(n: int, tag: str, before: str) -> str:
    return f"a relaunch hands each auditor `git -C saves diff <its last round> {tag} -- C{n}`, both tags for any git read; the one before: {before}"


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
def _reset_world(live_wbox: Path, name: str, description: str, erosion: bool) -> int:
    if worldbox_running():
        print("✗ WorldBox is running — quit the game before resetting, or it will write its own save back over this one", file=sys.stderr)
        return 1
    laws, unknown = _readme_laws()
    if unknown:
        print(f"✗ README.md, World laws: no law of WB goes by {', '.join(unknown)} — its titles are the game's own, in English", file=sys.stderr)
        return 1

    save = load_save(live_wbox)
    _bare_world(save, name, description)
    woken, volcanoes = _wake_volcanoes(save)
    # The README leaves two to the reset: no volcano, no lava but the map's own to keep; erosion, the player's own answer.
    turned = _set_laws(save, {**laws, "world_law_erosion": erosion, "world_law_forever_lava": not volcanoes})
    stats = save["mapStats"]
    write_save(live_wbox, save)
    _write_world(save)  # off the save, not off the arguments: a world that kept its name keeps it here too
    _purge_history(live_wbox.parent / "map_stats.s3db")
    (live_wbox.parent / "map.meta").unlink(missing_ok=True)  # WB rebuilds it from the save on opening; writing it ourselves would guess at a format we only read

    landmarks = ", ".join(f"{count} {asset}" for asset, count in sorted(Counter(b["asset_id"] for b in save["buildings"]).items()))
    print(f"✓ world reset — year 1 of the Age of Hope, {stats['current_world_ages_duration'] / UNITS_PER_YEAR:.0f} years long")
    print(f"  map kept, {f'with its landmarks: {landmarks}' if landmarks else 'no landmark on it'}")
    print(f"  volcanoes: {woken} of {volcanoes} woken, erupting till lightning or a cold aura stills them" if volcanoes else "  no volcano: its lava kept for good")
    print(f"  world laws as the README sets them{f', turned: {", ".join(turned)}' if turned else ', none to turn'}")
    print(f"  named: {stats['name'] or '—'}")
    if name or description:  # his own words, written before any audit stood and read by none after: checked here, the game still closed for the mending
        target = f"history/world.json (description, name) [{_BAPTISM}]"
        print(f"  → chronicler, first, the game still closed: a fresh sub-agent checks them — `Lis docs/audit/facts.md — {target}`")
        print('    a gap is fixed with `tools/chapter/new.py --name "…" --description "…"`, either alone leaving the other; the first chapter deletes the sub-agent')

    # The game alone redraws preview.png and has the mods stamp the save: hence the re-save, which is the one the chapter archives.
    when = ", once that check is done and mended — never while it runs" if name or description else ""
    print(f"  → player{when}: reopen the save in WorldBox and save again — the chapter then archives the world as it now stands")
    print("  → chronicler: once he has, `tools/chapter/new.py --reset-asked` writes the first chapter, on the bare world as it stands")
    return 0


# Delivered chapters reworked since their last round, each tagged `C<n>-r<k>` for a relaunch's diff — one whose panels' data alone moved, apart and roundless.
def _retouch() -> int:
    if not (SAVES_DIR / ".git").exists():
        print("✗ no chronicle Git yet — `--finalize` makes it at a chapter's first round", file=sys.stderr)
        return 1
    delivered = {int(tag[1:].split("-")[0]) for tag in chronicle_git("tag", "--list", "C*-delivered").stdout.split()}
    moved = re.findall(r"C(\d+)/(\S+)", chronicle_git("status", "--porcelain", "--", *(f"C{n}" for n in delivered)).stdout)
    touched = {int(n) for n, _ in moved} & delivered
    changed = sorted(n for n in touched if (str(n), "chapter.md") in moved or _record_prose_moved(n))  # its tale, or the prose its record carries
    if not (refreshed := sorted(touched - set(changed))) and not changed:
        print("✗ no delivered chapter has moved since its last round — the chapter under way rounds with `--finalize`", file=sys.stderr)
        return 1
    if refreshed:
        _commit(f"data {', '.join(f'C{n}' for n in refreshed)}", *(f"C{n}/chapter.json" for n in refreshed))
        print(f"✓ {', '.join(f'C{n}' for n in refreshed)} — data for the panels alone, committed with no round: nothing to read again")
    if not changed:
        return 0
    _commit(f"retouch {', '.join(f'C{n}' for n in changed)}", *(f"C{n}" for n in changed))
    latest = latest_chapter()
    for n in changed:
        rounds = sorted(int(tag.rsplit("-r", 1)[1]) for tag in chronicle_git("tag", "--list", f"C{n}-r*").stdout.split())
        chronicle_git("tag", tag := f"C{n}-r{rounds[-1] + 1 if rounds else 1}")
        before = f"C{n}-r{rounds[-1]}" if rounds else f"C{n}-delivered"
        if n < latest:  # its auditors went when the next chapter opened (`_forget_subagents`): the latest's read it, fresh ones costing a whole context each
            told = f"its auditors left with C{latest}'s opening: relaunch C{latest}'s by message on C{n}, handing `git -C saves diff {before} {tag} -- C{n}`"
            told += " and both tags — fresh ones only if none is alive yet"
        else:
            told = _relaunch(n, tag, before)
        print(f"✓ C{n} — round {tag}: {told}")
    return 0


# Runs a sibling `info.py` → its parsed JSON stdout, `None` (stderr surfaced) on failure or empty output. `sys.executable` so a venv never forks children elsewhere.
def _run(rel_path: str, *args: object) -> dict | None:
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
        PLACES_JSON.write_text(render(places) + "\n")

    registries.ensure(chapter, live)  # `live` is handed over so it spares itself a re-parse of the save we already hold
    return None


# Sets each law the README names, appending one an older save lacks → each law it turned, by WB's title.
def _set_laws(save: dict, laws: dict[str, bool]) -> list[str]:
    held = world_laws(save)
    entries = save.setdefault("worldLaws", {}).setdefault("list", [])
    for entry in entries:
        if entry["name"] in laws:  # every entry is named, as `world_laws` reads them
            entry["boolVal"] = laws[entry["name"]]
    entries.extend({"name": law, "boolVal": on} for law, on in laws.items() if law not in held)
    return sorted(f"{_LAW_NAMES[law]} {'on' if on else 'off'}" for law, on in laws.items() if held.get(law) != on)


# Tags the chapter as an audit round reads it, `C<n>-<k>`, and returns that round with the one before — the last one again when nothing moved since it.
def _snapshot(n: int) -> tuple[str, str | None] | None:
    # Made here the first time it is missing: a world's first round, the first since the reader's reset swept it away with the world, or the first at all.
    if (fresh := not (SAVES_DIR / ".git").exists()) and chronicle_git("init", "-q").returncode:
        return None
    _commit(f"C{n}", f"C{n}")
    for k in range(1, n) if fresh else ():  # every chapter before this one was delivered, a chapter opening only once the last is
        chronicle_git("tag", f"C{k}-delivered")
    rounds = sorted(int(k) for tag in chronicle_git("tag", "--list", f"C{n}-*").stdout.split() if (k := tag.rsplit("-", 1)[1]).isdigit())
    last = f"C{n}-{rounds[-1]}" if rounds else None
    if last and not chronicle_git("diff", "--quiet", last, "HEAD", "--", f"C{n}").returncode:
        return last, f"C{n}-{rounds[-2]}" if len(rounds) > 1 else None
    chronicle_git("tag", tag := f"C{n}-{rounds[-1] + 1 if rounds else 1}")
    return tag, last


# Step 5 off the chapter's files: its H1 and length, the favorite's descriptor and if carried, the summaries owed or too long, places astray, prose new since C<n-1>.
def _step_five_facts(n: int, lang: str) -> dict:
    chapter_dir, prior_path = SAVES_DIR / f"C{n}", SAVES_DIR / f"C{n - 1}" / "chapter.json"
    chapter = json.loads((chapter_dir / "chapter.json").read_text())
    prior = json.loads(prior_path.read_text()) if prior_path.exists() else {}
    prose = (chapter_dir / "chapter.md").read_text()
    headings = [line[2:] for line in prose.splitlines() if line.startswith("# ")]
    draft = _draft_heading(lang)
    favorite, before = chapter.get("favorite") or {}, prior.get("favorite") or {}
    descriptor = favorite.get("descriptor")
    same = (before.get("metadata") or {}).get("id") == (favorite.get("metadata") or {}).get("id")  # a favorite stays so until death: another, or none, mourns him
    carried = bool(descriptor) and same and descriptor == before.get("descriptor")
    written = {tier: summary for tier in _TRAIT_SOURCES if isinstance(summary := (chapter.get(tier) or {}).get("traits"), str)}
    h1 = headings[0] if len(headings) == 1 and headings[0] != draft else None
    h1_length = len(unmarked(h1 or ""))
    owed = {tier: _entity_id(chapter[tier]) for tier in sorted(_TRAIT_SOURCES) if chapter.get(tier) and tier not in written}
    long = {tier: f"{size} of {cap}" for tier, text in sorted(written.items()) if (size := len(text)) > (cap := _SUMMARY_CAPS.get(tier, _SUMMARY_CAP))}
    dialogues, doubled, misplaced, stray = short_dialogues(prose), _doubled_places(n), _misplaced_places(n), _stray_tags(n, prose)
    # A summary carried word for word was audited when written, so only a new one goes; the descriptor always, an age in it stale by the next chapter.
    fresh = [f"{tier}.traits" for tier in sorted(_TRAIT_SOURCES) if chapter.get(tier) and written.get(tier) != (prior.get(tier) or {}).get("traits")]
    faults = dialogues or doubled or owed or long or misplaced or stray
    return {
        "audited": sorted(fresh + (["favorite.descriptor"] if favorite else [])),
        "carried": carried,
        "descriptor": descriptor,
        "dialogues": dialogues,
        "done": 0 < h1_length <= _H1_CAP and (not favorite or 0 < len(descriptor or "") <= _DESCRIPTOR_CAP) and not faults,
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
        "stray": stray,
        "talk": _favorite_talk(n, favorite),
    }


# The chapter's tags whose id answers nothing, by line: an entity's is read in the chapter's registry, a kind's in WB's own data.
def _stray_tags(n: int, prose: str) -> list[tuple[int, str]]:
    kinds = {"g": load_data("equipment.json")["items"], "r": asset_set("resources"), "s": load_data("species.json")}

    @cache
    def known(letter: str) -> Collection[str] | None:
        if letter in kinds:
            return kinds[letter]
        if (name := _TAG_REGISTRIES.get(letter)) is None:
            return None
        return json.loads(path.read_text()) if (path := SAVES_DIR / f"C{n}" / f"{name}.json").exists() else {}

    tags = ((at, tag) for at, line in enumerate(prose.splitlines(), 1) for tag in _TAG_ID.finditer(line))
    return [(at, tag[0]) for at, tag in tags if (ids := known(tag[1])) is not None and tag[2] not in ids]


# How many thinking souls a world raises before its favorite is picked: one per `_LAND_PER_THINKER` of dry ground, never under the floor.
def _thinkers_wanted(save: dict) -> int:
    return max(_THINKER_FLOOR, int(_dry_land(save) / _LAND_PER_THINKER + 0.5))


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
    for card in (SAVES_DIR / f"C{n}" / "chapter.json", PLACES_JSON):
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
    return {str(f["id"]): {"chapter": "", "heart": f.get("heart") or f["centroid"], "name": "", "size": f["size"]} for f in features}


def _value(argv: list[str], flag: str) -> str:
    return argv[i] if flag in argv and (i := argv.index(flag) + 1) < len(argv) else ""


# Wakes between one and two thirds of the volcanoes, the rest put to sleep → (woken, volcanoes). An awake one erupts for good: two thirds leave the world some calm.
def _wake_volcanoes(save: dict) -> tuple[int, int]:
    volcanoes = [b for b in save["buildings"] if b["asset_id"] == "volcano"]  # landmarks alone, each named by `_bare_world`'s own filter
    random.shuffle(volcanoes)  # the local list alone: `buildings` keeps its order
    woken = random.randint(1, max(1, len(volcanoes) * 2 // 3)) if volcanoes else 0
    for rank, volcano in enumerate(volcanoes):
        flags = [flag for flag in volcano.get("custom_data_flags") or [] if flag != "stop_spawn_drops"]
        volcano["custom_data_flags"] = flags if rank < woken else [*flags, "stop_spawn_drops"]
    return woken, len(volcanoes)


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


# The prose the chronicler writes into a `chapter.json`, which the audit reads as it reads the chapter: the favourite's descriptor, each tier's trait summary.
def _written_prose(record: dict) -> dict:
    summaries = {f"{tier}.traits": summary for tier in _TRAIT_SOURCES if isinstance(summary := (record.get(tier) or {}).get("traits"), str)}
    return {**summaries, "favorite.descriptor": (record.get("favorite") or {}).get("descriptor")}


def main(argv: list[str]) -> int:
    if unknown := [a for a in argv if a.startswith("--") and a not in _FLAGS]:  # `--rest` would else read as « no reset asked » and put the question again
        print(f"✗ unknown flag {', '.join(unknown)} — new.py knows {', '.join(sorted(_FLAGS))}", file=sys.stderr)
        return 2
    if "--finalize" in argv:  # step 5 of the chapter under way, off its own files, its archived save among them: nothing is built, the live save never read
        return _finalize()
    if "--deliver" in argv:  # the close of the audit, off the same files
        return _deliver()
    if "--retouch" in argv:  # a round for the delivered chapters reworked since, the chapter under way left to `--finalize`
        return _retouch()
    live_wbox = live_save()
    if not live_wbox.exists():
        print(f"✗ no live save at {live_wbox} — ask the player to update the path, from the Settings button below the map", file=sys.stderr)
        return 2

    if "--erosion" in argv and "--reset" not in argv:  # a law the reset sets, read nowhere else: alone it would pass and do nothing
        print("✗ --erosion rides with --reset alone — on a world kept as it is, the player sets it in WorldBox's world laws", file=sys.stderr)
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
        return _reset_world(live_wbox, _value(argv, "--name"), _value(argv, "--description"), "--erosion" in argv)

    if n == 1 and "--reset-asked" not in argv:  # a reset would throw away whatever is written here, so nothing is, until the player has had his say
        print("\n".join(_RESET_PROMPT).format(beach=_beach_pct(load_save(live_wbox))))
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
            if failed := [f"{call[1]} {call[2]} full" for call, block in zip(calls, results, strict=True) if call and block is None]:
                return _abandon(chapter_dir, failed)
            *bodies, boat = results
            blocks = dict(zip(_TIERS, bodies, strict=True))
            fold_bodies(blocks, boat)

        # A third wave, the only one a tier opens — popped as `transport` is, the blocks it returns holding the names the crown's list would otherwise say twice.
        wars = [w for w in ((blocks.get("kingdom") or {}).pop("wars", None) or []) if w.get("id") is not None]
        if wars:
            fought = _run_together(*((_run, "war/info.py", w["id"], "full", chapter) for w in wars))
            if failed := [f"war/info.py {w['id']} full" for w, war in zip(wars, fought, strict=True) if war is None]:
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

        # The draft's H1, in the language the chronicler writes the chapter in: the reader has a page, and it reads unfinished.
        (chapter_dir / "chapter.md").write_text(f"# {_draft_heading()}\n")
        _write_index(n, world_time)

        _print_report(n, live, age_id, favorite, _regime(n, actors, fav_id, prev_fav_id), tags, prev_world)
        _print_next_step(n, live, favorite, _forget_subagents())
    except BaseException as fault:  # a crash or a Ctrl-C halfway, which `_abandon` never sees: the half-built folder goes the same way, the fault still surfacing
        shutil.rmtree(chapter_dir, ignore_errors=True)
        if isinstance(fault, Exception):  # a Ctrl-C or an exit is no crash, and an exit has said its own ✗ already
            print("✗ new.py crashed — nothing written, report the traceback below", file=sys.stderr)
        raise
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
