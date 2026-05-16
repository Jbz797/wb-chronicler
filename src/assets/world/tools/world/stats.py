#!/usr/bin/env python3
"""Aggregate world-level statistics from the live save.

Usage: python3 stats.py

Reads `map.meta` (sibling of `map.wbox`) which WorldBox already populates with all
panel counters (population, vegetation, cities, etc.). `houses` is derived from
`mapStats.housesBuilt - housesDestroyed` (matches the in-game world stats panel).
`alliances` lives in the compressed save and is loaded separately.

Output (two lines):
  `world  | <stat>=<value>,...`    (alphabetical)
  `deaths | <cause>=<value>,...`   (cumulative deaths by cause, alphabetical)
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _lib import CURRENT_SAVE, load_save

# Mapping chronicler key => map.meta top-level key.
_META_KEYS = {
    'books':      'books',
    'cities':     'cities',
    'clans':      'clans',
    'creatures':  'mobs',
    'cultures':   'cultures',
    'equipment':  'equipment',
    'families':   'families',
    'kingdoms':   'kingdoms',
    'languages':  'languages',
    'population': 'population',
    'religions':  'religions',
    'subspecies': 'subspecies',
    'vegetation': 'vegetation',
    'wars':       'wars',
}
# Mapping chronicler cause => map.meta.mapStats death-counter (`deaths_age` is what
# `world_statistics_deaths_natural` aggregates per the DLL; we surface it as `age`).
_DEATH_CAUSES = {
    'age':       'deaths_age',
    'drowning':  'deaths_drowning',
    'eaten':     'deaths_eaten',
    'explosion': 'deaths_explosion',
    'fire':      'deaths_fire',
    'hunger':    'deaths_hunger',
    'water':     'deaths_water',
    'weapon':    'deaths_weapon',
}


def main() -> int:
    meta_path = CURRENT_SAVE.with_name('map.meta')
    if not meta_path.exists():
        print(f'no map.meta found next to {CURRENT_SAVE}', file=sys.stderr)
        return 2
    meta = json.loads(meta_path.read_text())
    map_stats = meta.get('mapStats') or {}
    stats = {k: int(meta.get(v, 0)) for k, v in _META_KEYS.items()}
    # Current city-buildings — matches the in-game `world_statistics_houses` panel.
    stats['houses'] = int(map_stats.get('housesBuilt', 0)) - int(map_stats.get('housesDestroyed', 0))
    # Cumulative — UI surfaces only the per-chapter delta.
    stats['books_read'] = int(map_stats.get('booksRead', 0))
    stats['plots_succeeded'] = int(map_stats.get('plotsSucceeded', 0))
    # `alliances` isn't surfaced in map.meta — fall back to the compressed save.
    stats['alliances'] = len(load_save().get('alliances') or [])
    deaths = {k: int(map_stats.get(v, 0)) for k, v in _DEATH_CAUSES.items()}
    print(f"world  | {','.join(f'{k}={v}' for k, v in sorted(stats.items()))}")
    print(f"deaths | {','.join(f'{k}={v}' for k, v in sorted(deaths.items()))}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
