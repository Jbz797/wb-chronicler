# WorldBox mods

Two mods for WorldBox, both run by [NeoModLoader](https://steamcommunity.com/sharedfiles/filedetails/?id=3080294469) (NML):

- [Wandering Clouds](WanderingClouds/README.md): clouds rise anywhere in the sky and drift either way, so the seeds of life fall all over the world.
- [Faithful Saves](FaithfulSaves/README.md): a save keeps what every creature was in the middle of, stamps when it settled in its town and joined its army, and closes each year of history in January.

The chronicle this repository builds needs both: `tools/chapter/new.py` refuses a save that either did not write.

## 1. Install NeoModLoader (once)

1. In WorldBox, turn on **Experimental Mode** in the settings. NML only loads with it on.
2. Subscribe to [NeoModLoader](https://steamcommunity.com/sharedfiles/filedetails/?id=3080294469) on the Steam Workshop, and wait for the download.
3. Copy `NeoModLoader.dll` and `NeoModLoader.pdb` from the Workshop folder into the game's own mods folder:
   - **Windows**: from `<Steam>\steamapps\workshop\content\1206560\3080294469\` to `<Steam>\steamapps\common\worldbox\worldbox_Data\StreamingAssets\Mods\`
   - **macOS**: from `~/Library/Application Support/Steam/steamapps/workshop/content/1206560/3080294469/` to `worldbox.app/Contents/Resources/Data/StreamingAssets/mods/` (right-click `worldbox.app` › _Show Package Contents_)
   - **Linux / Steam Deck**: see the NML Workshop page.
4. Launch WorldBox once: NML adds its _Mods_ window, and creates a `Mods` folder next to the game.

Subscribing alone isn't enough the first time; afterwards, the subscription keeps NML up to date.

## 2. Install a mod

1. From the root of this repository, link the mod's folder into NML's `Mods` folder, under the same name, so a `git pull` updates it. For Faithful Saves, replace `WanderingClouds` with `FaithfulSaves`:
   - **macOS**: `ln -s "$PWD/mods/WanderingClouds" ~/"Library/Application Support/Steam/steamapps/common/worldbox/Mods/WanderingClouds"`
   - **Linux**: the same command, with your own Steam path (often `~/.steam/steam/steamapps/common/worldbox/Mods/WanderingClouds`)
   - **Windows** (a terminal run as administrator): `mklink /D "<Steam>\steamapps\common\worldbox\Mods\WanderingClouds" "%CD%\mods\WanderingClouds"`

   Without a clone, copy the folder's files there instead (`mod.json`, `icon.png` and the `.cs` files), with `mod.json` directly in `Mods/<name>/`.

2. Launch WorldBox. NML compiles each mod as the game starts: it shows up in the _Mods_ window, and the game log names it with what it now does.

**To uninstall**, disable the mod in NML's _Mods_ window, or delete its link (or its folder) from `Mods`. A save made with a mod loads fine without it: vanilla ignores the keys it wrote.

## For modders

Each `.csproj` is for the IDE alone: NML compiles the `.cs` files itself. To check a change without the game, compile with Mono's `csc` (C# 9 at most), referencing the game's `Managed/` assemblies (`Assembly-CSharp`, `UnityEngine`, `UnityEngine.CoreModule`, `netstandard`, `mscorlib`, `System`, `System.Core`), `NeoModLoader.dll` and NML's `0Harmony.dll`. Harmony itself can't patch under an arm64 Mono: the patches are only proven in the game.
