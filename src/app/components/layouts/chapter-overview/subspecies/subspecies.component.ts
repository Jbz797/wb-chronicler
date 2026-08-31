import { Component, computed, inject } from '@angular/core';

import { NzDescriptionsModule } from 'ng-zorro-antd/descriptions';

import { BreakdownComponent, RankedStatComponent, TraitSummaryComponent } from '..';
import { BIOME_NAMES } from '../../../../constants';
import { RankedStatKind } from '../../../../interfaces';
import { SpeciesNamePipe } from '../../../../pipes';
import { ChroniclerService } from '../../../../services';
import { LeadersComponent } from '../leaders/leaders.component';

@Component({
  selector: 'app-subspecies',
  imports: [BreakdownComponent, LeadersComponent, NzDescriptionsModule, RankedStatComponent, SpeciesNamePipe, TraitSummaryComponent],
  templateUrl: './subspecies.component.html',
})
export class SubspeciesComponent {

  private readonly _chronicler = inject(ChroniclerService);

  protected readonly subspecies = computed(() => this._chronicler.currentChapter()?.meta.subspecies ?? null);
  // The biome's French label, WB's key standing in for an unknown one — `null` where it set no variant, which drops the row.
  protected readonly biomeName = computed(() => {
    const key = this.subspecies()?.metadata.biome;
    return key ? BIOME_NAMES[key] ?? key : null;
  });
  // WB writes these only once the biology has scored on them, so a row appears the year it first matters — same rule as the clan's and the lineage's.
  protected readonly lifetimeStats = computed<{ icon: string; inverted: boolean; label: string; stat: RankedStatKind }[]>(() => {
    const m = this.subspecies()?.metadata;
    if (!m) return [];
    const rows = [
      { icon: 'assets/img/world/births.png', inverted: false, label: 'Naissances', shown: !!m.births, stat: 'births' as const },
      { icon: 'assets/img/world/deaths.png', inverted: true, label: 'Morts', shown: !!m.deaths, stat: 'deaths' as const },
      { icon: 'assets/img/professions/warrior.png', inverted: false, label: 'Guerriers', shown: true, stat: 'warriors' as const },
      { icon: 'assets/img/stats/kills.png', inverted: false, label: 'Tués', shown: !!m.kills, stat: 'kills' as const },
    ];
    return rows.filter(r => r.shown).map(({ icon, inverted, label, stat }) => ({ icon, inverted, label, stat }));
  });

}
