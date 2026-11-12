#!/usr/bin/env python3

# What a chapter says again, for `chronicler.md` § V « Ne te répète pas »: each passage it takes back from the two chapters before — a run of words, a
# rare word framed alike, a chute —, the runs it says twice itself and the terms it coins, the families it leans on past anything the chronicle did
# before, and the cast it is poured in again: a title, a heading, a section or paragraph begun alike. It points, the eye judges: an angle taken again slips past it.

import re
import sys
from collections import Counter, defaultdict
from functools import cache
from itertools import pairwise
from pathlib import Path
from typing import NamedTuple

sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))

from shared import (
    CHAPTER_CAP,
    COUNTED_AS,
    SAVES_DIR,
    TAG_MARK,
    chapter_floor,
    chapter_length,
    chronicle_git,
    emit,
    hand_usage,
    i18n,
    latest_chapter,
    short_dialogues,
    unmarked,
)

_CHUTE_WORDS = 2  # rare words a sentence must share with a section's last one to take it up again — a chute taken again is taken short
_DATE = "Dᴀᴛᴇ"  # a date as the chronicle must write one, read as a single name: the manual's own form, never a turn said again
_DETERMINERS = frozenset({"d", "de", "des", "du", "l", "la", "le", "les", "un", "une"})  # one mould whatever its article: `dans les lointains`, `dans des lointains`
_EXAMPLE = re.compile(r"_« (.+?) »_")  # how the manual and the lexicon write an example: an italic quote, cut where its `…` opens on the rest
_EXAMPLE_WORDS = 3  # words an example holds at least to be a mould: `du feu`, `une vingtaine` are the language's own
_FAMILY_FLOOR = 8  # uses under which no family is weighed: a word said 6 times in 12 000 characters is no tic, whatever the chapters before did
_FAMILY_ROOT = 5  # letters a family is known by — `compte`, `comptes`, `compter`, `comptées` under `compt` — a crude stem that French forgives well enough
_FORMULA_LINES = 4  # lines of one chapter a figured turn must come back on to be a tic: `il y a 3 ans` said on line after line
_FORMULA_WORDS = 3  # words a figured turn holds at least, the figure among them; from `_LONG_RUN_WITHIN` up, `internal` hears it already
_HEADING_START = 2  # words a heading is known by: `Loin d'elle` and `Loin d'elle, ce qui s'est éteint` open alike
_HEADING_WORDS = 2  # words of its own a heading must share with one before, in any order, to be cast again: `Les toits des rois`, `Les rois et leurs toits`

# A sentence opened on an inversion — `Peut-être a-t-elle`, `Sans doute compte-t-elle` —, its opener the one or two words before the verb.
_INVERTED = re.compile(
    r"(?P<opener>[^\W\d_][\w'’-]*(?:\s+[\w'’-]+)??)\s+(?:(?:ne|n['’]|y|en|se|s['’]|l['’]|le|la|les|lui|leur)\s*)*[\w'’]+-(?:t-)?(?:il|elle|on|ils|elles)\b"
)

_LONG_RUN = 7  # words from which a run is a turn of phrase with a single word of its own: `et ce qui verdit au ras du sol`, `à l'entrée de l'an 5`
_LONG_RUN_WITHIN = 6  # the same, within one chapter, where a formula said again ten lines on is heard: `jamais encore on n'avait vu`
_MARKS = re.compile(r"[*_#>|`]")  # emphasis, headings, quotes and table rules: markup, which no reader hears
_MIN_RUN = 4  # words a shared run must hold: three are the language's own (« il n'y a »), four start to be a turn of phrase
_NAMELESS = frozenset("grs")  # gear, resources and species: icons a chapter strews, no one whose angle can be told twice
_NEAR_ROOT = 4  # letters a family is known by when heard close: `bâti` takes `bâtir` and `bâtie`, which `_FAMILY_ROOT` splits; two merely alike cost a glance
_NEAR_SPAN = 2  # paragraphs running a family must come back in to be heard: a third doubles the count, `monde` and `venu` read as tics
_NEAR_USES = 3  # uses of one family in that span: twice is the language, thrice a reader hears it
_OPENING_START = 4  # words a section's first sentence is known by, a figure read as any other: `Voxzen est dans sa` 11ᵉ, then 13ᵉ année
_OPENING_WORDS = 2  # words of its own a chapter's first sentence must share with one before to pour its mould again: one alone is the chronicle's subject
_OVERUSE = 1.3  # how far past the chronicle's own highest rate a family must climb to be named: a wobble is not a tic
_RARE = 3  # uses across the whole chronicle under which a word shared with the two chapters before is an image borrowed, not the language
_RECENT = 6  # chapters before the one weighed that a mould is counted in: 3 of the 6 latest means the same at C11 as at C50, an old one resting out of it
_REFRAIN = 3  # chapters a run of words must be said in to be the chronicle's own refrain — `par la taille`, `n'obéissent à rien` — told apart, never dropped
_SCARCE = 8  # uses across the whole chronicle under which a word can carry a chute: `monde` or `terre` would join any two sentences
_SECTION = re.compile(r"^(##\s|---\s*$)")  # a heading or a separator: where a section, and so its chute, ends
_SENTENCE = re.compile(r"(?<=[.!?…])\s+")  # where a sentence ends inside a line
_TERM = 3  # lines of one chapter a turn must be said on to be a term it coined — `le bras du couchant`, a place with no name —, told apart as a refrain is

_WORD = re.compile(r"\b[^\W\d_]{1,2}['’]|\w[\w-]*(?:['’]\w[\w-]*)*")  # an elision splits, `qu'il` as `qu'` and `il`; `aujourd'hui` holds, `---` is none


class _Token(NamedTuple):
    content: bool  # a word that says something of its own, told once at reading: `_content`
    key: str  # the word as compared: `_key`
    line: int
    name: bool  # a tag's text or a capitalised word: a name, which returns by nature
    surface: str  # the word as written, to show a run as the chapter says it


# Each word family's count in the chapter at its last audited round: an overuse this retouch did not feed was weighed then, one it fed is news.
def _audited_roots(n: int) -> Counter:
    text = chronicle_git("show", f"{_last_round(n)}:C{n}/chapter.md").stdout
    tokens = (token for line in text.splitlines() for part in _SENTENCE.split(line) for token in _tokens(part, 0))
    return Counter(token.key[:_FAMILY_ROOT] for token in tokens if len(token.key) >= _FAMILY_ROOT and token.content)


# A name the chapter tags elsewhere, written bare on a line, headings included: a capitalised tag text alone, `la reine` being a reprise free of its tag.
def _bare(n: int) -> list[dict]:
    prose = _chapter(n) or ""
    tags: defaultdict[str, set[str]] = defaultdict(set)
    for tag in TAG_MARK.finditer(prose):
        if tag["kind"] not in _NAMELESS and (text := tag["text"]) and text[:1].isupper():
            tags[text].add(f"{tag['kind']} {tag['id']}")
    if not tags:
        return []
    spoken = re.compile("|".join(rf"(?<![\w-]){re.escape(name)}(?![\w-])" for name in sorted(tags, key=len, reverse=True)))  # the longest first
    rows = []
    for at, line in enumerate(prose.splitlines(), 1):
        for name in dict.fromkeys(found[0] for found in spoken.finditer(TAG_MARK.sub(lambda tag: " " * len(tag[0]), line))):
            one = next(iter(tags[name])) if len(tags[name]) == 1 else None  # two entities sharing a name: the tag is the chronicler's to pick
            rows.append({"line": at, "name": name, "tag": one})
    return rows


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


# The lines a delivered chapter has changed since its last audited round, off the chronicle's git tag — `None` before delivery, or with no git: weighed whole.
@cache
def _changed(n: int) -> set[int] | None:
    if (tag := _last_round(n)) is None:
        return None
    lines: set[int] = set()
    for start, count in re.findall(r"^@@ -\S+ \+(\d+)(?:,(\d+))? @@", chronicle_git("diff", "-U0", tag, "--", f"C{n}/chapter.md").stdout, re.MULTILINE):
        first, span = int(start), int(count or 1)
        lines.update(range(first, first + span) if span else (first,))  # a line cut leaves its neighbour to answer for it
    return lines


# Chapter `n` as written, read once for its length and its lines alike — `None` where it has none yet.
@cache
def _chapter(n: int) -> str | None:
    return path.read_text() if (path := SAVES_DIR / f"C{n}" / "chapter.md").exists() else None


# The chapter's sentence pairs sharing scarce words with a section's last sentence in chapter `before`: `s'ils dormaient` answered by `[…]. Ils dormaient.`
def _chutes(n: int, before: int) -> list[tuple[int, int, frozenset[str]]]:
    out = []
    for at, chute in _section_ends(before):
        if len(said := {t.key for t in chute if t.key in _scarce() and t.content}) >= _CHUTE_WORDS:
            out += [(line, at, shared) for line, words in _heard(n) if len(shared := said & words) >= _CHUTE_WORDS]
    return out


# A word that says something of its own: neither short, a figure (`N`) among them, common, a measure, a name nor a species — `loups`, `mouches` return by nature.
def _content(word: str, name: bool) -> bool:
    return len(word) >= 4 and word not in _plain() and not name and word[:4] not in _species_roots()


# The chronicle's dates, « en Crocojuin de l'an 13 », its months read in its own language: the form the manual dates by, which no repeat is made of.
@cache
def _dates() -> re.Pattern[str]:
    months = "|".join(map(re.escape, i18n("months.json").values()))
    return re.compile(rf"\b(?:(?:en|au|à)\s+)?(?:{months})\s+de\s+l['’]an\s+\d+", re.IGNORECASE)


# The manual's examples chapter `n` says, each at its first line, as written there: an example used is no fault, used again from chapter to chapter a mould.
@cache
def _example_lines(n: int) -> dict[tuple[str, ...], tuple[int, str]]:
    said: dict[tuple[str, ...], tuple[int, str]] = {}
    raw = (_chapter(n) or "").splitlines()
    for number, _, sentences in _lines(n):  # the tokens every other check reads, a line's sentences end to end
        if not (line := raw[number - 1]).strip() or line[0] in "|<#":
            continue
        tokens = [token for sentence in sentences for token in sentence]
        keys = _moulded(tokens)
        for example in _examples():
            span = len(example)
            if (at := next((i for i, key in enumerate(keys) if key == example[0] and keys[i : i + span] == example), None)) is not None:
                said.setdefault(example, (number, " ".join(token.surface for token in tokens[at : at + span])))
    return said


# The examples `chronicler.md` and `lexicon.md` give, articles levelled: none with a figure or a tag, a form the manual sets, nor too short to be a mould.
@cache
def _examples() -> frozenset[tuple[str, ...]]:
    docs, words = SAVES_DIR.parent / "docs", i18n("words.json")
    quoted = (found[1].split("…")[0] for doc in ("chronicler.md", "lexicon.md") for found in _EXAMPLE.finditer((docs / doc).read_text()))
    units, bearings = _measures() | frozenset(words.get("years", ())), frozenset(words.get("bearings", ()))

    # A form the manual sets, not a turn: a measure or a year (`il y a trois ans`), a bearing after its article (`à l'est`), said as asked.
    def set_form(key: tuple[str, ...]) -> bool:
        return any(word in units for word in key) or any(first == "·" and then in bearings for first, then in pairwise(key))

    keys = (_moulded(_tokens(text, 0)) for text in quoted if not re.search(r"[\d\[`]", text))
    return frozenset(key for key in keys if len(key) >= _EXAMPLE_WORDS and not set_form(key))


# A figured turn chapter `n` keeps coming back to — `il y a 3 ans`, `plus de 5` —, figures as one: a date or a measure aside, whose form the manual sets.
def _formulas(n: int) -> list[dict]:
    said: defaultdict[tuple[str, ...], dict[int, str]] = defaultdict(dict)
    for number, _, sentences in _lines(n):
        if number in _table_rows(n):
            continue
        for tokens in sentences:
            for at, token in enumerate(tokens):
                after = tokens[at + 1].key if at + 1 < len(tokens) else ""
                if token.key != "N" or after in _measures() or (at and tokens[at - 1].key == "an"):
                    continue
                for size in range(_FORMULA_WORDS, _LONG_RUN_WITHIN):
                    for start in range(max(0, at - size + 1), min(at, len(tokens) - size) + 1):
                        run = tokens[start : start + size]
                        if not any(t.name for t in run[1:]):  # a name inside is a tag's or a place's, said again by nature; a capital first is a sentence's
                            said[tuple(t.key for t in run)].setdefault(number, " ".join(t.surface for t in run))
    kept = {run: lines for run, lines in said.items() if len(lines) >= _FORMULA_LINES}
    # A turn held whole by a longer one on the same lines is that one, told once.
    longest = [run for run in kept if not any(len(other) > len(run) and kept[other].keys() == kept[run].keys() and _inside(run, other) for other in kept)]
    return sorted(({"lines": sorted(kept[run]), "text": next(iter(kept[run].values()))} for run in longest), key=lambda row: (-len(row["lines"]), row["text"]))


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


# Chapter `n`'s title and headings as the roots of their own words, whatever their order — its first word lowered, a capital no name there.
@cache
def _headings(n: int) -> list[tuple[int, str, frozenset[str]]]:
    out = []
    for number, line in enumerate((_chapter(n) or "").splitlines(), 1):
        if line.startswith(("# ", "## ")):
            text = line.lstrip("# ")
            out.append((number, text, frozenset(t.key[:_FAMILY_ROOT] for t in _tokens(text[:1].lower() + text[1:], number) if t.content)))
    return out


# The roots of the words the manual sets for an entity — `lignée`, `foyer`, `royaume` —, per language: no other word says the same, so none is a tic.
@cache
def _imposed() -> frozenset[str]:
    return frozenset(word[:_FAMILY_ROOT] for word in i18n("words.json").get("terms", ()))


# Whether run `run` sits inside run `other`, word for word.
def _inside(run: tuple[str, ...], other: tuple[str, ...]) -> bool:
    return any(other[at : at + len(run)] == run for at in range(len(other) - len(run) + 1))


# Chapter `n`'s sentences opened on an inversion, by their opener lower-cased, each at its first line as written: a question asks, and is no mould.
@cache
def _inverted(n: int) -> dict[str, tuple[int, str]]:
    said: dict[str, tuple[int, str]] = {}
    for number, line in enumerate((_chapter(n) or "").splitlines(), 1):
        if line.strip() and line[0] not in "|<#":
            for sentence in _SENTENCE.split(_MARKS.sub(" ", unmarked(line)).strip()):
                if not sentence.endswith("?") and (found := _INVERTED.match(sentence)):
                    said.setdefault(found["opener"].lower(), (number, found[0]))
    return said


# A word as compared: lower-case, its elision's apostrophe gone, each figure as `N` — `21 sont morts` and `15 sont morts` are one mould.
def _key(word: str) -> str:
    return re.sub(r"\d+", "N", word.lower().rstrip("'’"))


# A shown run's words as compared, to tell which rare words it already carries.
def _keys(text: str) -> set[str]:
    return {_key(word) for word in _WORD.findall(text)}


# The tag a delivered chapter was last audited at: its latest `--retouch` round, else its delivery — what `--retouch` diffs from; `None` undelivered, or with no git.
@cache
def _last_round(n: int) -> str | None:
    rounds = [int(tag.rsplit("-r", 1)[1]) for tag in chronicle_git("tag", "--list", f"C{n}-r*").stdout.split()]
    if rounds:
        return f"C{n}-r{max(rounds)}"
    return None if chronicle_git("rev-parse", "-q", "--verify", f"refs/tags/C{n}-delivered").returncode else f"C{n}-delivered"


# Chapter `n` read once, line by line: its number, whether it is a section's edge (a heading, a separator), and its sentences as tokens.
@cache
def _lines(n: int) -> list[tuple[int, bool, list[list[_Token]]]]:
    lines = enumerate(text.splitlines(), 1) if (text := _chapter(n)) is not None else ()
    return [(number, bool(_SECTION.match(line)), [tokens for part in _SENTENCE.split(line) if (tokens := _tokens(part, number))]) for number, line in lines]


# The units a measure is said in — `words.json`, per language: a figure before one is a measure, its form the manual's.
@cache
def _measures() -> frozenset[str]:
    return frozenset(i18n("words.json").get("measures", ()))


# Tokens as an example is matched on, every article one: the mould is the turn, never the article it was said with.
def _moulded(tokens: list[_Token]) -> tuple[str, ...]:
    return tuple("·" if token.key in _DETERMINERS else token.key for token in tokens)


# Each one the chapter tags, by its tag, beside the lines that tagged it in the 2 chapters before: where the same angle is likeliest taken twice.
def _names(n: int) -> list[dict]:
    def tagged(m: int) -> dict[str, tuple[str | None, list[int]]]:
        found: dict[str, tuple[str | None, list[int]]] = {}
        for at, line in enumerate((_chapter(m) or "").splitlines(), 1):
            for tag in TAG_MARK.finditer(line):
                if tag["kind"] not in _NAMELESS:
                    lines = found.setdefault(f"{tag['kind']} {tag['id']}", (tag["text"], []))[1]
                    if not lines or lines[-1] != at:
                        lines.append(at)
        return found

    now, before = tagged(n), {m: tagged(m) for m in (n - 2, n - 1) if m >= 1}
    rows = []
    for tag, (name, lines) in now.items():
        if seen := {f"C{m}": found[tag][1] for m, found in before.items() if tag in found}:
            rows.append({**seen, "lines": lines, "name": name, "tag": tag})
    return sorted(rows, key=lambda row: row["lines"][0])


# A family said `_NEAR_USES` times within `_NEAR_SPAN` paragraphs running, its forms and lines: heard close, where `overused` weighs the chapter whole.
def _near(n: int) -> list[dict]:
    tables = _table_rows(n)
    at = {number: i for i, number in enumerate(number for number, edge, sentences in _lines(n) if sentences and not edge and number not in tables)}
    said: defaultdict[str, list[_Token]] = defaultdict(list)
    for token in _words(n):
        if token.content and token.line in at and token.key[:_FAMILY_ROOT] not in _imposed():  # the manual's own word, `foyer`, has no other to swap
            said[token.key[:_NEAR_ROOT]].append(token)
    rows = []
    for root, tokens in said.items():
        starts = (i for i in range(len(tokens) - _NEAR_USES + 1) if at[tokens[i + _NEAR_USES - 1].line] - at[tokens[i].line] < _NEAR_SPAN)
        if (start := next(starts, None)) is not None:
            run = tokens[start : start + _NEAR_USES]
            rows.append({"family": root, "forms": sorted({token.key for token in run}), "lines": sorted({token.line for token in run})})
    return sorted(rows, key=lambda row: row["lines"])


# Chapter `n`'s first sentence, its line and the words of its own it carries, each by its family's root: what a mould taken again with other words still keeps.
@cache
def _opening(n: int) -> tuple[int, dict[str, str]] | None:
    for number, line in enumerate((_chapter(n) or "").splitlines(), 1):
        if line.strip() and line[0] not in "|<#" and line.strip() != "---":
            words = (token for token in _tokens(_SENTENCE.split(line)[0], number) if token.content)
            return number, {token.key[:_FAMILY_ROOT]: token.surface for token in words}
    return None


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
        if count < _FAMILY_FLOOR or root in _imposed():
            continue
        peak_rate, peak_count, peak_in = max((then[root] / total, then[root], f"C{k}") for k, (then, total) in history.items())
        if peak_count > 1 and count / size > peak_rate * _OVERUSE and count > peak_count:
            used = sorted({form for form in forms if form.startswith(root)}, key=lambda form: (-forms[form], form))
            out.append({"count": count, "family": root, "forms": used[:4], "most_before": {"chapter": peak_in, "count": peak_count}})
    return sorted(out, key=lambda row: -row["count"])


# Each line's take from the 2 chapters before, one entry per chapter, each match with its line and signs; a chapter a stronger one covers is dropped
def _passages(words: list[_Token], n: int) -> list[dict]:
    found: defaultdict[tuple[int, int], list[dict]] = defaultdict(list)
    for before in range(max(n - 2, 1), n):
        for (line, at), texts in _runs(words, _words(before)).items():
            found[line, before] += [{"by": {"echo", *(("refrain",) if _refrain(text, n) else ())}, "from": at, "text": text} for text in texts]
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
            match["by"] |= {"chute", *(("refrain",) if _refrain_chute(frozenset(match.get("words") or shared), n) else ())}
    out, shown = [], defaultdict(set)  # per line, the words its stronger chapters already show
    for (line, before), matches in sorted(found.items(), key=lambda item: (item[0][0], [-rank for rank in _weight(item[0][1], item[1])])):
        heard = {key for match in matches for key in (_keys(match["text"]) if "text" in match else {match.get("word"), *match.get("words", ())})}
        if heard <= shown[line]:
            continue
        shown[line] |= heard
        # `from` names its chapter with its line: set beside `line`, the chapter read as this line's own.
        ordered = sorted(matches, key=lambda m: m["from"])
        told = [{**m, "by": sorted(m["by"]), "from": f"C{before} l.{m['from']}", "words": sorted(m.get("words") or ())} for m in ordered]
        out.append({"line": line, "matches": told})
    return out


# The words too common to make two runs a turn of phrase or a family worth counting, and the units a measure is said in — `words.json`, per language.
@cache
def _plain() -> frozenset[str]:
    words = i18n("words.json")
    return frozenset((*words.get("measures", ()), *words.get("stop", ())))


# The words the chronicle uses at most `_RARE` times, long enough to be more than a particle: those a borrowed image can be known by.
@cache
def _rare() -> frozenset[str]:
    return frozenset(word for word, count in _uses().items() if count <= _RARE and len(word) >= _FAMILY_ROOT)


# The `_RECENT` chapters before chapter `n`, all of them while the chronicle is shorter: where a mould is counted, never past `n`.
def _recent(n: int) -> range:
    return range(max(n - _RECENT, 1), n)


# Whether a shown run holds `_MIN_RUN` words chapter `n` and those `_recent` say in `_REFRAIN` chapters or more: its own voice, weighed apart from a repeat.
def _refrain(text: str, n: int) -> bool:
    keys = [_key(word) for word in _WORD.findall(text)]
    return any(tuple(keys[i : i + _MIN_RUN]) in _refrains(n) for i in range(len(keys) - _MIN_RUN + 1))


# Whether a chute's words are heard together in `_REFRAIN` chapters of `n` and those `_recent` — `voit court` in three chapters running: a refrain, not a repeat.
def _refrain_chute(words: frozenset[str], n: int) -> bool:
    return sum(any(words <= heard for _, heard in _heard(k)) for k in (*_recent(n), n)) >= _REFRAIN


# Every telling run of `_MIN_RUN` words said in `_REFRAIN` chapters of `n` and those `_recent`: `de ce monde ne` is the language's, whatever its count.
@cache
def _refrains(n: int) -> frozenset[tuple[str, ...]]:
    said = Counter(run for k in (*_recent(n), n) for run in _telling_runs(k))
    return frozenset(run for run, chapters in said.items() if chapters >= _REFRAIN)


# Runs of `_MIN_RUN`+ words shared with `earlier`, each followed along one passage of it, keyed (line, line said first); against itself, only an earlier line counts
def _runs(words: list[_Token], earlier: list[_Token]) -> dict[tuple[int, int], list[str]]:
    within = earlier is words
    long_run = _LONG_RUN_WITHIN if within else _LONG_RUN
    seen: defaultdict[tuple[str, ...], list[int]] = defaultdict(list)
    for at in range(len(earlier) - _MIN_RUN + 1):
        if earlier[at].line == earlier[at + _MIN_RUN - 1].line:
            seen[tuple(token.key for token in earlier[at : at + _MIN_RUN])].append(at)

    # How far the words at `i` and the passage at `at` run alike, neither leaving its line: a heading sewn to the paragraph under it was never written so.
    def along(i: int, at: int) -> int:
        size = 0
        while i + size < len(words) and at + size < len(earlier):
            word, said = words[i + size], earlier[at + size]
            if word.key != said.key or word.line != words[i].line or said.line != earlier[at].line:
                break
            size += 1
        return size

    runs: dict[tuple[int, int], list[str]] = {}
    i = 0
    while i <= len(words) - _MIN_RUN:
        places = [at for at in seen.get(tuple(token.key for token in words[i : i + _MIN_RUN]), ()) if not within or earlier[at].line < words[i].line]
        # The longest it follows, never sewn from two places: « serait à près de » off one line and « à près de 2 » off another are two runs, or none.
        sizes = [along(i, at) for at in places]
        if (size := max(sizes, default=0)) >= _MIN_RUN and _telling(run := words[i : i + size], long_run):
            said = earlier[places[sizes.index(size)]].line  # the first to say it, on a tie
            runs.setdefault((run[0].line, said), []).append("".join(t.surface + ("" if t.surface[-1] in "'’" else " ") for t in run).strip())
            i += size
        else:
            i += 1  # a run too plain to tell may hide a longer one begun inside it
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


# What chapter `n` is cast in: its title's start, each heading's, each section's first and last sentence's first words, each paragraph's, its sections between `---`.
@cache
def _shape(n: int) -> tuple[dict[tuple[str, tuple[str, ...]], tuple[int, str]], tuple[int, ...]]:
    marks: dict[tuple[str, tuple[str, ...]], tuple[int, str]] = {}
    movements, opening, last = [0], False, None  # `last`: the section's latest prose line, whose last sentence is its chute

    def mark(what: str, line: str, number: int, size: int) -> None:
        start = _tokens(line, number)[:size]
        if what == "sentence":  # whole, with a word of its own and articles levelled: `Au Berceau, les aînées`, never a refrain the chronicle keeps
            if len(start) < size or not any(token.content for token in start) or tuple(token.key for token in start) in _refrains(n):
                return
            keys = _moulded(start)
        else:
            heading = what in ("heading", "title")  # its words by root, articles levelled: `Celle du` and `Celles de` one mould, `Le premier`, `La première` too
            keys = tuple(("·" if token.key in _DETERMINERS else token.key[:_FAMILY_ROOT]) if heading else token.key for token in start)
        marks.setdefault((what, keys), (number, " ".join(token.surface for token in start)))

    def close() -> None:
        if last is not None:
            mark("closing", _SENTENCE.split(last[1])[-1], last[0], _OPENING_START)

    for number, line in enumerate((_chapter(n) or "").splitlines(), 1):
        if line.startswith(("# ", "## ")):
            close()
            mark("heading" if line[1] == "#" else "title", line, number, _HEADING_START)
            movements[-1] += line[1] == "#"
            opening, last = True, None
        elif line.strip() == "---":
            close()
            movements.append(0)
            opening, last = True, None
        elif line.strip() and line[0] not in "|<":  # a table or a tag line opens nothing and closes nothing: prose does
            sentences = _SENTENCE.split(line)
            if opening:
                mark("opening", sentences[0], number, _OPENING_START)  # its first sentence alone: `Crabanvier, an 15.` whatever follows
            # Every paragraph too, a section's first among them: a mould taken again mid-section, `Loin à l'ouest, la` before a name no run weighs
            mark("paragraph", sentences[0], number, _OPENING_START)
            for sentence in sentences:  # every one, mid-paragraph too: `On raconte que Umtp` said again wherever it falls
                mark("sentence", sentence, number, _OPENING_START)
            opening, last = False, (number, line)
    close()
    return marks, tuple(movements)


# The cast chapter `n` takes back, which no run of words shows: a title, a heading, a section or paragraph begun alike, the same cut thrice.
def _shaped(n: int) -> list[dict]:
    marks, movements = _shape(n)
    before = [k for k in (n - 2, n - 1) if k >= 1 and _chapter(k) is not None]
    # A section's opening is what a reader keeps best: weighed over the chapters `_recent`, where the rest of the cast holds to the two before.
    rows = [
        {"chapters": said, "line": line, "text": text, "what": what}
        for (what, key), (line, text) in marks.items()
        if key and (said := [f"C{k}" for k in (_recent(n) if what == "opening" else before) if (what, key) in _shape(k)[0]])
    ]
    rows += [
        {"chapters": said, "line": line, "text": text, "what": "example"}
        for example, (line, text) in _example_lines(n).items()
        if (said := [f"C{k}" for k in before if example in _example_lines(k)])
    ]
    if (first := _opening(n)) is not None:  # the chapter's opening against theirs: the words it keeps, whatever else was rewritten
        line, roots = first
        for k in before:
            if (theirs := _opening(k)) and len(shared := sorted(roots.keys() & theirs[1].keys())) >= _OPENING_WORDS:
                rows.append({"chapters": [f"C{k}"], "line": line, "text": ", ".join(roots[root] for root in shared), "what": "opening_words"})
    started = {row["line"] for row in rows if row["what"] in ("heading", "title")}  # begun alike already: told once
    for line, text, roots in _headings(n):  # its own words in another order, which no start shows
        if line in started or len(roots) < _HEADING_WORDS:
            continue
        if theirs := [f"C{k}" for k in before if any(len(roots & other) >= _HEADING_WORDS for _, _, other in _headings(k))]:
            rows.append({"chapters": theirs, "line": line, "text": text, "what": "heading_words"})
    # An inversion is a mould by itself, `Peut-être a-t-elle` whatever the verb: weighed over the chapters `_recent`, where a gap of one hides no habit.
    for opener, (line, text) in _inverted(n).items():
        if len(said := [f"C{k}" for k in _recent(n) if opener in _inverted(k)]) >= _REFRAIN:
            rows.append({"chapters": said, "line": line, "text": text, "what": "inverted"})
    opened = {row["line"] for row in rows if row["what"] == "opening"}
    rows = [row for row in rows if row["what"] != "paragraph" or row["line"] not in opened]  # a section's opening, told once
    told = {(row["line"], row["text"]) for row in rows if row["what"] != "sentence"}
    rows = [row for row in rows if row["what"] != "sentence" or (row["line"], row["text"]) not in told]  # a paragraph's or a chute's start, told once
    if len(before) == 2 and all(_shape(k)[1] == movements for k in before):  # twice may be chance, three times is a mould
        rows.append({"chapters": [f"C{k}" for k in before], "text": " | ".join(str(count) for count in movements), "what": "sections per movement"})
    return sorted(rows, key=lambda row: row.get("line", 0))


# The species as the chronicle names them in its own language, by their first four letters — `loup` catches `loups`, `mouc` catches `mouches`.
@cache
def _species_roots() -> frozenset[str]:
    names = i18n("species.json").values()
    return frozenset(word[:4].lower() for name in names for word in re.findall(r"[\wÀ-ÿ-]+", name) if len(word) >= 4)


# The lines of chapter `n` that are a table's rows: cast alike by design, so never a repeat of one another.
@cache
def _table_rows(n: int) -> frozenset[int]:
    return frozenset(number for number, line in enumerate((_chapter(n) or "").splitlines(), 1) if line.lstrip().startswith("|"))


# The words a run must carry to be a turn of phrase rather than the language: two that say something of their own, one from `long_run` words.
def _telling(run: list[_Token], long_run: int = _LONG_RUN) -> bool:
    return sum(token.content for token in run) >= (1 if len(run) >= long_run else 2)


# Chapter `k`'s telling runs of `_MIN_RUN` words, each within a line, as compared: read once a chapter, whichever window `_refrains` counts them in.
@cache
def _telling_runs(k: int) -> frozenset[tuple[str, ...]]:
    words = _words(k)
    runs = (words[i : i + _MIN_RUN] for i in range(len(words) - _MIN_RUN + 1))
    return frozenset(tuple(token.key for token in run) for run in runs if run[0].line == run[-1].line and _telling(run))


# A stretch of prose as tokens: markup gone, a tag's text kept and marked as a name, an elision split from the word it leans on.
def _tokens(text: str, number: int) -> list[_Token]:
    text = _dates().sub(_DATE, text)
    names = {_key(word) for tag in TAG_MARK.finditer(text) for word in _WORD.findall(tag["text"] or "")}
    out = []
    for word in _WORD.findall(_MARKS.sub(" ", unmarked(text))):
        key = _key(word)
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


# What chapter `n` says twice itself, and apart the terms it coins: a turn said on `_TERM` lines or more, its variants joined by the words they carry.
def _within(words: list[_Token], n: int) -> tuple[list[dict], list[dict]]:
    rows = _table_rows(n)
    said: defaultdict[frozenset[str], list[tuple[int, int, str]]] = defaultdict(list)
    for (line, at), texts in _runs(words, words).items():
        if not (line in rows and at in rows):
            for text in texts:
                said[frozenset(key for key in _keys(text) if _content(key, False))].append((line, at, text))
    again: defaultdict[int, list[dict]] = defaultdict(list)  # `line` the one saying it again, `from` the line that said it first
    terms = []
    for matches in said.values():
        if len(lines := {number for line, at, _ in matches for number in (line, at)}) >= _TERM:
            terms.append({"lines": sorted(lines), "text": Counter(text for *_, text in matches).most_common(1)[0][0]})
        else:
            for line, at, text in matches:
                again[line].append({"from": at, "text": text})
    internal = [
        {"line": line, "matches": [{**match, "from": f"l.{match['from']}"} for match in sorted(matches, key=lambda match: match["from"])]}
        for line, matches in sorted(again.items())
    ]
    return internal, sorted(terms, key=lambda term: term["lines"])


# A chapter as the reader hears it, word by word, each with its line.
@cache
def _words(n: int) -> list[_Token]:
    return [token for _, _, sentences in _lines(n) for tokens in sentences for token in tokens]


# What chapter `n` says again, `None` where it is not written — the first has only itself to repeat. `new.py --finalize` counts it before the audit reads it.
def echoes(n: int, whole: bool = False) -> dict | None:
    if not (words := _words(n)):
        return None
    internal, terms = _within(words, n)
    found = {
        "bare": _bare(n),
        "formulas": _formulas(n),
        "internal": internal,
        "names": _names(n),
        "near": _near(n),
        "overused": _overused(words, n),
        "passages": _passages(words, n),
        "shape": _shaped(n),
        "terms": terms,
    }
    if whole or (changed := _changed(n)) is None:
        return found

    # Delivered: a row stands by the lines it names, its own or the one it echoes — an overused family, named by no line, by a count the retouch raised
    def named(row: dict) -> set[int]:
        echoed = {int(match["from"][2:]) for match in row.get("matches") or () if str(match.get("from", "")).startswith("l.")}
        return {*([row["line"]] if "line" in row else row.get("lines") or ()), *echoed}

    then = _audited_roots(n) if found["overused"] else Counter()  # the tag read only where a family is over
    return {key: [row for row in rows if (row["count"] > then[row["family"]] if key == "overused" else changed & named(row))] for key, rows in found.items()}


# What chapter `n` breaks, empty while it holds: its length, the cap at every retouch too, its dialogues against `--finalize`'s floor: `--retouch` refuses on them.
def faults(n: int) -> dict[str, list[str]]:
    floor, length = chapter_floor(n), chapter_length(prose := _chapter(n) or "")
    told = f"✗ chapter.md, {length} characters, {COUNTED_AS} — its bounds are {floor} to {CHAPTER_CAP}"
    return {"dialogue": short_dialogues(prose), "length": [] if floor <= length <= CHAPTER_CAP else [told]}


def main(argv: list[str]) -> int:
    chapter, whole, listed = next((arg for arg in argv if arg[:1] == "C" and arg[1:].isdigit()), None), "--whole" in argv, "--names" in argv
    if stray := [arg for arg in argv if arg not in (chapter, "--whole", "--names")]:  # `--help` among them: a word unheard would else run the latest chapter
        return hand_usage("usage: chapter/echo.py [C<n>] [--whole] [--names]\neach field and option: `gloss chapter.echo`", stray)
    n = int(chapter[1:]) if chapter else latest_chapter()
    if (found := echoes(n, whole)) is None:
        print(f"✗ no chapter.md for C{n}", file=sys.stderr)
        return 1
    told = faults(n)
    for fault in (*told["length"], *told["dialogue"]):
        print(fault, file=sys.stderr)
    # A check gone silent found nothing: named, so it is not read as unrun — the length and the dialogue too, silent while they hold.
    clear = sorted(check for check, rows in {**found, **told}.items() if not rows)
    if not listed:  # a reading aid, never a fault: counted, the lines on `--names` — listed, it drowned what is to mend
        found["names"] = len(found["names"])
    emit({**found, "clear": clear, "delivered": (not whole and _changed(n) is not None) or None})
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
