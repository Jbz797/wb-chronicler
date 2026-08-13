import { SubspeciesInfo } from '../../interfaces';

import { SpriteHelpers } from './sprite.helpers';

// A biology's bookmark — WB `SubspeciesBanner.setupBanner`: two ribbons on one origin, the outer dyed `color_main_2`, the inner `color_main`. The slab is CSS.
export class SubspeciesSpriteHelpers {

  private static readonly _bookmarks = new Map<string, Promise<HTMLCanvasElement | null>>();
  private static readonly _slabs = 12; // WB `SubspeciesBannerLibrary` ships `background_00..11` and indexes them straight

  public static paint = async (canvas: HTMLCanvasElement, subspecies: SubspeciesInfo): Promise<void> => SpriteHelpers.blit(canvas, await this._compose(subspecies));

  public static paintAll(root: ParentNode, subspecies: Record<string, SubspeciesInfo | undefined>): void {
    SpriteHelpers.paintAll(root, 'subspecies', subspecies, (canvas, entry) => this.paint(canvas, entry));
  }

  // The CSS ground, given as a ready `url(…)`: the slab is 9-sliced by the stylesheet, never composed here. Out of range falls back to the first, as WB does.
  public static slab(slot: number | undefined): string {
    const index = slot !== undefined && slot >= 0 && slot < this._slabs ? slot : 0;
    return `url('assets/img/subspecies/background_${String(index).padStart(2, '0')}.png')`;
  }

  // Both sprites are 7×9 and share their origin, so the outer one sizes the canvas and the inner lands at 0,0 over it.
  private static async _build(subspecies: SubspeciesInfo): Promise<HTMLCanvasElement | null> {
    const [outer, inner] = await Promise.all([
      SpriteHelpers.load('assets/img/subspecies/bookmark_1.png'),
      SpriteHelpers.load('assets/img/subspecies/bookmark_2.png'),
    ]);
    const cut = document.createElement('canvas');
    cut.height = outer.naturalHeight;
    cut.width = outer.naturalWidth;
    const context = cut.getContext('2d');
    const dyed = this._tinted(outer, subspecies.color_main_2);
    if (!context || !dyed) return null;

    context.drawImage(dyed, 0, 0);
    const core = this._tinted(inner, subspecies.color_main);
    if (core) context.drawImage(core, 0, 0);
    return cut;
  }

  // Keyed on the two hues alone — every biology sharing a colour wears one bookmark between them, the slab underneath varying on its own.
  private static async _compose(subspecies: SubspeciesInfo): Promise<HTMLCanvasElement | null> {
    if (!subspecies.color_main && !subspecies.color_main_2) return null;
    return SpriteHelpers.compose(this._bookmarks, `${subspecies.color_main},${subspecies.color_main_2}`, () => this._build(subspecies));
  }

  // Each ribbon dyed on a canvas of its own, so the inner hue never reaches the outer already painted underneath.
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
