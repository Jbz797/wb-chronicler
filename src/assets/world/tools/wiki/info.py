#!/usr/bin/env python3

# Reads the official WorldBox wiki through its MediaWiki API, the one door its 403 leaves open. User-facing docs: `docs/chronicler.md` § « Accès au wiki WorldBox ».
# `<Page>` prints its wikitext, a redirect followed to the section it names; `--entry <name>` the table rows naming it, cell by cell, else list items opening on it;
# `--list [word]` its titles, every batch of the listing walked, filtered on a word when one is given; `--search <words>` the pages whose text holds them.
# A page past `_OUTLINE` prints its sections and their sizes instead, `--section <title>` reading one whole.

import html
import json
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))

from shared import arg_parser

_API = "https://the-official-worldbox-wiki.fandom.com/api.php"
_BATCH = 500  # the most titles one `allpages` call hands back
_CELL_ATTRS = re.compile(r'^\s*(?:[\w-]+\s*=\s*"[^"]*"\s*)+\|(?!\|)')  # `| style="…" | text`: a cell's own styling, before its single pipe
_CHANGELOG = re.compile(r"^\d+\.\d")  # a version's release notes, `0.7.0 - Crabs and Sorcery`: the game's history, never its rules as they stand
_FOUND = 10  # pages `--search` hands back, best first: past them the wiki only grazes the words
_HEADERS = {"User-Agent": "Mozilla/5.0"}  # the wiki turns away a request that names no browser, 403 and nothing else
_LABEL_WORDS = 3  # words past which a cell is prose, not a label: « Spore », « Mushroom Production »
_OUTLINE = 8000  # characters past which a page prints its sections, one read by `--section`: Culture Traits runs 35 000, a few hundred of them asked
_STEM = 4  # letters two words must open on alike to be taken for one: `spore` and `spores`, `corruption` and `corrupted`
_TIMEOUT = 15
_UNTOLD = frozenset({"version of introduction"})  # columns that tell the wiki's own history, none of the game's rules


# Whether a cell is a label close to the one asked: a few words, one of them beginning as one of its words does — `spore` for `spores`, never an effect's sentence.
def _akin(label: list[str], asked: list[str]) -> bool:
    return 0 < len(label) <= _LABEL_WORDS and any(a.startswith(b[:_STEM]) for a in asked for b in label if len(b) >= _STEM)


# One API call, its answer parsed.
def _ask(params: dict) -> dict:
    request = urllib.request.Request(f"{_API}?{urllib.parse.urlencode({**params, 'format': 'json'})}", headers=_HEADERS)
    with urllib.request.urlopen(request, timeout=_TIMEOUT) as response:
        return json.load(response)


# The names a cell answers to as `--entry` weighs them: itself, and each term a break sets apart — « Close Borders / Far Borders » holds two opinions.
def _names(cell: str) -> set[str]:
    return {_said(cell), *(_said(term) for term in cell.split(" / "))}


# Whether a list item opens on the asked name, a whole word of it: `nutrition (hunger) value…` on `nutrition`, never `nutritional`.
def _opens_on(item: str, asked: str) -> bool:
    return item.startswith(asked) and not item[len(asked) : len(asked) + 1].isalnum()


# A long page's sections as `--section` takes them, each sized as it would read, sub-sections indented under it and counted in it — the lead apart.
def _outline(wikitext: str, sections: list[dict]) -> str:
    cut = [s for s in sections if s.get("byteoffset") is not None]
    lines = [f"(lead) {cut[0]['byteoffset'] if cut else len(wikitext)}"]
    for at, s in enumerate(cut):
        end = next((o["byteoffset"] for o in cut[at + 1 :] if int(o["level"]) <= int(s["level"])), len(wikitext))
        lines.append(f"{'  ' * (int(s['level']) - 2)}{_plain(s.get('line', ''))} {end - s['byteoffset']}")
    return "\n".join(lines)


# A cell as it reads: no pictures, links down to their label, no tags, a break a « / », italics kept as `*…*` — the traits page italicises what the game hides
def _plain(cell: str) -> str:
    text = re.sub(r"\[\[(?:File|Image):[^\]]*\]\]", "", cell)
    text = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]*)\]\]", r"\1", text)
    text = re.sub(r"<br\s*/?>", " / ", text)
    text = re.sub(r"<[^>]+>|\{\{[^}]*\}\}|'''", "", text)
    text = re.sub(r"''(.*?)''", r"*\1*", text).replace("**", "")
    text = re.sub(r"\s+", " ", re.sub(r"\s*\n\s*", " / ", html.unescape(text))).strip(" /")
    return "" if text == "-" else text  # a lone dash is how the wiki leaves a cell empty — stripped anywhere else, it would take a negative's sign


# Every row of every table on the page, with its table's caption and column names — a cell may run over several lines, a list inside it most of all.
def _rows(wikitext: str) -> list[tuple[str, list[str], list[str]]]:
    rows = []
    for table in re.findall(r"^\{\|.*?^\|\}", wikitext, flags=re.MULTILINE | re.DOTALL):
        caption, header = "", []
        for chunk in re.split(r"^\|-.*$", table.split("\n", 1)[1].rsplit("\n|}", 1)[0], flags=re.MULTILINE):
            cells: list[str] = []
            for line in chunk.strip("\n").split("\n"):
                if line.startswith("|+"):  # a caption names the table, the only thing that tells an interval list from the traits it times
                    caption = _plain(line[2:])
                elif line[:1] in ("|", "!"):
                    cells += re.split(r"\|\||!!", _CELL_ATTRS.sub("", line[1:]))
                elif cells:
                    cells[-1] += "\n" + line
            if not header and re.search(r"^!", chunk, flags=re.MULTILINE):
                header = [_plain(c) for c in cells]
            elif cells:
                rows.append((caption, header, [_plain(c) for c in cells]))
    return rows


# A cell as `--entry` weighs it: case aside, and a `_` a space, as the asked name is read — a table of ids (`random_move`) answers like one of labels.
def _said(cell: str) -> str:
    return cell.casefold().replace("_", " ")


# The section a title or an anchor names, its sub-sections with it, a heading of its rank closing it — cut by the wiki's `byteoffset`, which counts characters.
def _section(wikitext: str, sections: list[dict], fragment: str) -> str | None:
    anchor = fragment.replace(" ", "_").casefold()  # the wiki's anchor is its title, `_` for a space: either is asked, case aside
    at = next((i for i, s in enumerate(sections) if s.get("anchor", "").casefold() == anchor and s.get("byteoffset") is not None), None)
    if at is None:
        return None
    rank = int(sections[at]["level"])
    end = next((s["byteoffset"] for s in sections[at + 1 :] if int(s["level"]) <= rank and s.get("byteoffset") is not None), len(wikitext))
    return wikitext[sections[at]["byteoffset"] : end].strip()


# Every title, batch after batch while the API says more remain.
def _titles() -> list[str]:
    titles, resume = [], {}
    while True:
        answer = _ask({"action": "query", "aplimit": _BATCH, "list": "allpages", **resume})
        titles += [page["title"] for page in answer["query"]["allpages"]]
        if not (resume := answer.get("continue") or {}):
            return titles


def main(argv: list[str]) -> int:
    parser = arg_parser(prog="wiki/info.py")
    parser.add_argument("page", nargs="?")
    parser.add_argument("--entry", metavar="name")
    parser.add_argument("--list", nargs="?", const="", metavar="word")
    parser.add_argument("--search", metavar="words")
    parser.add_argument("--section", metavar="title")
    args = parser.parse_args(argv)
    if args.list is None and not args.search and not args.page:  # one of three, which argparse cannot ask for
        print("✗ name a page, `--list [word]` or `--search <words>` — see docs/chronicler.md § « Accès au wiki WorldBox »", file=sys.stderr)
        return 2
    page = (args.page or "").removeprefix("wiki:")  # the docs write a page as `wiki:<Page>`, and that prefix is no part of its title
    try:
        if args.list is not None:
            print("\n".join(title for title in _titles() if args.list.lower() in title.lower()))
            return 0
        if args.search:
            hits = _ask({"action": "query", "list": "search", "srsearch": args.search, "srwhat": "text", "srlimit": _BATCH})["query"]["search"]
            if not (found := [hit["title"] for hit in hits if not _CHANGELOG.match(hit["title"])][:_FOUND]):
                print(f"✗ no page speaks of « {args.search} » — the wiki is in English: the game's own words", file=sys.stderr)
                return 1
            print("\n".join(found))
            return 0
        # `redirects`: a third of the pages are but a pointer to another, and without it the pointer is all that comes back.
        answer = _ask({"action": "parse", "page": page, "prop": "wikitext|sections", "redirects": 1})
    except OSError as e:  # `URLError` for a refused call, a bare `TimeoutError` for an answer that stalls midway: urllib wraps the first kind only
        print(f"✗ the wiki did not answer: {getattr(e, 'reason', e)} — try again", file=sys.stderr)
        return 1
    if "error" in answer:
        print(f"✗ no page `{page}` — `--list <word>` finds its title", file=sys.stderr)
        return 1
    parsed = answer["parse"]
    wikitext, sections = parsed["wikitext"]["*"], parsed.get("sections") or []
    if args.section:
        if (part := _section(wikitext, sections, args.section)) is None:
            print(f"✗ no section « {args.section} » in `{parsed['title']}` — its sections:\n{_outline(wikitext, sections)}", file=sys.stderr)
            return 1
        wikitext = part
    if args.entry is None:
        # A title that points into a page is read where it points: `Renown` is one section of `Unit Stats`, not its 550 lines.
        fragment = None if args.section else next((turn["tofragment"] for turn in parsed.get("redirects") or [] if turn.get("tofragment")), None)
        if fragment and (part := _section(wikitext, sections, fragment)):
            print(f'→ `{page}` is § {fragment} of `{parsed["title"]}`, read alone — the page whole: `wiki/info.py "{parsed["title"]}"`', file=sys.stderr)
            wikitext = part
        elif not args.section and len(wikitext) > _OUTLINE and sections:  # too long to read whole: its map, each part asked for by name
            print(f"· `{parsed['title']}` runs {len(wikitext)} characters — `--section <title>` reads one, `--entry <name>` a row", file=sys.stderr)
            print(_outline(wikitext, sections))
            return 0
        print(wikitext)
        return 0
    wanted = _said(args.entry)
    blocks, rows = [], _rows(wikitext)
    cited = [row for row in rows if any(wanted in _names(cell) for cell in row[2])]
    # A row is named by its first cell that says anything, an icon's being blank: those alone where any is, the rows that only cite the word failing one.
    named = [row for row in cited if wanted in _names(next((cell for cell in row[2] if cell), ""))]
    for caption, header, cells in named or cited:
        # A column past the header keeps its rank for a name: the header is a help, a ragged row still prints whole.
        kept = [(column, cell) for i, cell in enumerate(cells) if cell and (column := (header[i : i + 1] or [f"#{i + 1}"])[0]).casefold() not in _UNTOLD]
        if any(wanted not in _names(cell) for _, cell in kept):  # a row left with its name alone, its only other column untold, says nothing
            blocks.append("\n".join([f"[{caption}]"] * bool(caption) + [f"{column}: {cell}" for column, cell in kept]))
    if not blocks:  # a rule the wiki keeps as a list, not a table — Reproduction's conditions: the items that open on the name
        blocks = [item for line in wikitext.splitlines() if line.startswith(("*", "#")) and _opens_on(_said(item := _plain(line.lstrip("*#: "))), wanted)]
    if not blocks:
        # A label the wiki cuts short — its « Spore » for WB's « Spore Reproduction » — is offered where no row answers, and sought only then.
        asked = wanted.split()
        near = sorted({cell for _, _, cells in rows for cell in cells if _akin(cell.casefold().split(), asked)})
        like = f"; near it: {', '.join(near)}" if near else ""
        print(f"✗ no row or list item of `{page}` names « {args.entry} » — the wiki names a thing by its in-game label{like}", file=sys.stderr)
        return 1
    print("\n\n".join(blocks))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
