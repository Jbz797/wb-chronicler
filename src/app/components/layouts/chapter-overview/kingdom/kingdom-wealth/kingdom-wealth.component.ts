import { Component, computed, inject } from '@angular/core';

import { NzDescriptionsModule } from 'ng-zorro-antd/descriptions';

import { CompactPipe } from '../../../../../pipes';
import { ChroniclerService } from '../../../../../services';
import { RankedStatComponent } from '../../../../misc';

@Component({
  selector: 'app-kingdom-wealth',
  imports: [CompactPipe, NzDescriptionsModule, RankedStatComponent],
  templateUrl: './kingdom-wealth.component.html',
})
export class KingdomWealthComponent {

  private readonly _chronicler = inject(ChroniclerService);

  protected readonly kingdom = computed(() => this._chronicler.currentChapter()?.meta.kingdom ?? null);
  // Disjoint shares of `metadata.wealth` — crown, nobility, commoners, vaults — so the four cells sum to the total. Ranks stay Python-side, for the chronicler only.
  protected readonly shares = computed(() => {
    const k = this.kingdom();
    if (!k) return [];
    // `undefined` renders as `—`: on chapters predating the split the share is unknown, not zero (those coins fall back into the subjects' cell).
    return [
      { icon: 'professions/king', label: 'Seigneur', value: k.metadata.king?.money },
      { icon: 'world/nobles', label: 'Nobles', value: k.population.nobles_money },
      { icon: 'world/population', label: 'Habitants', value: k.population.subjects_money },
      { icon: 'world/gold', label: 'Lingots', value: k.metadata.gold },
    ];
  });

}
