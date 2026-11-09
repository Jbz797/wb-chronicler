using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using db;
using HarmonyLib;
using SQLite;

namespace FaithfulSaves
{
    // WB keeps nothing of the dead: every death of the world, each by who died, of what, when, where and by whose hand, in a table of its history database.
    // A metamorphosis ends a body under a blow WB then forgets, neither counting the death nor crediting the killer: the blow, its author and the new body kept too.
    internal static class DeathPatches
    {
        private const string Create = "CREATE TABLE IF NOT EXISTS " + Table + " (id INTEGER PRIMARY KEY, asset_id TEXT, name TEXT, subspecies INTEGER, "
            + "parent_id_1 INTEGER, parent_id_2 INTEGER, born REAL, died REAL, cause TEXT, killer INTEGER, x INTEGER, y INTEGER, blow TEXT, job TEXT, "
            + "became INTEGER, sex TEXT, overgrowth INTEGER)";
        private const string Became = "became"; // the column a table before 1.13.0 lacks, added at its first save under it
        private const string Blow = "blow"; // the column a table from 1.7.0 lacks, added at its first save under 1.8.0
        private const string Job = "job"; // the column a table before 1.10.0 lacks, added at its first save under it
        private const string Overgrowth = "overgrowth"; // the column a table before 1.16.0 lacks, added at its first save under it
        private const string Sex = "sex"; // the column a table before 1.15.0 lacks, added at its first save under it
        private const string From = "faithful_deaths_from"; // the world's time since which the table misses no death: the mod's first death or save there
        private const string Insert = "INSERT OR REPLACE INTO " + Table + " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)";
        private const string Table = "FaithfulDeaths";

        private static readonly AccessTools.FieldRef<Actor, BaseSimObject> _attackedBy = AccessTools.FieldRefAccess<Actor, BaseSimObject>("attackedBy");
        private static readonly AccessTools.FieldRef<Actor, AttackType> _lastAttackType = AccessTools.FieldRefAccess<Actor, AttackType>("_last_attack_type");
        private static readonly AccessTools.FieldRef<MapBox, MapStats> _mapStats = AccessTools.FieldRefAccess<MapBox, MapStats>("map_stats");

        // WB files a bolt's hit under `Other` with the heat and the sun: whether a bolt is striking now, and the bodies whose last hit was one.
        private static bool _bolting;
        private static readonly HashSet<long> _boltStruck = new HashSet<long>();

        // Every metamorphosis copies the old body onto the new one right before the old one's `die`: the last copy, held till then.
        private static long _copiedFrom = -1;
        private static long _copiedTo = -1;

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

        [HarmonyPostfix]
        [HarmonyPatch(typeof(ai.ActorTool), "copyUnitToOtherUnit")]
        private static void AfterUnitCopied(Actor __0, Actor __1)
        {
            _copiedFrom = __0.getID();
            _copiedTo = __1.getID();
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
            object blow = null;
            object became = null;
            _victim = -1;
            // `getHit` runs the death actions (a crab's rebirth, a cursed body's skeleton) once health is spent, before `checkDeath` would credit the blow.
            if (__1 == AttackType.Metamorphosis)
            {
                blow = Named(_lastAttackType(__instance), id);
                if (_copiedFrom == id)
                    became = _copiedTo;
                _copiedFrom = -1;
                if (_attackedBy(__instance) is Actor hitter && !hitter.isRekt())
                    killer = hitter.getID();
            }
            WorldTile tile = __instance.current_tile;
            _pending.Add(new object[]
            {
                id, __instance.asset.id, data.name, data.subspecies, data.parent_id_1, data.parent_id_2, data.created_time, World.world.getCurWorldTime(),
                Named(__1, id), killer, tile?.x ?? 0, tile?.y ?? 0, blow, JobOf(__instance), became, data.sex.ToString(), data.age_overgrowth,
            });
            _boltStruck.Remove(id);
            MarkFrom();
        }

        // `Actor.getHit` sets the body's last attack type first thing, the one `die` is handed: a bolt's mark follows it hit for hit.
        [HarmonyPrefix]
        [HarmonyPatch(typeof(Actor), "getHit")]
        private static void BeforeGetHit(Actor __instance, AttackType __2)
        {
            if (_bolting && __2 == AttackType.Other)
                _boltStruck.Add(__instance.getID());
            else
                _boltStruck.Remove(__instance.getID());
        }

        // A world left for another, or loaded anew: the deaths not yet saved fell in a world no save will hold.
        [HarmonyPrefix]
        [HarmonyPatch(typeof(DBManager), nameof(DBManager.clearAndClose))]
        private static void BeforeWorldClosed()
        {
            _boltStruck.Clear();
            _pending.Clear();
        }

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
                foreach ((string column, string type) in new[] { (Blow, "TEXT"), (Job, "TEXT"), (Became, "INTEGER"), (Sex, "TEXT"), (Overgrowth, "INTEGER") })
                {
                    if (!connection.GetTableInfo(Table).Exists(kept => kept.Name == column))
                        connection.Execute("ALTER TABLE " + Table + " ADD COLUMN " + column + " " + type);
                }
                connection.RunInTransaction(() => _pending.ForEach(row => connection.Execute(Insert, row)));
            }
            _pending.Clear();
        }

        // A world saved before its first death still says since when the table holds, an empty one meaning no death since.
        [HarmonyPrefix]
        [HarmonyPatch(typeof(SaveManager), nameof(SaveManager.currentWorldToSavedMap))]
        private static void BeforeWorldSave() => MarkFrom();

        // A cause as WB names it, `Lightning` apart where the body's last hit was a bolt's.
        private static string Named(AttackType type, long id) => type == AttackType.Other && _boltStruck.Contains(id) ? "Lightning" : type.ToString();

        // The post a body dies in, as the chronicle's tools word the save's `profession`, a warrior leading an army apart: `civilian` for any other, beasts too.
        private static string JobOf(Actor actor)
        {
            if (actor.is_army_captain)
                return "army_captain";
            switch (actor.getProfession())
            {
                case UnitProfession.King: return "king";
                case UnitProfession.Leader: return "leader";
                case UnitProfession.Unit: return "civilian";
                case UnitProfession.Warrior: return "warrior";
                default: return null;
            }
        }

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

        // Every bolt, a cloud's, a spell's or a god's, falls through a `MapBox.spawnLightning*`: its strike, then its blast (`damageWorld`).
        [HarmonyPatch]
        internal static class Bolts
        {
            private static IEnumerable<MethodBase> TargetMethods()
            {
                return new[] { "spawnLightningBig", "spawnLightningMedium", "spawnLightningSmall" }.Select(name => AccessTools.Method(typeof(MapBox), name));
            }

            // A finalizer, so a throw never leaves the bolt striking.
            [HarmonyFinalizer]
            private static void Finalizer() => _bolting = false;

            [HarmonyPrefix]
            private static void Prefix() => _bolting = true;
        }
    }
}
