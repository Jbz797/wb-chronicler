using System.Collections.Generic;
using db;
using HarmonyLib;
using SQLite;

namespace FaithfulSaves
{
    // WB keeps nothing of the dead: every death of the world, each by who died, of what, when, where and by whose hand, in a table of its history database.
    internal static class DeathPatches
    {
        private const string Create = "CREATE TABLE IF NOT EXISTS " + Table + " (id INTEGER PRIMARY KEY, asset_id TEXT, name TEXT, subspecies INTEGER, "
            + "parent_id_1 INTEGER, parent_id_2 INTEGER, born REAL, died REAL, cause TEXT, killer INTEGER, x INTEGER, y INTEGER)";
        private const string From = "faithful_deaths_from"; // the world's time since which the table misses no death: the mod's first death or save there
        private const string Insert = "INSERT OR REPLACE INTO " + Table + " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)";
        private const string Table = "FaithfulDeaths";

        private static readonly AccessTools.FieldRef<MapBox, MapStats> _mapStats = AccessTools.FieldRefAccess<MapBox, MapStats>("map_stats");

        // The deaths since the last save, written into the database only as a save copies it out: a load wipes them with the world they fell in.
        private static readonly List<object[]> _pending = new List<object[]>();

        // `Actor.checkDeath` names the killer through `newKillAction` right before the victim's `die`: held till then.
        private static long _killer = -1;
        private static long _victim = -1;

        [HarmonyPostfix]
        [HarmonyPatch(typeof(Actor), "newKillAction")]
        private static void AfterNewKillAction(Actor __instance, Actor __0)
        {
            if (__0 == null)
                return;
            _killer = __instance.getID();
            _victim = __0.getID();
        }

        // `Actor.die` is every death's way out, counted or not (a metamorphosis, a god's finger); a call on a body already dead ends its dying animation.
        [HarmonyPrefix]
        [HarmonyPatch(typeof(Actor), "die")]
        private static void BeforeDie(Actor __instance, AttackType __1)
        {
            if (!__instance.isAlive())
                return;
            ActorData data = (ActorData)__instance.getData();
            long id = __instance.getID();
            object killer = _victim == id ? _killer : null;
            _victim = -1;
            WorldTile tile = __instance.current_tile;
            _pending.Add(new object[]
            {
                id, __instance.asset.id, data.name, data.subspecies, data.parent_id_1, data.parent_id_2, data.created_time, World.world.getCurWorldTime(),
                __1.ToString(), killer, tile?.x ?? 0, tile?.y ?? 0,
            });
            MarkFrom();
        }

        // A world left for another, or loaded anew: the deaths not yet saved fell in a world no save will hold.
        [HarmonyPrefix]
        [HarmonyPatch(typeof(DBManager), nameof(DBManager.clearAndClose))]
        private static void BeforeWorldClosed() => _pending.Clear();

        // As WB copies its history out to the save's folder: the deaths since the last save go in first, under its own lock.
        [HarmonyPrefix]
        [HarmonyPatch(typeof(DBManager), nameof(DBManager.saveToPath))]
        private static void BeforeHistorySaved()
        {
            if (Config.disable_db)
                return;
            SQLiteConnectionWithLock connection = DBManager.getSyncConnection();
            using (connection.Lock())
            {
                connection.Execute(Create);
                connection.RunInTransaction(() => _pending.ForEach(row => connection.Execute(Insert, row)));
            }
            _pending.Clear();
        }

        // A world saved before its first death still says since when the table holds, an empty one meaning no death since.
        [HarmonyPrefix]
        [HarmonyPatch(typeof(SaveManager), nameof(SaveManager.currentWorldToSavedMap))]
        private static void BeforeWorldSave() => MarkFrom();

        // The table's start, set once in the save: deaths before the mod ran are none of its knowing.
        private static void MarkFrom()
        {
            BaseSystemData data = _mapStats(World.world)?.custom_data;
            if (data == null)
                return;
            data.get(From, out float from, -1f);
            if (from < 0f)
                data.set(From, (float)World.world.getCurWorldTime());
        }
    }
}
