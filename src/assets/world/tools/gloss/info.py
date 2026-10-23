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


# One key's glosses, or its refusal told: the fields it names, a tool's whole with the shared ones, or the neighbour whose gloss tells it.
def _found(wanted: str, glosses: dict[str, str], segmented: dict[str, list[str]]) -> dict[str, str]:
    asked = wanted.split(".")
    # The bare keys a tool shares, on what is asked of it: all for the whole tool (`actor` its `crow_tiles`), a section's own (`actor.traits`, `traits.absorbed`).
    section = asked[1:] if asked[0] in _TOOLS else None
    found = {
        key: glosses[key]
        for key, segments in segmented.items()
        if _holds(segments, asked) or (section is not None and segments[0] not in _TOOLS and segments[: len(section)] == section)
    }
    # A field that has no key of its own is told inside a neighbour's gloss: `their_opinion` within `opinion`'s, `was_at` within `gone`'s.
    found = found or {key: gloss for key, gloss in glosses.items() if f"`{asked[-1]}`" in gloss}
    if not found:
        words = sorted({segment for segments in segmented.values() for segment in segments})
        near = difflib.get_close_matches(asked[-1], words, n=_NEAR) or difflib.get_close_matches(wanted, sorted(glosses), n=_NEAR)
        print(f"✗ no gloss for `{wanted}`" + (f" — near it: {', '.join(near)}" if near else " — the field says what it is"), file=sys.stderr)
    return found


# Whether the asked segments run inside the key's, in order and unbroken: `pairings.lovers` in `world.pairings.lovers`, never `world.lovers`.
def _holds(key: list[str], asked: list[str]) -> bool:
    return any(key[at : at + len(asked)] == asked for at in range(len(key) - len(asked) + 1))


def main(argv: list[str]) -> int:
    parser = arg_parser(prog="gloss/info.py", description="Gloss a field of the tools' outputs.")
    parser.add_argument("field", help="a field, `section.field` or `tool.section.field`, as `gloss:<key>` names it — several by commas")
    args = parser.parse_args(argv)
    glosses: dict[str, str] = json.loads(_FIELDS.read_text(encoding="utf-8"))
    for key, gloss in glosses.items():  # checked at every run: a gloss past the cap is a doc to cut, and only a run sees it
        if len(gloss) > _CAP:
            print(f"✗ {key}: {len(gloss)} characters, past {_CAP} — cut it in tools/gloss/fields.json", file=sys.stderr)
    segmented, found, missed = {key: key.split(".") for key in glosses}, {}, False
    for wanted in dict.fromkeys(args.field.split(",")):  # several asked at once, each gloss told once: tools share their fields
        got = _found(wanted.removeprefix("gloss:"), glosses, segmented)  # the docs write a key as `gloss:<key>`, and that prefix is no part of it
        found, missed = found | got, missed or not got
    if not found:
        return 1
    found = {key: glosses[key] for key in glosses if key in found}  # in the file's order, whatever order they were asked in
    print(render(found))
    return 1 if missed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
