#!/usr/bin/env python3

# Reads what the chronicler's own Claude session has said since the last reading — the dev's bridge to it, never the chronicler's tool. Claude Code keeps a
# transcript per session under `~/.claude/projects/`, one folder per working directory; the date of the last reading lives in the dev session's memory.

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

_CUTOFF = re.compile(r'\*\*`CUTOFF = "([^"]+)"`\*\*(?: — soit le [^(]*\(heure de Paris\)\.)?')  # the one line of the memory file a reading moves on

# What reads as a message and is none: a sub-agent handing back its work, which the chronicler's own account follows, and the summary a long session restarts on.
_NOISE = ("<task-notification>", "This session is being continued from a previous conversation")

_PASTED = re.compile(r'(?s)(<pasted_content id="[^"]*">\n[^\n]*\n).*?(</pasted_content[^>]*>)')  # a prompt the dev wrote: its first line names it
_PROJECTS = Path.home() / ".claude" / "projects"
_REPO = Path(__file__).resolve().parents[1]


# The messages of every chronicler session after `cutoff`, oldest first whichever session said them: two sessions may overlap, and are read in the order of time.
def _events(cutoff: str) -> list[tuple[str, str, str, str]]:
    events = []
    for path in sorted(_folder(_REPO / "src" / "assets" / "world").glob("*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                entry = json.loads(line)
            except ValueError:
                continue
            stamp = entry.get("timestamp") or ""
            if entry.get("type") not in ("user", "assistant") or entry.get("isSidechain") or entry.get("isMeta") or stamp <= cutoff:
                continue
            content = (entry.get("message") or {}).get("content")  # a string where JB typed, blocks elsewhere — of which the text alone is prose
            parts = [content] if isinstance(content, str) else [b["text"] for b in content or [] if isinstance(b, dict) and b.get("type") == "text"]
            if (text := "\n".join(part for part in parts if part).strip()) and not any(noise in text for noise in _NOISE):
                events.append((stamp, path.stem[:8], "JB  " if entry["type"] == "user" else "CHRO", text))
    return sorted(events)


# Where Claude Code keeps what was said from a working directory: its path, every character but letters and digits turned to a dash.
def _folder(cwd: Path) -> Path:
    return _PROJECTS / re.sub(r"[^A-Za-z0-9]", "-", str(cwd))


# The reading's date written back into the memory file, as it stands there: the stamp, then the same instant on JB's clock.
def _mark(memory: Path, stamp: str) -> None:
    local = datetime.fromisoformat(stamp.replace("Z", "+00:00")).astimezone(ZoneInfo("Europe/Paris"))
    line = f'**`CUTOFF = "{stamp}"`** — soit le {local:%d/%m/%y} à {local:%H:%M} (heure de Paris).'
    memory.write_text(_CUTOFF.sub(lambda _: line, memory.read_text(encoding="utf-8"), count=1), encoding="utf-8")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Read what the chronicler's session said since the last reading.")
    parser.add_argument("--full", action="store_true", help="show the pasted prompts whole — they are the dev's own, cut to their first line otherwise")
    parser.add_argument("--mark", action="store_true", help="move the date of the last reading on to the latest message read")
    args = parser.parse_args(argv)
    memory = _folder(_REPO) / "memory" / "project_chronicler_bridge.md"
    if not memory.exists() or not (found := _CUTOFF.search(memory.read_text(encoding="utf-8"))):
        print(f"✗ no `CUTOFF` line in {memory}", file=sys.stderr)
        return 1
    cutoff = found[1]
    events = _events(cutoff)
    for stamp, session, who, text in events:
        shown = text if args.full else _PASTED.sub(r"\1[…]\n\2", text)
        print(f"\n── [{stamp[:16].replace('T', ' ')}Z · {session}] {who} ─────\n{shown}")
    latest = events[-1][0] if events else cutoff
    if args.mark and latest != cutoff:
        _mark(memory, latest)
    print(f"\n{len(events)} message(s) since {cutoff}" + (f" — last reading {'moved on' if args.mark else 'would move on'} to {latest}" if events else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
