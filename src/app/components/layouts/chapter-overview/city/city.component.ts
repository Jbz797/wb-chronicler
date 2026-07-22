import { Component, computed, inject } from '@angular/core';

import { NzDescriptionsModule } from 'ng-zorro-antd/descriptions';

import { RankedStatKind } from '../../../../interfaces';
import { ChroniclerService } from '../../../../services';
import { BreakdownComponent, NewBadgeComponent, RankedStatComponent, WealthComponent } from '../../../misc';
import { PersonTagComponent } from '../../../tags';

@Component({
  selector: 'app-city',
  imports: [
    BreakdownComponent,
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

  protected readonly city = computed(() => this._chronicler.currentChapter()?.meta.city ?? null);
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

}
