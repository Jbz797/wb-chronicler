import { Component, computed, inject } from '@angular/core';

import { NzDescriptionsModule } from 'ng-zorro-antd/descriptions';

import { RankedStatKind } from '../../../../interfaces';
import { ChroniclerService, RegistryService } from '../../../../services';
import { BreakdownComponent, RankedStatComponent } from '../../../misc';
import { PersonTagComponent } from '../../../tags';

@Component({
  selector: 'app-family',
  imports: [BreakdownComponent, NzDescriptionsModule, PersonTagComponent, RankedStatComponent],
  templateUrl: './family.component.html',
})
export class FamilyComponent {

  private readonly _chronicler = inject(ChroniclerService);
  private readonly _registry = inject(RegistryService);

  protected readonly family = computed(() => this._chronicler.currentChapter()?.meta.family ?? null);
  // A founder is titled after her own sex — half of WB's are women, and the registry is the only place that survives, the family record keeping just a name.
  protected readonly founders = computed(() => {
    const persons = this._registry.persons();
    const title = (id: number): string => persons[String(id)]?.sex === 'female' ? 'Fondatrice' : 'Fondateur';
    return (this.family()?.metadata.founders ?? []).map(founder => ({ ...founder, label: title(founder.id) }));
  });
  // WB writes these only once the lineage has scored on them, so a row appears the year it first matters. Ordered births → deaths → kills, as the other tiers are.
  protected readonly lifetimeStats = computed<{ icon: string; inverted: boolean; label: string; stat: RankedStatKind }[]>(() => {
    const m = this.family()?.metadata;
    if (!m) return [];
    const rows = [
      { icon: 'assets/img/world/births.png', inverted: false, label: 'Naissances', shown: !!m.births, stat: 'births' as const },
      { icon: 'assets/img/world/deaths.png', inverted: true, label: 'Morts', shown: !!m.deaths, stat: 'deaths' as const },
      { icon: 'assets/img/stats/kills.png', inverted: false, label: 'Tués', shown: !!m.kills, stat: 'kills' as const },
    ];
    return rows.filter(r => r.shown).map(({ icon, inverted, label, stat }) => ({ icon, inverted, label, stat }));
  });

}
