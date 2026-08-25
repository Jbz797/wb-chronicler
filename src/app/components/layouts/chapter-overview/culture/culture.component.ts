import { Component, computed, inject } from '@angular/core';

import { NzDescriptionsModule } from 'ng-zorro-antd/descriptions';

import { RankedStatKind } from '../../../../interfaces';
import { ChroniclerService } from '../../../../services';
import { BreakdownComponent, RankedStatComponent, TraitSummaryComponent } from '../../../misc';
import { PersonTagComponent } from '../../../tags';
import { LeadersComponent } from '../leaders/leaders.component';

@Component({
  selector: 'app-culture',
  imports: [
    BreakdownComponent,
    LeadersComponent,
    NzDescriptionsModule,
    PersonTagComponent,
    RankedStatComponent,
    TraitSummaryComponent,
  ],
  templateUrl: './culture.component.html',
})
export class CultureComponent {

  private readonly _chronicler = inject(ChroniclerService);

  protected readonly culture = computed(() => this._chronicler.currentChapter()?.meta.culture ?? null);
  // A row appears the year its counter first matters: WB writes these only once scored on, and `books`, though in a block of its own, earns its place alike.
  protected readonly lifetimeStats = computed<{ icon: string; inverted: boolean; label: string; stat: RankedStatKind }[]>(() => {
    const m = this.culture()?.metadata;
    if (!m) return [];
    const rows = [
      { icon: 'assets/img/world/deaths.png', inverted: true, label: 'Morts', shown: !!m.deaths, stat: 'deaths' as const },
      { icon: 'assets/img/stats/kills.png', inverted: false, label: 'Tués', shown: !!m.kills, stat: 'kills' as const },
      { icon: 'assets/img/world/books.png', inverted: false, label: 'Livres', shown: !!this.culture()?.books.total, stat: 'books' as const },
    ];
    return rows.filter(r => r.shown).map(({ icon, inverted, label, stat }) => ({ icon, inverted, label, stat }));
  });

}
