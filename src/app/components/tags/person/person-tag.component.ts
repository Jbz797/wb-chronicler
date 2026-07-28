import { Component, computed, inject, input } from '@angular/core';

import { NzTagModule } from 'ng-zorro-antd/tag';

import { PaletteHelpers } from '../../../helpers';
import { RegistryService } from '../../../services';
import { ActorPortraitComponent } from '../../misc';

@Component({
  selector: 'app-person-tag',
  imports: [ActorPortraitComponent, NzTagModule],
  templateUrl: './person-tag.component.html',
})
export class PersonTagComponent {

  private readonly _registry = inject(RegistryService);

  public readonly id = input.required<number>();
  public readonly name = input.required<string>();

  // Species/sex/profession badge/dead come from the person registry, kept fresh by actor/city/kingdom info.py. `null` until the person is registered.
  protected readonly person = computed(() => this._registry.persons()[String(this.id())] ?? null);
  // Their realm's own name hue — a subject reads as belonging to that crown, exactly as its `[k]` tag does.
  protected readonly color = computed(() => PaletteHelpers.realmHue(this.person()?.kingdom));

}
