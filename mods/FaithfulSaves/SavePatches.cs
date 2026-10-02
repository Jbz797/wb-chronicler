using System;
using System.Collections.Generic;
using HarmonyLib;

namespace FaithfulSaves
{
    // WB writes no status into a save: a load ends every pregnancy with no birth, hatches every egg, puts out every burning body, lifts the
    // afterglow that spaces two matings and wakes every sleeper. It then redraws at random how long each creature must wait before its next
    // sleep, and winds the world's own clocks back. The time each of those had left now rides in custom data, which WB does save — the
    // creature's own, or the world's —, and is handed back once the world is loaded.
    internal static class SavePatches
    {
        private const int LongWait = 90; // a decision's cooldown from which a redrawn wait is rarely sat out before the next load: sleeps, a herd's march
        private const string Possessed = "possessed"; // the one status left out: it is the player's own hand on a creature, which no save holds
        private const string SavedAt = "faithful_saved_at"; // the world's time at the save, in its custom data: proof the mod wrote this very save
        private const string Sleeping = "sleeping"; // handed back through `Actor.makeSleep`, which stills the body as well
        private const string StatusPrefix = "faithful_status_"; // `faithful_status_pregnant`: the seconds that status had left
        private const string TimerPrefix = "faithful_timer_"; // `faithful_timer_disasters`, in the world's custom data: the seconds before its next turn
        private const string WaitPrefix = "faithful_wait_"; // `faithful_wait_monophasic_sleep`: the seconds before that decision may be taken again
        private const string WaitsKept = "faithful_waits"; // set on a creature whose waits were written: a long wait with no key is over, not unknown

        // The two turns WB takes every 80 seconds, a disaster and a wave of migrants: `clearWorld` rewinds both to a full interval on every load.
        private static readonly string[] _keptTimers = { "disasters", "migrants" };

        private static readonly Func<BaseSimObject, string, float, bool, bool> _addStatusEffect =
            AccessTools.MethodDelegate<Func<BaseSimObject, string, float, bool, bool>>(
                AccessTools.Method(typeof(BaseSimObject), "addStatusEffect", new[] { typeof(string), typeof(float), typeof(bool) }));

        // `Actor._decision_cooldowns`: when each decision was last taken, by `DecisionAsset.decision_index` — 0 for one free to be taken.
        private static readonly AccessTools.FieldRef<Actor, double[]> _lastTaken = AccessTools.FieldRefAccess<Actor, double[]>("_decision_cooldowns");
        private static readonly AccessTools.FieldRef<MapBox, MapStats> _mapStats = AccessTools.FieldRefAccess<MapBox, MapStats>("map_stats");
        private static readonly AccessTools.FieldRef<WorldBehaviour, float> _timer = AccessTools.FieldRefAccess<WorldBehaviour, float>("_timer");

        // Before WB serialises a creature: what each status and each long wait has left, or no key at all — a stale one would hand back a time long over.
        [HarmonyPrefix]
        [HarmonyPatch(typeof(Actor), nameof(Actor.prepareForSave))]
        private static void BeforeSave(Actor __instance)
        {
            BaseObjectData data = __instance.getData();
            IReadOnlyDictionary<string, Status> statuses = __instance.getStatusesDict();
            foreach (StatusAsset asset in AssetManager.status.list)
            {
                bool kept = asset.id != Possessed && statuses.TryGetValue(asset.id, out Status status) && !status.is_finished;
                Keep(data, StatusPrefix + asset.id, kept ? (float)statuses[asset.id].getRemainingTime() : 0f);
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

        // WB's last step of a load, every creature standing and its waits just redrawn: the place to hand each status, wait and clock back.
        [HarmonyPostfix]
        [HarmonyPatch(typeof(SaveManager), "randomDecisionCooldowns")]
        private static void AfterLoad()
        {
            double now = World.world.getCurWorldTime();
            foreach (Actor actor in World.world.units)
            {
                BaseObjectData data = actor.getData();
                foreach (StatusAsset asset in AssetManager.status.list)
                {
                    float left = Take(data, StatusPrefix + asset.id);
                    if (left > 0f)
                        GiveBack(actor, asset, left);
                }
                double[] lastTaken = _lastTaken(actor);
                if (lastTaken == null || Take(data, WaitsKept) == 0f) // no mark: a save from before the mod, left to the waits WB has just drawn
                    continue;
                foreach (DecisionAsset decision in LongDecisions(lastTaken))
                {
                    float left = Take(data, WaitPrefix + decision.id);
                    lastTaken[decision.decision_index] = left > 0f ? now - (decision.cooldown - left) : 0d; // WB reads a wait off the time it began
                }
            }
            BaseSystemData world = _mapStats(World.world)?.custom_data;
            if (world == null)
                return;
            foreach (string id in _keptTimers)
            {
                float left = Take(world, TimerPrefix + id);
                WorldBehaviour clock = AssetManager.world_behaviours.get(id)?.manager;
                if (left > 0f && clock != null)
                    _timer(clock) = left;
            }
        }

        // A status handed back for the time it had left, without what WB does on first posing it: the mood it brought was felt, and saved, already.
        private static void GiveBack(Actor pActor, StatusAsset pAsset, float pLeft)
        {
            if (pAsset.id == Sleeping)
            {
                pActor.makeSleep(pLeft);
                return;
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
    }
}
