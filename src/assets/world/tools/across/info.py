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


# The block whose fields `--keep` reads: the answer itself, or a list's first item — none off a refusal.
def _block_of(answer: object) -> dict | None:
    if isinstance(answer, list) and answer:
        answer = answer[0]
    return answer if isinstance(answer, dict) else None


# The paths `--keep` meant on an answer keyed by its sections: each field as the section one level down holds it — none if no section does.
def _by_section(block: dict, paths: list[str]) -> list[str]:
    return [f"{section}.{path}" for path in paths for section, held in block.items() if path.split(".")[0] in (_block_of(held) or {})]


# One chapter's answer cut to the fields asked, each by its dotted path from the block's top: a field it lacks says nothing, a refusal stays whole.
def _kept(answer: object, paths: list[str]) -> object:
    if isinstance(answer, list):  # a section that is a list: each item cut alike, a lone field read flat (`traits --keep id`: the ids)
        if len(paths) == 1:
            return _picked(answer, paths[0].split("."))
        return [kept for item in answer if (kept := _kept(item, paths))]
    if not isinstance(answer, dict):
        return answer
    return {path: value for path in sorted(paths) if (value := _picked(answer, path.split("."))) is not None}  # in the order every output keeps its keys


# The value at a dotted path, a list on the way walked item by item: `victims.all.id` the id of each victim.
def _picked(value: object, keys: list[str]) -> object:
    for at, key in enumerate(keys):
        if isinstance(value, list):
            return [found for item in value if (found := _picked(item, keys[at:])) is not None] or None
        value = value.get(key) if isinstance(value, dict) else None
    return value


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
        blocks = (block for answer in answers.values() if (block := _block_of(answer)) is not None)  # a section that is a list offers its items' fields
        if not any(kept.values()) and (shown := next(blocks, None)) is not None:
            if deeper := _by_section(shown, keep):
                print(f"✗ none of {', '.join(keep)} at the top — by their section: {', '.join(deeper)}", file=sys.stderr)
            else:
                print(f"✗ none of {', '.join(keep)} in any chapter — its fields: {', '.join(sorted(shown))}", file=sys.stderr)
            return 1
        roots = {path.split(".")[0] for path in keep}
        for chapter, answer in answers.items():
            # An answer holding none of the sections asked is of another shape — a dead body's — and says what it holds; a field merely lacking stays silent
            if not kept[chapter] and (block := _block_of(answer)) is not None and not roots & block.keys():
                kept[chapter] = f"✗ no {', '.join(f'`{root}`' for root in sorted(roots))} here — its fields: {', '.join(sorted(block))}"
        answers = kept
    print(render(answers, key="across"))
    for note, where in notes.items():
        print(f"⚠ {', '.join(where)}: {note}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(run(main))
