#!/usr/bin/env python3

# Reads the official WorldBox wiki through its MediaWiki API, the one door its 403 leaves open. User-facing docs: `docs/chronicler.md` § « Accès au wiki ».
# `<Page>` prints its wikitext, a redirect followed to the section it names; `--row <name>` only the table rows naming it, cell by cell under its column;
# `--list [word]` its titles, every batch of the listing walked, filtered on a word when one is given; `--search <words>` the pages whose text holds them.

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


# A cell as `--row` weighs it: case aside, and a `_` a space, as the asked name is read — a table of ids (`random_move`) answers like one of labels.
def _said(cell: str) -> str:
    return cell.casefold().replace("_", " ")


# The section an anchor names, its sub-sections with it, a heading of its rank closing it — cut by the wiki's `byteoffset`, which counts characters, not bytes.
def _section(wikitext: str, sections: list[dict], fragment: str) -> str | None:
    anchor = fragment.replace(" ", "_")
    at = next((i for i, section in enumerate(sections) if section.get("anchor") == anchor and section.get("byteoffset") is not None), None)
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
    parser = arg_parser(prog="wiki/info.py", description="Read a page of the official WorldBox wiki, list its titles or search its text.")
    parser.add_argument("page", nargs="?", help="the page's title, as `wiki:<Page>` names it")
    parser.add_argument("--list", nargs="?", const="", metavar="word", help="its titles, those holding the word alone if one is given")
    parser.add_argument("--search", metavar="words", help="the pages whose text holds them, best first — where no title does")
    parser.add_argument("--row", metavar="name", help="the table rows naming it alone, cell by cell — a trait's id works, `_` read as a space")
    args = parser.parse_args(argv)
    if args.list is None and not args.search and not args.page:  # said here rather than by `arg_parser`, whose error points to `tools.md`, where the wiki is not
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
    wikitext = parsed["wikitext"]["*"]
    if args.row is None:
        # A title that points into a page is read where it points: `Renown` is one section of `Unit Stats`, not its 550 lines.
        fragment = next((turn["tofragment"] for turn in parsed.get("redirects") or [] if turn.get("tofragment")), None)
        if fragment and (part := _section(wikitext, parsed.get("sections") or [], fragment)):
            print(f'→ `{page}` is § {fragment} of `{parsed["title"]}`, read alone — the page whole: `wiki/info.py "{parsed["title"]}"`', file=sys.stderr)
            wikitext = part
        print(wikitext)
        return 0
    wanted = _said(args.row)
    blocks, rows = [], _rows(wikitext)
    cited = [row for row in rows if any(_said(cell) == wanted for cell in row[2])]
    # A row is named by its first cell that says anything, an icon's being blank: those alone where any is, the rows that only cite the word failing one.
    named = [row for row in cited if _said(next((cell for cell in row[2] if cell), "")) == wanted]
    for caption, header, cells in named or cited:
        # A column past the header keeps its rank for a name: the header is a help, a ragged row still prints whole.
        kept = [(column, cell) for i, cell in enumerate(cells) if cell and (column := (header[i : i + 1] or [f"#{i + 1}"])[0]).casefold() not in _UNTOLD]
        if any(_said(cell) != wanted for _, cell in kept):  # a row left with its name alone, its only other column untold, says nothing
            blocks.append("\n".join([f"[{caption}]"] * bool(caption) + [f"{column}: {cell}" for column, cell in kept]))
    if not blocks:
        # A label the wiki cuts short — its « Spore » for WB's « Spore Reproduction » — is offered where no row answers, and sought only then.
        asked = wanted.split()
        near = sorted({cell for _, _, cells in rows for cell in cells if _akin(cell.casefold().split(), asked)})
        like = f"; near it: {', '.join(near)}" if near else ""
        print(f"✗ no row of `{page}` names « {args.row} » — a table names a thing by its in-game label{like}", file=sys.stderr)
        return 1
    print("\n\n".join(blocks))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
