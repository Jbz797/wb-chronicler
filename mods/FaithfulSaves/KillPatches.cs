using System.Collections.Generic;
using System.Globalization;
using HarmonyLib;

namespace FaithfulSaves
{
    // WB counts the deaths a creature deals, never whom: a stamp of its latest victims, each by id, kind, name and the world's time it fell.
    internal static class KillPatches
    {
        private const int Kept = 3; // victims the stamp keeps: enough to name who fell near a village, never a ledger the save swells with
        private const string Kills = "faithful_kills"; // among its custom strings: one victim a line, `id\tasset\tname\ttime`, the newest last

        // `Actor.checkDeath` hands the killer `newKillAction` once per death it deals, the victim first: a hull's as a creature's.
        [HarmonyPostfix]
        [HarmonyPatch(typeof(Actor), "newKillAction")]
        private static void AfterNewKillAction(Actor __instance, Actor __0)
        {
            if (__0 == null)
                return;
            BaseObjectData data = __instance.getData();
            data.get(Kills, out string held, "");
            List<string> lines = new List<string>((held ?? "").Split(new[] { '\n' }, System.StringSplitOptions.RemoveEmptyEntries));
            string name = (__0.getData().name ?? "").Replace('\t', ' ').Replace('\n', ' '); // a name holds neither, or the line would split
            string time = ((float)World.world.getCurWorldTime()).ToString("R", CultureInfo.InvariantCulture); // a dot whatever the player's locale
            lines.Add($"{__0.getID()}\t{__0.asset.id}\t{name}\t{time}");
            if (lines.Count > Kept)
                lines.RemoveRange(0, lines.Count - Kept);
            data.set(Kills, string.Join("\n", lines));
        }
    }
}
