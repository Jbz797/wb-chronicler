#!/usr/bin/env python3

# Glosses a field of the tools' outputs from `fields.json` beside it, one sentence of at most 165 characters each. User-facing docs: `docs/tools.md`.
# A key reads `<tool>.<section>.<field>`, or bare when several tools share the field; any run of its segments finds it: `pairings` hands back the whole section.

import difflib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))

from shared import arg_parser, render

_CAP = 165  # characters a gloss holds at most: one line of the chronicler's, never a paragraph
_FIELDS = Path(__file__).with_name("fields.json")
_NEAR = 5  # keys a refusal offers
_TOOLS = frozenset(path.parent.name for path in Path(__file__).parents[1].glob("*/*.py")) - {"lib"}  # a key's first segment when it names one


# Whether the asked segments run inside the key's, in order and unbroken: `pairings.lovers` in `world.pairings.lovers`, never `world.lovers`.
def _holds(key: list[str], asked: list[str]) -> bool:
    return any(key[at : at + len(asked)] == asked for at in range(len(key) - len(asked) + 1))


def main(argv: list[str]) -> int:
    parser = arg_parser(prog="gloss/info.py", description="Gloss a field of the tools' outputs.")
    parser.add_argument("field", help="a field, `section.field` or `tool.section.field`, as `gloss:<key>` names it")
    args = parser.parse_args(argv)
    glosses: dict[str, str] = json.loads(_FIELDS.read_text(encoding="utf-8"))
    for key, gloss in glosses.items():  # checked at every run: a gloss past the cap is a doc to cut, and only a run sees it
        if len(gloss) > _CAP:
            print(f"✗ {key}: {len(gloss)} characters, past {_CAP} — cut it in tools/gloss/fields.json", file=sys.stderr)
    wanted = args.field.removeprefix("gloss:")  # the docs write a key as `gloss:<key>`, and that prefix is no part of it
    asked, segmented = wanted.split("."), {key: key.split(".") for key in glosses}
    # A tool asked whole brings the fields it shares with the others, keyed bare, `actor` its `crow_tiles` with it: one call before the first read of its output.
    shared = len(asked) == 1 and asked[0] in _TOOLS
    found = {key: glosses[key] for key, segments in segmented.items() if _holds(segments, asked) or (shared and segments[0] not in _TOOLS)}
    # A field that has no key of its own is told inside a neighbour's gloss: `their_opinion` within `opinion`'s, `was_at` within `gone`'s.
    found = found or {key: gloss for key, gloss in glosses.items() if f"`{asked[-1]}`" in gloss}
    if not found:
        words = sorted({segment for segments in segmented.values() for segment in segments})
        near = difflib.get_close_matches(asked[-1], words, n=_NEAR) or difflib.get_close_matches(wanted, sorted(glosses), n=_NEAR)
        print(f"✗ no gloss for `{wanted}`" + (f" — near it: {', '.join(near)}" if near else " — the field says what it is"), file=sys.stderr)
        return 1
    print(render(found))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
