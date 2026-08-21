import { CultureInfo } from '../../interfaces';

import { SpriteHelpers } from './sprite.helpers';

// A culture's emblem, WB `CultureBanner.setupBanner`: the fixed field and the chosen border share `color_main_2`, the central motif takes `color_banner`.
export class CultureSpriteHelpers {

  private static readonly _emblems = new Map<string, Promise<HTMLCanvasElement | null>>();

  public static paint = async (canvas: HTMLCanvasElement, culture: CultureInfo): Promise<void> => SpriteHelpers.blit(canvas, await this._compose(culture));

  public static paintAll(root: ParentNode, cultures: Record<string, CultureInfo | undefined>): void {
    SpriteHelpers.paintAll(root, 'culture', cultures, (canvas, culture) => this.paint(canvas, culture));
  }

  // The three layers ship pre-cropped to one common 26×33 box, so they stack at the origin — cropping each to its own ink would have pulled them apart.
  private static async _build(culture: CultureInfo): Promise<HTMLCanvasElement | null> {
    const [field, border, motif] = await Promise.all([
      SpriteHelpers.load('assets/img/cultures/culture_background.png'),
      SpriteHelpers.load(`assets/img/cultures/culture_decor_${culture.banner_bg ?? 0}.png`),
      SpriteHelpers.load(`assets/img/cultures/culture_element_${culture.banner_icon ?? 0}.png`),
    ]);
    const cut = document.createElement('canvas');
    cut.height = field.naturalHeight;
    cut.width = field.naturalWidth;
    const context = cut.getContext('2d');
    if (!context) return null;

    for (const [sprite, hue] of [[field, culture.banner_bg_color], [border, culture.banner_bg_color], [motif, culture.banner_icon_color]] as const) {
      const tinted = this._tinted(sprite, hue);
      if (tinted) context.drawImage(tinted, 0, 0);
    }
    return cut;
  }

  // Keyed on the emblem alone — every culture sharing both slots and both hues wears the same banner.
  private static async _compose(culture: CultureInfo): Promise<HTMLCanvasElement | null> {
    const key = [culture.banner_bg, culture.banner_bg_color, culture.banner_icon, culture.banner_icon_color].join(',');
    return SpriteHelpers.compose(this._emblems, key, () => this._build(culture));
  }

  // Each layer tinted on a canvas of its own, so no hue reaches what is already painted underneath.
  private static _tinted(sprite: HTMLImageElement, hue: string | undefined): HTMLCanvasElement | null {
    const cut = document.createElement('canvas');
    cut.height = sprite.naturalHeight;
    cut.width = sprite.naturalWidth;
    const context = cut.getContext('2d');
    if (!context) return null;

    context.drawImage(sprite, 0, 0);
    SpriteHelpers.tint(context, cut.width, cut.height, hue);
    return cut;
  }

}
