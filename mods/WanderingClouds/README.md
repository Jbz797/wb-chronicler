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

Install it with the other mods of this repository, as [mods/README.md](../README.md) describes. The game log then reads `[Wandering Clouds]: clouds now rise anywhere and drift either way`.

## Notes

- **Compatibility:** the mod only adds two Harmony postfixes, on `Cloud.spawn` and `Cloud.update`, and a prefix on the save, and replaces no game code. It works with other mods unless they also move natural clouds.
- **What it writes into your saves:** one number, `wandering_clouds_saved_at`, in the world's own `custom_data`: the world's time at the save. It lets the chronicle this repository builds tell a save the mod ran on from one it did not. Vanilla ignores it, so the mod is safe to remove.

## For modders

- `CloudPatches.AfterSpawn`, postfix on `Cloud.spawn(WorldTile pTile, string pType)`: when `pTile` is `null` (a natural cloud), it moves the cloud to `x = Randy.randomFloat(0, MapBox.width)` and flips the sign of its `speed` half the time. `Cloud.update` moves a cloud by `speed`, so a negative speed sends it west.
- `CloudPatches.AfterUpdate`, postfix on `Cloud.update`: vanilla only kills a cloud once `x > MapBox.width`. This postfix calls `startToDie()` on a live west-bound cloud once `x < 0`.
- `SaveStamp.BeforeWorldSave`, prefix on `SaveManager.currentWorldToSavedMap()`: it writes `World.world.getCurWorldTime()` under `wandering_clouds_saved_at` in `MapStats.custom_data`. A time rather than a flag: a flag would stay in the save once the mod is off.
