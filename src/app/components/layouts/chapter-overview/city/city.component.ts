import { Component, computed, inject } from '@angular/core';

import { NzDescriptionsModule } from 'ng-zorro-antd/descriptions';

import { TranslatePipe } from '@ngx-translate/core';

import { BreakdownComponent, InventoryComponent, NewBadgeComponent, RankedStatComponent, WealthComponent } from '..';
import { NonZeroDirective, PresentDirective } from '../../../../directives';
import { RankedStatKind } from '../../../../interfaces';
import { ChroniclerService, RegistryService } from '../../../../services';
import { LeadersComponent } from '../leaders/leaders.component';
import { PersonTagComponent } from '../tags';

@Component({
  selector: 'app-city',
  imports: [
    BreakdownComponent,
    InventoryComponent,
    LeadersComponent,
    NewBadgeComponent,
    NonZeroDirective,
    NzDescriptionsModule,
    PersonTagComponent,
    PresentDirective,
    RankedStatComponent,
    TranslatePipe,
    WealthComponent,
  ],
  templateUrl: './city.component.html',
})
export class CityComponent {

  private readonly _chronicler = inject(ChroniclerService);
  private readonly _registry = inject(RegistryService);

  protected readonly city = computed(() => this._chronicler.currentChapter()?.meta.city ?? null);
  protected readonly heirSex = computed(() => this._registry.persons()[String(this.city()?.metadata.heir?.id)]?.sex ?? '');
  // NEW badge on the leader when the same featured city installed a different head since the previous chapter.
  protected readonly isNewHeir = computed(() => {
    const current = this.city()?.metadata;
    const previous = this._chronicler.previousChapter()?.meta.city?.metadata;
    return !!current?.heir && !!previous?.heir && current.id === previous.id && current.heir.id !== previous.heir.id;
  });
  protected readonly isNewLeader = computed(() => {
    const current = this.city();
    const previous = this._chronicler.previousChapter()?.meta.city;
    return !!current?.rulers && !!previous?.rulers && current.metadata.id === previous.metadata.id && current.rulers[0].id !== previous.rulers[0].id;
  });
  // Situational demographics surfaced only when present — kept out of the always-on rows to avoid noise.
  protected readonly optionalStats = computed<{ icon: string; label: string; stat: RankedStatKind }[]>(() => {
    const p = this.city()?.population;
    if (!p) return [];
    const rows = [
      { icon: 'assets/img/world/sick.png', label: 'ui_sick', stat: 'sick' as const },
      { icon: 'assets/img/world/infected.png', label: 'ui_infected', stat: 'infected' as const },
      { icon: 'assets/img/world/immortals.png', label: 'ui_immortals', stat: 'immortals' as const },
    ];
    return rows.filter(r => (p[r.stat] ?? 0) > 0);
  });
  // Score dimensions with no other home in the panel — a row appears where the value is not 0, `attractivity` showing its negatives all the same.
  protected readonly scoreStats = computed<{ icon: string; label: string; stat: RankedStatKind }[]>(() => {
    const c = this.city();
    if (!c) return [];
    const rows = [
      { icon: 'assets/img/world/population.png', label: 'ui_attractiveness', shown: c.metadata.attractivity !== 0, stat: 'attractivity' as const },
      { icon: 'assets/img/world/books_read.png', label: 'ui_reach', shown: (c.metadata.book_reach ?? 0) > 0, stat: 'book_reach' as const },
      { icon: 'assets/img/world/books.png', label: 'ui_books', shown: !!c.books.total, stat: 'books' as const },
      { icon: 'assets/img/stats/equipment_power.png', label: 'ui_racks', shown: !!c.gear.total, stat: 'gear' as const },
    ];
    return rows.filter(r => r.shown).map(({ icon, label, stat }) => ({ icon, label, stat }));
  });

}
