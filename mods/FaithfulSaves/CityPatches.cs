using HarmonyLib;

namespace FaithfulSaves
{
    // WB keeps which town a creature belongs to, never since when: a stamp, set the moment it settles in a town other than the one it had.
    internal static class CityPatches
    {
        private const string CityOf = "faithful_city_of"; // the id of the town the stamp was set for, among its custom longs
        private const string CitySince = "faithful_city_since"; // the world's time it settled there, among its custom floats

        // Every way into a town runs through `Actor.setCity`, a load seating each creature again among them: the town it already held is no move.
        // A creature leaving keeps its stamp till it settles somewhere — it dies, or its town falls, more often than it wanders off.
        [HarmonyPostfix]
        [HarmonyPatch(typeof(Actor), "setCity")]
        private static void AfterSetCity(Actor __instance, City __0)
        {
            if (__0 == null)
                return;
            BaseObjectData data = __instance.getData();
            data.get(CityOf, out long held, -1L);
            if (held == __0.getID())
                return;
            data.set(CityOf, __0.getID());
            data.set(CitySince, (float)World.world.getCurWorldTime());
        }
    }
}
