import { ReligionInfo } from '../../interfaces';

import { SpriteHelpers } from './sprite.helpers';

// A religion's emblem, WB `ReligionBanner.setupBanner`: the field takes `color_main_2`, the sign raised over it `color_banner`.
export class ReligionSpriteHelpers {

  private static readonly _emblems = new Map<string, Promise<HTMLCanvasElement | null>>();

  public static paint = async (canvas: HTMLCanvasElement, religion: ReligionInfo): Promise<void> => SpriteHelpers.blit(canvas, await this._compose(religion));

  public static paintAll(root: ParentNode, religions: Record<string, ReligionInfo | undefined>): void {
    SpriteHelpers.paintAll(root, 'religion', religions, (canvas, religion) => this.paint(canvas, religion));
  }

  // The three layers ship pre-cropped to one common 24×36 box, so they stack at the origin — cropping each to its own ink would have pulled them apart.
  private static async _build(religion: ReligionInfo): Promise<HTMLCanvasElement | null> {
    const [field, sign, pedestal] = await Promise.all([
      SpriteHelpers.load(`assets/img/religions/religion_background_${String(religion.banner_bg ?? 0).padStart(2, '0')}.png`),
      SpriteHelpers.load(`assets/img/religions/religion_icon_${String(religion.banner_icon ?? 0).padStart(2, '0')}.png`),
      SpriteHelpers.load('assets/img/religions/religion_frame.png'),
    ]);
    const cut = document.createElement('canvas');
    cut.height = field.naturalHeight;
    cut.width = field.naturalWidth;
    const context = cut.getContext('2d');
    if (!context) return null;

    // The pedestal comes last and untinted: WB ships it gold and stands the sign on it, so the flame rises from behind rather than washing over it.
    for (const [sprite, hue] of [[field, religion.banner_bg_color], [sign, religion.banner_icon_color], [pedestal, undefined]] as const) {
      const tinted = this._tinted(sprite, hue);
      if (tinted) context.drawImage(tinted, 0, 0);
    }
    return cut;
  }

  // Keyed on the emblem alone — every religion sharing both slots and both hues wears the same banner.
  private static async _compose(religion: ReligionInfo): Promise<HTMLCanvasElement | null> {
    const key = [religion.banner_bg, religion.banner_bg_color, religion.banner_icon, religion.banner_icon_color].join(',');
    return SpriteHelpers.compose(this._emblems, key, () => this._build(religion));
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
