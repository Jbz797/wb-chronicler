import { Component, computed, inject, input } from '@angular/core';

import { NzTagModule } from 'ng-zorro-antd/tag';

import { PaletteHelpers } from '../../../helpers';
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

  // Visuals (palette, plate, size, species) come from the cities registry, kept fresh by each city/info.py run. `null` until the city is registered.
  protected readonly city = computed(() => this._registry.cities()[String(this.id())] ?? null);
  // Its crown's name hue — the plate text and the medallion — resolved rather than stored, as its subjects' tags do.
  protected readonly color = computed(() => PaletteHelpers.realmText(this.city()?.kingdom));
  // WB's own settlement nameplate: the gold-studded slab for a seat, the plain stone one for the rest. Falls back to the plain one for an unregistered city.
  protected readonly plate = computed(() => `url('assets/img/nameplates/${this.city()?.plate === 'capital' ? 'capital' : 'city'}.png')`);

}
