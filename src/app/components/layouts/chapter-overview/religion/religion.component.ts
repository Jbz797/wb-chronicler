import { Component, computed, inject } from '@angular/core';

import { NzDescriptionsModule } from 'ng-zorro-antd/descriptions';

import { TranslatePipe } from '@ngx-translate/core';

import { BreakdownComponent, RankedStatComponent, TraitSummaryComponent } from '..';
import { PresentDirective } from '../../../../directives';
import { RankedStatKind } from '../../../../interfaces';
import { ChroniclerService } from '../../../../services';
import { LeadersComponent } from '../leaders/leaders.component';
import { PersonTagComponent } from '../tags';

@Component({
  selector: 'app-religion',
  imports: [
    BreakdownComponent,
    LeadersComponent,
    NzDescriptionsModule,
    PersonTagComponent,
    PresentDirective,
    RankedStatComponent,
    TraitSummaryComponent,
    TranslatePipe,
  ],
  templateUrl: './religion.component.html',
})
export class ReligionComponent {

  private readonly _chronicler = inject(ChroniclerService);

  protected readonly religion = computed(() => this._chronicler.currentChapter()?.meta.religion ?? null);
  // A row appears the year its counter first matters: WB writes these only once scored on, and `books`, though in a block of its own, earns its place alike.
  protected readonly lifetimeStats = computed<{ icon: string; inverted: boolean; label: string; stat: RankedStatKind }[]>(() => {
    const tier = this.religion();
    if (!tier) return [];
    const m = tier.metadata;
    const pop = tier.population;
    const rows = [
      { icon: 'assets/img/world/deaths.png', inverted: true, label: 'ui_deaths', shown: !!m.deaths, stat: 'deaths' as const },
      { icon: 'assets/img/professions/warrior.png', inverted: false, label: 'ui_warriors', shown: pop.warriors !== undefined, stat: 'warriors' as const },
      { icon: 'assets/img/stats/kills.png', inverted: false, label: 'ui_kills', shown: !!m.kills, stat: 'kills' as const },
      { icon: 'assets/img/world/books.png', inverted: false, label: 'ui_books', shown: !!this.religion()?.books.total, stat: 'books' as const },
    ];
    return rows.filter(r => r.shown).map(({ icon, inverted, label, stat }) => ({ icon, inverted, label, stat }));
  });

}
