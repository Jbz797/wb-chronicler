"""Shared utilities for tool scripts — kept intentionally tiny.

Imported from sibling tool folders via:
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from _lib import ...
"""
import json
import sys
import zlib
from pathlib import Path

# macOS path — mirror chronicler.md § "Emplacement source des saves WorldBox".
CURRENT_SAVE = Path.home() / 'Library/Application Support/mkarpenko/WorldBox/saves/save1/map.wbox'


def load_save() -> dict:
    with CURRENT_SAVE.open('rb') as f:
        return json.loads(zlib.decompress(f.read()))


# Shared body for clan / language / subspecies trait stats scripts: each holds a
# `{trait_id: {stats: {k:v}}}` JSON file and prints `id | stats` per requested ID.
def trait_lookup_main(data_path: Path, argv: list[str], doc: str) -> int:
    if not argv:
        print(doc, file=sys.stderr)
        return 2
    with data_path.open() as f:
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
