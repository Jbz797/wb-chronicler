using HarmonyLib;

namespace FaithfulSaves
{
    // WB keeps which army a creature serves in, never since when: a stamp, set the moment it joins an army other than the one it had.
    internal static class ArmyPatches
    {
        private const string ArmyOf = "faithful_army_of"; // the id of the army the stamp was set for, among its custom longs
        private const string ArmySince = "faithful_army_since"; // the world's time it joined, among its custom floats

        // Every way into an army runs through `Actor.setArmy`, a load mustering each creature again into its own: the army it already held is no move.
        // A creature leaving keeps its stamp till it joins another — `removeFromArmy` hands this method a `null`, which dates nothing.
        [HarmonyPostfix]
        [HarmonyPatch(typeof(Actor), "setArmy")]
        private static void AfterSetArmy(Actor __instance, Army __0)
        {
            if (__0 == null)
                return;
            BaseObjectData data = __instance.getData();
            data.get(ArmyOf, out long held, -1L);
            if (held == __0.getID())
                return;
            data.set(ArmyOf, __0.getID());
            data.set(ArmySince, (float)World.world.getCurWorldTime());
        }
    }
}
