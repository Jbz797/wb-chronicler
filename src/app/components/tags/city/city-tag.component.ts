import { Component, computed, inject, input } from '@angular/core';

import { NzTagModule } from 'ng-zorro-antd/tag';

import { RegistryService } from '../../../services';

@Component({
  selector: 'app-city-tag',
  imports: [NzTagModule],
  templateUrl: './city-tag.component.html',
})
export class CityTagComponent {

  private readonly _registry = inject(RegistryService);

  public readonly id = input.required<number>();
  public readonly name = input.required<string>();

  // Visuals (palette, size, species, capital) come from the cities registry, kept fresh by each city/info.py run. `null` until the city is registered.
  protected readonly city = computed(() => this._registry.cities()[String(this.id())] ?? null);

}
