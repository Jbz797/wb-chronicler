using System;
using HarmonyLib;
using UnityEngine;

namespace WanderingClouds
{
    // WB raises every cloud on the west edge (`BaseEffect.prepare`: x in -50..29) and blows it east, so a young world's first seeds of life
    // all fall in its west. A cloud the world raises by itself now rises anywhere across the width and drifts either way; one a god drops is left as it was.
    [HarmonyPatch(typeof(Cloud))]
    internal static class CloudPatches
    {
        private const int Alive = 1; // `BaseEffect.state`: 1 while it lives and fades in, 2 once `startToDie` has it fading out

        private static readonly AccessTools.FieldRef<Cloud, float> _speed = AccessTools.FieldRefAccess<Cloud, float>("speed");
        private static readonly Action<BaseEffect> _startToDie =
            AccessTools.MethodDelegate<Action<BaseEffect>>(AccessTools.Method(typeof(BaseEffect), "startToDie"));
        private static readonly AccessTools.FieldRef<BaseEffect, int> _state = AccessTools.FieldRefAccess<BaseEffect, int>("state");

        // A world-raised cloud comes with no tile: lift it off the west edge, and turn it back west half the time.
        [HarmonyPostfix]
        [HarmonyPatch(nameof(Cloud.spawn))]
        private static void AfterSpawn(Cloud __instance, WorldTile pTile)
        {
            if (pTile != null)
                return;
            Transform transform = __instance.transform;
            Vector3 position = transform.position;
            transform.position = new Vector3(Randy.randomFloat(0f, MapBox.width), position.y, position.z);
            if (Randy.randomBool())
                _speed(__instance) = -_speed(__instance); // `update` moves it by `speed`, so a negative one blows it west
        }

        // WB lets a cloud die only past the east edge: one blowing west would drift on forever, off the map.
        [HarmonyPostfix]
        [HarmonyPatch(nameof(Cloud.update))]
        private static void AfterUpdate(Cloud __instance)
        {
            if (_speed(__instance) < 0f && _state(__instance) == Alive && __instance.transform.localPosition.x < 0f)
                _startToDie(__instance);
        }
    }
}
