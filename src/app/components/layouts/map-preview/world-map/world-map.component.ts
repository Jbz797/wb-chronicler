import { DecimalPipe } from '@angular/common';
import { httpResource } from '@angular/common/http';
import { afterRenderEffect, Component, computed, ElementRef, inject, input, signal, viewChild, viewChildren } from '@angular/core';

import { NzTagModule } from 'ng-zorro-antd/tag';
import { NzTooltipModule } from 'ng-zorro-antd/tooltip';

import { PLACES_FILE, SPECIES_COLORS } from '../../../../constants';
import { LabelBox, MapPin, PlaceArea, Places, TileExtent, TilePoint } from '../../../../interfaces';
import { ChroniclerService, RegistryService } from '../../../../services';

@Component({
  selector: 'app-world-map',
  imports: [DecimalPipe, NzTagModule, NzTooltipModule],
  templateUrl: './world-map.component.html',
  styleUrl: './world-map.component.scss',
})
export class WorldMapComponent {

  private readonly _chronicler = inject(ChroniclerService);
  private readonly _registry = inject(RegistryService);

  public readonly previewUrl = input.required<string>();

  private readonly _extent = signal<TileExtent | null>(null);

  // A tile's centre in percent of the picture, the save counting `y` northward where the rows run south — `map/show.py`'s one conversion.
  private readonly _at = (tile: TilePoint, extent: TileExtent): Pick<MapPin, 'left' | 'top'> => ({
    left: ((tile.x + 0.5) / extent.width) * 100,
    top: ((extent.height - tile.y - 0.5) / extent.height) * 100,
  });

  // Where the favourite stood as the chapter was written, sited as every pin is and dyed as its species' tag in the prose — none before a favourite is chosen.
  protected readonly favorite = computed(() => {
    const extent = this._extent();
    const metadata = this._chronicler.currentChapter()?.meta.favorite?.metadata;
    if (!extent || !metadata) return null;
    const color = SPECIES_COLORS[this._registry.persons()[String(metadata.id)]?.asset_id ?? ''];
    return { ...this._at({ x: metadata.x, y: metadata.y }, extent), color, name: metadata.name };
  });
  // The picture's own box, as wide as the screen allows at its ratio — the pins sit in percent of it, so they hold wherever it lands.
  protected readonly frame = computed(() => {
    const extent = this._extent();
    return extent && { ratio: `${extent.width} / ${extent.height}`, width: `min(100vw, ${(100 * extent.width) / extent.height}vh)` };
  });
  // How far each name steps off its point so that none sits on another, in `cqw` — measured once the names are drawn, their size set by their font.
  protected readonly nudges = signal<Record<string, { dx: number; dy: number }>>({});
  // Read at each opening, the chronicler baptising between two chapters: what the picture shows is the gazetteer as it stands.
  protected readonly places = httpResource<Places>(() => PLACES_FILE);

  // A name grows with the root of its extent — the width a land spans, not its area —, from the smallest named land or water to the largest, in `cqw`.
  private readonly _sizer = (sizes: number[]): (size: number) => number => {
    const [low, high] = [0.7, 0.7 * 3];
    const roots = sizes.map(size => Math.sqrt(size));
    const [least, most] = [Math.min(...roots), Math.max(...roots)];
    return size => most === least ? high : low + ((Math.sqrt(size) - least) / (most - least)) * (high - low);
  };

  // The gazetteer's named entries alone, each as a chapter up to the one read has named it — a later baptism is not yet known here.
  protected readonly pins = computed((): MapPin[] => {
    const extent = this._extent();
    const places = this.places.hasValue() ? this.places.value() : undefined;
    if (!extent || !places) return [];
    const chapter = Number(this._chronicler.currentChapter()?.slug.slice(1) ?? 0);
    const isKnown = (given: string): boolean => given !== '' && Number(given.slice(1)) <= chapter;
    const named = (book: Record<string, PlaceArea>): [string, PlaceArea][] => Object.entries(book).filter(([, entry]) => isKnown(entry.chapter));
    const [islands, lakes] = [named(places.islands), named(places.lakes)];
    const fontSize = this._sizer([...islands, ...lakes].map(([, entry]) => entry.size)); // lands and waters on one scale: a lake never outgrows a wider land
    const areas = (kind: 'island' | 'lake', entries: [string, PlaceArea][]): MapPin[] => entries.map(([id, entry]) => ({
      ...this._at(entry.centroid, extent), area: entry.size * this._tileKm2, fontSize: fontSize(entry.size), key: `${kind}-${id}`, kind, name: entry.name,
    }));

    return [
      ...areas('island', islands),
      ...areas('lake', lakes),
      ...Object.entries(places.places)
        .filter(([, spot]) => isKnown(spot.chapter))
        .map(([name, spot]): MapPin => ({
          ...this._at(spot.centroid, extent), emoji: spot.emoji, key: `spot-${name}`, kind: 'spot', name, spotKind: spot.kind,
        })),
    ];
  });

  private readonly _favoriteTag = viewChild<unknown, ElementRef<HTMLElement>>('favoriteTag', { read: ElementRef });
  private readonly _gap = 0.3; // the room left between two names, in `cqw`
  private readonly _resized = signal(0);
  private readonly _stage = viewChild<ElementRef<HTMLElement>>('stage');
  private readonly _tags = viewChildren<unknown, ElementRef<HTMLElement>>('pinTag', { read: ElementRef });
  private readonly _tileKm2 = 0.01; // the chronicler's scale, a tile 100 m a side — `chronicler.md` § Échelle

  constructor() {
    // A name's box settles only once its font is in, and a display face lands after the first draw: each resize of a name asks for the placing again.
    afterRenderEffect((onCleanup) => {
      const observer = new ResizeObserver(() => this._resized.update(count => count + 1));
      for (const tag of this._tags()) observer.observe(tag.nativeElement);
      onCleanup(() => observer.disconnect());
    });

    afterRenderEffect(() => {
      this._resized();
      const [frame, extent, pins, tags] = [this._stage()?.nativeElement, this._extent(), this.pins(), this._tags()];
      if (!frame || !extent || tags.length !== pins.length) return;
      const box = frame.getBoundingClientRect();
      const unit = box.width / 100; // one `cqw`, in pixels
      const ratio = extent.height / extent.width;
      const boxes: LabelBox[] = pins.map((pin, index) => {
        const { height = 0, width = 0 } = tags[index]?.nativeElement.getBoundingClientRect() ?? {};
        return { fixed: pin.kind === 'island', h: height / unit, key: pin.key, w: width / unit, x: pin.left, y: pin.top * ratio };
      });
      const favorite = this._favoriteTag()?.nativeElement.getBoundingClientRect();
      if (favorite) {
        const [x, y] = [(favorite.left + favorite.width / 2 - box.left) / unit, (favorite.top + favorite.height / 2 - box.top) / unit];
        boxes.push({ fixed: true, h: favorite.height / unit, key: 'favorite', w: favorite.width / unit, x, y });
      }
      this.nudges.set(this._placeLabels(boxes));
    });
  }

  protected readonly measure = (event: Event): void => {
    const picture = event.target as HTMLImageElement;
    this._extent.set({ height: picture.naturalHeight, width: picture.naturalWidth });
  };

  protected readonly nudge = (key: string): string | null => {
    const step = this.nudges()[key];
    return step ? `${step.dx}cqw ${step.dy}cqw` : null;
  };

  // The steps that take a name clear of each name it touches on its point — just above, below, left or right of that one —, the shortest first.
  private readonly _clearings = (box: LabelBox, placed: LabelBox[]): [number, number][] => placed
    .filter(other => this._overlaps(box, other))
    .flatMap((other): [number, number][] => {
      const [up, down] = [other.y - (other.h + box.h) / 2 - this._gap - box.y, other.y + (other.h + box.h) / 2 + this._gap - box.y];
      const [left, right] = [other.x - (other.w + box.w) / 2 - this._gap - box.x, other.x + (other.w + box.w) / 2 + this._gap - box.x];
      return [[0, up], [0, down], [left, 0], [right, 0]];
    })
    .toSorted((a, b) => Math.hypot(...a) - Math.hypot(...b));

  private readonly _overlaps = (a: LabelBox, b: LabelBox): boolean => Math.abs(a.x - b.x) < (a.w + b.w) / 2 && Math.abs(a.y - b.y) < (a.h + b.h) / 2;

  // Greedy, as a printed map is lettered: fixed names first (lands, largest first), then each other on its point or the nearest clear spot, else back on it.
  private _placeLabels(boxes: LabelBox[]): Record<string, { dx: number; dy: number }> {
    const placed: LabelBox[] = [];
    const nudges: Record<string, { dx: number; dy: number }> = {};
    const order = [...boxes.filter(box => box.fixed).toSorted((a, b) => b.h - a.h), ...boxes.filter(box => !box.fixed)];
    for (const box of order) {
      const isFree = ([dx, dy]: [number, number]): boolean => placed.every(other => !this._overlaps({ ...box, x: box.x + dx, y: box.y + dy }, other));
      const tries: [number, number][] = box.fixed ? [[0, 0]] : [[0, 0], ...this._clearings(box, placed)];
      const [dx, dy] = tries.find(step => isFree(step)) ?? [0, 0];
      placed.push({ ...box, x: box.x + dx, y: box.y + dy });
      if (dx || dy) nudges[box.key] = { dx, dy };
    }
    return nudges;
  }

}
