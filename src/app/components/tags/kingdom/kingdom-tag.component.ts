import { Component, computed, inject, input } from '@angular/core';

import { NzTagModule } from 'ng-zorro-antd/tag';

import { SAVES_DIR } from '../../../constants';
import { RegistryService } from '../../../services';

@Component({
  selector: 'app-kingdom-tag',
  imports: [NzTagModule],
  templateUrl: './kingdom-tag.component.html',
})
export class KingdomTagComponent {

  private readonly _registry = inject(RegistryService);

  public readonly id = input.required<number>();
  public readonly name = input.required<string>();

  // WB banner, pre-generated per chapter (species background + icon, kingdom-tinted).
  protected readonly bannerSrc = computed(() => `${SAVES_DIR}/${this._registry.chapter()}/banners/k${this.id()}.png`);
  // Visuals (palette, species) come from the kingdoms registry, kept fresh by each world/info.py run. `null` until the kingdom is registered.
  protected readonly kingdom = computed(() => this._registry.kingdoms()[String(this.id())] ?? null);

}
