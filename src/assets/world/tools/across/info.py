#!/usr/bin/env python3

# One tool asked of a run of chapters at once, its answers keyed by chapter in their order. User-facing docs: `docs/tools.md`.
# A chapter the tool refuses keeps its refusal in its slot: an absence reads chapter by chapter, and one save missing never breaks the run.

import json
import re
import subprocess
import sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))

from shared import SAVES_DIR, hand_usage, render, run

_SPAN = re.compile(r"C(\d+)(?:-C?(\d+))?")  # `C1-C5`, or `C1-5` — a lone `C5` read too, to be refused with the call it stands for
_TOOLS = Path(__file__).parents[1]
_USAGE = "usage: across/info.py C<a>-C<b> <tool> [args…] [--keep a,b.c]\neach option: `gloss across`"


# One chapter's answer: the tool's JSON and the `⚠` it told beside, else the line its refusal says why in — a traceback's last, where it fell over.
def _answer(script: Path, args: list[str], chapter: str) -> tuple[object, list[str]]:
    tool = subprocess.run([sys.executable, str(script), *args, chapter], capture_output=True, text=True, check=False)
    lines = tool.stderr.strip().splitlines()
    if not tool.returncode and tool.stdout.strip():
        return json.loads(tool.stdout), [line.removeprefix("⚠ ") for line in lines if line.startswith("⚠")]
    return next((line for line in lines if line.startswith("✗")), lines[-1] if lines else f"✗ exit {tool.returncode}"), []


# One chapter's answer cut to the fields asked, each by its dotted path from the block's top: a field it lacks says nothing, a refusal stays whole.
def _kept(answer: object, paths: list[str]) -> object:
    if not isinstance(answer, dict):
        return answer
    kept = {}
    for path in sorted(paths):  # in the order every output keeps its keys
        value: object = answer
        for key in path.split("."):
            value = value.get(key) if isinstance(value, dict) else None
        if value is not None:
            kept[path] = value
    return kept


def main(argv: list[str]) -> int:
    if len(argv) < 2 or not (span := _SPAN.fullmatch(argv[0])):
        return hand_usage(_USAGE, argv)
    tool, args = argv[1], argv[2:]
    keep = None
    if "--keep" in args:  # `across`'s own, never the tool's: a few fields followed over the span, the rest of each answer left out
        at = args.index("--keep")
        if at + 1 >= len(args):
            print("✗ `--keep` takes fields, comma-separated: `--keep task,statuses,stats.health`", file=sys.stderr)
            return 2
        keep, args = args[at + 1].split(","), args[:at] + args[at + 2 :]
    if tool == "across" or not (script := _TOOLS / tool / "info.py").exists():
        print(f"✗ no tool {tool} — `docs/tools.md` lists them", file=sys.stderr)
        return 2
    if chapters := [arg for arg in args if re.fullmatch(r"C\d+", arg)]:
        print(f"✗ {', '.join(chapters)}: the span names the chapters — {_USAGE.splitlines()[0]}", file=sys.stderr)
        return 2
    first, last = sorted((int(span[1]), int(span[2] or span[1])))
    if first == last:  # one chapter is the tool's own suffix, its answer bare
        print(f"✗ one chapter needs no `across`: `{' '.join([tool, *args, f'C{first}'])}`", file=sys.stderr)
        return 2
    chapters = [f"C{n}" for n in range(first, last + 1)]
    with ThreadPoolExecutor(max_workers=len(chapters)) as pool:  # each chapter a process of its own, none waiting on another
        jobs = {chapter: pool.submit(_answer, script, args, chapter) for chapter in chapters if (SAVES_DIR / chapter / "map.wbox").exists()}
    results = {chapter: jobs[chapter].result() if chapter in jobs else (f"✗ no save for {chapter}", []) for chapter in chapters}
    answers, notes = {chapter: answer for chapter, (answer, _) in results.items()}, defaultdict(list)
    for chapter, (_, told) in results.items():  # what each chapter's answer left out, once for every chapter that says it alike
        for note in told:
            notes[note].append(chapter)
    if keep is not None:
        kept = {chapter: _kept(answer, keep) for chapter, answer in answers.items()}
        if not any(kept.values()) and (shown := next((answer for answer in answers.values() if isinstance(answer, dict)), None)) is not None:
            print(f"✗ none of {', '.join(keep)} in any chapter — its fields: {', '.join(sorted(shown))}", file=sys.stderr)
            return 1
        answers = kept
    print(render(answers, key="across"))
    for note, where in notes.items():
        print(f"⚠ {', '.join(where)}: {note}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(run(main))
