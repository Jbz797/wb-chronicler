import { Component, computed, effect, ElementRef, inject, input, viewChild } from '@angular/core';

import { NzTagModule } from 'ng-zorro-antd/tag';

import { ANONYMOUS_NAME } from '../../../constants';
import { ActorSpriteHelpers, PaletteHelpers } from '../../../helpers';
import { RegistryService } from '../../../services';

@Component({
  selector: 'app-person-tag',
  imports: [NzTagModule],
  templateUrl: './person-tag.component.html',
})
export class PersonTagComponent {

  private readonly _registry = inject(RegistryService);

  public readonly id = input.required<number>();
  public readonly name = input.required<string | undefined>(); // absent on 42 % of WB's actors, but always bound — a silent « Anonyme » would hide a forgotten one

  // Species/sex/profession badge/dead come from the person registry, kept fresh by actor/city/kingdom info.py. `null` until the person is registered.
  protected readonly person = computed(() => this._registry.persons()[String(this.id())] ?? null);
  // Their realm's own name hue — a subject reads as belonging to that crown, exactly as its `[k]` tag does.
  protected readonly color = computed(() => PaletteHelpers.realmText(this.person()?.kingdom));
  // What the plate prints: their name, or the stand-in where WB never gave them one — the row still belongs, only the soul in it went unrecorded.
  protected readonly label = computed(() => this.name() ?? ANONYMOUS_NAME);
  // And its emblem tint around the plate — the second half of that belonging, shared with the crown's own tag and its villages'.
  protected readonly ring = computed(() => PaletteHelpers.realmRing(this.person()?.kingdom));

  private readonly _portrait = viewChild<ElementRef<HTMLCanvasElement>>('portrait'); // absent until `@if (person())` has drawn the plate

  constructor() {
    effect(() => {
      const canvas = this._portrait()?.nativeElement;
      const person = this.person();
      if (canvas && person) ActorSpriteHelpers.paint(canvas, person).catch(() => {}); // a species we hold no sheet for leaves it collapsed
    });
  }

}
