import { KingdomInfo } from '../../interfaces';

import { SpriteHelpers } from './sprite.helpers';

// Composes a realm's banner — species shield, then emblem — over the plumbing in `SpriteHelpers`. Feeds every `[k]` plate, panel and prose alike.
export class KingdomSpriteHelpers {

  private static readonly _banners = new Map<string, Promise<HTMLCanvasElement | null>>();

  // Native size: a shield stands taller than the 22px cap `.banner` sets, so the CSS scales it down and no upscale is wanted here.
  public static paint = async (canvas: HTMLCanvasElement, kingdom: KingdomInfo): Promise<void> => SpriteHelpers.blit(canvas, await this._compose(kingdom));

  public static paintAll(root: ParentNode, kingdoms: Record<string, KingdomInfo | undefined>): void {
    SpriteHelpers.paintAll(root, 'kingdom', kingdoms, (canvas, kingdom) => this.paint(canvas, kingdom));
  }

  // Shield tinted `color_main_2`, emblem tinted `color_banner` on its own canvas, then laid over it — WB `KingdomBanner.setupBanner`.
  private static async _build(kingdom: KingdomInfo): Promise<HTMLCanvasElement | null> {
    const [shield, emblem] = await Promise.all([
      SpriteHelpers.load(`assets/img/banner-backgrounds/${kingdom.banner_bg}.png`),
      SpriteHelpers.load(`assets/img/banners/${kingdom.banner_icon}.png`),
    ]);
    const tinted = this._tinted(emblem, kingdom.banner_icon_color);
    const cut = document.createElement('canvas');
    cut.height = shield.naturalHeight;
    cut.width = shield.naturalWidth;
    const context = cut.getContext('2d');
    if (!context || !tinted) return null;

    context.drawImage(shield, 0, 0);
    SpriteHelpers.tint(context, cut.width, cut.height, kingdom.banner_bg_color);

    // WB seats the emblem on the shield's *width* for both axes — on a tall shield that holds it in the upper field; the floor of 1 keeps the widest on the cloth.
    context.drawImage(tinted, Math.floor((cut.width - emblem.naturalWidth) / 2), Math.max(1, Math.floor((cut.width - emblem.naturalHeight) / 2)));
    return cut;
  }

  // Keyed on the heraldry alone — every realm sharing a species and a palette wears the same banner.
  private static async _compose(kingdom: KingdomInfo): Promise<HTMLCanvasElement | null> {
    if (kingdom.banner_bg === undefined || kingdom.banner_icon === undefined) return null;
    const key = [kingdom.banner_bg, kingdom.banner_bg_color, kingdom.banner_icon, kingdom.banner_icon_color].join(',');
    return SpriteHelpers.compose(this._banners, key, () => this._build(kingdom));
  }

  // The emblem on a canvas of its own, so its hue never reaches the shield already painted underneath.
  private static _tinted(emblem: HTMLImageElement, hue: string | undefined): HTMLCanvasElement | null {
    const cut = document.createElement('canvas');
    cut.height = emblem.naturalHeight;
    cut.width = emblem.naturalWidth;
    const context = cut.getContext('2d');
    if (!context) return null;

    context.drawImage(emblem, 0, 0);
    SpriteHelpers.tint(context, cut.width, cut.height, hue);
    return cut;
  }

}
