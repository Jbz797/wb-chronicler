using HarmonyLib;

namespace WanderingClouds
{
    // Nothing of a cloud is kept in a save, so nothing in one says the mod ran. The chronicle this mod ships with only follows a world it runs on:
    // each save now carries the world's time under the mod's key, which a save written without the mod cannot match.
    internal static class SaveStamp
    {
        private const string SavedAt = "wandering_clouds_saved_at"; // in the world's custom data, which WB saves: a time, where a flag would outlive the mod

        private static readonly AccessTools.FieldRef<MapBox, MapStats> _mapStats = AccessTools.FieldRefAccess<MapBox, MapStats>("map_stats");

        // Before WB gathers the world into a save.
        [HarmonyPrefix]
        [HarmonyPatch(typeof(SaveManager), nameof(SaveManager.currentWorldToSavedMap))]
        private static void BeforeWorldSave()
        {
            _mapStats(World.world)?.custom_data?.set(SavedAt, (float)World.world.getCurWorldTime());
        }
    }
}
