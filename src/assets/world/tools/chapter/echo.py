#!/usr/bin/env python3

# What a chapter says again, for `chronicler.md` § V « Ne te répète pas »: each passage it takes back from the two chapters before — a run of words, a
# rare word framed alike, a chute —, the runs it says twice itself, and the families it leans on past anything the chronicle did before. It points, the
# eye judges: an angle taken again slips past it, a refrain meant as one is caught all the same.

import json
import re
import sys
from collections import Counter, defaultdict
from functools import cache
from pathlib import Path
from typing import NamedTuple

sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))

from shared import SAVES_DIR, emit, latest_chapter

_CHUTE_WORDS = 2  # rare words a sentence must share with a section's last one to take it up again — a chute taken again is taken short
_FAMILY_FLOOR = 8  # uses under which no family is weighed: a word said 6 times in 14 000 characters is no tic, whatever the chapters before did
_FAMILY_ROOT = 5  # letters a family is known by — `compte`, `comptes`, `compter`, `comptées` under `compt` — a crude stem that French forgives well enough
_MARKS = re.compile(r"[*_#>|`]")  # emphasis, headings, quotes and table rules: markup, which no reader hears
_MIN_RUN = 4  # words a shared run must hold: three are the language's own (« il n'y a »), four start to be a turn of phrase
_OVERUSE = 1.3  # how far past the chronicle's own highest rate a family must climb to be named: a wobble is not a tic
_RARE = 3  # uses across the whole chronicle under which a word shared with the two chapters before is an image borrowed, not the language
_REFRAIN = 3  # Chapters a run of words must be said in to be the chronicle's own refrain — `par la taille`, `n'obéissent à rien` — told apart, never dropped.
_SCARCE = 8  # uses across the whole chronicle under which a word can carry a chute: `monde` or `terre` would join any two sentences
_SECTION = re.compile(r"^(##\s|---\s*$)")  # a heading or a separator: where a section, and so its chute, ends
_SENTENCE = re.compile(r"(?<=[.!?…])\s+")  # where a sentence ends inside a line
_TAG = re.compile(r"\[[a-z] [^\s\]]+(?: ([^\]]+))?\]")  # `[p 28 Voxzen]` read as its text, as `new.py` reads a title: a bare marker says nothing
_WORD = re.compile(r"\b[^\W\d_]{1,2}['’]|[\w-]+(?:['’][\w-]+)*")  # an elision splits, `qu'il` as `qu'` and `il`; `aujourd'hui` and `jusqu'à` hold


class _Token(NamedTuple):
    content: bool  # a word that says something of its own, told once at reading: `_content`
    key: str  # the word as compared: lower-case, its elision's apostrophe gone
    line: int
    name: bool  # a tag's text or a capitalised word: a name, which returns by nature
    surface: str  # the word as written, to show a run as the chapter says it


# Chronicle-rare words taken from chapter `before` between the same neighbours — `au flanc de celui` against `au flanc de ceux` —, as (line, line before, word)
def _borrowed(words: list[_Token], before: int) -> list[tuple[int, int, str]]:
    rare = _rare()
    earlier = _words(before)
    framed = {(token.key, _frame(earlier, i)): token.line for i, token in enumerate(earlier) if token.key in rare}
    taken: dict[str, tuple[int, int]] = {}
    for i, token in enumerate(words):
        if token.key in rare and not token.name and (at := framed.get((token.key, _frame(words, i)))) is not None:
            taken.setdefault(token.key, (token.line, at))
    return [(line, at, word) for word, (line, at) in taken.items()]


# The chapter's sentence pairs sharing scarce words with a section's last sentence in chapter `before`: `s'ils dormaient` answered by `[…]. Ils dormaient.`
def _chutes(n: int, before: int) -> list[tuple[int, int, frozenset[str]]]:
    out = []
    for at, chute in _section_ends(before):
        if len(said := {t.key for t in chute if t.key in _scarce() and t.content}) >= _CHUTE_WORDS:
            out += [(line, at, shared) for line, words in _heard(n) if len(shared := said & words) >= _CHUTE_WORDS]
    return out


# A word that says something of its own: neither short, common, a number, a unit of measure, a name nor a species — `loups`, `mouches` return by nature.
def _content(word: str, name: bool) -> bool:
    return len(word) >= 4 and word not in _plain() and not word.isdigit() and not name and word[:4] not in _species_roots()


# The words just before and after word `i`, as a pair: a borrowing keeps both — `au flanc de` —, where one alone is too often the language's `le` or `de`.
def _frame(words: list[_Token], i: int) -> tuple[str, str]:
    return words[i - 1].key if i else "", words[i + 1].key if i + 1 < len(words) else ""


# Chapter `n` sentence by sentence, each heard with the next of its paragraph, as the scarce words it carries — what a chute taken up short is sought in.
@cache
def _heard(n: int) -> list[tuple[int, frozenset[str]]]:
    sentences = _sentences(n)
    out = []
    for (line, sentence), (after_line, after) in zip(sentences, [*sentences[1:], (0, None)], strict=True):
        heard = [*(sentence or ()), *(after or () if after_line == line else ())]
        if sentence and (words := frozenset(t.key for t in heard if t.key in _scarce() and t.content)):
            out.append((line, words))
    return out


# A file of `i18n/<lang>/`, in the chronicle's language as the settings name it — `{}` where that language has none, the tool then only the chattier.
@cache
def _i18n(name: str) -> dict:
    world = Path(__file__).parents[2]
    settings = world / "history" / "settings.json"
    lang = (json.loads(settings.read_text()) if settings.exists() else {}).get("lang") or "fr"
    path = world / "i18n" / lang / name
    return json.loads(path.read_text()) if path.exists() else {}


# A shown run's words as compared, to tell which rare words it already carries.
def _keys(text: str) -> set[str]:
    return {word.lower().rstrip("'’") for word in _WORD.findall(text)}


# Chapter `n` read once, line by line: its number, whether it is a section's edge (a heading, a separator), and its sentences as tokens.
@cache
def _lines(n: int) -> list[tuple[int, bool, list[list[_Token]]]]:
    path = SAVES_DIR / f"C{n}" / "chapter.md"
    lines = enumerate(path.read_text().splitlines(), 1) if path.exists() else ()
    return [(number, bool(_SECTION.match(line)), [tokens for part in _SENTENCE.split(line) if (tokens := _tokens(part, number))]) for number, line in lines]


# Families past the chronicle's highest rate, from 2 chapters before, none it all but never used: `lignée` must overflow the chapter first telling lineages
def _overused(words: list[_Token], n: int) -> list[dict]:
    def rates(chapter_words: list[_Token]) -> tuple[Counter, Counter, int]:
        roots, forms = Counter(), Counter()
        for token in chapter_words:
            if len(token.key) >= _FAMILY_ROOT and token.content:
                roots[token.key[:_FAMILY_ROOT]] += 1
                forms[token.key] += 1
        return roots, forms, len(chapter_words) or 1

    if n < 3:
        return []
    roots, forms, size = rates(words)
    history = {k: (roots_then, total) for k in range(1, n) for roots_then, _, total in (rates(_words(k)),)}
    out = []
    for root, count in roots.items():
        if count < _FAMILY_FLOOR:
            continue
        peak_rate, peak_count, peak_in = max((then[root] / total, then[root], f"C{k}") for k, (then, total) in history.items())
        if peak_count > 1 and count / size > peak_rate * _OVERUSE and count > peak_count:
            used = sorted({form for form in forms if form.startswith(root)}, key=lambda form: (-forms[form], form))
            out.append({"count": count, "family": root, "forms": used[:4], "most_before": {"chapter": peak_in, "count": peak_count}})
    return sorted(out, key=lambda row: -row["count"])


# Each line's take from the 2 chapters before, one entry per chapter, each match with its line and signs; a chapter a stronger one covers is dropped
def _passages(words: list[_Token], n: int) -> list[dict]:
    found: defaultdict[tuple[int, int], list[dict]] = defaultdict(list)
    for before in range(n - 2 or 1, n):
        for (line, at), texts in _runs(words, _words(before)).items():
            found[line, before] += [{"by": {"echo", *(("refrain",) if _refrain(text) else ())}, "from": at, "text": text} for text in texts]
        for line, at, word in _borrowed(words, before):
            # A borrowed word inside a run from the same line is told on that run, never on its own with nothing new to show
            carried = [m for m in found[line, before] if m["from"] == at and "text" in m and word in _keys(m["text"])]
            if not carried:
                carried = [{"by": set(), "from": at, "word": word}]
                found[line, before] += carried
            for match in carried:
                match["by"].add("borrowed")
        for line, at, shared in _chutes(n, before):  # told on the run already showing its words, else one match per line it comes from
            same = [m for m in found[line, before] if m["from"] == at and ("chute" in m["by"] or shared <= _keys(m.get("text", "")))]
            if match := next((m for m in same if "text" in m), None) or next(iter(same), None):
                match.setdefault("words", set()).update(() if "text" in match else shared)
            else:
                found[line, before].append(match := {"by": set(), "from": at, "words": set(shared)})
            match["by"] |= {"chute", *(("refrain",) if _refrain_chute(frozenset(match.get("words") or shared)) else ())}
    out, shown = [], defaultdict(set)  # per line, the words its stronger chapters already show
    for (line, before), matches in sorted(found.items(), key=lambda item: (item[0][0], [-rank for rank in _weight(item[0][1], item[1])])):
        heard = {key for match in matches for key in (_keys(match["text"]) if "text" in match else {match.get("word"), *match.get("words", ())})}
        if heard <= shown[line]:
            continue
        shown[line] |= heard
        matches = [{**m, "by": sorted(m["by"]), "words": sorted(m.get("words") or ())} for m in sorted(matches, key=lambda m: m["from"])]
        out.append({"chapter": f"C{before}", "line": line, "matches": matches})
    return out


# The words too common to make two runs a turn of phrase or a family worth counting, and the units a measure is said in — `words.json`, per language.
@cache
def _plain() -> frozenset[str]:
    words = _i18n("words.json")
    return frozenset((*words.get("measures", ()), *words.get("stop", ())))


# The words the chronicle uses at most `_RARE` times, long enough to be more than a particle: those a borrowed image can be known by.
@cache
def _rare() -> frozenset[str]:
    return frozenset(word for word, count in _uses().items() if count <= _RARE and len(word) >= _FAMILY_ROOT)


# Whether a shown run holds `_MIN_RUN` words the chronicle says in `_REFRAIN` chapters or more: its own voice, which the eye weighs apart from a repeat.
def _refrain(text: str) -> bool:
    keys = [word.lower().rstrip("'’") for word in _WORD.findall(text)]
    return any(tuple(keys[i : i + _MIN_RUN]) in _refrains() for i in range(len(keys) - _MIN_RUN + 1))


# Whether a chute's words are heard together in `_REFRAIN` chapters of the chronicle or more — `voit court` in C2, C3 and C4: its refrain, not a repeat.
def _refrain_chute(words: frozenset[str]) -> bool:
    return sum(any(words <= heard for _, heard in _heard(k)) for k in range(1, latest_chapter() + 1)) >= _REFRAIN


# Every telling run of `_MIN_RUN` words said in `_REFRAIN` chapters of the chronicle or more: `de ce monde ne` is the language's, whatever its count.
@cache
def _refrains() -> frozenset[tuple[str, ...]]:
    said: defaultdict[tuple[str, ...], set[int]] = defaultdict(set)
    for k in range(1, latest_chapter() + 1):
        words = _words(k)
        for i in range(len(words) - _MIN_RUN + 1):
            if (run := words[i : i + _MIN_RUN])[0].line == run[-1].line and _telling(run):
                said[tuple(token.key for token in run)].add(k)
    return frozenset(run for run, chapters in said.items() if len(chapters) >= _REFRAIN)


# Widened runs of `_MIN_RUN`+ words shared with `earlier`, keyed (line, line said first); against itself, a run counts only where an earlier line said it
def _runs(words: list[_Token], earlier: list[_Token]) -> dict[tuple[int, int], list[str]]:
    within = earlier is words
    seen: dict[tuple[str, ...], int] = {}
    for i in range(len(earlier) - _MIN_RUN + 1):
        if earlier[i].line == earlier[i + _MIN_RUN - 1].line:
            seen.setdefault(tuple(token.key for token in earlier[i : i + _MIN_RUN]), earlier[i].line)

    def said_at(i: int) -> int | None:
        if words[i].line != words[i + _MIN_RUN - 1].line:  # a run never spans two lines: a heading sewn to the paragraph under it was never written so
            return None
        at = seen.get(tuple(token.key for token in words[i : i + _MIN_RUN]))
        return at if at is not None and (not within or at < words[i].line) else None

    runs: dict[tuple[int, int], list[str]] = {}
    i = 0
    while i <= len(words) - _MIN_RUN:
        if (at := said_at(i)) is None:
            i += 1
            continue
        end = i + _MIN_RUN
        while end < len(words) and said_at(end - _MIN_RUN + 1) is not None:
            end += 1
        if _telling(run := words[i:end]):
            runs.setdefault((run[0].line, at), []).append("".join(t.surface + ("" if t.surface[-1] in "'’" else " ") for t in run).strip())
        i = end
    return runs


# The words the chronicle uses at most `_SCARCE` times: those a chute can be known by.
@cache
def _scarce() -> frozenset[str]:
    return frozenset(word for word, count in _uses().items() if count <= _SCARCE)


# The last sentence of each section of chapter `n`, the closing's included, with its line: what a chapter lands on, and so what a later one may take up again.
def _section_ends(n: int) -> list[tuple[int, list[_Token]]]:
    ends, last = [], None
    for line, sentence in _sentences(n):
        if sentence is None:  # a section's edge: the sentence met just before it closed that section
            if last is not None:
                ends.append(last)
            last = None
        else:
            last = (line, sentence)
    return ends + ([last] if last is not None else [])


# Chapter `n` sentence by sentence, each with its line — a heading or a separator yielded as `None`, the edge a section ends on.
def _sentences(n: int) -> list[tuple[int, list[_Token] | None]]:
    return [pair for number, edge, sentences in _lines(n) for pair in ([(number, None)] if edge else [(number, tokens) for tokens in sentences])]


# The species as the chronicle names them in its own language, by their first four letters — `loup` catches `loups`, `mouc` catches `mouches`.
@cache
def _species_roots() -> frozenset[str]:
    names = _i18n("species.json").values()
    return frozenset(word[:4].lower() for name in names for word in re.findall(r"[\wÀ-ÿ-]+", name) if len(word) >= 4)


# The words a run must carry to be a turn of phrase rather than the language: two that say something of their own.
def _telling(run: list[_Token]) -> bool:
    return sum(token.content for token in run) >= 2


# A stretch of prose as tokens: markup gone, a tag's text kept and marked as a name, an elision split from the word it leans on.
def _tokens(text: str, number: int) -> list[_Token]:
    names = {word.lower().rstrip("'’") for tag in _TAG.finditer(text) for word in _WORD.findall(tag[1] or "")}
    out = []
    for word in _WORD.findall(_MARKS.sub(" ", _TAG.sub(lambda m: m[1] or "", text))):
        key = word.lower().rstrip("'’")
        name = key in names or word[:1].isupper()
        out.append(_Token(_content(key, name), key, number, name, word))
    return out


# Every word of the chronicle's chapters on disk and how often it is used: rarity is the chronicle's, not the window's, so a chapter's own terms never read as rare.
@cache
def _uses() -> Counter:
    return Counter(t.key for k in range(1, latest_chapter() + 1) for t in _words(k) if t.content)


# How strongly chapter `before` is heard on a line: its signs, its nearness, how many matches it has.
def _weight(before: int, matches: list[dict]) -> tuple[int, int, int]:
    return len(set().union(*(match["by"] for match in matches)) - {"refrain"}), before, len(matches)


# A chapter as the reader hears it, word by word, each with its line.
@cache
def _words(n: int) -> list[_Token]:
    return [token for _, _, sentences in _lines(n) for tokens in sentences for token in tokens]


# What chapter `n` says again, `None` where there is no chapter or none before it — `new.py --finalize` counts it before the audit reads the chapter.
def echoes(n: int) -> dict | None:
    if n < 2 or not (words := _words(n)):
        return None
    again: defaultdict[int, list[dict]] = defaultdict(list)  # `line` the one saying it again, `from` the line that said it first
    for (line, at), texts in sorted(_runs(words, words).items()):
        again[line] += [{"from": at, "text": text} for text in texts]
    internal = [{"line": line, "matches": matches} for line, matches in again.items()]
    return {"internal": internal, "overused": _overused(words, n), "passages": _passages(words, n)}


def main(argv: list[str]) -> int:
    chapter = next((arg for arg in argv if arg[:1] == "C" and arg[1:].isdigit()), None)
    n = int(chapter[1:]) if chapter else latest_chapter()
    if (found := echoes(n)) is None:
        print(f"✗ no chapter.md for C{n}" if n > 1 else "✗ C1 has no chapter before it to take back from", file=sys.stderr)
        return 1
    emit(found)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
