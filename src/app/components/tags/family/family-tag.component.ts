import { Component, computed, inject, input } from '@angular/core';

import { NzTagModule } from 'ng-zorro-antd/tag';

import { PaletteHelpers } from '../../../helpers';
import { RegistryService } from '../../../services';

@Component({
  selector: 'app-family-tag',
  imports: [NzTagModule],
  templateUrl: './family-tag.component.html',
})
export class FamilyTagComponent {

  private readonly _registry = inject(RegistryService);

  public readonly id = input.required<number>();
  public readonly name = input.required<string>();

  // The frame is worn as a 9-sliced border rather than drawn, so the tag stretches to its name instead of hanging a fixed portrait.
  protected readonly border = computed(() => this._sprite('frame'));
  // Its corner volutes overflow that slice, so they ride on a second layer — see the `::after` rule in `styles.scss`.
  protected readonly corner = computed(() => this._sprite('corner'));
  // Frame, backing hue and founding species come from the families registry, rebuilt each chapter. `null` until the lineage is registered.
  protected readonly family = computed(() => this._registry.families()[String(this.id())] ?? null);
  // A lineage carries its own fill, so its ink is chosen against that fill rather than inherited from a crown.
  protected readonly ink = computed(() => PaletteHelpers.readableOn(this.family()?.bg_color));

  // Both layers hang off the same frame number — `null` until the lineage is registered, which drops the `framed` class with them.
  private _sprite(kind: 'corner' | 'frame'): string | null {
    const frame = this.family()?.frame;
    return frame === undefined ? null : `url(assets/img/families/${kind}_${String(frame).padStart(2, '0')}.png)`;
  }

}
