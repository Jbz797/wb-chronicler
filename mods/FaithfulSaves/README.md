# Faithful Saves

A save keeps what every creature was in the middle of: a pregnancy, an egg, a sleep, a fire, a mood, a task, and the wait before its next sleep. Loading no longer wipes them. It also dates each creature's arrival in its town and its army, and each couple, records every death of the world, and closes each history year in January.

## Why

Vanilla WorldBox writes no status into a save, so every load quietly resets them:

- **Pregnancy.** A live-bearing mother carries for as many months as her kind matures. A load before she is due ends it, with no birth: a kind that carries 21 months, loaded every 2 years, loses 9 pregnancies in 10.
- **Eggs.** An egg hatches the moment the world loads, however long it had left.
- **Afterglow.** After a mating, both lovers wait before they can breed again, 90 seconds for most kinds: a load lifts that wait.
- **Sleep.** Every sleeper wakes at once.
- **Harm.** Fires go out, the poisoned, the cursed and the ash-fevered are cured.
- **Moods.** A tantrum, a rage, a dream, a fresh love: all gone.
- **Tasks.** Every creature drops what it was doing and picks a task anew.
- **Roofs.** Every creature indoors is set back on its doorstep.
- **Clouds.** The sky is cleared, a cloud of rage over a town with it.

WorldBox also redraws two kinds of timers on every load:

- **The wait before a decision may be taken again**, drawn anew between half of it and the whole. A long one is hardly ever sat out before the next load: a kind that naps long barely sleeps again, a herd's alpha barely ever moves its family.
- **The world's own clocks.** A disaster and a wave of migrants each come every 80 seconds, and both clocks rewind to a full 80.

## What this mod changes

- **On save**, each creature keeps what is left of its statuses and of its long waits (90 seconds or more), its task (the step reached, the time spent, its aim: a prey, a tile, a building) and the building it is inside; a boat, the shore it was ferrying to; the world, the time left on its two clocks and every cloud of its sky.
- **On load**, each is handed back for exactly the time it had left, and each creature takes its task up at that very step: a woodcutter walks on to the store, a hunter keeps its prey, a sleeper stays under its roof. Each cloud rises again where it was.
- **A creature settling in a new town, joining an army or becoming a couple** is stamped with the world's time; **every death** goes into the history database (`map_stats.s3db`, table `FaithfulDeaths`): who died (kind, name, lineage, parents, birth, role), when, of what (lightning apart from WorldBox's `Other`), where, by whose hand, and the blow a metamorphosis hides.
- **The world's history** closes each year in January, under the year that ended: a row is a calendar year.

Nothing else changes: no status is lengthened, shortened or added, nor replays its first effects (a mood, a sound).

**Not kept:** the `possessed` status, your own hand on a creature; a boat's errand to fetch passengers, asked for again; short waits, soon sat out; and what a town was in the middle of (a capture, a building site).

## Installation

Install it as [mods/README.md](../README.md) describes. The game log then reads `[Faithful Saves]: a save now keeps…`.

## Notes

- **Compatibility:** the mod replaces no game method (it reshapes one), and works with other mods unless they also use `faithful_` keys or reshape the history's yearly close.
- **What it writes into your saves:** keys prefixed `faithful_`, per creature (statuses, waits, task, roof, town, army, lover) and per world (clocks, clouds, and `faithful_saved_at`, by which this repository's chronicle knows the mod wrote the save). Vanilla ignores them, and the `FaithfulDeaths` table.
- **A save made before the mod:** its first load still wipes everything; all is kept from the next save on, and its first history year after the mod runs 13 months.
- **The log** warns of what a load could not hand back.

## For modders

`SavePatches.cs` writes in prefixes on `Actor.prepareForSave()` and `SaveManager.currentWorldToSavedMap()`, and hands back in postfixes on `SaveManager.randomDecisionCooldowns()` (statuses, waits, clocks) and `MapBox.finishingUpLoading()`, the very last step of a load (tasks and roofs: buildings load after the creatures, and WorldBox, seating each king and leader anew, cancels the task they hold). `CityPatches.cs`, `ArmyPatches.cs` and `LoverPatches.cs` stamp in postfixes on `Actor.setCity`, `Actor.setArmy` (skipping what is already stamped, so a load moves nothing) and `Actor.becomeLoversWith()`; `DeathPatches.cs` keeps each death on `Actor.die()` (its killer from `Actor.newKillAction()`), writes them on `DBManager.saveToPath()`, drops them on `DBManager.clearAndClose()`. `CloudPatches.cs` keeps the sky on those same two steps. `HistoryPatches.cs` transpiles `MapBox.updateMetaHistory`: its month 12 becomes 1, its row is filed under the year before; finding neither, it leaves the method whole and logs a warning.
