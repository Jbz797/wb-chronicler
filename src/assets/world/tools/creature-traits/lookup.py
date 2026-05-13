#!/usr/bin/env python3
"""Look up creature traits by ID.

Usage: python3 lookup.py <id> [<id> ...]

Prints `id | rarity | description | flavor | stats` per ID — `stats` is `k=v` pairs
(alphabetical, empty when none). Unknown IDs reported on stderr.
"""
# ─── Maintenance / re-extraction notes ───
# `data.json` is rebuilt from the WorldBox game files (macOS):
#   $HOME/Library/Application Support/Steam/steamapps/common/worldbox/worldbox.app/
#       Contents/Resources/Data/Managed/Assembly-CSharp.dll  (rarity + stats)
#       Contents/Resources/Data/resources.assets             (TextAsset `traits_units`)
# Toolchain: `dncil` (IL decoder), `dnfile` (PE/metadata parser), `UnityPy` (TextAsset extraction).
#
# Each trait aggregates 3 independent extractions:
#   • id / name / description / flavor → `traits_units` TextAsset, EN locale (UnityPy).
#   • rarity → reconstructed from `BaseTraitLibrary<T>.autoSetRarity` (IL walk).
#       ⚠️ Gotcha: `BaseTrait<T>.ctor` defaults `rarity = 1` (= Rare), not Normal. Many
#       traits never re-assign rarity, so the “fallback” is Rare. Algorithm summary:
#       Legendary if `unlocked_with_achievement`; else feature counter (actions /
#       decisions / spells / combat_actions / hasTags / plot) → Epic (≥2) / Rare (==1) /
#       constructor default (Rare unless explicit Normal).
#   • stats → `BaseStats.set_Item` calls inside `ActorTraitLibrary.addTraits{Body,Mind,
#       Spirit,Acquired,Fun,Misc,Special}` IL bodies. Pattern after `library.add(trait)`:
#       `ldfld library.t.base_stats ; ldstr <stat> ; ldc.r4|ldc.i4 <val> ; callvirt set_Item`.
#       Float values from `ldc.r4` rounded to 4 decimals; integer-equivalents cast to int.
#
# Output ordering assumption: `data.json` was dumped with `json.dump(..., sort_keys=True)`,
# so the `stats` dict from `json.load` is already alphabetical (dict preserves order since
# Python 3.7). If a future extraction drops `sort_keys`, restore `sorted(...)` below.
import json
import sys
from pathlib import Path

DATA = Path(__file__).parent / 'data.json'


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__, file=sys.stderr)
        return 2
    with DATA.open() as f:
        traits = json.load(f)
    exit_code = 0
    for tid in argv:
        entry = traits.get(tid)
        if entry is None:
            print(f'unknown: {tid}', file=sys.stderr)
            exit_code = 1
            continue
        stats = ','.join(f'{k}={v}' for k, v in (entry.get('stats') or {}).items())
        print(f"{tid} | {entry['rarity']} | {entry['description']} | {entry['flavor']} | {stats}")
    return exit_code


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
