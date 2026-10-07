using System;
using System.Collections.Generic;
using ai.behaviours;
using HarmonyLib;
using NeoModLoader.services;
using Mind = AiSystem<Actor, ActorJob, ai.behaviours.BehaviourTaskActor, ai.behaviours.BehaviourActionActor, BehaviourActorCondition>;

namespace FaithfulSaves
{
    // WB writes no status into a save: a load ends every pregnancy with no birth, hatches every egg, puts out every burning body, lifts the
    // afterglow that spaces two matings and wakes every sleeper. It then redraws at random how long each creature must wait before its next
    // sleep, and winds the world's own clocks back. The time each of those had left now rides in custom data, which WB does save — the
    // creature's own, or the world's —, and is handed back once the world is loaded. So is the task a creature was at, which WB drops as well:
    // the step it had reached, how long it had been at it, the pause it was holding, and what that step was aimed at — a tile, a wall, a prey.
    internal static class SavePatches
    {
        private const string Log = "[Faithful Saves]: "; // every load says what it handed back, and names what it could not
        private const int LongWait = 90; // a decision's cooldown from which a redrawn wait is rarely sat out before the next load: sleeps, a herd's march
        private const string Possessed = "possessed"; // the one status left out: it is the player's own hand on a creature, which no save holds
        private const string SavedAt = "faithful_saved_at"; // the world's time at the save, in its custom data: proof the mod wrote this very save
        private const string Sleeping = "sleeping"; // handed back through `Actor.makeSleep`, which stills the body as well
        private const string StatusPrefix = "faithful_status_"; // `faithful_status_pregnant`: the seconds that status had left
        private const string Task = "faithful_task"; // the id of the task the creature was at, among its custom strings
        private const string TaskActor = "faithful_task_actor"; // the id of the creature that task was aimed at: a prey, a lover, a foe
        private const string TaskBook = "faithful_task_book"; // the id of the book it was after
        private const string TaskBuilding = "faithful_task_building"; // the id of the building it was at work on, or bound for
        private const string TaskObject = "faithful_task_object"; // the id of a building held where a creature usually is: one it was attacking
        private const string TaskStep = "faithful_task_step"; // which of that task's steps it had reached: `AiSystem.action_index`
        private const string TaskTileX = "faithful_task_tile_x"; // the tile it was walking to, among its custom ints
        private const string TaskTileY = "faithful_task_tile_y";
        private const string TaskTime = "faithful_task_time"; // the seconds it had been at that task, as its window shows them
        private const string TaskWait = "faithful_task_wait"; // the seconds its pause had left before it acts again: `Actor.timer_action`
        private const string TimerPrefix = "faithful_timer_"; // `faithful_timer_disasters`, in the world's custom data: the seconds before its next turn
        private const string WaitPrefix = "faithful_wait_"; // `faithful_wait_monophasic_sleep`: the seconds before that decision may be taken again
        private const string WaitsKept = "faithful_waits"; // set on a creature whose waits were written: a long wait with no key is over, not unknown

        // The two turns WB takes every 80 seconds, a disaster and a wave of migrants: `clearWorld` rewinds both to a full interval on every load.
        private static readonly string[] _keptTimers = { "disasters", "migrants" };

        // What a task's step is aimed at — `beh_actor_target`, and below it a book, a building, a tile —, each set by an earlier step of the task:
        // `Actor.clearBeh` empties all four when a task ends.
        private static readonly AccessTools.FieldRef<Actor, BaseSimObject> _actorTarget = AccessTools.FieldRefAccess<Actor, BaseSimObject>("beh_actor_target");

        private static readonly Func<BaseSimObject, string, float, bool, bool> _addStatusEffect =
            AccessTools.MethodDelegate<Func<BaseSimObject, string, float, bool, bool>>(
                AccessTools.Method(typeof(BaseSimObject), "addStatusEffect", new[] { typeof(string), typeof(float), typeof(bool) }));

        private static readonly AccessTools.FieldRef<Actor, AiSystemActor> _ai = AccessTools.FieldRefAccess<Actor, AiSystemActor>("ai");
        private static readonly AccessTools.FieldRef<Actor, Book> _bookTarget = AccessTools.FieldRefAccess<Actor, Book>("beh_book_target");
        private static readonly AccessTools.FieldRef<Actor, Building> _buildingTarget = AccessTools.FieldRefAccess<Actor, Building>("beh_building_target");

        // `Actor._decision_cooldowns`: when each decision was last taken, by `DecisionAsset.decision_index` — 0 for one free to be taken.
        private static readonly AccessTools.FieldRef<Actor, double[]> _lastTaken = AccessTools.FieldRefAccess<Actor, double[]>("_decision_cooldowns");
        private static readonly AccessTools.FieldRef<MapBox, MapStats> _mapStats = AccessTools.FieldRefAccess<MapBox, MapStats>("map_stats");

        private static readonly AccessTools.FieldRef<Actor, float> _pause = AccessTools.FieldRefAccess<Actor, float>("timer_action");

        // `AiSystem`'s own fields, declared on the generic base every thinking thing of the game shares. `task` is `null` between two tasks.
        private static readonly AccessTools.FieldRef<Mind, int> _step = AccessTools.FieldRefAccess<Mind, int>("action_index");
        private static readonly AccessTools.FieldRef<Mind, BehaviourTaskActor> _task = AccessTools.FieldRefAccess<Mind, BehaviourTaskActor>("task");
        private static readonly AccessTools.FieldRef<Mind, double> _taskStart = AccessTools.FieldRefAccess<Mind, double>("_timestamp_task_start");

        private static readonly AccessTools.FieldRef<Actor, WorldTile> _tileTarget = AccessTools.FieldRefAccess<Actor, WorldTile>("beh_tile_target");
        private static readonly AccessTools.FieldRef<WorldBehaviour, float> _timer = AccessTools.FieldRefAccess<WorldBehaviour, float>("_timer");

        // Before WB serialises a creature: what each status and each long wait has left, or no key at all — a stale one would hand back a time long over —,
        // and the task it is at.
        [HarmonyPrefix]
        [HarmonyPatch(typeof(Actor), nameof(Actor.prepareForSave))]
        private static void BeforeSave(Actor __instance)
        {
            BaseObjectData data = __instance.getData();
            IReadOnlyDictionary<string, Status> statuses = __instance.getStatusesDict();
            foreach (StatusAsset asset in AssetManager.status.list)
            {
                bool kept = asset.id != Possessed && Wears(__instance, asset.id);
                Keep(data, StatusPrefix + asset.id, kept ? (float)statuses[asset.id].getRemainingTime() : 0f);
            }
            AiSystemActor mind = _ai(__instance);
            // A boat's task is WB's own to keep: it saves the state of each hull and sets its task anew on load (`SaveManager.loadBoatStates`).
            BehaviourTaskActor task = mind != null && !__instance.asset.is_boat ? _task(mind) : null;
            if (task != null)
                data.set(Task, task.id);
            else
                data.removeString(Task);
            Keep(data, TaskStep, task != null ? _step(mind) : 0f);
            Keep(data, TaskTime, task != null ? World.world.getWorldTimeElapsedSince(_taskStart(mind)) : 0f);
            Keep(data, TaskWait, task != null ? _pause(__instance) : 0f);
            BaseSimObject aim = task != null ? _actorTarget(__instance) : null;
            KeepAim(data, TaskActor, aim is Actor ? aim : null);
            KeepAim(data, TaskObject, aim is Building ? aim : null);
            KeepAim(data, TaskBook, task != null ? _bookTarget(__instance) : null);
            KeepAim(data, TaskBuilding, task != null ? _buildingTarget(__instance) : null);
            WorldTile tile = task != null ? _tileTarget(__instance) : null;
            if (tile != null)
            {
                data.set(TaskTileX, tile.x);
                data.set(TaskTileY, tile.y);
            }
            else
            {
                data.removeInt(TaskTileX);
                data.removeInt(TaskTileY);
            }
            double[] lastTaken = _lastTaken(__instance);
            if (lastTaken == null)
                return;
            double now = World.world.getCurWorldTime();
            foreach (DecisionAsset decision in LongDecisions(lastTaken))
            {
                double taken = lastTaken[decision.decision_index];
                Keep(data, WaitPrefix + decision.id, taken > 0d ? (float)(decision.cooldown - (now - taken)) : 0f);
            }
            data.set(WaitsKept, 1f);
        }

        // Before WB gathers the world into a save: what each kept clock has left.
        [HarmonyPrefix]
        [HarmonyPatch(typeof(SaveManager), nameof(SaveManager.currentWorldToSavedMap))]
        private static void BeforeWorldSave()
        {
            BaseSystemData data = _mapStats(World.world)?.custom_data;
            if (data == null)
                return;
            foreach (string id in _keptTimers)
            {
                WorldBehaviour clock = AssetManager.world_behaviours.get(id)?.manager;
                Keep(data, TimerPrefix + id, clock != null ? _timer(clock) : 0f);
            }
            data.set(SavedAt, (float)World.world.getCurWorldTime()); // a time, not a flag: one left by an older save would read as today's
        }

        // WB's last step over the creatures of a load, each one standing and its waits just redrawn: the place to hand each status, wait and clock
        // back. Whatever a save was given is handed back or named in the log: a key read and dropped in silence would be a thing lost unseen.
        [HarmonyPostfix]
        [HarmonyPatch(typeof(SaveManager), "randomDecisionCooldowns")]
        private static void AfterLoad()
        {
            double now = World.world.getCurWorldTime();
            int statuses = 0, waits = 0, clocks = 0;
            List<string> lost = new List<string>();
            foreach (Actor actor in World.world.units)
            {
                BaseObjectData data = actor.getData();
                foreach (StatusAsset asset in AssetManager.status.list)
                {
                    float left = Take(data, StatusPrefix + asset.id);
                    if (left <= 0f)
                        continue;
                    if (GiveBack(actor, asset, left))
                        statuses++;
                    else
                        lost.Add($"{asset.id} of {actor.getName()}");
                }
                double[] lastTaken = _lastTaken(actor);
                if (lastTaken == null || Take(data, WaitsKept) == 0f) // no mark: a save from before the mod, left to the waits WB has just drawn
                    continue;
                foreach (DecisionAsset decision in LongDecisions(lastTaken))
                {
                    float left = Take(data, WaitPrefix + decision.id);
                    lastTaken[decision.decision_index] = left > 0f ? now - (decision.cooldown - left) : 0d; // WB reads a wait off the time it began
                    if (left > 0f)
                        waits++;
                }
            }
            BaseSystemData world = _mapStats(World.world)?.custom_data;
            foreach (string id in world != null ? _keptTimers : new string[0])
            {
                float left = Take(world, TimerPrefix + id);
                WorldBehaviour clock = AssetManager.world_behaviours.get(id)?.manager;
                if (left <= 0f)
                    continue;
                if (clock == null)
                {
                    lost.Add($"clock {id}");
                    continue;
                }
                _timer(clock) = left;
                clocks++;
            }
            Report($"{statuses} statuses, {waits} long waits and {clocks} clocks", lost);
        }

        // WB's very last step of a load, and the place for the tasks: the buildings a task may aim at load after the creatures, and WB, seating each
        // king and each leader anew on its way, cancels whatever task they hold (`Actor.setProfession` calls `cancelAllBeh`).
        [HarmonyPostfix]
        [HarmonyPatch(typeof(MapBox), "finishingUpLoading")]
        private static void AfterWorldLoaded()
        {
            double now = World.world.getCurWorldTime();
            int tasks = 0;
            List<string> lost = new List<string>();
            foreach (Actor actor in World.world.units)
                if (GiveTaskBack(actor, actor.getData(), now, lost))
                    tasks++;
            Report($"{tasks} tasks", lost);
        }

        // A status handed back for the time it had left, without what WB does on first posing it: the mood it brought was felt, and saved, already.
        private static bool GiveBack(Actor pActor, StatusAsset pAsset, float pLeft)
        {
            if (pAsset.id == Sleeping)
            {
                pActor.makeSleep(pLeft);
                return Wears(pActor, pAsset.id);
            }
            WorldAction onReceive = pAsset.action_on_receive;
            pAsset.action_on_receive = null;
            try
            {
                _addStatusEffect(pActor, pAsset.id, pLeft, false);
            }
            finally
            {
                pAsset.action_on_receive = onReceive;
            }
            return Wears(pActor, pAsset.id); // WB may refuse one: a kind barred from that tier of statuses, an opposite one already worn
        }

        // A task handed back at the step it had reached, not replayed from its first: a sleep already begun, a meal already taken are not taken twice.
        // What that step was aimed at comes back with it, looked up by where or who it was; an aim the world no longer holds is named in `pLost`, and
        // WB then ends the task as it does when a prey dies. A task this game no longer has is named too; a save from before the mod has none.
        private static bool GiveTaskBack(Actor pActor, BaseObjectData pData, double pNow, List<string> pLost)
        {
            pData.get(Task, out string id, null);
            pData.removeString(Task);
            float step = Take(pData, TaskStep);
            float time = Take(pData, TaskTime);
            float pause = Take(pData, TaskWait);
            long actor = TakeAim(pData, TaskActor);
            long book = TakeAim(pData, TaskBook);
            long building = TakeAim(pData, TaskBuilding);
            long attacked = TakeAim(pData, TaskObject);
            pData.get(TaskTileX, out int x, -1);
            pData.get(TaskTileY, out int y, -1);
            pData.removeInt(TaskTileX);
            pData.removeInt(TaskTileY);
            if (string.IsNullOrEmpty(id)) // a creature between two tasks, or a save from before the mod
                return false;
            AiSystemActor mind = _ai(pActor);
            if (mind == null || !AssetManager.tasks_actor.has(id))
            {
                pLost.Add($"task {id} of {pActor.getName()}");
                return false;
            }
            pActor.setTask(id, true, false, false); // empties every aim, hence handed back below
            _step(mind) = (int)step;
            _taskStart(mind) = pNow - time; // WB reads the time spent off the moment the task began
            if (pause > 0f)
                pActor.makeWait(pause);
            if (x >= 0 && y >= 0)
                _tileTarget(pActor) = World.world.GetTile(x, y);
            if (actor >= 0)
                _actorTarget(pActor) = World.world.units.get(actor);
            if (attacked >= 0)
                _actorTarget(pActor) = World.world.buildings.get(attacked);
            if (book >= 0)
                _bookTarget(pActor) = World.world.books.get(book);
            if (building >= 0)
                _buildingTarget(pActor) = World.world.buildings.get(building);
            bool whole = (x < 0 || y < 0 || _tileTarget(pActor) != null) && (actor < 0 && attacked < 0 || _actorTarget(pActor) != null)
                && (book < 0 || _bookTarget(pActor) != null) && (building < 0 || _buildingTarget(pActor) != null);
            if (!whole)
                pLost.Add($"an aim of task {id} of {pActor.getName()}");
            return true;
        }

        // Every decision of the game with a long wait, whoever takes it: a creature draws from its kind's and from lists all share (`bored_sleep`),
        // not from `Actor.decisions` alone, and WB keeps one wait per decision of the library on each creature.
        private static IEnumerable<DecisionAsset> LongDecisions(double[] pLastTaken)
        {
            foreach (DecisionAsset decision in AssetManager.decisions_library.list)
                if (decision.cooldown >= LongWait && decision.decision_index < pLastTaken.Length)
                    yield return decision;
        }

        // What a step is aimed at written by its id, the key dropped where it aims at none, or at one that died.
        private static void KeepAim(BaseSystemData pData, string pKey, NanoObject pAim)
        {
            if (pAim != null && pAim.isAlive())
                pData.set(pKey, pAim.getID());
            else
                pData.removeLong(pKey);
        }

        // A time left written under its key, the key dropped when nothing is left.
        private static void Keep(BaseSystemData pData, string pKey, float pLeft)
        {
            if (pLeft > 0f)
                pData.set(pKey, pLeft);
            else
                pData.removeFloat(pKey);
        }

        // What a load handed back, and by name what it could not: twenty at most, the log being no place for a whole world.
        private static void Report(string pHandedBack, List<string> pLost)
        {
            LogService.LogInfo($"{Log}handed back {pHandedBack}");
            if (pLost.Count > 0)
                LogService.LogWarning($"{Log}could not hand back {pLost.Count}: {string.Join(", ", pLost.GetRange(0, Math.Min(pLost.Count, 20)))}");
        }

        // A kept time read and its key dropped: the game carries it from here, and the next save writes it anew.
        private static float Take(BaseSystemData pData, string pKey)
        {
            pData.get(pKey, out float left, 0f);
            if (left != 0f)
                pData.removeFloat(pKey);
            return left;
        }

        // A kept aim read by its id and its key dropped, -1 where none was kept: WB counts its ids from 1.
        private static long TakeAim(BaseSystemData pData, string pKey)
        {
            pData.get(pKey, out long id, -1L);
            pData.removeLong(pKey);
            return id;
        }

        // Whether a creature is under a status still running: what a save keeps, and what a load checks it has handed back.
        private static bool Wears(Actor pActor, string pStatus)
        {
            return pActor.getStatusesDict().TryGetValue(pStatus, out Status status) && !status.is_finished;
        }
    }
}
