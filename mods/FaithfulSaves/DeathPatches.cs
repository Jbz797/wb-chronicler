using System.Collections.Generic;
using db;
using HarmonyLib;
using SQLite;

namespace FaithfulSaves
{
    // WB keeps nothing of the dead: every death of the world, each by who died, of what, when, where and by whose hand, in a table of its history database.
    // A metamorphosis ends a body under a blow WB then forgets, neither counting the death nor crediting the killer: the blow and its author are kept too.
    internal static class DeathPatches
    {
        private const string Create = "CREATE TABLE IF NOT EXISTS " + Table + " (id INTEGER PRIMARY KEY, asset_id TEXT, name TEXT, subspecies INTEGER, "
            + "parent_id_1 INTEGER, parent_id_2 INTEGER, born REAL, died REAL, cause TEXT, killer INTEGER, x INTEGER, y INTEGER, blow TEXT, job TEXT)";
        private const string Blow = "blow"; // the column a table from 1.7.0 lacks, added at its first save under 1.8.0
        private const string Job = "job"; // the column a table before 1.10.0 lacks, added at its first save under it
        private const string From = "faithful_deaths_from"; // the world's time since which the table misses no death: the mod's first death or save there
        private const string Insert = "INSERT OR REPLACE INTO " + Table + " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)";
        private const string Table = "FaithfulDeaths";

        private static readonly AccessTools.FieldRef<Actor, BaseSimObject> _attackedBy = AccessTools.FieldRefAccess<Actor, BaseSimObject>("attackedBy");
        private static readonly AccessTools.FieldRef<Actor, AttackType> _lastAttackType = AccessTools.FieldRefAccess<Actor, AttackType>("_last_attack_type");
        private static readonly AccessTools.FieldRef<MapBox, MapStats> _mapStats = AccessTools.FieldRefAccess<MapBox, MapStats>("map_stats");

        // WB files a bolt's hit under `Other` with the heat and the sun: whether a bolt is striking now, and the bodies whose last hit was one.
        private static bool _bolting;
        private static readonly HashSet<long> _boltStruck = new HashSet<long>();

        // The deaths since the last save, written into the database only as a save copies it out: a load wipes them with the world they fell in.
        private static readonly List<object[]> _pending = new List<object[]>();

        // `Actor.checkDeath` names the killer through `newKillAction` right before the victim's `die`: held till then.
        private static long _killer = -1;
        private static long _victim = -1;

        // Every bolt, a cloud's, a spell's or a god's, strikes through `MapAction.checkLightningAction`: a finalizer, so a throw never leaves it on.
        [HarmonyFinalizer]
        [HarmonyPatch(typeof(MapAction), "checkLightningAction")]
        private static void AfterBolt() => _bolting = false;

        [HarmonyPostfix]
        [HarmonyPatch(typeof(Actor), "newKillAction")]
        private static void AfterNewKillAction(Actor __instance, Actor __0)
        {
            if (__0 == null)
                return;
            _killer = __instance.getID();
            _victim = __0.getID();
        }

        [HarmonyPrefix]
        [HarmonyPatch(typeof(MapAction), "checkLightningAction")]
        private static void BeforeBolt() => _bolting = true;

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
            _victim = -1;
            // `getHit` runs the death actions (a crab's rebirth, a cursed body's skeleton) once health is spent, before `checkDeath` would credit the blow.
            if (__1 == AttackType.Metamorphosis)
            {
                blow = Named(_lastAttackType(__instance), id);
                if (_attackedBy(__instance) is Actor hitter && !hitter.isRekt())
                    killer = hitter.getID();
            }
            WorldTile tile = __instance.current_tile;
            _pending.Add(new object[]
            {
                id, __instance.asset.id, data.name, data.subspecies, data.parent_id_1, data.parent_id_2, data.created_time, World.world.getCurWorldTime(),
                Named(__1, id), killer, tile?.x ?? 0, tile?.y ?? 0, blow, JobOf(__instance),
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
                foreach (string column in new[] { Blow, Job })
                {
                    if (!connection.GetTableInfo(Table).Exists(kept => kept.Name == column))
                        connection.Execute("ALTER TABLE " + Table + " ADD COLUMN " + column + " TEXT");
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
    }
}
