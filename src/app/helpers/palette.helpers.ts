import { KINGDOM_REGISTRY, REALM_FALLBACK_HUE } from '../constants';

// A realm's colours, read from the chapter registry — the layer between chapter data and everything drawn in a crown's hues, tags and sprites alike.
export class PaletteHelpers {

  // A realm's `getColorText` hue — its `[k]` name, its subjects' tags and their cloth, resolved here so the three never drift; the crownless wear undyed grey.
  public static realmHue = (kingdom: number | undefined): string => (kingdom === undefined ? null : KINGDOM_REGISTRY[String(kingdom)]?.color) ?? REALM_FALLBACK_HUE;

}
