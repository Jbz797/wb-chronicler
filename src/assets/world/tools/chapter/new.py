#!/usr/bin/env python3

# Bootstraps a new chapter from the live WorldBox save: archives it under `saves/C<n>/`, builds the registries (via `registries.py`) and a
# `chapter.json` skeleton. The chronicler then analyses (§III), writes `chapter.md`, and fills `title`, the favorite's `descriptor` and the trait summaries
# this run says are owed. Docs: `tools/tools.md`.

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

# What no panel reads, cut by the section holding it, never by name alone — a homonym elsewhere (`population.nobles`, a hull's `loot`) keeps the place a panel reads.
_AUDIT = {
    "army": frozenset({"captain_years", "total_captains"}),  # the corps' tenure and its roll of captains — the panel names the one in post, and only him
    "identity": frozenset({"founding_city", "founding_clan", "founding_kingdom", "motto", "name_culture", "name_template_set", "worldview"}),
    "metadata": frozenset(
        {
            "can_reproduce",
            "clan_chief_years",
            "deaths_by_cause",
            "favorite_food",
            "founding_city",
            "founding_kingdom",
            "gen",
            "home",
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
    "stats": frozenset({"birth_rate", "bonus_towers", "damage_range", "loot"}),
}

# No panel reads them: `report` is reworded per call, `taxonomy` derives from `identity.species`, `passengers` counts souls at sea, an age's pair is WB's English.
_CHRONICLER_ONLY = frozenset({"age_description", "age_name", "info", "passengers", "report", "taxonomy"})

# `population` keys no panel reads — the chronicler still gets them whole from `<tier>/info.py <id> population`, they simply don't ride along in the chapter.
_DEMOGRAPHY = frozenset({"adults", "babies", "children", "couples", "elders", "familyless", "gen_deepest", "gen_median", "happy", "men", "nobles", "teens", "women"})

_HISTORY_S3DB = SAVES_DIR.parent / "history" / "map_stats.s3db"  # cumulative WB SQLite → one copy, overwritten each chapter, for the chronicler to browse

# The podium rows a panel names, mirroring `LEADER_FAMILY_ROWS`/`LEADER_PERSON_ROWS` (`stats.constant.ts`). The rest stays in `<tier>/info.py <id> leaders`.
_LEADER_ROWS = {"families": frozenset({"population"}), "persons": frozenset({"kills", "level", "money", "oldest", "renown"})}

_LIVE_FILES = ("map.wbox", "preview.png")  # archived into the chapter dir under WB's own names; `map.wbox` alone regenerates everything for the chapter
_MIN_KINGDOM_POP = 4  # `DISABLE_HANDSOME_MIGRANTS` threshold — the headcount every playable species must reach in a kingdom of its own.
_PLACES_JSON = SAVES_DIR.parent / "history" / "places.json"  # the toponyms the chronicler coins — seeded with the world's isles at C1, his thereafter

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

_TIERS = ("city", "clan", "culture", "family", "kingdom", "language", "religion", "subspecies")  # the favorite's bodies, in chapter order; each is optional
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

_WORLD_JSON = SAVES_DIR.parent / "history" / "world.json"  # world identity {name, description} — scaffolded empty at C1, chronicler-owned thereafter


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
def _drop_chronicler_keys(node):
    if isinstance(node, dict):
        kept = {}
        for key, value in node.items():
            if key in _CHRONICLER_ONLY:
                continue
            if cut := _AUDIT.get(key):  # a section is a dict, save `relations`, which is a list of them
                if isinstance(value, dict):
                    value = _without(value, cut)
                elif isinstance(value, list):
                    value = [_without(item, cut) if isinstance(item, dict) else item for item in value]
            kept[key] = _drop_chronicler_keys(value)
        return kept
    return [_drop_chronicler_keys(value) for value in node] if isinstance(node, list) else node


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


# Keeps `opinion.top_drivers` on the ally/enemy ties only — a summary earns its place where it drives events. The `relations` section still gives the full ledger.
def _fold_kingdom_detail(kingdom: dict) -> None:
    for relation in kingdom.get("relations") or []:
        if relation.get("status") == "neutral":
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


# The manual's regime this chapter falls under. The script holds the state, so the chronicler need not read it off `chapter.json` to know which section governs.
def _regime(n: int, actors: list, fav_id: int | None, prev_fav_id: int | None) -> str:
    if n == 1:
        return "premier chapitre — cf. « Cas du premier chapitre du monde », dont le baptême à écrire dans `history/world.json`"
    if prev_fav_id is not None and not any(a.get("id") == prev_fav_id for a in actors):  # WB drops the dead from `actors_data`: an absent favorite is a dead one
        if fav_id is None:  # `favorite.py` n'est pas encore passé : le successeur reste à choisir
            return "le favori a quitté le monde — cf. « Mort du favori », puis « Choix du favori »"
        return "le favori a quitté le monde, son successeur est en place — cf. « Mort du favori » : le chapitre s'ouvre sur sa fin"
    if fav_id is None:
        return "aucun favori — cf. « Structure du chapitre (avant désignation d'un favori) » et « Choix du favori »"
    return "favori désigné — cf. « Structure du chapitre (favori désigné) »"


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


# An entity's traits as the save spells them, id included so a change of clan reads like a change of traits — both mean the summary must be written afresh.
def _trait_fingerprint(save: dict, tier: str, entity_id: int | None) -> tuple | None:
    if entity_id is None:
        return None
    collection, fields = _TRAIT_SOURCES[tier]
    record = next((r for r in save.get(collection) or [] if r.get("id") == entity_id), None)
    return None if record is None else (entity_id, *(tuple(sorted(record.get(field) or [])) for field in fields))


def _without(block: dict, cut: frozenset) -> dict:
    return {key: value for key, value in block.items() if key not in cut}


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
    prev_fav_id = ((prev_favorite or {}).get("metadata") or {}).get("id")
    # A favorite the chapter before did not carry — the world's first, or a successor to one who died. Both earn a chapter at an unchanged timestamp, and the tag.
    just_designated = fav_id is not None and fav_id != prev_fav_id

    # Read off the chapter before rather than by re-parsing its save for one field — `world/info.py` rounds it exactly as `world_time` above does, to the digit.
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
    if not _PLACES_JSON.exists():  # same for his toponyms, the isles seeded by id: WB numbers them, so the chronicler has only their names left to forge
        isles = ((_run("geography/info.py", "islands", chapter) or {}).get("islands")) or []
        seeded = {"islands": {str(i["id"]): {"centroid": i["centroid"], "chapter": "", "name": "", "size": i["size"]} for i in isles}, "places": {}}
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
        "boat": boat,
        "city": blocks["city"],
        "clan": blocks["clan"],
        "culture": blocks["culture"],
        "family": blocks["family"],
        "favorite": favorite,
        "kingdom": blocks["kingdom"],
        "language": blocks["language"],
        "religion": blocks["religion"],
        "subspecies": blocks["subspecies"],
        "tags": tags,
        "title": "",
        "world": world,
    }

    # `render`, not `json.dumps(indent=2)`: same tree, a good quarter fewer characters once branches inline. No `_strip_none` — `tags: []` and a `null` city belong.
    (chapter_dir / "chapter.json").write_text(render(_drop_chronicler_keys(chapter_json)) + "\n")

    year = int(world_time / UNITS_PER_YEAR) + 1  # WB `Date.getYear`: the displayed year is 1-based, `getYear0` alone lags a year behind
    counts = " · ".join(  # The chronicler's own order: the map first, then who fills it.
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
    print(f"  favori: {fav_name or 'aucun'}")
    print(f"  régime: {_regime(n, actors, fav_id, prev_fav_id)}")
    for _code, message in new_alerts:
        print(f"  ⚠ {message}")
    todo = "analyse §III · chapter.md"
    if favorite and not favorite.get("descriptor"):  # new favorite → its epithet is the one favorite field the chronicler still writes
        todo += " · descriptor du favori"
    if owed:
        todo += f" · résumés de traits ({', '.join(sorted(owed))})"
    if new_alerts:
        todo += " · relayer l'alerte"
    print(f"  → chroniqueur: {todo}")

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
