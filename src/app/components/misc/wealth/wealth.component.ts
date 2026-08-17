import { Component, computed, inject, input } from '@angular/core';

import { NzDescriptionsModule } from 'ng-zorro-antd/descriptions';

import { CompactPipe, ExactPipe } from '../../../pipes';
import { ChroniclerService } from '../../../services';
import { RankedStatComponent } from '../ranked-stat/ranked-stat.component';

@Component({
  selector: 'app-wealth',
  imports: [CompactPipe, ExactPipe, NzDescriptionsModule, RankedStatComponent],
  templateUrl: './wealth.component.html',
})
export class WealthComponent {

  private readonly _chronicler = inject(ChroniclerService);

  public readonly source = input.required<'city' | 'kingdom'>();

  // Disjoint shares of `metadata.wealth`, so the cells sum to the total. Same four-way split either side: the crown or the mayor, then nobility, commoners, vaults.
  protected readonly shares = computed(() => {
    const meta = this._chronicler.currentChapter()?.meta;
    if (this.source() === 'city') {
      const c = meta?.city;
      if (!c) return [];
      return [
        { icon: 'professions/leader', label: 'Dirigeant', value: c.metadata.leader?.money },
        { icon: 'world/nobles', label: 'Nobles', value: c.population.nobles_money },
        { icon: 'world/population', label: 'Habitants', value: c.population.subjects_money },
        { icon: 'world/gold', label: 'Lingots', value: c.metadata.gold },
      ];
    }
    const k = meta?.kingdom;
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
