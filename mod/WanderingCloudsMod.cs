using HarmonyLib;
using NeoModLoader.api;
using NeoModLoader.services;
using UnityEngine;

namespace WanderingClouds
{
    // NML finds the mod through `IMod`; the patches go in on load, before any world ticks.
    public class WanderingCloudsMod : MonoBehaviour, IMod
    {
        private ModDeclare _declare;
        private GameObject _gameObject;

        public ModDeclare GetDeclaration() => _declare;

        public GameObject GetGameObject() => _gameObject;

        public string GetUrl() => _declare?.RepoUrl ?? string.Empty;

        // Keeps what NML hands over, then patches the cloud once for the whole session.
        public void OnLoad(ModDeclare pModDecl, GameObject pGameObject)
        {
            _declare = pModDecl;
            _gameObject = pGameObject;
            Harmony.CreateAndPatchAll(typeof(CloudPatches), pModDecl.UID);
            LogService.LogInfo($"[{pModDecl.Name}]: clouds now rise anywhere and drift either way");
        }
    }
}
