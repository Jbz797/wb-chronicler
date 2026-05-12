#!/usr/bin/env python3
"""Look up creature traits by ID.

Usage:
    python3 lookup.py <trait_id> [<trait_id> ...]

Reads `data.json` (sibling file) and prints `id | rarity | description | flavor | stats` for each
requested ID. `stats` is formatted as `k1=v1,k2=v2,...` (alphabetical) using the game's internal
stat names — empty when the trait has no modifiers. Unknown IDs are reported on stderr.

Data source: game assets only — IDs/names/descriptions from the `traits_units` TextAsset
(EN locale); rarity reconstructed from the `autoSetRarity` algorithm of `BaseTraitLibrary<T>`;
stats extracted from `BaseStats.set_Item` calls in `ActorTraitLibrary.addTraits*` methods
(`Assembly-CSharp.dll`).
"""
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
        if not entry:
            print(f'unknown: {tid}', file=sys.stderr)
            exit_code = 1
            continue
        stats = ','.join(f'{k}={v}' for k, v in sorted(entry.get('stats', {}).items()))
        print(f"{tid} | {entry['rarity']} | {entry['description']} | {entry['flavor']} | {stats}")
    return exit_code


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
