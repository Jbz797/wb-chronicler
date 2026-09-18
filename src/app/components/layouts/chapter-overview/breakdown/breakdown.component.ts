import { Component, computed, inject, input } from '@angular/core';

import { NzDescriptionsModule } from 'ng-zorro-antd/descriptions';

import { TranslatePipe } from '@ngx-translate/core';

import { BreakdownLeader, PopulatedTier } from '../../../../interfaces';
import { ChroniclerService } from '../../../../services';
import { NewBadgeComponent } from '../new-badge/new-badge.component';
import { CultureTagComponent, KingdomTagComponent, LanguageTagComponent, ReligionTagComponent, SubspeciesTagComponent } from '../tags';

@Component({
  selector: 'app-breakdown',
  imports: [
    CultureTagComponent,
    KingdomTagComponent,
    LanguageTagComponent,
    NewBadgeComponent,
    NzDescriptionsModule,
    ReligionTagComponent,
    SubspeciesTagComponent,
    TranslatePipe,
  ],
  templateUrl: './breakdown.component.html',
  styleUrl: './breakdown.component.scss',
})
export class BreakdownComponent {

  private readonly _chronicler = inject(ChroniclerService);

  public readonly source = input.required<PopulatedTier>();

  protected readonly breakdown = computed(() => this._chronicler.currentChapter()?.meta[this.source()]?.breakdown ?? null);
  // Each dimension's leader, `null` where the chapter carries none — the runners-up and any leader at 100 % stay in `<tier>/info.py <id> breakdown`.
  protected readonly tops = computed(() => {
    const b = this.breakdown();
    return {
      culture: b?.cultures?.[0] ?? null,
      kingdom: b?.kingdoms?.[0] ?? null,
      language: b?.languages?.[0] ?? null,
      religion: b?.religions?.[0] ?? null,
      species: b?.species?.[0] ?? null, // a lineage carries none — it would only restate the species its `identity` already stamps
      subspecies: b?.subspecies?.[0] ?? null,
    };
  });

  private readonly _isNew = (now: BreakdownLeader | null, was?: BreakdownLeader): boolean => !!now && !!was && (now.asset_id ?? now.id) !== (was.asset_id ?? was.id);

  // Each dimension whose leader changed since the chapter before, for the same body — never a share that only moved, nor a row that has just risen.
  protected readonly renewed = computed(() => {
    const source = this.source();
    const before = this._chronicler.carriesOver(source) ? this._chronicler.previousChapter()?.meta[source]?.breakdown : undefined;
    const tops = this.tops();
    return {
      culture: this._isNew(tops.culture, before?.cultures?.[0]),
      kingdom: this._isNew(tops.kingdom, before?.kingdoms?.[0]),
      language: this._isNew(tops.language, before?.languages?.[0]),
      religion: this._isNew(tops.religion, before?.religions?.[0]),
      species: this._isNew(tops.species, before?.species?.[0]),
      subspecies: this._isNew(tops.subspecies, before?.subspecies?.[0]),
    };
  });

}
