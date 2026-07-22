import { Component, computed, inject, input } from '@angular/core';

import { NzTagModule } from 'ng-zorro-antd/tag';

import { SPECIES_COLORS } from '../../../constants';
import { RegistryService } from '../../../services';

@Component({
  selector: 'app-person-tag',
  imports: [NzTagModule],
  templateUrl: './person-tag.component.html',
})
export class PersonTagComponent {

  private readonly _registry = inject(RegistryService);

  public readonly id = input.required<number>();
  public readonly name = input.required<string>();

  // Species/sex/profession badge/dead come from the person registry, kept fresh by actor/city/kingdom info.py. `null` until the person is registered.
  protected readonly person = computed(() => this._registry.persons()[String(this.id())] ?? null);
  protected readonly color = computed(() => SPECIES_COLORS[this.person()?.asset_id ?? ''] ?? null);

}
