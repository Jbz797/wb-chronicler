import { AllianceInfo } from '../../interfaces';

import { SpriteHelpers } from './sprite.helpers';

// A pact's emblem, WB `AllianceBanner.setupBanner`: field `color_main_2`, sign `color_banner`, untinted frame over both — off the pact's own sheets, not a species'.
export class AllianceSpriteHelpers {

  private static readonly _emblems = new Map<string, Promise<HTMLCanvasElement | null>>();

  public static paint = async (canvas: HTMLCanvasElement, alliance: AllianceInfo): Promise<void> => SpriteHelpers.blit(canvas, await this._compose(alliance));

  public static paintAll(root: ParentNode, alliances: Record<string, AllianceInfo | undefined>): void {
    SpriteHelpers.paintAll(root, 'alliance', alliances, (canvas, alliance) => this.paint(canvas, alliance));
  }

  // The three layers ship pre-cropped to one common 26×40 box, so they stack at the origin — cropping each to its own ink would have pulled them apart.
  private static async _build(alliance: AllianceInfo): Promise<HTMLCanvasElement | null> {
    // `Alliance.isNormalType` reads `alliance_type`: the plain frame for a normal pact, the golden one for any other. The registry flags the latter.
    const [field, sign, frame] = await Promise.all([
      SpriteHelpers.load(`assets/img/alliances/background_${String(alliance.banner_bg ?? 0).padStart(2, '0')}.png`),
      SpriteHelpers.load(`assets/img/alliances/icon_${String(alliance.banner_icon ?? 0).padStart(2, '0')}.png`),
      SpriteHelpers.load(`assets/img/alliances/frame${alliance.banner_unity ? '_unity' : ''}.png`),
    ]);
    const cut = document.createElement('canvas');
    cut.height = field.naturalHeight;
    cut.width = field.naturalWidth;
    const context = cut.getContext('2d');
    if (!context) return null;

    // The frame comes last and untinted: WB ships it in its own metal and stands the shield inside it, so the pact's hue never washes over the border.
    for (const [sprite, hue] of [[field, alliance.banner_bg_color], [sign, alliance.banner_icon_color], [frame, undefined]] as const) {
      const tinted = this._tinted(sprite, hue);
      if (tinted) context.drawImage(tinted, 0, 0);
    }
    return cut;
  }

  // Keyed on the emblem alone — every pact sharing both slots, both hues and the same frame wears the same banner.
  private static async _compose(alliance: AllianceInfo): Promise<HTMLCanvasElement | null> {
    const key = [alliance.banner_bg, alliance.banner_bg_color, alliance.banner_icon, alliance.banner_icon_color, alliance.banner_unity].join(',');
    return SpriteHelpers.compose(this._emblems, key, () => this._build(alliance));
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
