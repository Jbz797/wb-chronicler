#!/usr/bin/env python3

# WB's own history, `history/map_stats.s3db`, read so that no one queries it raw: windows joined, blanks carried, tallies told as each year's gains, dates compact.
# User-facing docs: `docs/tools.md`.

import re
import sqlite3
import sys
from collections import Counter, defaultdict
from contextlib import closing
from pathlib import Path
lazy from collections.abc import Mapping

sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))

from shared import (
    HISTORY_S3DB,
    SAVES_DIR,
    UNITS_PER_YEAR,
    absent_entity,
    alive_or_dead_ref,
    arg_parser,
    crowns_named,
    emit,
    entity_born,
    entity_ref,
    index_by_id,
    kept_deaths,
    latest_chapter,
    limit_arg,
    load_data,
    load_save,
    log_entries,
    pickle_cached,
    quiet_zeros,
    reigns,
    run,
    take_chapter,
    take_since,
    world_date,
)

_DEATHS_TOTAL = "deaths_total"  # WB's yearly total, which the causes fall short of where a death was filed under none
_DEATH_CAUSE = re.compile(r"^deaths_(?!attackers$|defenders$|total$)(\w+)$")  # a death's cause, where `natural` is WB's old age — a war's two sides are no cause

# Tool kind => (WB table stem, save collection): the collection finds the living, whom alone WB keeps the years of.
_ENTITIES = {
    "alliance": ("Alliance", "alliances"),
    "army": ("Army", "armies"),
    "city": ("City", "cities"),
    "clan": ("Clan", "clans"),
    "culture": ("Culture", "cultures"),
    "family": ("Family", "families"),
    "kingdom": ("Kingdom", "kingdoms"),
    "language": ("Language", "languages"),
    "religion": ("Religion", "religions"),
    "subspecies": ("Subspecies", "subspecies"),
    "war": ("War", "wars"),
}

_ENTITY_RENAMED = {"population": "pop"}  # WB's column under the name every tier's section tells it by

# A column that only rises, an event's tally — where a bare noun (`pop`, `cities`) is a state, and a year's value is the state it closed on.
_EVENT_COLUMN = re.compile(
    r"^(births|deaths(_\w+)?|evolutions|joined|kills|left|metamorphosis|migrated|moved|speakers_\w+)$"
    r"|_(born|built|burnt|conquered|created|destroyed|dissolved|extinct|forgotten|made|read|rebelled|started|succeeded|written)$"
)

_FINE_STEP = 1  # WB's yearly table: a row a year, the only one whose `timestamp` is a year — every coarser one averages its span or keeps its last year

# What a body founds and the save keeps, by its record's founder id, name and birth town — a crown's founder its first ruler, a town's town none but itself.
_FOUNDED = {
    "cities": ("founder_id", "founder_name", None),
    "clans": ("founder_actor_id", "founder_actor_name", "founder_city_id"),
    "cultures": ("creator_id", "creator_name", "creator_city_id"),
    "families": ("main_founder_id_1", "founder_actor_name_1", "founder_city_id"),
    "kingdoms": (None, None, None),
    "languages": ("creator_id", "creator_name", "creator_city_id"),
    "religions": ("creator_id", "creator_name", "creator_city_id"),
}

_LIMIT = 10  # the lines each block of `founded` gives unless `--limit` says otherwise: the latest, the cut told beside
_MAX_LOG = 50  # past so many entries the journal is read by its kinds of event, not line by line: `-t` or `--actor` narrow it back
_REIGN_EDGES = {"king_dead": "to", "king_killed": "to", "king_left": "to", "king_new": "from"}  # the log's ends of a reign, a flight none

# WB's `world_statistics_beasts` walks every unit, the dying and the hulls with it, where `Actor.die` counts a death at the blow and none for a metamorphosis.
_ROLL = ("population_beasts", "population_civ")  # the two columns a year's bodies stand in
_ROLL_TERMS = {"creatures_born": 1, "creatures_created": 1, _DEATHS_TOTAL: -1}  # and what moves them, by its sign

_RULED = {"army": "past_captains", "city": "past_rulers", "kingdom": "past_rulers"}  # the seats `rulers` follows, by the succession WB keeps of each
_SECTIONS = ("dead_kingdoms", "entity", "founded", "log", "rulers", "world")
_SKIPPED = frozenset({"auto", "id", "timestamp"})  # WB's row bookkeeping: `auto` flags a row it wrote itself, and says nothing of the world
_STAT_KEYS = {"deaths_natural": "deaths_age", _DEATHS_TOTAL: "deaths"}  # the yearly columns `mapStats` names otherwise: old age, and the bare total
_STEPS = (1, 5, 10, 50, 100, 500, 1000, 5000, 10000)  # WB's table suffixes, each keeping a window of the last rows at that step

# WB's columns under the names `world`'s own sections tell them by: its houses are all its buildings, its two populations the thinking and the wild.
_WORLD_RENAMED = {
    "houses": "buildings",
    "houses_built": "buildings_built",
    "houses_destroyed": "buildings_destroyed",
    "population_beasts": "wild_creatures",
    "population_civ": "sapient_pop",
}

# What a year's row closed on, as `world … snapshot` tells today's — WB's fifty-odd counts of tiles and biomes are left out.
_WORLD_STATES = (
    "alliances",
    "books",
    "cities",
    "clans",
    "cultures",
    "families",
    "houses",
    "infected",
    "kingdoms",
    "languages",
    "plots",
    "population_beasts",
    "population_civ",
    "religions",
    "subspecies",
    "trees",
    "vegetation",
    "wars",
)


# WB's fallen crowns with their dates, who passed through them and how they died, and the reigns the log names — all a crown keeps once its years are gone.
def _build_dead_kingdoms(conn: sqlite3.Connection, save: dict) -> list[dict]:
    now = _chapter_time(save)
    found = conn.execute("SELECT * FROM KingdomData WHERE died_time IS NOT NULL AND died_time <= ? ORDER BY died_time", (now,))
    columns = [c for c, *_ in found.description]
    crowns = [dict(zip(columns, row, strict=True)) for row in found.fetchall()]
    fallen, reigns = {c["id"] for c in crowns}, defaultdict(list)
    for entry in log_entries(0.0, now, deaths=True) if crowns else ():
        if entry["event"].startswith("king_") and entry["kingdom_id"] in fallen:
            reigns[entry["kingdom_id"]].append(_king_entry(entry))
    out = []
    for crown in crowns:
        deaths = {"old_age" if m[1] == "natural" else m[1]: n for c, n in crown.items() if (m := _DEATH_CAUSE.match(c)) and n}
        if (unknown := (crown["total_deaths"] or 0) - (crown["metamorphosis"] or 0) - sum(deaths.values())) > 0:
            deaths["unknown"] = unknown
        tallies = {key: crown[key] or 0 for key in ("joined", "left", "migrated", "moved")}
        out.append(
            {
                **quiet_zeros(tallies),
                "asset_id": crown["original_actor_asset"],
                "births": crown["total_births"],
                "deaths": deaths or None,
                "fell": world_date(crown["died_time"]),
                "founded": world_date(crown["created_time"] or 0),
                "id": crown["id"],
                "kills": crown["total_kills"],
                "name": crown["name"],
                "reigns": reigns.get(crown["id"]),
            }
        )
    return out


# One entity's years: its states as they closed each year, and what its tallies gained in it; older years, coarse, their states alone and never as a date.
def _build_entity(conn: sqlite3.Connection, kind: str, entity_id: int, save: dict, chapter: str | None) -> list[dict] | str:
    stem, collection = _ENTITIES[kind]
    closed = _closed_year(save)
    columns, coarse, rows = _series(conn, stem, entity_id, closed + 1)
    living = next((e for e in save.get(collection) or [] if e.get("id") == entity_id), None)
    if not rows and not coarse:
        # The base is the latest chapter's, where WB has dropped the years of what ended since: alive in an earlier one, it is judged by the last.
        last = f"C{latest_chapter()}"
        earlier = living is not None and chapter not in (None, last)  # the save in hand is the latest otherwise, and is not read twice
        ended = earlier and all(e.get("id") != entity_id for e in load_save(SAVES_DIR / last / "map.wbox").get(collection) or [])
        if living is not None and not ended:
            return f"✗ {kind} {entity_id} has no year closed yet: a year's row is written as the next one opens"
        refusal = absent_entity(kind, collection, entity_id, last if ended else chapter)
        return f"{refusal} — WB keeps the years of the living alone" if " is gone " in refusal else refusal
    events = [c for c in columns if _EVENT_COLUMN.search(c)]
    # A gain at nought is unsaid on its year, as every count: the tallies this kind keeps, said once, let a silence read as none gained, not as none kept.
    if tallies := sorted({"deaths" if _DEATH_CAUSE.match(c) else _WORLD_RENAMED.get(c, c) for c in events}):
        print(f"· {kind} tallies: {', '.join(tallies)} — one unsaid on a year gained none", file=sys.stderr)
    states = [c for c in columns if c not in events and any(r[c] for r in (*coarse, *rows))]  # a state at nought all along says nothing
    names = {c: _ENTITY_RENAMED.get(c, c) for c in states}
    born = _row_year(float(living["created_time"])) if living and living.get("created_time") is not None else None
    # WB's triggers average a span's states and keep a tally's highest, its value at the close: told as gains on the span before, the first since birth.
    older, before = [], dict.fromkeys(events, 0)
    for r in coarse:
        now = {c: r[c] for c in events}
        older.append({**{names[c]: r[c] for c in states if r[c]}, **_gains(before, now, events), "year": _span(r, born or 1)})
        before = now
    # Its first fine year is its first only if born in it, or in a December filed under the next before the mod: a late window, coarse-less, holds a total.
    if not coarse and born not in (rows[0]["timestamp"], rows[0]["timestamp"] - 1):
        before = {}
    years, by_year = [], {row["timestamp"]: row for row in rows}
    row = rows[0] if rows else {}
    # Every year from its first to the last closed, a quiet one too: WB drops a year's row when nothing moved, and a gap would read as an end.
    for at in range(rows[0]["timestamp"], closed + 1) if rows else ():
        row = by_year.get(at, row)
        now = {c: row[c] for c in events}
        gains = _gains(before, now, events) if at in by_year else {}
        # The first fine row after a span that closed earlier than the year before gains over every year between, not over its own alone.
        since = {"from_year": coarse[-1]["timestamp"]} if gains and coarse and at == rows[0]["timestamp"] > coarse[-1]["timestamp"] else {}
        years.append({**{names[c]: row[c] for c in states if row[c]}, **gains, **since, "year": f"y{at}"})
        before = now
    return older + years  # the coarse spans first, each `year` a span `y20–y24`


# What rose since a chapter, or ever, and still stands, off the save, `log` telling the fallen; `actor`: one body's alone; each block cut to its latest `limit`.
def _build_founded(save: dict, since: str | None, actor: int | None, limit: int | None) -> dict:
    start = _chapter_time(load_save(SAVES_DIR / since / "map.wbox")) if since else -1.0
    cities, out = index_by_id(save.get("cities") or []), {}
    for collection, (founder, name, town) in _FOUNDED.items():
        risen = sorted(
            (record for record in save.get(collection) or [] if float(record.get("created_time") or 0) > start),
            key=lambda r: (float(r.get("created_time") or 0), r["id"]),
        )
        rows = []
        for record in risen:
            first = (record.get("past_rulers") or [{}])[0] if founder is None else {"id": record.get(founder), "name": record.get(name)}
            if actor is not None and first.get("id") != actor:
                continue
            rows.append(
                {
                    "born": entity_born(record),
                    "city": entity_ref(record.get(town), cities) if town else None,
                    "founder": {"id": first["id"], "name": first.get("name")} if first.get("id") is not None else None,
                    "id": record["id"],
                    "name": record.get("name"),
                }
            )
        if limit and len(rows) > limit:  # the latest kept, as a chapter reads what rose last
            print(f"⚠ {collection}: {len(rows)}, the latest {limit} — `--limit all` for every one", file=sys.stderr)
            rows = rows[-limit:]
        if rows:
            out[collection] = rows
    return out


# WB's own log up to the chapter, its bodies named by the save and the death register, its crowns by `crowns_named` — past `_MAX_LOG` entries, a count by kind.
def _build_log(save: dict, since: str | None, actor: int | None, event: str | None) -> dict | list[dict] | str:
    start = _chapter_time(load_save(SAVES_DIR / since / "map.wbox")) if since else 0.0
    if not (entries := log_entries(start, end := _chapter_time(save), actor, event)):
        told = "✗ nothing logged" + (f" since {since}" if since else "") + (" for that body" if actor is not None else "") + (f" as {event}" if event else "")
        # A kind WB knows but this world never logged, told beside what it did log: the kind exists, its day has not come
        others = Counter(e["event"] for e in log_entries(start, end, actor, None)) if event else None
        return told + (" — logged here: " + ", ".join(f"{kind} {n}" for kind, n in sorted(others.items())) if others else "")
    if len(entries) > _MAX_LOG:
        counts = Counter(e["event"] for e in entries)
        return {"by_event": dict(sorted(counts.items()))}
    persons, deaths, crowns = index_by_id(save.get("actors_data") or []), kept_deaths(save), crowns_named(save)
    for entry in entries:
        if event:  # the one `-t` asked for, so no entry repeats it — nor the body `--actor` named
            entry.pop("event")
        if (unit := entry.pop("actor_id")) is not None and actor is None:
            entry["actor"] = alive_or_dead_ref(unit, persons, deaths)
        if (crown := entry.pop("kingdom_id")) is not None:
            entry["kingdom"] = entity_ref(crown, crowns) or {"id": crown}
    return entries


# Every term the world still knows, a crown's, a town's or an army's, off its succession in the last save that held it — a fallen crown's, off the log too.
def _build_rulers(save: dict, save_path: Path, chapter: str | None, kinds: tuple[str, ...]) -> list[dict] | dict | str:
    persons = index_by_id(save.get("actors_data") or [])
    standing = {(kind, record["id"]) for kind in kinds for record in save.get(_ENTITIES[kind][1]) or []}
    records, rows = _ruled_records(save, save_path, chapter), []
    for (kind, entity_id), record in records.items():
        if kind in kinds:
            seat = {kind: {"id": entity_id, "name": record.get("name")}, "gone": (kind, entity_id) not in standing or None}
            rows += [{**reign, **seat} for reign in reigns(record, persons, "rulers")]
    if "kingdom" in kinds:  # a fallen crown's kings as the log names them, crowned (`from`) or gone (`to`): an end past its last save, a crown no save held
        crowns, logged = crowns_named(save), {}
        for entry in log_entries(0.0, _chapter_time(save), deaths=True):
            if entry["event"] in _REIGN_EDGES and (crown := entry["kingdom_id"]) is not None and ("kingdom", crown) not in standing:
                king = _king_entry(entry)
                seat = {"gone": True, "id": king.get("id"), "kingdom": entity_ref(crown, crowns) or {"id": crown}, "name": king["name"]}
                logged.setdefault((crown, king["name"]), seat)[_REIGN_EDGES[entry["event"]]] = king["date"]
        for row in rows:
            if row.get("gone") and "kingdom" in row and "to" not in row and (end := logged.get((row["kingdom"]["id"], row["name"]), {}).get("to")):
                row["to"] = end
        rows += [row for (crown, _), row in logged.items() if ("kingdom", crown) not in records]
    if not rows:
        return f"✗ no {' nor '.join(kinds)} has had a head yet"
    if len(rows) > _MAX_LOG:
        return {"by_kind": dict(sorted(Counter(kind for row in rows for kind in kinds if kind in row).items()))}
    deaths = kept_deaths(save)  # 60 ms of register, for the listed rows' `born` alone
    for row in rows:
        if (body := persons.get(row["id"])) is not None:
            row["born"] = entity_born(body)
        elif (dead := deaths.get(row["id"])) is not None:
            row["born"] = world_date(dead["born"])
    return sorted(rows, key=lambda row: (tuple(int(part[1:]) for part in (row.get("from") or row["to"]).split()), row.get("id") or 0))


# The world's years: what each one saw born, raised, razed or dying, as gains, and what it closed on — the one under way, with no row yet, off the save's tallies.
def _build_world(conn: sqlite3.Connection, save: dict) -> list[dict]:
    map_stats = save.get("mapStats") or {}
    closed = _closed_year(save)
    columns, coarse, rows = _series(conn, "World", None, closed + 1)
    # The deaths and the metamorphoses off the register: WB's tallies miss what dies uncounted, a crab reborn among them
    events = [c for c in columns if _EVENT_COLUMN.search(c) and c not in (_DEATHS_TOTAL, "metamorphosis") and not _DEATH_CAUSE.match(c)]
    died: defaultdict[int, Counter] = defaultdict(Counter)  # each year's deaths by cause, sorted once for every span to sum
    for dead in kept_deaths(save).values():
        died[_row_year(dead["died"])][dead["cause"]] += 1
    tracked = [*events, _DEATHS_TOTAL] if _DEATHS_TOTAL in columns else events
    before: dict = dict.fromkeys(tracked, 0)
    spans = []
    # The years before the window, as `entity` tells them: gains on each span from the world's birth, its states a mean, never what a year closed on.
    for r in coarse:
        now = {c: r[c] for c in tracked}
        gains, mean = _gains(before, now, events) | _died(died, max(r["timestamp"] - r["step"], 1), r["timestamp"] - 1), _world_states(r)
        if gains or mean:
            spans.append({**gains, "mean": mean or None, "year": _span(r, 1)})
        before = now
    if not coarse and rows and rows[0]["timestamp"] != 1:  # a window opened past the world's first year, with no span before it: its first row holds totals
        before = {}
    stood = 0 if before and not coarse else None  # the bodies the year before closed on: a span's are a mean, and a late window's unknown
    owed, timeline = 0, []
    for row in rows:
        now = {c: row[c] for c in tracked}
        roll = sum(row.get(column) or 0 for column in _ROLL)
        over = roll - stood - sum(sign * (now[c] - before[c]) for c, sign in _ROLL_TERMS.items() if c in now) if stood is not None else 0
        # A gap the next year takes back is one body counted a year off, and says so: the two years together fall right.
        gap = {"close_gap": over, "made_up": over == -owed or None} if over else {}
        owed, stood = over, roll
        if gains := _gains(before, now, events) | _died(died, row["timestamp"], row["timestamp"]):
            timeline.append({**gains, **gap, "at_close": _world_states(row), "year": f"y{row['timestamp']}"})
        before = now
    # WB's `mapStats` holds the same tallies in camelCase, the deaths snake-cased — two of them under names of their own.
    keys = {c: _STAT_KEYS.get(c) or (c if c.startswith("deaths_") else _camel(c)) for c in tracked}
    now = {c: int(v) if (v := map_stats.get(key)) is not None else None for c, key in keys.items()}
    start = closed + 1 if rows else coarse[-1]["timestamp"] if coarse else 1  # the year after the last row read: a span's end where no year is left
    if gains := _gains(before, now, events) | _died(died, start, closed + 1):
        timeline.append({**gains, "year": f"y{start}" if start > closed else f"y{start}–y{closed + 1}", "so_far": True})
    return spans + timeline


def _camel(column: str) -> str:
    return re.sub(r"_(\w)", lambda m: m.group(1).upper(), column)


# The chapter's own time: the base is the latest chapter's, so an older chapter reads it only up to the year it had closed.
def _chapter_time(save: dict) -> float:
    return float((save.get("mapStats") or {}).get("world_time") or 0)


# The last year closed at the chapter's hour, the one before its own: the year under way is told `so_far`.
def _closed_year(save: dict) -> int:
    return _row_year(_chapter_time(save)) - 1


# The deaths of the years `first` to `last` by cause, as the register keeps them — a metamorphosis is no death, and its tally stands apart.
def _died(died: Mapping[int, Counter], first: int, last: int) -> dict:
    counts = sum((died[year] for year in range(first, last + 1) if year in died), Counter())
    changed = counts.pop("metamorphosis", 0)
    return ({"deaths": dict(counts)} if counts else {}) | ({"metamorphosis": changed} if changed else {})


# Each year's rise of the rising tallies: `None` before any reading, so a window opened past the entity's first year never passes a total off as a year's gain.
def _gains(before: dict, now: dict, events: list[str]) -> dict:
    out: dict = {}
    by_cause = any(_DEATH_CAUSE.match(c) for c in events)  # the total, where causes stand, is their sum
    for column in events:
        if before.get(column) is None or now.get(column) is None or not (gain := now[column] - before[column]):
            continue
        if cause := _DEATH_CAUSE.match(column):
            out.setdefault("deaths", {})["old_age" if cause[1] == "natural" else cause[1]] = gain
        elif column != "deaths" or not by_cause:
            out[_WORLD_RENAMED.get(column, column)] = gain
    return out


# A king's line in the log, under the names it was written with: a murder's body is its killer, every other entry's the king himself.
def _king_entry(entry: dict) -> dict:
    body, at = entry["actor_id"], {"date": entry["date"], "event": entry["event"]}
    if entry["event"] == "king_killed":
        return {**at, "killer": {"id": body, "name": entry.get("killer")}, "name": entry.get("king")}
    names = entry.get("names") or []
    return {**at, "id": body, "name": names[1] if len(names) > 1 else None}


# The year whose row a moment falls in: Faithful Saves closes a calendar year as January opens — the rows WB wrote before it, a month early, read the same.
def _row_year(world_time: float) -> int:
    return int(world_time // UNITS_PER_YEAR) + 1


# Each crown, town and army as the last save to hold it left it, up to the chapter read: its name and succession, a seat gone between two chapters included.
def _ruled_records(save: dict, save_path: Path, chapter: str | None) -> dict[tuple[str, int], dict]:
    def table() -> dict[tuple[str, int], dict]:
        saves = [load_save(SAVES_DIR / f"C{n}" / "map.wbox") for n in range(1, int(chapter[1:]) if chapter else 1)] + [save]
        held = ((kind, record) for each in saves for kind in _RULED for record in each.get(_ENTITIES[kind][1]) or [])
        return {(kind, record["id"]): {"name": record.get("name"), "past_rulers": record.get(_RULED[kind])} for kind, record in held}  # as `reigns` reads it

    return pickle_cached("ruled_records_v2", save_path, table)


# Every row of one series before `year`, the fine window's years and, older, the coarse steps' approximations — each row its own blanks carried.
def _series(conn: sqlite3.Connection, stem: str, entity_id: int | None, year: int) -> tuple[list[str], list[dict], list[dict]]:
    where, params = ("WHERE timestamp < ?", [year]) if entity_id is None else ("WHERE id = ? AND timestamp < ?", [entity_id, year])
    fine = conn.execute(f"SELECT * FROM {stem}Yearly{_FINE_STEP} {where} ORDER BY timestamp", params)
    names = [c for c, *_ in fine.description]
    columns = [c for c in names if c not in _SKIPPED]
    rows = [dict(zip(names, row, strict=True)) for row in fine.fetchall()]
    opens = rows[0]["timestamp"] if rows else year
    coarse: list[dict] = []
    owner, held = ("", []) if entity_id is None else ("id = ? AND ", [entity_id])
    # The finest step still reaching further back, one at a time, never two for the same years: a row at `timestamp` spans the `step` years before it.
    for step in _STEPS[1:]:
        older = conn.execute(f"SELECT * FROM {stem}Yearly{step} WHERE {owner}timestamp <= ? ORDER BY timestamp", [*held, opens])
        coarse_names = [c for c, *_ in older.description]
        if found := [{**dict(zip(coarse_names, row, strict=True)), "step": step} for row in older.fetchall()]:
            coarse, opens = found + coarse, found[0]["timestamp"] - step
    carried: dict = {}
    for row in [*coarse, *rows]:  # WB blanks a value equal to the one before: every cell carries the last one read, in the order they were written
        for column in columns:
            if row.get(column) is None:
                row[column] = carried.get(column)
            carried[column] = row[column]
    return columns, coarse, rows


# The years a coarse row spans, the `step` before its own, from `first` at the earliest: `y5–y9`, or one year bare.
def _span(row: dict, first: int) -> str:
    start, end = max(row["timestamp"] - row["step"], first), row["timestamp"] - 1
    return f"y{start}–y{end}" if start < end else f"y{end}"


# A world row's states under `world`'s own names. WB's `vegetation` counts its trees in, where `snapshot` tells them apart — and a nought goes unsaid.
def _world_states(row: dict) -> dict:
    states = {_WORLD_RENAMED.get(column, column): row[column] for column in _WORLD_STATES if row.get(column)}
    if (plants := states.pop("vegetation", 0) - states.get("trees", 0)) > 0:
        states["vegetation"] = plants
    return states


def main(argv: list[str]) -> int:
    try:
        since, argv = take_since(argv)
    except ValueError as e:
        print(f"✗ {e}", file=sys.stderr)
        return 2
    save_path, argv, chapter = take_chapter(argv)
    parser = arg_parser(prog="history/info.py", taken="[--since C<n>] [C<n>]")
    parser.add_argument("section")
    parser.add_argument("entity", nargs="*", metavar="kind id")
    parser.add_argument("--actor", type=int, metavar="id")
    parser.add_argument("--limit", type=limit_arg, metavar="n|all")
    kinds = sorted(load_data("world-log.json"))  # WB's own kinds of entry: a word outside them is a typo, refused with the list, never a quiet nothing
    parser.add_argument("--type", "-t", choices=kinds, metavar="event")
    args = parser.parse_args(argv)
    if args.section not in _SECTIONS:
        hint = f"an entity's years: `entity {args.section} <id>`" if args.section in _ENTITIES else f"valid: {', '.join(_SECTIONS)}"
        print(f"✗ no section {args.section} — {hint}", file=sys.stderr)
        return 2
    seats = tuple(sorted({seat for arg in args.entity for seat in arg.split(",")})) if args.section == "rulers" else ()  # a comma list, as sections take
    if not set(seats) <= set(_RULED):
        print(f"✗ rulers takes a seat or none: {', '.join(_RULED)} — one seat's own: `kingdom <id> rulers`, `city <id> rulers`, `city <id> army`", file=sys.stderr)
        return 2
    if args.section not in ("entity", "rulers") and args.entity:
        print(f"✗ {args.section} takes no entity", file=sys.stderr)
        return 2
    if args.section == "entity" and not (len(args.entity) == 2 and args.entity[0] in _ENTITIES and args.entity[1].isdigit()):
        print(f"✗ entity takes a kind and an id: `entity family 12` — kinds: {', '.join(_ENTITIES)}", file=sys.stderr)
        return 2
    if args.actor is not None and args.section not in ("founded", "log"):
        print("✗ --actor narrows `log` and `founded`: name one", file=sys.stderr)
        return 2
    if args.type and args.section != "log":
        print("✗ -t narrows `log`: name it", file=sys.stderr)
        return 2
    if args.limit is not None and args.section != "founded":
        print("✗ --limit cuts `founded`: name it", file=sys.stderr)
        return 2
    if since and args.section not in ("founded", "log"):
        print("✗ --since narrows `log` and `founded`: name one", file=sys.stderr)
        return 2
    if since and not (SAVES_DIR / since / "map.wbox").exists():
        print(f"✗ no save for {since}", file=sys.stderr)
        return 2
    if not HISTORY_S3DB.exists():
        print("✗ no history base yet — `chapter/new.py` copies WB's with each chapter", file=sys.stderr)
        return 1
    save = load_save(save_path)
    with closing(sqlite3.connect(f"file:{HISTORY_S3DB}?mode=ro", uri=True)) as conn:  # `with connect()` alone commits, it never closes
        if args.section == "world":
            out = _build_world(conn, save) or "✗ no year closed, and nothing born, raised or dead yet"
        elif args.section == "log":
            out = _build_log(save, since, args.actor, args.type)
        elif args.section == "founded":
            limit = _LIMIT if args.limit is None else args.limit or None  # `all` read as 0: every line
            by = f" by {args.actor}" if args.actor is not None else ""
            out = _build_founded(save, since, args.actor, limit) or f"✗ nothing founded{by} {f'since {since}' if since else 'yet'} still stands — the fallen: `log`"
        elif args.section == "rulers":
            out = _build_rulers(save, save_path, chapter, seats or tuple(_RULED))
        elif args.section == "dead_kingdoms":
            out = _build_dead_kingdoms(conn, save) or "✗ no crown has fallen"
        else:
            out = _build_entity(conn, args.entity[0], int(args.entity[1]), save, chapter)
    if isinstance(out, str):
        print(out, file=sys.stderr)
        return 1
    emit({args.section: out})
    return 0


if __name__ == "__main__":
    sys.exit(run(main))
