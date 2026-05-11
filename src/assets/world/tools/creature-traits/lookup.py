#!/usr/bin/env python3
"""Look up creature traits by ID.

Usage:
    python3 lookup.py <trait_id> [<trait_id> ...]

Reads `data.json` (sibling file) and prints `id | rarity | description` for each requested ID.
Unknown IDs are reported on stderr. Data source: game assets only — IDs/names/descriptions from the `traits_units` TextAsset (EN locale), rarity reconstructed from the `autoSetRarity` algorithm of `BaseTraitLibrary<T>` in `Assembly-CSharp.dll`.
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
        print(f"{tid} | {entry['rarity']} | {entry['description']}")
    return exit_code


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
