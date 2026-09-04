#!/usr/bin/env python3

# Marks an actor as the world's favorite in the live WorldBox save, then rebuilds the current chapter around him. Spares the player the in-game marking and the
# re-save: the chronicler names his pick, the player agrees, and the chapter is born with its favorite. Docs: `tools/tools.md`, the rules in `chronicler.md`.

import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))

from shared import SAVES_DIR, index_by_id, is_sapient, latest_chapter, live_save, load_save, worldbox_running, write_save


# The actor the chronicler picked, refused unless he can actually carry a chronicle: alive in the save, and thinking — a beast holds no story of its own.
def _picked(save: dict, actor_id: int) -> dict | None:
    actor = next((a for a in save.get("actors_data") or [] if a.get("id") == actor_id), None)
    if actor is None:
        print(f"✗ no actor {actor_id} in the save — either he is dead, or the id is wrong", file=sys.stderr)
        return None
    if not is_sapient(index_by_id(save.get("subspecies") or []).get(actor.get("subspecies"))):
        print(f"✗ {actor.get('name')} ({actor.get('asset_id')}) is not sapient — a favorite must be able to hold a chronicle", file=sys.stderr)
        return None
    return actor


# The hour the save was taken at, rounded as `new.py` rounds it so the two scripts never disagree over a digit.
def _world_time(save: dict) -> float:
    return round(float((save.get("mapStats") or {}).get("world_time", 0)), 2)


# Moves the flag onto `favorite` and writes both files WB keeps in step: the save itself, and the `favorites` tally its save-list reads.
def _write_flag(wbox: Path, save: dict, favorite: dict) -> None:
    for actor in save.get("actors_data") or []:
        if actor.get("favorite") and actor.get("id") != favorite.get("id"):
            del actor["favorite"]  # WB carries one favorite at a time
    favorite["favorite"] = True

    write_save(wbox, save)

    meta = wbox.parent / "map.meta"
    if not meta.exists():
        return
    count = sum(1 for a in save.get("actors_data") or [] if a.get("favorite"))
    patched, hits = re.subn(r'"favorites":\s*\d+', f'"favorites":{count}', meta.read_text(), count=1)
    if hits:  # a miss leaves WB showing its old tally in the save list, the save itself staying right — nothing the chronicler could act on, so nothing is said
        meta.write_text(patched)


def main(argv: list[str]) -> int:
    if not argv or not argv[0].isdigit():
        print("usage: favorite.py <actor_id>", file=sys.stderr)
        return 2
    actor_id = int(argv[0])

    if worldbox_running():
        print("✗ WorldBox is running — quit the game before marking the favorite, or it will write its own save back over this one", file=sys.stderr)
        return 1

    live_wbox = live_save()
    if not (n := latest_chapter()):  # the chapter the bootstrap laid down is the one this script rebuilds around its favorite
        print("✗ no chapter yet — run `tools/chapter/new.py` first", file=sys.stderr)
        return 1
    chapter_dir = SAVES_DIR / f"C{n}"
    # Judged on the world's clock, not the file's bytes: WorldBox rewrites a save whole on every quit, so saving twice without playing would else read as moved.
    archived = chapter_dir / "map.wbox"
    if not archived.exists():
        print(f"✗ C{n} has no archived save — run `tools/chapter/new.py` again, then mark the favorite right after", file=sys.stderr)
        return 1
    save = load_save(live_wbox)
    if _world_time(load_save(archived)) != _world_time(save):
        print(f"✗ the world has turned since C{n} — run `tools/chapter/new.py` again, then mark the favorite right after", file=sys.stderr)
        return 1

    if (actor := _picked(save, actor_id)) is None:
        return 1

    # A fresh copy, not the chapter's archive: the two now agree on the hour, not on the byte, and only this one can undo exactly what the next line writes.
    with tempfile.NamedTemporaryFile(suffix=".wbox", delete=False) as backup:
        shutil.copy2(live_wbox, backup.name)
    _write_flag(live_wbox, save, actor)
    reread = load_save(live_wbox)  # read back from disk: the flag must have landed, and nothing else moved
    marked = [a.get("id") for a in reread.get("actors_data") or [] if a.get("favorite")]
    if marked != [actor_id]:
        shutil.copy2(backup.name, live_wbox)
    Path(backup.name).unlink(missing_ok=True)  # spent either way: it has served as the undo, or the write it guarded went through
    if marked != [actor_id]:
        print(f"✗ inconsistent write (favorites={marked}) — the save has been restored as it stood", file=sys.stderr)
        return 1

    print(f"✓ {actor.get('name')} ({actor.get('asset_id')}, id {actor_id}) is the world's favorite")

    # The whole chapter goes, prose included: a world with a favorite is told in circles around him. The hour has not moved, so only the words are lost.
    had_prose = (chapter_dir / "chapter.md").exists()
    shutil.rmtree(chapter_dir)
    print(f"  C{n} erased then rebuilt around him — `new.py` lays the NEW_FAVORITE tag on its own")
    if had_prose:
        print(f"  → chronicler: its prose went with it — write C{n} afresh, from his eyes, in circles")
    print(flush=True)  # a blank line, flushed: the child writes next

    # `--reset-asked` because reaching here means a chapter stood a moment ago, so the reset question was settled long before — without it C1 would ask again.
    return subprocess.run([sys.executable, str(Path(__file__).with_name("new.py")), "--reset-asked"], check=False).returncode


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
