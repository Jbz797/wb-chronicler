import { Component, computed, effect, ElementRef, inject, input, viewChild } from '@angular/core';

import { TranslatePipe, TranslateService } from '@ngx-translate/core';

import { DEATH_CAUSES } from '../../../constants';
import { ActorSpriteHelpers, LabelHelpers } from '../../../helpers';
import { Mourned } from '../../../interfaces';
import { RegistryService } from '../../../services';

@Component({
  selector: 'app-tombstone',
  imports: [TranslatePipe],
  templateUrl: './tombstone.component.html',
  styleUrl: './tombstone.component.scss',
})
export class TombstoneComponent {

  private readonly _registry = inject(RegistryService);
  private readonly _translate = inject(TranslateService);

  public readonly mourned = input.required<Mourned>();

  // His registry entry, which keeps a dead body's look, sex and year of death.
  protected readonly person = computed(() => this._registry.persons()[String(this.mourned().id)]);
  // A death nobody dealt, cut as a phrase in the dead one's gender — « other » for the causes the deaths table files there (ash fever, none, a change of body).
  protected readonly cause = computed(() => {
    const cause = DEATH_CAUSES.find(c => c.key === this.mourned().cause)?.key ?? 'other';
    return LabelHelpers.gendered(this._translate, `ui_tombstone_${cause}`, this.person()?.sex);
  });
  // « Slain by », in the dead one's own gender where the tongue inflects it.
  protected readonly slainBy = computed(() => LabelHelpers.gendered(this._translate, 'ui_slain_by', this.person()?.sex));

  private readonly _portrait = viewChild<unknown, ElementRef<HTMLCanvasElement>>('portrait', { read: ElementRef });

  constructor() {
    effect(() => {
      const canvas = this._portrait()?.nativeElement;
      const person = this.person(); // the plates' own sprite, carved larger
      if (canvas && person) ActorSpriteHelpers.paint(canvas, person).catch(() => {}); // a species we hold no sheet for leaves the niche empty
    });
  }

}
