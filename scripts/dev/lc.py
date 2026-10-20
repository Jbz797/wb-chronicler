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

_ANSWERED = re.compile(r'"((?:[^"\\]|\\.)*)"="((?:[^"\\]|\\.)*)"')  # how Claude Code hands asked questions back: each one, then the option picked
_CUTOFF = re.compile(r'\*\*`CUTOFF = "([^"]+)"`\*\*(?: — soit le [^(]*\(heure de Paris\)\.)?')  # the one line of the memory file a reading moves on

# What reads as a message and is none: a sub-agent handing back its work, which the chronicler's own account follows, and the summary a long session restarts on.
_NOISE = ("<task-notification>", "This session is being continued from a previous conversation")

_PASTED = re.compile(r'(?s)(<pasted_content id="[^"]*">\n[^\n]*\n).*?(</pasted_content[^>]*>)')  # a prompt the dev wrote: its first line names it
_PROJECTS = Path.home() / ".claude" / "projects"
_REPO = Path(__file__).resolve().parents[2]


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
            content = (entry.get("message") or {}).get("content")  # a string where JB typed, blocks elsewhere — prose, a question put to JB, his answer
            parts = [content] if isinstance(content, str) else [_said(block) for block in content or []]
            if (text := "\n".join(part for part in parts if part).strip()) and not any(noise in text for noise in _NOISE):
                events.append((stamp, path.stem[:8], "JB  " if entry["type"] == "user" else "CHRO", text))
    return sorted(events)


# Where Claude Code keeps what was said from a working directory: its path, every character but letters and digits turned to a dash.
def _folder(cwd: Path) -> Path:
    return _PROJECTS / re.sub(r"[^A-Za-z0-9]", "-", str(cwd))


# The reading's date written back into the memory file, as it stands there: the stamp, then the same instant on JB's clock.
def _mark(memory: Path, stamp: str) -> None:
    local = datetime.fromisoformat(stamp).astimezone(ZoneInfo("Europe/Paris"))
    line = f'**`CUTOFF = "{stamp}"`** — soit le {local:%d/%m/%y} à {local:%H:%M} (heure de Paris).'
    memory.write_text(_CUTOFF.sub(lambda _: line, memory.read_text(encoding="utf-8"), count=1), encoding="utf-8")


# What a block tells the reader of the session: its text, a question the chronicler put to JB with its options, or the option JB picked — no tool's work else.
def _said(block: object) -> str | None:
    if not isinstance(block, dict):
        return None
    if block.get("type") == "text":
        return block.get("text")
    if block.get("type") == "tool_use" and block.get("name") == "AskUserQuestion":
        asked = (block.get("input") or {}).get("questions") or []
        return "\n".join(f"? {q.get('question')}" + "".join(f"\n  · {o.get('label')} — {o.get('description', '')}" for o in q.get("options") or []) for q in asked)
    if block.get("type") == "tool_result":
        result = block.get("content")
        text = result if isinstance(result, str) else " ".join(part.get("text", "") for part in result or [] if isinstance(part, dict))
        if "Your questions have been answered" in text:
            return "\n".join(f"→ {picked}" for _, picked in _ANSWERED.findall(text))
    return None


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
