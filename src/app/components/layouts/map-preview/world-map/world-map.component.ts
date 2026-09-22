import { DecimalPipe } from '@angular/common';
import { httpResource } from '@angular/common/http';
import { Component, computed, inject, input, signal } from '@angular/core';

import { NzTooltipModule } from 'ng-zorro-antd/tooltip';

import { TranslatePipe } from '@ngx-translate/core';

import { PLACES_FILE } from '../../../../constants';
import { MapPin, PlaceArea, Places, TileExtent, TilePoint } from '../../../../interfaces';
import { ChroniclerService } from '../../../../services';

@Component({
  selector: 'app-world-map',
  imports: [DecimalPipe, NzTooltipModule, TranslatePipe],
  templateUrl: './world-map.component.html',
  styleUrl: './world-map.component.scss',
})
export class WorldMapComponent {

  private readonly _chronicler = inject(ChroniclerService);

  public readonly previewUrl = input.required<string>();

  private readonly _extent = signal<TileExtent | null>(null);

  // A tile's centre in percent of the picture, the save counting `y` northward where the rows run south — `map/show.py`'s one conversion.
  private readonly _at = (tile: TilePoint, extent: TileExtent): Pick<MapPin, 'left' | 'top'> => ({
    left: ((tile.x + 0.5) / extent.width) * 100,
    top: ((extent.height - tile.y - 0.5) / extent.height) * 100,
  });

  // Where the favourite stood as the chapter was written, sited as every pin is — none before a favourite is chosen.
  protected readonly favorite = computed(() => {
    const extent = this._extent();
    const metadata = this._chronicler.currentChapter()?.meta.favorite?.metadata;
    return extent && metadata && { ...this._at({ x: metadata.x, y: metadata.y }, extent), name: metadata.name };
  });
  // The picture's own box, as wide as the screen allows at its ratio — the pins sit in percent of it, so they hold wherever it lands.
  protected readonly frame = computed(() => {
    const extent = this._extent();
    return extent && { ratio: `${extent.width} / ${extent.height}`, width: `min(100vw, ${(100 * extent.width) / extent.height}vh)` };
  });
  // Read at each opening, the chronicler baptising between two chapters: what the picture shows is the gazetteer as it stands.
  protected readonly places = httpResource<Places>(() => PLACES_FILE);
  // The gazetteer's named entries alone, each as a chapter up to the one read has named it — a later baptism is not yet known here.
  protected readonly pins = computed((): MapPin[] => {
    const extent = this._extent();
    const places = this.places.hasValue() ? this.places.value() : undefined;
    if (!extent || !places) return [];
    const chapter = Number(this._chronicler.currentChapter()?.slug.slice(1) ?? 0);
    const isKnown = (given: string): boolean => given !== '' && Number(given.slice(1)) <= chapter;
    const areas = (kind: 'island' | 'lake', book: Record<string, PlaceArea>): MapPin[] => {
      const named = Object.entries(book).filter(([, entry]) => isKnown(entry.chapter));
      const fontSize = this._sizer(kind, named.map(([, entry]) => entry.size));
      return named.map(([id, entry]) => ({
        ...this._at(entry.centroid, extent), fontSize: fontSize(entry.size), key: `${kind}-${id}`, kind, name: entry.name, size: entry.size,
      }));
    };

    return [
      ...areas('island', places.islands),
      ...areas('lake', places.lakes),
      ...Object.entries(places.places)
        .filter(([, spot]) => isKnown(spot.chapter))
        .map(([name, spot]): MapPin => ({ ...this._at(spot.centroid, extent), key: `spot-${name}`, kind: 'spot', name, spotKind: spot.kind })),
    ];
  });

  protected readonly measure = (event: Event): void => {
    const picture = event.target as HTMLImageElement;
    this._extent.set({ height: picture.naturalHeight, width: picture.naturalWidth });
  };

  // A name grows with the root of its extent — the width a land spans, not its area —, from the smallest named of its kind to the largest, in `cqw`.
  private readonly _sizer = (kind: 'island' | 'lake', sizes: number[]): (size: number) => number => {
    const [low, high] = kind === 'island' ? [0.8, 1.6] : [0.7, 1];
    const roots = sizes.map(size => Math.sqrt(size));
    const [least, most] = [Math.min(...roots), Math.max(...roots)];
    return size => most === least ? high : low + ((Math.sqrt(size) - least) / (most - least)) * (high - low);
  };

}
