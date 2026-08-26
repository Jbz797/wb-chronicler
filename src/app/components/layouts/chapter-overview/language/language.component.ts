import { Component, computed, inject } from '@angular/core';

import { NzDescriptionsModule } from 'ng-zorro-antd/descriptions';

import { BreakdownComponent, RankedStatComponent, TraitSummaryComponent } from '..';
import { RankedStatKind } from '../../../../interfaces';
import { ChroniclerService } from '../../../../services';
import { LeadersComponent } from '../leaders/leaders.component';
import { PersonTagComponent } from '../tags';

@Component({
  selector: 'app-language',
  imports: [
    BreakdownComponent,
    LeadersComponent,
    NzDescriptionsModule,
    PersonTagComponent,
    RankedStatComponent,
    TraitSummaryComponent,
  ],
  templateUrl: './language.component.html',
})
export class LanguageComponent {

  private readonly _chronicler = inject(ChroniclerService);

  protected readonly language = computed(() => this._chronicler.currentChapter()?.meta.language ?? null);
  // A row appears the year its counter first matters. `books` counts the volumes still standing, `written` every one ever penned in it — burnt ones included.
  protected readonly lifetimeStats = computed<{ icon: string; inverted: boolean; label: string; stat: RankedStatKind }[]>(() => {
    const m = this.language()?.metadata;
    if (!m) return [];
    const rows = [
      { icon: 'assets/img/world/deaths.png', inverted: true, label: 'Morts', shown: !!m.deaths, stat: 'deaths' as const },
      { icon: 'assets/img/stats/kills.png', inverted: false, label: 'Tués', shown: !!m.kills, stat: 'kills' as const },
      { icon: 'assets/img/world/books.png', inverted: false, label: 'Livres', shown: !!this.language()?.books.total, stat: 'books' as const },
      { icon: 'assets/img/world/books_written.png', inverted: false, label: 'Écrits', shown: !!m.written, stat: 'written' as const },
    ];
    return rows.filter(r => r.shown).map(({ icon, inverted, label, stat }) => ({ icon, inverted, label, stat }));
  });
  // WB's own three ways of counting a tongue's reach, and the only tier to split them: born to it, won from another, lost to one. Each drops before it is scored on.
  protected readonly speakerFlow = computed<{ icon: string; inverted: boolean; label: string; stat: RankedStatKind }[]>(() => {
    const m = this.language()?.metadata;
    if (!m) return [];
    const rows = [
      { icon: 'assets/img/world/births.png', inverted: false, label: 'Natifs', shown: !!m.native, stat: 'native' as const },
      { icon: 'assets/img/world/metamorphosis.png', inverted: false, label: 'Convertis', shown: !!m.converted, stat: 'converted' as const },
      { icon: 'assets/img/world/cities_rebelled.png', inverted: true, label: 'Perdus', shown: !!m.lost, stat: 'lost' as const },
    ];
    return rows.filter(r => r.shown).map(({ icon, inverted, label, stat }) => ({ icon, inverted, label, stat }));
  });

}
