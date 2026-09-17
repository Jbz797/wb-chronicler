import { Component, computed, inject, input } from '@angular/core';

import { NzDescriptionsModule } from 'ng-zorro-antd/descriptions';

import { TranslatePipe } from '@ngx-translate/core';

import { BreakdownSource } from '../../../../interfaces';
import { ChroniclerService } from '../../../../services';
import { CultureTagComponent, KingdomTagComponent, LanguageTagComponent, ReligionTagComponent, SubspeciesTagComponent } from '../tags';

@Component({
  selector: 'app-breakdown',
  imports: [CultureTagComponent, KingdomTagComponent, LanguageTagComponent, NzDescriptionsModule, ReligionTagComponent, SubspeciesTagComponent, TranslatePipe],
  templateUrl: './breakdown.component.html',
  styleUrl: './breakdown.component.scss',
})
export class BreakdownComponent {

  private readonly _chronicler = inject(ChroniclerService);

  public readonly source = input.required<BreakdownSource>();

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

}
