import { ClanInfo } from '../../interfaces';

import { SpriteHelpers } from './sprite.helpers';

// A clan's heraldry: tinted field with its emblem over it, indexed by the two ids — the wreath dropped on a tag, whose nameplate carries one, kept elsewhere.
export class ClanSpriteHelpers {

  private static readonly _banners = new Map<string, Promise<HTMLCanvasElement | null>>();
  // Where the field sits on that canvas — the same box on all 17, so cropping the composite to it yields the shield alone, emblem included.
  private static readonly _field = { height: 21, width: 18, x: 4, y: 13 };

  public static paint = async (canvas: HTMLCanvasElement, clan: ClanInfo): Promise<void> => SpriteHelpers.blit(canvas, await this._compose(clan, false));

  public static paintAll(root: ParentNode, clans: Record<string, ClanInfo | undefined>): void {
    SpriteHelpers.paintAll(root, 'clan', clans, (canvas, clan) => this.paint(canvas, clan));
  }

  // WB's own banner, wreath and rose included (`clans/clan_frame`, untinted over both) — for where no nameplate stands in for it.
  public static paintWreathed = async (canvas: HTMLCanvasElement, clan: ClanInfo): Promise<void> => SpriteHelpers.blit(canvas, await this._compose(clan, true));

  // All sheets share one 26×40 canvas with a centred pivot and align by it alone; the emblems are hand-placed, (6,16) to (9,21), so no centring can stand in.
  private static async _build(clan: ClanInfo, hasWreath: boolean): Promise<HTMLCanvasElement | null> {
    const pad = (slot = 0): string => String(slot).padStart(2, '0');
    const [field, emblem, wreath] = await Promise.all([
      SpriteHelpers.load(`assets/img/clans/clan_background_${pad(clan.banner_bg)}.png`),
      SpriteHelpers.load(`assets/img/clans/clan_icon_${pad(clan.banner_icon)}.png`),
      hasWreath ? SpriteHelpers.load('assets/img/clans/clan_frame.png') : null,
    ]);
    const box = wreath ? { height: wreath.naturalHeight, width: wreath.naturalWidth, x: 0, y: 0 } : this._field; // the whole canvas, or the shield alone
    const cut = document.createElement('canvas');
    cut.height = box.height;
    cut.width = box.width;
    const context = cut.getContext('2d');
    const tinted = this._tinted(field, clan.banner_bg_color);
    if (!context || !tinted) return null;

    context.drawImage(tinted, -box.x, -box.y);
    const badge = this._tinted(emblem, clan.banner_icon_color);
    if (badge) context.drawImage(badge, -box.x, -box.y);
    if (wreath) context.drawImage(wreath, 0, 0); // last and untinted, the rose laid over the shield's brow as WB lays it
    return cut;
  }

  // Keyed on the heraldry alone — every clan sharing both slots and both hues wears the same badge, with its wreath or without.
  private static async _compose(clan: ClanInfo, hasWreath: boolean): Promise<HTMLCanvasElement | null> {
    if (clan.banner_bg === undefined || clan.banner_icon === undefined) return null;
    const key = [clan.banner_bg, clan.banner_bg_color, clan.banner_icon, clan.banner_icon_color, hasWreath].join(',');
    return SpriteHelpers.compose(this._banners, key, () => this._build(clan, hasWreath));
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
