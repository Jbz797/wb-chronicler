using HarmonyLib;

namespace FaithfulSaves
{
    // WB keeps who a creature loves, never since when: a stamp on both lovers, set the moment they become a couple.
    internal static class LoverPatches
    {
        private const string LoverOf = "faithful_lover_of"; // the id of the lover the stamp was set for, among its custom longs
        private const string LoverSince = "faithful_lover_since"; // the world's time they became a couple, among its custom floats

        // `Actor.becomeLoversWith` is the one way two become a couple: a load pairs lovers again through `setLover` alone, leaving the stamp as it was.
        [HarmonyPostfix]
        [HarmonyPatch(typeof(Actor), "becomeLoversWith")]
        private static void AfterBecomeLovers(Actor __instance, Actor __0)
        {
            float now = (float)World.world.getCurWorldTime();
            Stamp(__instance, __0, now);
            Stamp(__0, __instance, now);
        }

        private static void Stamp(Actor creature, Actor lover, float now)
        {
            BaseObjectData data = creature.getData();
            data.set(LoverOf, lover.getID());
            data.set(LoverSince, now);
        }
    }
}
