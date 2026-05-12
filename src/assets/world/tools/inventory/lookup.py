#!/usr/bin/env python3
"""Look up equipped items by ID in a `map.wbox`.

Usage:
    python3 lookup.py <map.wbox> <id> [<id> ...]

For each requested ID (from an actor's `saved_items`), prints `id | rarity`.
Unknown IDs are reported on stderr.

Rarity rule (cf. wiki Equipment#Rarity): max level among leveled modifiers in `items[].modifiers`
(`name1`..`name5`). Special non-leveled modifiers (`stun`, `flame`, `ice`, `cursed`, `slowness`,
`eternal`, `divine_rune`, `poison`, `normal`) don't count.

    max level >= 5 -> Legendary
    max level >= 4 -> Epic
    max level >= 3 -> Rare
    otherwise     -> Normal
"""
import json
import re
import sys
import zlib
from pathlib import Path

LEVEL_RE = re.compile(r'(\d+)$')


def rarity(modifiers: list[str]) -> str:
    levels = [int(m.group(1)) for m in (LEVEL_RE.search(x) for x in modifiers) if m]
    max_level = max(levels) if levels else 0
    if max_level >= 5: return 'Legendary'
    if max_level >= 4: return 'Epic'
    if max_level >= 3: return 'Rare'
    return 'Normal'


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__, file=sys.stderr)
        return 2
    map_path = Path(argv[0])
    with map_path.open('rb') as f:
        save = json.loads(zlib.decompress(f.read()))
    items_by_id = {it['id']: it for it in save['items']}
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
        print(f"{iid} | {rarity(item.get('modifiers', []))}")
    return exit_code


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
