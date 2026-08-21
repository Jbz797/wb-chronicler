import { LanguageInfo } from '../../interfaces';

import { SpriteHelpers } from './sprite.helpers';

// A language's emblem, WB `LanguageBanner.setupBanner`: the parchment takes `color_main_2`, the script inked over it `color_banner`.
export class LanguageSpriteHelpers {

  private static readonly _emblems = new Map<string, Promise<HTMLCanvasElement | null>>();

  public static paint = async (canvas: HTMLCanvasElement, language: LanguageInfo): Promise<void> => SpriteHelpers.blit(canvas, await this._compose(language));

  public static paintAll(root: ParentNode, languages: Record<string, LanguageInfo | undefined>): void {
    SpriteHelpers.paintAll(root, 'language', languages, (canvas, language) => this.paint(canvas, language));
  }

  // The three layers ship pre-cropped to one common 26×33 box, so they stack at the origin — cropping each to its own ink would have pulled them apart.
  private static async _build(language: LanguageInfo): Promise<HTMLCanvasElement | null> {
    const [field, script, rings] = await Promise.all([
      SpriteHelpers.load(`assets/img/languages/language_background_${String(language.banner_bg ?? 0).padStart(2, '0')}.png`),
      SpriteHelpers.load(`assets/img/languages/language_icon_${String(language.banner_icon ?? 0).padStart(2, '0')}.png`),
      SpriteHelpers.load('assets/img/languages/language_frame.png'),
    ]);
    const cut = document.createElement('canvas');
    cut.height = field.naturalHeight;
    cut.width = field.naturalWidth;
    const context = cut.getContext('2d');
    if (!context) return null;

    // The rings come last and untinted: WB ships them gold and hangs the vellum from them, so no hue of the tongue's own reaches the brass.
    for (const [sprite, hue] of [[field, language.banner_bg_color], [script, language.banner_icon_color], [rings, undefined]] as const) {
      const tinted = this._tinted(sprite, hue);
      if (tinted) context.drawImage(tinted, 0, 0);
    }
    return cut;
  }

  // Keyed on the emblem alone — every language sharing both slots and both hues wears the same banner.
  private static async _compose(language: LanguageInfo): Promise<HTMLCanvasElement | null> {
    const key = [language.banner_bg, language.banner_bg_color, language.banner_icon, language.banner_icon_color].join(',');
    return SpriteHelpers.compose(this._emblems, key, () => this._build(language));
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
