#!/usr/bin/env python3

# Reads the official WorldBox wiki through its MediaWiki API, the one door its 403 leaves open. User-facing docs: `docs/chronicler.md` § « Accès au wiki ».
# `<Page>` prints its wikitext, redirects followed; `--row <name>` only the table rows naming it, cell by cell under its column; `--list [word]` its titles,
# every batch of the listing walked, filtered on a word when one is given.

import html
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))

from shared import arg_parser

_API = "https://the-official-worldbox-wiki.fandom.com/api.php"
_BATCH = 500  # the most titles one `allpages` call hands back
_CELL_ATTRS = re.compile(r'^\s*(?:[\w-]+\s*=\s*"[^"]*"\s*)+\|(?!\|)')  # `| style="…" | text`: a cell's own styling, before its single pipe
_HEADERS = {"User-Agent": "Mozilla/5.0"}  # the wiki turns away a request that names no browser, 403 and nothing else
_TIMEOUT = 15


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
    for table in re.findall(r"^\{\|.*?^\|\}", wikitext, flags=re.M | re.S):
        caption, header = "", []
        for chunk in re.split(r"^\|-.*$", table.split("\n", 1)[1].rsplit("\n|}", 1)[0], flags=re.M):
            cells: list[str] = []
            for line in chunk.strip("\n").split("\n"):
                if line.startswith("|+"):  # a caption names the table, the only thing that tells an interval list from the traits it times
                    caption = _plain(line[2:])
                elif line[:1] in ("|", "!"):
                    cells += re.split(r"\|\||!!", _CELL_ATTRS.sub("", line[1:]))
                elif cells:
                    cells[-1] += "\n" + line
            if not header and re.search(r"^!", chunk, flags=re.M):
                header = [_plain(c) for c in cells]
            elif cells:
                rows.append((caption, header, [_plain(c) for c in cells]))
    return rows


# Every title, batch after batch while the API says more remain.
def _titles() -> list[str]:
    titles, resume = [], {}
    while True:
        answer = _ask({"action": "query", "aplimit": _BATCH, "list": "allpages", **resume})
        titles += [page["title"] for page in answer["query"]["allpages"]]
        if not (resume := answer.get("continue") or {}):
            return titles


def main(argv: list[str]) -> int:
    parser = arg_parser(prog="wiki/info.py", description="Read a page of the official WorldBox wiki, or list its titles.")
    parser.add_argument("page", nargs="?", help="the page's title, as `wiki:<Page>` names it")
    parser.add_argument("--list", nargs="?", const="", metavar="word", help="its titles, those holding the word alone if one is given")
    parser.add_argument("--row", metavar="name", help="the table rows naming it alone, cell by cell — a trait's id works, `_` read as a space")
    args = parser.parse_args(argv)
    if args.list is None and not args.page:  # said here rather than by `arg_parser`, whose error points to `tools.md`, where the wiki is not
        print("✗ name a page, or `--list [word]` — see docs/chronicler.md § « Accès au wiki WorldBox »", file=sys.stderr)
        return 2
    page = (args.page or "").removeprefix("wiki:")  # the docs write a page as `wiki:<Page>`, and that prefix is no part of its title
    try:
        if args.list is not None:
            print("\n".join(title for title in _titles() if args.list.lower() in title.lower()))
            return 0
        # `redirects`: a third of the pages are but a pointer to another, and without it the pointer is all that comes back.
        answer = _ask({"action": "parse", "page": page, "prop": "wikitext", "redirects": 1})
    except urllib.error.URLError as e:
        print(f"✗ the wiki did not answer: {e.reason}", file=sys.stderr)
        return 1
    if "error" in answer:
        print(f"✗ no page `{page}` — `--list <word>` finds its title", file=sys.stderr)
        return 1
    wikitext = answer["parse"]["wikitext"]["*"]
    if args.row is None:
        print(wikitext)
        return 0
    wanted = args.row.replace("_", " ").casefold()
    found = [row for row in _rows(wikitext) if any(cell.casefold() == wanted for cell in row[2])]
    if not found:
        print(f"✗ no row of `{page}` names « {args.row} » — a table names a thing by its in-game label", file=sys.stderr)
        return 1
    # A column past the header keeps its rank for a name: the header is a help, and a ragged row still prints whole.
    for k, (caption, header, cells) in enumerate(found):
        lines = [f"{(header[i : i + 1] or [f'#{i + 1}'])[0]}: {cell}" for i, cell in enumerate(cells) if cell]
        print(("\n" if k else "") + "\n".join([f"[{caption}]"] * bool(caption) + lines))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
