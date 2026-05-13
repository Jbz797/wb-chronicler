#!/usr/bin/env python3
"""Look up subspecies traits by ID.

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
# Stats extracted from `BaseStats.set_Item` calls in `SubspeciesTraitLibrary.add*` IL bodies
# (`addStats`, `addLimits`, `addMaturation`, `addAdaptations`, `addMagic`, `addChaos`,
# `addMetamorphosis`, `addSpawnSomething`, `addSleepCycles`, `addOther`, `addReproductionModes`,
# `addReproduction`, `addDiet`, `addGenetic`, `addMutations`, `addEggs`, `addPhenotypes`,
# `addMutationOpposites`, `addEggOpposites`).
#
# Pattern: after `library.add(trait)`, sequences of `ldfld library.t.base_stats ; ldstr <stat>
# ; ldc.r4|ldc.i4 <val> ; callvirt set_Item` assign each stat to the most-recently-added trait.
# Float values rounded to 4 decimals; integer-equivalents cast to int.
#
# Important: most subspecies traits (~106/113) are **behavioral only** — they affect game
# logic (reproduction strategy, diet, mutations…) without contributing numeric stats. Only 7
# carry stat values (e.g. `hyper_intelligence` → intelligence=30, `long_lifespan` → lifespan=100).
#
# `data.json` was dumped with `sort_keys=True`, so `stats` dicts are already alphabetical;
# no runtime `sorted()` needed.
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
