#!/usr/bin/env python3

# What a chapter says again, for `chronicler.md` § V « Ne te répète pas »: each passage it takes back from the two chapters before — a run of words, a
# rare word framed alike, a chute —, the runs it says twice itself and the terms it coins, the families it leans on past anything the chronicle did
# before, and the cast it is poured in again: a title, a heading, a section or paragraph begun alike. It points, the eye judges: an angle taken again slips past it.

import re
import sys
from collections import Counter, defaultdict
from functools import cache
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
_LONG_RUN = 7  # words from which a run is a turn of phrase with a single word of its own: `et ce qui verdit au ras du sol`, `à l'entrée de l'an 5`
_LONG_RUN_WITHIN = 6  # the same, within one chapter, where a formula said again ten lines on is heard: `jamais encore on n'avait vu`
_MARKS = re.compile(r"[*_#>|`]")  # emphasis, headings, quotes and table rules: markup, which no reader hears
_MIN_RUN = 4  # words a shared run must hold: three are the language's own (« il n'y a »), four start to be a turn of phrase
_NAMELESS = frozenset("grs")  # gear, resources and species: icons a chapter strews, no one whose angle can be told twice
_OPENING_START = 4  # words a section's first sentence is known by, a figure read as any other: `Voxzen est dans sa` 11ᵉ, then 13ᵉ année
_OPENING_WORDS = 2  # words of its own a chapter's first sentence must share with one before to pour its mould again: one alone is the chronicle's subject
_OVERUSE = 1.3  # how far past the chronicle's own highest rate a family must climb to be named: a wobble is not a tic
_RARE = 3  # uses across the whole chronicle under which a word shared with the two chapters before is an image borrowed, not the language
_REFRAIN = 3  # chapters a run of words must be said in to be the chronicle's own refrain — `par la taille`, `n'obéissent à rien` — told apart, never dropped
_SCARCE = 8  # uses across the whole chronicle under which a word can carry a chute: `monde` or `terre` would join any two sentences
_SECTION = re.compile(r"^(##\s|---\s*$)")  # a heading or a separator: where a section, and so its chute, ends
_SENTENCE = re.compile(r"(?<=[.!?…])\s+")  # where a sentence ends inside a line
_TERM = 3  # lines of one chapter a turn must be said on to be a term it coined — `le bras du couchant`, a place with no name —, told apart as a refrain is

_USAGE = (
    "usage: chapter/echo.py [C<n>] — what the chapter says again, each row by its `line`: `passages` taken back from the 2 chapters before (`from` their line, "
    "`by` its sign), `internal` runs it says twice, `terms` it coins, `formulas` figured turns it keeps coming back to, "
    "`overused` families, `shape` its cast poured again, `names` each one it tags beside the lines that did in the 2 chapters before; "
    "`clear` the checks that found nothing, `length` and `dialogue` among them — "
    "out of its bounds or under its floor, a ✗ says so; every field glossed by `gloss/info.py echo`"
)

_WORD = re.compile(r"\b[^\W\d_]{1,2}['’]|\w[\w-]*(?:['’]\w[\w-]*)*")  # an elision splits, `qu'il` as `qu'` and `il`; `aujourd'hui` holds, `---` is none


class _Token(NamedTuple):
    content: bool  # a word that says something of its own, told once at reading: `_content`
    key: str  # the word as compared: `_key`
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


# The lines a delivered chapter has changed since, off the chronicle's git tag — `None` before delivery, or with no git, when the whole chapter is weighed.
@cache
def _changed(n: int) -> set[int] | None:
    tag = f"C{n}-delivered"
    if chronicle_git("rev-parse", "-q", "--verify", f"refs/tags/{tag}").returncode:
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
    docs = SAVES_DIR.parent / "docs"
    quoted = (found[1].split("…")[0] for doc in ("chronicler.md", "lexicon.md") for found in _EXAMPLE.finditer((docs / doc).read_text()))
    return frozenset(key for text in quoted if not re.search(r"[\d\[`]", text) and len(key := _moulded(_tokens(text, 0))) >= _EXAMPLE_WORDS)


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


# The roots of the words the manual sets for an entity — `lignée`, `foyer`, `royaume` —, per language: no other word says the same, so none is a tic.
@cache
def _imposed() -> frozenset[str]:
    return frozenset(word[:_FAMILY_ROOT] for word in i18n("words.json").get("terms", ()))


# Whether run `run` sits inside run `other`, word for word.
def _inside(run: tuple[str, ...], other: tuple[str, ...]) -> bool:
    return any(other[at : at + len(run)] == run for at in range(len(other) - len(run) + 1))


# A word as compared: lower-case, its elision's apostrophe gone, each figure as `N` — `21 sont morts` and `15 sont morts` are one mould.
def _key(word: str) -> str:
    return re.sub(r"\d+", "N", word.lower().rstrip("'’"))


# A shown run's words as compared, to tell which rare words it already carries.
def _keys(text: str) -> set[str]:
    return {_key(word) for word in _WORD.findall(text)}


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


# Whether a shown run holds `_MIN_RUN` words the chronicle says in `_REFRAIN` chapters or more: its own voice, which the eye weighs apart from a repeat.
def _refrain(text: str) -> bool:
    keys = [_key(word) for word in _WORD.findall(text)]
    return any(tuple(keys[i : i + _MIN_RUN]) in _refrains() for i in range(len(keys) - _MIN_RUN + 1))


# Whether a chute's words are heard together in `_REFRAIN` chapters of the chronicle or more — `voit court` in three chapters running: its refrain, not a repeat.
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
        marks.setdefault((what, tuple(token.key for token in start)), (number, " ".join(token.surface for token in start)))

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
            if opening:
                mark("opening", _SENTENCE.split(line)[0], number, _OPENING_START)  # its first sentence alone: `Crabanvier, an 15.` whatever follows
            # Every paragraph too, a section's first among them: a mould taken again mid-section, `Loin à l'ouest, la` before a name no run weighs
            mark("paragraph", _SENTENCE.split(line)[0], number, _OPENING_START)
            opening, last = False, (number, line)
    close()
    return marks, tuple(movements)


# The cast chapter `n` takes back from the two before, which no run of words shows: a title, a heading, a section or paragraph begun alike, the same cut thrice.
def _shaped(n: int) -> list[dict]:
    marks, movements = _shape(n)
    before = [k for k in (n - 2, n - 1) if k >= 1 and _chapter(k) is not None]
    rows = [
        {"chapters": said, "line": line, "text": text, "what": what}
        for (what, key), (line, text) in marks.items()
        if key and (said := [f"C{k}" for k in before if (what, key) in _shape(k)[0]])
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
    opened = {row["line"] for row in rows if row["what"] == "opening"}
    rows = [row for row in rows if row["what"] != "paragraph" or row["line"] not in opened]  # a section's opening, told once
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
def echoes(n: int) -> dict | None:
    if not (words := _words(n)):
        return None
    internal, terms = _within(words, n)
    found = {
        "formulas": _formulas(n),
        "internal": internal,
        "names": _names(n),
        "overused": _overused(words, n),
        "passages": _passages(words, n),
        "shape": _shaped(n),
        "terms": terms,
    }
    if (changed := _changed(n)) is None:
        return found

    # Delivered: a row stands by the lines it names, its own or the one it echoes — a count over the whole chapter names none, and was weighed at delivery.
    def named(row: dict) -> set[int]:
        echoed = {int(match["from"][2:]) for match in row.get("matches") or () if str(match.get("from", "")).startswith("l.")}
        return {*([row["line"]] if "line" in row else row.get("lines") or ()), *echoed}

    return {key: [row for row in rows if changed & named(row)] for key, rows in found.items()}


def main(argv: list[str]) -> int:
    chapter = next((arg for arg in argv if arg[:1] == "C" and arg[1:].isdigit()), None)
    if stray := [arg for arg in argv if arg != chapter]:  # `--help` among them: a word unheard would else pass for a run of the latest chapter
        asked = stray[0] in ("-h", "--help")
        print(_USAGE, file=sys.stdout if asked else sys.stderr)
        return 0 if asked else 2
    n = int(chapter[1:]) if chapter else latest_chapter()
    if (found := echoes(n)) is None:
        print(f"✗ no chapter.md for C{n}", file=sys.stderr)
        return 1
    # Said only past its bounds, as every check says a fault alone: a retouch after delivery would else pass the cap unseen, `--deliver` long run.
    floor, length = chapter_floor(n), chapter_length(prose := _chapter(n) or "")
    if not (held := floor <= length <= CHAPTER_CAP):
        print(f"✗ chapter.md, {length} characters, {COUNTED_AS} — its bounds are {floor} to {CHAPTER_CAP}", file=sys.stderr)
    for fault in (short := short_dialogues(prose)):  # `--finalize`'s own floor, measured each round where the audit reads it
        print(fault, file=sys.stderr)
    # A check gone silent found nothing: named, so it is not read as unrun — the length and the dialogue too, silent while they hold.
    clear = sorted(check for check, rows in {**found, "dialogue": short, "length": not held}.items() if not rows)
    emit({**found, "clear": clear, "delivered": _changed(n) is not None or None})
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
