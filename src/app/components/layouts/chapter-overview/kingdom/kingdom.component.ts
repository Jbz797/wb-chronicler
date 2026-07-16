import { Component, computed, inject } from '@angular/core';

import { NzDescriptionsModule } from 'ng-zorro-antd/descriptions';

import { KingdomWar, RankedStatKind } from '../../../../interfaces';
import { ChroniclerService, RegistryService } from '../../../../services';
import { NewBadgeComponent, RankedStatComponent } from '../../../misc';
import { PersonTagComponent } from '../../../tags';

import { KingdomRelationsComponent } from './kingdom-relations/kingdom-relations.component';
import { KingdomWealthComponent } from './kingdom-wealth/kingdom-wealth.component';
import { WarCardComponent } from './war-card/war-card.component';

@Component({
  selector: 'app-kingdom',
  imports: [
    KingdomRelationsComponent,
    KingdomWealthComponent,
    NewBadgeComponent,
    NzDescriptionsModule,
    PersonTagComponent,
    RankedStatComponent,
    WarCardComponent,
  ],
  templateUrl: './kingdom.component.html',
})
export class KingdomComponent {

  private readonly _chronicler = inject(ChroniclerService);
  private readonly _registry = inject(RegistryService);

  protected readonly kingdom = computed(() => this._chronicler.currentChapter()?.meta.kingdom ?? null);
  // Founder sex: from the save when alive, else fall back to the person registry (registered in a past chapter), else '' → the tag drops the sex icon.
  protected readonly founderSex = computed(() => {
    const f = this.kingdom()?.metadata.founder;
    return f ? (f.sex ?? this._registry.persons()[String(f.id)]?.sex ?? '') : '';
  });
  // NEW badge on the king when the same featured kingdom crowned a different ruler since the previous chapter.
  protected readonly isNewKing = computed(() => {
    const current = this.kingdom()?.metadata;
    const previous = this._chronicler.previousChapter()?.meta.kingdom?.metadata;
    if (!current?.king || !previous?.king || current.id !== previous.id) return false;
    return current.king.id !== previous.king.id;
  });
  // Situational demographics surfaced only when present — kept out of the always-on rows to avoid noise.
  protected readonly optionalStats = computed<{ icon: string; label: string; stat: RankedStatKind }[]>(() => {
    const p = this.kingdom()?.population;
    if (!p) return [];
    const rows = [
      { icon: 'assets/img/world/sick.png', label: 'Malades', stat: 'sick' as const },
      { icon: 'assets/img/world/infected.png', label: 'Infectés', stat: 'infected' as const },
      { icon: 'assets/img/world/immortals.png', label: 'Immortels', stat: 'immortals' as const },
    ];
    return rows.filter(r => (p[r.stat] ?? 0) > 0);
  });
  // Set of war ids that surfaced this chapter (not present in the previous chapter's wars list).
  protected readonly startedWarIds = computed(() => {
    const wars: KingdomWar[] = this.kingdom()?.wars ?? [];
    const previousWars: KingdomWar[] = this._chronicler.previousChapter()?.meta.kingdom?.wars ?? [];
    const previousIds = new Set<number>(previousWars.map(w => w.id));
    return new Set<number>(wars.filter(w => !previousIds.has(w.id)).map(w => w.id));
  });

}
