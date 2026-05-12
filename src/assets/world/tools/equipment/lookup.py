#!/usr/bin/env python3
"""Look up equipment items by ID for a given chapter (or the live save).

Usage:
    python3 lookup.py <chapterIndex|current> <id> [<id> ...]

`<chapterIndex>` = chapter number (1, 2, ...) → resolves `saves/C<chapterIndex>/map.wbox`
relative to this script. `current` = the live WorldBox save (cf. CURRENT_SAVE below) — used
when the chronicler is generating a new chapter from the freshly saved game state.
Accepts any item ID in `save['items']`. Prints `id | rarity | asset_id | durability | by |
from | kills | age | stats` per item. Unknown IDs are reported on stderr.

  - `by` / `from` / `kills`  : creator name / kingdom / kill counter — `—` / `0` when absent
  - `age`                    : (current world_time - item.created_time) / 60, rounded (years)
  - `stats`                  : combined `base_item + sum(modifiers)`, k=v alphabetical

Data sources:
  - Rarity rule: max level among leveled modifiers (`name1`..`name5`); special non-leveled
    modifiers (`stun`, `flame`, `ice`, `cursed`, `slowness`, `eternal`, `divine_rune`, `poison`)
    contribute nothing — see wiki Equipment#Rarity:
        >= 5 -> Legendary,  >= 4 -> Epic,  >= 3 -> Rare,  otherwise Normal
  - Base item & modifier stats: extracted from `BaseStats.set_Item` calls in
    `ItemLibrary.initWeapons*/initArmors/...` and `ItemModifierLibrary.init` IL bodies of
    `Assembly-CSharp.dll`; clones resolved against their source.
"""
import json
import re
import sys
import zlib
from pathlib import Path

DATA = Path(__file__).parent / 'data.json'
SAVES_DIR = Path(__file__).parent.parent.parent / 'saves'
# macOS path — mirror chronicler.md § "Emplacement source des saves WorldBox".
CURRENT_SAVE = Path.home() / 'Library/Application Support/mkarpenko/WorldBox/saves/save1/map.wbox'
LEVEL_RE = re.compile(r'(\d+)$')
MONTHS_PER_YEAR = 60


def rarity(modifiers: list[str]) -> str:
    levels = [int(m.group(1)) for m in (LEVEL_RE.search(x) for x in modifiers) if m]
    max_level = max(levels) if levels else 0
    if max_level >= 5: return 'Legendary'
    if max_level >= 4: return 'Epic'
    if max_level >= 3: return 'Rare'
    return 'Normal'


# Combine base-item stats with the summed contribution of each applied modifier.
# Drops stats that sum to 0 (no effect).
def combine_stats(asset_id: str, modifiers: list[str], item_stats: dict, mod_stats: dict) -> dict:
    out = dict(item_stats.get(asset_id, {}))
    for mod in modifiers:
        for k, v in mod_stats.get(mod, {}).items():
            out[k] = out.get(k, 0) + v
    cleaned = {}
    for k, v in out.items():
        if isinstance(v, float):
            r = round(v, 4)
            v = int(r) if r.is_integer() else r
        if v != 0: cleaned[k] = v
    return cleaned


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__, file=sys.stderr)
        return 2
    target = argv[0]
    if target == 'current':
        map_path = CURRENT_SAVE
    else:
        try: chapter_index = int(target)
        except ValueError:
            print(f'invalid chapterIndex: {target} (expected integer or "current")', file=sys.stderr)
            return 2
        map_path = SAVES_DIR / f'C{chapter_index}' / 'map.wbox'
    if not map_path.exists():
        print(f'no save found at {map_path}', file=sys.stderr)
        return 2
    with map_path.open('rb') as f:
        save = json.loads(zlib.decompress(f.read()))
    items_by_id = {it['id']: it for it in save['items']}
    world_time = save['mapStats']['world_time']
    with DATA.open() as f:
        data = json.load(f)
    item_stats = data['items']
    mod_stats = data['modifiers']

    exit_code = 0
    for raw in argv[1:]:
        try: iid = int(raw)
        except ValueError:
            print(f'invalid id: {raw}', file=sys.stderr)
            exit_code = 1
            continue
        item = items_by_id.get(iid)
        if not item:
            print(f'unknown: {iid}', file=sys.stderr)
            exit_code = 1
            continue
        mods = item.get('modifiers') or []
        aid = item['asset_id']
        dur = item.get('durability', '—')
        by = item.get('by') or '—'
        kingdom = item.get('from') or '—'
        kills = item.get('kills', 0)
        ct = item.get('created_time')
        age = round((world_time - ct) / MONTHS_PER_YEAR) if ct is not None else '—'
        combined = combine_stats(aid, mods, item_stats, mod_stats)
        stats_str = ','.join(f'{k}={v}' for k, v in sorted(combined.items()))
        print(f"{iid} | {rarity(mods)} | {aid} | {dur} | {by} | {kingdom} | {kills} | {age} | {stats_str}")
    return exit_code


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
