using System.Collections.Generic;
using System.Reflection;
using System.Reflection.Emit;
using HarmonyLib;
using NeoModLoader.services;

namespace FaithfulSaves
{
    // WB closes a year of its history as the year's 12th month opens, so each row runs from one December to the next November. It now closes it as
    // the next January opens, and dates the row by the year that ended: a row is a calendar year, and the year under way begins in January.
    internal static class HistoryPatches
    {
        // `MapBox.updateMetaHistory` waits for `Date.getCurrentMonth() == 12`, then files the row under `Date.getCurrentYear()`: the month becomes 1,
        // the year the one before. Its checks, its collectors and its reset of the year's tallies stay WB's own.
        [HarmonyTranspiler]
        [HarmonyPatch(typeof(MapBox), "updateMetaHistory")]
        private static IEnumerable<CodeInstruction> CloseAtYearEnd(IEnumerable<CodeInstruction> pCodes)
        {
            MethodInfo month = AccessTools.Method(typeof(Date), nameof(Date.getCurrentMonth));
            MethodInfo year = AccessTools.Method(typeof(Date), nameof(Date.getCurrentYear));
            List<CodeInstruction> codes = new List<CodeInstruction>(pCodes);
            int check = -1, read = -1;
            for (int i = 0; i < codes.Count; i++)
            {
                if (codes[i].Calls(month) && i + 1 < codes.Count && codes[i + 1].LoadsConstant(12))
                    check = check == -1 ? i + 1 : -2;
                else if (codes[i].Calls(year))
                    read = read == -1 ? i : -2;
            }
            if (check < 0 || read < 0) // a game update that reshapes the method: left whole, on WB's own calendar, and said
            {
                LogService.LogWarning("[Faithful Saves]: history kept on WB's own calendar — `updateMetaHistory` no longer reads as expected");
                return codes;
            }
            codes[check].opcode = OpCodes.Ldc_I4_1; // the labels a branch lands on stay with the instruction: only what it does changes
            codes[check].operand = null;
            codes[read].operand = AccessTools.Method(typeof(HistoryPatches), nameof(EndedYear));
            return codes;
        }

        // The year January closes: the one before the year that has just begun.
        public static int EndedYear() => Date.getCurrentYear() - 1;
    }
}
