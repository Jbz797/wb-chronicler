import { Component, computed, inject, input } from '@angular/core';

import { ChapterOverviewPanel } from '../../../../interfaces';
import { ChroniclerService } from '../../../../services';
import {
  AllianceTagComponent, CityTagComponent, ClanTagComponent, CultureTagComponent, FamilyTagComponent, KingdomTagComponent, LanguageTagComponent, PersonTagComponent,
  ReligionTagComponent, SubspeciesTagComponent,
} from '../tags';

// The chip a collapse header wears on its right — every panel but the world's names one body, and each body resolves its tag the same way, from `metadata`.
@Component({
  selector: 'app-panel-extra',
  imports: [
    AllianceTagComponent,
    CityTagComponent,
    ClanTagComponent,
    CultureTagComponent,
    FamilyTagComponent,
    KingdomTagComponent,
    LanguageTagComponent,
    PersonTagComponent,
    ReligionTagComponent,
    SubspeciesTagComponent,
  ],
  templateUrl: './panel-extra.component.html',
})
export class PanelExtraComponent {

  private readonly _chronicler = inject(ChroniclerService);

  public readonly panel = input.required<ChapterOverviewPanel>();

  // The tier's id + name, `null` where the chapter never named that body — the panel is then collapsed shut and wears no chip.
  protected readonly ref = computed(() => {
    const panel = this.panel();
    const meta = this._chronicler.currentChapter()?.meta;
    // The two panels that are no tier: the world names no body, and the wars are several — that one hangs a count of its own rather than a plate.
    if (!meta || panel === 'world-stats' || panel === 'wars') return null;
    return meta[panel]?.metadata ?? null;
  });

}
