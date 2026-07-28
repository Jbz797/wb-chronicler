import { REALM_FALLBACK_HUE } from '../../constants';
import { CityInfo } from '../../interfaces';

import { SpriteHelpers } from './sprite.helpers';

// Composes a settlement's crown — one sprite, its placeholders dyed in the realm's ramp — over `SpriteHelpers`. Feeds every `[c]` plate, panel and prose alike.
export class CitySpriteHelpers {

  private static readonly _crowns = new Map<string, Promise<HTMLCanvasElement | null>>();

  // Native size — 26×12 for a village, 26×14 for a seat, both already under the cap the tag's icons wear, so nothing is scaled.
  public static async paint(canvas: HTMLCanvasElement, city: CityInfo): Promise<void> {
    SpriteHelpers.blit(canvas, await this._compose(city));
  }

  public static paintAll(root: ParentNode, cities: Record<string, CityInfo | undefined>): void {
    SpriteHelpers.paintAll(root, 'city', cities, (canvas, city) => this.paint(canvas, city));
  }

  // WB `CityBanner.setupBanner`: gold crown for a capital, stone rampart for the rest, both wearing their realm's five shades.
  private static async _build(city: CityInfo): Promise<HTMLCanvasElement | null> {
    const sprite = await SpriteHelpers.load(`assets/img/crowns/${city.crown}.png`);
    const cut = document.createElement('canvas');
    cut.height = sprite.naturalHeight;
    cut.width = sprite.naturalWidth;
    const context = cut.getContext('2d');
    if (!context) return null;

    context.drawImage(sprite, 0, 0);
    SpriteHelpers.repaint(context, cut.width, cut.height, SpriteHelpers.realmRamp(city.crown_color ?? REALM_FALLBACK_HUE));
    return cut;
  }

  // Keyed on sprite and hue alone: every settlement of one realm — and every `[c]` tag echoing them — composes once between them.
  private static async _compose(city: CityInfo): Promise<HTMLCanvasElement | null> {
    if (!city.crown) return null;
    const key = `${city.crown},${city.crown_color ?? ''}`;
    const cached = this._crowns.get(key);
    if (cached) return cached;
    const pending = this._build(city);
    this._crowns.set(key, pending);
    return pending;
  }

}
