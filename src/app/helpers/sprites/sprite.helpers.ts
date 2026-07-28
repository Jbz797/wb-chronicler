// Canvas plumbing every WorldBox sprite shares — image cache, compose cache, the two recolouring passes, and the DOM sweep. Actors, crowns and banners ride on it.
export class SpriteHelpers {

  private static readonly _dark: readonly [number, number, number] = [30, 30, 30]; // WB `ColorAsset.initColor` Lerp target
  private static readonly _images = new Map<string, Promise<HTMLImageElement>>();
  // WB's sixth placeholder, `color_light` → black, is left alone: it lands on a crown's 1-2 highlights, which WB blacks out only to paint the glow back over.
  private static readonly _magentaRamp = ['255,0,255', '222,0,222', '167,0,167', '127,0,127', '88,0,88']; // WB `color_magenta_0..4` → `k_color_0..4`
  private static readonly _shadeTs = [0, 0.13, 0.35, 0.51, 0.66]; // Lerp factors of the five realm steps towards `_dark`

  // WB `Toolbox.blendColor`: `a * t + b * (1 - t)`, so `t = 1` yields `a`. Truncated, as Unity casts a `Color` to `Color32` — rounding drifts a shade off WB's own.
  public static blend(a: readonly number[], b: readonly number[], t: number): [number, number, number] {
    const at = (index: number): number => Math.floor((a[index] ?? 0) * t + (b[index] ?? 0) * (1 - t));
    return [at(0), at(1), at(2)];
  }

  // Sizes the target to the sprite (×`scale`) and stamps it, smoothing off so the art stays crisp. A `null` sprite collapses the canvas instead of leaving 300×150.
  public static blit(canvas: HTMLCanvasElement, sprite: HTMLCanvasElement | null, scale = 1): void {
    const context = canvas.getContext('2d');
    if (!sprite || !context) {
      canvas.height = 0;
      canvas.width = 0;
      return;
    }

    canvas.height = sprite.height * scale; // resizing resets the context, so smoothing goes off after it, not before
    canvas.width = sprite.width * scale;
    context.imageSmoothingEnabled = false;
    context.drawImage(sprite, 0, 0, sprite.width, sprite.height, 0, 0, canvas.width, canvas.height);
  }

  // Memoises a composed sprite under `key` — entities sharing one visual identity compose once between them, however many tags echo them.
  public static async compose(
    store: Map<string, Promise<HTMLCanvasElement | null>>,
    key: string,
    build: () => Promise<HTMLCanvasElement | null>,
  ): Promise<HTMLCanvasElement | null> {
    const cached = store.get(key);
    if (cached) return cached;
    const pending = build();
    store.set(key, pending);
    return pending;
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

  // Fills every `<canvas data-<kind>>` a renderer left in the prose. An id absent from the registry stays collapsed rather than showing a blank box.
  public static paintAll<T>(
    root: ParentNode,
    kind: string,
    registry: Record<string, T | undefined>,
    paint: (canvas: HTMLCanvasElement, entry: T) => Promise<void>,
  ): void {
    for (const canvas of root.querySelectorAll<HTMLCanvasElement>(`canvas[data-${CSS.escape(kind)}]`)) {
      const entry = registry[canvas.dataset[kind] ?? ''];
      if (entry) paint(canvas, entry).catch(() => {}); // a missing sheet or sprite set just leaves the canvas collapsed
    }
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

  // WB dyes a banner part by multiplying each channel by the hue — PIL's `point` LUT, integer-floored the same way so the canvas matches the sprites byte for byte.
  public static tint(context: CanvasRenderingContext2D, width: number, height: number, hex: string | undefined): void {
    if (!hex) return;
    const [r, g, b] = this.hexRgb(hex);
    const data = context.getImageData(0, 0, width, height);
    const px = data.data;
    for (let index = 0; index < px.length; index += 4) { // unrolled: a `[0, 1, 2]` loop would allocate that array once per pixel
      px[index] = Math.floor(((px[index] ?? 0) * r) / 255);
      px[index + 1] = Math.floor(((px[index + 1] ?? 0) * g) / 255);
      px[index + 2] = Math.floor(((px[index + 2] ?? 0) * b) / 255);
    }
    context.putImageData(data, 0, 0);
  }

}
