#!/usr/bin/env python3
"""Aggregate world-level statistics from the live save.

Usage: python3 stats.py

Reads `map.meta` (sibling of `map.wbox`) which WorldBox already populates with all
panel counters (population, vegetation, cities, etc.). `houses` is derived from
`mapStats.housesBuilt - housesDestroyed` (matches the in-game world stats panel).
`alliances` lives in the compressed save and is loaded separately.

Output: `world | <stat>=<value>,...` (alphabetical).
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
    'deaths':     'deaths',
    'equipment':  'equipment',
    'families':   'families',
    'kingdoms':   'kingdoms',
    'languages':  'languages',
    'plants':     'vegetation',
    'population': 'population',
    'religions':  'religions',
    'subspecies': 'subspecies',
    'wars':       'wars',
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
    # `alliances` isn't surfaced in map.meta — fall back to the compressed save.
    stats['alliances'] = len(load_save().get('alliances') or [])
    print(f"world | {','.join(f'{k}={v}' for k, v in sorted(stats.items()))}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
