#!/usr/bin/env python3

# Bootstraps a new chapter from the live WorldBox save: archives it under `saves/C<n>/`, builds its registries (`registries.py`) and `chapter.json` (`fold.py`).
# The recap steers the chronicler's analysis; `--finalize` then lays out step 5 and what each auditor is handed, `--deliver` the delivery. Docs: `docs/`.

import json
import random
import re
import shutil
import sqlite3
import subprocess
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))

import registries
from fold import drop_chronicler_keys, fold_bodies, fold_favorite_detail, fold_world
from grid import tile_layer, tile_runs
from islands import compute_islands_cached
from shared import (
    HISTORY_S3DB,
    SAVES_DIR,
    UNITS_PER_YEAR,
    index_by_id,
    is_boat,
    is_sapient,
    latest_chapter,
    live_save,
    load_data,
    load_save,
    render,
    rounded_world_time,
    world_laws,
    worldbox_running,
    write_save,
)

# The chapter's own tongue, for what leaves the chronicler: the audit account the player reads beside it, and the one verb each auditor is handed with paths.
_ACCOUNT = {
    "en": {
        "facts": "Fact check: {} gaps fixed",
        "none": "not applicable",
        "read": "Read",
        "reaudit": "Re-audit: {} gaps fixed",
        "story": "Story check: {} gaps fixed",
    },
    "fr": {
        "facts": "Vérification des faits : {} écarts corrigés",
        "none": "non applicable",
        "read": "Lis",
        "reaudit": "Réaudit : {} écarts corrigés",
        "story": "Vérification du récit : {} écarts corrigés",
    },
}

# What becomes of the auditors' reports, in the order it is done — the chronicler's to follow between rounds, said where the audit is handed over.
_AFTER_REPORTS = (
    "every report in hand, and chapter.md untouched while any auditor reads — each report waits for the others, a message from the player or the dev too:"
    " correct each confirmed gap, one raised by a single fact check checked all the same, a tool settling a disagreement",
    "mend first what a section stands on — its closing thread, a superlative, a date — since its fall rewrites the rest; correct where that suffices, rewrite"
    " only what it cannot mend, and read off a tool any figure a rewrite brings, never from the draft, a report or memory",
    "then seek the same value or word everywhere: chapter.md with its title and epigraph, and your prose in chapter.json",
    "the story check's proposals and compliance's better-possible are yours to take or leave, in your own hand",
    "a touch of manner varies or cuts, never swaps a word wherever it recurs, and goes back to no one",
    "what asserts anything new goes back to the same auditors, flagged as new, the lines alone and never your reading of them — each resumed by message"
    " on its report's id, noted as a compaction drops them, a fresh one only if that fails; a cut goes back as the passage it took out, what leaned on it"
    " theirs to find",
    "the last round settled: `tools/chapter/new.py --deliver`",
)

_AGE_LABELS = load_data("world-ages.json")  # WB `WorldAgeLibrary` key → `{name, description}`; an unknown id falls back to the raw key.
_AGE_SLOTS = ("age_hope", *("age_unknown",) * 7)  # WB resolves them one at a time; a world always opens on the first

# World-law alerts, a state while the law stays on: sapient crowns weighed against dry ground, and no settlers cut off while the favorite's own crown stands short
_ALERTS = {
    "DISABLE_DROP_OF_THOUGHTS": {
        "condition": lambda pops, quota, _own: len(pops) >= quota,
        "law": "world_law_drop_of_thoughts",
        "title": "Drop of Thoughts",
    },
    "DISABLE_HANDSOME_MIGRANTS": {
        "condition": lambda pops, quota, own: _stands_alone(own) and sum(1 for sexes in pops if _stands_alone(sexes)) >= quota,
        "law": "world_law_civ_migrants",
        "title": "Handsome Migrants",
    },
}

_AUDITORS = (("compliance", 1), ("facts", 2), ("story", 1))  # each by its sheet under `docs/audit/`, and how many of it the audit opens with
_CHAPTER_CAP = 15000  # a sitting's read, some 12 minutes: past it the chapter says more than its world has done — held with the floor, in no doc either
_CHAPTER_FLOOR = 7500  # in no doc: the recap gives it, delivery holds it — counted past the audit, which cuts as much as it adds
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

_FLAGS = frozenset({"--deliver", "--description", "--finalize", "--name", "--reset", "--reset-asked"})  # all `main` reads — others are refused as typos
_GEO_ASSETS = re.compile(r"(volcano|geyser)", re.IGNORECASE)  # WB's three natural landmarks, `acid_geyser` included — all a bare world keeps of `buildings`
_H1_CAP = 68  # in no doc: `--finalize` gives it as the H1 falls due, and holds the audit on it
_INDEX_JSON = SAVES_DIR / "index.json"  # the chapter list the reader's nav reads, so it need not open every `chapter.json` to name them
_KEPT_STATS = frozenset({"custom_data", "is_world_ages_paused"})  # a dict and a player preference, both of which a numeric sweep would flatten
_KINGDOM_FLOOR = 2  # even a Tiny map must raise two crowns before it stands alone: one war would else leave a single people
_LAND_PER_KINGDOM = 52_044  # a quarter of what a map carries once grown — measured at ~12k land tiles per crown on two worlds
_LIVE_FILES = ("map.wbox", "preview.png")  # archived into the chapter dir under WB's own names; `map.wbox` alone regenerates everything for the chapter
_LONG_AGE_YEARS = (35, 55)  # WB draws an age's span when it opens; only the two bleak ones run shorter
_MAP_BLOCK = 64  # WB sizes a world in blocks of this many tiles, every stock size over: Tiny 2×2 = 128, Iceberg 9×9 = 576. Not `ZONE_TILES`, the city grid.
_MIN_PER_SEX = 2  # `DISABLE_HANDSOME_MIGRANTS`: a crown stands on its own with two of each sex — four bodies of one sex are a hamlet with a banner, and a dead end
_PLACES_JSON = SAVES_DIR.parent / "history" / "places.json"  # the toponyms the chronicler coins — seeded with the world's isles at C1, his thereafter
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

_SETTINGS_JSON = SAVES_DIR.parent / "history" / "settings.json"  # the reader's settings, where the player's workshop switch sits beside the live save's path
_SHORT_AGES = frozenset({"age_despair", "age_ice"})
_SHORT_AGE_YEARS = (30, 40)
_SUMMARY_CAP = 400
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


# The whole rewind, in the order WB's fields depend on one another: survivors first, `id_building` counting from them. Of `buildings`, only landmarks stand.
def _bare_world(save: dict, name: str, description: str) -> None:
    save["buildings"] = [b for b in save.get("buildings") or [] if _GEO_ASSETS.search(b.get("asset_id") or "")]
    for landmark in save["buildings"]:  # stamped afresh: the clock restarts below, and a peak left on the old one would read older than the world it stands in
        landmark["created_time"] = 0.0
    for key in _EMPTIED:
        save[key] = []

    stats = save["mapStats"]
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
def _chapter_tags(live: dict, blocks: dict, boat: dict | None, favorite: dict | None, just_designated: bool, prior: tuple, age_id: str) -> list[str]:
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

    realm = _entity_id(blocks.get("kingdom") or {})  # read twice below: the war tag for what the favorite's crown enters, the migrants alert for what it holds

    # A war the favorite's crown found itself in since the chapter before, whoever declared it — the first chapter having no before, it owes none.
    if realm is not None and (since := prev_world.get("world_time")) is not None and _entered_war(live, realm, since):
        tags.append("FAVORITE_KINGDOM_NEW_WAR")

    if boat:  # a chapter caught at sea — the favorite is aboard right now, which the panel badges and the chronicler owes a scene
        tags.append("FAVORITE_ABOARD")

    # A scheme afoot under the favorite's own hand. Read after the fold, which leaves the type's key behind: a plot ripens in months, so it may be gone next chapter.
    if (favorite or {}).get("plot"):
        tags.append("FAVORITE_PLOTTING")
    return tags + _fired_alerts(live, realm)


# The close of the audit, once its last round is settled: step 5 checked again and the chapter's floor, the audit having maybe moved both, then the hand-back.
def _deliver() -> int:
    if not (n := latest_chapter()):
        print("✗ no chapter yet — run `tools/chapter/new.py` first", file=sys.stderr)
        return 1
    settings = _settings()
    facts = _step_five_facts(n, settings.get("lang", ""))
    length = facts["length"]
    short, long = length < _CHAPTER_FLOOR, length > _CHAPTER_CAP
    if short or long or not facts["done"]:
        print(f"✗ C{n} — not yet deliverable")
        _print_step_five(n, facts)
        if short:
            print(f"  ✗ chapter.md, {length} characters of {_CHAPTER_FLOOR} at least, blanks folded — what the tale gains goes to the audit as new")
        elif long:
            print(f"  ✗ chapter.md, {length} characters of {_CHAPTER_CAP} at most, blanks folded — cut whole passages, the least-borne first, never a correction")
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
        for line in _DEV_NOTE:
            print(f"    · {line}")
    else:
        print("  → mode: player — the chapter and that account, nothing else")
    # A world law's alert asks the player at the close, where the errand is due: raised at step 2, it would have to outlast the whole audit to be remembered.
    laws = [_ALERTS[code]["title"] for code in json.loads((SAVES_DIR / f"C{n}" / "chapter.json").read_text()).get("tags") or [] if code in _ALERTS]
    off = f"to turn the {' and '.join(laws)} world law{'s' if len(laws) > 1 else ''} off, and " if laws else ""
    print(f"  → then hand back: tell the player the chapter is closed, and ask him {off}to say when the save has moved on")
    return 0


# Whether the crown was drawn into a war begun after `since`, on either side and ended or not — the declaration is the event the chapter owes, not the fighting.
def _entered_war(save: dict, kingdom_id: int, since: float) -> bool:
    return any(
        float(war.get("created_time") or 0) > since
        and kingdom_id in {war.get("main_attacker"), war.get("main_defender"), *(war.get("list_attackers") or []), *(war.get("list_defenders") or [])}
        for war in save.get("wars") or []
    )


def _entity_id(block: dict) -> int | None:
    return (block.get("metadata") or {}).get("id")


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
    facts = _step_five_facts(n, lang)
    print(f"✓ C{n} — step 5")
    _print_step_five(n, facts)
    # The patches name what this chapter wrote, so they wait for it: printed on the first pass, a descriptor rewritten after them would slip past the audit.
    if not facts["done"]:
        print("  → once nothing above is left, run `tools/chapter/new.py --finalize` again: the audit comes with them")
        return 0
    chapter_md, labels = f"saves/C{n}/chapter.md", _ACCOUNT.get(lang, _ACCOUNT["en"])
    # Paths alone past the verb, so nothing but the verb need speak the chapter's tongue: each sheet says what follows its own name.
    written = f", saves/C{n}/chapter.json ({', '.join(facts['audited'])})" if facts["audited"] else ""
    auditors = sum(copies for _, copies in _AUDITORS)
    print(f"  → the audit: {auditors} sub-agents new to this chapter, at once, each handed its line below as it stands — nothing of your analysis nor notes")
    print("    docs/audit/ is theirs: never read it, you write for your reader, not the audit")
    for sheet, copies in _AUDITORS:
        many = f", {'twice' if copies == 2 else f'{copies} times'}, each on its own" if copies > 1 else ""
        target = chapter_md if sheet == "story" else chapter_md + written  # the story read takes the chapter alone: the chronicle is its ground
        print(f"    · {sheet}{many}: « {labels['read']} docs/audit/{sheet}.md — {target} »")
    for line in _AFTER_REPORTS:
        print(f"  → {line}")
    return 0


# The alerts whose law is on and whose condition holds.
def _fired_alerts(save: dict, realm: int | None) -> list[str]:
    laws = world_laws(save)
    standing = {code: spec for code, spec in _ALERTS.items() if laws.get(spec["law"], True)}  # the laws first: once both are off, neither world is walked at all
    if not standing:
        return []
    crowns, quota = _sapient_kingdoms(save), _kingdom_quota(save)
    pops, own = crowns.values(), (crowns.get(realm) if realm else None) or [0, 0]  # hoisted, and a view: no condition asks more than a length and a walk
    return [code for code, spec in standing.items() if spec["condition"](pops, quota, own)]


# WB's own log since `since`: crowns and favorites fallen with their killer, realms and towns raised or razed, wars, pacts. WB stamps a whole unit, hence `>=`.
def _journal_since(since: float | None) -> list[tuple]:
    try:
        with sqlite3.connect(f"file:{HISTORY_S3DB}?mode=ro", uri=True) as conn:
            return conn.execute(
                "SELECT timestamp, asset_id, special1, special2, special3, x, y FROM WorldLogMessage"
                " WHERE timestamp >= ? AND asset_id != 'auto_tester' ORDER BY timestamp, rowid",
                (int(since or 0),),
            ).fetchall()
    except sqlite3.Error:  # no copy yet, the live save having come without one: the recap goes on, a journal short
        return []


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
    spots = (json.loads(_PLACES_JSON.read_text()).get("places") or {}) if _PLACES_JSON.exists() else {}
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


# The recap's closing lines: the choice of a favorite before anything else, then step 3 with the commands and files it calls for, and step 4's bounds.
def _print_next_step(n: int, live: dict, favorite: dict | None) -> None:
    # No favorite while a thinking soul stands: the pick comes first, `favorite.py` erasing the chapter, prose and all, to rebuild it around the one chosen.
    thinking = index_by_id(live.get("subspecies") or [])
    if favorite is None and any(is_sapient(thinking.get(a.get("subspecies"))) for a in live.get("actors_data") or [] if not is_boat(a)):
        print("  → chronicler: choose a favorite before a single word (docs/chronicler.md § « Choix du favori »), then:")
        for line in _DESIGNATION:
            print(f"    · {line}")
        print("  → without one, step 3, the analysis, before the first word and not to be hurried:")
    else:
        print("  → chronicler: step 3, the analysis, before the first word and not to be hurried:")
    fav_id = ((favorite or {}).get("metadata") or {}).get("id")
    if n > 1:
        order = ", the favorite first, then circle by circle:" if fav_id else ","  # the chapter's own order, so the analysis lands already sorted by tier
        print(f"    · the deltas since C{n - 1}{order} what moved as much as what held — `geography bodies C{n}` shows a land newly peopled")
    print("    · the thresholds just crossed: the first times, the levels reached")
    if fav_id:
        print(f"    · who lives around the favorite: `actor {fav_id} surroundings C{n}`, each by its id: names repeat")
    if n > 1:
        print(f"    · the chapter before, reread: `saves/C{n - 1}/chapter.md`, and the open watches to settle or carry: `history/watches.md`")
    print(f"  → step 4, the writing: {_CHAPTER_FLOOR} to {_CHAPTER_CAP} characters, blanks folded, counted at delivery, past the audit")


# The recap's first half: where the world stands, what fired, and what the journal logged since the chapter before.
def _print_report(n: int, world_time: float, age_id: str, favorite: dict | None, regime: str, tags: list[str], prev_world: dict) -> None:
    age_label = (_AGE_LABELS.get(f"age_{age_id}") or {}).get("name") or age_id  # recap line only, the chapter carrying the id alone
    year = int(world_time / UNITS_PER_YEAR) + 1  # WB `Date.getYear`: the displayed year is 1-based, `getYear0` alone lags a year behind
    fav_name = ((favorite or {}).get("metadata") or {}).get("name")
    print(f"✓ C{n} — year {year}, {age_label}")
    print(f"  favorite: {fav_name or 'none'}{f' — {regime}' if regime else ''}")
    print(_RECAP_RULE)
    # A tag in `chapter.json` alone never reaches the chronicler. Alerts wait for `--deliver`, and `NEW_FAVORITE` is his own pick.
    if events := [code for code in tags if code not in _ALERTS and code != "NEW_FAVORITE"]:
        for code in events:
            print(f"  ⚑ {code}")
        print("  → each ⚑ is an event the chapter owes its reader, glossed in docs/tags.md")
        print(_RECAP_RULE)
    # The one source that names a killer, printed so a king's fall need not wait on the chronicler thinking to open the file. C1 has no « since »: the whole
    # past of a world taken up as it stood would pour out, and that is the s3db's to browse.
    journal = _journal_since(prev_world.get("world_time")) if n > 1 else []
    for timestamp, asset_id, *names, x, y in journal:
        print(f"  ✎ {' · '.join((f'year {timestamp // UNITS_PER_YEAR + 1}', asset_id, *filter(None, names)))} ({x},{y})")  # a meteorite names no one
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
                f" — {_DESCRIPTOR_CAP} characters at most"
            )
        elif carrying:
            print(
                f"  → `favorite.descriptor`, carried from C{n - 1}: « {text} » — nothing notable since, it may stand;"
                f" else rewrite it, {_DESCRIPTOR_CAP} characters at most"
            )
        elif len(text) > _DESCRIPTOR_CAP:
            print(f"  ✗ descriptor, {len(text)} characters of {_DESCRIPTOR_CAP}")
    if owed := facts["owed"]:
        reads = ", ".join(f"`{'actor' if tier == 'favorite' else tier} {entity} traits C{n}`" for tier, entity in owed.items())
        print(f"  → trait summaries owed ({', '.join(owed)}): one string each under the block's own `traits` key, read off {reads}")
        print(f"    what those traits make of the body, {_SUMMARY_CAP} characters at most; never a list, a tally of the traits or a figure that ages")
    if long := facts["long"]:
        print(f"  ✗ trait summaries, {', '.join(f'{tier} {size}' for tier, size in long.items())} characters of {_SUMMARY_CAP}")
    if sized:
        print("  → every length above counts spaces and markup too")
    if misplaced := facts["misplaced"]:
        for name, x, y, found, declared in misplaced:
            print(f"  ✗ places.json « {name} »: ({x},{y}) lies on {f'land {found}' if found else 'no counted land'}, its `island_id` saying {declared or 'none'}")
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
            world = (data.get("world") or {}).get("metadata") or {}
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
        if fav_id is None:  # the pick itself is the closing block's, printed only while a thinking soul is left to pick
            return "the favorite has left the world"
        return "successor to one who has left the world: open on that death before the tiers"
    return "yet to be designated" if fav_id is None else ""


# Zeroed by type rather than by name: WB adds counters between versions, and a hardcoded list would leave the new ones running. `id_*` restarts at 1, the rest at 0.
def _reset_counters(stats: dict) -> None:
    for key, value in stats.items():
        if key in _KEPT_STATS or isinstance(value, bool):  # `bool` subclasses `int`, so it has to be spared before the number test, not after
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

    landmarks = ", ".join(f"{count} {asset}" for asset, count in sorted(Counter(b["asset_id"] for b in save["buildings"]).items())) or "none"
    print(f"✓ world reset — year 1 of the Age of Hope, {stats['current_world_ages_duration'] / UNITS_PER_YEAR:.0f} years long")
    print(f"  map kept: {landmarks}")
    print(f"  named: {stats['name'] or '—'}")

    # WB re-pauses the ages on any year-1 load, so no flag set here holds; and it is saved, hence the wheel before the re-save — else a still world is archived.
    print("  → player, in this order: 1. reopen the save in WorldBox and press play on the age wheel — the reset leaves the ages paused, or the age never turns")
    print("                           2. save again — only the game redraws preview.png, and the chapter then archives a world whose ages run")
    print("  → chronicler: once he has done both, `tools/chapter/new.py --reset-asked` writes the first chapter, on the bare world as it stands")
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


# The headcount of each crown a thinking people answers to — a beast bows to none, a hull is no subject, and a soul under no banner raises no crown of its own.
def _sapient_kingdoms(save: dict) -> dict[int, list[int]]:
    subspecies_by_id = index_by_id(save.get("subspecies") or [])
    pops: dict[int, list[int]] = {}
    for actor in save.get("actors_data") or []:  # the crown first, being both the cheapest test and the one that turns most of a wild world away
        if (kid := actor.get("civ_kingdom_id")) and not is_boat(actor) and is_sapient(subspecies_by_id.get(actor.get("subspecies"))):
            pops.setdefault(kid, [0, 0])[actor.get("sex") or 0] += 1  # WB writes ♀ as `sex: 1` and omits ♂, so the field indexes its own tally
    return pops


# The chapter's folder and what surrounds it: the save, the history the chronicler browses, the world card, the C1 toponyms, the registries → a failed command.
def _scaffold(chapter: str, chapter_dir: Path, live_wbox: Path, live: dict) -> str | None:
    live_dir = live_wbox.parent
    for name in _LIVE_FILES:
        if (src := live_dir / name).exists():
            shutil.copy2(src, chapter_dir / name)
    if (s3db := live_dir / "map_stats.s3db").exists():
        shutil.copy2(s3db, HISTORY_S3DB)
    _write_world(live)
    if not _PLACES_JSON.exists():  # his toponyms, the lands and waters seeded by id — each already numbered, so only their names are left to forge
        if (surveyed := _run("geography/info.py", "islands,waters", chapter)) is None:  # seeded once and never again: an empty survey would stay empty
            return "geography/info.py islands,waters"
        seeded = {
            "islands": _unnamed(surveyed.get("islands") or []),
            "lakes": _unnamed((surveyed.get("waters") or {}).get("lakes") or []),
            "places": {},
        }
        _PLACES_JSON.write_text(render(seeded) + "\n")

    registries.ensure(chapter, live)  # `live` is handed over so it spares itself a re-parse of the save we already hold
    return None


# The reader's settings: the player's workshop switch and the chronicle's language. A missing or broken file reads as a player who never opened the panel.
def _settings() -> dict:
    try:
        return json.loads(_SETTINGS_JSON.read_text())
    except (OSError, ValueError):
        return {}


def _stands_alone(sexes: list[int]) -> bool:
    return min(sexes) >= _MIN_PER_SEX


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
    carried = bool(descriptor) and (before.get("metadata") or {}).get("id") == (favorite.get("metadata") or {}).get("id") and descriptor == before.get("descriptor")
    written = {tier: summary for tier in _TRAIT_SOURCES if isinstance(summary := (chapter.get(tier) or {}).get("traits"), str)}
    h1 = headings[0] if len(headings) == 1 and headings[0] != draft else None
    h1_length = len(_TAG.sub(lambda m: m[1] or "", h1 or ""))  # as read: a tag in the title shows its name alone, never its markup
    owed = {tier: _entity_id(chapter[tier]) for tier in sorted(_TRAIT_SOURCES) if chapter.get(tier) and tier not in written}
    long = {tier: len(summary) for tier, summary in sorted(written.items()) if len(summary) > _SUMMARY_CAP}
    misplaced = _misplaced_places(n)
    # A summary or a descriptor carried word for word was audited when it was written — only what this chapter wrote, or still owes, goes to the audit.
    fresh = [f"{tier}.traits" for tier in sorted(_TRAIT_SOURCES) if chapter.get(tier) and written.get(tier) != (prior.get(tier) or {}).get("traits")]
    return {
        "audited": sorted(fresh + (["favorite.descriptor"] if favorite and not carried else [])),
        "carried": carried,
        "descriptor": descriptor,
        "done": 0 < h1_length <= _H1_CAP and (not favorite or 0 < len(descriptor or "") <= _DESCRIPTOR_CAP) and not (owed or long or misplaced),
        "draft": draft,
        "favorite": bool(favorite),
        "h1": h1,
        "h1_length": h1_length,
        "length": len(re.sub(r"\s+", " ", prose).strip()),  # blanks folded, as the docs' budget counts: a blank line or an indent is no prose
        "long": long,
        "misplaced": misplaced,
        "owed": owed,
    }


# An entity's traits as the save spells them, id included so a change of clan reads like a change of traits — both mean the summary must be written afresh.
def _trait_fingerprint(save: dict, tier: str, entity_id: int | None) -> tuple | None:
    if entity_id is None:
        return None
    collection, fields = _TRAIT_SOURCES[tier]
    record = next((r for r in save.get(collection) or [] if r.get("id") == entity_id), None)
    return None if record is None else (entity_id, *(tuple(sorted(record.get(field) or [])) for field in fields))


# A surveyed feature stripped to what a toponym needs: where it lies, how big it is, and the two fields the chronicler fills when his tale reaches it.
def _unnamed(features: list[dict]) -> dict:
    return {str(f["id"]): {"centroid": f["centroid"], "chapter": "", "name": "", "size": f["size"]} for f in features}


def _value(argv: list[str], flag: str) -> str:
    return argv[i] if flag in argv and (i := argv.index(flag) + 1) < len(argv) else ""


# Every chapter in one file: what the nav prints beside a slug, and nothing else. Rewritten whole each time, so a chapter deleted by hand drops out on the next run.
def _write_index() -> None:
    entries = []
    for chapter_json in sorted(SAVES_DIR.glob("C*/chapter.json"), key=lambda f: int(f.parent.name[1:])):
        data = json.loads(chapter_json.read_text())
        entries.append(
            {
                "n": int(chapter_json.parent.name[1:]),
                "tags": data.get("tags") or [],
                "world_time": ((data.get("world") or {}).get("metadata") or {}).get("world_time", 0),
            }
        )
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

    # A world's name and blurb are set at its reset alone: accepted nowhere else, and staying mute on them would leave it bare while the run looked well.
    resetting = "--reset" in argv
    if not resetting and (lone := [flag for flag in ("--description", "--name") if flag in argv]):
        print(f"✗ {', '.join(lone)}: only with `--reset` — a world is named and described once, when it is reset", file=sys.stderr)
        return 2
    n = latest_chapter() + 1

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
    actors = live.get("actors_data") or []
    world_time = rounded_world_time(live["mapStats"])
    fav_id = next((a["id"] for a in actors if a.get("favorite") is True), None)
    prior = _prior_context(n)
    _, prev_favorite, prev_world, _ = prior
    prev_fav_id = ((prev_favorite or {}).get("metadata") or {}).get("id")
    # A favorite the chapter before did not carry — the world's first, or a successor to one who died. Both earn a chapter at an unchanged timestamp, and the tag.
    just_designated = fav_id is not None and fav_id != prev_fav_id

    # Read off the chapter before rather than by re-parsing its save for one field — `world/info.py` wrote it through the same `rounded_world_time`.
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
        tags = _chapter_tags(live, blocks, boat, favorite, just_designated, prior, age_id)

        # No `age_label`: the panel translates `world.metadata.age_id`. No `title` either: the H1 of `chapter.md` is the title, and nothing reads a copy of it.
        chapter_json = {
            **blocks,  # `render` sorts a record's keys, so the tiers need no place of their own here
            "boat": boat,
            "favorite": favorite,
            "tags": tags,
            "wars": wars,
            "world": world,
        }

        # `render`, not `json.dumps(indent=2)`: same tree, a quarter fewer characters once branches inline. No `_strip_none` — `tags: []` and a `null` city belong.
        (chapter_dir / "chapter.json").write_text(render(drop_chronicler_keys(chapter_json)) + "\n")
        settings = _settings()

        # The draft's H1, in the language the chronicler writes the chapter in: the reader has a page, and it reads unfinished.
        (chapter_dir / "chapter.md").write_text(f"# {_DRAFT_HEADINGS.get(settings.get('lang', ''), 'Draft')}\n")
        _write_index()

        _print_report(n, world_time, age_id, favorite, _regime(n, actors, fav_id, prev_fav_id), tags, prev_world)
        _print_next_step(n, live, favorite)
        return 0
    except BaseException as fault:  # a crash or a Ctrl-C halfway, which `_abandon` never sees: the half-built folder goes the same way, the fault still surfacing
        shutil.rmtree(chapter_dir, ignore_errors=True)
        if isinstance(fault, Exception):  # a Ctrl-C or an exit is no crash, and an exit has said its own ✗ already
            print("✗ new.py crashed — nothing written, report the traceback below", file=sys.stderr)
        raise


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
