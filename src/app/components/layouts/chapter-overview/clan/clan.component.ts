import { Component, computed, inject } from '@angular/core';

import { NzDescriptionsModule } from 'ng-zorro-antd/descriptions';

import { BreakdownComponent, RankedStatComponent, TraitSummaryComponent } from '..';
import { RankedStatKind } from '../../../../interfaces';
import { ChroniclerService, RegistryService } from '../../../../services';
import { LeadersComponent } from '../leaders/leaders.component';
import { PersonTagComponent } from '../tags';

@Component({
  selector: 'app-clan',
  imports: [BreakdownComponent, LeadersComponent, NzDescriptionsModule, PersonTagComponent, RankedStatComponent, TraitSummaryComponent],
  templateUrl: './clan.component.html',
})
export class ClanComponent {

  private readonly _chronicler = inject(ChroniclerService);
  private readonly _registry = inject(RegistryService);

  protected readonly clan = computed(() => this._chronicler.currentChapter()?.meta.clan ?? null);
  protected readonly heirSex = computed(() => this._registry.persons()[String(this.clan()?.metadata.heir?.id)]?.sex ?? '');
  // WB writes these only once the clan has scored on them, so a row appears the year it first matters — same rule as the lineage's.
  protected readonly lifetimeStats = computed<{ icon: string; inverted: boolean; label: string; stat: RankedStatKind }[]>(() => {
    const m = this.clan()?.metadata;
    if (!m) return [];
    const rows = [
      { icon: 'assets/img/world/deaths.png', inverted: true, label: 'Morts', shown: !!m.deaths, stat: 'deaths' as const },
      { icon: 'assets/img/stats/kills.png', inverted: false, label: 'Tués', shown: !!m.kills, stat: 'kills' as const },
      { icon: 'assets/img/world/books.png', inverted: false, label: 'Livres écrits', shown: !!m.books_written, stat: 'books_written' as const },
    ];
    return rows.filter(r => r.shown).map(({ icon, inverted, label, stat }) => ({ icon, inverted, label, stat }));
  });

}
