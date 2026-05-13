#!/usr/bin/env python3
"""Look up language traits by ID.

Usage: python3 stats.py <id> [<id> ...]

Prints `id | stats` per ID — `stats` is `k=v` pairs (alphabetical, empty when none).
Unknown IDs reported on stderr.
"""
# ─── Maintenance / re-extraction notes ───
# `data.json` is rebuilt from `Assembly-CSharp.dll` (macOS):
#   $HOME/Library/Application Support/Steam/steamapps/common/worldbox/worldbox.app/
#       Contents/Resources/Data/Managed/Assembly-CSharp.dll
# Toolchain: `dncil` (IL decoder), `dnfile` (PE/metadata parser).
#
# Stats extracted from `library.t.base_stats.set_Item` calls in `LanguageTraitLibrary.init` IL.
# Pattern: after `library.add(trait)` (sets `library.t` to the last-added entry), sequences of
# `ldfld library.t.base_stats ; ldstr <stat> ; ldc.r4|ldc.i4 <val> ; callvirt set_Item` assign
# each stat. Trait boundary is detected via `ldstr <id> ; stfld id` (the asset's id field).
# Float values rounded to 4 decimals; integer-equivalents cast to int.
#
# Most language traits are behavioral (alphabet, calligraphy, decision triggers...) and carry
# no numeric stat. Only a handful contribute directly to intelligence / warfare / lifespan /
# offspring.
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
        print(f"{tid} | {stats}")
    return exit_code


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
