import { ClanInfo } from '../../interfaces';

import { SpriteHelpers } from './sprite.helpers';

// A clan's heraldry: tinted field, emblem, untinted wreath over both — from its own sheets, indexed straight by the two ids where a crown keys them by species.
export class ClanSpriteHelpers {

  private static readonly _banners = new Map<string, Promise<HTMLCanvasElement | null>>();
  // The wreath is 26×37 but the hollow it encloses spans y 14-32 — centring the field in the whole sprite would ride it 6px high and leave daylight underneath.
  private static readonly _hollow = { bottom: 32, top: 14 };

  public static paint = async (canvas: HTMLCanvasElement, clan: ClanInfo): Promise<void> => SpriteHelpers.blit(canvas, await this._compose(clan));

  public static paintAll(root: ParentNode, clans: Record<string, ClanInfo | undefined>): void {
    SpriteHelpers.paintAll(root, 'clan', clans, (canvas, clan) => this.paint(canvas, clan));
  }

  // The wreath sets the canvas: it is the tallest of the three, and the other two seat centred inside it.
  private static async _build(clan: ClanInfo): Promise<HTMLCanvasElement | null> {
    const pad = (slot: number | undefined): string => String(slot ?? 0).padStart(2, '0');
    const [field, emblem, wreath] = await Promise.all([
      SpriteHelpers.load(`assets/img/clans/clan_background_${pad(clan.banner_bg)}.png`),
      SpriteHelpers.load(`assets/img/clans/clan_icon_${pad(clan.banner_icon)}.png`),
      SpriteHelpers.load('assets/img/clans/clan_frame.png'),
    ]);
    const cut = document.createElement('canvas');
    cut.height = wreath.naturalHeight;
    cut.width = wreath.naturalWidth;
    const context = cut.getContext('2d');
    const tinted = this._tinted(field, clan.banner_bg_color);
    if (!context || !tinted) return null;

    const middle = (this._hollow.top + this._hollow.bottom) / 2;
    context.drawImage(tinted, Math.floor((cut.width - field.naturalWidth) / 2), this._hollow.top);
    const badge = this._tinted(emblem, clan.banner_icon_color);
    if (badge) context.drawImage(badge, Math.floor((cut.width - emblem.naturalWidth) / 2), Math.round(middle - emblem.naturalHeight / 2));
    context.drawImage(wreath, 0, 0);
    return cut;
  }

  // Keyed on the heraldry alone — every clan sharing both slots and both hues wears the same badge.
  private static async _compose(clan: ClanInfo): Promise<HTMLCanvasElement | null> {
    if (clan.banner_bg === undefined || clan.banner_icon === undefined) return null;
    const key = [clan.banner_bg, clan.banner_bg_color, clan.banner_icon, clan.banner_icon_color].join(',');
    return SpriteHelpers.compose(this._banners, key, () => this._build(clan));
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
