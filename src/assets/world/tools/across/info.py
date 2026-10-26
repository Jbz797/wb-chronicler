#!/usr/bin/env python3

# One tool asked of a run of chapters at once, its answers keyed by chapter in their order. User-facing docs: `docs/tools.md`.
# A chapter the tool refuses keeps its refusal in its slot: an absence reads chapter by chapter, and one save missing never breaks the run.

import json
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))

from shared import SAVES_DIR, render

_SPAN = re.compile(r"C(\d+)-C?(\d+)")  # `C1-C5`, or `C1-5`
_TOOLS = Path(__file__).parents[1]
_USAGE = "✗ usage: across/info.py C<a>-C<b> <tool> [args…] — `across C1-C5 geography burning -i 1`, each chapter's suffix the span's"


# One chapter's answer: the tool's JSON, else the line its refusal says why in — a traceback's last, where it fell over.
def _answer(script: Path, args: list[str], chapter: str) -> object:
    run = subprocess.run([sys.executable, str(script), *args, chapter], capture_output=True, text=True, check=False)
    if not run.returncode and run.stdout.strip():
        return json.loads(run.stdout)
    lines = run.stderr.strip().splitlines()
    return next((line for line in lines if line.startswith("✗")), lines[-1] if lines else f"✗ exit {run.returncode}")


def main(argv: list[str]) -> int:
    if len(argv) < 2 or not (span := _SPAN.fullmatch(argv[0])):
        print(_USAGE, file=sys.stderr)
        return 2
    tool, args = argv[1], argv[2:]
    if tool == "across" or not (script := _TOOLS / tool / "info.py").exists():
        print(f"✗ no tool {tool} — `docs/tools.md` lists them", file=sys.stderr)
        return 2
    if chapters := [arg for arg in args if re.fullmatch(r"C\d+", arg)]:
        print(f"✗ {', '.join(chapters)}: the span names the chapters — {_USAGE.removeprefix('✗ ')}", file=sys.stderr)
        return 2
    first, last = sorted((int(span[1]), int(span[2])))
    chapters = [f"C{n}" for n in range(first, last + 1)]
    with ThreadPoolExecutor(max_workers=len(chapters)) as pool:  # each chapter a process of its own, none waiting on another
        jobs = {chapter: pool.submit(_answer, script, args, chapter) for chapter in chapters if (SAVES_DIR / chapter / "map.wbox").exists()}
    print(render({chapter: jobs[chapter].result() if chapter in jobs else f"✗ no save for {chapter}" for chapter in chapters}, key="across"))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
