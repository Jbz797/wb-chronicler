# Wandering Clouds

Clouds rise anywhere in the sky and drift either way, so the seeds of life fall all over your world, not just in its west.

## Why

In vanilla WorldBox, every cloud the world raises by itself is born on the **west edge** of the map and drifts **east**. Ordinary clouds drop a seed of life every couple of seconds, and those seeds hatch the world's new creatures. With the _Drop of Thoughts_ law on, half of them hatch **thinking peoples**.

The game also caps each species at 4 bodies from seeds. On a young world, the first clouds have only crossed the western strip when every species reaches that cap. Once those peoples breed, the cap never lifts again, so no later cloud can seed them anywhere else. That is why a new world's first civilizations all start out crowded in its west.

## What this mod changes

For the clouds the world raises by itself:

- each one is born at a **random point across the whole width** of the map, instead of on the west edge;
- each one drifts **east or west, at random** (50/50);
- a cloud heading west fades away when it leaves the map by the west edge, just as vanilla clouds do on the east.

Everything else stays vanilla: cloud types, speeds, heights, what they drop, and how often.

**Not touched:** clouds you summon with a god power keep their spot and their heading.

## Installation

The mod isn't on the Steam Workshop yet, so it installs by hand, in two steps.

### 1. Install NeoModLoader (once)

1. In WorldBox, turn on **Experimental Mode** in the settings. NML only loads with it on.
2. Subscribe to [NeoModLoader](https://steamcommunity.com/sharedfiles/filedetails/?id=3080294469) on the Steam Workshop, and wait for the download.
3. Copy `NeoModLoader.dll` and `NeoModLoader.pdb` from the Workshop folder into the game's own mods folder:
   - **Windows**: from `<Steam>\steamapps\workshop\content\1206560\3080294469\` to `<Steam>\steamapps\common\worldbox\worldbox_Data\StreamingAssets\Mods\`
   - **macOS**: from `~/Library/Application Support/Steam/steamapps/workshop/content/1206560/3080294469/` to `worldbox.app/Contents/Resources/Data/StreamingAssets/mods/` (right-click `worldbox.app` › _Show Package Contents_)
   - **Linux / Steam Deck**: see the NML Workshop page.
4. Launch WorldBox once: NML adds its _Mods_ window, and creates a `Mods` folder next to the game.

Subscribing alone isn't enough the first time; afterwards, the subscription keeps NML up to date.

### 2. Install Wandering Clouds

1. Copy this folder's files (`mod.json`, `icon.png` and the two `.cs` files) into a folder of their own inside the `Mods` folder NML created, with `mod.json` directly in it:
   - **Windows**: `<Steam>\steamapps\common\worldbox\Mods\WanderingClouds\`
   - **macOS**: `~/Library/Application Support/Steam/steamapps/common/worldbox/Mods/WanderingClouds/`
2. Launch WorldBox. NML compiles the mod as the game starts: it shows up in the _Mods_ window, and the game log reads `[Wandering Clouds]: clouds now rise anywhere and drift either way`.

**To uninstall**, disable the mod in NML's _Mods_ window, or delete its folder.

## Notes

- **Compatibility:** the mod only adds two Harmony postfixes, on `Cloud.spawn` and `Cloud.update`, and replaces no game code. It works with other mods unless they also move natural clouds.
- **Safe to remove:** nothing is written into your saves.

## For modders

- `CloudPatches.AfterSpawn`, postfix on `Cloud.spawn(WorldTile pTile, string pType)`: when `pTile` is `null` (a natural cloud), it moves the cloud to `x = Randy.randomFloat(0, MapBox.width)` and flips the sign of its `speed` half the time. `Cloud.update` moves a cloud by `speed`, so a negative speed sends it west.
- `CloudPatches.AfterUpdate`, postfix on `Cloud.update`: vanilla only kills a cloud once `x > MapBox.width`. This postfix calls `startToDie()` on a live west-bound cloud once `x < 0`.
