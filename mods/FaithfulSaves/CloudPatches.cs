using System;
using System.Collections.Generic;
using System.Globalization;
using HarmonyLib;
using NeoModLoader.services;
using UnityEngine;

namespace FaithfulSaves
{
    // WB writes no cloud into a save: a cloud is an effect of the sky, not a thing of the world, and a load clears the sky. A cloud of rage hanging
    // over a town, a cloud of life halfway across the map, are gone, and the drops they had yet to let fall with them. Each cloud the sky holds is
    // now kept in the world's custom data — its kind, where it stands, its speed and heading, what is left of a summoned cloud's life, its sprite and
    // the reach of its drops, which that sprite sets — and raised
    // again where it was once the world is loaded.
    internal static class CloudPatches
    {
        private const int Alive = 1; // `BaseEffect.state` while a cloud lives: 2 once it fades out, which is not kept
        private const string Clouds = "faithful_clouds"; // in the world's custom strings, one per `;`: `kind x y speed left sprite flip reach_x reach_y`
        private const string Effect = "fx_cloud"; // the effect every cloud is, wild or summoned
        private const string Log = "[Faithful Saves]: ";

        // The sky's own list of clouds, both steps internal to WB: the controller its stack keeps for an effect, and that controller's effects.
        private static readonly Func<StackEffects, string, BaseEffectController> _controller =
            AccessTools.MethodDelegate<Func<StackEffects, string, BaseEffectController>>(AccessTools.Method(typeof(StackEffects), "get"));
        private static readonly Func<BaseEffectController, List<BaseEffect>> _effects =
            AccessTools.MethodDelegate<Func<BaseEffectController, List<BaseEffect>>>(AccessTools.Method(typeof(BaseEffectController), "getList"));

        private static readonly AccessTools.FieldRef<BaseEffect, bool> _active = AccessTools.FieldRefAccess<BaseEffect, bool>("active");
        private static readonly AccessTools.FieldRef<Cloud, float> _aliveTime = AccessTools.FieldRefAccess<Cloud, float>("alive_time");
        // 0 for a wild cloud, which lives till it leaves the map: only a cloud a plot summons is given a life.
        private static readonly AccessTools.FieldRef<Cloud, float> _lifespan = AccessTools.FieldRefAccess<Cloud, float>("_lifespan");
        private static readonly AccessTools.FieldRef<MapBox, MapStats> _mapStats = AccessTools.FieldRefAccess<MapBox, MapStats>("map_stats");

        // How far around it a cloud's drops fall, in tiles: `Cloud.prepare` reads it off the sprite it drew, and `CloudLibrary.dropAction` off these.
        private static readonly AccessTools.FieldRef<Cloud, float> _reachX = AccessTools.FieldRefAccess<Cloud, float>("effect_texture_width");
        private static readonly AccessTools.FieldRef<Cloud, float> _reachY = AccessTools.FieldRefAccess<Cloud, float>("effect_texture_height");

        private static readonly AccessTools.FieldRef<BaseEffect, SpriteRenderer> _renderer =
            AccessTools.FieldRefAccess<BaseEffect, SpriteRenderer>("sprite_renderer");
        private static readonly AccessTools.FieldRef<Cloud, float> _speed = AccessTools.FieldRefAccess<Cloud, float>("speed"); // negative: drifting west
        private static readonly AccessTools.FieldRef<CloudAsset, Sprite[]> _sprites = AccessTools.FieldRefAccess<CloudAsset, Sprite[]>("cached_sprites");
        private static readonly AccessTools.FieldRef<MapBox, StackEffects> _stackEffects = AccessTools.FieldRefAccess<MapBox, StackEffects>("stack_effects");
        private static readonly AccessTools.FieldRef<BaseEffect, int> _state = AccessTools.FieldRefAccess<BaseEffect, int>("state");

        // Before WB gathers the world into a save: every living cloud, or no key at all, so a stale sky is never raised again.
        [HarmonyPrefix]
        [HarmonyPatch(typeof(SaveManager), nameof(SaveManager.currentWorldToSavedMap))]
        private static void BeforeWorldSave()
        {
            BaseSystemData data = _mapStats(World.world)?.custom_data;
            if (data == null)
                return;
            List<string> kept = new List<string>();
            StackEffects sky = _stackEffects(World.world);
            BaseEffectController controller = sky != null ? _controller(sky, Effect) : null;
            foreach (BaseEffect effect in controller != null ? _effects(controller) : new List<BaseEffect>())
            {
                if (!(effect is Cloud cloud) || !_active(cloud) || _state(cloud) != Alive)
                    continue;
                Vector3 at = cloud.transform.localPosition; // in tiles, as its drops fall: `CloudLibrary.dropAction` reads the same
                float left = _lifespan(cloud) > 0f ? Math.Max(_lifespan(cloud) - _aliveTime(cloud), 0.01f) : 0f;
                SpriteRenderer look = _renderer(cloud);
                int sprite = look != null ? Array.IndexOf(_sprites(cloud.asset) ?? new Sprite[0], look.sprite) : -1;
                string flip = look != null && look.flipX ? "1" : "0";
                string where = string.Join(" ", Number(at.x), Number(at.y), Number(_speed(cloud)), Number(left));
                string seen = string.Join(" ", sprite.ToString(CultureInfo.InvariantCulture), flip, Number(_reachX(cloud)), Number(_reachY(cloud)));
                kept.Add($"{cloud.asset.id} {where} {seen}");
            }
            if (kept.Count > 0)
                data.set(Clouds, string.Join(";", kept));
            else
                data.removeString(Clouds);
        }

        // WB's very last step of a load: each kept cloud raised at its tile, as a god's hand would (`Wandering Clouds` leaves such a cloud where it is),
        // then set back to its exact place, speed and heading. A kind this game no longer has, or a sky past its limit, is named in the log.
        [HarmonyPostfix]
        [HarmonyPatch(typeof(MapBox), "finishingUpLoading")]
        private static void AfterWorldLoaded()
        {
            BaseSystemData data = _mapStats(World.world)?.custom_data;
            if (data == null)
                return;
            data.get(Clouds, out string kept, null);
            data.removeString(Clouds);
            if (string.IsNullOrEmpty(kept))
                return;
            List<string> lost = new List<string>();
            foreach (string entry in kept.Split(';'))
            {
                string[] parts = entry.Split(' ');
                if (!Raise(parts))
                    lost.Add($"cloud {parts[0]}");
            }
            if (lost.Count > 0)
                LogService.LogWarning($"{Log}could not hand back {lost.Count}: {string.Join(", ", lost.GetRange(0, Math.Min(lost.Count, 20)))}");
        }

        private static string Number(float pValue) => pValue.ToString("0.###", CultureInfo.InvariantCulture); // a French locale would write `12,5`

        // One kept cloud raised again: its kind, at the tile under its place, then moved to the place itself, with its speed and what its life had left.
        private static bool Raise(string[] pParts)
        {
            if (pParts.Length < 5 || AssetManager.clouds.get(pParts[0]) == null || !Parse(pParts[1], out float x) || !Parse(pParts[2], out float y)
                || !Parse(pParts[3], out float speed) || !Parse(pParts[4], out float left))
                return false;
            WorldTile tile = World.world.GetTile(Mathf.Clamp((int)x, 0, MapBox.width - 1), Mathf.Clamp((int)y, 0, MapBox.height - 1));
            if (tile == null || !(EffectsLibrary.spawn(Effect, tile, pParts[0]) is Cloud cloud))
                return false;
            Transform transform = cloud.transform;
            transform.localPosition = new Vector3(x, y, transform.localPosition.z);
            _speed(cloud) = speed;
            if (left > 0f)
                cloud.setLifespan(left); // a summoned cloud's life, counted again from a fresh `alive_time`
            if (pParts.Length >= 9)
                GiveLookBack(cloud, pParts);
            return true;
        }

        // The sprite a cloud had drawn, its mirroring and the reach of its drops: a load draws a sprite anew, and a smaller one would rain on less.
        private static void GiveLookBack(Cloud pCloud, string[] pParts)
        {
            Sprite[] sprites = _sprites(pCloud.asset);
            SpriteRenderer look = _renderer(pCloud);
            if (look != null && sprites != null && int.TryParse(pParts[5], NumberStyles.Integer, CultureInfo.InvariantCulture, out int sprite) && sprite >= 0
                && sprite < sprites.Length)
            {
                look.sprite = sprites[sprite];
                look.flipX = pParts[6] == "1";
            }
            if (Parse(pParts[7], out float reachX) && Parse(pParts[8], out float reachY))
            {
                _reachX(pCloud) = reachX;
                _reachY(pCloud) = reachY;
            }
        }

        private static bool Parse(string pText, out float pValue) => float.TryParse(pText, NumberStyles.Float, CultureInfo.InvariantCulture, out pValue);
    }
}
