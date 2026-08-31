import { Component, computed, inject } from '@angular/core';

import { NzDescriptionsModule } from 'ng-zorro-antd/descriptions';

import { BreakdownComponent, RankedStatComponent } from '..';
import { RankedStatKind } from '../../../../interfaces';
import { ChroniclerService } from '../../../../services';
import { LeadersComponent } from '../leaders/leaders.component';
import { KingdomTagComponent, PersonTagComponent } from '../tags';

@Component({
  selector: 'app-alliance',
  imports: [
    BreakdownComponent,
    KingdomTagComponent,
    LeadersComponent,
    NzDescriptionsModule,
    PersonTagComponent,
    RankedStatComponent,
  ],
  templateUrl: './alliance.component.html',
})
export class AllianceComponent {

  private readonly _chronicler = inject(ChroniclerService);

  protected readonly alliance = computed(() => this._chronicler.currentChapter()?.meta.alliance ?? null);
  // Display order, not a lone rule: WB drops the scored rows at zero, while the warriors standing is always there to print.
  protected readonly lifetimeStats = computed<{ icon: string; inverted: boolean; label: string; stat: RankedStatKind }[]>(() => {
    const meta = this.alliance()?.metadata;
    if (!meta) return [];
    const rows = [
      { icon: 'assets/img/world/births.png', inverted: false, label: 'Naissances', shown: meta.births !== undefined, stat: 'births' as const },
      { icon: 'assets/img/world/deaths.png', inverted: true, label: 'Morts', shown: meta.deaths !== undefined, stat: 'deaths' as const },
      { icon: 'assets/img/professions/warrior.png', inverted: false, label: 'Guerriers', shown: true, stat: 'warriors' as const },
      { icon: 'assets/img/stats/kills.png', inverted: false, label: 'Tués', shown: meta.kills !== undefined, stat: 'kills' as const },
    ];
    return rows.filter(r => r.shown).map(({ icon, inverted, label, stat }) => ({ icon, inverted, label, stat }));
  });

}
