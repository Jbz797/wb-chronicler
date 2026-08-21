import { Component, computed, inject, input } from '@angular/core';

import { NzDescriptionsModule } from 'ng-zorro-antd/descriptions';

import { BreakdownSource } from '../../../interfaces';
import { SpeciesNamePipe } from '../../../pipes';
import { ChroniclerService } from '../../../services';
import { CultureTagComponent, KingdomTagComponent, LanguageTagComponent, ReligionTagComponent, SubspeciesTagComponent } from '../../tags';

@Component({
  selector: 'app-breakdown',
  imports: [
    CultureTagComponent, KingdomTagComponent, LanguageTagComponent, NzDescriptionsModule, ReligionTagComponent, SpeciesNamePipe, SubspeciesTagComponent,
  ],
  templateUrl: './breakdown.component.html',
  styleUrl: './breakdown.component.scss',
})
export class BreakdownComponent {

  private readonly _chronicler = inject(ChroniclerService);

  public readonly source = input.required<BreakdownSource>();

  protected readonly breakdown = computed(() => this._chronicler.currentChapter()?.meta[this.source()]?.breakdown ?? null);
  // The most-represented entry of each dimension — the table shows the leader, the chronicler keeps the full top-3. `null` for a dimension with no data.
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

  // A dimension the whole body shares says nothing the row does not already say — the share prints only where there is something to share.
  protected share = (pct: number): string => pct < 100 ? `• ${pct}%` : '';

}
