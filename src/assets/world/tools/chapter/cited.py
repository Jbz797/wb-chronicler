#!/usr/bin/env python3

# Where the chronicle names something: each sentence of its chapters that carries a tag, `p46`, or a phrase as the sentence reads, `la reine` — whole,
# with its chapter and line, where a `git grep` hands back a paragraph to cut by hand. `--around` adds the sentences beside it, within its paragraph.

import re
import sys
from argparse import ArgumentTypeError
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))

from shared import SAVES_DIR, TAG_MARK, emit, hand_usage, latest_chapter, limit_arg, unmarked

_LIMIT = 10  # the sentences kept unless `--limit` says otherwise: the latest, where the story stands

# A sentence of a line, its closing quote kept with it: it ends where a capital, a dash or a tag follows, never before a word going on (`demanda-t-elle`)
_SENTENCE = re.compile(r"\S.*?(?:[.!?…]+(?:\s?[»”])?(?=\s+[^a-zà-ÿ\s]|\s*$)|$)")

_TAG = re.compile(r"\[?([a-z]) ?(\d+)(?: [^\]]*)?\]?")  # `p46`, as `--to` aims at one, or the tag as the prose writes it: `[p 46 `, `[p 46 Name]`
_USAGE = "usage: chapter/cited.py <p46|phrase> [--around n] [--limit n|all] [C<n>]\neach field and option: `gloss chapter.cited`"


# Each sentence that names `sought`, chapter by chapter up to `upto`, with `around` neighbours each side: a tag by its letter and id, a phrase by its words.
def _cited(sought: str, upto: int, around: int) -> list[dict]:
    if tag := _TAG.fullmatch(sought.strip()):
        kind, tag_id = tag.groups()

        def names(sentence: str) -> bool:
            return any(mark["kind"] == kind and mark["id"] == tag_id for mark in TAG_MARK.finditer(sentence))
    else:
        phrase = sought.casefold()

        def names(sentence: str) -> bool:
            return phrase in unmarked(sentence).casefold()  # the sentence as it reads, a tag by its name: `la reine`, `Creaker` alike

    rows = []
    for n in range(1, upto + 1):
        if not (path := SAVES_DIR / f"C{n}" / "chapter.md").exists():
            continue
        for number, line in enumerate(path.read_text().splitlines(), 1):
            sentences = _SENTENCE.findall(line)
            rows += (
                {"chapter": f"C{n}", "line": number, "text": " ".join(sentences[max(i - around, 0) : i + around + 1])}
                for i, sentence in enumerate(sentences)
                if names(sentence)
            )
    return rows


# The value of `flag` taken out of the call, the rest left as they were — `None` unasked.
def _taken(argv: list[str], flag: str) -> tuple[str | None, list[str]]:
    if flag not in argv:
        return None, argv
    at = argv.index(flag)
    return (argv[at + 1] if at + 1 < len(argv) else ""), argv[:at] + argv[at + 2 :]


def main(argv: list[str]) -> int:
    around, argv = _taken(argv, "--around")
    limit, argv = _taken(argv, "--limit")
    chapter = next((arg for arg in argv if arg[:1] == "C" and arg[1:].isdigit()), None)
    words = [arg for arg in argv if arg != chapter]
    if len(words) != 1 or words[0].startswith("-"):
        return hand_usage(_USAGE, words)
    if around is not None and not around.isdigit():
        print(f"✗ `--around {around}`: a number of sentences each side", file=sys.stderr)
        return 2
    try:
        kept = _LIMIT if limit is None else limit_arg(limit)
    except ArgumentTypeError as e:
        print(f"✗ --limit: {e}", file=sys.stderr)
        return 2
    if not (rows := _cited(words[0], int(chapter[1:]) if chapter else latest_chapter(), int(around or 0))):
        print(f"✗ no sentence of the chronicle names `{words[0]}`", file=sys.stderr)
        return 1
    if kept and len(rows) > kept:
        print(f"⚠ sentences: {len(rows)}, the latest {kept} — `--limit all` for every one", file=sys.stderr)
        rows = rows[-kept:]
    emit(rows)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
