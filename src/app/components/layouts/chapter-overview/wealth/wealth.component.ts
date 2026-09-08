import { Component, computed, inject, input } from '@angular/core';

import { NzDescriptionsModule } from 'ng-zorro-antd/descriptions';
import { NzTooltipModule } from 'ng-zorro-antd/tooltip';

import { TranslatePipe } from '@ngx-translate/core';

import { PresentDirective } from '../../../../directives';
import { CompactPipe, ExactPipe } from '../../../../pipes';
import { ChroniclerService } from '../../../../services';
import { RankedStatComponent } from '../ranked-stat/ranked-stat.component';

@Component({
  selector: 'app-wealth',
  imports: [CompactPipe, ExactPipe, NzDescriptionsModule, NzTooltipModule, PresentDirective, RankedStatComponent, TranslatePipe],
  templateUrl: './wealth.component.html',
})
export class WealthComponent {

  private readonly _chronicler = inject(ChroniclerService);

  public readonly source = input.required<'city' | 'kingdom'>();

  // Python trims the ratio under `MIN_PER_CAPITA_UNITS`, where the divisor speaks louder than the body — `undefined` drops the row rather than printing a 0.
  protected readonly perCapita = computed(() => {
    const meta = this._chronicler.currentChapter()?.meta;
    return this.source() === 'city' ? meta?.city?.population.wealth_per_capita : meta?.kingdom?.population.wealth_per_capita;
  });
  // Disjoint shares of `metadata.wealth`, so the cells sum to the total. Same four-way split either side: the crown or the mayor, then nobility, commoners, vaults.
  protected readonly shares = computed(() => {
    const meta = this._chronicler.currentChapter()?.meta;
    if (this.source() === 'city') {
      const c = meta?.city;
      if (!c) return [];
      return [
        { icon: 'professions/leader', label: 'ui_ruler', value: c.metadata.leader?.money },
        { icon: 'world/nobles', label: 'ui_nobles', value: c.population.nobles_money },
        { icon: 'world/population', label: 'ui_inhabitants', value: c.population.subjects_money },
        { icon: 'world/gold', label: 'ui_ingots', value: c.metadata.gold },
      ];
    }
    const k = meta?.kingdom;
    if (!k) return [];
    // `undefined` renders as `—`: on chapters predating the split the share is unknown, not zero (those coins fall back into the subjects' cell).
    return [
      { icon: 'professions/king', label: 'ui_lord', value: k.metadata.king?.money },
      { icon: 'world/nobles', label: 'ui_nobles', value: k.population.nobles_money },
      { icon: 'world/population', label: 'ui_inhabitants', value: k.population.subjects_money },
      { icon: 'world/gold', label: 'ui_ingots', value: k.metadata.gold },
    ];
  });

}
