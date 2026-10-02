using HarmonyLib;
using NeoModLoader.api;
using NeoModLoader.services;
using UnityEngine;

namespace FaithfulSaves
{
    // NML finds the mod through `IMod`; the patches go in on load, before any world is saved or loaded.
    public class FaithfulSavesMod : MonoBehaviour, IMod
    {
        private ModDeclare _declare;
        private GameObject _gameObject;

        public ModDeclare GetDeclaration() => _declare;

        public GameObject GetGameObject() => _gameObject;

        public string GetUrl() => _declare?.RepoUrl ?? string.Empty;

        // Keeps what NML hands over, then patches the save and the load once for the whole session.
        public void OnLoad(ModDeclare pModDecl, GameObject pGameObject)
        {
            _declare = pModDecl;
            _gameObject = pGameObject;
            Harmony.CreateAndPatchAll(typeof(SavePatches), pModDecl.UID);
            LogService.LogInfo($"[{pModDecl.Name}]: a save now keeps statuses, long waits and the world's clocks");
        }
    }
}
