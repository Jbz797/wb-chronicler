import { KINGDOM_REGISTRY, REALM_FALLBACK_HUE } from '../constants';

import { SpriteHelpers } from './sprites/sprite.helpers';

// A realm's colours, read from the chapter registry — the layer between chapter data and everything drawn in a crown's hues, tags and sprites alike.
export class PaletteHelpers {

  private static readonly _liftCache = new Map<string, string>();
  private static readonly _liftSteps = 100; // finer than a byte of channel, so the first step to clear the target is already the least altered colour
  private static readonly _ringTarget = 3.5; // WCAG 1.4.11 asks 3.0 of a non-text border; the ring reads as a half-pixel band, so it carries some margin
  private static readonly _textTarget = 6; // above the 4.5 AA floor for 12.5px text, short of the 7 of AAA — enough to lift the three dimmest realms, no more

  // Ink for a tag carrying its own fill (the lineages): `_contrast` measures against black, so above √21 ≈ 4.58 the fill is nearer white — dark ink then wins.
  public static readableOn = (fill: string | undefined): string => fill && this._contrast(SpriteHelpers.hexRgb(fill)) > 4.58 ? '#141414' : '#F5F2EA';

  // A realm's `getColorText` hue, verbatim — WB's own value, and the root both `realmRamp` and `realmText` build on. The crownless wear undyed grey.
  public static realmHue = (kingdom: number | undefined): string => (kingdom === undefined ? null : KINGDOM_REGISTRY[String(kingdom)]?.color) ?? REALM_FALLBACK_HUE;

  // WB tints a sprite from two ramps: `realmHue` feeds the magenta one, this feeds the teal. `undefined` leaves the teal placeholders untouched, as WB does.
  public static realmMain = (kingdom: number | undefined): string | undefined => kingdom === undefined ? undefined : KINGDOM_REGISTRY[String(kingdom)]?.color_main;

  // A realm's banner-emblem tint, ringing the tags of its subjects — cities carry their own copy, so a razed one keeps it once its crown is gone.
  public static realmRing(kingdom: number | undefined): string | undefined {
    const raw = kingdom === undefined ? undefined : KINGDOM_REGISTRY[String(kingdom)]?.banner_icon_color;
    return raw && this._lift(raw, this._ringTarget);
  }

  // The name hue as a tag wears it: `realmHue` lifted clear of the black plate. Sprites keep the raw one — only type on that plate needs the help.
  public static realmText = (kingdom: number | undefined): string => this._lift(this.realmHue(kingdom), this._textTarget);

  // WCAG relative luminance, read as a ratio against the plate — that plate being pure black, the whole formula collapses to `20 * L + 1`.
  private static _contrast(rgb: readonly number[]): number {
    const channel = (byte: number): number => {
      const value = byte / 255;
      return value <= 0.03928 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4;
    };
    return 20 * (0.2126 * channel(rgb[0] ?? 0) + 0.7152 * channel(rgb[1] ?? 0) + 0.0722 * channel(rgb[2] ?? 0)) + 1;
  }

  // Kept out of the registry so sprites keep the game's own tints: scaling all channels alike raises HSV value, hue held, then a topped-out one fades to white.
  private static _lift(hex: string, target: number): string {
    const key = `${hex}:${target}`;
    const cached = this._liftCache.get(key);
    if (cached) return cached;
    const base = SpriteHelpers.hexRgb(hex);
    const peak = base.map(byte => Math.round((byte * 255) / Math.max(...base, 1))); // value maxed out, hue and saturation intact
    const found = this._contrast(base) >= target ? base : this._walk(base, peak, target) ?? this._walk(peak, [255, 255, 255], target) ?? [255, 255, 255];
    const lifted = `#${found.map(byte => byte.toString(16).padStart(2, '0')).join('').toUpperCase()}`;
    this._liftCache.set(key, lifted);
    return lifted;
  }

  // First point of the `from`→`to` segment to clear the target; contrast climbs monotonically along it, so that point is also the least altered one.
  private static _walk(from: readonly number[], to: readonly number[], target: number): [number, number, number] | undefined {
    for (let step = 1; step <= this._liftSteps; step++) {
      const candidate = SpriteHelpers.blend(to, from, step / this._liftSteps);
      if (this._contrast(candidate) >= target) return candidate;
    }
    return undefined;
  }

}
