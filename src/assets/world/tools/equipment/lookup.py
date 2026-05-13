#!/usr/bin/env python3
"""Look up equipment items by ID for a given chapter (or the live save).

Usage: python3 lookup.py <chapterIndex|current> <id> [<id> ...]

`<chapterIndex>` resolves `saves/C<chapterIndex>/map.wbox` relative to this script.
`current` reads the live WorldBox save (cf. CURRENT_SAVE below) — used when generating a
new chapter from a freshly saved game.

Output per item: `id | rarity | asset_id | durability | by | from | kills | age | stats`
  • `by` / `from` / `kills`: creator name / kingdom / kill counter — `—` / `0` when absent
  • `age`: `(world_time - created_time) / 60`, rounded (years)
  • `stats`: combined `base_item + Σ modifiers`, k=v alphabetical, zeros dropped
"""
# ─── Maintenance / re-extraction notes ───
# `data.json` is rebuilt from the WorldBox game files (macOS):
#   $HOME/Library/Application Support/Steam/steamapps/common/worldbox/worldbox.app/
#       Contents/Resources/Data/Managed/Assembly-CSharp.dll
# Toolchain: `dncil` (IL decoder), `dnfile` (PE/metadata parser).
#
# `data.json` has two sub-dicts: `items` and `modifiers`.
#   • `items`: base item stats from `ItemLibrary.init{WeaponsSwords,WeaponsBows,WeaponsAxes,
#     WeaponsSpears,WeaponsHammers,WeaponsUnique,Amulets,Helmets,Armors,Boots,Rings,...}`.
#     Items are defined via `library.clone(new_id, src_id)` from a template chain (e.g.
#     `hammer_stone` ← `$hammer` ← `$civ_unit$` ← ...). Extraction resolves clones
#     recursively, flattening to one `{stat: value}` per final item.
#   • `modifiers`: stat boosts from `ItemModifierLibrary.init`. Same pattern: `newobj` for
#     base definitions, `library.clone(...)` for level variants (`balance5` cloned from
#     `balance1`, etc.) → recursive resolution too.
#
# Stat-setting pattern in IL (both libraries): after `library.add(...)` or `library.clone(...)`,
# sequences of `ldfld library.t.base_stats ; ldstr <stat> ; ldc.r4|ldc.i4 <val> ; callvirt set_Item`
# assign each stat to the most-recently-added entry (`library.t` = pointer to last added).
# Float values from `ldc.r4` are rounded to 4 decimals; integer-equivalents cast to `int`.
#
# Rarity rule (cf. WorldBox wiki Equipment#Rarity): max trailing-digit level across the
# item's modifiers (`name1`..`name5`). Special non-leveled modifiers like `stun`, `flame`,
# `ice`, `cursed`, `slowness`, `eternal`, `divine_rune`, `poison` contribute 0 — the regex
# `(\d+)$` only matches modifiers ending in a digit.
#
# `sorted(combined.items())` at output time is required: each sub-dict in `data.json` is
# alphabetical, but the merge (base item + modifiers) doesn't preserve that order.
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
    max_level = max((int(m.group(1)) for m in (LEVEL_RE.search(x) for x in modifiers) if m), default=0)
    if max_level >= 5: return 'Legendary'
    if max_level >= 4: return 'Epic'
    if max_level >= 3: return 'Rare'
    return 'Normal'


# Combine base-item stats with the summed contribution of each applied modifier.
# Rounds floats to 4 decimals, casts integer-equivalents to int, drops zeros.
def combine_stats(asset_id: str, modifiers: list[str], item_stats: dict, mod_stats: dict) -> dict:
    out = dict(item_stats.get(asset_id, {}))
    for mod in modifiers:
        for k, v in mod_stats.get(mod, {}).items():
            out[k] = out.get(k, 0) + v
    result = {}
    for k, v in out.items():
        if isinstance(v, float):
            v = round(v, 4)
            if v.is_integer(): v = int(v)
        if v: result[k] = v
    return result


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
        if item is None:
            print(f'unknown: {iid}', file=sys.stderr)
            exit_code = 1
            continue
        mods = item.get('modifiers') or []
        aid = item['asset_id']
        ct = item.get('created_time')
        age = round((world_time - ct) / MONTHS_PER_YEAR) if ct is not None else '—'
        combined = combine_stats(aid, mods, item_stats, mod_stats)
        stats_str = ','.join(f'{k}={v}' for k, v in sorted(combined.items()))
        print(f"{iid} | {rarity(mods)} | {aid} | {item.get('durability', '—')} | "
              f"{item.get('by') or '—'} | {item.get('from') or '—'} | "
              f"{item.get('kills', 0)} | {age} | {stats_str}")
    return exit_code


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
