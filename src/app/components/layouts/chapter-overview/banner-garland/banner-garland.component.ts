import { afterRenderEffect, Component, computed, DestroyRef, ElementRef, inject, signal, viewChildren } from '@angular/core';

import {
  AllianceSpriteHelpers, ClanSpriteHelpers, CultureSpriteHelpers, KingdomSpriteHelpers, LanguageSpriteHelpers, ReligionSpriteHelpers,
} from '../../../../helpers';
import { ChroniclerService, RegistryService } from '../../../../services';

// Every banner the favourite stands under, hung from one sagging cord in the collapse's order — shown only while every panel is folded.
@Component({
  selector: 'app-banner-garland',
  templateUrl: './banner-garland.component.html',
  styleUrl: './banner-garland.component.scss',
})
export class BannerGarlandComponent {

  private readonly _chronicler = inject(ChroniclerService);
  private readonly _destroyRef = inject(DestroyRef);
  private readonly _element = inject(ElementRef<HTMLElement>);
  private readonly _registry = inject(RegistryService);

  // Each tier that wears a banner, its painter and its registry — the collapse's order, crown and pact last as they stand there.
  private readonly _tiers = [
    { paint: ClanSpriteHelpers.paintWreathed, registry: this._registry.clans, tier: 'clan' },
    { paint: CultureSpriteHelpers.paint, registry: this._registry.cultures, tier: 'culture' },
    { paint: LanguageSpriteHelpers.paint, registry: this._registry.languages, tier: 'language' },
    { paint: ReligionSpriteHelpers.paint, registry: this._registry.religions, tier: 'religion' },
    { paint: KingdomSpriteHelpers.paint, registry: this._registry.kingdoms, tier: 'kingdom' },
    { paint: AllianceSpriteHelpers.paint, registry: this._registry.alliances, tier: 'alliance' },
  ] as const;

  // The banners this chapter gives the favourite: a tier it belongs to, registered — each with the painter that composes it.
  protected readonly banners = computed(() => {
    const meta = this._chronicler.currentChapter()?.meta;
    return this._tiers.flatMap(({ paint, registry, tier }) => {
      const id = meta?.[tier]?.metadata.id;
      const info = id === undefined ? undefined : registry()[String(id)];
      return info ? [{ paint: (canvas: HTMLCanvasElement): Promise<void> => paint(canvas, info), tier }] : [];
    });
  });

  private readonly _inset = 16; // the overview's padding, which the cord runs over while the banners keep inside it
  private readonly _painted = signal(0); // the tallest banner as painted, in native px — what the garland is centred on, the common box until then
  private readonly _room = signal<{ height: number; width: number } | null>(null); // the box the folded collapse leaves, read again as the window resizes
  private readonly _tallest = 40; // the alliance and clan sheets' common box — every other banner fits inside it
  private readonly _threaded = 2; // native px of a banner's brow above the cord, which runs behind it as if threaded through
  private readonly _widest = 26;
  // The cord nailed to both edges and dipping at its middle, the whole garland centred in the room; each banner in an even slot, hung where the cord passes over it.
  protected readonly layout = computed(() => {
    const room = this._room();
    const count = this.banners().length;
    if (!room || !count) return null;
    const inner = room.width - 2 * this._inset;
    const sag = Math.min(24, room.height / 8); // the cord's dip at its middle
    const scale = Math.max(1, Math.floor(Math.min((inner / count - 4) / this._widest, (room.height - sag) / this._tallest)));
    const anchor = Math.max(0, (room.height - sag - (this._painted() || this._tallest) * scale) / 2); // where the cord is nailed: sag and tallest banner centred
    const width = inner / count;
    return {
      cord: `M 0 ${anchor} Q ${room.width / 2} ${anchor + 2 * sag} ${room.width} ${anchor}`,
      scale,
      slots: this.banners().map((_, index) => {
        const centre = this._inset + width * (index + 0.5);
        const share = centre / room.width; // the quadratic the cord's path draws, read where the slot's centre sits
        const slope = (4 * sag * (1 - 2 * share)) / room.width; // and its tangent there, which the banner's brow follows
        const top = anchor + 4 * sag * share * (1 - share) - this._threaded * scale;
        return { left: centre - width / 2, tilt: `${(Math.atan(slope) * 180) / Math.PI}deg`, top, width };
      }),
    };
  });

  private readonly _blank = new WeakMap<object, number>(); // each banner's blank rows, read off its pixels once rather than at every resize
  private readonly _canvases = viewChildren<ElementRef<HTMLCanvasElement>>('banner');

  constructor() {
    const observer = new ResizeObserver(([entry]) => this._room.set(entry ? { height: entry.contentRect.height, width: entry.contentRect.width } : null));
    observer.observe(this._element.nativeElement);
    this._destroyRef.onDestroy(() => observer.disconnect());

    // Painted at native size, then shown at the layout's scale — read off the canvas once painted, each sheet keeping its own box.
    afterRenderEffect(() => {
      const [banners, canvases, layout] = [this.banners(), this._canvases(), this.layout()];
      if (!layout) return;
      Promise.all(canvases.map(async ({ nativeElement: canvas }, index) => {
        const banner = banners[index];
        if (!banner) return 0;
        await banner.paint(canvas);
        const blank = this._blank.get(banner) ?? this._blankRows(canvas); // a sheet's box can start above its ink, which would hang the banner clear of the cord
        this._blank.set(banner, blank);
        canvas.style.height = `${canvas.height * layout.scale}px`;
        canvas.style.marginTop = `${-blank * layout.scale}px`;
        canvas.style.width = `${canvas.width * layout.scale}px`;
        return canvas.height - blank;
      })).then(heights => this._painted.set(Math.max(1, ...heights))).catch(() => {});
    });
  }

  // The rows above a painted banner's ink down its middle, where the cord meets it — a scroll's rod ends stand higher than its centre.
  private _blankRows(canvas: HTMLCanvasElement): number {
    const middle = Math.floor(canvas.width / 2);
    const column = canvas.getContext('2d')?.getImageData(middle - 1, 0, 2, canvas.height).data;
    if (!column) return 0;
    const first = column.findIndex((value, index) => index % 4 === 3 && value > 0);
    return first === -1 ? 0 : Math.floor(first / 8);
  }

}
