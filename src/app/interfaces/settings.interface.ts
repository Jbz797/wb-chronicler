// A `map.wbox` sitting in a save slot — `mtime` orders them, so the slot the player wrote last comes first. `world` is absent when its `map.meta` says nothing.
export interface SaveCandidate {
  mtime: number;
  path: string;
  size: number;
  world?: string;
}

// What the reader records on disk, at `history/settings.json`: served as an asset, so any of it is one `GET` away — written only by the local service.
export interface Settings {
  lang?: string; // the tongue the chronicler writes in and the panels answer in; absent until the reader has picked one, which the panel makes him do
  savePath?: string;
}
