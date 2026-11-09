#!/usr/bin/env python3

# Glosses a field or an option of the tools from `fields.json` beside it, one sentence of at most 165 characters each. User-facing docs: `docs/tools.md`.
# A key reads `<tool>.<section>.<field>` or `<tool>.--<option>`, bare when several tools share it; any run of its segments finds it: `pairing` the whole block.

import difflib
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))

from shared import arg_parser, render, run

_CAP = 165  # characters a gloss holds at most: one line of the chronicler's, never a paragraph
_FIELDS = Path(__file__).with_name("fields.json")
_NEAR = 5  # keys a refusal offers
_SLIP = 0.75  # how near a word unknown here must stand to a known one to read as its slip: a looser match would flag a real field
_TOOLS = frozenset(path.parent.name for path in Path(__file__).parents[1].glob("*/*.py")) - {"lib"}  # a key's first segment when it names one


# One key's glosses, or its refusal told: the fields it names, a tool's whole with the shared ones, or the neighbour whose gloss tells it.
def _found(wanted: str, glosses: dict[str, str], segmented: dict[str, list[str]]) -> dict[str, str]:
    asked = wanted.split(".")
    option = asked[-1].startswith("-")
    found = {key: glosses[key] for key, segments in segmented.items() if _within(segments, asked)}
    # A field with no key is told in a gloss of its section (`their_opinion` in `opinion`'s), an option by its alias (`-i`) or by the field it fills: searched wider.
    cited = re.compile(rf"`{re.escape(asked[-1])}{'[` ]' if option else '`'}")
    if not found and (found := {key: gloss for key, gloss in glosses.items() if cited.search(gloss) and _related(segmented, key, asked[:-1])}):
        print(f"· no key for `{asked[-1]}` — told within {', '.join(found)}", file=sys.stderr)
    if found:
        return found
    # The words this file knows: its keys' and those its glosses cite — one unknown yet near one of them is a slip, refused with it, never given its section's gloss
    known = {segment for segments in segmented.values() for segment in segments} | {word for gloss in glosses.values() for word in re.findall(r"`([\w-]+)`", gloss)}
    section = ".".join(asked[:-1])
    sectioned = len(asked) > 1 and section in glosses  # a field its section's gloss answers for: the one that says where its fields are told
    if asked[-1] not in known and (slip := difflib.get_close_matches(asked[-1], sorted(known), n=_NEAR, cutoff=_SLIP)):
        whole = f" — its section: `gloss {section}`" if sectioned else ""  # a real field never cited, read as a slip, still finds it
        print(f"✗ no gloss for `{wanted}` — near it: {', '.join(f'`{word}`' for word in slip)}?{whole}", file=sys.stderr)
        return found
    if sectioned:
        print(f"· no gloss of its own for `{asked[-1]}` — its section's", file=sys.stderr)
        return {section: glosses[section]}
    if homes := [key for key, segments in segmented.items() if segments[-1] == asked[-1]]:  # its keys named: a bare word would read as a match
        print(f"✗ no gloss for `{wanted}` — `{asked[-1]}` is glossed only as {', '.join(homes)}", file=sys.stderr)
        return found
    words = sorted({segment for segments in segmented.values() for segment in segments})
    near = difflib.get_close_matches(asked[-1], words, n=_NEAR) or difflib.get_close_matches(wanted, sorted(glosses), n=_NEAR)
    unglossed = " — `<tool> --help` lists its options" if option else " — the field says what it is"
    print(f"✗ no gloss for `{wanted}`" + (f" — near it: {', '.join(near)}" if near else unglossed), file=sys.stderr)
    return found


# Whether the asked segments run inside the key's, in order and unbroken: `pairing.lovers` in `subspecies.species.pairing.lovers`, never `species.lovers`.
def _holds(key: list[str], asked: list[str]) -> bool:
    return any(key[at : at + len(asked)] == asked for at in range(len(key) - len(asked) + 1))


# Whether a gloss citing the word may tell it: under a tool alone, its keys and the shared ones of its sections (`war` has no `leaders`), else the keys within.
def _related(segmented: dict[str, list[str]], key: str, parent: list[str]) -> bool:
    segments = segmented[key]
    if len(parent) == 1 and parent[0] in _TOOLS:
        return segments[0] == parent[0] or (segments[0] not in _TOOLS and any(other[:2] == [parent[0], segments[0]] for other in segmented.values()))
    return _within(segments, parent)


# Whether the key's segments run through the asked in order, on its very field: a level the output groups by (`common`, `fires`, `base`) is no part of a key.
def _threads(key: list[str], asked: list[str]) -> bool:
    rest = iter(asked)
    return key[-1] == asked[-1] and all(segment in rest for segment in key)


# Whether a key falls within the asked: held, threaded through it (`ground.spot`), a section's shared key, or a value of the field asked (`statuses.rage`).
def _within(key: list[str], asked: list[str]) -> bool:
    if key[0] in _TOOLS:
        return _holds(key, asked) or (asked[0] == key[0] and _threads(key, asked))
    return _holds(key, asked) or _threads(key, asked) or (asked[0] in _TOOLS and key[: len(asked) - 1] == asked[1:]) or key[0] == asked[-1] != asked[0]


def main(argv: list[str]) -> int:
    parser = arg_parser(prog="gloss/info.py")
    parser.add_argument("field", metavar="key,…")
    args = parser.parse_args(argv if argv[:1] in (["-h"], ["--help"]) else ["--", *argv])  # `gloss --since`: an option asked, not one given
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
    sys.exit(run(main))
