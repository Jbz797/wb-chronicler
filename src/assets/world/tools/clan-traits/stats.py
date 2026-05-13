#!/usr/bin/env python3
"""Look up clan traits by ID.

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
# Stats extracted from `library.t.base_stats.set_Item` calls in `ClanTraitLibrary.init` IL.
# Pattern: after `library.add(trait)` (sets `library.t` to the last-added entry), sequences of
# `ldfld library.t.base_stats ; ldstr <stat> ; ldc.r4|ldc.i4 <val> ; callvirt set_Item` assign
# each stat. Trait boundary is detected via `ldstr <id> ; stfld id` (the asset's id field).
# Float values rounded to 4 decimals; integer-equivalents cast to int.
#
# Most clan traits carry a single numeric stat (warfare, damage, multiplier_*, ...). Some are
# purely behavioral (limits, decisions, opposites) and end up with empty stats.
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _lib import trait_lookup_main

DATA = Path(__file__).parent / 'data.json'


if __name__ == '__main__':
    sys.exit(trait_lookup_main(DATA, sys.argv[1:], __doc__ or ''))
