#!/usr/bin/env python3

# Geographic stats reserved for the chronicler (not consumed by the UI). User-facing docs: `tools/tools.md`.

import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).parent.parent))
from shared import CURRENT_SAVE, emit, load_save, parse_sections  # noqa: E402
from islands import compute_islands_cached  # noqa: E402

_ALL_SECTIONS = ("islands",)


def main(argv: list[str]) -> int:
    try:
        sections = parse_sections(argv[0] if argv else None, _ALL_SECTIONS, accept_full=False)
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 2
    save = load_save()
    out: dict = {}
    if "islands" in sections:
        islands, _ = compute_islands_cached(save, CURRENT_SAVE)
        out["islands"] = islands
    emit(out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
