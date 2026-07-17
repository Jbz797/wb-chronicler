import { Component, computed, inject } from '@angular/core';

import { NzDescriptionsModule } from 'ng-zorro-antd/descriptions';

import { ChroniclerService } from '../../../../../services';
import { RankedStatComponent } from '../../../../misc';
import { KingdomTagComponent } from '../../../../tags';

@Component({
  selector: 'app-kingdom-alliance',
  imports: [KingdomTagComponent, NzDescriptionsModule, RankedStatComponent],
  templateUrl: './kingdom-alliance.component.html',
})
export class KingdomAllianceComponent {

  private readonly _chronicler = inject(ChroniclerService);

  // `null` for an unaligned kingdom — 10 of 16 here — which drops the whole table.
  protected readonly alliance = computed(() => this._chronicler.currentChapter()?.meta.kingdom?.alliance ?? null);
  // The most-represented entry of each dimension — the table shows only the leader, the chronicler keeps the full top-3. `null` for an empty dimension.
  protected readonly tops = computed(() => {
    const b = this.alliance()?.breakdown;
    return {
      culture: b?.cultures?.[0] ?? null,
      language: b?.languages?.[0] ?? null,
      religion: b?.religions?.[0] ?? null,
      species: b?.species[0] ?? null,
      subspecies: b?.subspecies[0] ?? null,
    };
  });

}
