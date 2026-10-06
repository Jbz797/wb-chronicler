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
    // the step it had reached, how long it had been at it, and the pause it was holding.
    internal static class SavePatches
    {
        private const string Log = "[Faithful Saves]: "; // every load says what it handed back, and names what it could not
        private const int LongWait = 90; // a decision's cooldown from which a redrawn wait is rarely sat out before the next load: sleeps, a herd's march
        private const string Possessed = "possessed"; // the one status left out: it is the player's own hand on a creature, which no save holds
        private const string SavedAt = "faithful_saved_at"; // the world's time at the save, in its custom data: proof the mod wrote this very save
        private const string Sleeping = "sleeping"; // handed back through `Actor.makeSleep`, which stills the body as well
        private const string StatusPrefix = "faithful_status_"; // `faithful_status_pregnant`: the seconds that status had left
        private const string Task = "faithful_task"; // the id of the task the creature was at, among its custom strings
        private const string TaskStep = "faithful_task_step"; // which of that task's steps it had reached: `AiSystem.action_index`
        private const string TaskTime = "faithful_task_time"; // the seconds it had been at that task, as its window shows them
        private const string TaskWait = "faithful_task_wait"; // the seconds its pause had left before it acts again: `Actor.timer_action`
        private const string TimerPrefix = "faithful_timer_"; // `faithful_timer_disasters`, in the world's custom data: the seconds before its next turn
        private const string WaitPrefix = "faithful_wait_"; // `faithful_wait_monophasic_sleep`: the seconds before that decision may be taken again
        private const string WaitsKept = "faithful_waits"; // set on a creature whose waits were written: a long wait with no key is over, not unknown

        // The two turns WB takes every 80 seconds, a disaster and a wave of migrants: `clearWorld` rewinds both to a full interval on every load.
        private static readonly string[] _keptTimers = { "disasters", "migrants" };

        private static readonly AccessTools.FieldRef<Actor, AiSystemActor> _ai = AccessTools.FieldRefAccess<Actor, AiSystemActor>("ai");

        private static readonly Func<BaseSimObject, string, float, bool, bool> _addStatusEffect =
            AccessTools.MethodDelegate<Func<BaseSimObject, string, float, bool, bool>>(
                AccessTools.Method(typeof(BaseSimObject), "addStatusEffect", new[] { typeof(string), typeof(float), typeof(bool) }));

        // `Actor._decision_cooldowns`: when each decision was last taken, by `DecisionAsset.decision_index` — 0 for one free to be taken.
        private static readonly AccessTools.FieldRef<Actor, double[]> _lastTaken = AccessTools.FieldRefAccess<Actor, double[]>("_decision_cooldowns");
        private static readonly AccessTools.FieldRef<MapBox, MapStats> _mapStats = AccessTools.FieldRefAccess<MapBox, MapStats>("map_stats");

        private static readonly AccessTools.FieldRef<Actor, float> _pause = AccessTools.FieldRefAccess<Actor, float>("timer_action");

        // `AiSystem`'s own fields, declared on the generic base every thinking thing of the game shares. `task` is `null` between two tasks.
        private static readonly AccessTools.FieldRef<Mind, int> _step = AccessTools.FieldRefAccess<Mind, int>("action_index");
        private static readonly AccessTools.FieldRef<Mind, BehaviourTaskActor> _task = AccessTools.FieldRefAccess<Mind, BehaviourTaskActor>("task");
        private static readonly AccessTools.FieldRef<Mind, double> _taskStart = AccessTools.FieldRefAccess<Mind, double>("_timestamp_task_start");

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
            BehaviourTaskActor task = mind != null ? _task(mind) : null;
            if (task != null)
                data.set(Task, task.id);
            else
                data.removeString(Task);
            Keep(data, TaskStep, task != null ? _step(mind) : 0f);
            Keep(data, TaskTime, task != null ? World.world.getWorldTimeElapsedSince(_taskStart(mind)) : 0f);
            Keep(data, TaskWait, task != null ? _pause(__instance) : 0f);
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

        // WB's last step of a load, every creature standing and its waits just redrawn: the place to hand each status, task, wait and clock back.
        // Whatever a save was given is handed back or named in the log: a key read and dropped in silence would be a thing lost unseen.
        [HarmonyPostfix]
        [HarmonyPatch(typeof(SaveManager), "randomDecisionCooldowns")]
        private static void AfterLoad()
        {
            double now = World.world.getCurWorldTime();
            int statuses = 0, tasks = 0, waits = 0, clocks = 0;
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
                string task = GiveTaskBack(actor, data, now); // after the statuses: a sleeper's pause is the task's own, written the same
                if (task == null)
                    tasks++;
                else if (task.Length > 0)
                    lost.Add($"task {task} of {actor.getName()}");
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
            LogService.LogInfo($"{Log}handed back {statuses} statuses, {tasks} tasks, {waits} long waits and {clocks} clocks");
            if (lost.Count > 0)
                LogService.LogWarning($"{Log}could not hand back {lost.Count}: {string.Join(", ", lost.GetRange(0, Math.Min(lost.Count, 20)))}");
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
        // What a step aims at — a prey, a tile, a wall — is in no save: WB ends a task whose aim is gone, as it does when the prey dies, and the
        // creature picks one anew. Returns `null` once handed back, the id of a task this game no longer has, and nothing where none was kept.
        private static string GiveTaskBack(Actor pActor, BaseObjectData pData, double pNow)
        {
            pData.get(Task, out string id, null);
            pData.removeString(Task);
            float step = Take(pData, TaskStep);
            float time = Take(pData, TaskTime);
            float pause = Take(pData, TaskWait);
            if (string.IsNullOrEmpty(id)) // a creature between two tasks, or a save from before the mod
                return string.Empty;
            AiSystemActor mind = _ai(pActor);
            if (mind == null || !AssetManager.tasks_actor.has(id))
                return id;
            pActor.setTask(id, true, false, false);
            _step(mind) = (int)step;
            _taskStart(mind) = pNow - time; // WB reads the time spent off the moment the task began
            if (pause > 0f)
                pActor.makeWait(pause);
            return null;
        }

        // Every decision of the game with a long wait, whoever takes it: a creature draws from its kind's and from lists all share (`bored_sleep`),
        // not from `Actor.decisions` alone, and WB keeps one wait per decision of the library on each creature.
        private static IEnumerable<DecisionAsset> LongDecisions(double[] pLastTaken)
        {
            foreach (DecisionAsset decision in AssetManager.decisions_library.list)
                if (decision.cooldown >= LongWait && decision.decision_index < pLastTaken.Length)
                    yield return decision;
        }

        // A time left written under its key, the key dropped when nothing is left.
        private static void Keep(BaseSystemData pData, string pKey, float pLeft)
        {
            if (pLeft > 0f)
                pData.set(pKey, pLeft);
            else
                pData.removeFloat(pKey);
        }

        // A kept time read and its key dropped: the game carries it from here, and the next save writes it anew.
        private static float Take(BaseSystemData pData, string pKey)
        {
            pData.get(pKey, out float left, 0f);
            if (left != 0f)
                pData.removeFloat(pKey);
            return left;
        }

        // Whether a creature is under a status still running: what a save keeps, and what a load checks it has handed back.
        private static bool Wears(Actor pActor, string pStatus)
        {
            return pActor.getStatusesDict().TryGetValue(pStatus, out Status status) && !status.is_finished;
        }
    }
}
