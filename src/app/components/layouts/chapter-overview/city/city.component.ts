import { Component, computed, inject } from '@angular/core';

import { NzDescriptionsModule } from 'ng-zorro-antd/descriptions';

import { RankedStatKind } from '../../../../interfaces';
import { ChroniclerService, RegistryService } from '../../../../services';
import { BreakdownComponent, InventoryComponent, NewBadgeComponent, RankedStatComponent, WealthComponent } from '../../../misc';
import { PersonTagComponent } from '../../../tags';

@Component({
  selector: 'app-city',
  imports: [
    BreakdownComponent,
    InventoryComponent,
    NewBadgeComponent,
    NzDescriptionsModule,
    PersonTagComponent,
    RankedStatComponent,
    WealthComponent,
  ],
  templateUrl: './city.component.html',
})
export class CityComponent {

  private readonly _chronicler = inject(ChroniclerService);
  private readonly _registry = inject(RegistryService);

  protected readonly city = computed(() => this._chronicler.currentChapter()?.meta.city ?? null);
  protected readonly heirSex = computed(() => this._registry.persons()[String(this.city()?.metadata.heir?.id)]?.sex ?? '');
  protected readonly inventoryEntries = computed(() => {
    const inventory = this.city()?.inventory ?? {};
    return Object.entries(inventory).map(([key, amount]) => ({ amount, key }));
  });
  // NEW badge on the leader when the same featured city installed a different head since the previous chapter.
  protected readonly isNewLeader = computed(() => {
    const current = this.city()?.metadata;
    const previous = this._chronicler.previousChapter()?.meta.city?.metadata;
    if (!current?.leader || !previous?.leader || current.id !== previous.id) return false;
    return current.leader.id !== previous.leader.id;
  });
  // Situational demographics surfaced only when present — kept out of the always-on rows to avoid noise.
  protected readonly optionalStats = computed<{ icon: string; label: string; stat: RankedStatKind }[]>(() => {
    const p = this.city()?.population;
    if (!p) return [];
    const rows = [
      { icon: 'assets/img/world/sick.png', label: 'Malades', stat: 'sick' as const },
      { icon: 'assets/img/world/infected.png', label: 'Infectés', stat: 'infected' as const },
      { icon: 'assets/img/world/immortals.png', label: 'Immortels', stat: 'immortals' as const },
    ];
    return rows.filter(r => (p[r.stat] ?? 0) > 0);
  });
  // Score dimensions with no other home in the panel — a row appears when Python emitted the field, so `attractivity` always shows, 0 and negatives included.
  protected readonly scoreStats = computed<{ icon: string; label: string; stat: RankedStatKind }[]>(() => {
    const c = this.city();
    if (!c) return [];
    const rows = [
      { icon: 'assets/img/world/population.png', label: 'Attractivité', shown: true, stat: 'attractivity' as const },
      { icon: 'assets/img/world/books_read.png', label: 'Rayonnement', shown: (c.metadata.book_reach ?? 0) > 0, stat: 'book_reach' as const },
      { icon: 'assets/img/stats/equipment_power.png', label: 'Équipements', shown: !!c.equipment.total, stat: 'equipment' as const },
    ];
    return rows.filter(r => r.shown).map(({ icon, label, stat }) => ({ icon, label, stat }));
  });

}
