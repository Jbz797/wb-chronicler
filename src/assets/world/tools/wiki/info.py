#!/usr/bin/env python3

# Reads the official WorldBox wiki through its MediaWiki API, the one door its 403 leaves open. User-facing docs: `docs/chronicler.md` § « Accès au wiki ».
# `<Page>` prints its wikitext, redirects followed; `--list [word]` its titles, every batch of the listing walked, filtered on a word when one is given.

import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))

from shared import arg_parser

_API = "https://the-official-worldbox-wiki.fandom.com/api.php"
_BATCH = 500  # the most titles one `allpages` call hands back
_HEADERS = {"User-Agent": "Mozilla/5.0"}  # the wiki turns away a request that names no browser, 403 and nothing else
_TIMEOUT = 15


# One API call, its answer parsed.
def _ask(params: dict) -> dict:
    request = urllib.request.Request(f"{_API}?{urllib.parse.urlencode({**params, 'format': 'json'})}", headers=_HEADERS)
    with urllib.request.urlopen(request, timeout=_TIMEOUT) as response:
        return json.load(response)


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
    print(answer["parse"]["wikitext"]["*"])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
