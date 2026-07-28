// Canvas plumbing every WorldBox sprite shares — image cache, placeholder swap, colour maths. Actors paint through it today; crowns and banners will follow.
export class SpriteHelpers {

  private static readonly _dark: readonly [number, number, number] = [30, 30, 30]; // WB `ColorAsset.initColor` Lerp target
  private static readonly _images = new Map<string, Promise<HTMLImageElement>>();
  // WB's sixth placeholder, `color_light` → black, is left alone: it lands on a crown's 1-2 highlights, which WB blacks out only to paint the glow back over.
  private static readonly _magentaRamp = ['255,0,255', '222,0,222', '167,0,167', '127,0,127', '88,0,88']; // WB `color_magenta_0..4` → `k_color_0..4`
  private static readonly _shadeTs = [0, 0.13, 0.35, 0.51, 0.66]; // Lerp factors of the five realm steps towards `_dark`

  // WB `Toolbox.blendColor`: `a * t + b * (1 - t)`, so `t = 1` yields `a`.
  public static blend(a: readonly number[], b: readonly number[], t: number): [number, number, number] {
    const at = (index: number): number => Math.round((a[index] ?? 0) * t + (b[index] ?? 0) * (1 - t));
    return [at(0), at(1), at(2)];
  }

  // `#RRGGBB` to a channel triple — the atlas and the registries both store hex, while every blend works in bytes.
  public static hexRgb(hex: string): [number, number, number] {
    return [1, 3, 5].map(index => Number.parseInt(hex.slice(index, index + 2), 16)) as [number, number, number];
  }

  // One decoded image per URL, shared across every sprite on the page.
  public static async load(url: string): Promise<HTMLImageElement> {
    const cached = this._images.get(url);
    if (cached) return cached;
    const pending = new Promise<HTMLImageElement>((resolve, reject) => {
      const img = new Image();
      img.addEventListener('load', () => resolve(img));
      img.addEventListener('error', () => reject(new Error(url)));
      img.src = url;
    });
    this._images.set(url, pending);
    return pending;
  }

  // The five magenta placeholders mapped to a realm's shade ramp — what dyes an actor's cloth and, in WB, a city's crown. Callers extend the table with their own.
  public static realmRamp(hue: string): Map<string, string> {
    const base = this.hexRgb(hue);
    return new Map(this._magentaRamp.map((placeholder, step) => [placeholder, this.blend(this._dark, base, this._shadeTs[step] ?? 0).join(',')]));
  }

  // WB `DynamicColorPixelTool.checkSpecialColors`: run once, on the assembled sprite — placeholders survive compositing, so per-part passes are wasted work.
  public static repaint(context: CanvasRenderingContext2D, width: number, height: number, swaps: Map<string, string>): void {
    const data = context.getImageData(0, 0, width, height);
    const px = data.data;
    for (let index = 0; index < px.length; index += 4) {
      const swap = px[index + 3] === 0 ? undefined : swaps.get(`${px[index]},${px[index + 1]},${px[index + 2]}`);
      if (swap) {
        const [r, g, b] = swap.split(',');
        px[index] = Number(r);
        px[index + 1] = Number(g);
        px[index + 2] = Number(b);
      }
    }
    context.putImageData(data, 0, 0);
  }

}
