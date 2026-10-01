#!/usr/bin/env python3

# WB's own history, `history/map_stats.s3db`, read so that no one queries it raw: windows joined, blanks carried, tallies told as each year's gains, dates compact.
# User-facing docs: `docs/tools.md`.

import json
import re
import sqlite3
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))

from shared import (
    HISTORY_S3DB,
    SAVES_DIR,
    UNITS_PER_YEAR,
    absent_entity,
    arg_parser,
    emit,
    entity_ref,
    latest_chapter,
    load_save,
    log_entries,
    take_chapter,
    take_since,
    world_date,
)

_DEATHS_TOTAL = "deaths_total"  # WB's yearly total, which the causes fall short of where a death was filed under none
_DEATH_CAUSE = re.compile(r"^deaths_(?!attackers$|defenders$|total$)(\w+)$")  # a death's cause, where `natural` is WB's old age — a war's two sides are no cause

# Tool kind => (WB table stem, save collection): the collection finds the living, whom alone WB keeps the years of.
_ENTITIES = {
    "alliance": ("Alliance", "alliances"),
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

# A column that only rises, an event's tally — where a bare noun (`population`, `cities`) is a state, and a year's value is the state it closed on.
_EVENT_COLUMN = re.compile(
    r"^(births|deaths(_\w+)?|evolutions|joined|kills|left|metamorphosis|migrated|moved|speakers_\w+)$"
    r"|_(born|built|burnt|conquered|created|destroyed|dissolved|extinct|forgotten|made|read|rebelled|started|succeeded|written)$"
)

_FINE_STEP = 1  # WB's yearly table: a row a year, the only one whose `timestamp` is a year — every coarser one averages its span or keeps its last year
_MAX_LOG = 50  # past so many entries the journal is read by its kinds of event, not line by line: `-t` or `--actor` narrow it back
_SECTIONS = ("dead_kingdoms", "entity", "log", "world")
_SKIPPED = frozenset({"auto", "id", "timestamp"})  # WB's row bookkeeping: `auto` flags a row it wrote itself, and says nothing of the world
_STAT_KEYS = {"deaths_natural": "deaths_age", _DEATHS_TOTAL: "deaths"}  # the yearly columns `mapStats` names otherwise: old age, and the bare total
_STEPS = (1, 5, 10, 50, 100, 500, 1000, 5000, 10000)  # WB's table suffixes, each keeping a window of the last rows at that step
_WORLD_RENAMED = {"houses_built": "buildings_built", "houses_destroyed": "buildings_destroyed"}  # `world … cumulative`'s names: WB's houses are all its buildings


# WB's crowns once raised, fallen ones with their dates — the one record a fallen crown keeps once its years are gone.
def _build_dead_kingdoms(conn: sqlite3.Connection, save: dict) -> list[dict]:
    _, now = _chapter_clock(save)
    rows = conn.execute(
        "SELECT id, name, original_actor_asset, created_time, died_time, total_births, total_deaths, total_kills FROM KingdomData"
        " WHERE died_time IS NOT NULL AND died_time <= ? ORDER BY died_time",
        (now,),
    ).fetchall()
    return [
        {"asset_id": asset, "births": b, "deaths": d, "fell": world_date(died), "founded": world_date(born or 0), "id": kid, "kills": k, "name": name}
        for kid, name, asset, born, died, b, d, k in rows
    ]


# One entity's years: its states as they closed each year, and what its tallies gained in it; older years, coarse, their states alone and never as a date.
def _build_entity(conn: sqlite3.Connection, kind: str, entity_id: int, save: dict, chapter: str | None) -> list[dict] | str:
    stem, collection = _ENTITIES[kind]
    year, _ = _chapter_clock(save)
    columns, coarse, rows = _series(conn, stem, entity_id, year)
    living = next((e for e in save.get(collection) or [] if e.get("id") == entity_id), None)
    if not rows and not coarse:
        if living is not None:
            return f"✗ {kind} {entity_id} has no year closed yet: WB writes a year's row as it ends"
        refusal = absent_entity(kind, collection, entity_id, chapter)
        return f"{refusal} — WB keeps the years of the living alone" if " is gone " in refusal else refusal
    events = [c for c in columns if _EVENT_COLUMN.search(c)]
    states = [c for c in columns if c not in events and any(r[c] for r in (*coarse, *rows))]  # a state at nought all along says nothing
    born = int(float(living["created_time"]) // UNITS_PER_YEAR) + 1 if living and living.get("created_time") is not None else None
    # Its first fine year is a first year only when it was born in it: a window opened later holds a total, not that year's gain.
    before: dict = dict.fromkeys(events, 0) if rows and not coarse and born == rows[0]["timestamp"] else {}
    years, by_year = [], {row["timestamp"]: row for row in rows}
    row = rows[0] if rows else {}
    # Every year from its first to the last closed, a quiet one too: WB drops a year's row when nothing moved, and a gap would read as an end.
    for at in range(rows[0]["timestamp"], year) if rows else ():
        row = by_year.get(at, row)
        now = {c: row[c] for c in events}
        years.append({"year": at, **{c: row[c] for c in states if row[c]}, **(_gains(before, now, events) if at in by_year else {})})
        before = now
    older = [{"around_year": r["timestamp"], "step": r["step"], **{c: r[c] for c in states if r[c]}} for r in coarse]
    return older + years  # the coarse steps' approximations first, each told `around_year`, never as a date


# WB's own log up to the chapter, its bodies and crowns named off the registries — past `_MAX_LOG` entries, a count by kind of event.
def _build_log(save: dict, since: str | None, actor: int | None, event: str | None) -> dict | list[dict] | str:
    start = _chapter_clock(load_save(SAVES_DIR / since / "map.wbox"))[1] if since else 0.0
    if not (entries := log_entries(start, _chapter_clock(save)[1], actor, event)):
        return "✗ nothing logged" + (f" since {since}" if since else "") + (" for that body" if actor is not None else "") + (f" as {event}" if event else "")
    if len(entries) > _MAX_LOG:
        counts = Counter(e["event"] for e in entries)
        return {"by_event": dict(sorted(counts.items())), "info": f"{len(entries)} entries — `-t <event>` or `--actor <id>` lists them"}
    persons, crowns = _registry("persons"), _registry("kingdoms")
    for entry in entries:
        if event:  # the one `-t` asked for, so no entry repeats it — nor the body `--actor` named
            entry.pop("event")
        if (unit := entry.pop("actor_id")) is not None and actor is None:
            entry["actor"] = entity_ref(unit, persons) or {"id": unit}
        if (crown := entry.pop("kingdom_id")) is not None:
            entry["kingdom"] = entity_ref(crown, crowns) or {"id": crown}
    return entries


# The world's years: what each one saw born, raised, razed or dying, as gains — the year under way, which has no row yet, off the save's own tallies.
def _build_world(conn: sqlite3.Connection, save: dict) -> list[dict]:
    map_stats = save.get("mapStats") or {}
    year, _ = _chapter_clock(save)
    columns, _, rows = _series(conn, "World", None, year)
    events = [c for c in columns if _EVENT_COLUMN.search(c) and c != _DEATHS_TOTAL]
    tracked = [*events, _DEATHS_TOTAL] if _DEATHS_TOTAL in columns else events
    before: dict = dict.fromkeys(tracked, 0) if not rows or rows[0]["timestamp"] == 1 else {}
    timeline = []
    for row in rows:
        now = {c: row[c] for c in tracked}
        if gains := _with_unknown(_gains(before, now, events), before, now):
            timeline.append({"year": row["timestamp"], **gains})
        before = now
    # WB's `mapStats` holds the same tallies in camelCase, the deaths snake-cased — two of them under names of their own.
    keys = {c: _STAT_KEYS.get(c) or (c if c.startswith("deaths_") else _camel(c)) for c in tracked}
    now = {c: int(v) if (v := map_stats.get(key)) is not None else None for c, key in keys.items()}
    if gains := _with_unknown(_gains(before, now, events), before, now):
        timeline.append({"year": year, **gains, "so_far": True})
    return timeline


def _camel(column: str) -> str:
    return re.sub(r"_(\w)", lambda m: m.group(1).upper(), column)


# The chapter's own year and time: the base is the latest chapter's, so an older chapter reads it only up to the year it had closed.
def _chapter_clock(save: dict) -> tuple[int, float]:
    world_time = float((save.get("mapStats") or {}).get("world_time") or 0)
    return int(world_time // UNITS_PER_YEAR) + 1, world_time


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


# The persons and crowns named by id in the latest chapter's registries — the dead kept, whom no save carries any more.
def _registry(name: str) -> dict:
    n = latest_chapter()
    path = SAVES_DIR / f"C{n}" / f"{name}.json" if n else None
    return {int(k): v for k, v in json.loads(path.read_text()).items()} if path and path.exists() else {}


# Every row of one series before `year`, the fine window's years and, older, the coarse steps' approximations — each row its own blanks carried.
def _series(conn: sqlite3.Connection, stem: str, entity_id: int | None, year: int) -> tuple[list[str], list[dict], list[dict]]:
    where, params = ("WHERE timestamp < ?", [year]) if entity_id is None else ("WHERE id = ? AND timestamp < ?", [entity_id, year])
    fine = conn.execute(f"SELECT * FROM {stem}Yearly{_FINE_STEP} {where} ORDER BY timestamp", params)
    names = [c for c, *_ in fine.description]
    columns = [c for c in names if c not in _SKIPPED]
    rows = [dict(zip(names, row)) for row in fine.fetchall()]
    opens = rows[0]["timestamp"] if rows else year
    coarse: list[dict] = []
    for step in _STEPS[1:]:  # the finest step still reaching further back, one step at a time, never two for the same years
        older = conn.execute(f"SELECT * FROM {stem}Yearly{step} {where} AND timestamp < ? ORDER BY timestamp", [*params, opens])
        coarse_names = [c for c, *_ in older.description]
        if found := [{**dict(zip(coarse_names, row)), "step": step} for row in older.fetchall()]:
            coarse, opens = found + coarse, found[0]["timestamp"]
    carried: dict = {}
    for row in [*coarse, *rows]:  # WB blanks a value equal to the one before: every cell carries the last one read, in the order they were written
        for column in columns:
            if row.get(column) is None:
                row[column] = carried.get(column)
            carried[column] = row[column]
    return columns, coarse, rows


# A year's deaths WB counted in its total and filed under no cause, as `world … cumulative` says them: the causes then sum to the total.
def _with_unknown(gains: dict, before: dict, now: dict) -> dict:
    if before.get(_DEATHS_TOTAL) is None or now.get(_DEATHS_TOTAL) is None:
        return gains
    if (unknown := now[_DEATHS_TOTAL] - before[_DEATHS_TOTAL] - sum((gains.get("deaths") or {}).values())) > 0:
        gains.setdefault("deaths", {})["unknown"] = unknown
    return gains


def main(argv: list[str]) -> int:
    try:
        since, argv = take_since(argv)
    except ValueError as e:
        print(f"✗ {e}", file=sys.stderr)
        return 2
    save_path, argv, chapter = take_chapter(argv)
    parser = arg_parser(prog="history/info.py", description="The world's past, from WB's own history base.")
    parser.add_argument("section", help=f"Valid: {', '.join(_SECTIONS)}")
    parser.add_argument("entity", nargs="*", help=f"`entity`: its kind and id, `entity family 12` — kinds: {', '.join(_ENTITIES)}")
    parser.add_argument("--actor", type=int, metavar="id", help="`log`: the entries naming one body")
    parser.add_argument("--type", "-t", metavar="event", help="`log`: one kind of entry, by WB's id (`kingdom_new`…)")
    args = parser.parse_args(argv)
    if args.section not in _SECTIONS:
        hint = f"an entity's years: `entity {args.section} <id>`" if args.section in _ENTITIES else f"valid: {', '.join(_SECTIONS)}"
        print(f"✗ no section {args.section} — {hint}", file=sys.stderr)
        return 2
    if args.section != "entity" and args.entity:
        print(f"✗ {args.section} takes no entity", file=sys.stderr)
        return 2
    if args.section == "entity" and not (len(args.entity) == 2 and args.entity[0] in _ENTITIES and args.entity[1].isdigit()):
        print(f"✗ entity takes a kind and an id: `entity family 12` — kinds: {', '.join(_ENTITIES)}", file=sys.stderr)
        return 2
    if (args.actor is not None or args.type or since) and args.section != "log":
        print("✗ --actor, -t and --since narrow `log`: name it", file=sys.stderr)
        return 2
    if since and not (SAVES_DIR / since / "map.wbox").exists():
        print(f"✗ no save for {since}", file=sys.stderr)
        return 2
    if not HISTORY_S3DB.exists():
        print("✗ no history base yet — `chapter/new.py` copies WB's with each chapter", file=sys.stderr)
        return 1
    save = load_save(save_path)
    with sqlite3.connect(f"file:{HISTORY_S3DB}?mode=ro", uri=True) as conn:
        if args.section == "world":
            out = _build_world(conn, save)
        elif args.section == "log":
            out = _build_log(save, since, args.actor, args.type)
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
    sys.exit(main(sys.argv[1:]))
