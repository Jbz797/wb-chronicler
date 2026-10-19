# Faithful Saves

A save keeps what every creature was in the middle of: a pregnancy, an egg, a sleep, a fire, a mood, a task, and the wait before its next sleep. Loading no longer wipes them.

## Why

Vanilla WorldBox writes no status into a save, so every load quietly resets them, and a world loaded often drifts from the one the game means to run:

- **Pregnancy.** A load before the birth ends it: a kind that carries 21 months, loaded every 2 years, loses nearly 9 pregnancies in 10.
- **Eggs.** An egg hatches the moment the world loads, however long it had left.
- **Afterglow.** The wait between two matings, 90 seconds for most kinds, is lifted.
- **Sleep.** Every sleeper wakes.
- **Harm.** Every burning creature is put out, the poisoned and the cursed are cured: a death the game was dealing never comes.
- **Moods.** A tantrum, a rage, a dream, a fresh love: all gone.
- **Tasks.** Every creature drops what it was doing and picks a task anew.
- **Roofs.** Every creature indoors is set back on its doorstep.

WorldBox also redraws two kinds of timers on every load:

- **The wait before a decision may be taken again**, drawn anew between half of it and the whole: a long one is hardly ever sat out, so a kind that naps long barely sleeps again, and nobody repairs a tool.
- **The world's own clocks.** A disaster and a wave of migrants each come every 80 seconds, and both clocks rewind to a full 80.

## What this mod changes

- **On save**, each creature keeps what is left of its statuses and of its long waits (90 seconds or more), its task (the step reached, the time spent, its aim: a prey, a tile, a building) and the building it is inside; a boat, the shore it was ferrying to; the world, the time left on its two clocks.
- **On load**, each is handed back for exactly the time it had left, and each creature takes its task up at that very step: a woodcutter carrying his logs walks on to the store, a hunter keeps its prey, a sleeper stays under its roof.

Nothing else changes: no status lasts longer or shorter than in vanilla, none is added. A status handed back does not replay its first effects (a change of mood, a sound).

**Not kept:** the `possessed` status, your own hand on a creature; a boat's errand to fetch passengers, asked for again by those waiting; short waits, soon sat out; and what a town was in the middle of (a capture, a building site).

## Installation

Install [NeoModLoader](https://steamcommunity.com/sharedfiles/filedetails/?id=3080294469) first, as described in the [Wandering Clouds](../WanderingClouds/README.md#1-install-neomodloader-once) notes.

1. From the root of this repository, link this folder into NML's `Mods` folder, so a `git pull` updates the mod:
   - **macOS**: `ln -s "$PWD/mods/FaithfulSaves" ~/"Library/Application Support/Steam/steamapps/common/worldbox/Mods/FaithfulSaves"`
   - **Linux**: the same, with your own Steam path (often `~/.steam/steam/steamapps/common/worldbox/Mods/FaithfulSaves`)
   - **Windows** (as administrator): `mklink /D "<Steam>\steamapps\common\worldbox\Mods\FaithfulSaves" "%CD%\mods\FaithfulSaves"`

   Without a clone, copy `mod.json`, `icon.png` and the two `.cs` files into `Mods/FaithfulSaves/`.
2. Launch WorldBox. NML compiles the mod as the game starts: it shows in the _Mods_ window, and the game log reads `[Faithful Saves]: a save now keeps statuses, tasks, roofs, long waits and the world's clocks`.

**To uninstall**, disable the mod in NML's _Mods_ window, or delete its link from `Mods`.

## Notes

- **Compatibility:** the mod replaces no game code. It works with other mods unless they also store data under a `faithful_` key.
- **What it writes into your saves:** keys prefixed `faithful_`, in each creature's custom data and in the world's (`faithful_saved_at` tells this repository's chronicle the mod wrote the save). A save made with the mod loads fine without it: vanilla ignores those keys.
- **A save made before the mod:** its first load still wipes everything; all is kept from the next save on.
