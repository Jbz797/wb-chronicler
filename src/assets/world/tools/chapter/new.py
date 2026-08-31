#!/usr/bin/env python3

# Bootstraps a new chapter from the live WorldBox save: archives it under `saves/C<n>/`, builds the registries (via `registries.py`) and a
# `chapter.json` skeleton. The chronicler then analyses (§III), writes `chapter.md`, and fills `title`, the favorite's `descriptor` and the trait summaries
# this run says are owed. Docs: `tools/tools.md`.

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
from shared import SAVES_DIR, UNITS_PER_YEAR, is_boat, latest_chapter, live_save, load_data, load_save, render, worldbox_running, write_save

_AGE_LABELS = load_data("world-ages.json")  # WB `WorldAgeLibrary` key → `{name, description}`; an unknown id falls back to the raw key.
_AGE_SLOTS = ("age_hope", *("age_unknown",) * 7)  # WB resolves them one at a time; a world always opens on the first

# World-law alerts, fired once ever (`chapter.json.tags` logs them). Adding one = an entry here + a row in `tags.md`; both args come from `_playable_kingdoms`.
_ALERTS = {
    "DISABLE_DROP_OF_THOUGHTS": {
        "condition": lambda kingdoms, present: all(kingdoms.get(species) for species in present),
        "message": "at the chapter's end, ask the player to turn the Drop of Thoughts world law off",
    },
    "DISABLE_HANDSOME_MIGRANTS": {
        "condition": lambda kingdoms, present: all(any(pop >= _MIN_KINGDOM_POP for pop in kingdoms.get(species, ())) for species in present),
        "message": "at the chapter's end, ask the player to turn the Handsome Migrants world law off",
    },
}

# What no panel reads, cut by its section and never by name alone — `nobles` and `loot` have homonyms; a `<tier>.<section>` key overrides the bare one.
_AUDIT = {
    "alliance.identity": frozenset({"founding_kingdom", "motto"}),  # the pact is read by its own name and its members, not by the crown that opened it
    "army": frozenset({"captain_years", "total_captains"}),  # the corps' tenure and its roll of captains — the panel names the one in post, and only him
    "identity": frozenset({"founding_city", "founding_clan", "founding_kingdom", "motto", "name_culture", "name_template_set", "worldview"}),
    "metadata": frozenset(
        {
            "alliance",  # the pact a realm or a soul answers to — the panel has a tier of its own for it, and the scripts still hand the ref over
            "besieged_by",
            "can_reproduce",
            "clan_chief_years",
            "deaths_by_cause",
            "favorite_food",
            "founding_city",
            "founding_kingdom",
            "gen",
            "home",
            "in_building",
            "island_id",
            "islands",
            "mass",
            "months_until_next_age",
            "motto",
            "peace_time",
            "tax_local",
            "tax_tribute",
            "traits",
            "x",
            "y",
        }
    ),
    "ranks": frozenset(
        {
            "army_captain_years",
            "army_kills_per_death",
            "births_per_death",
            "gold",
            "kills_per_capita",
            "kills_per_death",
            "king_money",
            "nobles",
            "nobles_money",
            "renown_per_capita",
            "traits",
        }
    ),
    "ranks_in_species": frozenset({"birth_rate", "loot"}),
    "relations": frozenset({"age_years", "borders"}),  # how long the tie has held and whether the two touch — the panel prints the standing and its drivers
    "stats": frozenset({"birth_rate", "bonus_towers", "damage_range", "loot", "max_cities"}),
}

# What a tier sheds on top of its bare section, united with it where the cut is read — the bare one stays the only truth a change has to touch.
_AUDIT_TIERS = {
    "alliance.metadata": {"cities", "kingdoms"},  # the pact names its realms and towns as tags, so counting either says nothing the list has not
    "alliance.ranks": {"cities", "kingdoms", "money", "renown_total"},  # among two pacts a podium says less still; `age` and `warriors` are printed
    "clan.ranks": {"kingdoms"},  # its crowns tie on one realm apiece — `clan/info.py <id> ranks` still places the band that spans eight
    "family.metadata": {"kingdoms"},  # a lineage spans two crowns too rarely for a panel row, so the count rides the script's output alone
    "family.ranks": {"cities"},  # towns follow the heads that hold them, so the podium repeats the one `members` already draws
}


# No panel reads them: `report` is reworded per call, `taxonomy` derives from `identity.species`, `passengers` counts souls at sea, an age's pair is WB's English.
_CHRONICLER_ONLY = frozenset({"age_description", "age_name", "info", "passengers", "report", "taxonomy"})

# `population` keys no panel reads — the chronicler still gets them whole from `<tier>/info.py <id> population`, they simply don't ride along in the chapter.
_DEMOGRAPHY = frozenset({"adults", "babies", "children", "couples", "elders", "familyless", "gen_deepest", "gen_median", "happy", "men", "nobles", "teens", "women"})

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

_GEO_ASSETS = re.compile(r"(volcano|geyser)", re.IGNORECASE)  # WB's three natural landmarks, `acid_geyser` included — all a bare world keeps of `buildings`
_HISTORY_S3DB = SAVES_DIR.parent / "history" / "map_stats.s3db"  # cumulative WB SQLite → one copy, overwritten each chapter, for the chronicler to browse
_KEPT_STATS = frozenset({"custom_data", "is_world_ages_paused"})  # a dict and a player preference, both of which a numeric sweep would flatten

# The podium rows a panel names, mirroring `LEADER_FAMILY_ROWS`/`LEADER_PERSON_ROWS` (`stats.constant.ts`). The rest stays in `<tier>/info.py <id> leaders`.
_LEADER_ROWS = {"families": frozenset({"population"}), "persons": frozenset({"kills", "level", "money", "oldest", "renown"})}

_LIVE_FILES = ("map.wbox", "preview.png")  # archived into the chapter dir under WB's own names; `map.wbox` alone regenerates everything for the chapter
_LONG_AGE_YEARS = (35, 55)  # WB draws an age's span when it opens; only the two bleak ones run shorter
_MIN_KINGDOM_POP = 4  # `DISABLE_HANDSOME_MIGRANTS` threshold — the headcount every playable species must reach in a kingdom of its own.
_PLACES_JSON = SAVES_DIR.parent / "history" / "places.json"  # the toponyms the chronicler coins — seeded with the world's isles at C1, his thereafter

# Put to the player at the first chapter, before a line is written. The three commands answer it, and the naming brief rides with the third.
_RESET_PROMPT = """? first chapter — nothing is written until the player has answered. Put this to him, in one go:
  « Do you want to start over from a bare map — relief, biomes, volcanoes and geysers kept, everything else erased (creatures, buildings, kingdoms…),
    back to year 1 of the Age of Hope with a new genetic seed? And if so, shall I name it too? »
  → no: `tools/chapter/new.py --reset-asked`
  → reset alone: `tools/chapter/new.py --reset`, and the world keeps the name and description it carries
  → reset and naming: `tools/chapter/new.py --reset --name "…" --description "…"`
  the name is forged after a survey of the bare map, its geography being all that survives it: Tolkien-flavoured without pastiche, on the ground,
  the mood or whatever outlasts the ages, never the age itself. Yours alone to choose — his yes was the agreement."""

_SHORT_AGES = frozenset({"age_despair", "age_ice"})
_SHORT_AGE_YEARS = (30, 40)

# Rosters, libraries and fleets kept as a count alone — the tier's own `info.py <id> <section>` still names every soul, volume and hull behind the figure.
_TALLIES = {
    "clan": ("members",),
    "culture": ("books", "members"),
    "family": ("members",),
    "kingdom": ("boats",),
    "language": ("books", "members"),
    "religion": ("books", "members"),
    "subspecies": ("members",),
}

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

# The counters « Activité récente » prints, mirroring `CUMULATIVE_STATS` (`stats.constant.ts`), `deaths` riding along for the breakdown panel below it.
_UI_CUMULATIVE = frozenset({"books_burnt", "books_read", "cities_conquered", "cities_rebelled", "deaths", "evolutions", "metamorphosis", "plots_succeeded"})

_WORLD_JSON = SAVES_DIR.parent / "history" / "world.json"  # world identity {name, description}, mirrored off the save each chapter — what the reader displays


# The bare world's own age, drawn as WB draws it — the span is random, so two resets of the same map never run to the same calendar.
def _age_duration(age_id: str) -> float:
    low, high = _SHORT_AGE_YEARS if age_id in _SHORT_AGES else _LONG_AGE_YEARS
    return float(random.randint(low, high) * UNITS_PER_YEAR)


# The whole rewind, in the order WB's fields depend on one another: survivors first, `id_building` counting from them. Of `buildings`, only landmarks stand.
def _bare_world(save: dict, name: str, description: str) -> None:
    save["buildings"] = [b for b in save.get("buildings") or [] if _GEO_ASSETS.search(b.get("asset_id") or "")]
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


# Carries last chapter's trait summaries over wherever neither the entity nor its traits moved, and names those still owed — as `descriptor` is already carried.
def _carry_trait_summaries(n: int, blocks: dict, live: dict) -> list[str]:
    prior_dir = SAVES_DIR / f"C{n - 1}"
    prior = json.loads(path.read_text()) if (path := prior_dir / "chapter.json").exists() else {}
    # A chapter from before the summaries holds a tally there, which is no summary to carry. The save behind it is parsed only to date what is worth carrying.
    written = {tier: text.strip() for tier in blocks if isinstance(text := (prior.get(tier) or {}).get("traits"), str) and text.strip()}
    prior_save = load_save(wbox) if written and (wbox := prior_dir / "map.wbox").exists() else {}
    owed = []
    for tier, block in blocks.items():
        if not block:
            continue
        # Both saves are walked only where a summary stands to be carried — an owed tier is owed whether or not its traits moved.
        if tier in written and _trait_fingerprint(live, tier, _entity_id(block)) == _trait_fingerprint(prior_save, tier, _entity_id(prior.get(tier) or {})):
            block["traits"] = written[tier]  # same entity, same traits: what the chronicler wrote still holds
        else:
            owed.append(tier)
    return owed


# `_CHRONICLER_ONLY` cuts at every depth of the tree, `_AUDIT` from one named section alone — neither loses the chronicler a thing, `<tier>/info.py` replaying both.
def _drop_chronicler_keys(node, parent: str = ""):
    if isinstance(node, dict):
        kept = {}
        for key, value in node.items():
            if key in _CHRONICLER_ONLY:
                continue
            if cut := _AUDIT.get(key, frozenset()) | _AUDIT_TIERS.get(f"{parent}.{key}", frozenset()):  # a section is a dict, save `relations`, a list of them
                if isinstance(value, dict):
                    value = _without(value, cut)
                elif isinstance(value, list):
                    value = [_without(item, cut) if isinstance(item, dict) else item for item in value]
            kept[key] = _drop_chronicler_keys(value, key)
        return kept
    return [_drop_chronicler_keys(value, parent) for value in node] if isinstance(node, list) else node


def _entity_id(block: dict) -> int | None:
    return (block.get("metadata") or {}).get("id")


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


# The panel prints the hull's name, stock, crown, port, age and health; `boat/info.py <id>` has the rest. `kind` goes: WB boards souls onto `$boat_transport$` alone.
def _fold_boat_detail(boat: dict) -> None:
    (boat.get("identity") or {}).pop("kind", None)
    for section in ("combat", "traits"):
        boat.pop(section, None)  # a hull's merits — `kingslayer`, `veteran` — narrate well and print nowhere
    metadata = boat.get("metadata") or {}
    for key in ("kills", "level", "loot", "mass_kg", "renown", "speed"):  # `home`, `x` and `y` go with `_AUDIT`, which takes them from every `metadata`
        metadata.pop(key, None)


# Drops the loyalty summary and both stock lists, keeping their `total` — the panels print that alone, the sections still itemising each modifier and piece.
def _fold_city_detail(city: dict) -> None:
    (city.get("loyalty") or {}).pop("top_drivers", None)
    _fold_total(city, "books", "equipment")


# Cut to what « Activité récente » charts — WB tallies a good deal more, and `world/info.py <chapter> cumulative` still hands the chronicler every one of them.
def _fold_cumulative(world: dict) -> None:
    if isinstance(block := world.get("cumulative"), dict):
        world["cumulative"] = {key: value for key, value in block.items() if key in _UI_CUMULATIVE}


# Folds the favorite's heavy blocks: his traits, his gear and the scheme's detail all go — `actor/info.py <id>` still hands the chronicler each one whole.
def _fold_favorite_detail(favorite: dict) -> None:
    favorite.pop("equipment", None)
    # The panel prints the type, the target and the gauge: WB's English is the chronicler's, and so is how long the scheme has run.
    plot = favorite.get("plot") or {}
    plot.pop("months", None)
    if kind := plot.get("type"):
        plot["type"] = {"id": kind.get("id")}
    favorite.pop("traits", None)  # the chronicler's summary takes its place, carried over or owed


# Drops every `opinion.top_drivers`: the table prints the standing alone, and `kingdom/info.py <id> relations` still gives the chronicler the whole ledger.
def _fold_kingdom_detail(kingdom: dict) -> None:
    for relation in kingdom.get("relations") or []:
        (relation.get("opinion") or {}).pop("top_drivers", None)
    _fold_total(kingdom, "equipment")


# A tier's podium cut to the six rows its panel names — each rank being a full `{id, name}` ref, the ones it never prints outweigh the ones it does.
def _fold_leaders(entity: dict) -> None:
    podium = entity.get("leaders") or {}
    for block, kept in _LEADER_ROWS.items():
        if isinstance(rows := podium.get(block), dict):
            podium[block] = {key: ref for key, ref in rows.items() if key in kept}


# The age and sex slices, the lineage depth, the count of nobles — figures the chronicler writes with and no panel prints. `population` keeps what the UI reads.
def _fold_population(entity: dict) -> None:
    if isinstance(block := entity.get("population"), dict):
        entity["population"] = {k: v for k, v in block.items() if k not in _DEMOGRAPHY}


# `stats` goes here rather than through `_CHRONICLER_ONLY`, which would take the favorite's own block along with it.
def _fold_subspecies_detail(subspecies: dict) -> None:
    subspecies.pop("stats", None)
    (subspecies.get("species") or {}).pop("description", None)  # WB's blurb on the parent stock — narrative, and the panel never prints it


# The panels read nothing but the `total`, whichever form `full` handed over — nothing is lost, the chapter's own `map.wbox` replaying any section.
def _fold_total(entity: dict, *keys: str) -> None:
    for key in keys:
        if isinstance(block := entity.get(key), dict):
            entity[key] = {"total": block.get("total", 0)}


# WB's `life_dna` seeds a world's genetics, redrawn on the hour so a reused map never repopulates with the lineages before it. WB's format: `YYYYMMDDHH`, UTC.
def _life_dna() -> int:
    return int(datetime.now(timezone.utc).strftime("%Y%m%d%H"))


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


# Empties a world's own chronicle, table by table, leaving the schema WB expects. `VACUUM` hands the megabytes back rather than leaving a hollow file.
def _purge_history(s3db: Path) -> int:
    if not s3db.exists():
        return 0
    s3db.chmod(0o644)  # WB leaves it read-only often enough that a bare `connect` would fail
    with sqlite3.connect(s3db) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        purged = 0
        for (table,) in cursor.fetchall():
            cursor.execute(f'DELETE FROM "{table}"')  # interpolated, but the name comes from the file's own schema a line above
            purged += cursor.rowcount
        conn.commit()
        cursor.execute("VACUUM")
    return purged


# The regime this chapter falls under, so the chronicler need not deduce it — a favorite gone from `actors_data` is a dead one, and nothing else says so.
def _regime(n: int, actors: list, fav_id: int | None, prev_fav_id: int | None) -> str:
    if n == 1:
        return "first chapter"
    if prev_fav_id is not None and not any(a.get("id") == prev_fav_id for a in actors):  # WB drops the dead from `actors_data`: an absent favorite is a dead one
        if fav_id is None:  # `favorite.py` has not run yet: the successor is still to be picked
            return "the favorite has left the world — pick a successor, get the player's word, then `tools/chapter/favorite.py <id>`"
        return "the favorite has left the world, his successor is in place — open on that death before the tiers, then follow the successor's eyes from here on"
    if fav_id is None:
        return "no favorite yet"
    return "favorite designated"


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
    _write_world(stats)  # off the save, not off the arguments: a world that kept its name keeps it here too
    purged = _purge_history(live_wbox.parent / "map_stats.s3db")
    (live_wbox.parent / "map.meta").unlink(missing_ok=True)  # WB rebuilds it from the save on opening; writing it ourselves would guess at a format we only read

    landmarks = ", ".join(f"{count} {asset}" for asset, count in sorted(Counter(b["asset_id"] for b in save["buildings"]).items())) or "none"
    print(f"✓ world reset — year 1 of the Age of Hope, {stats['current_world_ages_duration'] / UNITS_PER_YEAR:.0f} years long, life_dna {stats['life_dna']}")
    print(f"  map kept: {landmarks} · {purged} history rows purged · map.meta dropped, WorldBox rebuilds it")
    print(f"  named: {stats['name'] or '—'}")
    # WB pauses them itself on loading a world set back to year 1, whatever the save says — writing the flag here would not survive the next open.
    print("  ⚠ the world ages come back paused: the play button on the age wheel, or the Era never turns")
    print("  → player: reopen this save in WorldBox and save it again — only the game redraws preview.png, and every chapter archives it")
    print("  then `tools/chapter/new.py --reset-asked` writes the first chapter, on the bare world as it stands")
    return 0


# Runs a sibling `info.py` → its parsed JSON stdout, `None` (stderr surfaced) on failure or empty output. `sys.executable` so a venv never forks children elsewhere.
def _run(rel_path: str, *args) -> dict | None:
    result = subprocess.run([sys.executable, str(_TOOLS / rel_path), *map(str, args)], capture_output=True, text=True, check=False)
    if result.returncode:
        print(f"  ⚠ tools/{rel_path} {' '.join(map(str, args))}: {result.stderr.strip()[:200]}", file=sys.stderr)
        return None
    return json.loads(result.stdout) if result.stdout.strip() else None


# Runs `(callable, *args)` tuples at once, results in order (`None` call → `None`) — each `info.py` re-parses the whole save and only reads, so overlap is free.
def _run_together(*calls: tuple | None) -> list:
    with ThreadPoolExecutor(max_workers=max(len(calls), 1)) as pool:
        jobs = [pool.submit(*call) if call else None for call in calls]
    return [job.result() if job else None for job in jobs]


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
    return argv[argv.index(flag) + 1] if flag in argv and argv.index(flag) + 1 < len(argv) else ""


def _without(block: dict, cut: frozenset) -> dict:
    return {key: value for key, value in block.items() if key not in cut}


# The world's name and blurb as WB spells them, rewritten every chapter rather than seeded once: a rename, in game or by `--reset`, reaches the reader on its own.
def _write_world(stats: dict) -> None:
    _WORLD_JSON.write_text(json.dumps({"description": stats.get("description") or "", "name": stats.get("name") or ""}, ensure_ascii=False, indent=2) + "\n")


def main(argv: list[str]) -> int:
    live_wbox = live_save()
    if not live_wbox.exists():
        print(f"✗ no live save at {live_wbox} — ask the player to update the path, from the settings cog under the map", file=sys.stderr)
        return 2
    n = latest_chapter() + 1
    chapter, chapter_dir = f"C{n}", SAVES_DIR / f"C{n}"
    if chapter_dir.exists():  # a directory would have raised `latest_chapter` and carried `n` past it: only a file, or a broken link, can stand in its place
        print(f"✗ {chapter_dir} exists but is not a chapter directory — remove it, then run again", file=sys.stderr)
        return 1
    if "--reset" in argv:  # the player said yes, and only he can: nothing but this flag ever reaches the branch below
        if n > 1:  # `n` already counted the chapters a moment ago, and a chronicle past its first cannot afford the world it tells of being unmade
            print("✗ the chronicle has begun — a reset erases the world its chapters tell of, and only one not yet started can afford that", file=sys.stderr)
            return 1
        return _reset_world(live_wbox, _value(argv, "--name"), _value(argv, "--description"))
    if n == 1 and "--reset-asked" not in argv:  # a reset would throw away whatever is written here, so nothing is, until the player has had his say
        print(_RESET_PROMPT)
        return 0

    live = load_save(live_wbox)
    actors = live.get("actors_data") or []
    world_time = round(float(live["mapStats"].get("world_time", 0)), 2)
    fav_id = next((a["id"] for a in actors if a.get("favorite") is True), None)
    already, prev_favorite, prev_world = _prior_context(n)
    prev_fav_id = ((prev_favorite or {}).get("metadata") or {}).get("id")
    # A favorite the chapter before did not carry — the world's first, or a successor to one who died. Both earn a chapter at an unchanged timestamp, and the tag.
    just_designated = fav_id is not None and fav_id != prev_fav_id

    # Read off the chapter before rather than by re-parsing its save for one field — `world/info.py` rounds it exactly as `world_time` above does, to the digit.
    if (prev_time := prev_world.get("world_time")) is not None and world_time <= prev_time and not just_designated and "--force" not in argv:
        print(
            f"✗ save not advanced (world_time {world_time} ≤ C{n - 1} {prev_time}), and no new favorite either — ask the player to play on, then save again",
            file=sys.stderr,
        )
        return 1

    chapter_dir.mkdir(parents=True)
    live_dir = live_wbox.parent
    for name in _LIVE_FILES:
        if (src := live_dir / name).exists():
            shutil.copy2(src, chapter_dir / name)
    if (s3db := live_dir / "map_stats.s3db").exists():
        shutil.copy2(s3db, _HISTORY_S3DB)
    _write_world(live["mapStats"])
    if not _PLACES_JSON.exists():  # his toponyms, the lands and waters seeded by id — each already numbered, so only their names are left to forge
        surveyed = _run("geography/info.py", "islands,waters", chapter) or {}
        seeded = {
            "islands": _unnamed(surveyed.get("islands") or []),
            "lakes": _unnamed((surveyed.get("waters") or {}).get("lakes") or []),
            "places": {},
        }
        _PLACES_JSON.write_text(render(seeded) + "\n")

    registries.ensure(chapter, live)  # `live` is handed over so it spares itself a re-parse of the save we already hold

    # Two waves rather than a call per tier: the favorite's metadata names the bodies it belongs to, so none of those can start until it has landed.
    world, favorite = _run_together(
        (_run, "world/info.py", chapter),
        (_featured_favorite, chapter, fav_id, prev_favorite) if fav_id is not None else None,
    )

    if world is None:
        print("✗ world/info.py failed — check the save", file=sys.stderr)
        return 1

    blocks: dict = dict.fromkeys(_TIERS)  # `None` where the favorite belongs to no such body — the chapter carries the key either way
    boat = None
    if favorite:
        meta = favorite.get("metadata") or {}
        calls = [(_run, f"{tier}/info.py", tid, "full", chapter) if (tid := (meta.get(tier) or {}).get("id")) else None for tier in _TIERS]
        # The hull rides the same wave, `transport` being a ref like the tiers. Popped, not read: the `boat` block replaces it, `actor/info.py <id>` keeping the ref.
        boat_id = (meta.pop("transport", None) or {}).get("id")
        calls.append((_run, "boat/info.py", boat_id, "full", chapter) if boat_id else None)
        *bodies, boat = _run_together(*calls)
        blocks = dict(zip(_TIERS, bodies))
        folds = {"city": _fold_city_detail, "kingdom": _fold_kingdom_detail, "subspecies": _fold_subspecies_detail}  # on top of what every tier sheds alike
        for tier, block in blocks.items():
            if not block:
                continue
            _fold_leaders(block)
            _fold_population(block)
            block.pop("traits", None)  # the raw list goes; `_carry_trait_summaries` writes the chronicler's prose in its place
            if fold := folds.get(tier):
                fold(block)
            if keys := _TALLIES.get(tier):
                _fold_total(block, *keys)
        if boat:
            _fold_boat_detail(boat)
            _fold_total(boat, "crew")  # the panel prints how many souls are aboard, `boat/info.py <id> crew` names them

    # A third wave, and the only one a tier opens: the crown names its wars, each of which answers for itself — neither camp being `ours` from up here.
    wars = [w for w in ((blocks.get("kingdom") or {}).get("wars") or []) if w.get("id") is not None]
    if wars:
        fought = _run_together(*((_run, "war/info.py", w["id"], "full", chapter) for w in wars))
        wars = [war for war in fought if war]

    summaries = {tier: favorite if tier == "favorite" else blocks[tier] for tier in _TRAIT_SOURCES}  # a tier is summarised the day it gains a trait source
    owed = _carry_trait_summaries(n, summaries, live)

    _fold_cumulative(world)
    _fold_total(world, "boats")  # Counted, never listed: both panels print the count alone, `<tier>/info.py … boats` naming the hulls on demand.
    for scheme in world.get("plots") or []:  # the schemer and the type's key: WB's English is the chronicler's, and the panel owns the French
        scheme["type"] = {"id": (scheme.get("type") or {}).get("id")}

    age_id = (live["mapStats"].get("world_age_id") or "").removeprefix("age_")  # short form, as `world/info.py` emits it — `prev_world` carries that one
    # Mechanical event codes — `chapter.json.tags` is their single source of truth, no separate log.
    tags = ["NEW_FAVORITE"] if just_designated else []
    if (prev_age_id := prev_world.get("age_id")) and age_id != prev_age_id:
        tags.append("NEW_AGE")

    # First hull ever afloat — WB's boat techs leave no trace in the save, so the boat itself is the discovery. One-time, like the `DISABLE_*` alerts.
    if "NAVIGATION" not in already and any(is_boat(a) for a in actors):
        tags.append("NAVIGATION")
    if boat:  # a chapter caught at sea — the favorite is aboard right now, which the panel badges and the chronicler owes a scene
        tags.append("FAVORITE_ABOARD")
    # A scheme afoot under the favorite's own hand. Read after the fold, which leaves the type's key behind: a plot ripens in months, so it may be gone next chapter.
    if (favorite or {}).get("plot"):
        tags.append("FAVORITE_PLOTTING")
    new_alerts = _fired_alerts(live, already)
    tags += [code for code, _message in new_alerts]

    age_label = (_AGE_LABELS.get(f"age_{age_id}") or {}).get("name") or age_id  # recap line only, the chapter carrying the id alone

    # No `age_label`: the panel translates `world.metadata.age_id`. `title` stays empty — the chronicler writes it post-audit; everything else is script-generated.
    chapter_json = {
        **blocks,  # `render` sorts a record's keys, so the eight tiers need no place of their own here
        "boat": boat,
        "favorite": favorite,
        "tags": tags,
        "wars": wars,
        "title": "",
        "world": world,
    }

    # `render`, not `json.dumps(indent=2)`: same tree, a good quarter fewer characters once branches inline. No `_strip_none` — `tags: []` and a `null` city belong.
    (chapter_dir / "chapter.json").write_text(render(_drop_chronicler_keys(chapter_json)) + "\n")

    year = int(world_time / UNITS_PER_YEAR) + 1  # WB `Date.getYear`: the displayed year is 1-based, `getYear0` alone lags a year behind
    counts = " · ".join(  # The chronicler's own order: the map first, then who fills it.
        f"{len(json.loads((chapter_dir / f'{name}.json').read_text()))} {name}" for name in ("cities", "kingdoms", "clans", "families", "subspecies", "persons")
    )
    fav_name = ((favorite or {}).get("metadata") or {}).get("name")
    print(f"✓ {chapter} — year {year}, {age_label} (world_time {world_time})")
    print(f"  registries: {counts}")
    print(f"  favorite: {fav_name or 'none'}")
    print(f"  regime: {_regime(n, actors, fav_id, prev_fav_id)}")
    for _code, message in new_alerts:
        print(f"  ⚠ {message}")
    todo = "analysis §III · chapter.md"
    if favorite and not favorite.get("descriptor"):  # new favorite → its epithet is the one favorite field the chronicler still writes
        todo += " · the favorite's descriptor"
    if owed:
        todo += f" · trait summaries ({', '.join(sorted(owed))})"
    print(f"  → chronicler: {todo}")

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
