import { Component, computed, inject } from '@angular/core';

import { NzDescriptionsModule } from 'ng-zorro-antd/descriptions';

import { KingdomWar, RankedStatKind } from '../../../../interfaces';
import { ChroniclerService, RegistryService } from '../../../../services';
import { BreakdownComponent, NewBadgeComponent, RankedStatComponent, WealthComponent } from '../../../misc';
import { CityTagComponent, PersonTagComponent } from '../../../tags';

import { KingdomAllianceComponent } from './kingdom-alliance/kingdom-alliance.component';
import { KingdomRelationsComponent } from './kingdom-relations/kingdom-relations.component';
import { WarCardComponent } from './war-card/war-card.component';

@Component({
  selector: 'app-kingdom',
  imports: [
    BreakdownComponent,
    CityTagComponent,
    KingdomAllianceComponent,
    KingdomRelationsComponent,
    NewBadgeComponent,
    NzDescriptionsModule,
    PersonTagComponent,
    RankedStatComponent,
    WarCardComponent,
    WealthComponent,
  ],
  templateUrl: './kingdom.component.html',
})
export class KingdomComponent {

  private readonly _chronicler = inject(ChroniclerService);
  private readonly _registry = inject(RegistryService);

  protected readonly kingdom = computed(() => this._chronicler.currentChapter()?.meta.kingdom ?? null);
  protected readonly heirSex = computed(() => this._registry.persons()[String(this.kingdom()?.metadata.heir?.id)]?.sex ?? '');
  // NEW badge on the king when the same featured kingdom crowned a different ruler since the previous chapter.
  protected readonly isNewKing = computed(() => {
    const current = this.kingdom()?.metadata;
    const previous = this._chronicler.previousChapter()?.meta.kingdom?.metadata;
    if (!current?.king || !previous?.king || current.id !== previous.id) return false;
    return current.king.id !== previous.king.id;
  });
  // Drives the « Reine/Roi » descriptions title — the registry holds it, `king` being emitted as `{id, name}`.
  protected readonly kingSex = computed(() => this._registry.persons()[String(this.kingdom()?.metadata.king?.id)]?.sex ?? '');
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
  // Score dimensions with no other home in the panel — Python omits each at 0, so a row appears only once the realm has earned it.
  protected readonly scoreStats = computed<{ icon: string; label: string; stat: RankedStatKind }[]>(() => {
    const m = this.kingdom()?.metadata;
    if (!m) return [];
    const rows = [
      { icon: 'assets/img/world/cultures.png', label: 'Traits culturels', stat: 'culture_traits' as const },
      { icon: 'assets/img/world/foundings.png', label: 'Fondations', stat: 'foundings' as const },
      { icon: 'assets/img/world/books_read.png', label: 'Rayonnement', stat: 'book_reach' as const },
      { icon: 'assets/img/world/wars.png', label: 'Guerres gagnées', stat: 'wars_won' as const },
    ];
    return rows.filter(r => (m[r.stat] ?? 0) > 0);
  });
  // Set of war ids that surfaced this chapter (not present in the previous chapter's wars list).
  protected readonly startedWarIds = computed(() => {
    const wars: KingdomWar[] = this.kingdom()?.wars ?? [];
    const previousWars: KingdomWar[] = this._chronicler.previousChapter()?.meta.kingdom?.wars ?? [];
    const previousIds = new Set<number>(previousWars.map(w => w.id));
    return new Set<number>(wars.filter(w => !previousIds.has(w.id)).map(w => w.id));
  });

}
