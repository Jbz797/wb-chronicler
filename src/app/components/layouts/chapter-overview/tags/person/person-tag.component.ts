import { Component, computed, effect, ElementRef, inject, input, viewChild } from '@angular/core';

import { NzTagModule } from 'ng-zorro-antd/tag';
import { NzTooltipModule } from 'ng-zorro-antd/tooltip';

import { TranslateService } from '@ngx-translate/core';

import { TruncatedDirective } from '../../../../../directives';
import { ActorSpriteHelpers, LabelHelpers, PaletteHelpers } from '../../../../../helpers';
import { ChroniclerService, RegistryService } from '../../../../../services';

@Component({
  selector: 'app-person-tag',
  imports: [NzTagModule, NzTooltipModule, TruncatedDirective],
  templateUrl: './person-tag.component.html',
})
export class PersonTagComponent {

  private readonly _chronicler = inject(ChroniclerService);
  private readonly _registry = inject(RegistryService);
  private readonly _translate = inject(TranslateService);

  public readonly id = input.required<number>();
  public readonly name = input.required<string | undefined>(); // absent on 42 % of WB's actors, but always bound — a silent « Anonyme » would hide a forgotten one

  // Species/sex/profession badge/dead come from the person registry, kept fresh by actor/city/kingdom info.py. `null` until the person is registered.
  protected readonly person = computed(() => this._registry.persons()[String(this.id())] ?? null);
  // Their blood tie, species and crown for the plate's tooltip, as the prose's plates tell them.
  protected readonly about = computed(() => {
    const person = this.person();
    return person ? LabelHelpers.personAbout(this._translate, person) : '';
  });
  // Their bond to the favourite — lover or best friend —, marked by the icon its own panel gives it; blood wears its own beside it.
  protected readonly bond = computed(() => this._chronicler.bondIcon(this.id()));
  // Their realm's own name hue — a subject reads as belonging to that crown, exactly as its `[k]` tag does.
  protected readonly color = computed(() => PaletteHelpers.realmText(this.person()?.kingdom));
  // Their species and crown on hover for anyone but the favourite, whose own panel already says both.
  protected readonly hint = computed(() => this.id() !== this._chronicler.currentChapter()?.meta.favorite?.metadata.id);
  // What the plate prints: their name, or the stand-in where WB never gave them one — the row still belongs, only the soul in it went unrecorded.
  protected readonly label = computed(() => this.name() ?? (this._translate.instant('anonymous') as string));
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
