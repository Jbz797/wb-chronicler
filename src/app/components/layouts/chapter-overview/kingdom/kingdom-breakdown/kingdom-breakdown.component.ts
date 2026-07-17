import { Component, computed, inject } from '@angular/core';

import { NzDescriptionsModule } from 'ng-zorro-antd/descriptions';

import { ChroniclerService } from '../../../../../services';

@Component({
  selector: 'app-kingdom-breakdown',
  imports: [NzDescriptionsModule],
  templateUrl: './kingdom-breakdown.component.html',
})
export class KingdomBreakdownComponent {

  private readonly _chronicler = inject(ChroniclerService);

  protected readonly breakdown = computed(() => this._chronicler.currentChapter()?.meta.kingdom?.breakdown ?? null);
  // The most-represented entry of each dimension — the table shows the leader, the chronicler keeps the full top-3. `null` for a dimension with no data.
  protected readonly tops = computed(() => {
    const b = this.breakdown();
    return {
      culture: b?.cultures?.[0] ?? null,
      language: b?.languages?.[0] ?? null,
      religion: b?.religions?.[0] ?? null,
      species: b?.species[0] ?? null,
      subspecies: b?.subspecies[0] ?? null,
    };
  });

}
