import { Component, computed, effect, ElementRef, inject, input, viewChild } from '@angular/core';

import { NzTagModule } from 'ng-zorro-antd/tag';

import { CitySpriteHelpers, PaletteHelpers } from '../../../helpers';
import { RegistryService } from '../../../services';

@Component({
  selector: 'app-city-tag',
  imports: [NzTagModule],
  templateUrl: './city-tag.component.html',
})
export class CityTagComponent {

  private readonly _registry = inject(RegistryService);

  public readonly id = input.required<number>();
  public readonly medal = input(true); // Podium medal shown by default; hidden in the world « Palmarès » where the village is always the winner (gold, redundant).
  public readonly name = input.required<string>();

  // Visuals (palette, crown, size, species) come from the cities registry, kept fresh by each city/info.py run. `null` until the city is registered.
  protected readonly city = computed(() => this._registry.cities()[String(this.id())] ?? null);
  // Its crown's name hue — the plate text and the medallion — resolved rather than stored, as its subjects' tags do.
  protected readonly color = computed(() => PaletteHelpers.realmHue(this.city()?.kingdom));
  // And that crown's emblem tint, framing the plate — the same ring the crown and its subjects wear, so the three read as one holding.
  protected readonly ring = computed(() => PaletteHelpers.realmRing(this.city()?.kingdom));

  private readonly _crown = viewChild<ElementRef<HTMLCanvasElement>>('crown'); // absent until `@if (city())` has drawn the plate

  constructor() {
    effect(() => {
      const canvas = this._crown()?.nativeElement;
      const city = this.city();
      if (canvas && city) CitySpriteHelpers.paint(canvas, city).catch(() => {}); // an entry without the crown fields leaves it collapsed
    });
  }

}
