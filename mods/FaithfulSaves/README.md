# Faithful Saves

A save keeps what every creature was in the middle of: a pregnancy, an egg, a sleep, a fire, a mood, and the wait before its next sleep. Loading no longer wipes them.

## Why

Vanilla WorldBox writes no status into a save. A creature's statuses live in memory only, so every load quietly resets them, and a world saved and loaded often drifts away from the one the game means to run:

- **Pregnancy.** A live-bearing mother carries for as many months as her kind matures (5 seconds a month). Load the world before she is due and the pregnancy is gone, with no birth. A kind that carries 21 months, saved and loaded every 2 years, loses nearly 9 pregnancies in 10.
- **Eggs.** An egg hatches the moment the world loads, however long it had left: egg-layers gain on every load what live-bearers lose.
- **Afterglow.** After a kiss, both lovers wait before they can breed again — 90 seconds for most kinds. A load lifts that wait.
- **Sleep.** A sleeper wakes at every load, however long it had left to sleep.
- **Harm.** A load puts out every burning creature and cures the poisoned, the cursed and the ash-fevered: a death the game was dealing never comes.
- **Moods.** A tantrum, a rage, a dream, a fresh love: all gone.

WorldBox also redraws two kinds of timers on every load:

- **The wait before a decision may be taken again**, drawn at random between half of it and the whole. A short wait is soon sat out. A long one hardly ever is before the next load: a kind that naps long (a 200-second wait) barely sleeps again, a herd's alpha barely ever moves its family, nobody repairs a tool.
- **The world's own clocks.** A disaster and a wave of migrants each get their turn every 80 seconds, and both clocks rewind to a full 80 on load.

## What this mod changes

- **On save**, each creature gets written into its own saved data the time each of its statuses has left, and the time left before each of its long decisions (a wait of 90 seconds or more) may be taken again. The world gets the time left on its two clocks.
- **On load**, once the world stands, each status, wait and clock is handed back for exactly the time it had left.

Nothing else changes: no status lasts longer or shorter than in vanilla, and none is added that the creature did not have. A status handed back does not replay what it does when first given (a change of mood, a sound): that was felt before the save.

**Not kept:** the `possessed` status, which is your own hand on a creature; the waits of short decisions, which WorldBox still redraws on load and which are soon sat out; and what a town was in the middle of (a capture, a building site).

## Installation

The mod installs by hand. Install [NeoModLoader](https://steamcommunity.com/sharedfiles/filedetails/?id=3080294469) first, as described in the [Wandering Clouds](../WanderingClouds/README.md#1-install-neomodloader-once) notes.

1. Link this folder into the `Mods` folder NML created, under the name `FaithfulSaves`. A link keeps the mod in step with the repository: a `git pull` updates it, with nothing to copy again.
   - **macOS**: `ln -s "$PWD/mods/FaithfulSaves" ~/"Library/Application Support/Steam/steamapps/common/worldbox/Mods/FaithfulSaves"`
   - **Linux**: the same command, with your own Steam path (often `~/.steam/steam/steamapps/common/worldbox/Mods/FaithfulSaves`)
   - **Windows** (a terminal run as administrator): `mklink /D "<Steam>\steamapps\common\worldbox\Mods\FaithfulSaves" "%CD%\mods\FaithfulSaves"`

   Run it from the root of this repository. Without a clone, copy the folder's files there instead (`mod.json`, `icon.png` and the two `.cs` files), with `mod.json` directly in `Mods/FaithfulSaves/`.
2. Launch WorldBox. NML compiles the mod as the game starts: it shows up in the _Mods_ window, and the game log reads `[Faithful Saves]: a save now keeps statuses, long waits and the world's clocks`.

**To uninstall**, disable the mod in NML's _Mods_ window, or delete its link (or its folder) from `Mods`.

## Notes

- **Compatibility:** the mod replaces no game code. It works with other mods unless they also store data under a `faithful_` key.
- **What it writes into your saves:** a handful of numbers per creature, in its `custom_data_float` — one `faithful_status_<status>` for each status under way, one `faithful_wait_<decision>` for each long wait still running, and a `faithful_waits` mark — and, in the world's own `custom_data`, two `faithful_timer_<clock>` and `faithful_saved_at`, the world's time at the save, by which the chronicle this repository builds knows the mod wrote it. A save made with the mod loads fine without it: vanilla ignores those keys, and everything is simply lost as before.
- **A save made before the mod** carries no such key, so its first load still wipes the statuses and redraws the waits. Everything is kept from the next save on.

## For modders

- `SavePatches.BeforeSave`, prefix on `Actor.prepareForSave()`: it stores the time left on each status and on each long wait.
- `SavePatches.BeforeWorldSave`, prefix on `SaveManager.currentWorldToSavedMap()`: it stores the two world clocks and stamps the save with the world's time.
- `SavePatches.AfterLoad`, postfix on `SaveManager.randomDecisionCooldowns()`, the last step WorldBox runs over every creature when a world loads: it hands each status, wait and clock back, and removes its key.
